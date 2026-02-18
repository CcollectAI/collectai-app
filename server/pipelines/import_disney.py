"""
Import Disney collectibles catalog.

Layer 1 (Catalog):  Curated pins, Loungefly, figures & park items → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (eBay, Mercari, ShopDisney)
- Covers Disney pins (LE, park exclusive), Loungefly, D23 figures,
  vintage items, designer ears, and limited ornaments

Usage:
    python -m pipelines.import_disney [--dry-run]
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

CATEGORY = "disney"


def get_curated_catalog() -> list[dict]:
    """Curated Disney collectibles catalog."""

    # (subcategory, name, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (80-200), mid (30-80), standard (<30)

    items = [
        # Disney Pins - Limited Edition
        ("pins", "Haunted Mansion 50th Anniversary LE 2500 Pin", "LE 2500", "high", 120),
        ("pins", "Nightmare Before Christmas 30th LE 3000 Pin", "LE 3000", "high", 95),
        ("pins", "Walt Disney Portrait LE 1000 Pin", "LE 1000", "grail", 200),
        ("pins", "Figment Epcot 40th Anniversary LE 4000 Pin", "LE 4000", "high", 80),
        ("pins", "Stitch Crashes Disney Complete Set (12 Pins)", "LE Monthly", "grail", 450),
        ("pins", "Stitch Crashes Disney Single Pin", "LE Monthly", "mid", 40),
        ("pins", "Disney Villains LE 5000 Pin Set", "LE 5000", "high", 90),

        # Disney Pins - Park Exclusive
        ("pins", "Disneyland 70th Anniversary Park Pin", "Park Exclusive", "mid", 35),
        ("pins", "EPCOT Festival of the Arts Pin", "Park Exclusive", "mid", 30),
        ("pins", "Magic Kingdom 50th Anniversary Pin", "Park Exclusive", "mid", 45),
        ("pins", "Disney Pin Trading Starter Set", "Standard", "standard", 15),
        ("pins", "Hidden Mickey Pin (Rare Character)", "Park Exclusive", "mid", 25),
        ("pins", "Disney Cast Member Exclusive Pin", "Cast Exclusive", "high", 80),

        # Loungefly
        ("loungefly", "Loungefly Haunted Mansion Mini Backpack", "Standard", "mid", 65),
        ("loungefly", "Loungefly Villains AOP Backpack", "Standard", "mid", 55),
        ("loungefly", "Loungefly Enchanted Tiki Room Crossbody", "Park Exclusive", "high", 85),
        ("loungefly", "Loungefly Figment Epcot Backpack", "Park Exclusive", "high", 95),
        ("loungefly", "Loungefly Disney Princess Wallet Set", "Standard", "mid", 40),
        ("loungefly", "Loungefly NYCC Exclusive Maleficent Bag", "NYCC Exclusive", "high", 130),
        ("loungefly", "Loungefly Disney100 Platinum Backpack", "D100 Exclusive", "high", 110),

        # Figures - D23 & Limited
        ("figures", "D23 Exclusive Sorcerer Mickey Figure", "D23 Exclusive", "grail", 200),
        ("figures", "D23 Exclusive Villain Designer Doll", "D23 Exclusive", "high", 180),
        ("figures", "Disney Designer Collection Ariel Doll", "Designer LE", "high", 150),
        ("figures", "Disney Designer Collection Belle Doll", "Designer LE", "high", 140),
        ("figures", "Jim Shore Fantasia 80th Anniversary Figure", "Limited", "high", 95),
        ("figures", "Walt Disney Archives Figure (50th)", "Park Exclusive", "mid", 65),

        # Vintage Disney
        ("vintage", "Vintage Disneyland 1960s Park Map", "Vintage", "grail", 350),
        ("vintage", "Vintage Walt Disney World Opening Day Ticket", "Vintage", "grail", 500),
        ("vintage", "Vintage Disney Pin-back Button Set (1970s)", "Vintage", "high", 80),
        ("vintage", "Vintage EPCOT Center Opening Poster", "Vintage", "high", 150),

        # Disney Ears
        ("ears", "Designer Minnie Ears by Vera Wang", "Designer", "high", 95),
        ("ears", "50th Anniversary Gold Ears", "LE Park", "mid", 55),
        ("ears", "Spirit Jersey Matching Ears Set", "Seasonal", "mid", 40),
        ("ears", "Disney Parks Loungefly Ears (Haunted Mansion)", "Park Exclusive", "mid", 45),
        ("ears", "Disney Parks Sequin Ears Rose Gold", "Park Exclusive", "mid", 35),
        ("ears", "Walt Disney World Marathon Ears", "Event Exclusive", "high", 80),

        # Ornaments
        ("ornaments", "Hallmark Disney Castle LE Ornament", "LE", "mid", 50),
        ("ornaments", "Disney Sketchbook Legacy Ornament Set", "Limited", "mid", 45),
        ("ornaments", "Disney Parks 50th Anniversary Ornament", "Park Exclusive", "mid", 35),
        ("ornaments", "Swarovski Disney Castle Ornament", "Premium", "high", 80),
        ("ornaments", "Radko Disney Ornament (Vintage)", "Vintage", "high", 75),
    ]

    catalog = []
    for subcategory, name, edition, tier, price in items:
        catalog.append({
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    name = item["name"]
    edition = item["edition"]
    subcategory = item["subcategory"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{subcategory}-{name}"),
        title=name,
        set_code=subcategory,
        brand="Disney",
        rarity=item["rarity_tier"].title(),
        notes=f"{subcategory} | {edition}",
        attributes_json={
            "subcategory": subcategory,
            "edition": edition,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    edition = item["edition"]
    edition_map = {
        "LE 1000": 0.95, "LE 2500": 0.85, "LE 3000": 0.8,
        "LE 4000": 0.75, "LE 5000": 0.7, "LE Monthly": 0.7,
        "D23 Exclusive": 0.9, "Designer LE": 0.85, "NYCC Exclusive": 0.85,
        "D100 Exclusive": 0.8, "Cast Exclusive": 0.8,
        "Park Exclusive": 0.65, "LE Park": 0.65,
        "Designer": 0.7, "Event Exclusive": 0.7,
        "Vintage": 0.8, "Premium": 0.7,
        "Limited": 0.6, "LE": 0.6, "Seasonal": 0.4,
        "Standard": 0.2,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_map.get(edition, 0.4),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Disney collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Disney Import ===")

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

    logger.info(f"\n=== Disney Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
