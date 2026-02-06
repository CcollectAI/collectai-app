"""
Import Loungefly bags & accessories catalog.

Layer 1 (Catalog):  Curated Loungefly items → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Disney exclusive backpacks (active & vaulted)
- BoxLunch exclusives
- Hot Topic exclusives
- Marvel / Star Wars lines
- Halloween / holiday limited editions
- Funko Shop exclusives
- Vintage pre-Funko era Loungefly

Usage:
    python -m pipelines.import_loungefly [--dry-run]
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

CATEGORY = "loungefly"


def get_curated_catalog() -> list[dict]:
    """Curated Loungefly bags & accessories catalog."""

    # (franchise, name, item_type, exclusive, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (100-200), mid (50-100), standard (<50)

    items = [
        # Disney exclusive backpacks – active
        ("Disney", "Cinderella Castle Sequin Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 75),
        ("Disney", "Sleeping Beauty Castle Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 70),
        ("Disney", "Mickey Mouse Holographic Mini Backpack", "Mini Backpack", "Disney Parks", "mid", 65),
        ("Disney", "Stitch Shoppe Ariel Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Disney", "Bambi Scenes Mini Backpack", "Mini Backpack", "Standard", "standard", 45),

        # Disney exclusive backpacks – vaulted
        ("Disney", "Villains Scene AOP Mini Backpack", "Mini Backpack", "Vaulted", "high", 180),
        ("Disney", "Fantasia Sorcerer Mickey Sequin Mini Backpack", "Mini Backpack", "Vaulted", "high", 200),
        ("Disney", "Snow White Evil Queen Sequin Mini Backpack", "Mini Backpack", "Vaulted", "high", 160),
        ("Disney", "Haunted Mansion Black Widow Bride Mini Backpack", "Mini Backpack", "Vaulted", "grail", 280),
        ("Disney", "Orange Bird Disney Parks Exclusive Mini Backpack", "Mini Backpack", "Vaulted Disney Parks", "grail", 250),

        # BoxLunch exclusives
        ("Disney", "Wall-E & Eve Boot Plant Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 70),
        ("Disney", "Up Adventure Book Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),
        ("Studio Ghibli", "Spirited Away No-Face Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 72),
        ("Studio Ghibli", "My Neighbor Totoro Catbus Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 68),
        ("Pokemon", "Eevee Evolutions Mini Backpack", "Mini Backpack", "BoxLunch", "mid", 65),

        # Hot Topic exclusives
        ("Disney", "Maleficent Dragon Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),
        ("Sanrio", "Hello Kitty Monster Costumes Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 50),
        ("Disney", "Nightmare Before Christmas Blacklight Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 60),
        ("Disney", "Ursula Iridescent Mini Backpack", "Mini Backpack", "Hot Topic", "mid", 55),

        # Marvel / Star Wars lines
        ("Marvel", "Iron Man Mark 85 Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 45),
        ("Marvel", "Spider-Verse Miles Morales Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Marvel", "Thanos Infinity Gauntlet Mini Backpack", "Mini Backpack", "Standard", "mid", 55),
        ("Star Wars", "Grogu (Baby Yoda) Cradle Mini Backpack", "Mini Backpack", "Standard", "standard", 50),
        ("Star Wars", "Darth Vader Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 48),
        ("Star Wars", "Princess Leia Cosplay Mini Backpack", "Mini Backpack", "Standard", "standard", 45),

        # Halloween / holiday limited editions
        ("Disney", "Mickey & Minnie Halloween Candy Corn Mini Backpack", "Mini Backpack", "Halloween LE", "high", 100),
        ("Disney", "Nightmare Before Christmas Pumpkin King LE Mini Backpack", "Mini Backpack", "Halloween LE", "high", 110),
        ("Disney", "Mickey Mouse Christmas Ugly Sweater Mini Backpack", "Mini Backpack", "Holiday LE", "mid", 85),
        ("Disney", "Stitch Holiday Gingerbread Mini Backpack", "Mini Backpack", "Holiday LE", "mid", 80),

        # Funko Shop exclusives
        ("Funko", "Freddy Funko Cosplay Mini Backpack", "Mini Backpack", "Funko Shop", "high", 120),
        ("Disney", "Fantasia Sorcerer Mickey Funko Pop! Mini Backpack", "Mini Backpack", "Funko Shop", "high", 130),
        ("Marvel", "Venom Blacklight Mini Backpack", "Mini Backpack", "Funko Shop", "high", 100),
        ("Disney", "Alice in Wonderland Blacklight Mini Backpack", "Mini Backpack", "Funko Shop", "high", 140),

        # Vintage pre-Funko era Loungefly
        ("Disney", "Vintage Mickey Embossed Denim Bag", "Shoulder Bag", "Pre-Funko", "grail", 220),
        ("Hello Kitty", "Hello Kitty Vintage Studded Crossbody", "Crossbody Bag", "Pre-Funko", "high", 150),
        ("Disney", "Vintage Tinker Bell Patent Leather Bag", "Shoulder Bag", "Pre-Funko", "high", 180),
        ("Skull & Roses", "Loungefly OG Skull Roses Embroidered Bag", "Shoulder Bag", "Pre-Funko", "grail", 250),
        ("Hello Kitty", "Hello Kitty Quilted Vintage Tote", "Tote Bag", "Pre-Funko", "high", 130),
    ]

    catalog = []
    for franchise, name, item_type, exclusive, tier, price in items:
        catalog.append({
            "franchise": franchise,
            "name": name,
            "item_type": item_type,
            "exclusive": exclusive,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    franchise = item["franchise"]
    name = item["name"]
    item_type = item["item_type"]
    exclusive = item["exclusive"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{franchise}-{name}"),
        title=f"Loungefly {name}",
        set_code=slugify(franchise),
        brand="Loungefly",
        rarity=item["rarity_tier"].title(),
        notes=f"{franchise} | {item_type}" + (f" | {exclusive}" if exclusive else ""),
        attributes_json={
            "franchise": franchise,
            "item_type": item_type,
            "exclusive": exclusive,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}

    exclusive = item["exclusive"]
    edition_scores = {
        "Vaulted": 0.90,
        "Vaulted Disney Parks": 0.95,
        "Disney Parks": 0.75,
        "BoxLunch": 0.65,
        "Hot Topic": 0.60,
        "Funko Shop": 0.80,
        "Halloween LE": 0.75,
        "Holiday LE": 0.70,
        "Pre-Funko": 0.90,
        "Standard": 0.30,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": edition_scores.get(exclusive, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Loungefly catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Loungefly Import ===")

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

    print(f"\n=== Loungefly Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
