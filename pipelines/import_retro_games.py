"""
Import retro video game consoles & cartridges catalog.

Layer 1 (Catalog):  Consoles + top games per platform → category_items
Layer 2 (Prices):   PriceCharting-style estimates (loose/CIB/sealed) → train.jsonl

Source: Curated database of retro gaming platforms and notable titles.
Can be augmented with PriceCharting API or scraping later.

Usage:
    python -m pipelines.import_retro_games [--dry-run]
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

CATEGORY = "retro_games"


def get_curated_catalog() -> list[dict]:
    """Curated retro gaming catalog: consoles + high-value games."""

    items = []

    # Consoles
    consoles = [
        ("Nintendo", "NES", "Nintendo Entertainment System", 1985, 60, 250, 800),
        ("Nintendo", "SNES", "Super Nintendo Entertainment System", 1990, 80, 200, 600),
        ("Nintendo", "N64", "Nintendo 64", 1996, 70, 150, 400),
        ("Nintendo", "GameCube", "Nintendo GameCube", 2001, 80, 180, 350),
        ("Nintendo", "Game Boy", "Game Boy (Original DMG)", 1989, 50, 120, 350),
        ("Nintendo", "Game Boy Color", "Game Boy Color", 1998, 45, 100, 250),
        ("Nintendo", "Game Boy Advance", "Game Boy Advance", 2001, 50, 110, 250),
        ("Nintendo", "GBA SP", "Game Boy Advance SP", 2003, 60, 120, 200),
        ("Nintendo", "DS Lite", "Nintendo DS Lite", 2006, 30, 60, 120),
        ("Nintendo", "Virtual Boy", "Virtual Boy", 1995, 200, 400, 800),
        ("Sega", "Genesis", "Sega Genesis / Mega Drive", 1988, 40, 100, 300),
        ("Sega", "Saturn", "Sega Saturn", 1994, 100, 200, 500),
        ("Sega", "Dreamcast", "Sega Dreamcast", 1998, 60, 120, 300),
        ("Sega", "Game Gear", "Sega Game Gear", 1990, 40, 80, 200),
        ("Sony", "PS1", "PlayStation 1", 1994, 30, 80, 250),
        ("Sony", "PS2", "PlayStation 2", 2000, 40, 80, 200),
        ("Sony", "PSP", "PlayStation Portable", 2004, 50, 100, 200),
        ("Atari", "2600", "Atari 2600", 1977, 40, 120, 400),
        ("SNK", "Neo Geo", "Neo Geo AES", 1990, 400, 800, 2000),
        ("Bandai", "WonderSwan", "WonderSwan Color", 1999, 60, 120, 250),
        ("Misc", "Tamagotchi", "Original Tamagotchi", 1996, 20, 60, 200),
    ]

    for maker, platform, full_name, year, loose, cib, sealed in consoles:
        items.append({
            "type": "console",
            "maker": maker,
            "platform": platform,
            "name": full_name,
            "year": year,
            "price_loose": loose,
            "price_cib": cib,
            "price_sealed": sealed,
        })

    # High-value games
    games = [
        # NES
        ("NES", "Stadium Events", 1987, 8000, 20000, 35000, "Ultra Rare"),
        ("NES", "Little Samson", 1992, 800, 2000, 5000, "Rare"),
        ("NES", "Super Mario Bros.", 1985, 10, 60, 500, "Common"),
        ("NES", "The Legend of Zelda", 1986, 15, 80, 600, "Common"),
        ("NES", "Mega Man 5", 1992, 100, 250, 800, "Uncommon"),
        ("NES", "Contra", 1988, 25, 80, 400, "Common"),
        ("NES", "Duck Tales", 1989, 15, 50, 300, "Common"),

        # SNES
        ("SNES", "EarthBound", 1994, 200, 600, 2500, "Rare"),
        ("SNES", "Chrono Trigger", 1995, 150, 350, 1500, "Uncommon"),
        ("SNES", "Super Mario RPG", 1996, 60, 150, 500, "Uncommon"),
        ("SNES", "Super Metroid", 1994, 60, 150, 600, "Uncommon"),
        ("SNES", "Mega Man X3", 1995, 180, 400, 1200, "Rare"),
        ("SNES", "Final Fantasy III", 1994, 50, 120, 400, "Uncommon"),

        # N64
        ("N64", "Conker's Bad Fur Day", 2001, 80, 200, 800, "Uncommon"),
        ("N64", "Super Smash Bros.", 1999, 30, 80, 300, "Common"),
        ("N64", "The Legend of Zelda: Ocarina of Time", 1998, 25, 60, 250, "Common"),
        ("N64", "Pokemon Stadium", 1999, 15, 40, 150, "Common"),
        ("N64", "GoldenEye 007", 1997, 20, 50, 200, "Common"),
        ("N64", "Paper Mario", 2000, 50, 120, 350, "Uncommon"),
        ("N64", "Harvest Moon 64", 1999, 70, 150, 400, "Uncommon"),

        # GameCube
        ("GameCube", "Fire Emblem: Path of Radiance", 2005, 150, 250, 600, "Rare"),
        ("GameCube", "Pokemon Colosseum", 2003, 60, 120, 300, "Uncommon"),
        ("GameCube", "Skies of Arcadia Legends", 2002, 80, 150, 400, "Uncommon"),
        ("GameCube", "Chibi-Robo!", 2005, 80, 180, 500, "Rare"),
        ("GameCube", "Metroid Prime", 2002, 30, 60, 200, "Common"),

        # Game Boy
        ("GB", "Pokemon Red/Blue", 1996, 25, 80, 500, "Common"),
        ("GB", "Pokemon Yellow", 1998, 25, 100, 600, "Common"),
        ("GBC", "Pokemon Crystal", 2000, 40, 120, 500, "Uncommon"),
        ("GBA", "Pokemon Emerald", 2004, 80, 200, 500, "Uncommon"),
        ("GBA", "Pokemon FireRed/LeafGreen", 2004, 60, 150, 300, "Uncommon"),
        ("GBA", "Mother 3 (JP)", 2006, 30, 60, 150, "JP Only"),
        ("GBA", "Castlevania: Aria of Sorrow", 2003, 60, 120, 300, "Uncommon"),

        # Sega
        ("Genesis", "Sonic the Hedgehog", 1991, 8, 25, 150, "Common"),
        ("Genesis", "Streets of Rage 2", 1992, 20, 50, 200, "Uncommon"),
        ("Saturn", "Panzer Dragoon Saga", 1998, 500, 800, 2000, "Ultra Rare"),
        ("Saturn", "Radiant Silvergun (JP)", 1998, 100, 200, 500, "Rare"),
        ("Dreamcast", "Skies of Arcadia", 2000, 60, 120, 300, "Uncommon"),

        # PS1
        ("PS1", "Suikoden II", 1999, 150, 300, 800, "Rare"),
        ("PS1", "Castlevania: Symphony of the Night", 1997, 60, 150, 400, "Uncommon"),
        ("PS1", "Final Fantasy VII", 1997, 20, 60, 300, "Common"),
        ("PS1", "Chrono Cross", 1999, 25, 60, 200, "Common"),

        # Neo Geo
        ("Neo Geo", "Kizuna Encounter", 1996, 2000, 3000, 5000, "Ultra Rare"),
        ("Neo Geo", "Metal Slug", 1996, 500, 800, 2000, "Rare"),
    ]

    for platform, title, year, loose, cib, sealed, rarity in games:
        items.append({
            "type": "game",
            "platform": platform,
            "name": title,
            "year": year,
            "price_loose": loose,
            "price_cib": cib,
            "price_sealed": sealed,
            "rarity": rarity,
        })

    return items


def item_to_catalog_item(item: dict) -> CatalogItem:
    name = item["name"]
    platform = item.get("platform", item.get("maker", ""))
    item_type = item["type"]
    year = item.get("year", 0)

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{platform}-{name}"),
        title=f"{name}" if item_type == "console" else f"{name} ({platform})",
        set_code=platform.lower(),
        brand=item.get("maker", platform),
        rarity=item.get("rarity", item_type.title()),
        notes=f"{platform} | {year}",
        attributes_json={
            "console_type": platform if item_type == "console" else "",
            "platform": platform if item_type == "game" else "",
            "year": str(year),
            "type": item_type,
        },
    )


def item_to_price_observations(item: dict) -> list[PriceObservation]:
    """Create observations for loose, CIB, and sealed conditions."""
    observations = []
    rarity_str = item.get("rarity", "Common")
    rarity_map = {"Common": 0.2, "Uncommon": 0.4, "Rare": 0.7,
                  "Ultra Rare": 0.9, "JP Only": 0.6, "Console": 0.3}
    rarity_score = rarity_map.get(rarity_str, 0.4)

    conditions = [
        ("loose", item["price_loose"], 0.5),
        ("cib", item["price_cib"], 0.8),
        ("sealed", item["price_sealed"], 1.0),
    ]

    for condition, price, cond_score in conditions:
        if price > 0:
            observations.append(PriceObservation(
                features={
                    "condition_score": cond_score,
                    "rarity_score": rarity_score,
                    "edition_score": 0.5,
                    "completeness": cond_score,
                },
                price=float(price),
            ))
    return observations


def main():
    parser = argparse.ArgumentParser(description="Import retro games catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Retro Games Import ===")

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

    print(f"\n=== Retro Games Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
