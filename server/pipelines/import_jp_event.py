"""
Import Japanese event exclusives catalog.

Layer 1 (Catalog):  Curated JP event-exclusive goods → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Wonder Festival (WonFes): garage kits, exclusive figures
- Comiket: doujinshi, tapestries, acrylic stands
- AnimeJapan: exclusive goods, clear files, badges
- Tamashii Nations event: exclusive figures
- Jump Festa exclusives
- Key franchises: Fate, Vocaloid, Love Live, Gundam

Usage:
    python -m pipelines.import_jp_event [--dry-run]
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

CATEGORY = "jp_event"


def get_curated_catalog() -> list[dict]:
    """Curated Japanese event exclusives catalog."""

    # (event, franchise, item_type, name, rarity_tier, price_eur)
    # rarity_tier: grail (>300), high (100-300), mid (30-100), standard (<30)

    items = [
        # Wonder Festival (WonFes) – garage kits & exclusive figures
        ("WonFes", "Fate/Grand Order", "Garage Kit", "Saber Artoria Pendragon 1/6 GK (Unpainted)", "grail", 350),
        ("WonFes", "Evangelion", "Garage Kit", "EVA Unit-02 Beast Mode 1/8 GK (Unpainted)", "high", 280),
        ("WonFes", "Vocaloid", "Exclusive Figure", "Hatsune Miku WonFes 2023 Exclusive Nendoroid", "high", 120),
        ("WonFes", "Fate/Grand Order", "Exclusive Figure", "Mash Kyrielight WonFes Limited 1/7", "high", 180),
        ("WonFes", "Gundam", "Garage Kit", "Sazabi Ver.Ka 1/100 Resin Conversion GK", "grail", 450),
        ("WonFes", "Original", "Garage Kit", "WonFes Original Character 1/6 GK Limited 20pcs", "grail", 500),
        ("WonFes", "Chainsaw Man", "Exclusive Figure", "Power WonFes Limited Painted GK", "high", 250),

        # Comiket – doujinshi, tapestries, acrylic stands
        ("Comiket", "Fate/Grand Order", "Tapestry", "FGO Comiket 103 Exclusive B2 Tapestry Castoria", "mid", 45),
        ("Comiket", "Touhou Project", "Doujinshi Set", "Touhou C103 Popular Circle Doujinshi Bundle (5)", "mid", 40),
        ("Comiket", "Hololive", "Acrylic Stand", "Hololive C103 Exclusive Acrylic Stand Set", "mid", 35),
        ("Comiket", "Love Live!", "Tapestry", "Love Live! Sunshine!! Comiket Summer Tapestry", "mid", 40),
        ("Comiket", "Vocaloid", "Art Book", "Hatsune Miku 15th Anniversary Doujin Art Book", "mid", 30),
        ("Comiket", "Original", "Tapestry", "Comiket Limited Original Character B2 Tapestry", "standard", 25),
        ("Comiket", "Various", "Badge Set", "Comiket Corporate Booth Badge Random Set (10)", "standard", 15),
        ("Comiket", "Fate/Grand Order", "Acrylic Stand", "FGO Comiket Exclusive Acrylic Diorama Set", "high", 100),

        # AnimeJapan – exclusive goods
        ("AnimeJapan", "Demon Slayer", "Clear File", "Demon Slayer AnimeJapan Exclusive Clear File Set", "standard", 15),
        ("AnimeJapan", "Spy x Family", "Acrylic Stand", "Spy x Family AnimeJapan 2024 Acrylic Stand Trio", "standard", 20),
        ("AnimeJapan", "Jujutsu Kaisen", "Badge Set", "JJK AnimeJapan Random Badge Collection (8pc)", "standard", 18),
        ("AnimeJapan", "Gundam", "Clear File", "Gundam Seed Freedom AnimeJapan Clear File Pair", "standard", 10),
        ("AnimeJapan", "My Hero Academia", "Mini Poster Set", "MHA AnimeJapan Exclusive Mini Poster Set (5)", "mid", 30),
        ("AnimeJapan", "Attack on Titan", "Acrylic Stand", "AoT Final Season AnimeJapan Acrylic Diorama", "mid", 45),

        # Tamashii Nations Event – exclusive figures
        ("Tamashii Nations", "Dragon Ball Z", "S.H.Figuarts", "SSJ Vegito Event Exclusive S.H.Figuarts", "high", 150),
        ("Tamashii Nations", "Kamen Rider", "S.H.Figuarts", "Kamen Rider Black Sun Event Exclusive", "high", 130),
        ("Tamashii Nations", "Gundam", "Robot Spirits", "Gundam Aerial Permet Score 6 Event Exclusive", "high", 110),
        ("Tamashii Nations", "One Piece", "Figuarts ZERO", "Kaido Dragon Form Event Exclusive", "high", 180),
        ("Tamashii Nations", "Evangelion", "Metal Build", "EVA Unit-01 Metal Build Event Color Ver.", "grail", 350),

        # Jump Festa exclusives
        ("Jump Festa", "One Piece", "Figure", "Luffy Gear 5 Jump Festa Exclusive Figure", "high", 100),
        ("Jump Festa", "Dragon Ball Super", "Clear File", "DBS Super Hero Jump Festa Clear File Set", "standard", 15),
        ("Jump Festa", "My Hero Academia", "Acrylic Stand", "Deku vs Shigaraki Jump Festa Acrylic Stand", "mid", 35),
        ("Jump Festa", "Jujutsu Kaisen", "Poster Set", "JJK Jump Festa 2024 Exclusive Poster Set", "mid", 40),
        ("Jump Festa", "Chainsaw Man", "Badge Set", "CSM Jump Festa Random Badge Set (6pc)", "standard", 20),
    ]

    catalog = []
    for event, franchise, item_type, name, tier, price in items:
        catalog.append({
            "event": event,
            "franchise": franchise,
            "item_type": item_type,
            "name": name,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    event = item["event"]
    name = item["name"]
    franchise = item["franchise"]
    item_type = item["item_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{event}-{name}"),
        title=name,
        set_code=slugify(event),
        brand=event,
        rarity=item["rarity_tier"].title(),
        notes=f"{event} | {franchise} | {item_type}",
        attributes_json={
            "event": event,
            "franchise": franchise,
            "item_type": item_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    event = item["event"]
    edition_scores = {
        "WonFes": 0.90,
        "Comiket": 0.70,
        "AnimeJapan": 0.50,
        "Tamashii Nations": 0.85,
        "Jump Festa": 0.65,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(event, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import JP event exclusives catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== JP Event Exclusives Import ===")

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

    logger.info(f"\n=== JP Event Exclusives Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
