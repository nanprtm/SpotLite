import asyncio
import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types
from app.prompts import build_system_instruction
from app.prices import load_materials, generate_bom

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _chat_log_path() -> Path:
    return LOG_DIR / f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"


class ConversationLog:
    """Writes a human-readable conversation log to a txt file."""

    def __init__(self):
        self.path = _chat_log_path()
        self._write(f"=== Stage Buddy Session — {datetime.now().isoformat()} ===\n")

    def _write(self, text: str):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def system(self, text: str):
        self._write(f"[{datetime.now().strftime('%H:%M:%S')}] SYSTEM: {text}")

    def assistant(self, text: str):
        self._write(f"[{datetime.now().strftime('%H:%M:%S')}] PAK PANGGUNG: {text}")

    def tool_call(self, name: str, args: str):
        self._write(f"[{datetime.now().strftime('%H:%M:%S')}] TOOL CALL: {name}({args})")

    def tool_result(self, name: str, result: str):
        self._write(f"[{datetime.now().strftime('%H:%M:%S')}] TOOL RESULT: {name} → {result}")

    def event(self, text: str):
        self._write(f"[{datetime.now().strftime('%H:%M:%S')}] EVENT: {text}")

_client = None

LIVE_MODEL = "gemini-live-2.5-flash-native-audio"
IMAGE_MODEL = "gemini-2.5-flash-image"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
    return _client

# Function declarations for the Live API
TOOLS = [
    {
        "function_declarations": [
            {
                "name": "generate_stage_image",
                "description": "Generate a visual mockup of the stage set based on the director's description. Call this when the director describes what they want on stage or asks for visual changes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Detailed description of the stage set to visualize, including all elements, their positions, colors, and materials. Be specific enough to generate a clear image.",
                        }
                    },
                    "required": ["description"],
                },
            },
            {
                "name": "generate_bom",
                "description": "Generate a bill of materials with real local prices for the stage set. Call this after generating a stage image to show the director the cost breakdown.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Material name (use Indonesian building material names, e.g., 'Triplek 9mm', 'Pipa PVC 3/4 inch')",
                                    },
                                    "quantity": {
                                        "type": "integer",
                                        "description": "Number of units needed",
                                    },
                                },
                                "required": ["name", "quantity"],
                            },
                            "description": "List of materials needed with quantities",
                        }
                    },
                    "required": ["items"],
                },
            },
        ]
    }
]


def _materials_summary() -> str:
    materials = load_materials()
    lines = []
    current_cat = None
    for m in sorted(materials, key=lambda x: x["category"]):
        if m["category"] != current_cat:
            current_cat = m["category"]
            lines.append(f"\n[{current_cat.upper()}]")
        lines.append(f"  - {m['name']}: Rp {m['price_idr']:,} {m['unit']}")
    return "\n".join(lines)


