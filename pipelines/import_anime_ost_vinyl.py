"""
Import anime OST vinyl records catalog.

Layer 1 (Catalog):  Curated anime vinyl releases → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Tiger Lab Vinyl releases (Cowboy Bebop, Samurai Champloo)
- Milan Records anime vinyl (Studio Ghibli)
- Japanese pressings: King Records, Flying Dog
- Event-exclusive color variants
- City pop / anime crossover vinyl
- Key titles: Akira, Ghost in the Shell, Evangelion, Your Name

Usage:
    python -m pipelines.import_anime_ost_vinyl [--dry-run]
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

CATEGORY = "anime_ost_vinyl"


def get_curated_catalog() -> list[dict]:
    """Curated anime OST vinyl records catalog."""

    # (label, title, franchise, pressing, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>100), high (50-100), mid (25-50), standard (<25)

    items = [
        # Tiger Lab Vinyl
        ("Tiger Lab Vinyl", "Cowboy Bebop OST 1 (Seatbelts)", "Cowboy Bebop", "US Pressing", "Black", "mid", 40),
        ("Tiger Lab Vinyl", "Cowboy Bebop OST 1 (Seatbelts)", "Cowboy Bebop", "US Pressing", "Red Translucent", "high", 70),
        ("Tiger Lab Vinyl", "Cowboy Bebop Vitaminless", "Cowboy Bebop", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Cowboy Bebop Blue", "Cowboy Bebop", "US Pressing", "Blue Translucent", "high", 65),
        ("Tiger Lab Vinyl", "Samurai Champloo: The Way of the Samurai", "Samurai Champloo", "US Pressing", "Black", "mid", 35),
        ("Tiger Lab Vinyl", "Samurai Champloo: The Way of the Samurai", "Samurai Champloo", "US Pressing", "Red/White Splatter", "high", 80),
        ("Tiger Lab Vinyl", "Samurai Champloo: Departure", "Samurai Champloo", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Samurai Champloo: Impression", "Samurai Champloo", "US Pressing", "Black", "mid", 38),

        # Milan Records – Studio Ghibli
        ("Milan Records", "Spirited Away Soundtrack (Joe Hisaishi)", "Spirited Away", "EU/US Pressing", "Black", "mid", 35),
        ("Milan Records", "Princess Mononoke Soundtrack", "Princess Mononoke", "EU/US Pressing", "Black", "mid", 32),
        ("Milan Records", "My Neighbor Totoro Image Album", "My Neighbor Totoro", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Howl's Moving Castle Soundtrack", "Howl's Moving Castle", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Nausicaa Soundtrack", "Nausicaa", "EU/US Pressing", "Black", "mid", 35),
        ("Milan Records", "Castle in the Sky Soundtrack", "Castle in the Sky", "EU/US Pressing", "Black", "mid", 30),

        # Japanese pressings – King Records, Flying Dog, etc.
        ("King Records", "Macross Frontier Vocal Collection (2LP)", "Macross Frontier", "Japanese Pressing", "Black", "high", 75),
        ("Flying Dog", "Cowboy Bebop OST (Original Japanese)", "Cowboy Bebop", "Japanese Pressing", "Black", "grail", 130),
        ("King Records", "Evangelion Original Soundtrack (2LP)", "Evangelion", "Japanese Pressing", "Black", "high", 85),
        ("Tokuma Japan", "Nausicaa OST (Original 1984 Pressing)", "Nausicaa", "Japanese OG Pressing", "Black", "grail", 150),
        ("King Records", "Ghost in the Shell OST (Kenji Kawai)", "Ghost in the Shell", "Japanese Pressing", "Black", "high", 95),
        ("Flying Dog", "Macross Plus OST (Yoko Kanno)", "Macross Plus", "Japanese Pressing", "Black", "high", 80),

        # Event-exclusive color variants
        ("Mondo", "Akira Symphonic Suite (2LP)", "Akira", "Event Exclusive", "Tetsuo Splatter", "grail", 140),
        ("Tiger Lab Vinyl", "Cowboy Bebop OST 1 (Record Store Day)", "Cowboy Bebop", "RSD Exclusive", "Gold", "grail", 110),
        ("Milan Records", "Spirited Away (Anime Expo Exclusive)", "Spirited Away", "Event Exclusive", "Clear Blue", "grail", 120),
        ("Mondo", "Ghost in the Shell OST (Deluxe)", "Ghost in the Shell", "Event Exclusive", "Cyber Green Marble", "grail", 150),

        # City pop / anime crossover vinyl
        ("Nippon Columbia", "Kimagure Orange Road: Singing Heart", "Kimagure Orange Road", "Japanese OG Pressing", "Black", "high", 65),
        ("Canyon Records", "Dirty Pair Original Soundtrack", "Dirty Pair", "Japanese OG Pressing", "Black", "high", 55),
        ("Victor", "Urusei Yatsura: Music Capsule", "Urusei Yatsura", "Japanese OG Pressing", "Black", "high", 60),
        ("King Records", "Megazone 23 Soundtrack", "Megazone 23", "Japanese OG Pressing", "Black", "high", 70),
        ("Canyon Records", "City Hunter OST (Get Wild)", "City Hunter", "Japanese OG Pressing", "Black", "high", 55),

        # Key titles – modern pressings
        ("Mondo", "Akira OST (Geinoh Yamashirogumi)", "Akira", "Reissue", "Black", "mid", 45),
        ("Milan Records", "Your Name OST (RADWIMPS)", "Your Name", "EU Pressing", "Black", "mid", 35),
        ("Tiger Lab Vinyl", "FLCL OST (The Pillows)", "FLCL", "US Pressing", "Black", "mid", 40),
    ]

    catalog = []
    for label, title, franchise, pressing, variant, tier, price in items:
        catalog.append({
            "label": label,
            "title": title,
            "franchise": franchise,
            "pressing": pressing,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    label = item["label"]
    title = item["title"]
    franchise = item["franchise"]
    pressing = item["pressing"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{label}-{title}-{variant}"),
        title=f"{title} ({variant})",
        set_code=slugify(label),
        brand=label,
        rarity=item["rarity_tier"].title(),
        notes=f"{label} | {franchise} | {pressing} | {variant}",
        attributes_json={
            "label": label,
            "franchise": franchise,
            "pressing": pressing,
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}

    pressing = item["pressing"]
    edition_scores = {
        "Japanese OG Pressing": 0.95,
        "Japanese Pressing": 0.80,
        "Event Exclusive": 0.90,
        "RSD Exclusive": 0.85,
        "US Pressing": 0.50,
        "EU/US Pressing": 0.45,
        "EU Pressing": 0.45,
        "Reissue": 0.35,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": edition_scores.get(pressing, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import anime OST vinyl catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Anime OST Vinyl Import ===")

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

    print(f"\n=== Anime OST Vinyl Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
