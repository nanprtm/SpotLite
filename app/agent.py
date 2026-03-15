"""ADK Agent definition for SpotLite."""

import asyncio
import base64
import logging
import os
from pathlib import Path

from google.adk.agents import Agent
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
    for visual changes. The image generates in the background and will
    appear on the director's screen shortly.

    Args:
        description: Detailed description of the stage set to visualize,
            including all elements, their positions, colors, and materials.
    """
    # Grab what we need from state before returning
    stage_photo_b64 = tool_context.state.get("stage_photo_b64")
    base_stage_b64 = tool_context.state.get("base_stage_b64")
    send_fn = tool_context.state.get("_send_to_client")

    if stage_photo_b64:
        reference_image = base64.b64decode(stage_photo_b64)
    elif base_stage_b64:
        reference_image = base64.b64decode(base_stage_b64)
    else:
        reference_image = None

    # Fire background task and return immediately so Gemini keeps talking
    asyncio.create_task(
        _generate_image_background(description, reference_image, send_fn)
    )

    return {
        "status": "success",
        "message": "Stage image is being generated and will appear shortly.",
    }


async def _generate_image_background(
    description: str,
    reference_image: bytes | None,
    send_fn,
):
    """Background image generation with retry — sends result directly to client."""
    from google import genai

    client = genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    if send_fn:
        await send_fn({
            "type": "transcript",
            "role": "assistant",
            "text": "Generating stage visualization...",
        })

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
                    if send_fn:
                        await send_fn({
                            "type": "stage_image",
                            "data": img_b64,
                            "mime_type": part.inline_data.mime_type,
                        })
                        await send_fn({
                            "type": "transcript",
                            "role": "assistant",
                            "text": "Stage visualization ready!",
                        })
                    logger.info("Background image generation complete")
                    return

            logger.warning("Image generation returned no image data")
            return

        except Exception as e:
            is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if is_rate_limit and attempt < max_retries - 1:
                wait = (attempt + 1) * 10
                logger.warning("Rate limited, retrying in %ds", wait)
                if send_fn:
                    await send_fn({
                        "type": "transcript",
                        "role": "assistant",
                        "text": f"Image generation busy, retrying in {wait}s...",
                    })
                await asyncio.sleep(wait)
                continue
            logger.error("Background image generation failed: %s", e)
            if send_fn:
                await send_fn({
                    "type": "error",
                    "message": f"Image generation failed: {e}",
                })
            return


async def estimate_bom(
    items: list[dict], tool_context: ToolContext
) -> dict:
    """Generate a bill of materials with real local prices for the stage set.

    Call this after generating a stage image to show the director the cost
    breakdown. Quantities will be auto-corrected if they are too low for
    the stage dimensions — you will be told about any corrections.

    Args:
        items: List of materials needed. Each item is a dict with 'name'
            (str, Indonesian building material name like 'Triplek 9mm',
            'Pipa PVC 3/4 inch') and 'quantity' (int, number of units needed).
    """
    budget = tool_context.state.get("budget", 25_000_000)
    stage_config = tool_context.state.get("stage_config", {})
    bom = _generate_bom(items, budget, stage_dims=stage_config)

    # Store in session state for the WebSocket handler to pick up
    tool_context.state["_pending_bom"] = bom

    result = {
        "status": "success",
        "total_cost": f"Rp {bom['total']:,}",
        "budget_remaining": f"Rp {bom['remaining']:,}",
        "within_budget": bom["remaining"] >= 0,
        "item_count": len(bom["items"]),
    }

    # Tell Gemini about auto-corrections so it can mention them
    if bom.get("corrections"):
        result["quantity_corrections"] = bom["corrections"]
        result["note"] = (
            "Some quantities were auto-corrected because they were too low "
            "for the stage dimensions. Mention the corrected quantities to "
            "the director."
        )

    return result


# ── Vendor Search Tool (Google Search grounding via generate_content) ──


async def search_vendors(
    query: str, tool_context: ToolContext
) -> dict:
    """Search for local Indonesian vendors and suppliers for stage materials.

    Use this when the director asks where to buy materials, wants price
    comparisons across stores, or needs vendor recommendations in a
    specific area.

    Args:
        query: Search query for finding vendors, e.g. 'harga triplek 9mm
            Tokopedia' or 'toko bangunan terdekat Jakarta Selatan' or
            'supplier kain backdrop murah Bandung'.
    """
    from google import genai

    client = genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    try:
        search_tool = types.Tool(google_search=types.GoogleSearch())
        prompt = (
            f"Find local Indonesian vendors/suppliers for: {query}. "
            f"Focus on pricing, store names, locations, and availability. "
            f"Include online marketplace links (Tokopedia, Shopee, Bukalapak) "
            f"if available. Respond in Indonesian."
        )

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(tools=[search_tool]),
        )

        result_text = response.text if response.text else "Tidak ada hasil."

        # Extract grounding sources
        sources = []
        if response.candidates and response.candidates[0].grounding_metadata:
            gm = response.candidates[0].grounding_metadata
            if gm.grounding_chunks:
                for chunk in gm.grounding_chunks[:5]:
                    if hasattr(chunk, "web") and chunk.web:
                        sources.append({
                            "title": getattr(chunk.web, "title", ""),
                            "url": getattr(chunk.web, "uri", ""),
                        })

        # Store for WebSocket handler to pick up
        tool_context.state["_pending_vendor_results"] = {
            "query": query,
            "text": result_text,
            "sources": sources,
        }

        return {
            "status": "success",
            "results": result_text[:1000],
            "source_count": len(sources),
        }
    except Exception as e:
        logger.error("Vendor search failed: %s", e)
        return {"status": "error", "message": str(e)}


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
    name="spotlite",
    model=LIVE_MODEL,
    instruction=_default_instruction,
    tools=[generate_stage_image, estimate_bom, search_vendors],
    generate_content_config=types.GenerateContentConfig(
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.OFF,
            ),
        ]
    ),
)
