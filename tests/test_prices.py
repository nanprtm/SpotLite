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
