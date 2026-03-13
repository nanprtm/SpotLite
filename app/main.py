import asyncio
import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

load_dotenv()

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

    session: StageSession | None = None

    async def send_to_client(msg: dict):
        await ws.send_json(msg)

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "start_session":
                config = msg.get("config", {})
                session = StageSession(config=config, send_to_client=send_to_client)
                try:
                    await session.start()
                    await ws.send_json({"type": "session_started"})
                except Exception as e:
                    await ws.send_json({"type": "error", "message": f"Failed to start session: {str(e)}"})
                    session = None

            elif msg_type == "audio" and session:
                audio_bytes = base64.b64decode(msg["data"])
                await session.send_audio(audio_bytes)

            elif msg_type == "photo" and session:
                photo_bytes = base64.b64decode(msg["data"])
                await session.send_photo(photo_bytes)

    except WebSocketDisconnect:
        pass
    finally:
        if session:
            await session.stop()


@app.get("/api/export/bom")
async def export_bom(items: str, budget: int = 25000000):
    """Export BOM as JSON. items is a JSON string of [{name, quantity}]."""
    item_list = json.loads(items)
    bom = generate_bom(item_list, budget)
    return bom
