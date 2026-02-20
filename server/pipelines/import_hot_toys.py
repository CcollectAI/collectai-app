"""
Import Hot Toys & Premium Collectible Statues catalog.

Layer 1 (Catalog):  Curated Hot Toys + Sideshow figures → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Hot Toys Marvel MCU 1/6 scale figures (Iron Man, Spider-Man, Thanos, Doctor Strange,
  Black Panther, Scarlet Witch, Moon Knight, Loki, Deadpool & Wolverine, etc.)
- Hot Toys Star Wars 1/6 scale figures (Mandalorian, Darth Vader, Boba Fett, Clones,
  Ahsoka, Rex, Cad Bane, Grogu Life Size, etc.)
- Hot Toys DC 1/6 scale figures (Batman, Joker, Superman, Aquaman, Wonder Woman, etc.)
- Hot Toys movie icons (John Wick, Terminator, RoboCop, Predator, Alien, Back to the
  Future, Indiana Jones, James Bond)
- Sideshow Premium Format statues (Marvel, DC, Star Wars, Predator)
- Sideshow & Queen Studios life-size busts
- 100+ items across all tiers (grail / high / mid / standard)

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
    """Curated 100+ item catalog: Hot Toys 1/6 (MCU, Star Wars, DC, movie icons),
    Sideshow Premium Format & Maquettes, Sideshow/Queen Studios life-size busts."""

    # (brand, franchise, name, figure_type, rarity_tier, price_eur)
    # rarity_tier: grail (>1500), high (600-1500), mid (300-600), standard (<300)

    figures = [
        # ─── Marvel MCU — Hot Toys 1/6 ───────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark LXXXV (Mk 85)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark L (Mk 50)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark VII", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark III", "1/6 Figure", "high", 600),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLVI (Mk 46)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark IV", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Integrated Suit)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Iron Spider)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Symbiote Suit)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Black & Gold Suit)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Thanos (Endgame)", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Marvel MCU", "Thanos (Infinity War)", "1/6 Figure", "mid", 550),
        ("Hot Toys", "Marvel MCU", "Thanos (Battle Damaged)", "1/6 Figure", "mid", 520),
        ("Hot Toys", "Marvel MCU", "Captain America (Endgame)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Captain America (Stealth Suit)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Thor (Love and Thunder)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Marvel MCU", "Hulkbuster 1/6 Scale", "1/6 Figure", "high", 900),
        ("Hot Toys", "Marvel MCU", "Black Panther (Original Suit)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Black Panther (Wakanda Forever)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Doctor Strange (Multiverse of Madness)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Doctor Strange (Infinity War)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel MCU", "Scarlet Witch (WandaVision)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Scarlet Witch (Multiverse of Madness)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Moon Knight", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Moon Knight (Mr. Knight)", "1/6 Figure", "mid", 300),
        ("Hot Toys", "Marvel MCU", "Loki (Avengers Endgame)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Loki (TVA Variant)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Deadpool & Wolverine Set", "1/6 Figure", "mid", 580),
        ("Hot Toys", "Marvel MCU", "War Machine Mark IV", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Vision (WandaVision)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Black Widow (Endgame)", "1/6 Figure", "mid", 320),

        # ─── Star Wars — Hot Toys 1/6 ───────────────────────────────────
        ("Hot Toys", "Star Wars", "The Mandalorian & Grogu Deluxe", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Star Wars", "The Mandalorian (Beskar)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "The Mandalorian (Beskar Staff)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Grogu Life-Size", "Life-Size Figure", "high", 620),
        ("Hot Toys", "Star Wars", "Darth Vader (ESB 40th Anniversary)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "Darth Vader (Rogue One)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Darth Vader (Obi-Wan Kenobi)", "1/6 Figure", "mid", 390),
        ("Hot Toys", "Star Wars", "Boba Fett (Vintage Color)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Boba Fett (Repaint Armor)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Clone Trooper 501st Battalion", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "Clone Trooper Phase II (Deluxe)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Captain Rex (Ahsoka Series)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Captain Rex (Clone Wars)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Ahsoka Tano (The Mandalorian)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Star Wars", "Ahsoka Tano (Ahsoka Series)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Cad Bane (The Book of Boba Fett)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Luke Skywalker (Crait)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Luke Skywalker (ROTJ Deluxe)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Emperor Palpatine Deluxe", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Star Wars", "Stormtrooper (A New Hope)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Star Wars", "Darth Maul (Solo)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi (Deluxe)", "1/6 Figure", "mid", 350),

        # ─── DC — Hot Toys 1/6 ──────────────────────────────────────────
        ("Hot Toys", "DC", "Batman (The Dark Knight)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "Batman (Batman Returns)", "1/6 Figure", "high", 650),
        ("Hot Toys", "DC", "Batman (Tactical Batsuit - Zack Snyder)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "DC", "Batman (The Batman 2022)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "DC", "Batman (The Batman 2022 - Batcycle)", "1/6 Figure", "high", 680),
        ("Hot Toys", "DC", "The Joker (The Dark Knight) DX11", "1/6 Figure", "high", 800),
        ("Hot Toys", "DC", "The Joker (The Dark Knight) DX32", "1/6 Figure", "high", 750),
        ("Hot Toys", "DC", "The Joker (Joaquin Phoenix)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "Harley Quinn (Birds of Prey)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "DC", "Superman (Christopher Reeve)", "1/6 Figure", "high", 650),
        ("Hot Toys", "DC", "Superman (Justice League)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "DC", "Aquaman (Aquaman and the Lost Kingdom)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "DC", "Aquaman (Justice League)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "DC", "Wonder Woman (Justice League)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "DC", "The Flash (The Flash 2023)", "1/6 Figure", "mid", 310),

        # ─── Movie Icons — Hot Toys 1/6 ─────────────────────────────────
        ("Hot Toys", "John Wick", "John Wick (Chapter 4)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "John Wick", "John Wick (Chapter 2)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Terminator", "T-800 (Terminator 2) DX10", "1/6 Figure", "high", 700),
        ("Hot Toys", "Terminator", "T-800 (Battle Damaged)", "1/6 Figure", "mid", 550),
        ("Hot Toys", "RoboCop", "RoboCop (1987)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "RoboCop", "RoboCop (Diecast)", "1/6 Figure", "mid", 500),
        ("Hot Toys", "Predator", "City Hunter Predator", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Predator", "Classic Predator", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Alien", "Alien Warrior", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Alien", "Ellen Ripley (Aliens)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Back to the Future", "Marty McFly", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Back to the Future", "Doc Brown", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Back to the Future", "Marty McFly & DeLorean Set", "1/6 Figure", "high", 850),
        ("Hot Toys", "Indiana Jones", "Indiana Jones (Raiders of the Lost Ark)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Indiana Jones", "Indiana Jones (Dial of Destiny) Deluxe", "1/6 Figure", "mid", 350),
        ("Hot Toys", "James Bond", "James Bond (Goldfinger - Sean Connery)", "1/6 Figure", "high", 650),
        ("Hot Toys", "James Bond", "James Bond (No Time to Die)", "1/6 Figure", "mid", 350),

        # ─── Sideshow Premium Format & Maquettes ────────────────────────
        ("Sideshow", "Marvel", "Spider-Man Premium Format", "Premium Format", "high", 750),
        ("Sideshow", "Marvel", "Wolverine Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "Marvel", "Thanos on Throne Maquette", "Maquette", "grail", 1550),
        ("Sideshow", "Marvel", "Venom Premium Format", "Premium Format", "high", 720),
        ("Sideshow", "Marvel", "Hulk Premium Format", "Premium Format", "high", 800),
        ("Sideshow", "Marvel", "Iron Man Mark XLIII Maquette", "Maquette", "high", 850),
        ("Sideshow", "DC", "Batman Premium Format", "Premium Format", "high", 680),
        ("Sideshow", "DC", "Catwoman Premium Format", "Premium Format", "high", 650),
        ("Sideshow", "DC", "The Joker Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "DC", "Harley Quinn Premium Format", "Premium Format", "high", 660),
        ("Sideshow", "Star Wars", "Darth Vader Premium Format", "Premium Format", "high", 800),
        ("Sideshow", "Star Wars", "Boba Fett Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "Star Wars", "General Grievous Premium Format", "Premium Format", "high", 900),
        ("Sideshow", "Predator", "Predator Maquette", "Maquette", "high", 900),
        ("Sideshow", "Alien", "Alien Queen Maquette", "Maquette", "grail", 1600),
        ("Sideshow", "Mythos", "Frankensteins Monster Premium Format", "Premium Format", "high", 650),

        # ─── Life-Size Busts — Sideshow ─────────────────────────────────
        ("Sideshow", "Marvel", "Iron Man Mark III Life-Size Bust", "Life-Size Bust", "grail", 2200),
        ("Sideshow", "Marvel", "Thanos Life-Size Bust", "Life-Size Bust", "grail", 2800),
        ("Sideshow", "Marvel", "Deadpool Life-Size Bust", "Life-Size Bust", "grail", 1800),
        ("Sideshow", "Marvel", "Wolverine Life-Size Bust", "Life-Size Bust", "grail", 2000),
        ("Sideshow", "Star Wars", "Darth Vader Life-Size Bust", "Life-Size Bust", "grail", 3000),
        ("Sideshow", "Star Wars", "Boba Fett Life-Size Bust", "Life-Size Bust", "grail", 2400),
        ("Sideshow", "DC", "Batman Life-Size Bust", "Life-Size Bust", "grail", 2500),
        ("Sideshow", "DC", "The Joker Life-Size Bust", "Life-Size Bust", "grail", 2200),

        # ─── Life-Size Busts — Queen Studios ─────────────────────────────
        ("Queen Studios", "Marvel", "Iron Man Mark 50 Life-Size Bust", "Life-Size Bust", "grail", 3500),
        ("Queen Studios", "Marvel", "Spider-Man Life-Size Bust", "Life-Size Bust", "grail", 3200),
        ("Queen Studios", "Marvel", "Thanos Life-Size Bust", "Life-Size Bust", "grail", 4000),
        ("Queen Studios", "DC", "The Joker (Heath Ledger) Life-Size Bust", "Life-Size Bust", "grail", 4500),
        ("Queen Studios", "DC", "Batman (The Dark Knight) Life-Size Bust", "Life-Size Bust", "grail", 3800),
        ("Queen Studios", "DC", "Superman Life-Size Bust", "Life-Size Bust", "grail", 3600),
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
        "Life-Size Figure": 0.9,
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
