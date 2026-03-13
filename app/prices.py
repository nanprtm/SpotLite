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
