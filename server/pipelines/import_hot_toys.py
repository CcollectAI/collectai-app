"""
Import Hot Toys & Premium Collectible Statues catalog.

Layer 1 (Catalog):  Curated Hot Toys + Sideshow figures → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Hot Toys Marvel MCU 1/6 scale figures
- Hot Toys Star Wars 1/6 scale figures
- Hot Toys DC 1/6 scale figures
- Sideshow Premium Format statues
- Life-size busts

Usage:
    python -m pipelines.import_hot_toys [--dry-run]
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

CATEGORY = "hot_toys"


def get_curated_catalog() -> list[dict]:
    """Curated Hot Toys catalog covering MCU, Star Wars, DC and premium formats."""

    # (brand, franchise, name, figure_type, rarity_tier, price_eur)
    # rarity_tier: grail (>1500), high (600-1500), mid (300-600), standard (<300)

    figures = [
        # Marvel MCU - Hot Toys 1/6
        ("Hot Toys", "Marvel MCU", "Iron Man Mark LXXXV (Mk 85)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark L (Mk 50)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark VII", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark III", "1/6 Figure", "high", 600),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Integrated Suit)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Iron Spider)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Symbiote Suit)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Thanos (Endgame)", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Marvel MCU", "Thanos (Infinity War)", "1/6 Figure", "mid", 550),
        ("Hot Toys", "Marvel MCU", "Captain America (Endgame)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Thor (Love and Thunder)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Marvel MCU", "Hulkbuster 1/6 Scale", "1/6 Figure", "high", 900),
        ("Hot Toys", "Marvel MCU", "Black Panther (Original Suit)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Doctor Strange (Multiverse of Madness)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Scarlet Witch (WandaVision)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Deadpool & Wolverine Set", "1/6 Figure", "mid", 580),

        # Star Wars - Hot Toys 1/6
        ("Hot Toys", "Star Wars", "The Mandalorian & Grogu Deluxe", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Star Wars", "The Mandalorian (Beskar)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Darth Vader (ESB 40th Anniversary)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "Darth Vader (Rogue One)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Boba Fett (Vintage Color)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Clone Trooper 501st Battalion", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "Clone Trooper Phase II (Deluxe)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Ahsoka Tano (The Mandalorian)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Star Wars", "Luke Skywalker (Crait)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Emperor Palpatine Deluxe", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Star Wars", "Stormtrooper (A New Hope)", "1/6 Figure", "standard", 280),

        # DC - Hot Toys 1/6
        ("Hot Toys", "DC", "Batman (The Dark Knight)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "Batman (Batman Returns)", "1/6 Figure", "high", 650),
        ("Hot Toys", "DC", "Batman (Tactical Batsuit - Zack Snyder)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "DC", "Batman (The Batman 2022)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "DC", "The Joker (The Dark Knight) DX11", "1/6 Figure", "high", 800),
        ("Hot Toys", "DC", "The Joker (Joaquin Phoenix)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "Harley Quinn (Birds of Prey)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "DC", "Superman (Christopher Reeve)", "1/6 Figure", "high", 650),
        ("Hot Toys", "DC", "Wonder Woman (Justice League)", "1/6 Figure", "mid", 320),

        # Sideshow Premium Format
        ("Sideshow", "Marvel", "Spider-Man Premium Format", "Premium Format", "high", 750),
        ("Sideshow", "Marvel", "Wolverine Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "Marvel", "Thanos on Throne Maquette", "Maquette", "grail", 1500),
        ("Sideshow", "DC", "Batman Premium Format", "Premium Format", "high", 680),
        ("Sideshow", "DC", "Catwoman Premium Format", "Premium Format", "high", 650),
        ("Sideshow", "Star Wars", "Darth Vader Premium Format", "Premium Format", "high", 800),
        ("Sideshow", "Star Wars", "Boba Fett Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "Predator", "Predator Maquette", "Maquette", "high", 900),

        # Life-size Busts
        ("Sideshow", "Marvel", "Iron Man Mark III Life-Size Bust", "Life-Size Bust", "grail", 2200),
        ("Sideshow", "Marvel", "Thanos Life-Size Bust", "Life-Size Bust", "grail", 2800),
        ("Sideshow", "Star Wars", "Darth Vader Life-Size Bust", "Life-Size Bust", "grail", 3000),
        ("Sideshow", "DC", "Batman Life-Size Bust", "Life-Size Bust", "grail", 2500),
        ("Queen Studios", "Marvel", "Iron Man Mark 50 Life-Size Bust", "Life-Size Bust", "grail", 3500),
        ("Queen Studios", "DC", "The Joker (Heath Ledger) Life-Size Bust", "Life-Size Bust", "grail", 4500),
    ]

    catalog = []
    for brand, franchise, name, figure_type, tier, price in figures:
        catalog.append({
            "brand": brand,
            "franchise": franchise,
            "name": name,
            "figure_type": figure_type,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    name = item["name"]
    franchise = item["franchise"]
    figure_type = item["figure_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}"),
        title=name,
        set_code=slugify(franchise),
        brand=brand,
        rarity=item["rarity_tier"].title(),
        notes=f"{brand} | {franchise} | {figure_type}",
        attributes_json={
            "brand": brand,
            "franchise": franchise,
            "figure_type": figure_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    figure_type = item["figure_type"]
    edition_scores = {
        "1/6 Figure": 0.6,
        "Premium Format": 0.75,
        "Maquette": 0.85,
        "Life-Size Bust": 0.95,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(figure_type, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Hot Toys catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Hot Toys Import ===")

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

    logger.info(f"\n=== Hot Toys Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
