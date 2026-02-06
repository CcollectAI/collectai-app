"""
Import Scale Model Kits catalog.

Layer 1 (Catalog):  Curated scale model kits → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Aircraft: Tamiya 1/48, Hasegawa, Eduard (WWII fighters, jets)
- Armor: Tamiya 1/35 tanks (Tiger, Sherman, Leopard)
- Ships: 1/350 Yamato, Bismarck, carriers
- Cars: Tamiya 1/24 sports cars
- Sci-fi: Bandai Star Wars kits, Moebius

Usage:
    python -m pipelines.import_scale_models [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem, PriceObservation, SupabaseIngest,
    write_training_jsonl, write_catalog_sql,
    log_progress, slugify,
)

CATEGORY = "scale_models"


def get_curated_catalog() -> list[dict]:
    """Curated scale model kit catalog covering key categories and manufacturers."""

    # (manufacturer, model_type, name, scale, rarity_tier, price_eur)
    # rarity_tier: grail (>150), high (80-150), mid (40-80), standard (<40)

    kits = [
        # Aircraft - WWII Fighters
        ("Tamiya", "Aircraft", "Spitfire Mk.IXc", "1/48", "mid", 42),
        ("Tamiya", "Aircraft", "P-51D Mustang", "1/48", "mid", 45),
        ("Tamiya", "Aircraft", "Bf 109 G-6", "1/48", "mid", 40),
        ("Tamiya", "Aircraft", "Fw 190 D-9", "1/48", "mid", 42),
        ("Tamiya", "Aircraft", "Zero Fighter Type 52 (Zeke)", "1/48", "mid", 38),
        ("Hasegawa", "Aircraft", "P-47D Thunderbolt", "1/48", "mid", 35),
        ("Hasegawa", "Aircraft", "Ki-84 Hayate (Frank)", "1/48", "standard", 32),
        ("Eduard", "Aircraft", "Spitfire Mk.I Profipack", "1/48", "mid", 48),
        ("Eduard", "Aircraft", "Bf 109 E-4 Profipack", "1/48", "mid", 45),
        ("Eduard", "Aircraft", "Fw 190 A-8 Profipack", "1/48", "mid", 50),

        # Aircraft - Jets
        ("Tamiya", "Aircraft", "F-14A Tomcat", "1/48", "high", 95),
        ("Tamiya", "Aircraft", "F-16CJ Fighting Falcon", "1/48", "mid", 55),
        ("Hasegawa", "Aircraft", "F-4E Phantom II", "1/48", "mid", 50),
        ("Tamiya", "Aircraft", "F-35A Lightning II", "1/48", "high", 85),
        ("GWH (Great Wall Hobby)", "Aircraft", "Su-27 Flanker B", "1/48", "high", 90),
        ("Tamiya", "Aircraft", "A-10 Thunderbolt II", "1/48", "high", 110),

        # Armor - Tanks
        ("Tamiya", "Armor", "Tiger I Late Production", "1/35", "mid", 55),
        ("Tamiya", "Armor", "King Tiger (Production Turret)", "1/35", "mid", 60),
        ("Tamiya", "Armor", "M4A3E8 Sherman Easy Eight", "1/35", "mid", 45),
        ("Tamiya", "Armor", "Panther Ausf.G", "1/35", "mid", 50),
        ("Tamiya", "Armor", "Leopard 2A6", "1/35", "mid", 65),
        ("Tamiya", "Armor", "M1A2 SEP Abrams TUSK II", "1/35", "mid", 70),
        ("Tamiya", "Armor", "T-34/85", "1/35", "standard", 30),
        ("Meng Model", "Armor", "Merkava Mk.4M w/ Trophy APS", "1/35", "high", 80),
        ("RFM (Rye Field Model)", "Armor", "Tiger I Early w/ Full Interior", "1/35", "high", 85),
        ("Takom", "Armor", "Maus V1 Super Heavy Tank", "1/35", "high", 75),

        # Ships
        ("Tamiya", "Ship", "Yamato (Premium Edition)", "1/350", "grail", 200),
        ("Tamiya", "Ship", "Bismarck", "1/350", "high", 120),
        ("Tamiya", "Ship", "USS Enterprise CV-6", "1/350", "high", 130),
        ("Tamiya", "Ship", "King George V", "1/350", "high", 100),
        ("Fujimi", "Ship", "IJN Akagi", "1/350", "high", 150),
        ("Trumpeter", "Ship", "USS Nimitz CVN-68", "1/350", "grail", 180),

        # Cars
        ("Tamiya", "Car", "Toyota GR Supra", "1/24", "standard", 32),
        ("Tamiya", "Car", "Nissan GT-R (R35)", "1/24", "standard", 35),
        ("Tamiya", "Car", "Ferrari FXX K", "1/24", "mid", 45),
        ("Tamiya", "Car", "Porsche 911 GT3 RS", "1/24", "mid", 42),
        ("Tamiya", "Car", "Mercedes-AMG GT3", "1/24", "mid", 40),
        ("Tamiya", "Car", "Ford GT", "1/24", "standard", 35),
        ("Tamiya", "Car", "LaFerrari", "1/24", "mid", 48),
        ("Hasegawa", "Car", "Toyota 2000GT", "1/24", "mid", 55),

        # Sci-fi
        ("Bandai", "Sci-fi", "Star Wars X-Wing Starfighter", "1/72", "mid", 40),
        ("Bandai", "Sci-fi", "Star Wars Millennium Falcon", "1/144", "high", 85),
        ("Bandai", "Sci-fi", "Star Wars Star Destroyer", "1/5000", "high", 100),
        ("Bandai", "Sci-fi", "Star Wars AT-AT", "1/144", "mid", 55),
        ("Bandai", "Sci-fi", "Star Wars TIE Fighter", "1/72", "standard", 28),
        ("Moebius", "Sci-fi", "Battlestar Galactica", "1/4105", "high", 120),
        ("Moebius", "Sci-fi", "1966 Batmobile", "1/25", "mid", 45),
        ("Bandai", "Sci-fi", "Star Wars Y-Wing Starfighter", "1/72", "mid", 42),
    ]

    catalog = []
    for manufacturer, model_type, name, scale, tier, price in kits:
        catalog.append({
            "manufacturer": manufacturer,
            "model_type": model_type,
            "name": name,
            "scale": scale,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    manufacturer = item["manufacturer"]
    name = item["name"]
    model_type = item["model_type"]
    scale = item["scale"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{manufacturer}-{name}-{scale}"),
        title=f"{name} ({scale})",
        set_code=slugify(model_type),
        brand=manufacturer,
        rarity=item["rarity_tier"].title(),
        notes=f"{manufacturer} | {model_type} | {scale}",
        attributes_json={
            "manufacturer": manufacturer,
            "model_type": model_type,
            "scale": scale,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}

    model_type = item["model_type"]
    type_scores = {
        "Aircraft": 0.5,
        "Armor": 0.5,
        "Ship": 0.7,
        "Car": 0.4,
        "Sci-fi": 0.6,
    }

    manufacturer = item["manufacturer"]
    mfr_scores = {
        "Tamiya": 0.7,
        "Hasegawa": 0.5,
        "Eduard": 0.6,
        "Bandai": 0.6,
        "Meng Model": 0.6,
        "RFM (Rye Field Model)": 0.65,
        "Takom": 0.5,
        "GWH (Great Wall Hobby)": 0.55,
        "Fujimi": 0.5,
        "Trumpeter": 0.5,
        "Moebius": 0.6,
    }

    edition_score = (type_scores.get(model_type, 0.5) + mfr_scores.get(manufacturer, 0.5)) / 2

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": round(edition_score, 2),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Scale Models catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Scale Models Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()

    all_items = [item_to_catalog_item(i) for i in catalog]
    all_observations = [item_to_price_observation(i) for i in catalog]

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()

    print(f"\n=== Scale Models Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
