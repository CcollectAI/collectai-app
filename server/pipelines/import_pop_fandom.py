"""
Import Pop music fandom collectibles catalog.

Layer 1 (Catalog):  Curated vinyl variants, tour merch & limited items → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (Discogs, eBay sold listings)
- Covers Ariana Grande, Olivia Rodrigo, Harry Styles, Billie Eilish,
  Dua Lipa, and K-pop soloists (IU, Lisa, Jungkook)

Usage:
    python -m pipelines.import_pop_fandom [--dry-run]
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

CATEGORY = "pop_fandom"


def get_curated_catalog() -> list[dict]:
    """Curated pop music fandom collectibles catalog."""

    # (artist, item_type, name, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>100), high (50-100), mid (25-50), standard (<25)

    items = [
        # Ariana Grande
        ("Ariana Grande", "vinyl", "thank u, next Clear Vinyl", "Clear (UO Exclusive)", "mid", 45),
        ("Ariana Grande", "vinyl", "thank u, next Standard Vinyl", "Standard", "standard", 22),
        ("Ariana Grande", "vinyl", "Positions Coke Bottle Clear Vinyl", "Coke Bottle (UO)", "mid", 40),
        ("Ariana Grande", "vinyl", "Sweetener Peach Vinyl", "Peach (UO Exclusive)", "high", 75),
        ("Ariana Grande", "vinyl", "Dangerous Woman Purple Vinyl", "Purple", "high", 65),
        ("Ariana Grande", "merch", "Sweetener World Tour Hoodie", "Tour Exclusive", "high", 80),
        ("Ariana Grande", "merch", "Positions Signed CD", "Signed", "high", 90),

        # Olivia Rodrigo
        ("Olivia Rodrigo", "vinyl", "SOUR Transparent Blue Vinyl", "Transparent Blue", "mid", 35),
        ("Olivia Rodrigo", "vinyl", "SOUR Amazon Purple Vinyl", "Amazon Purple", "mid", 38),
        ("Olivia Rodrigo", "vinyl", "SOUR Standard Vinyl", "Standard", "standard", 22),
        ("Olivia Rodrigo", "vinyl", "GUTS Red Vinyl (Target)", "Red (Target)", "mid", 32),
        ("Olivia Rodrigo", "vinyl", "GUTS Spotify Fans First Vinyl", "Spotify Exclusive", "high", 55),
        ("Olivia Rodrigo", "vinyl", "GUTS Standard Vinyl", "Standard", "standard", 20),
        ("Olivia Rodrigo", "merch", "GUTS World Tour Poster", "Tour Exclusive", "mid", 35),

        # Harry Styles
        ("Harry Styles", "vinyl", "Fine Line Black & White Vinyl", "Black & White Splatter", "mid", 38),
        ("Harry Styles", "vinyl", "Fine Line Coke Bottle Green Vinyl", "Coke Bottle Green", "mid", 35),
        ("Harry Styles", "vinyl", "Fine Line Standard Vinyl", "Standard", "standard", 22),
        ("Harry Styles", "vinyl", "Harry's House Sea Glass Vinyl", "Sea Glass (UO)", "mid", 40),
        ("Harry Styles", "vinyl", "Harry's House Standard Vinyl", "Standard", "standard", 20),
        ("Harry Styles", "merch", "Love On Tour Poster (City)", "Tour Exclusive", "high", 70),
        ("Harry Styles", "merch", "Love On Tour Tote Bag", "Tour Exclusive", "mid", 45),
        ("Harry Styles", "merch", "Fine Line Signed CD", "Signed", "high", 95),

        # Billie Eilish
        ("Billie Eilish", "vinyl", "WWAFAWDWG Green Vinyl", "Green", "mid", 30),
        ("Billie Eilish", "vinyl", "Happier Than Ever Gold Vinyl", "Gold (Amazon)", "mid", 35),
        ("Billie Eilish", "vinyl", "Happier Than Ever Painted Vinyl", "Painted (UO)", "high", 55),
        ("Billie Eilish", "vinyl", "Hit Me Hard and Soft Blue Vinyl", "Blue (Amazon)", "mid", 30),
        ("Billie Eilish", "merch", "Happier Than Ever World Tour Hoodie", "Tour Exclusive", "high", 80),

        # Dua Lipa
        ("Dua Lipa", "vinyl", "Future Nostalgia Pink Vinyl", "Pink (UO Exclusive)", "mid", 40),
        ("Dua Lipa", "vinyl", "Future Nostalgia Standard Vinyl", "Standard", "standard", 20),
        ("Dua Lipa", "vinyl", "Future Nostalgia Moonlight Edition", "Moonlight", "mid", 35),
        ("Dua Lipa", "vinyl", "Radical Optimism Red Vinyl", "Red", "mid", 30),

        # K-pop Soloists
        ("IU", "album", "IU LILAC Limited Edition", "Limited", "mid", 45),
        ("IU", "album", "IU The Golden Hour Photobook", "Photobook Edition", "high", 55),
        ("Lisa", "album", "Lisa LALISA Limited Gold Vinyl", "Limited Gold Vinyl", "high", 60),
        ("Lisa", "album", "Lisa LALISA Standard", "Standard", "standard", 16),
        ("Jungkook", "album", "Jungkook GOLDEN Set (Both Vers.)", "Set", "mid", 35),
        ("Jungkook", "album", "Jungkook GOLDEN Weverse POB", "Weverse Exclusive", "mid", 40),
    ]

    catalog = []
    for artist, item_type, name, variant, tier, price in items:
        catalog.append({
            "artist": artist,
            "item_type": item_type,
            "name": name,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    artist = item["artist"]
    name = item["name"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{artist}-{name}"),
        title=name,
        set_code=slugify(artist),
        brand=artist,
        rarity=item["rarity_tier"].title(),
        notes=f"{artist} | {item['item_type']} | {variant}",
        attributes_json={
            "artist": artist,
            "item_type": item["item_type"],
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    variant = item["variant"]
    edition_map = {
        "Signed": 0.85, "Tour Exclusive": 0.7, "Spotify Exclusive": 0.75,
        "UO Exclusive": 0.6, "Limited": 0.7, "Limited Gold Vinyl": 0.75,
        "Photobook Edition": 0.65, "Weverse Exclusive": 0.6,
        "Set": 0.5, "Amazon": 0.45, "Target": 0.45,
        "Standard": 0.2,
    }
    edition_score = 0.4
    for key, score in edition_map.items():
        if key in variant:
            edition_score = score
            break

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_score,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import pop fandom collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Pop Fandom Import ===")

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

    logger.info(f"\n=== Pop Fandom Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
