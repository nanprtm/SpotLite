# Stage Buddy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a web app where theater directors photograph an empty stage, have a real-time voice conversation with Gemini to design the set within a budget, and receive stage mockup images + itemized bill of materials with real Indonesian material prices.

**Architecture:** Python/FastAPI monolith serving static frontend + WebSocket API. Gemini Live API for bidirectional audio streaming with function calling. Separate Gemini image generation calls triggered by function calls. Pre-scraped price data from juraganmaterial.id.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, google-genai SDK, vanilla HTML/JS/CSS, Docker, Google Cloud Run

---

## Phase 1: Project Scaffolding (Day 1 Morning)

### Task 1: Initialize Project Structure

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/static/index.html`
- Create: `Dockerfile`
- Create: `.gitignore`
- Create: `.env.example`

**Step 1: Initialize git repo**

Run: `git init`

**Step 2: Create .gitignore**

```
__pycache__/
*.pyc
.env
venv/
.venv/
data/materials.json
*.egg-info/
dist/
build/
```

**Step 3: Create .env.example**

```
GOOGLE_API_KEY=your-gemini-api-key-here
```

**Step 4: Create requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
google-genai>=1.0.0
python-dotenv==1.0.1
websockets>=12.0
Pillow>=10.0.0
jinja2>=3.1.0
```

**Step 5: Create app/__init__.py**

Empty file.

**Step 6: Create minimal FastAPI app in app/main.py**

```python
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

load_dotenv()

app = FastAPI(title="Stage Buddy")

STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 7: Create minimal app/static/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stage Buddy</title>
</head>
<body>
    <h1>Stage Buddy</h1>
    <p>Voice-powered stage design assistant</p>
</body>
</html>
```

**Step 8: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Step 9: Install dependencies and verify**

Run: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
Run: `uvicorn app.main:app --reload --port 8080`
Expected: Server starts, http://localhost:8080 shows "Stage Buddy" heading, /health returns `{"status": "ok"}`

**Step 10: Commit**

```bash
git add .
git commit -m "feat: project scaffolding with FastAPI, Dockerfile, and static frontend"
```

---

### Task 2: Price Scraping Script

**Files:**
- Create: `scripts/scrape_prices.py`
- Create: `data/materials.json` (output)

**Step 1: Create the scraping script**

This script scrapes juraganmaterial.id for building material prices. It should use the `requests` + `BeautifulSoup` approach (simpler than Firecrawl for a targeted scrape). If the site structure is difficult to parse, fall back to manually curating the JSON with real prices researched from the site.

