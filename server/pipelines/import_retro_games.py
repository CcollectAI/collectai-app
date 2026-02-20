"""
Import retro video game consoles & cartridges catalog.

Layer 1 (Catalog):  Consoles + top games per platform → category_items
Layer 2 (Prices):   PriceCharting-style estimates (loose/CIB/sealed) → train.jsonl

Source: Curated database of 150+ retro gaming platforms and notable titles
covering Nintendo, Sega, Sony, Atari, NEC, SNK, Philips, 3DO, and more.
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
    rarity_score as shared_rarity_score,
    RARITY_SCORE_MAP,
    logger,
    close_http_client,
)

CATEGORY = "retro_games"


def get_curated_catalog() -> list[dict]:
    """Curated retro gaming catalog: consoles + high-value games."""

    items = []

    # Consoles: (maker, platform, full_name, year, loose, cib, sealed) — prices EUR
    consoles = [
        # Nintendo
        ("Nintendo", "NES", "Nintendo Entertainment System", 1985, 60, 250, 800),
        ("Nintendo", "SNES", "Super Nintendo Entertainment System", 1990, 80, 200, 600),
        ("Nintendo", "N64", "Nintendo 64", 1996, 70, 150, 400),
        ("Nintendo", "N64 Pikachu", "Nintendo 64 (Pikachu Edition)", 1999, 180, 350, 900),
        ("Nintendo", "GameCube", "Nintendo GameCube", 2001, 80, 180, 350),
        ("Nintendo", "GameCube Q", "Panasonic Q (GameCube/DVD)", 2001, 500, 900, 2500),
        ("Nintendo", "Wii", "Nintendo Wii", 2006, 35, 80, 200),
        ("Nintendo", "Game Boy", "Game Boy (Original DMG)", 1989, 50, 120, 350),
        ("Nintendo", "Game Boy Color", "Game Boy Color", 1998, 45, 100, 250),
        ("Nintendo", "Game Boy Advance", "Game Boy Advance", 2001, 50, 110, 250),
        ("Nintendo", "GBA SP", "Game Boy Advance SP", 2003, 60, 120, 200),
        ("Nintendo", "Game Boy Micro", "Game Boy Micro", 2005, 150, 280, 600),
        ("Nintendo", "DS Lite", "Nintendo DS Lite", 2006, 30, 60, 120),
        ("Nintendo", "Virtual Boy", "Virtual Boy", 1995, 200, 400, 800),
        # Sega
        ("Sega", "Master System", "Sega Master System", 1986, 50, 120, 350),
        ("Sega", "Genesis", "Sega Genesis / Mega Drive", 1988, 40, 100, 300),
        ("Sega", "Sega CD", "Sega CD / Mega-CD", 1991, 100, 200, 500),
        ("Sega", "Saturn", "Sega Saturn", 1994, 100, 200, 500),
        ("Sega", "Dreamcast", "Sega Dreamcast", 1998, 60, 120, 300),
        ("Sega", "Game Gear", "Sega Game Gear", 1990, 40, 80, 200),
        ("Sega", "Pico", "Sega Pico", 1993, 60, 130, 300),
        # Sony
        ("Sony", "PS1", "PlayStation 1", 1994, 30, 80, 250),
        ("Sony", "PS2", "PlayStation 2", 2000, 40, 80, 200),
        ("Sony", "PSP", "PlayStation Portable", 2004, 50, 100, 200),
        # Atari
        ("Atari", "2600", "Atari 2600", 1977, 40, 120, 400),
        ("Atari", "7800", "Atari 7800 ProSystem", 1986, 60, 150, 400),
        ("Atari", "Jaguar", "Atari Jaguar", 1993, 100, 220, 600),
        # NEC / Hudson
        ("NEC", "TurboGrafx-16", "TurboGrafx-16 / PC Engine", 1987, 120, 250, 700),
        # Philips
        ("Philips", "CDi", "Philips CD-i", 1991, 80, 180, 450),
        # 3DO
        ("Panasonic", "3DO", "3DO Interactive Multiplayer", 1993, 80, 180, 500),
        # Coleco / Mattel
        ("Coleco", "ColecoVision", "ColecoVision", 1982, 60, 150, 400),
        ("Mattel", "Intellivision", "Intellivision", 1979, 40, 100, 300),
        # SNK / Bandai / Misc
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

    # High-value games: (platform, title, year, loose, cib, sealed, rarity) — prices EUR
    games = [
        # ── NES ──────────────────────────────────────────────────────────
        ("NES", "Stadium Events", 1987, 8000, 20000, 35000, "Ultra Rare"),
        ("NES", "Little Samson", 1992, 800, 2000, 5000, "Rare"),
        ("NES", "Super Mario Bros.", 1985, 10, 60, 500, "Common"),
        ("NES", "The Legend of Zelda", 1986, 15, 80, 600, "Common"),
        ("NES", "Mega Man 5", 1992, 100, 250, 800, "Uncommon"),
        ("NES", "Contra", 1988, 25, 80, 400, "Common"),
        ("NES", "Duck Tales", 1989, 15, 50, 300, "Common"),

        # ── SNES ─────────────────────────────────────────────────────────
        ("SNES", "EarthBound", 1994, 200, 600, 2500, "Rare"),
        ("SNES", "Chrono Trigger", 1995, 150, 350, 1500, "Uncommon"),
        ("SNES", "Super Mario RPG", 1996, 60, 150, 500, "Uncommon"),
        ("SNES", "Super Metroid", 1994, 60, 150, 600, "Uncommon"),
        ("SNES", "Mega Man X3", 1995, 180, 400, 1200, "Rare"),
        ("SNES", "Final Fantasy III", 1994, 50, 120, 400, "Uncommon"),
        ("SNES", "Secret of Mana", 1993, 45, 120, 500, "Uncommon"),
        ("SNES", "Donkey Kong Country 2", 1995, 25, 70, 300, "Common"),
        ("SNES", "Terranigma", 1995, 200, 450, 1200, "Rare"),
        ("SNES", "Pocky & Rocky 2", 1994, 350, 700, 1800, "Rare"),
        ("SNES", "Wild Guns", 1994, 300, 600, 1500, "Rare"),
        ("SNES", "Demon's Crest", 1994, 120, 280, 800, "Uncommon"),
        ("SNES", "Harvest Moon", 1996, 80, 200, 600, "Uncommon"),
        ("SNES", "Star Fox 2 (Repro)", 2017, 20, 40, 80, "Repro"),
        ("SNES", "Lufia II: Rise of the Sinistrals", 1995, 80, 200, 600, "Uncommon"),
        ("SNES", "ActRaiser", 1990, 30, 80, 350, "Common"),

        # ── N64 ──────────────────────────────────────────────────────────
        ("N64", "Conker's Bad Fur Day", 2001, 80, 200, 800, "Uncommon"),
        ("N64", "Super Smash Bros.", 1999, 30, 80, 300, "Common"),
        ("N64", "The Legend of Zelda: Ocarina of Time", 1998, 25, 60, 250, "Common"),
        ("N64", "The Legend of Zelda: Majora's Mask", 2000, 35, 90, 400, "Common"),
        ("N64", "Pokemon Stadium", 1999, 15, 40, 150, "Common"),
        ("N64", "GoldenEye 007", 1997, 20, 50, 200, "Common"),
        ("N64", "Paper Mario", 2000, 50, 120, 350, "Uncommon"),
        ("N64", "Harvest Moon 64", 1999, 70, 150, 400, "Uncommon"),
        ("N64", "Banjo-Kazooie", 1998, 20, 55, 250, "Common"),
        ("N64", "Mario Kart 64", 1996, 25, 60, 250, "Common"),
        ("N64", "Ogre Battle 64", 1999, 80, 180, 500, "Uncommon"),
        ("N64", "ClayFighter: Sculptor's Cut", 1998, 250, 500, 1500, "Ultra Rare"),
        ("N64", "F-Zero X", 1998, 20, 50, 200, "Common"),
        ("N64", "Star Fox 64", 1997, 15, 40, 180, "Common"),
        ("N64", "Bomberman 64", 1997, 15, 40, 150, "Common"),

        # ── GameCube ─────────────────────────────────────────────────────
        ("GameCube", "Fire Emblem: Path of Radiance", 2005, 150, 250, 600, "Rare"),
        ("GameCube", "Pokemon Colosseum", 2003, 60, 120, 300, "Uncommon"),
        ("GameCube", "Skies of Arcadia Legends", 2002, 80, 150, 400, "Uncommon"),
        ("GameCube", "Chibi-Robo!", 2005, 80, 180, 500, "Rare"),
        ("GameCube", "Metroid Prime", 2002, 30, 60, 200, "Common"),
        ("GameCube", "The Legend of Zelda: Twilight Princess", 2006, 60, 120, 350, "Uncommon"),
        ("GameCube", "The Legend of Zelda: The Wind Waker", 2002, 40, 80, 250, "Common"),
        ("GameCube", "Super Mario Sunshine", 2002, 40, 80, 250, "Common"),
        ("GameCube", "Luigi's Mansion", 2001, 35, 70, 220, "Common"),
        ("GameCube", "Super Mario Strikers", 2005, 40, 80, 200, "Common"),
        ("GameCube", "Gotcha Force", 2003, 300, 550, 1200, "Rare"),
        ("GameCube", "Cubivore", 2002, 250, 450, 1000, "Rare"),
        ("GameCube", "Ikaruga", 2003, 60, 120, 350, "Uncommon"),

        # ── Game Boy / GBC / GBA ─────────────────────────────────────────
        ("GB", "Pokemon Red/Blue", 1996, 25, 80, 500, "Common"),
        ("GB", "Pokemon Yellow", 1998, 25, 100, 600, "Common"),
        ("GB", "Pokemon Trading Card Game", 1998, 15, 50, 250, "Common"),
        ("GBC", "Pokemon Crystal", 2000, 40, 120, 500, "Uncommon"),
        ("GBA", "Pokemon Emerald", 2004, 80, 200, 500, "Uncommon"),
        ("GBA", "Pokemon FireRed/LeafGreen", 2004, 60, 150, 300, "Uncommon"),
        ("GBA", "Mother 3 (JP)", 2006, 30, 60, 150, "JP Only"),
        ("GBA", "Castlevania: Aria of Sorrow", 2003, 60, 120, 300, "Uncommon"),
        ("GBA", "Mega Man Battle Network", 2001, 25, 60, 200, "Common"),
        ("GBA", "Fire Emblem: The Sacred Stones", 2004, 40, 100, 300, "Uncommon"),
        ("GBA", "Advance Wars 2: Black Hole Rising", 2003, 30, 70, 200, "Common"),
        ("GBA", "Final Fantasy VI Advance", 2006, 35, 80, 250, "Uncommon"),
        ("GBA", "Boktai: The Sun Is in Your Hand", 2003, 50, 120, 350, "Uncommon"),

        # ── Genesis / Mega Drive ─────────────────────────────────────────
        ("Genesis", "Sonic the Hedgehog", 1991, 8, 25, 150, "Common"),
        ("Genesis", "Streets of Rage 2", 1992, 20, 50, 200, "Uncommon"),
        ("Genesis", "Phantasy Star IV", 1993, 60, 140, 400, "Uncommon"),
        ("Genesis", "Gunstar Heroes", 1993, 40, 100, 300, "Uncommon"),
        ("Genesis", "Contra: Hard Corps", 1994, 50, 120, 350, "Uncommon"),
        ("Genesis", "Castlevania: Bloodlines", 1994, 70, 160, 450, "Uncommon"),
        ("Genesis", "Rocket Knight Adventures", 1993, 30, 70, 220, "Common"),
        ("Genesis", "Thunder Force IV", 1992, 60, 140, 400, "Uncommon"),

        # ── Sega Saturn ──────────────────────────────────────────────────
        ("Saturn", "Panzer Dragoon Saga", 1998, 500, 800, 2000, "Ultra Rare"),
        ("Saturn", "Radiant Silvergun (JP)", 1998, 100, 200, 500, "Rare"),
        ("Saturn", "Guardian Heroes", 1996, 120, 250, 600, "Rare"),
        ("Saturn", "Burning Rangers", 1998, 200, 400, 900, "Rare"),
        ("Saturn", "Shining Force III", 1997, 180, 350, 800, "Rare"),
        ("Saturn", "Dragon Force", 1996, 100, 220, 550, "Uncommon"),

        # ── Dreamcast ────────────────────────────────────────────────────
        ("Dreamcast", "Skies of Arcadia", 2000, 60, 120, 300, "Uncommon"),
        ("Dreamcast", "Power Stone 2", 2000, 80, 160, 400, "Uncommon"),
        ("Dreamcast", "Marvel vs. Capcom 2", 2000, 100, 200, 500, "Rare"),
        ("Dreamcast", "Rez", 2001, 40, 80, 200, "Uncommon"),
        ("Dreamcast", "Shenmue", 1999, 25, 60, 200, "Common"),
        ("Dreamcast", "Jet Set Radio", 2000, 30, 70, 200, "Common"),
        ("Dreamcast", "Crazy Taxi", 1999, 15, 40, 120, "Common"),

        # ── PS1 ──────────────────────────────────────────────────────────
        ("PS1", "Suikoden II", 1999, 150, 300, 800, "Rare"),
        ("PS1", "Castlevania: Symphony of the Night", 1997, 60, 150, 400, "Uncommon"),
        ("PS1", "Final Fantasy VII", 1997, 20, 60, 300, "Common"),
        ("PS1", "Chrono Cross", 1999, 25, 60, 200, "Common"),
        ("PS1", "Parasite Eve", 1998, 40, 100, 300, "Uncommon"),
        ("PS1", "Xenogears", 1998, 50, 120, 350, "Uncommon"),
        ("PS1", "Vagrant Story", 2000, 40, 100, 300, "Uncommon"),
        ("PS1", "Valkyrie Profile", 1999, 100, 220, 600, "Rare"),
        ("PS1", "Mega Man Legends 2", 2000, 80, 180, 500, "Uncommon"),
        ("PS1", "Final Fantasy Tactics", 1997, 15, 40, 150, "Common"),
        ("PS1", "Tomba!", 1997, 100, 200, 500, "Rare"),

        # ── PS2 ──────────────────────────────────────────────────────────
        ("PS2", "Kuon", 2004, 300, 500, 1200, "Ultra Rare"),
        ("PS2", "Rule of Rose", 2006, 350, 600, 1500, "Ultra Rare"),
        ("PS2", "Silent Hill 2", 2001, 60, 120, 350, "Uncommon"),
        ("PS2", "Haunting Ground", 2005, 200, 400, 900, "Rare"),
        ("PS2", "God Hand", 2006, 80, 160, 400, "Uncommon"),
        ("PS2", "Persona 3 FES", 2007, 30, 60, 180, "Common"),
        ("PS2", "Shadow Hearts: Covenant", 2004, 50, 100, 300, "Uncommon"),
        ("PS2", "Xenosaga Episode III", 2006, 80, 160, 400, "Uncommon"),

        # ── Atari 2600 ───────────────────────────────────────────────────
        ("2600", "Air Raid", 1982, 5000, 15000, 30000, "Ultra Rare"),
        ("2600", "River Raid", 1982, 5, 20, 100, "Common"),
        ("2600", "Pitfall!", 1982, 5, 20, 100, "Common"),
        ("2600", "Adventure", 1980, 5, 25, 120, "Common"),
        ("2600", "Yars' Revenge", 1982, 3, 15, 80, "Common"),

        # ── TurboGrafx-16 / PC Engine ────────────────────────────────────
        ("TurboGrafx-16", "Bonk's Adventure", 1989, 40, 100, 300, "Uncommon"),
        ("TurboGrafx-16", "Splatterhouse", 1990, 50, 120, 350, "Uncommon"),
        ("TurboGrafx-16", "Castlevania: Rondo of Blood", 1993, 100, 220, 600, "Rare"),

        # ── Neo Geo ──────────────────────────────────────────────────────
        ("Neo Geo", "Kizuna Encounter", 1996, 2000, 3000, 5000, "Ultra Rare"),
        ("Neo Geo", "Metal Slug", 1996, 500, 800, 2000, "Rare"),

        # ── Sega CD / Mega-CD ───────────────────────────────────────────
        ("Sega CD", "Snatcher", 1994, 300, 500, 1200, "Rare"),
        ("Sega CD", "Lunar: The Silver Star", 1993, 60, 140, 400, "Uncommon"),
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
    rarity_score = shared_rarity_score(rarity_str)

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

    logger.info("=== Retro Games Import ===")

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

    logger.info(f"\n=== Retro Games Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
