"""
Import K-pop lightstick catalog.

Layer 1 (Catalog):  Curated K-pop lightsticks & tour editions → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (official stores, resale platforms)
- Covers BTS, Blackpink, TWICE, Stray Kids, ATEEZ, EXO, and more
- Tour-exclusive versions command 2-3x premium

Usage:
    python -m pipelines.import_kpop_lightsticks [--dry-run]
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

CATEGORY = "kpop_lightsticks"


def get_curated_catalog() -> list[dict]:
    """Curated K-pop lightstick catalog."""

    # (group, name, version, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>100), high (60-100), mid (30-60), standard (<30)

    items = [
        # BTS ARMY Bomb
        ("BTS", "ARMY Bomb Ver. 1", "v1", "Original", "high", 90),
        ("BTS", "ARMY Bomb Ver. 2", "v2", "Standard", "high", 80),
        ("BTS", "ARMY Bomb Ver. 3", "v3", "Standard", "mid", 55),
        ("BTS", "ARMY Bomb Ver. 4", "v4", "Standard", "mid", 45),
        ("BTS", "ARMY Bomb Special Edition (Map of the Soul)", "SE", "Tour Exclusive", "grail", 120),
        ("BTS", "ARMY Bomb Special Edition (Yet To Come)", "SE-YTC", "Tour Exclusive", "high", 95),

        # Blackpink
        ("Blackpink", "Blackpink Official Lightstick Ver. 1", "v1", "Original", "mid", 50),
        ("Blackpink", "Blackpink Official Lightstick Ver. 2", "v2", "Standard", "mid", 40),
        ("Blackpink", "Blackpink Born Pink Tour Lightstick", "v2-tour", "Tour Exclusive", "high", 80),

        # TWICE Candy Bong
        ("TWICE", "Candy Bong Ver. 1", "v1", "Original", "high", 70),
        ("TWICE", "Candy Bong Z (Ver. 2)", "v2", "Standard", "mid", 45),
        ("TWICE", "Candy Bong Infinity", "Infinity", "Standard", "mid", 50),
        ("TWICE", "Candy Bong Ready To Be Tour Edition", "v2-tour", "Tour Exclusive", "high", 80),

        # Stray Kids Nachimbong
        ("Stray Kids", "Nachimbong Ver. 1", "v1", "Original", "mid", 45),
        ("Stray Kids", "Nachimbong Ver. 2", "v2", "Standard", "mid", 38),
        ("Stray Kids", "Nachimbong Maniac Tour Edition", "v1-tour", "Tour Exclusive", "high", 75),

        # ATEEZ
        ("ATEEZ", "Lightiny Ver. 1", "v1", "Standard", "mid", 35),
        ("ATEEZ", "Lightiny Ver. 2", "v2", "Standard", "mid", 40),
        ("ATEEZ", "Lightiny Tour Edition", "v2-tour", "Tour Exclusive", "high", 70),

        # EXO
        ("EXO", "EXO Official Lightstick Ver. 3 (Pharynx)", "v3", "Standard", "mid", 40),
        ("EXO", "EXO Official Lightstick Ver. 2", "v2", "Original", "high", 65),
        ("EXO", "EXO Pharynx EXO'rdium Tour Edition", "v2-tour", "Tour Exclusive", "high", 80),

        # Seventeen
        ("Seventeen", "Carat Bong Ver. 1", "v1", "Original", "high", 70),
        ("Seventeen", "Carat Bong Ver. 2", "v2", "Standard", "mid", 45),
        ("Seventeen", "Carat Bong Ver. 3", "v3", "Standard", "mid", 40),

        # Other groups
        ("NCT", "NCT Official Lightstick", "v1", "Standard", "mid", 38),
        ("Red Velvet", "Red Velvet Official Lightstick", "v1", "Standard", "mid", 42),
        ("ITZY", "ITZY Official Lightstick", "v1", "Standard", "mid", 35),
        ("aespa", "aespa Official Lightstick", "v1", "Standard", "mid", 38),
        ("IVE", "IVE Official Lightstick", "v1", "Standard", "standard", 30),
        ("NewJeans", "NewJeans Official Lightstick", "v1", "Standard", "mid", 38),
        ("ENHYPEN", "ENHYPEN Official Lightstick", "v1", "Standard", "mid", 35),
        ("TXT", "MOA Lightstick", "v1", "Standard", "mid", 38),

        # Vintage / Discontinued
        ("SHINee", "SHINee Official Lightstick", "v1", "Discontinued", "high", 85),
        ("2NE1", "2NE1 Official Lightstick", "v1", "Discontinued", "grail", 110),
        ("BIGBANG", "BIGBANG Crown Lightstick", "v1", "Discontinued", "grail", 100),
    ]

    catalog = []
    for group, name, version, variant, tier, price in items:
        catalog.append({
            "group": group,
            "name": name,
            "version": version,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    group = item["group"]
    name = item["name"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{group}-{name}"),
        title=f"{group} - {name}",
        set_code=group.lower().replace(" ", "-"),
        brand=group,
        rarity=item["rarity_tier"].title(),
        notes=f"{group} | {item['version']} | {variant}",
        attributes_json={
            "group": group,
            "version": item["version"],
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}

    variant = item["variant"]
    edition_map = {
        "Tour Exclusive": 0.85, "Discontinued": 0.8,
        "Original": 0.6, "Standard": 0.3,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": edition_map.get(variant, 0.4),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import K-pop lightstick catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== K-pop Lightsticks Import ===")

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

    print(f"\n=== K-pop Lightsticks Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