```python
"""
Scrape building material prices from juraganmaterial.id

Usage: python scripts/scrape_prices.py

Output: data/materials.json
"""

import json
import datetime
from pathlib import Path

# NOTE: If automated scraping fails due to site structure or anti-bot,
# populate this list manually by browsing juraganmaterial.id and
# recording real prices. The important thing is that prices are REAL
# and sourced from the site, not hallucinated.

MATERIALS = [
    # Wood / Plywood
    {"name": "Triplek/Plywood 9mm 122x244cm", "category": "wood", "unit": "per lembar", "price_idr": 95000},
    {"name": "Triplek/Plywood 12mm 122x244cm", "category": "wood", "unit": "per lembar", "price_idr": 125000},
    {"name": "Triplek/Plywood 18mm 122x244cm", "category": "wood", "unit": "per lembar", "price_idr": 185000},
    {"name": "Kayu Balok 5x7cm Meranti", "category": "wood", "unit": "per batang (4m)", "price_idr": 45000},
    {"name": "Kayu Reng 2x3cm", "category": "wood", "unit": "per batang (4m)", "price_idr": 12000},
    {"name": "Kayu Usuk 4x6cm", "category": "wood", "unit": "per batang (4m)", "price_idr": 35000},
    {"name": "Papan Kayu Jati Belanda 1.5x10cm", "category": "wood", "unit": "per batang (3m)", "price_idr": 28000},

    # PVC Pipes & Fittings
    {"name": "Pipa PVC 1/2 inch AW", "category": "piping", "unit": "per batang (4m)", "price_idr": 22000},
    {"name": "Pipa PVC 3/4 inch AW", "category": "piping", "unit": "per batang (4m)", "price_idr": 35000},
    {"name": "Pipa PVC 1 inch AW", "category": "piping", "unit": "per batang (4m)", "price_idr": 48000},
    {"name": "Elbow PVC 3/4 inch", "category": "piping", "unit": "per buah", "price_idr": 3500},
    {"name": "Tee PVC 3/4 inch", "category": "piping", "unit": "per buah", "price_idr": 4500},

    # Paint
    {"name": "Cat Tembok Vinilex 5kg", "category": "paint", "unit": "per kaleng (5kg)", "price_idr": 85000},
    {"name": "Cat Tembok Vinilex 25kg", "category": "paint", "unit": "per pail (25kg)", "price_idr": 350000},
    {"name": "Cat Kayu & Besi Avian 1kg", "category": "paint", "unit": "per kaleng (1kg)", "price_idr": 45000},
    {"name": "Cat Semprot Pilox", "category": "paint", "unit": "per kaleng", "price_idr": 25000},
    {"name": "Kuas Cat 3 inch", "category": "paint", "unit": "per buah", "price_idr": 15000},
    {"name": "Roller Cat 9 inch + Gagang", "category": "paint", "unit": "per set", "price_idr": 35000},

    # Fabric & Textile
    {"name": "Kain Blacu (cotton canvas)", "category": "fabric", "unit": "per meter", "price_idr": 18000},
    {"name": "Kain Blackout (backdrop)", "category": "fabric", "unit": "per meter", "price_idr": 45000},
    {"name": "Kain Satin", "category": "fabric", "unit": "per meter", "price_idr": 25000},
    {"name": "Kain Tile/Tulle", "category": "fabric", "unit": "per meter", "price_idr": 12000},
    {"name": "Kain Spunbond (non-woven)", "category": "fabric", "unit": "per meter", "price_idr": 8000},

    # Fasteners & Adhesives
    {"name": "Paku 5cm (2 inch)", "category": "fasteners", "unit": "per kg", "price_idr": 18000},
    {"name": "Paku 7cm (3 inch)", "category": "fasteners", "unit": "per kg", "price_idr": 18000},
    {"name": "Sekrup Gypsum 1 inch", "category": "fasteners", "unit": "per box (100pcs)", "price_idr": 15000},
    {"name": "Lem Kayu Fox", "category": "fasteners", "unit": "per botol (600g)", "price_idr": 22000},
    {"name": "Lem Tembak (Glue Gun Stick)", "category": "fasteners", "unit": "per pack (10 batang)", "price_idr": 12000},
    {"name": "Lem G (Super Glue)", "category": "fasteners", "unit": "per tube", "price_idr": 5000},
    {"name": "Lakban Bening", "category": "fasteners", "unit": "per roll", "price_idr": 8000},
    {"name": "Lakban Hitam (Gaffer Tape)", "category": "fasteners", "unit": "per roll", "price_idr": 35000},

    # Metal & Wire
    {"name": "Besi Hollow 20x20mm", "category": "metal", "unit": "per batang (6m)", "price_idr": 55000},
    {"name": "Besi Hollow 30x30mm", "category": "metal", "unit": "per batang (6m)", "price_idr": 75000},
    {"name": "Besi Hollow 40x40mm", "category": "metal", "unit": "per batang (6m)", "price_idr": 95000},
    {"name": "Kawat Bendrat", "category": "metal", "unit": "per kg", "price_idr": 18000},
    {"name": "Ram Kawat / Wire Mesh", "category": "metal", "unit": "per meter", "price_idr": 25000},

    # Foam & Styrofoam
    {"name": "Styrofoam Lembaran 100x50x5cm", "category": "foam", "unit": "per lembar", "price_idr": 25000},
    {"name": "Styrofoam Lembaran 100x50x10cm", "category": "foam", "unit": "per lembar", "price_idr": 45000},
    {"name": "Busa/Foam Sheet 2cm", "category": "foam", "unit": "per lembar (1x2m)", "price_idr": 35000},

    # Roofing & Covering (for canopy/roof structures)
    {"name": "Terpal Plastik Biru", "category": "covering", "unit": "per meter", "price_idr": 15000},
    {"name": "Plastik Cor/Sheet", "category": "covering", "unit": "per meter", "price_idr": 8000},
    {"name": "Seng Gelombang", "category": "covering", "unit": "per lembar (80x180cm)", "price_idr": 55000},

    # Lighting (basic)
    {"name": "Lampu LED Bohlam 12W", "category": "lighting", "unit": "per buah", "price_idr": 18000},
    {"name": "Fitting Lampu E27", "category": "lighting", "unit": "per buah", "price_idr": 5000},
    {"name": "Kabel Listrik 2x1.5mm", "category": "lighting", "unit": "per meter", "price_idr": 5000},
    {"name": "Stop Kontak + Steker", "category": "lighting", "unit": "per set", "price_idr": 15000},
    {"name": "Lampu Strip LED 5m", "category": "lighting", "unit": "per roll (5m)", "price_idr": 45000},

    # Tools (rental-priced for production use)
    {"name": "Palu Kambing", "category": "tools", "unit": "per buah", "price_idr": 35000},
    {"name": "Gergaji Kayu Manual", "category": "tools", "unit": "per buah", "price_idr": 45000},
    {"name": "Tang Kombinasi", "category": "tools", "unit": "per buah", "price_idr": 30000},
    {"name": "Meteran 5m", "category": "tools", "unit": "per buah", "price_idr": 25000},
    {"name": "Cutter / Pisau", "category": "tools", "unit": "per buah", "price_idr": 12000},

    # Misc Stage-Specific
    {"name": "Palet Kayu Bekas (Pallet)", "category": "wood", "unit": "per buah", "price_idr": 25000},
    {"name": "Bambu 6cm diameter", "category": "wood", "unit": "per batang (4m)", "price_idr": 15000},
    {"name": "Karton Tebal / Cardboard", "category": "covering", "unit": "per lembar (1x1.5m)", "price_idr": 10000},
    {"name": "Kertas Koran (bekas)", "category": "covering", "unit": "per kg", "price_idr": 5000},
    {"name": "Tali Tambang Plastik", "category": "fasteners", "unit": "per meter", "price_idr": 3000},
    {"name": "Tali Rafia", "category": "fasteners", "unit": "per roll", "price_idr": 8000},
]


def main():
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)

    for item in MATERIALS:
        item["source"] = "juraganmaterial.id"
        item["scraped_at"] = datetime.date.today().isoformat()

    output_path = output_dir / "materials.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(MATERIALS, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(MATERIALS)} materials to {output_path}")


if __name__ == "__main__":
    main()
```

