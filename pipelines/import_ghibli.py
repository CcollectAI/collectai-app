"""
Import Studio Ghibli collectibles catalog.

Layer 1 (Catalog):  Curated figures, music boxes, cels & exclusives → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (Yahoo Auctions JP, eBay, Mercari JP)
- Covers Donguri Sora figures, Benelic, music boxes, animation cels,
  Ghibli Museum exclusives, and JP-only merchandise
- Films: Totoro, Spirited Away, Princess Mononoke, Howl's, Kiki's

Usage:
    python -m pipelines.import_ghibli [--dry-run]
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

CATEGORY = "ghibli"


def get_curated_catalog() -> list[dict]:
    """Curated Studio Ghibli collectibles catalog."""

    # (film, subcategory, name, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (80-200), mid (30-80), standard (<30)

    items = [
        # Donguri Sora / Donguri Republic Store Figures
        ("My Neighbor Totoro", "figure", "Totoro Dondoko Dance Diorama", "Donguri Sora", "mid", 45),
        ("My Neighbor Totoro", "figure", "Totoro Bus Stop Scene Figure", "Donguri Sora", "mid", 50),
        ("My Neighbor Totoro", "figure", "Small Totoro & Makkuro Kurosuke Set", "Donguri Sora", "standard", 25),
        ("Kiki's Delivery Service", "figure", "Jiji the Cat Figure (Large)", "Donguri Sora", "mid", 40),
        ("Kiki's Delivery Service", "figure", "Kiki & Jiji Flying Scene Diorama", "Donguri Sora", "mid", 55),
        ("Spirited Away", "figure", "No-Face Sitting Figure", "Donguri Sora", "mid", 35),
        ("Spirited Away", "figure", "Haku Dragon Diorama", "Donguri Sora", "mid", 60),
        ("Princess Mononoke", "figure", "Kodama Glow-in-the-Dark Set (6pcs)", "Donguri Sora", "mid", 30),
        ("Howl's Moving Castle", "figure", "Calcifer on Logs Figure", "Donguri Sora", "mid", 38),

        # Music Boxes
        ("My Neighbor Totoro", "music_box", "Totoro Music Box (Stroll)", "Sekiguchi", "mid", 55),
        ("My Neighbor Totoro", "music_box", "Totoro Acorn Music Box", "Benelic", "mid", 45),
        ("Spirited Away", "music_box", "Always With Me Music Box", "Sekiguchi", "mid", 60),
        ("Spirited Away", "music_box", "No-Face Music Box (Kaonashi)", "Benelic", "high", 80),
        ("Howl's Moving Castle", "music_box", "Merry-Go-Round of Life Music Box", "Sekiguchi", "high", 85),
        ("Castle in the Sky", "music_box", "Laputa Robot Soldier Music Box", "Benelic", "high", 95),
        ("Kiki's Delivery Service", "music_box", "A Town with an Ocean View Music Box", "Sekiguchi", "mid", 50),

        # Benelic Official Figures & Goods
        ("Spirited Away", "figure", "No-Face Coin Munching Bank", "Benelic", "mid", 50),
        ("My Neighbor Totoro", "figure", "Totoro Crystal Puzzle 3D", "Benelic", "standard", 22),
        ("Princess Mononoke", "figure", "San & Moro Wolf Figure", "Benelic", "high", 80),
        ("Howl's Moving Castle", "figure", "Moving Castle Paper Theater", "Benelic", "mid", 35),

        # Vintage Animation Cels
        ("My Neighbor Totoro", "cel", "Totoro Animation Cel (Key Frame)", "Original Cel", "grail", 3500),
        ("Spirited Away", "cel", "No-Face Animation Cel", "Original Cel", "grail", 2500),
        ("Princess Mononoke", "cel", "Ashitaka Animation Cel", "Original Cel", "grail", 2000),
        ("Nausicaa", "cel", "Nausicaa Flying Animation Cel", "Original Cel", "grail", 4000),
        ("Castle in the Sky", "cel", "Laputa Robot Garden Cel", "Original Cel", "grail", 1800),
        ("My Neighbor Totoro", "cel", "Catbus Animation Cel (Background)", "Production Cel", "grail", 5000),

        # Ghibli Museum Exclusives
        ("Ghibli Museum", "museum", "Ghibli Museum Exclusive Totoro Plush", "Museum Exclusive", "high", 120),
        ("Ghibli Museum", "museum", "Ghibli Museum Film Strip Bookmark Set", "Museum Exclusive", "mid", 45),
        ("Ghibli Museum", "museum", "Ghibli Museum Stained Glass Postcard Set", "Museum Exclusive", "mid", 55),
        ("Ghibli Museum", "museum", "Robot Soldier Rooftop Figure (Museum)", "Museum Exclusive", "high", 150),
        ("Ghibli Museum", "museum", "Catbus Plush (Museum Only)", "Museum Exclusive", "high", 100),
        ("Ghibli Museum", "museum", "Ghibli Museum Saturn Theater Zoetrope Model", "Museum Exclusive", "grail", 200),

        # JP-Only Merchandise
        ("My Neighbor Totoro", "jp_merch", "Totoro Bento Box Set (JP Only)", "JP Exclusive", "mid", 40),
        ("Spirited Away", "jp_merch", "Spirited Away Chopstick Rest Set (Zeniba)", "JP Exclusive", "mid", 30),
        ("Howl's Moving Castle", "jp_merch", "Moving Castle 20th Anniversary Art Book", "JP Exclusive", "high", 80),
        ("Multi-Film", "jp_merch", "Ghibli Park Limited Tote Bag", "Ghibli Park Exclusive", "high", 90),
        ("Multi-Film", "jp_merch", "Ghibli Park Grand Opening Pin Set", "Ghibli Park Exclusive", "high", 110),
        ("Princess Mononoke", "jp_merch", "Mononoke Hime Exhibition Poster", "Exhibition", "high", 85),
        ("Kiki's Delivery Service", "jp_merch", "Kiki's Bakery Cookie Tin (JP Seasonal)", "JP Exclusive", "mid", 35),
        ("Spirited Away", "jp_merch", "Spirited Away Kabuki Collaboration Towel", "Collab Exclusive", "mid", 45),
    ]

    catalog = []
    for film, subcategory, name, edition, tier, price in items:
        catalog.append({
            "film": film,
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    film = item["film"]
    name = item["name"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{film}-{name}"),
        title=name,
        set_code=slugify(film),
        brand="Studio Ghibli",
        rarity=item["rarity_tier"].title(),
        notes=f"{film} | {item['subcategory']} | {edition}",
        attributes_json={
            "film": film,
            "subcategory": item["subcategory"],
            "edition": edition,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    edition = item["edition"]
    edition_map = {
        "Original Cel": 0.95, "Production Cel": 0.95,
        "Museum Exclusive": 0.85, "Ghibli Park Exclusive": 0.8,
        "JP Exclusive": 0.65, "Exhibition": 0.7, "Collab Exclusive": 0.6,
        "Sekiguchi": 0.5, "Benelic": 0.45, "Donguri Sora": 0.4,
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
    parser = argparse.ArgumentParser(description="Import Studio Ghibli collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Studio Ghibli Import ===")

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

    logger.info(f"\n=== Studio Ghibli Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
