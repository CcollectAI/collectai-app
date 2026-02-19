"""
Import K-pop merchandise catalog.

Layer 1 (Catalog):  Curated K-pop photocards, albums & exclusives → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (albums, photocards, fansign items)
- Covers BTS, Blackpink, Stray Kids, ATEEZ, Enhypen, Weverse exclusives

Usage:
    python -m pipelines.import_kpop [--dry-run]
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

CATEGORY = "kpop_merch"


def get_curated_catalog() -> list[dict]:
    """Curated K-pop merchandise catalog covering albums, photocards & exclusives."""

    # (group, item_type, name, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (80-200), mid (30-80), standard (<30)

    items = [
        # BTS Photocards
        ("BTS", "photocard", "Jungkook Fansign Photocard", "Fansign Event", "grail", 450),
        ("BTS", "photocard", "V Fansign Photocard", "Fansign Event", "grail", 420),
        ("BTS", "photocard", "Jimin Butter Lucky Draw", "Lucky Draw", "grail", 380),
        ("BTS", "photocard", "SUGA D-Day POB Photocard", "Pre-order Benefit", "high", 120),
        ("BTS", "photocard", "Jin The Astronaut Photocard", "Album POB", "high", 90),
        ("BTS", "photocard", "RM Indigo Weverse POB", "Weverse Exclusive", "mid", 55),
        ("BTS", "photocard", "J-Hope Jack In The Box POB", "Album POB", "mid", 50),
        ("BTS", "photocard", "BTS Proof Standard Photocard", "Standard", "standard", 8),

        # BTS Albums
        ("BTS", "album", "BTS Proof Collector's Edition", "Collector's Edition", "high", 180),
        ("BTS", "album", "BTS Proof Standard", "Standard", "standard", 22),
        ("BTS", "album", "Map of the Soul: 7 (Version 4)", "Limited Version", "high", 85),
        ("BTS", "album", "Map of the Soul: 7", "Standard", "standard", 20),
        ("BTS", "album", "BE Deluxe Edition", "Deluxe", "high", 95),
        ("BTS", "album", "BE Essential Edition", "Standard", "standard", 18),
        ("BTS", "album", "BTS Wings", "Standard", "mid", 45),
        ("BTS", "album", "BTS Young Forever Night Version", "Night Ver.", "high", 120),

        # Blackpink
        ("Blackpink", "album", "The Album Version 3 (Lisa)", "Limited", "mid", 55),
        ("Blackpink", "album", "The Album Standard", "Standard", "standard", 20),
        ("Blackpink", "album", "Born Pink Digipack Lisa", "Digipack", "mid", 35),
        ("Blackpink", "album", "Born Pink Limited Edition Vinyl", "Limited Vinyl", "high", 130),
        ("Blackpink", "album", "Born Pink Standard", "Standard", "standard", 18),
        ("Blackpink", "photocard", "Jennie Fansign Photocard", "Fansign Event", "grail", 500),
        ("Blackpink", "photocard", "Lisa Signed Polaroid", "Signed", "grail", 350),

        # Stray Kids — Albums
        ("Stray Kids", "album", "ATE Limited Edition", "Limited", "mid", 45),
        ("Stray Kids", "album", "ATE Standard", "Standard", "standard", 18),
        ("Stray Kids", "album", "5-STAR Limited Star Ver.", "Limited Star", "mid", 42),
        ("Stray Kids", "album", "5-STAR Standard", "Standard", "standard", 18),
        ("Stray Kids", "album", "MAXIDENT Limited Edition", "Limited", "mid", 40),
        ("Stray Kids", "album", "MAXIDENT Standard", "Standard", "standard", 16),
        ("Stray Kids", "album", "ODDINARY Limited Edition", "Limited", "mid", 38),
        ("Stray Kids", "album", "ODDINARY Jewel Case", "Jewel Case", "standard", 15),
        ("Stray Kids", "album", "NOEASY Limited Edition", "Limited", "high", 85),
        ("Stray Kids", "album", "NOEASY Standard", "Standard", "standard", 20),
        ("Stray Kids", "album", "IN LIFE Limited Edition", "Limited", "high", 95),
        ("Stray Kids", "album", "GO LIVE Limited Edition", "Limited", "high", 90),
        ("Stray Kids", "album", "Clé: LEVANTER Limited", "Limited", "high", 110),
        ("Stray Kids", "album", "I am NOT Standard", "Standard", "mid", 45),
        ("Stray Kids", "album", "Mixtape Standard", "Standard", "high", 130),

        # Stray Kids — Photocards (by member)
        ("Stray Kids", "photocard", "Bang Chan Video Call Fansign", "Fansign Event", "grail", 250),
        ("Stray Kids", "photocard", "Bang Chan POB Photocard", "Pre-order Benefit", "mid", 40),
        ("Stray Kids", "photocard", "Lee Know Video Call Fansign", "Fansign Event", "grail", 320),
        ("Stray Kids", "photocard", "Lee Know Lucky Draw", "Lucky Draw", "high", 150),
        ("Stray Kids", "photocard", "Changbin Fansign Photocard", "Fansign Event", "high", 180),
        ("Stray Kids", "photocard", "Changbin POB Photocard", "Pre-order Benefit", "mid", 35),
        ("Stray Kids", "photocard", "Hyunjin Video Call Fansign", "Fansign Event", "grail", 380),
        ("Stray Kids", "photocard", "Hyunjin POB Photocard", "Pre-order Benefit", "mid", 45),
        ("Stray Kids", "photocard", "Hyunjin Lucky Draw", "Lucky Draw", "high", 200),
        ("Stray Kids", "photocard", "Han Video Call Fansign", "Fansign Event", "grail", 260),
        ("Stray Kids", "photocard", "Han POB Photocard", "Pre-order Benefit", "mid", 38),
        ("Stray Kids", "photocard", "Felix Video Call Fansign", "Fansign Event", "grail", 350),
        ("Stray Kids", "photocard", "Felix Lucky Draw", "Lucky Draw", "high", 180),
        ("Stray Kids", "photocard", "Felix POB Photocard", "Pre-order Benefit", "mid", 50),
        ("Stray Kids", "photocard", "Seungmin Fansign Photocard", "Fansign Event", "high", 170),
        ("Stray Kids", "photocard", "Seungmin POB Photocard", "Pre-order Benefit", "mid", 30),
        ("Stray Kids", "photocard", "I.N Fansign Photocard", "Fansign Event", "high", 160),
        ("Stray Kids", "photocard", "I.N POB Photocard", "Pre-order Benefit", "standard", 25),

        # Stray Kids — Merch & Collectibles
        ("Stray Kids", "merch", "SKZ Nachibong Ver.2 Lightstick", "Official", "mid", 45),
        ("Stray Kids", "merch", "MANIAC World Tour Photobook", "Tour Exclusive", "high", 80),
        ("Stray Kids", "merch", "Stray Kids x SLBS Skzoo Plush", "Collaboration", "mid", 35),
        ("Stray Kids", "merch", "Stray Kids 2nd World Tour Merch Set", "Tour Exclusive", "high", 120),
        ("Stray Kids", "merch", "SKZ REPLAY DVD Limited", "Limited", "high", 90),
        ("Stray Kids", "merch", "Stray Kids SKZOO Standing Doll Set", "Official", "mid", 55),

        # ATEEZ
        ("ATEEZ", "album", "The World EP.2: Outlaw", "Standard", "standard", 18),
        ("ATEEZ", "album", "Treasure EP.FIN Limited", "Limited", "mid", 35),
        ("ATEEZ", "photocard", "Hongjoong Fansign Photocard", "Fansign Event", "high", 180),

        # Enhypen
        ("Enhypen", "album", "Dark Blood ENGENE Ver.", "Limited", "mid", 30),
        ("Enhypen", "album", "Dimension: Dilemma", "Standard", "standard", 16),
        ("Enhypen", "photocard", "Sunghoon Lucky Draw", "Lucky Draw", "high", 100),

        # Weverse Exclusives
        ("BTS", "merch", "BTS Artist Made Collection V Bag", "Weverse Exclusive", "high", 80),
        ("BTS", "merch", "BTS Official Light Stick SE", "Weverse Exclusive", "mid", 65),
        ("Seventeen", "album", "FML Weverse Albums Ver.", "Weverse Exclusive", "standard", 22),
        ("NewJeans", "album", "Get Up Bunny Beach Bag Ver.", "Weverse Exclusive", "mid", 45),
    ]

    catalog = []
    for group, item_type, name, variant, tier, price in items:
        catalog.append({
            "group": group,
            "item_type": item_type,
            "name": name,
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
        notes=f"{group} | {item['item_type']} | {variant}",
        attributes_json={
            "group": group,
            "item_type": item["item_type"],
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    variant = item["variant"]
    edition_map = {
        "Fansign Event": 0.95, "Lucky Draw": 0.9, "Signed": 0.95,
        "Collector's Edition": 0.85, "Limited Vinyl": 0.8,
        "Limited": 0.7, "Limited Version": 0.7, "Deluxe": 0.65,
        "Weverse Exclusive": 0.6, "Pre-order Benefit": 0.55,
        "Night Ver.": 0.65, "Digipack": 0.4, "Jewel Case": 0.3,
        "Standard": 0.2, "Album POB": 0.5,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_map.get(variant, 0.4),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import K-pop merchandise catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== K-pop Merch Import ===")

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

    logger.info(f"\n=== K-pop Merch Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
