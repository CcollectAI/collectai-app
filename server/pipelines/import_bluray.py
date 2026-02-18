"""
Import Blu-ray Steelbook & boutique label collector data.

Layer 1 (Catalog):  Curated collector Blu-rays → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Criterion, Arrow Video, Steelbooks, 4K UHD, boutique labels
- Can be augmented with Blu-ray.com or TMDB later

Usage:
    python -m pipelines.import_bluray [--dry-run]
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

CATEGORY = "bluray_steelbook"


def get_curated_catalog() -> list[dict]:
    """Curated Blu-ray collector catalog: Criterion, Arrow, Steelbooks, boutique labels."""

    # Format: (label, title, format, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>150), high (80-150), mid (40-80), standard (<40)

    discs = [
        # Criterion Collection
        ("Criterion", "Seven Samurai", "Blu-ray", "Criterion #2", "standard", 28),
        ("Criterion", "Stalker", "Blu-ray", "Criterion #888", "standard", 30),
        ("Criterion", "In the Mood for Love", "Blu-ray", "Criterion #4K", "mid", 35),
        ("Criterion", "Mulholland Dr.", "Blu-ray", "Criterion #779", "standard", 25),
        ("Criterion", "Parasite", "4K UHD", "Criterion 4K", "mid", 38),
        ("Criterion", "Do the Right Thing", "Blu-ray", "Criterion #97", "standard", 22),
        ("Criterion", "Paris, Texas", "Blu-ray", "Criterion #634", "standard", 28),
        ("Criterion", "Eraserhead", "Blu-ray", "Criterion #725", "mid", 35),
        ("Criterion", "The Before Trilogy", "Blu-ray", "Criterion Box Set", "mid", 55),
        ("Criterion", "World of Wong Kar Wai", "Blu-ray", "Criterion Box Set", "high", 90),

        # Arrow Video
        ("Arrow Video", "Suspiria", "4K UHD", "Arrow Limited", "high", 45),
        ("Arrow Video", "Re-Animator", "Blu-ray", "Arrow Limited", "mid", 35),
        ("Arrow Video", "The Thing", "4K UHD", "Arrow Limited", "high", 50),
        ("Arrow Video", "Donnie Darko", "4K UHD", "Arrow Limited", "mid", 40),
        ("Arrow Video", "Deep Red", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "Battle Royale", "Blu-ray", "Arrow Limited", "mid", 38),
        ("Arrow Video", "Hellraiser Trilogy", "Blu-ray", "Arrow Box Set", "high", 80),
        ("Arrow Video", "Oldboy", "4K UHD", "Arrow Limited", "mid", 45),

        # Steelbooks - Marvel MCU
        ("Steelbook", "Avengers: Endgame", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Steelbook", "Spider-Man: No Way Home", "4K UHD", "Best Buy Steelbook", "mid", 35),
        ("Steelbook", "Black Panther", "4K UHD", "Zavvi Steelbook", "mid", 38),
        ("Steelbook", "Iron Man", "4K UHD", "Zavvi Steelbook", "high", 55),

        # Steelbooks - Nolan
        ("Steelbook", "Interstellar", "4K UHD", "HDZeta Steelbook", "high", 120),
        ("Steelbook", "The Dark Knight", "4K UHD", "HDZeta Steelbook", "grail", 160),
        ("Steelbook", "Inception", "4K UHD", "Manta Lab Steelbook", "high", 100),
        ("Steelbook", "Oppenheimer", "4K UHD", "Zavvi Steelbook", "mid", 45),

        # Steelbooks - Miyazaki / Studio Ghibli
        ("Steelbook", "Spirited Away", "Blu-ray", "Zavvi Steelbook", "high", 60),
        ("Steelbook", "Princess Mononoke", "Blu-ray", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "My Neighbor Totoro", "Blu-ray", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Howl's Moving Castle", "Blu-ray", "Zavvi Steelbook", "mid", 55),

        # 4K UHD Limited Editions
        ("4K UHD", "Blade Runner 2049", "4K UHD", "Limited Collector's", "high", 80),
        ("4K UHD", "2001: A Space Odyssey", "4K UHD", "Titans of Cult", "high", 65),
        ("4K UHD", "The Shining", "4K UHD", "Titans of Cult", "mid", 55),
        ("4K UHD", "Dune (2021)", "4K UHD", "Limited SteelBook", "mid", 40),
        ("4K UHD", "Lawrence of Arabia", "4K UHD", "Columbia Classics Vol 1", "grail", 180),
        ("4K UHD", "Jaws", "4K UHD", "Limited Collector's", "mid", 45),

        # Vinegar Syndrome / Shout Factory
        ("Vinegar Syndrome", "Tammy and the T-Rex", "4K UHD", "VS Limited", "mid", 40),
        ("Vinegar Syndrome", "Psycho Goreman", "4K UHD", "VS Limited", "mid", 35),
        ("Vinegar Syndrome", "Blood Rage", "Blu-ray", "VS Limited", "mid", 30),
        ("Shout Factory", "The Fog", "4K UHD", "Shout Select", "mid", 35),
        ("Shout Factory", "Escape from New York", "4K UHD", "Shout Select", "mid", 38),
        ("Shout Factory", "They Live", "4K UHD", "Shout Select", "mid", 35),

        # Boutique Label Box Sets
        ("Indicator", "Columbia Noir Collection Vol 1", "Blu-ray", "Indicator Box Set", "high", 85),
        ("Eureka", "Buster Keaton: The Saphead", "Blu-ray", "Masters of Cinema", "mid", 30),
        ("88 Films", "Italian Horror Collection", "Blu-ray", "88 Films Box Set", "high", 100),
        ("Imprint", "Film Noir Collection", "Blu-ray", "Imprint Box Set", "high", 120),
        ("Severin", "Fulci Box Set", "Blu-ray", "Severin Limited", "grail", 200),
        ("Second Sight", "The Witch", "4K UHD", "Second Sight Limited", "mid", 50),
    ]

    catalog = []
    for label, title, fmt, edition, tier, price in discs:
        catalog.append({
            "label": label,
            "title": title,
            "format": fmt,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    label = item["label"]
    title = item["title"]
    fmt = item["format"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{label}-{title}-{edition}"),
        title=f"{title} ({fmt})",
        set_code=label.lower().replace(" ", "-"),
        brand=label,
        rarity=item["rarity_tier"].title(),
        notes=f"{label} | {edition} | {fmt}",
        attributes_json={
            "label": label,
            "format": fmt,
            "edition": edition,
            "is_steelbook": "steelbook" in edition.lower(),
            "is_4k": fmt == "4K UHD",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    is_limited = any(kw in item["edition"].lower() for kw in ["limited", "steelbook", "box set"])
    is_4k = item["format"] == "4K UHD"

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": 0.85 if is_limited else 0.4,
            "is_steelbook": 1.0 if "steelbook" in item["edition"].lower() else 0.0,
            "is_4k": 1.0 if is_4k else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Blu-ray Steelbook catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Blu-ray Steelbook Import ===")

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

    logger.info(f"\n=== Blu-ray Steelbook Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