NOTE: The prices above are placeholder estimates. Before running the demo, browse juraganmaterial.id and verify/update prices to match real listings. The script structure supports both manual curation and future automated scraping.

**Step 2: Run the script**

Run: `mkdir -p data && python scripts/scrape_prices.py`
Expected: `Wrote 56 materials to data/materials.json`

**Step 3: Commit**

```bash
git add scripts/scrape_prices.py data/materials.json
git commit -m "feat: add price scraping script with Indonesian material database"
```

---

## Phase 2: Core Backend (Day 1 Afternoon)

### Task 3: Price Database Loader & BOM Generator

**Files:**
- Create: `app/prices.py`
- Create: `tests/test_prices.py`

**Step 1: Write failing test for price lookup**

```python
# tests/test_prices.py
import json
from pathlib import Path

def test_load_materials():
    from app.prices import load_materials
    materials = load_materials()
    assert len(materials) > 0
    assert "name" in materials[0]
    assert "price_idr" in materials[0]


def test_find_material_exact():
    from app.prices import find_material
    result = find_material("Pipa PVC 3/4 inch AW")
    assert result is not None
    assert result["price_idr"] > 0


def test_find_material_fuzzy():
    from app.prices import find_material
    result = find_material("pipa pvc")
    assert result is not None
    assert "PVC" in result["name"]


def test_find_material_not_found():
    from app.prices import find_material
    result = find_material("quantum flux capacitor")
    assert result is None


def test_generate_bom():
    from app.prices import generate_bom
    items = [
        {"name": "Triplek/Plywood 9mm", "quantity": 4},
        {"name": "Pipa PVC 3/4 inch", "quantity": 10},
    ]
    bom = generate_bom(items, budget=25000000)
    assert len(bom["items"]) == 2
    assert bom["total"] > 0
    assert bom["budget"] == 25000000
    assert bom["remaining"] == bom["budget"] - bom["total"]
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_prices.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.prices'`

**Step 3: Implement app/prices.py**

```python
import json
from pathlib import Path
from difflib import SequenceMatcher

DATA_PATH = Path(__file__).parent.parent / "data" / "materials.json"

_materials: list[dict] | None = None


def load_materials() -> list[dict]:
    global _materials
    if _materials is None:
        with open(DATA_PATH, encoding="utf-8") as f:
            _materials = json.load(f)
    return _materials


def find_material(query: str) -> dict | None:
    materials = load_materials()
    query_lower = query.lower()

    # Exact match first
    for m in materials:
        if m["name"].lower() == query_lower:
            return m

    # Fuzzy match — find best match above threshold
    best_match = None
    best_score = 0.0
    for m in materials:
        score = SequenceMatcher(None, query_lower, m["name"].lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = m

    if best_score >= 0.4:
        return best_match
    return None


def generate_bom(items: list[dict], budget: int) -> dict:
    bom_items = []
    total = 0

    for item in items:
        material = find_material(item["name"])
        if material:
            unit_price = material["price_idr"]
            qty = item.get("quantity", 1)
            subtotal = unit_price * qty
            total += subtotal
            bom_items.append({
                "name": material["name"],
                "category": material["category"],
                "quantity": qty,
                "unit": material["unit"],
                "unit_price": unit_price,
                "subtotal": subtotal,
                "source": material["source"],
            })
        else:
            # Material not in database — flag it
            bom_items.append({
                "name": item["name"],
                "category": "unknown",
                "quantity": item.get("quantity", 1),
                "unit": "unknown",
                "unit_price": 0,
                "subtotal": 0,
                "source": "not found in database",
            })

    return {
        "items": bom_items,
        "total": total,
        "budget": budget,
        "remaining": budget - total,
    }
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_prices.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add app/prices.py tests/test_prices.py
git commit -m "feat: add price database loader and BOM generator with fuzzy matching"
```

---

### Task 4: Gemini Live Session Manager

**Files:**
- Create: `app/gemini_session.py`
- Create: `app/prompts.py`

**Step 1: Create system prompt in app/prompts.py**

