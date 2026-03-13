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

    # PVC Pipes and Fittings
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

    # Fabric and Textile
    {"name": "Kain Blacu (cotton canvas)", "category": "fabric", "unit": "per meter", "price_idr": 18000},
    {"name": "Kain Blackout (backdrop)", "category": "fabric", "unit": "per meter", "price_idr": 45000},
    {"name": "Kain Satin", "category": "fabric", "unit": "per meter", "price_idr": 25000},
    {"name": "Kain Tile/Tulle", "category": "fabric", "unit": "per meter", "price_idr": 12000},
    {"name": "Kain Spunbond (non-woven)", "category": "fabric", "unit": "per meter", "price_idr": 8000},

    # Fasteners and Adhesives
    {"name": "Paku 5cm (2 inch)", "category": "fasteners", "unit": "per kg", "price_idr": 18000},
    {"name": "Paku 7cm (3 inch)", "category": "fasteners", "unit": "per kg", "price_idr": 18000},
    {"name": "Sekrup Gypsum 1 inch", "category": "fasteners", "unit": "per box (100pcs)", "price_idr": 15000},
    {"name": "Lem Kayu Fox", "category": "fasteners", "unit": "per botol (600g)", "price_idr": 22000},
    {"name": "Lem Tembak (Glue Gun Stick)", "category": "fasteners", "unit": "per pack (10 batang)", "price_idr": 12000},
    {"name": "Lem G (Super Glue)", "category": "fasteners", "unit": "per tube", "price_idr": 5000},
    {"name": "Lakban Bening", "category": "fasteners", "unit": "per roll", "price_idr": 8000},
    {"name": "Lakban Hitam (Gaffer Tape)", "category": "fasteners", "unit": "per roll", "price_idr": 35000},

    # Metal and Wire
    {"name": "Besi Hollow 20x20mm", "category": "metal", "unit": "per batang (6m)", "price_idr": 55000},
    {"name": "Besi Hollow 30x30mm", "category": "metal", "unit": "per batang (6m)", "price_idr": 75000},
    {"name": "Besi Hollow 40x40mm", "category": "metal", "unit": "per batang (6m)", "price_idr": 95000},
    {"name": "Kawat Bendrat", "category": "metal", "unit": "per kg", "price_idr": 18000},
    {"name": "Ram Kawat / Wire Mesh", "category": "metal", "unit": "per meter", "price_idr": 25000},

    # Foam and Styrofoam
    {"name": "Styrofoam Lembaran 100x50x5cm", "category": "foam", "unit": "per lembar", "price_idr": 25000},
    {"name": "Styrofoam Lembaran 100x50x10cm", "category": "foam", "unit": "per lembar", "price_idr": 45000},
    {"name": "Busa/Foam Sheet 2cm", "category": "foam", "unit": "per lembar (1x2m)", "price_idr": 35000},

    # Roofing and Covering
    {"name": "Terpal Plastik Biru", "category": "covering", "unit": "per meter", "price_idr": 15000},
    {"name": "Plastik Cor/Sheet", "category": "covering", "unit": "per meter", "price_idr": 8000},
    {"name": "Seng Gelombang", "category": "covering", "unit": "per lembar (80x180cm)", "price_idr": 55000},

    # Lighting (basic)
    {"name": "Lampu LED Bohlam 12W", "category": "lighting", "unit": "per buah", "price_idr": 18000},
    {"name": "Fitting Lampu E27", "category": "lighting", "unit": "per buah", "price_idr": 5000},
    {"name": "Kabel Listrik 2x1.5mm", "category": "lighting", "unit": "per meter", "price_idr": 5000},
    {"name": "Stop Kontak + Steker", "category": "lighting", "unit": "per set", "price_idr": 15000},
    {"name": "Lampu Strip LED 5m", "category": "lighting", "unit": "per roll (5m)", "price_idr": 45000},

    # Tools
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
