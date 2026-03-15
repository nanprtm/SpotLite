"""FastAPI application for SpotLite using ADK Live API."""

import asyncio
import base64
import json
import logging
import uuid
import warnings
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from app.agent import root_agent, _load_base_stage, _materials_summary
from app.prices import generate_bom, load_materials
from app.prompts import build_system_instruction

# ── App Initialization ──────────────────────────────────────────

APP_NAME = "spotlite"

app = FastAPI(title="SpotLite")
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

session_service = InMemorySessionService()
runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=session_service)


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── WebSocket Endpoint ──────────────────────────────────────────


@app.websocket("/ws/session")
async def websocket_session(ws: WebSocket):
    await ws.accept()
    logger.info("Browser WebSocket accepted")

    # Wait for start_session message with config
    raw = await ws.receive_text()
    msg = json.loads(raw)
    if msg.get("type") != "start_session":
        await ws.close(code=1008, reason="Expected start_session")
        return

    config = msg.get("config", {})
    user_id = "director"
    session_id = str(uuid.uuid4())

    # Send helper for background tasks (image gen)
    async def send_to_client(msg: dict):
        try:
            await ws.send_json(msg)
        except Exception as e:
            logger.error("Failed to send to browser: %s", e)

    # Create ADK session with stage config in state
    base_stage_b64 = base64.b64encode(_load_base_stage()).decode()
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
        state={
            "budget": config.get("budget", 25_000_000),
            "stage_config": config,
            "base_stage_b64": base_stage_b64,
            "_send_to_client": send_to_client,
        },
    )

    # Override agent instruction with session-specific config
    root_agent.instruction = build_system_instruction(config, _materials_summary())

    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede"
                )
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        session_resumption=types.SessionResumptionConfig(),
    )

    live_request_queue = LiveRequestQueue()

    await ws.send_json({"type": "session_started"})
    logger.info("ADK session created: %s", session_id)

    # ── Upstream: Browser → ADK ──

    async def upstream_task():
        while True:
            message = await ws.receive()

            if "text" in message:
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "audio":
                    audio_bytes = base64.b64decode(data["data"])
                    live_request_queue.send_realtime(
                        types.Blob(
                            mime_type="audio/pcm;rate=16000",
                            data=audio_bytes,
                        )
                    )
                elif msg_type == "photo":
                    photo_bytes = base64.b64decode(data["data"])
                    # Store in session state for tools
                    adk_session = await session_service.get_session(
                        app_name=APP_NAME,
                        user_id=user_id,
                        session_id=session_id,
                    )
                    if adk_session:
                        adk_session.state["stage_photo_b64"] = data["data"]
                    # Send to Live API as video input
                    live_request_queue.send_realtime(
                        types.Blob(
                            mime_type="image/jpeg",
                            data=photo_bytes,
                        )
                    )
                    await ws.send_json({
                        "type": "transcript",
                        "role": "user",
                        "text": "[Stage photo captured]",
                    })

    # ── Downstream: ADK → Browser ──

    async def downstream_task():
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=live_request_queue,
            run_config=run_config,
        ):
            try:
                await _route_event(ws, event, user_id, session_id)
            except Exception as e:
                logger.error("Error routing event: %s", e)

    try:
        await asyncio.gather(upstream_task(), downstream_task())
    except WebSocketDisconnect:
        logger.info("Browser disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s: %s", type(e).__name__, e)
    finally:
        live_request_queue.close()
        logger.info("Session %s cleaned up", session_id)


async def _route_event(ws: WebSocket, event, user_id: str, session_id: str):
    """Translate ADK events into our frontend message protocol."""

    # Check for pending tool results in session state
    adk_session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if adk_session:
        pending_bom = adk_session.state.pop("_pending_bom", None)
        if pending_bom:
            await ws.send_json({
                "type": "bom",
                "items": pending_bom["items"],
                "total": pending_bom["total"],
                "budget": pending_bom["budget"],
                "remaining": pending_bom["remaining"],
            })

        pending_vendor = adk_session.state.pop("_pending_vendor_results", None)
        if pending_vendor:
            await ws.send_json({
                "type": "vendor_results",
                "query": pending_vendor.get("query", ""),
                "text": pending_vendor.get("text", ""),
                "sources": pending_vendor.get("sources", []),
            })

    # Input transcription (what the user said)
    if event.input_transcription and event.input_transcription.text:
        await ws.send_json({
            "type": "user_transcript",
            "text": event.input_transcription.text,
            "finished": getattr(event.input_transcription, "finished", True),
        })
        return

    # Output transcription (text version of assistant audio)
    if event.output_transcription and event.output_transcription.text:
        finished = getattr(event.output_transcription, "finished", False)
        await ws.send_json({
            "type": "assistant_transcript",
            "text": event.output_transcription.text,
            "finished": finished,
        })
        return

    if not event.content or not event.content.parts:
        return

    for part in event.content.parts:
        # Audio response
        if part.inline_data and part.inline_data.mime_type and "audio" in part.inline_data.mime_type:
            audio_b64 = base64.b64encode(part.inline_data.data).decode()
            await ws.send_json({"type": "audio", "data": audio_b64})

        # Text response — only show if NOT from the live audio model
        # (output_transcription already handles the text version of audio)
        elif part.text and event.author not in ("user", "spotlite"):
            await ws.send_json({
                "type": "transcript",
                "role": "assistant",
                "text": part.text,
            })


@app.get("/api/export/bom")
async def export_bom(items: str, budget: int = 25000000):
    """Export BOM as JSON. items is a JSON string of [{name, quantity}]."""
    item_list = json.loads(items)
    bom = generate_bom(item_list, budget)
    return bom