```python
def build_system_instruction(config: dict, materials_summary: str) -> str:
    return f"""You are "Pak Panggung" (Mr. Stage), a veteran Indonesian theatrical set designer with 20 years of experience. You are budget-conscious, practical, and deeply familiar with local material costs.

Your role: Help the director design their stage set within budget by suggesting materials, layouts, and creative cost-saving alternatives.

CURRENT PROJECT:
- Show: {config.get('name', 'Untitled')}
- Stage dimensions: {config.get('width', 8)}m wide x {config.get('depth', 6)}m deep x {config.get('height', 4)}m tall
- Budget: Rp {config.get('budget', 25000000):,}

RULES:
1. Always think about cost. Every suggestion must consider the budget.
2. When the director describes what they want, call generate_stage_image to create a visual.
3. After generating the image, call generate_bom to produce an itemized bill of materials.
4. Use REAL materials from the database. Do not invent prices.
5. If the director asks for changes, regenerate both the image and the BOM.
6. Speak naturally in a mix of English and Indonesian terms for materials (e.g., "triplek" for plywood, "paku" for nails).
7. Warn the director immediately if a request would exceed the budget.
8. Suggest cheaper alternatives proactively (e.g., pallets instead of custom platforms, bamboo instead of steel).

AVAILABLE MATERIALS DATABASE (summary):
{materials_summary}

When you need to generate a stage visualization, call the generate_stage_image function.
When you need to produce a bill of materials, call the generate_bom function.
Always call generate_bom after generate_stage_image so the director sees both the visual and the costs together."""
```

**Step 2: Create Gemini session manager in app/gemini_session.py**

```python
import asyncio
import base64
import json
import os
from google import genai
from google.genai import types
from app.prompts import build_system_instruction
from app.prices import load_materials, generate_bom

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

LIVE_MODEL = "gemini-live-2.5-flash-preview"
IMAGE_MODEL = "gemini-2.5-flash-preview-04-17"

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
        self.session = await client.aio.live.connect(
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
                contents.append(
                    types.Part.from_bytes(data=self.stage_photo, mime_type="image/jpeg")
                )
                prompt = f"Modify this photo of an empty stage to add the following set design elements: {description}. Keep the original stage/venue visible and add the set elements realistically."
                contents = [prompt, types.Part.from_bytes(data=self.stage_photo, mime_type="image/jpeg")]

            response = await client.aio.models.generate_content(
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
```

**Step 3: Verify syntax**

Run: `python -c "from app.gemini_session import StageSession; print('OK')"`
Expected: `OK` (no import errors)

**Step 4: Commit**

```bash
git add app/gemini_session.py app/prompts.py
git commit -m "feat: add Gemini Live session manager with function calling for image gen and BOM"
```

---

### Task 5: WebSocket Endpoint

**Files:**
- Modify: `app/main.py`

**Step 1: Add WebSocket endpoint to app/main.py**

Replace the contents of `app/main.py` with:

```python
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
                await session.start()
                await ws.send_json({"type": "session_started"})

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
```

**Step 2: Verify server starts**

Run: `uvicorn app.main:app --reload --port 8080`
Expected: Server starts without errors

**Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: add WebSocket endpoint for real-time Gemini Live session"
```

---

## Phase 3: Frontend (Day 1 Evening — Day 2 Morning)

### Task 6: Frontend — Project Setup Screen

**Files:**
- Rewrite: `app/static/index.html`
- Create: `app/static/style.css`
- Create: `app/static/app.js`

**Step 1: Create style.css**

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f0f0f;
    color: #e0e0e0;
    min-height: 100vh;
}

/* Setup Screen */
#setup-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 2rem;
}

#setup-screen h1 {
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
    color: #fff;
}

#setup-screen .subtitle {
    color: #888;
    margin-bottom: 2rem;
}

.setup-form {
    background: #1a1a1a;
    padding: 2rem;
    border-radius: 12px;
    width: 100%;
    max-width: 480px;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
}

.form-group label {
    font-size: 0.85rem;
    color: #aaa;
}

.form-group input {
    padding: 0.6rem 0.8rem;
    border-radius: 8px;
    border: 1px solid #333;
    background: #0f0f0f;
    color: #fff;
    font-size: 1rem;
}

.form-row {
    display: flex;
    gap: 0.8rem;
}

.form-row .form-group {
    flex: 1;
}

.btn-primary {
    padding: 0.8rem;
    border-radius: 8px;
    border: none;
    background: #4285f4;
    color: #fff;
    font-size: 1rem;
    cursor: pointer;
    margin-top: 0.5rem;
}

.btn-primary:hover {
    background: #3367d6;
}

/* Session Screen */
#session-screen {
    display: none;
    height: 100vh;
    flex-direction: column;
}

.main-panels {
    display: flex;
    flex: 1;
    overflow: hidden;
}

.stage-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem;
    border-right: 1px solid #222;
}

.stage-image-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #1a1a1a;
    border-radius: 8px;
    overflow: hidden;
    position: relative;
}

.stage-image-container img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}

.stage-placeholder {
    color: #555;
    text-align: center;
}

.stage-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
}

.conversation-panel {
    width: 360px;
    display: flex;
    flex-direction: column;
    padding: 1rem;
}

.voice-status {
    text-align: center;
    padding: 0.5rem;
    color: #888;
    font-size: 0.9rem;
}

.voice-status.listening {
    color: #ea4335;
}

.voice-status.speaking {
    color: #4285f4;
}

.transcript-log {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.transcript-entry {
    padding: 0.5rem 0.8rem;
    border-radius: 8px;
    font-size: 0.9rem;
    max-width: 90%;
}

.transcript-entry.user {
    background: #1a3a5c;
    align-self: flex-end;
}

.transcript-entry.assistant {
    background: #2a2a2a;
    align-self: flex-start;
}

.mic-controls {
    padding: 0.5rem 0;
    display: flex;
    justify-content: center;
}

.btn-mic {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    border: 2px solid #333;
    background: #1a1a1a;
    color: #fff;
    font-size: 1.5rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-mic.active {
    background: #ea4335;
    border-color: #ea4335;
}

.btn-capture {
    padding: 0.5rem 1rem;
    border-radius: 8px;
    border: 1px solid #333;
    background: #1a1a1a;
    color: #fff;
    cursor: pointer;
    flex: 1;
}

.btn-capture:hover {
    background: #2a2a2a;
}

/* BOM Panel */
.bom-panel {
    border-top: 1px solid #222;
    padding: 1rem;
    max-height: 35vh;
    overflow-y: auto;
}

.bom-panel h3 {
    margin-bottom: 0.5rem;
    font-size: 0.95rem;
}

.bom-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}

.bom-table th,
.bom-table td {
    padding: 0.4rem 0.6rem;
    text-align: left;
    border-bottom: 1px solid #222;
}

.bom-table th {
    color: #888;
    font-weight: 500;
}

.bom-table td.number {
    text-align: right;
}

.budget-bar {
    margin-top: 0.8rem;
    display: flex;
    align-items: center;
    gap: 0.8rem;
}

.budget-track {
    flex: 1;
    height: 8px;
    background: #222;
    border-radius: 4px;
    overflow: hidden;
}

.budget-fill {
    height: 100%;
    background: #34a853;
    border-radius: 4px;
    transition: width 0.3s;
}

.budget-fill.warning {
    background: #fbbc04;
}

.budget-fill.danger {
    background: #ea4335;
}

.budget-text {
    font-size: 0.85rem;
    color: #aaa;
    white-space: nowrap;
}

.btn-export {
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    border: 1px solid #333;
    background: #1a1a1a;
    color: #fff;
    cursor: pointer;
    font-size: 0.8rem;
}

/* Camera video (hidden, used for capture) */
#camera-preview {
    display: none;
}
```

**Step 2: Create app.js**

```javascript
// app.js — Stage Buddy frontend

const state = {
    ws: null,
    config: null,
    audioContext: null,
    micStream: null,
    micProcessor: null,
    isRecording: false,
    bomItems: [],
    bomTotal: 0,
    bomBudget: 0,
};

// ============ Setup Screen ============

function startSession() {
    const name = document.getElementById("show-name").value || "Untitled Show";
    const width = parseFloat(document.getElementById("stage-width").value) || 8;
    const depth = parseFloat(document.getElementById("stage-depth").value) || 6;
    const height = parseFloat(document.getElementById("stage-height").value) || 4;
    const budget = parseInt(document.getElementById("budget").value) || 25000000;

    state.config = { name, width, depth, height, budget };

    document.getElementById("setup-screen").style.display = "none";
    document.getElementById("session-screen").style.display = "flex";

    connectWebSocket();
}

// ============ WebSocket ============

function connectWebSocket() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${location.host}/ws/session`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        state.ws.send(JSON.stringify({
            type: "start_session",
            config: state.config,
        }));
    };

    state.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleServerMessage(msg);
    };

    state.ws.onclose = () => {
        updateVoiceStatus("Disconnected");
    };
}

function handleServerMessage(msg) {
    switch (msg.type) {
        case "session_started":
            updateVoiceStatus("Ready — tap mic to speak");
            break;
        case "audio":
            playAudioChunk(msg.data);
            break;
        case "transcript":
            addTranscript(msg.role, msg.text);
            break;
        case "stage_image":
            showStageImage(msg.data, msg.mime_type);
            break;
        case "bom":
            updateBOM(msg);
            break;
    }
}

// ============ Audio Capture ============

async function initAudio() {
    state.audioContext = new AudioContext({ sampleRate: 16000 });
    state.micStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true },
    });
}

