import json
import logging
import math
from pathlib import Path
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent.parent / "data" / "materials.json"

_materials: list[dict] | None = None


def load_materials() -> list[dict]:
    global _materials
    if _materials is None:
        with open(DATA_PATH, encoding="utf-8") as f:
            _materials = json.load(f)
    return _materials


# ── Coverage metadata ────────────────────────────────────────────
# Maps material name substrings to coverage info so we can auto-correct
# quantities that are obviously too low for the stage dimensions.

COVERAGE_RULES = [
    # Sheets: coverage in m² per unit
    {"match": "triplek", "coverage_sqm": 2.98, "use": "area"},
    {"match": "plywood", "coverage_sqm": 2.98, "use": "area"},
    {"match": "styrofoam lembaran 100x50x5", "coverage_sqm": 0.5, "use": "area"},
    {"match": "styrofoam lembaran 100x50x10", "coverage_sqm": 0.5, "use": "area"},
    {"match": "busa/foam sheet", "coverage_sqm": 2.0, "use": "area"},
    {"match": "seng gelombang", "coverage_sqm": 1.44, "use": "area"},
    {"match": "karton tebal", "coverage_sqm": 1.5, "use": "area"},

    # Linear: length in meters per unit
    {"match": "kayu balok", "length_m": 4.0, "use": "linear"},
    {"match": "kayu reng", "length_m": 4.0, "use": "linear"},
    {"match": "kayu usuk", "length_m": 4.0, "use": "linear"},
    {"match": "papan kayu", "length_m": 3.0, "use": "linear"},
    {"match": "pipa pvc", "length_m": 4.0, "use": "linear"},
    {"match": "besi hollow", "length_m": 6.0, "use": "linear"},
    {"match": "bambu", "length_m": 4.0, "use": "linear"},
    {"match": "kabel listrik", "length_m": 1.0, "use": "linear"},

    # Fabric: width 1.5m, sold per running meter
    {"match": "kain", "width_m": 1.5, "use": "fabric"},

    # Paint: coverage in m² per unit
    {"match": "cat tembok vinilex 5kg", "coverage_sqm": 50, "use": "paint"},
    {"match": "cat tembok vinilex 25kg", "coverage_sqm": 250, "use": "paint"},
    {"match": "cat kayu", "coverage_sqm": 10, "use": "paint"},

    # Fasteners: per kg or box, estimate per m² of surface
    {"match": "paku", "per_sqm": 0.1, "use": "fastener_weight"},
    {"match": "sekrup", "per_sqm": 0.5, "use": "fastener_box"},
]


def _get_coverage_rule(material_name: str) -> dict | None:
    name_lower = material_name.lower()
    for rule in COVERAGE_RULES:
        if rule["match"] in name_lower:
            return rule
    return None


def _estimate_min_quantity(
    material_name: str,
    stage_width: float,
    stage_depth: float,
    stage_height: float,
) -> int | None:
    """Estimate minimum realistic quantity based on material type and stage size."""
    rule = _get_coverage_rule(material_name)
    if not rule:
        return None

    # Approximate surface area of a single backdrop (width x height)
    backdrop_area = stage_width * stage_height
    # Approximate floor/platform area
    floor_area = stage_width * stage_depth
    # Perimeter for framing
    perimeter = 2 * (stage_width + stage_height)

    use = rule["use"]

    if use == "area":
        # Sheets — at minimum cover one backdrop
        coverage = rule["coverage_sqm"]
        return max(2, math.ceil(backdrop_area / coverage))

    elif use == "linear":
        # Timber/pipe — at minimum frame one backdrop
        length = rule["length_m"]
        # A frame needs: perimeter + some cross pieces
        total_linear = perimeter + stage_width  # basic frame
        return max(2, math.ceil(total_linear / length))

    elif use == "fabric":
        # Fabric per running meter — need height meters × number of widths
        widths_needed = math.ceil(stage_width / rule["width_m"])
        return max(2, math.ceil(stage_height * widths_needed))

    elif use == "paint":
        coverage = rule["coverage_sqm"]
        return max(1, math.ceil(backdrop_area / coverage))

    elif use == "fastener_weight":
        return max(1, math.ceil(backdrop_area * rule["per_sqm"]))

    elif use == "fastener_box":
        return max(1, math.ceil(backdrop_area * rule["per_sqm"]))

    return None


def find_material(query: str) -> dict | None:
    materials = load_materials()
    query_lower = query.lower().strip()

    # Exact match first
    for m in materials:
        if m["name"].lower() == query_lower:
            return m

    # Keyword containment — check if all query words appear in material name
    query_words = query_lower.split()
    keyword_matches = []
    for m in materials:
        name_lower = m["name"].lower()
        if all(w in name_lower for w in query_words):
            keyword_matches.append(m)

    if len(keyword_matches) == 1:
        return keyword_matches[0]
    elif len(keyword_matches) > 1:
        # Multiple keyword matches — pick best fuzzy score among them
        best = max(
            keyword_matches,
            key=lambda m: SequenceMatcher(None, query_lower, m["name"].lower()).ratio(),
        )
        return best

    # Fuzzy match — find best match above threshold
    best_match = None
    best_score = 0.0
    for m in materials:
        score = SequenceMatcher(None, query_lower, m["name"].lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = m

    if best_score >= 0.5:
        return best_match
    return None


def generate_bom(
    items: list[dict],
    budget: int,
    stage_dims: dict | None = None,
) -> dict:
    """Generate BOM with auto-corrected quantities based on stage dimensions."""
    bom_items = []
    total = 0
    corrections = []

    sw = float(stage_dims.get("width", 8)) if stage_dims else 8.0
    sd = float(stage_dims.get("depth", 6)) if stage_dims else 6.0
    sh = float(stage_dims.get("height", 4)) if stage_dims else 4.0

    for item in items:
        if isinstance(item, str):
            item = {"name": item, "quantity": 1}

        material = find_material(item["name"])
        if material:
            unit_price = material["price_idr"]
            qty = max(1, item.get("quantity", 1))

            # Auto-correct if quantity is unrealistically low
            min_qty = _estimate_min_quantity(material["name"], sw, sd, sh)
            if min_qty and qty < min_qty:
                logger.info(
                    "Auto-corrected %s: %d → %d (stage %.0fx%.0fx%.0f)",
                    material["name"], qty, min_qty, sw, sd, sh,
                )
                corrections.append(
                    f"{material['name']}: {qty} -> {min_qty} "
                    f"(minimum for {sw:.0f}m×{sh:.0f}m stage)"
                )
                qty = min_qty

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
            logger.warning("Material not found in database: '%s'", item["name"])
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
        "corrections": corrections,
    }
