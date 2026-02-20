"""
Import Scale Model Kits catalog.

Layer 1 (Catalog):  Curated scale model kits (85+ items) → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Aircraft: Tamiya 1/32 & 1/48, Hasegawa, Eduard, Trumpeter, Revell, Airfix, Academy, ICM
- Armor: Tamiya, Trumpeter, Dragon, Meng, Rye Field, Takom 1/35 tanks
- Ships: Tamiya, Trumpeter, Revell, Fujimi, Academy 1/200–1/570
- Cars: Tamiya 1/12 & 1/24, Hasegawa, Beemax, NuNu, Aoshima, Fujimi
- Sci-fi: Bandai Star Wars, Moebius, Pegasus, Kotobukiya, Fine Molds
- Figures: Tamiya, MasterBox, Alpine Miniatures, Nutsplanet
- Diorama/Accessories: Tamiya, MiniArt

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
    rarity_score as shared_rarity_score,
    RARITY_SCORE_MAP,
    logger,
    close_http_client,
)

CATEGORY = "scale_models"


def get_curated_catalog() -> list[dict]:
    """Curated scale model kit catalog — 88 items across 7 subcategories."""

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

        # === NEW ITEMS (38 additions below) ===

        # More Aircraft (+8)
        ("Tamiya", "Aircraft", "Supermarine Spitfire Mk.I", "1/32", "high", 95),
        ("Hasegawa", "Aircraft", "F-14A Tomcat High Visibility", "1/48", "mid", 52),
        ("Trumpeter", "Aircraft", "Su-27 Flanker B", "1/32", "grail", 160),
        ("Eduard", "Aircraft", "Bf 109 G-6 Late ProfiPACK", "1/48", "mid", 46),
        ("Revell", "Aircraft", "B-17G Flying Fortress", "1/72", "mid", 42),
        ("Airfix", "Aircraft", "Supermarine Spitfire Mk.IXc", "1/24", "high", 130),
        ("Academy", "Aircraft", "F-22A Raptor", "1/72", "standard", 28),
        ("ICM", "Aircraft", "P-51D-15 Mustang", "1/48", "mid", 38),

        # More Armor (+6)
        ("Tamiya", "Armor", "Panther Ausf.D", "1/35", "mid", 52),
        ("Trumpeter", "Armor", "T-34/76 Model 1943", "1/35", "mid", 42),
        ("Dragon", "Armor", "King Tiger Henschel Turret", "1/35", "high", 85),
        ("Meng Model", "Armor", "Merkava Mk.4/4LIC", "1/35", "high", 82),
        ("RFM (Rye Field Model)", "Armor", "M1A1 Abrams w/ Full Interior", "1/35", "high", 90),
        ("Takom", "Armor", "Panzer III Ausf.M w/ Schurzen", "1/35", "mid", 55),

        # More Ships (+6)
        ("Tamiya", "Ship", "USS Enterprise CVN-65", "1/350", "grail", 190),
        ("Trumpeter", "Ship", "HMS Hood", "1/200", "grail", 250),
        ("Revell", "Ship", "RMS Titanic", "1/570", "mid", 45),
        ("Pontos", "Ship", "Yamato Detail-Up Set", "1/350", "grail", 280),
        ("Fujimi", "Ship", "IJN Akagi (Full Hull)", "1/350", "grail", 165),
        ("Academy", "Ship", "USS Missouri BB-63", "1/350", "high", 110),

        # More Cars (+6)
        ("Tamiya", "Car", "Ferrari 312T", "1/12", "grail", 220),
        ("Hasegawa", "Car", "Lancia Stratos HF", "1/24", "mid", 48),
        ("Beemax", "Car", "Audi Quattro S1 E2", "1/24", "mid", 55),
        ("NuNu", "Car", "BMW M3 E30 Gr.A 1988 Spa", "1/24", "mid", 45),
        ("Aoshima", "Car", "Toyota AE86 Sprinter Trueno", "1/24", "standard", 35),
        ("Fujimi", "Car", "Honda Civic EF9 Gr.A", "1/24", "mid", 40),

        # More Sci-Fi (+6)
        ("Bandai", "Sci-fi", "Star Wars X-Wing Starfighter (Red Five)", "1/72", "mid", 44),
        ("Bandai", "Sci-fi", "Star Wars AT-AT (Empire Strikes Back)", "1/144", "mid", 58),
        ("Moebius", "Sci-fi", "USS Enterprise NCC-1701 Refit", "1/350", "high", 140),
        ("Pegasus", "Sci-fi", "War of the Worlds Alien Machine", "1/32", "high", 85),
        ("Kotobukiya", "Sci-fi", "Frame Arms Baselard", "1/100", "mid", 52),
        ("Fine Molds", "Sci-fi", "Millennium Falcon", "1/72", "grail", 195),

        # Figures (+4)
        ("Tamiya", "Figure", "German Infantry Set (Late WWII)", "1/35", "standard", 18),
        ("MasterBox", "Figure", "US Paratroopers 1944", "1/35", "standard", 22),
        ("Alpine Miniatures", "Figure", "WSS Panzer Officer Resin Bust", "1/16", "high", 85),
        ("Nutsplanet", "Figure", "Fantasy Barbarian Resin Bust", "1/10", "high", 95),

        # Diorama / Accessories (+2)
        ("Tamiya", "Diorama", "Diorama Texture Paint Soil Effect Set", "N/A", "standard", 15),
        ("MiniArt", "Diorama", "European Village Building Ruins", "1/35", "standard", 32),
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
            "rarity_score": shared_rarity_score(tier),
            "edition_score": round(edition_score, 2),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Scale Models catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Scale Models Import ===")

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

    logger.info(f"\n=== Scale Models Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