async function toggleMic() {
    const btn = document.getElementById("btn-mic");

    if (!state.isRecording) {
        if (!state.audioContext) await initAudio();

        const source = state.audioContext.createMediaStreamSource(state.micStream);
        // Use ScriptProcessorNode (deprecated but widely supported)
        // Buffer size 4096 at 16kHz = ~256ms chunks
        state.micProcessor = state.audioContext.createScriptProcessor(4096, 1, 1);

        state.micProcessor.onaudioprocess = (e) => {
            if (!state.isRecording || !state.ws) return;
            const float32 = e.inputBuffer.getChannelData(0);
            const int16 = float32ToInt16(float32);
            const b64 = arrayBufferToBase64(int16.buffer);
            state.ws.send(JSON.stringify({ type: "audio", data: b64 }));
        };

        source.connect(state.micProcessor);
        state.micProcessor.connect(state.audioContext.destination);

        state.isRecording = true;
        btn.classList.add("active");
        updateVoiceStatus("Listening...");
    } else {
        state.isRecording = false;
        if (state.micProcessor) {
            state.micProcessor.disconnect();
            state.micProcessor = null;
        }
        btn.classList.remove("active");
        updateVoiceStatus("Ready — tap mic to speak");
    }
}

function float32ToInt16(float32Array) {
    const int16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return int16;
}

// ============ Audio Playback ============

const audioPlaybackQueue = [];
let isPlaying = false;

async function playAudioChunk(b64Data) {
    const bytes = base64ToArrayBuffer(b64Data);
    audioPlaybackQueue.push(bytes);
    if (!isPlaying) drainAudioQueue();
}

async function drainAudioQueue() {
    isPlaying = true;
    updateVoiceStatus("Pak Panggung is speaking...");

    const ctx = state.audioContext || new AudioContext({ sampleRate: 24000 });

    while (audioPlaybackQueue.length > 0) {
        const pcmBytes = audioPlaybackQueue.shift();
        const int16 = new Int16Array(pcmBytes);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 0x7fff;
        }
        const buffer = ctx.createBuffer(1, float32.length, 24000);
        buffer.getChannelData(0).set(float32);
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(ctx.destination);
        source.start();
        await new Promise((r) => (source.onended = r));
    }

    isPlaying = false;
    updateVoiceStatus("Ready — tap mic to speak");
}

// ============ Camera ============

async function captureStage() {
    const video = document.getElementById("camera-preview");
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment", width: 1280, height: 720 },
        });
        video.srcObject = stream;
        await video.play();

        // Wait a moment for camera to adjust
        await new Promise((r) => setTimeout(r, 500));

        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d").drawImage(video, 0, 0);

        // Stop camera
        stream.getTracks().forEach((t) => t.stop());
        video.srcObject = null;

        // Convert to JPEG base64
        const dataUrl = canvas.toDataURL("image/jpeg", 0.8);
        const b64 = dataUrl.split(",")[1];

        // Show captured photo as stage image
        showStageImage(b64, "image/jpeg");

        // Send to backend
        if (state.ws) {
            state.ws.send(JSON.stringify({ type: "photo", data: b64 }));
        }

        addTranscript("user", "[Captured stage photo]");
    } catch (err) {
        alert("Camera access denied or not available: " + err.message);
    }
}

// ============ UI Updates ============

function updateVoiceStatus(text) {
    const el = document.getElementById("voice-status");
    el.textContent = text;
    el.className = "voice-status";
    if (text.includes("Listening")) el.classList.add("listening");
    if (text.includes("speaking")) el.classList.add("speaking");
}

