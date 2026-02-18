"""
Import Taylor Swift collectibles catalog.

Layer 1 (Catalog):  Curated vinyl variants, signed CDs & tour merch → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (Discogs, eBay sold listings)
- Covers vinyl variants, signed editions, Eras Tour exclusives, RSD releases

Usage:
    python -m pipelines.import_taylor_swift [--dry-run]
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

CATEGORY = "taylor_swift"


def get_curated_catalog() -> list[dict]:
    """Curated Taylor Swift collectibles catalog."""

    # (album, item_type, name, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>150), high (60-150), mid (30-60), standard (<30)

    items = [
        # Midnights Vinyl Variants
        ("Midnights", "vinyl", "Midnights Moonstone Blue Vinyl", "Moonstone Blue", "mid", 35),
        ("Midnights", "vinyl", "Midnights Jade Green Vinyl", "Jade Green", "mid", 38),
        ("Midnights", "vinyl", "Midnights Mahogany Vinyl", "Mahogany", "mid", 32),
        ("Midnights", "vinyl", "Midnights Blood Moon Vinyl", "Blood Moon", "mid", 40),
        ("Midnights", "vinyl", "Midnights Lavender Marbled Vinyl", "Lavender (Target)", "mid", 55),
        ("Midnights", "vinyl", "Midnights Signed CD with Heart", "Signed CD", "high", 130),
        ("Midnights", "vinyl", "Midnights Clock Set (4 Vinyl)", "Clock Set", "high", 140),

        # Folklore / Evermore
        ("Folklore", "vinyl", "Folklore In the Trees Vinyl", "In the Trees", "mid", 40),
        ("Folklore", "vinyl", "Folklore Running Like Water Vinyl", "Running Like Water", "mid", 38),
        ("Folklore", "vinyl", "Folklore Meet Me Behind the Mall Vinyl", "Meet Me Behind the Mall", "mid", 42),
        ("Folklore", "vinyl", "Folklore Hide and Seek Vinyl", "Hide and Seek", "mid", 35),
        ("Folklore", "vinyl", "Folklore Signed CD", "Signed CD", "high", 90),
        ("Evermore", "vinyl", "Evermore Green Vinyl", "Green (Target)", "mid", 45),
        ("Evermore", "vinyl", "Evermore Deluxe Vinyl", "Deluxe", "mid", 38),
        ("Evermore", "vinyl", "Evermore Signed CD", "Signed CD", "high", 85),

        # Signed CDs
        ("Lover", "signed_cd", "Lover Signed Booklet CD", "Signed", "high", 140),
        ("1989 TV", "signed_cd", "1989 Taylor's Version Signed CD", "Signed", "high", 110),
        ("TTPD", "signed_cd", "The Tortured Poets Department Signed CD", "Signed", "high", 65),
        ("TTPD", "signed_cd", "TTPD Signed CD with Heart", "Signed + Heart", "high", 130),

        # Eras Tour Exclusives
        ("Eras Tour", "merch", "Eras Tour Blue Crewneck", "Tour Exclusive", "high", 120),
        ("Eras Tour", "merch", "Eras Tour Poster (City Specific)", "Tour Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Friendship Bracelet Set", "Tour Exclusive", "standard", 20),
        ("Eras Tour", "merch", "Eras Tour Light-Up Wristband", "Tour Exclusive", "mid", 35),
        ("Eras Tour", "merch", "Eras Tour VIP Box", "VIP Exclusive", "grail", 200),
        ("Eras Tour", "merch", "Eras Tour Japan Exclusive Tee", "Japan Exclusive", "high", 90),

        # Record Store Day
        ("RSD", "vinyl", "Folklore Long Pond Sessions RSD", "RSD Exclusive", "high", 85),
        ("RSD", "vinyl", "Lakes 7-inch RSD", "RSD Exclusive", "high", 70),
        ("RSD", "vinyl", "All Too Well 10 Min RSD 7-inch", "RSD Exclusive", "high", 65),

        # Lover
        ("Lover", "vinyl", "Lover Pink + Blue Vinyl", "Standard", "standard", 28),
        ("Lover", "vinyl", "Lover Live From Paris Vinyl", "Limited", "mid", 40),

        # Reputation
        ("Reputation", "vinyl", "Reputation Picture Disc Vinyl", "Picture Disc", "mid", 55),
        ("Reputation", "vinyl", "Reputation Orange Vinyl (FYE)", "FYE Exclusive", "high", 75),

        # 1989
        ("1989 TV", "vinyl", "1989 TV Sunrise Boulevard Yellow", "Sunrise Boulevard", "mid", 32),
        ("1989 TV", "vinyl", "1989 TV Rose Garden Pink", "Rose Garden", "mid", 35),
        ("1989 TV", "vinyl", "1989 TV Aquamarine Green", "Aquamarine Green", "mid", 33),
        ("1989 TV", "vinyl", "1989 TV Crystal Skies Blue", "Crystal Skies", "mid", 34),

        # Tortured Poets Department
        ("TTPD", "vinyl", "TTPD Phantom Clear Vinyl", "Phantom Clear (Target)", "mid", 38),
        ("TTPD", "vinyl", "TTPD The Bolter Vinyl", "The Bolter", "mid", 35),
        ("TTPD", "vinyl", "TTPD The Albatross Vinyl", "The Albatross", "mid", 36),
    ]

    catalog = []
    for album, item_type, name, variant, tier, price in items:
        catalog.append({
            "album": album,
            "item_type": item_type,
            "name": name,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    album = item["album"]
    name = item["name"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{album}-{name}"),
        title=name,
        set_code=slugify(album),
        brand="Taylor Swift",
        rarity=item["rarity_tier"].title(),
        notes=f"{album} | {item['item_type']} | {variant}",
        attributes_json={
            "album": album,
            "item_type": item["item_type"],
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    variant = item["variant"]
    edition_map = {
        "Signed": 0.85, "Signed + Heart": 0.95, "Signed CD": 0.85,
        "RSD Exclusive": 0.8, "VIP Exclusive": 0.9, "Tour Exclusive": 0.7,
        "Japan Exclusive": 0.75, "FYE Exclusive": 0.7,
        "Picture Disc": 0.65, "Clock Set": 0.7,
        "Limited": 0.6, "Deluxe": 0.5, "Target": 0.5,
        "Standard": 0.2,
    }
    # Find best matching edition score
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
    parser = argparse.ArgumentParser(description="Import Taylor Swift collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Taylor Swift Import ===")

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

    logger.info(f"\n=== Taylor Swift Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
