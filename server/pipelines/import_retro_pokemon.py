"""
Import retro Pokemon accessories & merchandise data.

Layer 1 (Catalog):  Curated vintage Pokemon accessories → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Tiger Electronics, Game Boy accessories,
  TOMY figures, Burger King promos, Hasbro, vintage accessories,
  Bandai figures, fast food promos, vintage plush, electronic toys,
  Japanese exclusives, VHS/DVD media, stationery & school supplies
- Focus on 1990s-2000s era Pokemon merchandise (90+ items)

Usage:
    python -m pipelines.import_retro_pokemon [--dry-run]
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

CATEGORY = "retro_pokemon"


def get_curated_catalog() -> list[dict]:
    """Curated retro Pokemon accessories & merch catalog (90+ items)."""

    # Format: (brand, name, condition_note, rarity_tier, price_loose, price_boxed)
    # rarity_tier: grail (>100), high (50-100), mid (20-50), standard (<20)

    items = [
        # Tiger Electronics Pokedex
        ("Tiger Electronics", "Pokedex (Original 1998)", "Loose working", "mid", 35, 100),
        ("Tiger Electronics", "Pokedex (Deluxe Gold 1999)", "Loose working", "high", 60, 150),
        ("Tiger Electronics", "Pokedex (Johto 2000)", "Loose working", "mid", 30, 90),
        ("Tiger Electronics", "Pokemon Organizer (Pikachu)", "Loose working", "mid", 25, 70),

        # Game Boy Accessories
        ("Nintendo", "Game Boy Link Cable (Original)", "Loose", "standard", 10, 30),
        ("Nintendo", "Game Boy Link Cable (Color/GBC)", "Loose", "standard", 12, 35),
        ("Nintendo", "Game Boy Camera (Yellow)", "Loose", "mid", 25, 60),
        ("Nintendo", "Game Boy Camera (Pokemon Pikachu Ed.)", "Loose", "mid", 40, 80),
        ("Nintendo", "Game Boy Printer", "Loose", "mid", 30, 65),
        ("Nintendo", "Game Boy Carry Case (Pokemon)", "Loose", "standard", 15, 40),
        ("Nintendo", "Game Boy Color (Pokemon Yellow Ed.)", "Loose", "high", 80, 200),
        ("Nintendo", "Game Boy Color (Pokemon Gold/Silver Ed.)", "Loose", "high", 70, 180),
        ("Nintendo", "Game Boy Advance SP (Pikachu Ed.)", "Loose", "high", 100, 250),
        ("Nintendo", "Pokemon Mini Console", "Loose", "high", 60, 150),

        # TOMY Pokemon Figures (Original 151)
        ("TOMY", "Pikachu (TOMY Monster Collection)", "Loose", "standard", 8, 25),
        ("TOMY", "Charizard (TOMY Monster Collection)", "Loose", "mid", 20, 50),
        ("TOMY", "Mewtwo (TOMY Monster Collection)", "Loose", "standard", 12, 35),
        ("TOMY", "Blastoise (TOMY Monster Collection)", "Loose", "standard", 15, 40),
        ("TOMY", "Gengar (TOMY Monster Collection)", "Loose", "mid", 18, 45),
        ("TOMY", "Dragonite (TOMY Monster Collection)", "Loose", "standard", 12, 35),
        ("TOMY", "Mew (TOMY Monster Collection)", "Loose", "mid", 20, 50),
        ("TOMY", "Complete Gen 1 TOMY Set (151 figures)", "Loose", "grail", 400, 1200),

        # Burger King Gold-Plated Pokeball Cards (1999)
        ("Burger King", "Pikachu Gold Card #25 (Pokeball)", "With Pokeball", "mid", 15, 40),
        ("Burger King", "Charizard Gold Card #06 (Pokeball)", "With Pokeball", "mid", 20, 50),
        ("Burger King", "Mewtwo Gold Card #150 (Pokeball)", "With Pokeball", "mid", 15, 40),
        ("Burger King", "Poliwhirl Gold Card #61 (Pokeball)", "With Pokeball", "standard", 10, 30),
        ("Burger King", "Togepi Gold Card #175 (Pokeball)", "With Pokeball", "standard", 12, 35),
        ("Burger King", "Jigglypuff Gold Card #39 (Pokeball)", "With Pokeball", "standard", 10, 30),
        ("Burger King", "Complete Gold Card Set (6 cards)", "All sealed", "high", 60, 150),

        # Pokemon Pikachu Virtual Pet
        ("Nintendo", "Pokemon Pikachu (Virtual Pet Gen 1)", "Loose working", "mid", 25, 80),
        ("Nintendo", "Pokemon Pikachu 2 GS (Color)", "Loose working", "mid", 35, 100),

        # Hasbro Battle Figures
        ("Hasbro", "Pikachu Battle Figure (Electronic)", "Loose", "standard", 12, 35),
        ("Hasbro", "Charizard Battle Figure (Deluxe)", "Loose", "mid", 20, 45),
        ("Hasbro", "Blastoise Battle Figure (Deluxe)", "Loose", "standard", 18, 40),
        ("Hasbro", "Mewtwo Battle Figure (Electronic)", "Loose", "standard", 15, 38),
        ("Hasbro", "Pokemon Battle Arena Playset", "Loose", "mid", 25, 60),
        ("Hasbro", "Pokemon Trainer Belt Set", "Loose", "standard", 15, 40),

        # Card Binders, Playmats & Accessories Vintage
        ("Ultra Pro", "Pokemon Base Set Binder (1999)", "Good condition", "mid", 25, 60),
        ("Ultra Pro", "Pokemon Fossil Set Binder", "Good condition", "mid", 20, 50),
        ("Ultra Pro", "Pokemon Jungle Set Binder", "Good condition", "mid", 20, 50),
        ("Official", "Pokemon League Playmat (1999)", "Good condition", "mid", 30, 70),
        ("Official", "Pokemon TCG Coin Collection Set", "Loose", "standard", 15, 40),
        ("Official", "Pokemon Center Deck Box (Vintage)", "Good condition", "mid", 20, 55),
        ("Official", "Pokemon VHS Cassette: Indigo League Vol 1", "With case", "standard", 10, 25),
        ("Official", "Pokemon Movie 2000 Promo Card Set", "Sealed", "mid", 25, 60),

        # Bandai Pokemon Figures
        ("Bandai", "Pokemon Scale World Kanto Set (10 figures)", "Sealed", "high", 65, 120),
        ("Bandai", "Pokemon Scale World Johto Set (10 figures)", "Sealed", "high", 60, 110),
        ("Bandai", "Shodo Pokemon Vol.1 (Mewtwo/Mew/Pikachu)", "Sealed", "mid", 35, 70),
        ("Bandai", "Shodo Pokemon Vol.2 (Charizard/Dragonite)", "Sealed", "mid", 40, 75),
        ("Bandai", "Pokemon Plamo Mewtwo Model Kit", "Sealed", "mid", 25, 50),
        ("Bandai", "Pokemon Plamo Charizard Model Kit", "Sealed", "mid", 30, 55),
        ("Bandai", "Pokemon Plamo Rayquaza Model Kit", "Sealed", "mid", 35, 60),

        # KFC / McDonald's / Fast Food Promo Items
        ("KFC", "Pokemon Promo Box Set (Australia 1999)", "Complete", "grail", 120, 280),
        ("McDonald's", "Pokemon 25th Anniversary Promo Card Set (Sealed)", "Sealed", "mid", 25, 55),
        ("McDonald's", "Pokemon Happy Meal Toys Complete Set (1999)", "Loose", "mid", 30, 70),
        ("Wendy's", "Pokemon Toys Complete Set (2002)", "Loose", "mid", 20, 50),
        ("McDonald's", "Pikachu Plush (Happy Meal Exclusive 2000)", "With tag", "standard", 10, 30),
        ("Burger King", "Pokemon Beanbag Plush Set (1999)", "Complete set", "mid", 25, 60),

        # Vintage Plush
        ("TOMY", "Talking Pikachu Plush (1998)", "Working", "mid", 25, 65),
        ("Hasbro", "Dancing Pikachu Plush (Electronic)", "Working", "mid", 30, 70),
        ("Hasbro", "Large Pikachu Plush (20 inch, 1999)", "Good condition", "mid", 20, 50),
        ("Pokemon Center", "Mewtwo Plush (Tokyo Exclusive 1999)", "With tag", "high", 60, 140),
        ("Pokemon Center", "Mew Plush (Tokyo Exclusive 1999)", "With tag", "high", 55, 130),
        ("Banpresto", "UFO Catcher Prize Pikachu (Large 1999)", "Good condition", "mid", 30, 70),
        ("Banpresto", "UFO Catcher Prize Eevee (Large 2000)", "Good condition", "mid", 35, 75),
        ("Tomy", "Pocket Monsters Plush Pikachu (Japan 1996)", "With tag", "grail", 100, 250),
        ("Tomy", "Pocket Monsters Plush Charizard (Japan 1996)", "With tag", "grail", 110, 280),

        # Electronic Toys
        ("Tiger Electronics", "Pokemon Cyclone 2 Pinball Game", "Working", "mid", 25, 60),
        ("Tiger Electronics", "Pokemon Thunderbolt Game", "Working", "standard", 18, 45),
        ("Hasbro", "Pokemon Battle Stadium DX", "Working", "mid", 30, 70),
        ("Tiger Electronics", "Pokemon Electronic Catch Em All", "Working", "standard", 15, 40),
        ("Tiger Electronics", "Hit Clips Pokemon (Pikachu Player)", "Working", "mid", 20, 55),

        # Japanese Exclusive Merchandise
        ("Pokemon Center", "Japan Shop Bag (Vintage 1998)", "Good condition", "mid", 25, 55),
        ("Pokemon Center", "Japan Shop Bag (Pikachu Birthday 1999)", "Good condition", "mid", 30, 65),
        ("Shogakukan", "Corocoro Magazine Pokemon Promo Cards (1997)", "Sealed", "high", 50, 120),
        ("Shogakukan", "Corocoro Magazine Mew Promo Attachment", "Sealed", "grail", 80, 200),
        ("TOMY", "Pokemon Zukan 3D Encyclopedia (Kanto Set)", "Complete", "high", 70, 160),
        ("TOMY", "Pokemon Zukan 3D Encyclopedia (Johto Set)", "Complete", "high", 65, 150),
        ("Bandai", "Pokemon Kids Figures Gen 1 Complete Set", "Loose", "grail", 150, 350),
        ("Bandai", "Pokemon Kids Figures (Pikachu/Eevee/Mewtwo)", "Loose", "standard", 8, 25),
        ("Takara Tomy", "MONCOLLE Pikachu (Japan Exclusive)", "Sealed", "standard", 12, 30),
        ("Takara Tomy", "MONCOLLE Charizard (Japan Exclusive)", "Sealed", "standard", 15, 35),
        ("JR East", "Masuda Stamp Rally Prize Pikachu (2001)", "Good condition", "high", 55, 130),

        # VHS / DVD / Media
        ("Viz Video", "Pokemon Indigo League VHS Complete Set (13 tapes)", "With cases", "high", 50, 120),
        ("Warner Bros", "Pokemon The First Movie VHS (Original 1999)", "With case", "standard", 8, 25),
        ("Warner Bros", "Pokemon 2000 The Movie DVD (First Press)", "Sealed", "mid", 20, 45),
        ("Warner Bros", "Mewtwo Returns VHS", "With case", "standard", 10, 30),
        ("Shogakukan", "Pokemon Japanese LaserDisc Box Set", "Complete", "grail", 150, 400),

        # Stationery & School Supplies
        ("Mead", "Pokemon Trapper Keeper Binder (1999)", "Good condition", "mid", 25, 65),
        ("Official", "Pokemon Pencil Case (Japan Exclusive 1998)", "Good condition", "mid", 20, 50),
        ("Merlin", "Pokemon Sticker Album Complete (1999)", "All stickers", "mid", 30, 70),
        ("Topps", "Pokemon Sticker Album Series 1 (Complete)", "All stickers", "mid", 25, 60),
        ("Thermos", "Pokemon Lunchbox (Pikachu 1999)", "Good condition", "mid", 20, 50),
        ("Burger King", "Pokemon Watch (Promo 1999)", "Working", "standard", 12, 35),
    ]

    catalog = []
    for brand, name, condition_note, tier, price_loose, price_boxed in items:
        catalog.append({
            "brand": brand,
            "name": name,
            "condition_note": condition_note,
            "rarity_tier": tier,
            "price_loose": price_loose,
            "price_boxed": price_boxed,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    name = item["name"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}"),
        title=name,
        set_code=brand.lower().replace(" ", "-"),
        brand=brand,
        rarity=item["rarity_tier"].title(),
        notes=f"{brand} | {item['condition_note']}",
        attributes_json={
            "brand": brand,
            "condition_note": item["condition_note"],
            "era": "1990s-2000s",
            "is_electronic": any(kw in name.lower() for kw in ["electronic", "pokedex", "virtual pet", "camera", "printer", "mini console"]),
        },
    )


def item_to_price_observations(item: dict) -> list[PriceObservation]:
    """Create observations for loose and boxed conditions."""
    tier = item["rarity_tier"]
    rarity_score = shared_rarity_score(tier)

    observations = []

    # Loose price
    observations.append(PriceObservation(
        features={
            "condition_score": 0.5,
            "rarity_score": rarity_score,
            "edition_score": 0.5,
            "is_boxed": 0.0,
            "is_vintage": 1.0,
        },
        price=float(item["price_loose"]),
    ))

    # Boxed / complete price
    observations.append(PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": rarity_score,
            "edition_score": 0.5,
            "is_boxed": 1.0,
            "is_vintage": 1.0,
        },
        price=float(item["price_boxed"]),
    ))

    return observations


def main():
    parser = argparse.ArgumentParser(description="Import retro Pokemon accessories catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Retro Pokemon Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()

    all_items = [item_to_catalog_item(i) for i in catalog]
    all_observations = []
    for i in catalog:
        all_observations.extend(item_to_price_observations(i))

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()

    logger.info(f"\n=== Retro Pokemon Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
