"""
Import Nintendo & Pokemon merchandise data (non-cards).

Layer 1 (Catalog):  Curated plush, amiibo, figures, exclusives → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Pokemon Center, amiibo, Nintendo Store exclusives
- Covers: Pokemon, Mario, Zelda, Kirby, Splatoon, Animal Crossing

Usage:
    python -m pipelines.import_nintendo_merch [--dry-run]
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

CATEGORY = "nintendo_merch"


def get_curated_catalog() -> list[dict]:
    """Curated Nintendo / Pokemon merchandise catalog."""

    # Format: (franchise, product_type, name, exclusive, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (80-200), mid (30-80), standard (<30)

    merch = [
        # Pokemon Center Plush - Standard
        ("Pokemon", "Plush", "Pikachu Sitting Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Eevee Sitting Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Charizard Plush 12in", "", "standard", 28),
        ("Pokemon", "Plush", "Gengar Plush 8in", "", "standard", 20),
        ("Pokemon", "Plush", "Snorlax Plush 12in", "", "standard", 25),

        # Pokemon Center Plush - Exclusive / Limited
        ("Pokemon", "Plush", "Pikachu Halloween Costume Plush", "Pokemon Center", "mid", 45),
        ("Pokemon", "Plush", "Mimikyu Giant Plush 24in", "Pokemon Center", "high", 120),
        ("Pokemon", "Plush", "Snorlax Bean Bag Chair 60in", "Pokemon Center", "grail", 280),
        ("Pokemon", "Plush", "Life-Size Arcanine Plush", "Pokemon Center JP", "grail", 300),
        ("Pokemon", "Plush", "Ditto Transform Pikachu Plush", "Pokemon Center", "mid", 35),
        ("Pokemon", "Plush", "Eeveelution Collection Box Set", "Pokemon Center", "high", 180),
        ("Pokemon", "Plush", "Sitting Cuties Full Kanto Set", "Pokemon Center", "grail", 250),
        ("Pokemon", "Plush", "Scarlet & Violet Starter Set", "Pokemon Center", "mid", 50),

        # Amiibo - Common
        ("Mario", "Amiibo", "Mario (Super Smash Bros.)", "", "standard", 15),
        ("Zelda", "Amiibo", "Link (Breath of the Wild)", "", "standard", 18),
        ("Pokemon", "Amiibo", "Pikachu (Super Smash Bros.)", "", "standard", 15),
        ("Splatoon", "Amiibo", "Inkling Girl (Splatoon 3)", "", "standard", 14),

        # Amiibo - Rare / Out of Print
        ("Mario", "Amiibo", "Gold Mario", "Walmart Exclusive", "high", 80),
        ("Animal Crossing", "Amiibo", "Villager (1st Print)", "", "high", 100),
        ("Zelda", "Amiibo", "Guardian (Breath of the Wild)", "", "high", 90),
        ("Splatoon", "Amiibo", "Callie & Marie 2-Pack", "", "high", 120),
        ("Zelda", "Amiibo", "Link (Skyward Sword)", "", "mid", 50),
        ("Kirby", "Amiibo", "Meta Knight", "Best Buy Exclusive", "high", 80),
        ("Pokemon", "Amiibo", "Mewtwo (Super Smash Bros.)", "", "mid", 45),
        ("Mario", "Amiibo", "Samus (Metroid Dread)", "", "mid", 40),
        ("Zelda", "Amiibo", "Zelda & Loftwing", "", "high", 85),
        ("Zelda", "Amiibo", "Link (Tears of the Kingdom)", "", "mid", 35),

        # Pokemon Center Exclusive Figures
        ("Pokemon", "Figure", "Charizard Premium Figure", "Pokemon Center", "mid", 65),
        ("Pokemon", "Figure", "Mewtwo Gallery Figure DX", "Pokemon Center", "mid", 55),
        ("Pokemon", "Figure", "Pikachu VMAX Premium Figure", "Pokemon Center", "mid", 45),
        ("Pokemon", "Figure", "Rayquaza Gallery Figure", "Pokemon Center", "mid", 60),
        ("Pokemon", "Figure", "Legendary Birds Articuno Set", "Pokemon Center", "high", 80),

        # Nintendo Store Exclusives
        ("Mario", "Merch", "Super Mario Odyssey Coin Set", "Nintendo Store", "mid", 40),
        ("Zelda", "Merch", "Master Sword Replica Light", "Nintendo Store", "mid", 55),
        ("Mario", "Merch", "Mario Red Joy-Con Set", "Nintendo Store", "mid", 65),
        ("Kirby", "Merch", "Kirby Cafe Menu Plate Set", "Nintendo Store JP", "high", 85),
        ("Splatoon", "Merch", "Splatoon 3 Tableturf Battle Cards", "Nintendo Store", "mid", 30),
        ("Animal Crossing", "Merch", "Tom Nook Ceramic Mug Set", "Nintendo Store", "standard", 25),

        # Limited Event Items
        ("Pokemon", "Event", "Worlds 2023 Pikachu Plush", "Pokemon Worlds", "high", 150),
        ("Pokemon", "Event", "Pokemon Center 25th Anniversary Box", "Pokemon Center", "grail", 250),
        ("Mario", "Event", "Super Nintendo World Mario Hat", "Universal Studios JP", "mid", 60),
        ("Zelda", "Event", "Tears of the Kingdom Collector Pin Set", "Nintendo Store", "mid", 50),
        ("Pokemon", "Event", "GO Fest 2023 Exclusive Plush", "Pokemon GO Fest", "high", 100),
        ("Splatoon", "Event", "Splatoon Koshien Trophy Replica", "Nintendo JP", "grail", 200),
    ]

    catalog = []
    for franchise, product_type, name, exclusive, tier, price in merch:
        catalog.append({
            "franchise": franchise,
            "product_type": product_type,
            "name": name,
            "exclusive": exclusive,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    franchise = item["franchise"]
    product_type = item["product_type"]
    name = item["name"]
    exclusive = item["exclusive"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{franchise}-{product_type}-{name}"),
        title=name,
        set_code=franchise.lower().replace(" ", "-"),
        brand="Nintendo" if franchise in ("Mario", "Zelda", "Kirby", "Splatoon", "Animal Crossing") else "Pokemon Company",
        rarity=item["rarity_tier"].title(),
        notes=f"{franchise} | {product_type}" + (f" | {exclusive}" if exclusive else ""),
        attributes_json={
            "franchise": franchise,
            "product_type": product_type,
            "exclusive": exclusive,
            "is_amiibo": product_type == "Amiibo",
            "is_plush": product_type == "Plush",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}
    exclusive_score = 0.85 if item["exclusive"] else 0.3

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": exclusive_score,
            "is_amiibo": 1.0 if item["product_type"] == "Amiibo" else 0.0,
            "is_plush": 1.0 if item["product_type"] == "Plush" else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Nintendo / Pokemon merch catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Nintendo Merch Import ===")

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

    print(f"\n=== Nintendo Merch Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
