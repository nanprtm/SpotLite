import asyncio
import base64
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from app.gemini_session import StageSession
from app.prices import generate_bom, load_materials

app = FastAPI(title="Stage Buddy")

STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/session")
async def websocket_session(ws: WebSocket):
    await ws.accept()
    logger.info("Browser WebSocket accepted")

    session: StageSession | None = None

    async def send_to_client(msg: dict):
        try:
            await ws.send_json(msg)
        except Exception as e:
            logger.error("Failed to send to browser: %s", e)

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")
            if msg_type != "audio":
                logger.info("Received message type: %s", msg_type)

            if msg_type == "start_session":
                config = msg.get("config", {})
                session = StageSession(config=config, send_to_client=send_to_client)
                await ws.send_json({"type": "session_started"})
                logger.info("Session config stored, Gemini will connect on first audio")

            elif msg_type == "audio" and session:
                audio_bytes = base64.b64decode(msg["data"])
                await session.send_audio(audio_bytes)

            elif msg_type == "photo" and session:
                photo_bytes = base64.b64decode(msg["data"])
                await session.send_photo(photo_bytes)

    except WebSocketDisconnect:
        logger.info("Browser WebSocket disconnected")
    except Exception as e:
        logger.error("WebSocket handler error: %s: %s", type(e).__name__, e)
    finally:
        if session:
            logger.info("Cleaning up Gemini session")
            await session.stop()


@app.get("/api/export/bom")
async def export_bom(items: str, budget: int = 25000000):
    """Export BOM as JSON. items is a JSON string of [{name, quantity}]."""
    item_list = json.loads(items)
    bom = generate_bom(item_list, budget)
    return bom
