"""ADK Agent definition for Stage Buddy — Teman Panggung."""

import asyncio
import base64
import logging
import os
from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from app.prices import generate_bom as _generate_bom, load_materials
from app.prompts import build_system_instruction

logger = logging.getLogger(__name__)

LIVE_MODEL = "gemini-live-2.5-flash-native-audio"
IMAGE_MODEL = "gemini-2.5-flash-image"


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


def _load_base_stage() -> bytes:
    base_path = Path(__file__).parent / "static" / "stage.png"
    return base_path.read_bytes()


# ── Tool Functions ──────────────────────────────────────────────


async def generate_stage_image(
    description: str, tool_context: ToolContext
) -> dict:
    """Generate a visual mockup of the stage set based on the director's description.

    Call this when the director describes what they want on stage or asks
    for visual changes.

    Args:
        description: Detailed description of the stage set to visualize,
            including all elements, their positions, colors, and materials.
    """
    from google import genai

    client = genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    # Get reference image from session state
    stage_photo_b64 = tool_context.state.get("stage_photo_b64")
    base_stage_b64 = tool_context.state.get("base_stage_b64")

    if stage_photo_b64:
        reference_image = base64.b64decode(stage_photo_b64)
    elif base_stage_b64:
        reference_image = base64.b64decode(base_stage_b64)
    else:
        reference_image = None

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if reference_image:
                prompt = (
                    f"Modify this image of a stage to add the following set "
                    f"design elements: {description}. Keep the original stage "
                    f"structure visible and add the set elements realistically."
                )
                contents = [
                    prompt,
                    types.Part.from_bytes(
                        data=reference_image, mime_type="image/jpeg"
                    ),
                ]
            else:
                prompt = (
                    f"Create a realistic stage set design visualization: "
                    f"{description}. The image should look like a theatrical "
                    f"stage viewed from the audience perspective."
                )
                contents = [prompt]

            response = await client.aio.models.generate_content(
                model=IMAGE_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                    image_config=types.ImageConfig(aspect_ratio="16:9"),
                ),
            )

            if not response.candidates:
                await asyncio.sleep(5)
                continue

            parts = (
                response.candidates[0].content.parts
                if response.candidates[0].content
                else []
            )
            for part in parts:
                if part.inline_data:
                    img_b64 = base64.b64encode(part.inline_data.data).decode()
                    # Store in session state for the WebSocket handler to pick up
                    tool_context.state["_pending_image"] = {
                        "data": img_b64,
                        "mime_type": part.inline_data.mime_type,
                    }
                    tool_context.state["last_image_description"] = description
                    return {
                        "status": "success",
                        "message": "Stage image generated and displayed.",
                    }

            return {"status": "error", "message": "No image data returned."}

        except Exception as e:
            is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if is_rate_limit and attempt < max_retries - 1:
                wait = (attempt + 1) * 10
                logger.warning("Rate limited, retrying in %ds", wait)
                await asyncio.sleep(wait)
                continue
            logger.error("Image generation failed: %s", e)
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": "Max retries exceeded."}


async def estimate_bom(
    items: list[dict], tool_context: ToolContext
) -> dict:
    """Generate a bill of materials with real local prices for the stage set.

    Call this after generating a stage image to show the director the cost
    breakdown.

    Args:
        items: List of materials needed. Each item is a dict with 'name'
            (str, Indonesian building material name like 'Triplek 9mm',
            'Pipa PVC 3/4 inch') and 'quantity' (int, number of units needed).
    """
    budget = tool_context.state.get("budget", 25_000_000)
    bom = _generate_bom(items, budget)

    # Store in session state for the WebSocket handler to pick up
    tool_context.state["_pending_bom"] = bom

    return {
        "status": "success",
        "total_cost": f"Rp {bom['total']:,}",
        "budget_remaining": f"Rp {bom['remaining']:,}",
        "within_budget": bom["remaining"] >= 0,
        "item_count": len(bom["items"]),
    }


# ── Sub-Agent: Vendor Search (Google Search grounding) ──────────

vendor_search_agent = Agent(
    name="vendor_search",
    model="gemini-2.5-flash",
    instruction=(
        "You are a vendor search assistant for Indonesian building materials. "
        "Search for local vendors, suppliers, and marketplaces (Tokopedia, "
        "Shopee, Bukalapak, juraganmaterial.id) to find pricing, availability, "
        "and store locations. Return vendor names, prices, locations, and URLs. "
        "Always search in Indonesian language for best results."
    ),
    tools=[google_search],
)


# ── Root Agent ──────────────────────────────────────────────────

# Build instruction with a placeholder config — will be overridden per session
_default_config = {
    "name": "Untitled",
    "width": 8,
    "depth": 6,
    "height": 4,
    "budget": 25_000_000,
}
_default_instruction = build_system_instruction(_default_config, _materials_summary())

root_agent = Agent(
    name="teman_panggung",
    model=LIVE_MODEL,
    instruction=_default_instruction,
    tools=[generate_stage_image, estimate_bom],
    sub_agents=[vendor_search_agent],
    generate_content_config=types.GenerateContentConfig(
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.OFF,
            ),
        ]
    ),
)