class StageSession:
    """Manages a Gemini Live session for one stage design project."""

    def __init__(self, config: dict, send_to_client):
        """
        config: {name, width, depth, height, budget}
        send_to_client: async callable to push messages to the WebSocket client
        """
        self.config = config
        self.send_to_client = send_to_client
        self.session = None
        self._context_manager = None
        self.stage_photo: bytes | None = None
        self._base_stage_image: bytes = self._load_base_stage()
        self._receive_task: asyncio.Task | None = None
        self._tool_call_in_progress = False
        self._image_generating = False
        self._conversation_history: list[str] = []
        self._last_image_description: str | None = None
        self._log = ConversationLog()
        self._log.system(f"Session created: {config}")

    @staticmethod
    def _load_base_stage() -> bytes:
        base_path = Path(__file__).parent / "static" / "stage.png"
        return base_path.read_bytes()

    def _build_context_summary(self) -> str:
        """Build a summary of prior conversation to inject on reconnect."""
        if not self._conversation_history and not self._last_image_description:
            return ""
        parts = ["\n\nCONVERSATION SO FAR (continue from where you left off, do NOT restart or re-introduce yourself):"]
        # Keep last 20 entries to avoid system instruction getting too long
        recent = self._conversation_history[-20:]
        for entry in recent:
            parts.append(f"- {entry}")
        if self._last_image_description:
            parts.append(f"\nLAST GENERATED IMAGE: {self._last_image_description}")
        parts.append("\nIMPORTANT: The director is continuing the same session. Do NOT greet them again or ask what concept they want. Continue the design conversation naturally.")
        return "\n".join(parts)

    async def connect(self):
        """Open the Gemini Live session. Called lazily on first audio/photo."""
        if self.session:
            return
        try:
            base_instruction = build_system_instruction(self.config, _materials_summary())
            system_instruction = base_instruction + self._build_context_summary()
            live_config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                    )
                ),
                system_instruction=types.Content(
                    parts=[types.Part(text=system_instruction)]
                ),
                tools=TOOLS,
            )
            self._log.event(f"Connecting to {LIVE_MODEL} (history: {len(self._conversation_history)} entries)")
            logger.info("Connecting to Gemini Live API with model=%s", LIVE_MODEL)
            self._context_manager = _get_client().aio.live.connect(
                model=LIVE_MODEL,
                config=live_config,
            )
            self.session = await self._context_manager.__aenter__()
            logger.info("Gemini Live session established successfully")
            self._receive_task = asyncio.create_task(self._receive_loop())
        except Exception as e:
            self.session = None
            await self.send_to_client({
                "type": "error",
                "message": f"Failed to start Gemini session: {str(e)}"
            })
            raise

    async def stop(self):
        if self._receive_task:
            self._receive_task.cancel()
        if self._context_manager:
            try:
                await self._context_manager.__aexit__(None, None, None)
            except Exception:
                pass

    async def send_audio(self, audio_bytes: bytes):
        if not self.session:
            await self.connect()
        if self.session and not self._tool_call_in_progress:
            try:
                await self.session.send_realtime_input(
                    audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
                )
            except Exception as e:
                logger.warning("send_audio error: %s", e)

    async def send_photo(self, photo_bytes: bytes):
        self.stage_photo = photo_bytes
        self._base_stage_image = None  # user photo takes priority
        if not self.session:
            await self.connect()
        if self.session and not self._tool_call_in_progress:
            try:
                await self.session.send_realtime_input(
                    video=types.Blob(data=photo_bytes, mime_type="image/jpeg")
                )
            except Exception as e:
                logger.warning("send_photo error: %s", e)

    async def _receive_loop(self):
        try:
            logger.info("Receive loop started, waiting for messages...")
            msg_count = 0
            async for msg in self.session.receive():
                msg_count += 1
                try:
                    # Handle audio response
                    if msg.server_content and msg.server_content.model_turn:
                        for part in msg.server_content.model_turn.parts:
                            if part.inline_data:
                                audio_b64 = base64.b64encode(part.inline_data.data).decode()
                                await self.send_to_client({
                                    "type": "audio",
                                    "data": audio_b64,
                                })
                            if part.text:
                                logger.info("Gemini text: %s", part.text[:100])
                                self._log.assistant(part.text)
                                self._conversation_history.append(f"Teman Panggung: {part.text[:200]}")
                                await self.send_to_client({
                                    "type": "transcript",
                                    "role": "assistant",
                                    "text": part.text,
                                })

                    # Handle function calls
                    if msg.tool_call:
                        for fc in msg.tool_call.function_calls:
                            logger.info("Tool call: %s(%s)", fc.name, str(fc.args)[:200])
                            self._log.tool_call(fc.name, str(fc.args)[:500])
                        await self._handle_tool_calls(msg.tool_call)

                    if msg.tool_call_cancellation:
                        logger.warning("Tool call cancelled by server")

                except Exception as e:
                    logger.error("Error processing msg #%d: %s: %s", msg_count, type(e).__name__, e)
                    await self.send_to_client({
                        "type": "error",
                        "message": f"Error processing message: {str(e)}"
                    })

            # Session ended normally — will reconnect with context on next audio
            logger.info("Gemini session ended after %d messages, context preserved for reconnect", msg_count)
            self._log.event(f"Session ended after {msg_count} messages, will reconnect with context")
            self._cleanup_session()

        except asyncio.CancelledError:
            logger.info("Receive loop cancelled")
        except Exception as e:
            logger.error("Receive loop exception: %s: %s", type(e).__name__, e)
            self._log.event(f"Session error: {type(e).__name__}: {e}")
            self._cleanup_session()
            await self.send_to_client({
                "type": "error",
                "message": f"Session error: {str(e)}"
            })

    def _cleanup_session(self):
        """Reset session state so next send_audio triggers a fresh connect."""
        self.session = None
        self._context_manager = None
        self._receive_task = None
        self._tool_call_in_progress = False

    async def _handle_tool_calls(self, tool_call):
        self._tool_call_in_progress = True
        function_responses = []

        for fc in tool_call.function_calls:
            if fc.name == "generate_stage_image":
                description = fc.args.get("description", "")

                # Block if an image is already generating
                if self._image_generating:
                    logger.info("Image generation blocked — already in progress")
                    function_responses.append(
                        types.FunctionResponse(
                            id=fc.id, name=fc.name,
                            response={"status": "busy", "message": "An image is still being generated. Please wait for it to finish before requesting a new one. Tell the director to hold on."}
                        )
                    )
                    continue

                self._last_image_description = description
                self._conversation_history.append(f"[Generated stage image: {description[:200]}]")
                await self.send_to_client({
                    "type": "transcript",
                    "role": "assistant",
                    "text": "Generating stage visualization...",
                })
                self._image_generating = True
                asyncio.create_task(self._generate_image_background(description))
                function_responses.append(
                    types.FunctionResponse(
                        id=fc.id, name=fc.name,
                        response={"status": "success", "message": "Stage image is being generated and will appear shortly."}
                    )
                )
            elif fc.name == "generate_bom":
                result = await self._handle_generate_bom(fc.args)
                self._conversation_history.append(
                    f"[Generated BOM: {result.get('item_count', 0)} items, total {result.get('total_cost', '?')}]"
                )
                within = result.get("within_budget", True)
                summary = f"BOM updated: {result.get('item_count', 0)} items, total {result.get('total_cost', '?')}"
                if not within:
                    summary += f" — over budget by {result.get('budget_remaining', '?')}"
                else:
                    summary += f" — {result.get('budget_remaining', '?')} remaining"
                await self.send_to_client({
                    "type": "transcript",
                    "role": "assistant",
                    "text": summary,
                })
                function_responses.append(
                    types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                )

        try:
            await self.session.send_tool_response(function_responses=function_responses)
        except Exception as e:
            logger.error("Failed to send tool response: %s", e)
        self._tool_call_in_progress = False

    async def _generate_image_background(self, description: str):
        """Generate image in background with retry on rate limit."""
        # Use stage photo if captured, otherwise fall back to generated base image
        reference_image = self.stage_photo or self._base_stage_image
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info("Image generation attempt %d/%d...", attempt + 1, max_retries)
                if reference_image:
                    prompt = f"Modify this image of a stage to add the following set design elements: {description}. Keep the original stage structure visible and add the set elements realistically."
                    contents = [prompt, types.Part.from_bytes(data=reference_image, mime_type="image/jpeg")]
                else:
                    prompt = f"Create a realistic stage set design visualization: {description}. The image should look like a theatrical stage viewed from the audience perspective."
                    contents = [prompt]

                response = await _get_client().aio.models.generate_content(
                    model=IMAGE_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        image_config=types.ImageConfig(aspect_ratio="16:9"),
                    ),
                )

                if not response.candidates:
                    block_reason = getattr(response, 'prompt_feedback', None)
                    logger.warning("Image generation returned no candidates. Feedback: %s", block_reason)
                    self._log.tool_result("generate_stage_image", f"No candidates returned. Feedback: {block_reason}")
                    await self.send_to_client({
                        "type": "transcript",
                        "role": "assistant",
                        "text": "Image generation returned empty result, retrying...",
                    })
                    await asyncio.sleep(5)
                    continue

                parts = response.candidates[0].content.parts if response.candidates[0].content else []
                for part in parts:
                    if part.inline_data:
                        img_b64 = base64.b64encode(part.inline_data.data).decode()
                        await self.send_to_client({
                            "type": "stage_image",
                            "data": img_b64,
                            "mime_type": part.inline_data.mime_type,
                        })
                        await self.send_to_client({
                            "type": "transcript",
                            "role": "assistant",
                            "text": "Stage visualization ready!",
                        })
                        self._log.tool_result("generate_stage_image", "Image sent to client")
                        logger.info("Background image generation complete, sent to client")
                        self._image_generating = False
                        return

                logger.warning("Image generation returned no image data in parts")
                self._image_generating = False
                return
            except Exception as e:
                is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
                if is_rate_limit and attempt < max_retries - 1:
                    wait = (attempt + 1) * 10  # 10s, 20s
                    logger.warning("Rate limited, retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                    self._log.event(f"Image rate limited, retrying in {wait}s")
                    await self.send_to_client({
                        "type": "transcript",
                        "role": "assistant",
                        "text": f"Image generation busy, retrying in {wait}s...",
                    })
                    await asyncio.sleep(wait)
                    continue

                self._log.tool_result("generate_stage_image", f"FAILED: {e}")
                logger.error("Background image generation failed: %s", e)
                self._image_generating = False
                await self.send_to_client({
                    "type": "error",
                    "message": f"Image generation failed: {str(e)}"
                })
                return

    async def _handle_generate_bom(self, args: dict) -> dict:
        items = args.get("items", [])
        budget = self.config.get("budget", 25000000)

        bom = generate_bom(items, budget)

        await self.send_to_client({
            "type": "bom",
            "items": bom["items"],
            "total": bom["total"],
            "budget": bom["budget"],
            "remaining": bom["remaining"],
        })

        return {
            "status": "success",
            "total_cost": f"Rp {bom['total']:,}",
            "budget_remaining": f"Rp {bom['remaining']:,}",
            "within_budget": bom["remaining"] >= 0,
            "item_count": len(bom["items"]),
        }