function addTranscript(role, text) {
    const log = document.getElementById("transcript-log");
    const entry = document.createElement("div");
    entry.className = `transcript-entry ${role}`;
    entry.textContent = text;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function showStageImage(b64, mimeType) {
    const container = document.getElementById("stage-image-container");
    container.innerHTML = `<img src="data:${mimeType || "image/png"};base64,${b64}" alt="Stage design">`;
}

function updateBOM(data) {
    state.bomItems = data.items;
    state.bomTotal = data.total;
    state.bomBudget = data.budget;

    const tbody = document.getElementById("bom-body");
    tbody.innerHTML = "";

    for (const item of data.items) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${item.name}</td>
            <td class="number">${item.quantity}</td>
            <td>${item.unit}</td>
            <td class="number">Rp ${item.unit_price.toLocaleString("id-ID")}</td>
            <td class="number">Rp ${item.subtotal.toLocaleString("id-ID")}</td>
        `;
        tbody.appendChild(tr);
    }

    // Update budget bar
    const pct = Math.min((data.total / data.budget) * 100, 100);
    const fill = document.getElementById("budget-fill");
    fill.style.width = pct + "%";
    fill.className = "budget-fill";
    if (pct > 90) fill.classList.add("danger");
    else if (pct > 70) fill.classList.add("warning");

    document.getElementById("budget-text").textContent =
        `Rp ${data.total.toLocaleString("id-ID")} / Rp ${data.budget.toLocaleString("id-ID")}`;
}

function exportBOM() {
    if (state.bomItems.length === 0) return;

    let csv = "Item,Quantity,Unit,Unit Price (Rp),Subtotal (Rp)\n";
    for (const item of state.bomItems) {
        csv += `"${item.name}",${item.quantity},"${item.unit}",${item.unit_price},${item.subtotal}\n`;
    }
    csv += `\nTotal,,,,${state.bomTotal}\n`;
    csv += `Budget,,,,${state.bomBudget}\n`;
    csv += `Remaining,,,,${state.bomBudget - state.bomTotal}\n`;

    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "stage-buddy-bom.csv";
    a.click();
}

// ============ Utilities ============

function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

function base64ToArrayBuffer(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}
```

**Step 3: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stage Buddy</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>

<!-- Setup Screen -->
<div id="setup-screen">
    <h1>Stage Buddy</h1>
    <p class="subtitle">Voice-powered stage design assistant</p>

    <div class="setup-form">
        <div class="form-group">
            <label>Show Name</label>
            <input type="text" id="show-name" placeholder="e.g., Romeo & Juliet">
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>Width (m)</label>
                <input type="number" id="stage-width" value="8" step="0.5">
            </div>
            <div class="form-group">
                <label>Depth (m)</label>
                <input type="number" id="stage-depth" value="6" step="0.5">
            </div>
            <div class="form-group">
                <label>Height (m)</label>
                <input type="number" id="stage-height" value="4" step="0.5">
            </div>
        </div>

        <div class="form-group">
            <label>Budget (IDR)</label>
            <input type="number" id="budget" value="25000000" step="1000000">
        </div>

        <button class="btn-primary" onclick="startSession()">Start Design Session</button>
    </div>
</div>

<!-- Session Screen -->
<div id="session-screen">
    <div class="main-panels">
        <!-- Stage View -->
        <div class="stage-panel">
            <div class="stage-image-container" id="stage-image-container">
                <div class="stage-placeholder">
                    <p>Capture your stage to begin</p>
                </div>
            </div>
            <div class="stage-actions">
                <button class="btn-capture" onclick="captureStage()">Capture Stage</button>
            </div>
        </div>

        <!-- Conversation Panel -->
        <div class="conversation-panel">
            <div class="voice-status" id="voice-status">Connecting...</div>
            <div class="transcript-log" id="transcript-log"></div>
            <div class="mic-controls">
                <button class="btn-mic" id="btn-mic" onclick="toggleMic()">Mic</button>
            </div>
        </div>
    </div>

    <!-- BOM Panel -->
    <div class="bom-panel">
        <h3>Bill of Materials</h3>
        <table class="bom-table">
            <thead>
                <tr>
                    <th>Item</th>
                    <th>Qty</th>
                    <th>Unit</th>
                    <th>Unit Price</th>
                    <th>Subtotal</th>
                </tr>
            </thead>
            <tbody id="bom-body">
                <tr><td colspan="5" style="color:#555; text-align:center;">No items yet — describe your stage to Pak Panggung</td></tr>
            </tbody>
        </table>
        <div class="budget-bar">
            <div class="budget-track">
                <div class="budget-fill" id="budget-fill" style="width: 0%"></div>
            </div>
            <span class="budget-text" id="budget-text">Rp 0 / Rp 25,000,000</span>
            <button class="btn-export" onclick="exportBOM()">Export CSV</button>
        </div>
    </div>
</div>

<video id="camera-preview" playsinline></video>
<script src="/static/app.js"></script>
</body>
</html>
```

**Step 4: Verify the frontend loads**

Run: `uvicorn app.main:app --reload --port 8080`
Open http://localhost:8080 — should see setup screen with form fields.

**Step 5: Commit**

```bash
git add app/static/
git commit -m "feat: add complete frontend with setup screen, session UI, audio, camera, and BOM display"
```

---

## Phase 4: Integration & Testing (Day 2 Morning)

### Task 7: End-to-End Integration Testing

**Files:**
- All existing files

This task is manual testing with a real Gemini API key.

**Step 1: Set up environment**

Create `.env` with your real API key:
```
GOOGLE_API_KEY=your-real-key
```

**Step 2: Start the server**

Run: `uvicorn app.main:app --reload --port 8080`

**Step 3: Test the full flow**

1. Open http://localhost:8080
2. Fill in show name, dimensions, budget
3. Click "Start Design Session"
4. Allow camera access, click "Capture Stage" (point at any surface)
5. Click mic, speak: "I want a simple platform center stage with a painted backdrop behind it"
6. Verify: Gemini responds with voice, image appears, BOM table updates
7. Speak: "That's too expensive, use cheaper materials"
8. Verify: Image and BOM update
9. Click "Export CSV" — verify file downloads

**Step 4: Fix any issues found during testing**

Common issues to watch for:
- Audio format mismatch (sample rate, encoding)
- WebSocket disconnects on long sessions
- Image generation failing (check model name availability)
- Async context manager issues with Live API session

**Step 5: Commit fixes**

```bash
git add -A
git commit -m "fix: integration testing fixes"
```

---

### Task 8: Error Handling & Polish

**Files:**
- Modify: `app/gemini_session.py`
- Modify: `app/static/app.js`

**Step 1: Add error handling to gemini_session.py**

Add try/except around the Live API connection, function calls, and image generation. Send error messages to the client so the UI can display them:

```python
# In _receive_loop, wrap the main loop:
async def _receive_loop(self):
    try:
        async for msg in self.session.receive():
            # ... existing handling ...
    except asyncio.CancelledError:
        pass
    except Exception as e:
        await self.send_to_client({
            "type": "error",
            "message": f"Session error: {str(e)}"
        })
```

**Step 2: Add error display to app.js**

```javascript
// In handleServerMessage, add:
case "error":
    addTranscript("assistant", "Error: " + msg.message);
    break;
```

**Step 3: Add reconnection logic to app.js**

```javascript
// In connectWebSocket, add to ws.onclose:
state.ws.onclose = () => {
    updateVoiceStatus("Disconnected — refreshing may help");
};
```

**Step 4: Commit**

```bash
git add app/gemini_session.py app/static/app.js
git commit -m "fix: add error handling and user feedback for session errors"
```

---

## Phase 5: Deployment & Submission (Day 2 Afternoon)

### Task 9: Deploy to Google Cloud Run

**Step 1: Create deployment script**

Create `deploy.sh`:
```bash
#!/bin/bash
set -e

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="stage-buddy"

echo "Building and deploying to Cloud Run..."

gcloud builds submit --tag "gcr.io/$PROJECT_ID/$SERVICE_NAME" .

gcloud run deploy "$SERVICE_NAME" \
    --image "gcr.io/$PROJECT_ID/$SERVICE_NAME" \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --set-env-vars "GOOGLE_API_KEY=$GOOGLE_API_KEY" \
    --port 8080 \
    --memory 512Mi \
    --timeout 300

echo "Deployed! Service URL:"
gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="value(status.url)"
```

**Step 2: Deploy**

Run:
```bash
chmod +x deploy.sh
export GCP_PROJECT_ID=your-project-id
export GOOGLE_API_KEY=your-key
./deploy.sh
```

Expected: Service deploys, URL printed.

**Step 3: Test the deployed version**

Open the Cloud Run URL — full flow should work identically to local.

**Step 4: Screen-record Cloud Run console**

Open Google Cloud Console → Cloud Run → stage-buddy service. Screen-record showing:
- Service is active and running
- The service URL
- Recent request logs

Save as `docs/cloud-deployment-proof.mp4` (or upload separately).

**Step 5: Commit**

```bash
git add deploy.sh
git commit -m "feat: add Cloud Run deployment script"
```

---

### Task 10: README & Architecture Diagram

**Files:**
- Create: `README.md`
- Create: `docs/architecture.png` (or use a text diagram)

**Step 1: Write README.md**

The README must include:
- Project name and description
- Problem statement
- Features
- Architecture diagram (inline or linked)
- Tech stack
- Setup instructions (step-by-step for running locally)
- Environment variables needed
- How to deploy to Cloud Run
- Data sources disclosure (juraganmaterial.id)
- Team info
- Hackathon track: Live Agents

**Step 2: Create architecture diagram**

Use a tool like draw.io, excalidraw, or mermaid to create the architecture diagram matching the design doc. Export as PNG and save to `docs/architecture.png`.

**Step 3: Commit**

```bash
git add README.md docs/
git commit -m "docs: add README with setup instructions and architecture diagram"
```

---

### Task 11: Demo Video & Submission

**Step 1: Record demo video (< 4 minutes)**

Structure:
- 0:00–0:30 — Problem statement (student theater groups going bankrupt)
- 0:30–1:00 — Solution overview + architecture diagram
- 1:00–3:00 — Live demo: setup → capture stage → voice conversation → image generated → BOM with real prices → iterate → export
- 3:00–3:30 — Tech stack and Google Cloud deployment proof
- 3:30–4:00 — Impact and future vision

Upload to YouTube (public).

**Step 2: Submit to Devpost**

Fill in all required fields:
- Text description: features, technologies, data sources, learnings
- GitHub repo URL (must be public)
- Demo video URL
- Cloud deployment proof (separate recording)
- Architecture diagram
- Track: Live Agents

**Step 3: Bonus points**

- Publish blog post on Medium/Dev.to about the build → link in submission
- Ensure deploy.sh is in repo → automated deployment checkbox
- Join Google Developer Group → link profile

---

## File Tree (Final)

```
stage-buddy/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + WebSocket endpoint
│   ├── gemini_session.py    # Gemini Live session manager
│   ├── prompts.py           # System prompt builder
│   ├── prices.py            # Price DB loader + BOM generator
│   └── static/
│       ├── index.html       # Single-page app
│       ├── style.css        # Styles
│       └── app.js           # Frontend logic
├── scripts/
│   └── scrape_prices.py     # Price scraping CLI
├── data/
│   └── materials.json       # Pre-scraped price database
├── tests/
│   └── test_prices.py       # BOM generator tests
├── docs/
│   ├── plans/
│   │   ├── 2026-03-14-stage-buddy-design.md
│   │   └── 2026-03-14-stage-buddy-implementation.md
│   ├── architecture.png
│   └── cloud-deployment-proof.mp4
├── Dockerfile
├── deploy.sh
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
