import asyncio
import base64
import json
import os
from google import genai
from google.genai import types
from app.prompts import build_system_instruction
from app.prices import load_materials, generate_bom

_client = None

LIVE_MODEL = "gemini-live-2.5-flash-preview"
IMAGE_MODEL = "gemini-2.5-flash-preview-04-17"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
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
        self.stage_photo: bytes | None = None
        self._receive_task: asyncio.Task | None = None

    async def start(self):
        system_instruction = build_system_instruction(self.config, _materials_summary())
        live_config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            system_instruction=system_instruction,
            tools=TOOLS,
        )
        self.session = await _get_client().aio.live.connect(
            model=LIVE_MODEL,
            config=live_config,
        ).__aenter__()
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def stop(self):
        if self._receive_task:
            self._receive_task.cancel()
        if self.session:
            await self.session.__aexit__(None, None, None)

    async def send_audio(self, audio_bytes: bytes):
        if self.session:
            await self.session.send_realtime_input(
                audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
            )

    async def send_photo(self, photo_bytes: bytes):
        self.stage_photo = photo_bytes
        if self.session:
            await self.session.send_realtime_input(
                video=types.Blob(data=photo_bytes, mime_type="image/jpeg")
            )

    async def _receive_loop(self):
        try:
            async for msg in self.session.receive():
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
                            await self.send_to_client({
                                "type": "transcript",
                                "role": "assistant",
                                "text": part.text,
                            })

                # Handle function calls
                if msg.tool_call:
                    await self._handle_tool_calls(msg.tool_call)

        except asyncio.CancelledError:
            pass

    async def _handle_tool_calls(self, tool_call):
        function_responses = []

        for fc in tool_call.function_calls:
            if fc.name == "generate_stage_image":
                result = await self._handle_generate_image(fc.args)
                function_responses.append(
                    types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                )
            elif fc.name == "generate_bom":
                result = await self._handle_generate_bom(fc.args)
                function_responses.append(
                    types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                )

        await self.session.send_tool_response(function_responses=function_responses)

    async def _handle_generate_image(self, args: dict) -> dict:
        description = args.get("description", "")
        prompt = f"Create a realistic stage set design visualization: {description}. The image should look like a theatrical stage viewed from the audience perspective."

        try:
            contents = [prompt]
            if self.stage_photo:
                prompt = f"Modify this photo of an empty stage to add the following set design elements: {description}. Keep the original stage/venue visible and add the set elements realistically."
                contents = [prompt, types.Part.from_bytes(data=self.stage_photo, mime_type="image/jpeg")]

            response = await _get_client().aio.models.generate_content(
                model=IMAGE_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    img_b64 = base64.b64encode(part.inline_data.data).decode()
                    await self.send_to_client({
                        "type": "stage_image",
                        "data": img_b64,
                        "mime_type": part.inline_data.mime_type,
                    })
                    return {"status": "success", "message": "Stage image generated and sent to director"}

            return {"status": "error", "message": "No image was generated"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

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
