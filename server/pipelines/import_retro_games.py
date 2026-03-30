"""
Import retro video game consoles & cartridges catalog.

Layer 1 (Catalog):  Consoles + top games per platform → category_items
Layer 2 (Prices):   PriceCharting-style estimates (loose/CIB/sealed) → train.jsonl

Source: Curated database of 500+ retro gaming platforms and notable titles
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


def _additional_retro_2025_expansion() -> list[dict]:
    """55 more items: Saturn, Neo Geo AES, TG-16, Jaguar, 3DO, CIB variants."""
    extra = []

    # ── Sega Saturn — Holy Grails ──────────────────────────────────────
    saturn_games = [
        ("Saturn", "Panzer Dragoon Saga", 1998, 600, 1200, 3000, "Grail"),
        ("Saturn", "Radiant Silvergun", 1998, 250, 500, 1200, "Rare"),
        ("Saturn", "Burning Rangers", 1998, 200, 400, 1000, "Rare"),
        ("Saturn", "Shining Force III", 1997, 150, 300, 800, "Rare"),
        ("Saturn", "Guardian Heroes", 1996, 100, 220, 600, "Uncommon"),
        ("Saturn", "Dragon Force", 1996, 80, 180, 500, "Uncommon"),
        ("Saturn", "NiGHTS into Dreams", 1996, 30, 70, 200, "Common"),
        ("Saturn", "Virtua Fighter 2", 1995, 15, 40, 120, "Common"),
        ("Saturn", "Panzer Dragoon Zwei", 1996, 60, 130, 350, "Uncommon"),
        ("Saturn", "Shining the Holy Ark", 1996, 80, 180, 450, "Uncommon"),
    ]

    # ── Neo Geo AES — Premium Cartridges ───────────────────────────────
    neogeo_games = [
        ("Neo Geo AES", "Metal Slug", 1996, 800, 1500, 4000, "Grail"),
        ("Neo Geo AES", "Metal Slug 2", 1998, 600, 1100, 3000, "Grail"),
        ("Neo Geo AES", "Metal Slug 3", 2000, 1200, 2200, 5000, "Grail"),
        ("Neo Geo AES", "Metal Slug 4", 2002, 400, 800, 2000, "Rare"),
        ("Neo Geo AES", "Metal Slug 5", 2003, 500, 1000, 2500, "Rare"),
        ("Neo Geo AES", "The King of Fighters '98", 1998, 300, 600, 1500, "Rare"),
        ("Neo Geo AES", "Garou: Mark of the Wolves", 1999, 1500, 2800, 6000, "Grail"),
        ("Neo Geo AES", "The Last Blade 2", 1998, 500, 1000, 2500, "Rare"),
        ("Neo Geo AES", "Samurai Shodown II", 1994, 200, 400, 1000, "Uncommon"),
        ("Neo Geo AES", "Blazing Star", 1998, 400, 800, 2000, "Rare"),
    ]

    # ── TurboGrafx-16 / PC Engine ──────────────────────────────────────
    tg16_games = [
        ("TurboGrafx-16", "Bonk's Adventure", 1990, 40, 100, 300, "Common"),
        ("TurboGrafx-16", "Bonk's Revenge", 1991, 30, 80, 250, "Common"),
        ("TurboGrafx-16", "Blazing Lazers", 1989, 25, 60, 200, "Common"),
        ("TurboGrafx-16", "Dungeon Explorer", 1989, 20, 50, 150, "Common"),
        ("TurboGrafx-16", "Keith Courage in Alpha Zones", 1989, 10, 30, 100, "Common"),
        ("TurboGrafx-16", "Legendary Axe", 1989, 30, 70, 200, "Common"),
        ("TurboGrafx-16", "Soldier Blade", 1992, 50, 120, 350, "Uncommon"),
        ("TurboGrafx-16", "Air Zonk", 1992, 80, 180, 500, "Uncommon"),
        ("TurboGrafx-16", "Magical Chase", 1993, 2000, 4000, 8000, "Grail"),
        ("TurboGrafx-16", "Neutopia", 1989, 25, 60, 180, "Common"),
    ]

    # ── Atari Jaguar ───────────────────────────────────────────────────
    jaguar_games = [
        ("Jaguar", "Tempest 2000", 1994, 40, 100, 300, "Common"),
        ("Jaguar", "Alien vs Predator", 1994, 50, 120, 350, "Uncommon"),
        ("Jaguar", "Rayman", 1995, 20, 50, 150, "Common"),
        ("Jaguar", "Doom", 1994, 25, 60, 180, "Common"),
        ("Jaguar", "Iron Soldier", 1994, 15, 40, 120, "Common"),
        ("Jaguar", "Wolfenstein 3D", 1994, 20, 50, 150, "Common"),
        ("Jaguar", "Battlemorph (Jaguar CD)", 1995, 30, 70, 200, "Uncommon"),
    ]

    # ── 3DO Interactive Multiplayer ────────────────────────────────────
    threedo_games = [
        ("3DO", "Road Rash", 1994, 15, 40, 120, "Common"),
        ("3DO", "The Need for Speed", 1994, 15, 40, 120, "Common"),
        ("3DO", "Super Street Fighter II Turbo", 1994, 25, 60, 180, "Common"),
        ("3DO", "Star Control II", 1994, 30, 70, 200, "Uncommon"),
        ("3DO", "Return Fire", 1995, 20, 50, 150, "Common"),
        ("3DO", "Gex", 1995, 10, 30, 100, "Common"),
        ("3DO", "Samurai Shodown", 1994, 20, 50, 150, "Common"),
    ]

    # ── CIB Variants (premium complete-in-box for key titles) ──────────
    cib_variants = [
        ("NES", "The Legend of Zelda (CIB Gold Cart)", 1986, 80, 350, 1500, "Rare"),
        ("NES", "Mega Man 5 (CIB)", 1992, 150, 400, 1200, "Rare"),
        ("SNES", "EarthBound (CIB w/ Guide)", 1995, 400, 1200, 3500, "Grail"),
        ("SNES", "Chrono Trigger (CIB)", 1995, 200, 500, 1500, "Rare"),
        ("N64", "Conker's Bad Fur Day (CIB)", 2001, 120, 350, 1000, "Rare"),
        ("N64", "Paper Mario (CIB)", 2001, 80, 200, 600, "Uncommon"),
        ("Genesis", "Phantasy Star IV (CIB)", 1993, 100, 250, 700, "Rare"),
        ("Genesis", "MUSHA (CIB)", 1990, 300, 700, 2000, "Grail"),
        ("Dreamcast", "Skies of Arcadia (CIB)", 2000, 80, 180, 500, "Uncommon"),
        ("GameCube", "Pokémon Box: Ruby & Sapphire (CIB)", 2003, 300, 600, 1500, "Grail"),
        ("Game Boy", "Pokémon Crystal (CIB)", 2000, 100, 300, 800, "Rare"),
    ]

    for platform, title, year, loose, cib, sealed, rarity in (
        saturn_games + neogeo_games + tg16_games + jaguar_games + threedo_games
    ):
        extra.append({
            "type": "game",
            "platform": platform,
            "name": title,
            "year": year,
            "price_loose": loose,
            "price_cib": cib,
            "price_sealed": sealed,
            "rarity": rarity,
        })

    for platform, title, year, loose, cib, sealed, rarity in cib_variants:
        extra.append({
            "type": "game",
            "platform": platform,
            "name": title,
            "year": year,
            "price_loose": loose,
            "price_cib": cib,
            "price_sealed": sealed,
            "rarity": rarity,
        })

    return extra


def get_curated_catalog() -> list[dict]:
    """Curated retro gaming catalog: consoles + high-value games (500+ items)."""

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

        # ── NES — Additional High-Value Titles ─────────────────────────────
        ("NES", "Bubble Bobble Part 2", 1993, 500, 1200, 3000, "Rare"),
        ("NES", "Mike Tyson's Punch-Out!!", 1987, 20, 60, 350, "Common"),
        ("NES", "Metroid", 1986, 15, 55, 300, "Common"),
        ("NES", "Castlevania III: Dracula's Curse", 1989, 40, 100, 400, "Uncommon"),
        ("NES", "Final Fantasy", 1987, 15, 60, 350, "Common"),
        ("NES", "Dragon Warrior", 1986, 10, 40, 200, "Common"),
        ("NES", "Snow Brothers", 1991, 200, 500, 1500, "Rare"),

        # ── SNES — Additional Titles ───────────────────────────────────────
        ("SNES", "Mega Man X2", 1994, 120, 280, 800, "Uncommon"),
        ("SNES", "Mega Man 7", 1995, 200, 400, 1000, "Rare"),
        ("SNES", "Turtles in Time", 1992, 40, 100, 350, "Common"),
        ("SNES", "Aero Fighters", 1994, 350, 650, 1500, "Rare"),
        ("SNES", "E.V.O.: Search for Eden", 1992, 200, 400, 1000, "Rare"),

        # ── N64 — Additional Titles ────────────────────────────────────────
        ("N64", "Bomberman 64: The Second Attack", 2000, 150, 300, 800, "Rare"),
        ("N64", "Goemon's Great Adventure", 1999, 60, 120, 350, "Uncommon"),
        ("N64", "Snowboard Kids 2", 1999, 120, 250, 600, "Rare"),
        ("N64", "Worms Armageddon", 1999, 100, 200, 500, "Uncommon"),
        ("N64", "Diddy Kong Racing", 1997, 15, 40, 180, "Common"),

        # ── GameCube — Additional Titles ───────────────────────────────────
        ("GameCube", "Baten Kaitos: Eternal Wings", 2003, 60, 130, 350, "Uncommon"),
        ("GameCube", "Eternal Darkness: Sanity's Requiem", 2002, 50, 110, 300, "Uncommon"),
        ("GameCube", "Phantasy Star Online Episode I & II Plus", 2003, 80, 170, 450, "Uncommon"),
        ("GameCube", "Pikmin 2", 2004, 50, 100, 280, "Common"),
        ("GameCube", "Animal Crossing", 2002, 20, 50, 180, "Common"),

        # ── Game Boy — Additional Titles ───────────────────────────────────
        ("GB", "Tetris", 1989, 5, 20, 120, "Common"),
        ("GB", "Super Mario Land 2: 6 Golden Coins", 1992, 10, 30, 150, "Common"),
        ("GB", "Kirby's Dream Land", 1992, 10, 30, 150, "Common"),
        ("GBC", "Pokemon Gold/Silver", 1999, 20, 60, 300, "Common"),
        ("GBC", "The Legend of Zelda: Oracle of Seasons", 2001, 25, 70, 250, "Common"),
        ("GBC", "The Legend of Zelda: Oracle of Ages", 2001, 25, 70, 250, "Common"),
        ("GBA", "Mega Man Zero", 2002, 30, 60, 200, "Common"),
        ("GBA", "WarioWare, Inc.: Mega Microgame$!", 2003, 20, 50, 180, "Common"),
        ("GBA", "Drill Dozer", 2005, 50, 110, 300, "Uncommon"),
        ("GBA", "Gunstar Super Heroes", 2005, 40, 90, 250, "Uncommon"),

        # ── Genesis / Mega Drive — Additional ──────────────────────────────
        ("Genesis", "Mega Turrican", 1993, 80, 180, 500, "Uncommon"),
        ("Genesis", "MUSHA", 1990, 300, 550, 1500, "Rare"),
        ("Genesis", "Sonic the Hedgehog 2", 1992, 5, 15, 100, "Common"),
        ("Genesis", "Shining Force II", 1993, 40, 100, 300, "Uncommon"),
        ("Genesis", "Landstalker", 1992, 20, 50, 180, "Common"),

        # ── Sega Saturn — Additional ───────────────────────────────────────
        ("Saturn", "NiGHTS into Dreams...", 1996, 30, 70, 200, "Common"),
        ("Saturn", "Virtua Fighter 2", 1995, 10, 30, 100, "Common"),
        ("Saturn", "Panzer Dragoon II Zwei", 1996, 40, 90, 250, "Uncommon"),
        ("Saturn", "Albert Odyssey: Legend of Eldean", 1996, 120, 250, 600, "Rare"),

        # ── Dreamcast — Additional ─────────────────────────────────────────
        ("Dreamcast", "Sonic Adventure 2", 2001, 40, 80, 200, "Common"),
        ("Dreamcast", "Ikaruga", 2002, 80, 160, 400, "Uncommon"),
        ("Dreamcast", "Grandia II", 2000, 25, 60, 180, "Common"),
        ("Dreamcast", "Street Fighter III: 3rd Strike", 1999, 50, 110, 300, "Uncommon"),

        # ── PS1 — Additional ───────────────────────────────────────────────
        ("PS1", "Tail Concerto", 1998, 150, 300, 700, "Rare"),
        ("PS1", "Lunar: Silver Star Story Complete", 1999, 80, 180, 500, "Uncommon"),
        ("PS1", "Wild Arms", 1996, 25, 60, 200, "Common"),
        ("PS1", "Legend of Dragoon", 1999, 30, 70, 200, "Common"),

        # ── PS2 — Additional ───────────────────────────────────────────────
        ("PS2", "Ar tonelico II", 2008, 80, 160, 400, "Uncommon"),
        ("PS2", ".hack//Quarantine", 2003, 200, 400, 900, "Rare"),
        ("PS2", "Okami", 2006, 20, 50, 150, "Common"),
        ("PS2", "Ico", 2001, 15, 40, 120, "Common"),

        # ── PSP — High-Value Titles ────────────────────────────────────────
        ("PSP", "Valkyria Chronicles III (JP)", 2011, 25, 50, 120, "JP Only"),
        ("PSP", "Persona 3 Portable", 2009, 30, 70, 200, "Uncommon"),
        ("PSP", "Final Fantasy Tactics: The War of the Lions", 2007, 15, 35, 120, "Common"),

        # ── Neo Geo — Additional ───────────────────────────────────────────
        ("Neo Geo", "The Last Blade 2", 1998, 600, 1000, 2500, "Rare"),
        ("Neo Geo", "Blazing Star", 1998, 800, 1500, 3500, "Ultra Rare"),
        ("Neo Geo", "Garou: Mark of the Wolves", 1999, 400, 700, 1800, "Rare"),

        # ── TurboGrafx-16 — Additional ─────────────────────────────────────
        ("TurboGrafx-16", "Magical Chase", 1991, 3000, 5000, 10000, "Ultra Rare"),
        ("TurboGrafx-16", "Blazing Lazers", 1989, 20, 50, 180, "Common"),

        # ── Atari 2600 — Additional ────────────────────────────────────────
        ("2600", "Solaris", 1986, 8, 25, 120, "Common"),
        ("2600", "H.E.R.O.", 1984, 8, 30, 150, "Common"),

        # ── NES — More High-Value & Essential Titles ─────────────────────
        ("NES", "Zelda II: The Adventure of Link", 1987, 12, 50, 300, "Common"),
        ("NES", "Ninja Gaiden", 1988, 12, 45, 250, "Common"),
        ("NES", "Ninja Gaiden III", 1991, 60, 150, 500, "Uncommon"),
        ("NES", "Faxanadu", 1989, 10, 35, 200, "Common"),
        ("NES", "Battletoads", 1991, 20, 60, 300, "Common"),
        ("NES", "Battletoads & Double Dragon", 1993, 40, 100, 400, "Uncommon"),
        ("NES", "Power Blade 2", 1992, 300, 700, 2000, "Rare"),
        ("NES", "Bonk's Adventure", 1993, 400, 900, 2500, "Rare"),
        ("NES", "Panic Restaurant", 1992, 500, 1100, 3000, "Rare"),
        ("NES", "Shatterhand", 1991, 100, 250, 700, "Uncommon"),

        # ── SNES — More Essential RPGs & Rarities ────────────────────────
        ("SNES", "Breath of Fire II", 1994, 40, 100, 350, "Common"),
        ("SNES", "Illusion of Gaia", 1993, 25, 60, 250, "Common"),
        ("SNES", "Super Castlevania IV", 1991, 30, 80, 300, "Common"),
        ("SNES", "Contra III: The Alien Wars", 1992, 35, 90, 350, "Common"),
        ("SNES", "Kirby Super Star", 1996, 40, 100, 350, "Common"),
        ("SNES", "Metal Warriors", 1995, 350, 700, 1800, "Rare"),
        ("SNES", "Hagane: The Final Conflict", 1994, 500, 1000, 2500, "Rare"),
        ("SNES", "Robotrek", 1994, 60, 150, 450, "Uncommon"),

        # ── N64 — CIB Premiums & Hidden Gems ─────────────────────────────
        ("N64", "Super Mario 64", 1996, 25, 60, 250, "Common"),
        ("N64", "Banjo-Tooie", 2000, 25, 65, 280, "Common"),
        ("N64", "Jet Force Gemini", 1999, 10, 30, 150, "Common"),
        ("N64", "Mischief Makers", 1997, 20, 50, 200, "Common"),
        ("N64", "Sin and Punishment (JP)", 2000, 40, 80, 200, "JP Only"),
        ("N64", "Mario Party 3", 2000, 50, 100, 350, "Uncommon"),
        ("N64", "Pokemon Snap", 1999, 15, 40, 180, "Common"),
        ("N64", "Yoshi's Story", 1997, 15, 40, 180, "Common"),
        ("N64", "Perfect Dark", 2000, 15, 40, 180, "Common"),
        ("N64", "Stunt Race FX 64 (Prototype)", 1997, 500, 1000, 3000, "Ultra Rare"),

        # ── GameCube — Hidden Gems & Premium CIB ─────────────────────────
        ("GameCube", "Pokemon XD: Gale of Darkness", 2005, 100, 200, 500, "Uncommon"),
        ("GameCube", "Paper Mario: The Thousand-Year Door", 2004, 80, 160, 400, "Uncommon"),
        ("GameCube", "F-Zero GX", 2003, 60, 120, 300, "Uncommon"),
        ("GameCube", "Custom Robo", 2004, 30, 60, 200, "Common"),
        ("GameCube", "Metal Gear Solid: The Twin Snakes", 2004, 80, 160, 400, "Uncommon"),
        ("GameCube", "Resident Evil (Remake)", 2002, 25, 55, 200, "Common"),
        ("GameCube", "Viewtiful Joe", 2003, 20, 45, 180, "Common"),
        ("GameCube", "Def Jam: Fight for NY", 2004, 80, 160, 400, "Uncommon"),

        # ── Wii — Late-Gen Rarities ──────────────────────────────────────
        ("Wii", "Xenoblade Chronicles", 2010, 30, 70, 200, "Uncommon"),
        ("Wii", "The Last Story", 2011, 25, 60, 180, "Uncommon"),
        ("Wii", "Metroid Prime Trilogy", 2009, 40, 100, 300, "Uncommon"),
        ("Wii", "Fire Emblem: Radiant Dawn", 2007, 80, 160, 400, "Rare"),
        ("Wii", "Dokapon Kingdom", 2008, 100, 200, 500, "Rare"),
        ("Wii", "Kirby's Return to Dream Land", 2011, 30, 70, 200, "Common"),

        # ── DS — Late-Gen Rarities ───────────────────────────────────────
        ("DS", "Pokemon HeartGold/SoulSilver", 2009, 80, 200, 500, "Uncommon"),
        ("DS", "Pokemon Black 2/White 2", 2012, 60, 150, 350, "Uncommon"),
        ("DS", "Castlevania: Dawn of Sorrow", 2005, 30, 70, 200, "Common"),
        ("DS", "Castlevania: Order of Ecclesia", 2008, 50, 120, 300, "Uncommon"),
        ("DS", "Dragon Quest IX: Sentinels of the Starry Skies", 2010, 15, 40, 150, "Common"),
        ("DS", "The World Ends with You", 2007, 25, 60, 200, "Uncommon"),
        ("DS", "Solatorobo: Red the Hunter", 2010, 80, 180, 450, "Rare"),
        ("DS", "Pokemon Platinum", 2008, 60, 150, 350, "Uncommon"),

        # ── Game Boy — More Rarities ─────────────────────────────────────
        ("GB", "Kid Dracula", 1993, 200, 400, 1000, "Rare"),
        ("GB", "Mega Man V", 1994, 150, 350, 900, "Rare"),
        ("GB", "Trip World", 1992, 300, 600, 1500, "Rare"),
        ("GBC", "Shantae", 2002, 500, 1000, 2500, "Ultra Rare"),
        ("GBC", "Metal Gear Solid (GBC)", 2000, 30, 70, 200, "Common"),

        # ── GBA — More Essential Titles ──────────────────────────────────
        ("GBA", "Metroid Fusion", 2002, 40, 100, 300, "Uncommon"),
        ("GBA", "Metroid: Zero Mission", 2004, 50, 120, 350, "Uncommon"),
        ("GBA", "Golden Sun", 2001, 25, 60, 200, "Common"),
        ("GBA", "Golden Sun: The Lost Age", 2002, 30, 70, 220, "Common"),
        ("GBA", "Castlevania: Circle of the Moon", 2001, 20, 50, 180, "Common"),
        ("GBA", "Castlevania: Harmony of Dissonance", 2002, 25, 60, 200, "Common"),
        ("GBA", "Riviera: The Promised Land", 2004, 30, 70, 200, "Common"),

        # ── Sega Saturn — Japanese Exclusives ────────────────────────────
        ("Saturn", "Dungeons & Dragons Collection (JP)", 1999, 200, 400, 900, "Rare"),
        ("Saturn", "X-Men vs. Street Fighter (JP)", 1997, 60, 130, 350, "Uncommon"),
        ("Saturn", "Soukyugurentai (JP)", 1996, 80, 180, 450, "Uncommon"),
        ("Saturn", "Elevator Action Returns (JP)", 1997, 100, 220, 550, "Rare"),
        ("Saturn", "Bulk Slash (JP)", 1997, 80, 170, 400, "Uncommon"),
        ("Saturn", "Hyper Duel (JP)", 1996, 300, 600, 1500, "Rare"),

        # ── Neo Geo MVS/AES — More Premium Titles ────────────────────────
        ("Neo Geo", "Matrimelee", 2003, 3000, 5000, 8000, "Ultra Rare"),
        ("Neo Geo", "Shock Troopers 2nd Squad", 1998, 300, 500, 1200, "Rare"),
        ("Neo Geo", "Samurai Shodown V Special", 2004, 400, 700, 1800, "Rare"),
        ("Neo Geo", "King of Fighters 2003", 2003, 200, 400, 1000, "Uncommon"),
        ("Neo Geo", "Windjammers", 1994, 250, 450, 1200, "Rare"),

        # ── TurboGrafx-16 / PC Engine — More Gems ────────────────────────
        ("TurboGrafx-16", "Soldier Blade", 1992, 60, 140, 400, "Uncommon"),
        ("TurboGrafx-16", "Neutopia", 1989, 30, 70, 220, "Common"),
        ("TurboGrafx-16", "Lords of Thunder", 1993, 120, 250, 650, "Rare"),
        ("TurboGrafx-16", "Dungeon Explorer", 1989, 25, 60, 200, "Common"),

        # ── PS1 — More RPGs & Collectible Titles ─────────────────────────
        ("PS1", "Persona 2: Eternal Punishment", 2000, 120, 250, 600, "Rare"),
        ("PS1", "Breath of Fire III", 1997, 40, 100, 300, "Uncommon"),
        ("PS1", "Breath of Fire IV", 2000, 50, 120, 350, "Uncommon"),
        ("PS1", "Star Ocean: The Second Story", 1998, 35, 80, 250, "Uncommon"),
        ("PS1", "Threads of Fate", 1999, 40, 100, 300, "Uncommon"),
        ("PS1", "Legend of Mana", 1999, 40, 100, 300, "Uncommon"),
        ("PS1", "Brave Fencer Musashi", 1998, 40, 100, 300, "Uncommon"),
        ("PS1", "Alundra", 1997, 50, 120, 350, "Uncommon"),
        ("PS1", "Klonoa: Door to Phantomile", 1997, 150, 300, 700, "Rare"),
        ("PS1", "Harmful Park (JP)", 1997, 200, 400, 1000, "Ultra Rare"),

        # ── PS2 — More RPGs & Horror ─────────────────────────────────────
        ("PS2", "Suikoden V", 2006, 80, 160, 400, "Uncommon"),
        ("PS2", "Persona 4", 2008, 25, 60, 180, "Common"),
        ("PS2", "Digital Devil Saga", 2004, 30, 70, 200, "Common"),
        ("PS2", "Digital Devil Saga 2", 2005, 40, 90, 250, "Uncommon"),
        ("PS2", "Shin Megami Tensei: Nocturne", 2003, 40, 100, 300, "Uncommon"),
        ("PS2", "Fatal Frame II: Crimson Butterfly", 2003, 80, 160, 400, "Uncommon"),
        ("PS2", "Dark Cloud 2", 2002, 30, 70, 200, "Common"),
        ("PS2", "Radiata Stories", 2005, 30, 70, 200, "Common"),
        ("PS2", "Rogue Galaxy", 2006, 25, 60, 180, "Common"),
        ("PS2", "Wild Arms 3", 2002, 20, 50, 150, "Common"),

        # ── Atari Jaguar — Rare Titles ───────────────────────────────────
        ("Jaguar", "Tempest 2000", 1994, 50, 120, 350, "Uncommon"),
        ("Jaguar", "Alien vs Predator", 1994, 40, 100, 300, "Uncommon"),
        ("Jaguar", "Battlesphere Gold", 2000, 500, 1000, 2500, "Ultra Rare"),

        # ── NES — Complete Essential Library ───────────────────────────
        ("NES", "Mega Man", 1987, 25, 70, 400, "Common"),
        ("NES", "Mega Man 2", 1988, 15, 50, 300, "Common"),
        ("NES", "Mega Man 3", 1990, 15, 50, 300, "Common"),
        ("NES", "Mega Man 4", 1991, 20, 60, 350, "Common"),
        ("NES", "Mega Man 6", 1993, 40, 100, 400, "Uncommon"),
        ("NES", "Super Mario Bros. 2", 1988, 10, 40, 300, "Common"),
        ("NES", "Super Mario Bros. 3", 1988, 12, 45, 350, "Common"),
        ("NES", "Castlevania", 1986, 15, 55, 300, "Common"),
        ("NES", "Castlevania II: Simon's Quest", 1987, 10, 40, 250, "Common"),
        ("NES", "Kirby's Adventure", 1993, 15, 50, 250, "Common"),
        ("NES", "Kid Icarus", 1986, 12, 45, 250, "Common"),
        ("NES", "Excitebike", 1984, 8, 30, 200, "Common"),
        ("NES", "Duck Tales 2", 1993, 200, 500, 1500, "Rare"),
        ("NES", "Tecmo Super Bowl", 1991, 15, 40, 200, "Common"),
        ("NES", "Double Dragon II: The Revenge", 1989, 10, 35, 200, "Common"),
        ("NES", "Ghosts 'n Goblins", 1986, 12, 40, 250, "Common"),
        ("NES", "Blaster Master", 1988, 10, 35, 200, "Common"),
        ("NES", "Crystalis", 1990, 20, 55, 250, "Common"),
        ("NES", "River City Ransom", 1989, 35, 80, 350, "Uncommon"),
        ("NES", "Life Force (Salamander)", 1987, 12, 40, 250, "Common"),
        ("NES", "Chip 'n Dale: Rescue Rangers", 1990, 12, 40, 200, "Common"),
        ("NES", "Darkwing Duck", 1992, 25, 60, 300, "Uncommon"),
        ("NES", "Dragon Warrior III", 1991, 30, 70, 300, "Uncommon"),
        ("NES", "Dragon Warrior IV", 1992, 40, 100, 400, "Uncommon"),
        ("NES", "Ninja Gaiden II: The Dark Sword of Chaos", 1990, 15, 45, 250, "Common"),
        ("NES", "Bionic Commando", 1988, 12, 40, 250, "Common"),
        ("NES", "Star Tropics", 1990, 10, 35, 200, "Common"),
        ("NES", "Teenage Mutant Ninja Turtles II: The Arcade Game", 1990, 10, 35, 200, "Common"),
        ("NES", "Kung Fu", 1985, 5, 20, 150, "Common"),
        ("NES", "Ice Climber", 1985, 8, 30, 200, "Common"),
        ("NES", "Wizards & Warriors", 1987, 8, 30, 180, "Common"),
        ("NES", "Adventure Island", 1986, 10, 35, 200, "Common"),
        ("NES", "Vice: Project Doom", 1991, 80, 200, 600, "Uncommon"),
        ("NES", "Kickle Cubicle", 1990, 20, 50, 250, "Common"),
        ("NES", "Jackal", 1988, 10, 35, 200, "Common"),
        ("NES", "Gun-Nac", 1990, 200, 450, 1200, "Rare"),
        ("NES", "Metal Storm", 1991, 150, 350, 1000, "Rare"),

        # ── SNES — More Essential Titles ───────────────────────────────
        ("SNES", "The Legend of Zelda: A Link to the Past", 1991, 25, 65, 300, "Common"),
        ("SNES", "Super Mario World", 1990, 15, 45, 250, "Common"),
        ("SNES", "Super Mario World 2: Yoshi's Island", 1995, 25, 65, 300, "Common"),
        ("SNES", "Donkey Kong Country", 1994, 15, 45, 250, "Common"),
        ("SNES", "Donkey Kong Country 3", 1996, 25, 65, 280, "Common"),
        ("SNES", "Final Fantasy II (IV)", 1991, 40, 100, 400, "Uncommon"),
        ("SNES", "Secret of Evermore", 1995, 30, 80, 300, "Common"),
        ("SNES", "Ogre Battle: March of the Black Queen", 1993, 80, 200, 600, "Uncommon"),
        ("SNES", "Shin Megami Tensei (Fan Translation)", 1992, 20, 40, 100, "Repro"),
        ("SNES", "Sunset Riders", 1993, 60, 150, 450, "Uncommon"),
        ("SNES", "Space Megaforce (Super Aleste)", 1992, 120, 280, 800, "Uncommon"),
        ("SNES", "Zombies Ate My Neighbors", 1993, 30, 80, 300, "Common"),
        ("SNES", "Street Fighter II Turbo", 1993, 15, 40, 200, "Common"),
        ("SNES", "Tetris Attack", 1996, 15, 40, 200, "Common"),
        ("SNES", "Super Punch-Out!!", 1994, 30, 70, 300, "Common"),
        ("SNES", "Earthworm Jim", 1994, 25, 65, 280, "Common"),
        ("SNES", "R-Type III: The Third Lightning", 1993, 80, 200, 600, "Uncommon"),

        # ── N64 — More Essential Titles ────────────────────────────────
        ("N64", "Donkey Kong 64", 1999, 20, 50, 200, "Common"),
        ("N64", "Wave Race 64", 1996, 10, 30, 150, "Common"),
        ("N64", "Kirby 64: The Crystal Shards", 2000, 20, 50, 200, "Common"),
        ("N64", "Pokemon Stadium 2", 1999, 20, 50, 200, "Common"),
        ("N64", "Excitebike 64", 2000, 10, 30, 150, "Common"),
        ("N64", "1080 Snowboarding", 1998, 8, 25, 120, "Common"),
        ("N64", "WWF No Mercy", 2000, 20, 50, 200, "Common"),
        ("N64", "Mario Tennis", 2000, 15, 40, 180, "Common"),
        ("N64", "Mario Golf", 1999, 15, 40, 180, "Common"),
        ("N64", "Pilotwings 64", 1996, 10, 30, 150, "Common"),
        ("N64", "Blast Corps", 1997, 10, 30, 150, "Common"),
        ("N64", "Star Wars: Rogue Squadron", 1998, 10, 30, 150, "Common"),
        ("N64", "Turok: Dinosaur Hunter", 1997, 10, 30, 150, "Common"),
        ("N64", "Turok 2: Seeds of Evil", 1998, 10, 30, 150, "Common"),
        ("N64", "Doom 64", 1997, 25, 60, 250, "Common"),
        ("N64", "Mystical Ninja Starring Goemon", 1997, 60, 130, 400, "Uncommon"),

        # ── GameCube — More Titles ─────────────────────────────────────
        ("GameCube", "Mario Kart: Double Dash!!", 2003, 50, 100, 280, "Common"),
        ("GameCube", "Super Smash Bros. Melee", 2001, 40, 80, 250, "Common"),
        ("GameCube", "Resident Evil 4", 2005, 20, 50, 180, "Common"),
        ("GameCube", "Star Fox Adventures", 2002, 15, 40, 150, "Common"),
        ("GameCube", "Pikmin", 2001, 30, 60, 200, "Common"),
        ("GameCube", "The Legend of Zelda: Collector's Edition", 2003, 80, 160, 400, "Uncommon"),
        ("GameCube", "Tales of Symphonia", 2003, 30, 60, 200, "Common"),
        ("GameCube", "Wave Race: Blue Storm", 2001, 15, 40, 150, "Common"),
        ("GameCube", "Mario Party 7", 2005, 40, 80, 250, "Common"),
        ("GameCube", "Kirby Air Ride", 2003, 50, 100, 300, "Uncommon"),
        ("GameCube", "Harvest Moon: A Wonderful Life", 2003, 25, 55, 200, "Common"),
        ("GameCube", "Mega Man Network Transmission", 2003, 25, 55, 180, "Common"),

        # ── Game Boy / GBC — More Titles ───────────────────────────────
        ("GB", "The Legend of Zelda: Link's Awakening", 1993, 15, 45, 250, "Common"),
        ("GB", "The Legend of Zelda: Link's Awakening DX", 1998, 20, 60, 300, "Common"),
        ("GB", "Metroid II: Return of Samus", 1991, 15, 45, 250, "Common"),
        ("GB", "Donkey Kong Land", 1995, 8, 25, 150, "Common"),
        ("GB", "Wario Land: Super Mario Land 3", 1994, 10, 35, 200, "Common"),
        ("GB", "Super Mario Land", 1989, 8, 25, 150, "Common"),
        ("GBC", "Dragon Warrior III", 2001, 30, 80, 300, "Uncommon"),
        ("GBC", "Wario Land 3", 2000, 15, 40, 180, "Common"),
        ("GBC", "Mario Tennis", 2000, 10, 30, 150, "Common"),
        ("GBC", "Dragon Warrior Monsters", 1999, 15, 40, 200, "Common"),
        ("GBC", "Dragon Warrior Monsters 2", 2001, 20, 50, 200, "Common"),

        # ── GBA — More Complete Library ────────────────────────────────
        ("GBA", "Pokemon Ruby/Sapphire", 2002, 40, 100, 300, "Common"),
        ("GBA", "The Legend of Zelda: The Minish Cap", 2004, 50, 120, 350, "Uncommon"),
        ("GBA", "Mario & Luigi: Superstar Saga", 2003, 20, 50, 180, "Common"),
        ("GBA", "Fire Emblem", 2003, 30, 70, 250, "Common"),
        ("GBA", "Advance Wars", 2001, 20, 50, 200, "Common"),
        ("GBA", "Kirby & The Amazing Mirror", 2004, 20, 50, 180, "Common"),
        ("GBA", "Final Fantasy Tactics Advance", 2003, 15, 40, 150, "Common"),
        ("GBA", "Mega Man Battle Network 3 Blue", 2003, 20, 50, 180, "Common"),
        ("GBA", "Mega Man Battle Network 6", 2005, 40, 90, 280, "Uncommon"),
        ("GBA", "Castlevania: Double Pack", 2006, 80, 180, 450, "Uncommon"),
        ("GBA", "Summon Night: Swordcraft Story 2", 2006, 60, 140, 350, "Uncommon"),

        # ── Genesis / Mega Drive — More Titles ─────────────────────────
        ("Genesis", "Sonic the Hedgehog 3", 1994, 15, 40, 200, "Common"),
        ("Genesis", "Sonic & Knuckles", 1994, 12, 35, 180, "Common"),
        ("Genesis", "Streets of Rage", 1991, 12, 35, 180, "Common"),
        ("Genesis", "Streets of Rage 3", 1994, 40, 100, 350, "Uncommon"),
        ("Genesis", "Comix Zone", 1995, 30, 70, 250, "Common"),
        ("Genesis", "Vectorman", 1995, 10, 30, 150, "Common"),
        ("Genesis", "Vectorman 2", 1996, 15, 40, 180, "Common"),
        ("Genesis", "Ristar", 1995, 40, 100, 300, "Uncommon"),
        ("Genesis", "Dynamite Headdy", 1994, 25, 60, 250, "Common"),
        ("Genesis", "ToeJam & Earl", 1991, 20, 50, 200, "Common"),
        ("Genesis", "ToeJam & Earl in Panic on Funkotron", 1993, 20, 50, 200, "Common"),
        ("Genesis", "Alien Soldier", 1995, 200, 400, 1000, "Rare"),
        ("Genesis", "Panorama Cotton", 1994, 800, 1500, 3500, "Ultra Rare"),

        # ── Sega Saturn — More Titles ──────────────────────────────────
        ("Saturn", "Daytona USA", 1995, 8, 25, 100, "Common"),
        ("Saturn", "Sega Rally Championship", 1995, 10, 30, 120, "Common"),
        ("Saturn", "Tomb Raider", 1996, 15, 40, 150, "Common"),
        ("Saturn", "Castlevania: Symphony of the Night (JP)", 1997, 80, 180, 450, "Uncommon"),
        ("Saturn", "Thunder Force V", 1997, 50, 120, 350, "Uncommon"),

        # ── Dreamcast — More Titles ────────────────────────────────────
        ("Dreamcast", "Shenmue II", 2001, 30, 70, 200, "Common"),
        ("Dreamcast", "Soul Calibur", 1999, 15, 40, 150, "Common"),
        ("Dreamcast", "Phantasy Star Online", 2000, 15, 40, 150, "Common"),
        ("Dreamcast", "Samba de Amigo", 2000, 20, 50, 180, "Common"),
        ("Dreamcast", "Space Channel 5", 1999, 15, 40, 150, "Common"),
        ("Dreamcast", "Seaman", 1999, 25, 60, 200, "Common"),
        ("Dreamcast", "Under Defeat (JP)", 2005, 100, 220, 550, "Rare"),
        ("Dreamcast", "Giga Wing 2", 2001, 80, 180, 450, "Uncommon"),

        # ── PS1 — More Essential RPGs & Rarities ──────────────────────
        ("PS1", "Final Fantasy VIII", 1999, 12, 35, 150, "Common"),
        ("PS1", "Final Fantasy IX", 2000, 15, 40, 180, "Common"),
        ("PS1", "Mega Man Legends", 1997, 30, 70, 250, "Uncommon"),
        ("PS1", "Resident Evil 2", 1998, 25, 60, 200, "Common"),
        ("PS1", "Silent Hill", 1999, 60, 150, 400, "Uncommon"),
        ("PS1", "Metal Gear Solid", 1998, 15, 40, 180, "Common"),
        ("PS1", "Crash Bandicoot: Warped", 1998, 10, 30, 150, "Common"),
        ("PS1", "Spyro the Dragon", 1998, 15, 40, 150, "Common"),
        ("PS1", "Ape Escape", 1999, 20, 50, 200, "Common"),
        ("PS1", "Dino Crisis", 1999, 25, 60, 200, "Uncommon"),
        ("PS1", "Einhander", 1997, 80, 180, 500, "Uncommon"),
        ("PS1", "Adventures of Lomax", 1996, 150, 300, 700, "Rare"),
        ("PS1", "Misadventures of Tron Bonne", 1999, 200, 400, 1000, "Rare"),
        ("PS1", "Rapid Reload (Gunners Heaven)", 1995, 60, 140, 400, "Uncommon"),
        ("PS1", "R-Type Delta", 1998, 80, 180, 500, "Uncommon"),

        # ── PS2 — More Titles ──────────────────────────────────────────
        ("PS2", "Shadow of the Colossus", 2005, 15, 40, 150, "Common"),
        ("PS2", "Final Fantasy XII", 2006, 10, 30, 120, "Common"),
        ("PS2", "Kingdom Hearts", 2002, 10, 30, 120, "Common"),
        ("PS2", "Kingdom Hearts II", 2005, 10, 30, 120, "Common"),
        ("PS2", "Katamari Damacy", 2004, 15, 40, 150, "Common"),
        ("PS2", "We Love Katamari", 2005, 20, 50, 180, "Common"),
        ("PS2", "Resident Evil 4", 2005, 10, 30, 120, "Common"),
        ("PS2", "Metal Gear Solid 3: Snake Eater", 2004, 10, 30, 120, "Common"),
        ("PS2", "Jak and Daxter: The Precursor Legacy", 2001, 10, 30, 120, "Common"),
        ("PS2", "Ratchet & Clank: Going Commando", 2003, 10, 30, 120, "Common"),
        ("PS2", "Devil May Cry", 2001, 10, 30, 120, "Common"),
        ("PS2", "Viewtiful Joe", 2003, 15, 40, 150, "Common"),
        ("PS2", "Gradius V", 2004, 60, 140, 400, "Uncommon"),
        ("PS2", "Gitaroo Man", 2001, 50, 120, 350, "Uncommon"),
        ("PS2", "Shin Megami Tensei: Digital Devil Saga", 2004, 30, 70, 200, "Common"),
        ("PS2", "Valkyrie Profile 2: Silmeria", 2006, 30, 70, 200, "Common"),
        ("PS2", "Onimusha: Warlords", 2001, 10, 30, 120, "Common"),
        ("PS2", "Onimusha 3: Demon Siege", 2004, 15, 40, 150, "Common"),

        # ── Wii — More Late-Gen Titles ─────────────────────────────────
        ("Wii", "Super Mario Galaxy", 2007, 15, 40, 150, "Common"),
        ("Wii", "Super Mario Galaxy 2", 2010, 20, 50, 180, "Common"),
        ("Wii", "The Legend of Zelda: Skyward Sword", 2011, 20, 50, 180, "Common"),
        ("Wii", "The Legend of Zelda: Twilight Princess", 2006, 15, 40, 150, "Common"),
        ("Wii", "Super Smash Bros. Brawl", 2008, 15, 40, 150, "Common"),
        ("Wii", "Punch-Out!!", 2009, 20, 50, 180, "Common"),
        ("Wii", "Mario Kart Wii", 2008, 20, 50, 180, "Common"),
        ("Wii", "Rhythm Heaven Fever", 2012, 30, 70, 200, "Uncommon"),
        ("Wii", "Pandora's Tower", 2012, 40, 100, 300, "Uncommon"),

        # ── DS — More Essential Titles ─────────────────────────────────
        ("DS", "Pokemon Diamond/Pearl", 2007, 30, 70, 200, "Common"),
        ("DS", "Mario Kart DS", 2005, 10, 30, 120, "Common"),
        ("DS", "New Super Mario Bros.", 2006, 10, 30, 120, "Common"),
        ("DS", "Chrono Trigger DS", 2008, 50, 120, 350, "Uncommon"),
        ("DS", "Dragon Quest V: Hand of the Heavenly Bride", 2008, 60, 140, 400, "Uncommon"),
        ("DS", "Dragon Quest VI: Realms of Revelation", 2011, 40, 100, 300, "Uncommon"),
        ("DS", "Radiant Historia", 2010, 40, 100, 300, "Uncommon"),

        # ── TurboGrafx-16 / PC Engine — More Titles ───────────────────
        ("TurboGrafx-16", "R-Type", 1987, 20, 50, 200, "Common"),
        ("TurboGrafx-16", "Military Madness", 1989, 15, 40, 180, "Common"),
        ("TurboGrafx-16", "Devil's Crush", 1990, 20, 50, 200, "Common"),
        ("TurboGrafx-16", "Ys Book I & II", 1989, 40, 100, 300, "Uncommon"),
        ("TurboGrafx-16", "Snatcher (PCE CD)", 1992, 200, 400, 1000, "Rare"),

        # ── Neo Geo — More Premium AES Titles ──────────────────────────
        ("Neo Geo", "Metal Slug 2", 1998, 400, 700, 1800, "Rare"),
        ("Neo Geo", "Metal Slug 3", 2000, 600, 1000, 2500, "Rare"),
        ("Neo Geo", "The King of Fighters '98", 1998, 200, 400, 1000, "Uncommon"),
        ("Neo Geo", "Pulstar", 1995, 500, 900, 2200, "Rare"),
        ("Neo Geo", "Real Bout Fatal Fury 2", 1998, 250, 450, 1200, "Rare"),

        # ── Atari 2600 — More Classic Titles ───────────────────────────
        ("2600", "Pac-Man", 1982, 3, 10, 60, "Common"),
        ("2600", "Space Invaders", 1980, 3, 10, 60, "Common"),
        ("2600", "Frogger", 1982, 3, 12, 70, "Common"),
        ("2600", "CollectAI", 1982, 3, 10, 60, "Common"),
        ("2600", "Missile Command", 1981, 3, 10, 60, "Common"),
        ("2600", "Demon Attack", 1982, 5, 15, 80, "Common"),
        ("2600", "Starmaster", 1982, 5, 15, 80, "Common"),
        ("2600", "Montezuma's Revenge", 1984, 15, 40, 200, "Uncommon"),
        ("2600", "Jr. Pac-Man", 1986, 20, 50, 250, "Uncommon"),

        # ── Atari 7800 — Titles ────────────────────────────────────────
        ("7800", "Ninja Golf", 1990, 40, 100, 300, "Uncommon"),
        ("7800", "Midnight Mutants", 1990, 30, 70, 200, "Common"),
        ("7800", "Tower Toppler", 1988, 10, 30, 120, "Common"),

        # ── Sega CD / Mega-CD — More Titles ───────────────────────────
        ("Sega CD", "Lunar: Eternal Blue", 1994, 80, 180, 500, "Uncommon"),
        ("Sega CD", "Sonic CD", 1993, 30, 70, 200, "Common"),
        ("Sega CD", "Night Trap", 1992, 30, 80, 250, "Common"),
        ("Sega CD", "Popful Mail", 1994, 200, 400, 900, "Rare"),
        ("Sega CD", "Keio Flying Squadron", 1993, 300, 600, 1500, "Rare"),

        # ── PSP — More High-Value Titles ───────────────────────────────
        ("PSP", "Crisis Core: Final Fantasy VII", 2007, 10, 30, 100, "Common"),
        ("PSP", "Monster Hunter Freedom Unite", 2008, 10, 30, 100, "Common"),
        ("PSP", "Kingdom Hearts: Birth by Sleep", 2010, 15, 40, 150, "Common"),
        ("PSP", "Castlevania: The Dracula X Chronicles", 2007, 20, 50, 180, "Common"),
        ("PSP", "LocoRoco", 2006, 10, 25, 80, "Common"),
        ("PSP", "Patapon 2", 2008, 10, 25, 80, "Common"),
        ("PSP", "Mega Man Powered Up", 2006, 30, 70, 200, "Uncommon"),
        ("PSP", "Gitaroo Man Lives!", 2006, 30, 70, 200, "Uncommon"),

        # ── Sega Game Gear — Notable Titles ────────────────────────────
        ("Game Gear", "Sonic the Hedgehog", 1991, 5, 15, 80, "Common"),
        ("Game Gear", "Shinobi", 1991, 10, 30, 120, "Common"),
        ("Game Gear", "Shining Force: The Sword of Hajya", 1994, 30, 70, 200, "Uncommon"),
        ("Game Gear", "Mega Man", 1995, 40, 100, 300, "Uncommon"),

        # ── ColecoVision / Intellivision ───────────────────────────────
        ("ColecoVision", "Donkey Kong", 1982, 8, 25, 120, "Common"),
        ("ColecoVision", "Zaxxon", 1982, 8, 25, 120, "Common"),
        ("ColecoVision", "Turbo", 1982, 10, 30, 150, "Common"),
        ("Intellivision", "Advanced Dungeons & Dragons", 1982, 8, 25, 120, "Common"),
        ("Intellivision", "Astrosmash", 1981, 5, 15, 80, "Common"),
        ("Intellivision", "B-17 Bomber", 1982, 8, 25, 120, "Common"),

        # ── Sega Saturn — Japanese Exclusives ─────────────────────────────
        ("Saturn", "Grandia (JP)", 1997, 20, 50, 200, "Common"),
        ("Saturn", "Sakura Wars (JP)", 1996, 15, 40, 180, "Common"),
        ("Saturn", "Princess Crown (JP)", 1997, 80, 180, 500, "Uncommon"),
        ("Saturn", "Soukyugurentai (Terra Diver) (JP)", 1996, 100, 220, 600, "Uncommon"),
        ("Saturn", "Batsugun (JP)", 1996, 150, 350, 900, "Rare"),

        # ── Neo Geo AES — More Premium Titles ────────────────────────────
        ("Neo Geo", "Kizuna Encounter: Super Tag Battle", 1996, 600, 1100, 2800, "Rare"),
        ("Neo Geo", "Matrimelee", 2003, 1500, 2800, 6000, "Grail"),
        ("Neo Geo", "Twinkle Star Sprites", 1996, 400, 800, 2000, "Rare"),
        ("Neo Geo", "Waku Waku 7", 1996, 300, 600, 1500, "Rare"),
        ("Neo Geo", "Stakes Winner 2", 1996, 200, 400, 1000, "Uncommon"),

        # ── TurboGrafx-16 / PC Engine — More Titles ──────────────────────
        ("TurboGrafx-16", "Sapphire (PCE CD)", 1995, 1500, 3000, 6500, "Grail"),
        ("TurboGrafx-16", "Gate of Thunder (TurboGrafx-CD)", 1992, 30, 80, 250, "Common"),
        ("TurboGrafx-16", "Dracula X: Rondo of Blood (PCE CD)", 1993, 150, 350, 900, "Rare"),
        ("TurboGrafx-16", "Ninja Spirit", 1990, 40, 100, 300, "Uncommon"),
        ("TurboGrafx-16", "Splatterhouse (TurboGrafx-16)", 1990, 60, 150, 400, "Uncommon"),

        # ── NES — Mega Man & Castlevania CIB ────────────────────────────
        ("NES", "Mega Man (CIB)", 1987, 250, 600, 2000, "Rare"),
        ("NES", "Mega Man 2 (CIB)", 1988, 60, 180, 600, "Uncommon"),
        ("NES", "Mega Man 3 (CIB)", 1990, 50, 150, 500, "Uncommon"),
        ("NES", "Mega Man 4 (CIB)", 1991, 80, 200, 700, "Uncommon"),
        ("NES", "Mega Man 6 (CIB)", 1993, 100, 300, 900, "Rare"),
        ("NES", "Castlevania (CIB)", 1986, 80, 250, 800, "Uncommon"),
        ("NES", "Castlevania II: Simon's Quest (CIB)", 1987, 40, 120, 400, "Common"),
        ("NES", "Castlevania III: Dracula's Curse (CIB)", 1989, 100, 280, 900, "Rare"),
        ("NES", "Contra (CIB)", 1988, 80, 250, 800, "Uncommon"),
        ("NES", "Super C (CIB)", 1990, 50, 150, 500, "Uncommon"),
        ("NES", "Bubble Bobble (CIB)", 1988, 40, 120, 350, "Common"),
        ("NES", "Ninja Gaiden (CIB)", 1988, 35, 100, 350, "Common"),
        ("NES", "Ninja Gaiden II (CIB)", 1990, 30, 90, 300, "Common"),
        ("NES", "Ninja Gaiden III (CIB)", 1991, 80, 220, 700, "Uncommon"),
        ("NES", "Little Samson (CIB)", 1992, 1500, 3500, 7000, "Grail"),

        # ── SNES — RPGs & Platformers ────────────────────────────────────
        ("SNES", "Final Fantasy III (CIB)", 1994, 80, 250, 700, "Uncommon"),
        ("SNES", "Secret of Mana (CIB)", 1993, 60, 180, 500, "Uncommon"),
        ("SNES", "Illusion of Gaia (CIB)", 1993, 40, 120, 350, "Common"),
        ("SNES", "Lufia II: Rise of the Sinistrals (CIB)", 1995, 150, 350, 900, "Rare"),
        ("SNES", "Breath of Fire II (CIB)", 1994, 60, 150, 450, "Uncommon"),
        ("SNES", "Ogre Battle: March of the Black Queen (CIB)", 1993, 120, 300, 800, "Rare"),
        ("SNES", "Pocky & Rocky (CIB)", 1992, 200, 450, 1200, "Rare"),
        ("SNES", "Pocky & Rocky 2 (CIB)", 1994, 500, 1000, 2500, "Grail"),
        ("SNES", "Demon's Crest (CIB)", 1994, 200, 450, 1100, "Rare"),
        ("SNES", "Tetris Attack (CIB)", 1996, 30, 80, 250, "Common"),
        ("SNES", "Kirby Super Star (CIB)", 1996, 50, 140, 400, "Uncommon"),

        # ── N64 — CIB Games ──────────────────────────────────────────────
        ("N64", "Banjo-Kazooie (CIB)", 1998, 50, 150, 400, "Uncommon"),
        ("N64", "Banjo-Tooie (CIB)", 2000, 60, 170, 450, "Uncommon"),
        ("N64", "Donkey Kong 64 (CIB)", 1999, 40, 120, 350, "Common"),
        ("N64", "Star Fox 64 (CIB)", 1997, 35, 100, 300, "Common"),
        ("N64", "F-Zero X (CIB)", 1998, 40, 110, 300, "Common"),
        ("N64", "Sin and Punishment (JP CIB)", 2000, 50, 120, 350, "Uncommon"),
        ("N64", "Bomberman 64 (CIB)", 1997, 30, 80, 250, "Common"),
        ("N64", "Diddy Kong Racing (CIB)", 1997, 30, 90, 280, "Common"),
        ("N64", "Mario Party 2 (CIB)", 1999, 60, 160, 450, "Uncommon"),
        ("N64", "Mario Party 3 (CIB)", 2000, 70, 180, 500, "Uncommon"),

        # ── Sega Genesis — CIB Games ─────────────────────────────────────
        ("Genesis", "Gunstar Heroes (CIB)", 1993, 60, 150, 450, "Uncommon"),
        ("Genesis", "Rocket Knight Adventures (CIB)", 1993, 50, 130, 350, "Uncommon"),
        ("Genesis", "Castlevania: Bloodlines (CIB)", 1994, 100, 280, 800, "Rare"),
        ("Genesis", "Contra: Hard Corps (CIB)", 1994, 80, 220, 600, "Uncommon"),
        ("Genesis", "Shining Force (CIB)", 1992, 50, 130, 400, "Uncommon"),
        ("Genesis", "Shining Force II (CIB)", 1993, 60, 160, 500, "Uncommon"),
        ("Genesis", "Ranger X (CIB)", 1993, 40, 110, 300, "Common"),
        ("Genesis", "Landstalker (CIB)", 1993, 40, 100, 300, "Common"),

        # ── PS1 — RPGs ───────────────────────────────────────────────────
        ("PS1", "Suikoden II (CIB)", 1999, 200, 450, 1200, "Rare"),
        ("PS1", "Xenogears (CIB)", 1998, 80, 200, 600, "Uncommon"),
        ("PS1", "Vagrant Story (CIB)", 2000, 60, 150, 450, "Uncommon"),
        ("PS1", "Legend of Dragoon (CIB)", 1999, 40, 100, 300, "Common"),
        ("PS1", "Parasite Eve (CIB)", 1998, 50, 130, 400, "Uncommon"),
        ("PS1", "Parasite Eve II (CIB)", 1999, 60, 150, 500, "Uncommon"),
        ("PS1", "Brave Fencer Musashi (CIB)", 1998, 50, 130, 400, "Uncommon"),
        ("PS1", "Valkyrie Profile (CIB)", 1999, 120, 300, 800, "Rare"),
        ("PS1", "Lunar: Silver Star Story Complete (CIB)", 1999, 80, 200, 600, "Uncommon"),
        ("PS1", "Lunar 2: Eternal Blue Complete (CIB)", 2000, 100, 250, 700, "Rare"),
        ("PS1", "Tomba! (CIB)", 1997, 150, 350, 900, "Rare"),
        ("PS1", "Tomba! 2 (CIB)", 1999, 120, 280, 750, "Rare"),

        # ── TurboGrafx-16 — Additional Titles ────────────────────────────
        ("TurboGrafx-16", "Cadash (TurboGrafx-16)", 1991, 50, 120, 350, "Uncommon"),
        ("TurboGrafx-16", "Devil's Crush (TurboGrafx-16)", 1990, 25, 60, 200, "Common"),
        ("TurboGrafx-16", "Military Madness (TurboGrafx-16)", 1989, 20, 50, 180, "Common"),
        ("TurboGrafx-16", "Parasol Stars (PCE JP)", 1991, 30, 80, 250, "Common"),
        ("TurboGrafx-16", "Bomberman '94 (PCE JP)", 1993, 40, 100, 300, "Uncommon"),
        ("TurboGrafx-16", "Download (TurboGrafx-16)", 1990, 20, 50, 180, "Common"),

        # ── Neo Geo AES — More Premium Titles ────────────────────────────
        ("Neo Geo AES", "Pulstar", 1995, 600, 1200, 3000, "Grail"),
        ("Neo Geo AES", "Viewpoint", 1992, 350, 700, 1800, "Rare"),
        ("Neo Geo AES", "Ninja Master's", 1996, 400, 800, 2000, "Rare"),
        ("Neo Geo AES", "Shock Troopers", 1997, 700, 1400, 3500, "Grail"),
        ("Neo Geo AES", "Real Bout Fatal Fury 2", 1998, 250, 500, 1200, "Rare"),
        ("Neo Geo AES", "Art of Fighting 3", 1996, 300, 600, 1500, "Rare"),
        ("Neo Geo AES", "Windjammers", 1994, 250, 500, 1200, "Rare"),

        # ── Sega Saturn — More Japanese Imports ──────────────────────────
        ("Saturn", "Dungeons & Dragons Collection (JP)", 1999, 250, 500, 1200, "Rare"),
        ("Saturn", "X-Men vs Street Fighter (4MB Cart, JP)", 1997, 60, 140, 400, "Uncommon"),
        ("Saturn", "Marvel Super Heroes (JP)", 1997, 80, 180, 500, "Uncommon"),
        ("Saturn", "Cotton 2 (JP)", 1997, 120, 280, 700, "Rare"),

        # ── Additional Retro Games (+14) ───────────────────────────────────
        ("SNES", "Hagane: The Final Conflict", 1994, 300, 700, 1800, "Rare"),
        ("SNES", "Pocky & Rocky 2", 1994, 250, 600, 1500, "Rare"),
        ("NES", "Flintstones: The Surprise at Dinosaur Peak!", 1994, 600, 1500, 4000, "Rare"),
        ("NES", "Snow Brothers", 1991, 200, 500, 1200, "Rare"),
        ("N64", "Bomberman 64: The Second Attack!", 2000, 80, 200, 500, "Uncommon"),
        ("N64", "Stunt Racer 64", 2000, 60, 180, 450, "Uncommon"),
        ("GameCube", "Gotcha Force", 2003, 150, 400, 1000, "Rare"),
        ("GameCube", "Cubivore: Survival of the Fittest", 2002, 120, 300, 800, "Rare"),
        ("Game Boy", "Trip World", 1992, 200, 500, 1200, "Rare"),
        ("Game Boy Advance", "Drill Dozer", 2005, 50, 120, 300, "Uncommon"),
        ("Genesis", "Crusader of Centy", 1994, 200, 450, 1100, "Rare"),
        ("Genesis", "Musha", 1990, 300, 700, 1800, "Rare"),
        ("Dreamcast", "Project Justice", 2000, 60, 150, 400, "Uncommon"),
        ("Dreamcast", "Mars Matrix", 2001, 80, 200, 500, "Uncommon"),
        ("TurboGrafx-16", "Magical Chase", 1991, 2000, 4000, 8000, "Ultra Rare"),
        ("Game Boy Advance", "Ninja Five-O", 2003, 200, 500, 1200, "Rare"),
        ("Saturn", "Princess Crown (JP)", 1997, 80, 200, 500, "Uncommon"),

        # === EXPANSION ROUND 12 — 60 new unique titles for 700+ ===

        # ── Game Boy / Game Boy Color — Classics ────────────────────────
        ("GB", "Gargoyle's Quest", 1990, 25, 60, 200, "Common"),
        ("GB", "Mole Mania", 1996, 30, 80, 250, "Uncommon"),
        ("GB", "Donkey Kong (1994)", 1994, 15, 40, 120, "Common"),
        ("GB", "Wario Land: Super Mario Land 3", 1994, 20, 50, 150, "Common"),
        ("GB", "Kid Dracula", 1993, 150, 350, 900, "Rare"),
        ("GBC", "Dragon Warrior III (GBC)", 2000, 40, 100, 300, "Uncommon"),
        ("GBC", "Dragon Warrior Monsters 2: Cobi's Journey", 2001, 25, 60, 180, "Common"),
        ("GBC", "Metal Gear Solid (GBC)", 2000, 30, 80, 250, "Uncommon"),
        ("GBC", "Shantae (GBC)", 2002, 400, 900, 2200, "Rare"),
        ("GBC", "Survival Kids", 1999, 30, 80, 250, "Uncommon"),

        # ── Game Boy Advance — Hidden Gems ──────────────────────────────
        ("GBA", "Riviera: The Promised Land", 2004, 25, 60, 180, "Common"),
        ("GBA", "Summon Night: Swordcraft Story", 2003, 20, 50, 150, "Common"),
        ("GBA", "Summon Night: Swordcraft Story 2", 2005, 25, 60, 180, "Common"),
        ("GBA", "Sigma Star Saga", 2005, 20, 50, 150, "Common"),
        ("GBA", "Boktai: The Sun Is in Your Hand", 2003, 40, 100, 300, "Uncommon"),
        ("GBA", "Boktai 2: Solar Boy Django", 2004, 50, 130, 350, "Uncommon"),
        ("GBA", "Gunstar Super Heroes (GBA)", 2005, 30, 80, 250, "Uncommon"),
        ("GBA", "Astro Boy: Omega Factor", 2004, 35, 90, 280, "Uncommon"),

        # ── PS2 — Rare & Valuable ──────────────────────────────────────
        ("PS2", "Rule of Rose", 2006, 200, 500, 1200, "Rare"),
        ("PS2", "Haunting Ground", 2005, 100, 250, 600, "Rare"),
        ("PS2", "Kuon", 2004, 150, 350, 900, "Rare"),
        ("PS2", ".hack//Quarantine", 2003, 80, 200, 500, "Uncommon"),
        ("PS2", "Suikoden V", 2006, 60, 150, 400, "Uncommon"),
        ("PS2", "Xenosaga Episode III", 2006, 70, 180, 450, "Uncommon"),
        ("PS2", "Shadow Hearts: Covenant", 2004, 40, 100, 300, "Uncommon"),
        ("PS2", "Steambot Chronicles", 2006, 50, 130, 350, "Uncommon"),

        # ── Dreamcast — Additional Titles ──────────────────────────────
        ("Dreamcast", "Ikaruga", 2002, 60, 150, 400, "Uncommon"),
        ("Dreamcast", "Giga Wing", 1999, 50, 120, 350, "Uncommon"),
        ("Dreamcast", "Cannon Spike", 2000, 150, 350, 900, "Rare"),
        ("Dreamcast", "Tech Romancer", 1999, 40, 100, 300, "Uncommon"),
        ("Dreamcast", "Bangai-O", 1999, 60, 150, 400, "Uncommon"),
        ("Dreamcast", "Under Defeat (JP)", 2005, 80, 200, 500, "Uncommon"),
        ("Dreamcast", "Border Down (JP)", 2003, 100, 250, 600, "Rare"),

        # ── Sega Master System — Classics ──────────────────────────────
        ("Master System", "Phantasy Star", 1987, 60, 150, 400, "Uncommon"),
        ("Master System", "Golvellius: Valley of Doom", 1988, 30, 80, 250, "Common"),
        ("Master System", "Wonder Boy III: The Dragon's Trap", 1989, 25, 60, 200, "Common"),
        ("Master System", "Sonic the Hedgehog (SMS)", 1991, 15, 40, 120, "Common"),
        ("Master System", "Alex Kidd in Miracle World", 1986, 20, 50, 150, "Common"),

        # ── Sega CD — Additional Titles ────────────────────────────────
        ("Sega CD", "Popful Mail", 1994, 120, 300, 800, "Rare"),
        ("Sega CD", "Keio Flying Squadron", 1994, 200, 500, 1200, "Rare"),
        ("Sega CD", "Vay", 1994, 40, 100, 300, "Uncommon"),
        ("Sega CD", "Dark Wizard", 1993, 50, 130, 350, "Uncommon"),

        # ── PSP — Collectible Titles ───────────────────────────────────
        ("PSP", "Persona 3 Portable", 2009, 40, 100, 300, "Uncommon"),
        ("PSP", "Castlevania: The Dracula X Chronicles", 2007, 20, 50, 150, "Common"),
        ("PSP", "Mega Man Powered Up", 2006, 20, 50, 150, "Common"),
        ("PSP", "Mega Man Maverick Hunter X", 2005, 15, 40, 120, "Common"),
        ("PSP", "Valkyrie Profile: Lenneth", 2006, 30, 80, 250, "Uncommon"),
        ("PSP", "Tactics Ogre: Let Us Cling Together (PSP)", 2010, 25, 60, 200, "Uncommon"),

        # ── Nintendo DS — Collectible Titles ───────────────────────────
        ("DS", "Solatorobo: Red the Hunter", 2010, 80, 200, 500, "Uncommon"),
        ("DS", "Radiant Historia", 2010, 30, 80, 250, "Uncommon"),
        ("DS", "Infinite Space", 2009, 40, 100, 300, "Uncommon"),
        ("DS", "Retro Game Challenge", 2009, 30, 80, 250, "Uncommon"),
        ("DS", "Knights in the Nightmare", 2009, 25, 60, 200, "Common"),
        ("DS", "Dokapon Journey", 2009, 60, 150, 400, "Uncommon"),
        ("DS", "Nostalgia", 2009, 40, 100, 300, "Uncommon"),
        ("DS", "Avalon Code", 2009, 50, 130, 350, "Uncommon"),
        ("DS", "Lunar Knights", 2006, 20, 50, 150, "Common"),
        ("DS", "Okamiden", 2011, 25, 60, 200, "Common"),
        # --- Backyard Sports (Humongous Entertainment, 1997-2010) ---
        # PC Big Box releases (highest collectible value)
        ("PC", "Backyard Baseball", 1997, 50, 150, 500, "Grail"),
        ("PC", "Backyard Soccer", 1998, 30, 80, 250, "Rare"),
        ("PC", "Backyard Football", 1999, 30, 80, 250, "Rare"),
        ("PC", "Backyard Basketball", 2001, 25, 60, 200, "Uncommon"),
        ("PC", "Backyard Hockey", 2002, 25, 60, 200, "Uncommon"),
        ("PC", "Backyard Baseball 2001", 2000, 35, 100, 300, "Rare"),
        ("PC", "Backyard Football 2002", 2001, 20, 50, 180, "Uncommon"),
        ("PC", "Backyard Baseball 2003", 2002, 30, 80, 250, "Rare"),
        ("PC", "Backyard Baseball 2005", 2004, 20, 50, 180, "Uncommon"),
        ("PC", "Backyard Skateboarding", 2004, 20, 50, 180, "Uncommon"),
        ("PC", "Backyard Soccer MLS Edition", 2001, 25, 60, 200, "Uncommon"),
        ("PC", "Backyard Football 2004", 2003, 20, 50, 180, "Uncommon"),
        ("PC", "Backyard Baseball 2007", 2006, 15, 40, 150, "Common"),
        ("PC", "Backyard Sports Baseball 2007", 2006, 15, 40, 150, "Common"),
        ("PC", "Backyard Sports Football 2007", 2006, 15, 40, 150, "Common"),
        ("PC", "Backyard Sports Basketball 2007", 2006, 15, 40, 150, "Common"),
        ("PC", "Backyard Sports Soccer 2007", 2006, 15, 40, 150, "Common"),
        # Console versions — GBA
        ("GBA", "Backyard Baseball", 2002, 8, 25, 80, "Common"),
        ("GBA", "Backyard Football", 2002, 8, 25, 80, "Common"),
        ("GBA", "Backyard Hockey", 2003, 10, 30, 100, "Common"),
        ("GBA", "Backyard Skateboarding", 2004, 10, 30, 100, "Common"),
        ("GBA", "Backyard Baseball 2006", 2005, 8, 25, 80, "Common"),
        ("GBA", "Backyard Baseball 2007", 2006, 8, 25, 80, "Common"),
        ("GBA", "Backyard Basketball", 2004, 10, 30, 100, "Common"),
        ("GBA", "Backyard Football 2006", 2005, 8, 25, 80, "Common"),
        ("GBA", "Backyard Sports: Basketball 2007", 2006, 8, 25, 80, "Common"),
        # Console versions — PS2
        ("PS2", "Backyard Baseball '09", 2008, 10, 30, 100, "Common"),
        ("PS2", "Backyard Baseball '10", 2009, 10, 30, 100, "Common"),
        ("PS2", "Backyard Football '08", 2007, 10, 30, 100, "Common"),
        ("PS2", "Backyard Football '09", 2008, 10, 30, 100, "Common"),
        ("PS2", "Backyard Baseball", 2004, 8, 25, 80, "Common"),
        ("PS2", "Backyard Football", 2005, 8, 25, 80, "Common"),
        ("PS2", "Backyard Basketball", 2005, 8, 25, 80, "Common"),
        # Console versions — GameCube
        ("GameCube", "Backyard Baseball", 2003, 12, 35, 120, "Common"),
        ("GameCube", "Backyard Football", 2004, 12, 35, 120, "Common"),
        ("GameCube", "Backyard Basketball", 2004, 12, 35, 120, "Common"),
        # Console versions — Wii
        ("Wii", "Backyard Baseball '09", 2008, 8, 25, 80, "Common"),
        ("Wii", "Backyard Baseball '10", 2009, 8, 25, 80, "Common"),
        ("Wii", "Backyard Football '08", 2007, 8, 25, 80, "Common"),
        ("Wii", "Backyard Football '09", 2008, 8, 25, 80, "Common"),
        ("Wii", "Backyard Football '10", 2009, 8, 25, 80, "Common"),
        ("Wii", "Backyard Sports: Sandlot Sluggers", 2010, 10, 30, 100, "Common"),
        ("Wii", "Backyard Sports: Rookie Rush", 2010, 10, 30, 100, "Common"),
        ("Wii", "Backyard Basketball", 2007, 8, 25, 80, "Common"),
        # Console versions — DS
        ("DS", "Backyard Sports: Sandlot Sluggers", 2010, 10, 30, 100, "Common"),
        ("DS", "Backyard Sports: Rookie Rush", 2010, 10, 30, 100, "Common"),
        ("DS", "Backyard Baseball '09", 2008, 8, 25, 80, "Common"),
        ("DS", "Backyard Baseball '10", 2009, 8, 25, 80, "Common"),
        ("DS", "Backyard Football '09", 2008, 8, 25, 80, "Common"),
        ("DS", "Backyard Basketball", 2007, 8, 25, 80, "Common"),
        # Backyard Sports merch / collectibles
        ("Merch", "Backyard Baseball Pablo Sanchez Bobblehead", 2003, 40, 80, 200, "Ultra Rare"),
        ("Merch", "Backyard Sports Official Strategy Guide", 2001, 20, 50, 120, "Rare"),
        ("Merch", "Backyard Baseball Promotional Poster Set", 1999, 30, 60, 150, "Rare"),
        ("Merch", "Backyard Sports Collector's Tin (2003 Holiday Bundle)", 2003, 50, 120, 300, "Ultra Rare"),
        # --- Backyard Sports: International / Regional Variants ---
        ("PC", "Backyard Baseball (European Release)", 1998, 40, 120, 400, "Ultra Rare"),
        ("PC", "Backyard Baseball (German Hof-Baseball Edition)", 1999, 50, 140, 450, "Ultra Rare"),
        ("PC", "Backyard Soccer (European Release)", 1999, 25, 70, 220, "Rare"),
        ("PC", "Backyard Football (Canadian French Edition)", 2000, 30, 80, 250, "Rare"),
        ("GBA", "Backyard Baseball (PAL Region)", 2002, 12, 35, 120, "Uncommon"),
        ("GBA", "Backyard Football (PAL Region)", 2002, 12, 35, 120, "Uncommon"),
        ("GBA", "Backyard Hockey (PAL Region)", 2003, 15, 40, 130, "Uncommon"),
        ("GBA", "Backyard Baseball 2006 (PAL Region)", 2005, 12, 35, 120, "Uncommon"),
        ("DS", "Backyard Baseball '09 (PAL Region)", 2008, 10, 30, 100, "Uncommon"),
        ("DS", "Backyard Sports: Sandlot Sluggers (PAL Region)", 2010, 12, 35, 110, "Uncommon"),
        ("DS", "Backyard Sports: Rookie Rush (PAL Region)", 2010, 12, 35, 110, "Uncommon"),
        ("Wii", "Backyard Baseball '09 (PAL Region)", 2008, 10, 30, 100, "Uncommon"),
        ("Wii", "Backyard Sports: Sandlot Sluggers (PAL Region)", 2010, 12, 35, 110, "Uncommon"),
        ("Wii", "Backyard Sports: Rookie Rush (PAL Region)", 2010, 12, 35, 110, "Uncommon"),
        ("PC", "Backyard Baseball (Australian Release)", 1998, 45, 130, 420, "Ultra Rare"),
        ("PC", "Backyard Soccer (Australian Release)", 1999, 30, 80, 240, "Rare"),
        ("PC", "Backyard Football (Australian Release)", 2000, 30, 80, 240, "Rare"),
        ("Wii", "Backyard Baseball '10 (PAL Region)", 2009, 10, 30, 100, "Uncommon"),
        ("Wii", "Backyard Football '09 (PAL Region)", 2008, 10, 30, 100, "Uncommon"),
        ("DS", "Backyard Football '09 (PAL Region)", 2008, 10, 30, 100, "Uncommon"),
        # --- Backyard Sports: Special / Limited Editions ---
        ("PC", "Backyard Baseball: 10th Anniversary Edition", 2007, 40, 100, 300, "Rare"),
        ("PC", "Backyard Sports Mega Pack (All-in-One Collection)", 2005, 35, 90, 280, "Rare"),
        ("PC", "Backyard Baseball 2-Pack (1997 + 2001)", 2003, 30, 80, 250, "Uncommon"),
        ("PC", "Backyard Sports Holiday Bundle (Tin Case)", 2003, 50, 120, 350, "Rare"),
        ("PC", "Backyard Baseball Championship Edition", 2004, 25, 70, 220, "Uncommon"),
        ("PC", "Humongous Entertainment 10-Pack (Backyard + Putt-Putt + Freddi Fish)", 2004, 60, 150, 400, "Rare"),
        ("GBA", "Backyard Baseball + Backyard Football Combo (Dual Cart Bundle)", 2003, 20, 50, 160, "Rare"),
        ("Wii", "Backyard Sports Collection (Multi-Game Disc)", 2009, 15, 40, 130, "Uncommon"),
        ("PC", "Best of Backyard Sports (Compilation)", 2008, 20, 50, 180, "Uncommon"),
        ("PC", "Backyard Sports 4-Game Fun Pack", 2006, 25, 60, 200, "Uncommon"),
        ("PC", "Backyard Baseball Gold Edition (Infogrames Re-Release)", 2003, 20, 50, 170, "Uncommon"),
        ("PC", "Backyard Sports MVP Baseball Pack", 2005, 25, 60, 200, "Uncommon"),
        ("PC", "Backyard Sports Triple Play Bundle (Baseball + Football + Soccer)", 2004, 35, 90, 280, "Rare"),
        ("PC", "Backyard Sports Collector's Edition (Numbered, 2500 copies)", 2003, 80, 200, 500, "Ultra Rare"),
        ("PC", "Backyard Baseball Walmart Exclusive Bundle", 2005, 20, 50, 180, "Uncommon"),
        # --- Backyard Sports: Demo / Promo Versions ---
        ("PC", "Backyard Baseball Demo Disc (Cereal Box Promo)", 1998, 80, 150, 400, "Grail"),
        ("PC", "Backyard Baseball Kellogg's Promo CD", 1999, 60, 120, 300, "Ultra Rare"),
        ("PC", "Backyard Football Pizza Hut Promo Disc", 2000, 50, 100, 250, "Ultra Rare"),
        ("PC", "Backyard Sports Sampler Disc", 2002, 30, 70, 200, "Rare"),
        ("Promo", "Backyard Baseball Store Display Box (Promotional)", 1997, 100, 200, 500, "Grail"),
        ("Promo", "Backyard Baseball Press Kit (Media)", 1997, 120, 250, 600, "Grail"),
        ("PC", "Humongous Entertainment Catalog CD-ROM (Includes Backyard Demos)", 1999, 25, 60, 180, "Rare"),
        ("PC", "Backyard Baseball E3 Demo Disc", 1997, 100, 200, 500, "Grail"),
        ("PC", "Backyard Sports Holiday Sampler (Cereal Premium)", 2003, 40, 80, 200, "Rare"),
        ("PC", "Backyard Baseball 2003 Best Buy Exclusive Demo", 2002, 35, 70, 180, "Rare"),
        # --- Backyard Sports: Platform Variants & Ports ---
        ("PC", "Backyard Baseball 2006", 2005, 15, 40, 150, "Common"),
        ("GameCube", "Backyard Baseball 2005", 2004, 15, 40, 130, "Common"),
        ("PC", "Backyard Football 2006", 2005, 15, 40, 150, "Common"),
        ("PS2", "Backyard Football 2006", 2005, 10, 30, 100, "Common"),
        ("GameCube", "Backyard Football 2006", 2005, 12, 35, 120, "Common"),
        ("PC", "Backyard Basketball 2004", 2003, 15, 40, 150, "Common"),
        ("PC", "Backyard Hockey 2005", 2004, 15, 40, 150, "Common"),
        ("GameCube", "Backyard Baseball 2003", 2002, 15, 40, 130, "Common"),
        ("GBA", "Backyard Baseball 2003", 2002, 10, 30, 100, "Common"),
        ("GBA", "Backyard Football 2004", 2003, 10, 30, 100, "Common"),
        ("GameCube", "Backyard Football 2004", 2003, 12, 35, 120, "Common"),
        ("PC", "Backyard Skateboarding 2006", 2005, 15, 40, 150, "Common"),
        ("GBA", "Backyard Sports Basketball 2007", 2006, 8, 25, 80, "Common"),
        ("GBA", "Backyard Sports Football 2007", 2006, 8, 25, 80, "Common"),
        ("Wii", "Backyard Baseball", 2007, 8, 25, 80, "Common"),
        ("Wii", "Backyard Football", 2007, 8, 25, 80, "Common"),
        ("DS", "Backyard Baseball", 2007, 8, 25, 80, "Common"),
        ("DS", "Backyard Football '08", 2007, 8, 25, 80, "Common"),
        ("DS", "Backyard Baseball '10 (Atari)", 2009, 8, 25, 80, "Common"),
        ("Wii", "Backyard Sports: All-Stars", 2010, 10, 30, 100, "Common"),
        ("PS2", "Backyard Sports: Sandlot Sluggers", 2010, 10, 30, 100, "Common"),
        ("Xbox 360", "Backyard Sports: Sandlot Sluggers", 2010, 12, 35, 120, "Common"),
        ("Xbox 360", "Backyard Sports: Rookie Rush", 2010, 12, 35, 120, "Common"),
        # --- Backyard Sports: Strategy Guides & Books ---
        ("Book", "Backyard Baseball Official Strategy Guide (Prima)", 2001, 15, 35, 80, "Uncommon"),
        ("Book", "Backyard Football Official Strategy Guide (Prima)", 2002, 15, 35, 80, "Uncommon"),
        ("Book", "Backyard Sports: The Ultimate Player's Guide", 2003, 20, 45, 100, "Rare"),
        ("Book", "Humongous Entertainment: The History (Fan Publication)", 2010, 25, 50, 120, "Rare"),
        ("Book", "Backyard Baseball 2003 Pocket Guide (BradyGames)", 2002, 10, 25, 60, "Uncommon"),
        ("Book", "Backyard Sports: Complete Character Compendium", 2005, 20, 45, 100, "Rare"),
        ("Book", "Backyard Baseball Tips & Tricks Mini-Guide (Magazine Insert)", 2001, 8, 20, 50, "Uncommon"),
        ("Book", "Backyard Football Playbook (Official Guide)", 2003, 15, 35, 80, "Uncommon"),
        ("Book", "Humongous Entertainment Catalog Booklet (1997-2003 Archive)", 2003, 12, 30, 70, "Uncommon"),
        ("Book", "Backyard Sports Coloring & Activity Book", 2004, 10, 25, 60, "Uncommon"),
        # --- Backyard Sports: Merch & Collectibles ---
        ("Merch", "Pablo Sanchez Rookie Card (Promotional)", 2001, 200, 400, 800, "Grail"),
        ("Merch", "Backyard Baseball Team Pennants Set (Promo)", 1999, 30, 60, 150, "Rare"),
        ("Merch", "Backyard Baseball Mini Bat (Cereal Premium)", 2001, 25, 50, 120, "Rare"),
        ("Merch", "Backyard Sports Lunchbox (Licensed)", 2003, 30, 60, 150, "Rare"),
        ("Merch", "Backyard Baseball Cap (Official Merch)", 2002, 20, 40, 100, "Uncommon"),
        ("Merch", "Backyard Sports Action Figures Set (Unreleased Prototype)", 2004, 300, 500, 1200, "Grail"),
        ("Merch", "Backyard Baseball Mousepad (Promo)", 1998, 20, 40, 100, "Uncommon"),
        ("Merch", "Backyard Football Foam Football (Promo)", 2000, 25, 50, 120, "Rare"),
        ("Merch", "Backyard Soccer Mini Ball (Promo)", 1999, 25, 50, 120, "Rare"),
        ("Merch", "Backyard Baseball Dugout Playset Concept Art Prints", 2002, 40, 80, 200, "Ultra Rare"),
        ("Merch", "Humongous Entertainment Company Shirt (Employee Merch)", 2000, 50, 100, 250, "Ultra Rare"),
        ("Merch", "Backyard Sports Plush Pablo Sanchez", 2003, 40, 80, 200, "Ultra Rare"),
        ("Merch", "Backyard Sports Window Cling Set (Retail Display)", 2001, 15, 30, 80, "Uncommon"),
        ("Merch", "Backyard Sports Temporary Tattoos Sheet (Cereal Premium)", 2002, 10, 25, 60, "Common"),
        ("Merch", "Backyard Baseball Iron-On Patch Set", 2001, 15, 35, 90, "Uncommon"),
        ("Merch", "Backyard Sports Keychain Set (6-Pack)", 2003, 20, 40, 100, "Uncommon"),
        ("Merch", "Backyard Baseball Signed by Creator Ron Gilbert", 1997, 300, 500, 1500, "Grail"),
        ("Merch", "Humongous Entertainment Press Kit Folder", 1997, 80, 160, 400, "Ultra Rare"),
        ("Merch", "Backyard Baseball E3 Exclusive Poster", 1997, 60, 120, 300, "Ultra Rare"),
        ("Merch", "Backyard Sports Retail Standee (Cardboard Display)", 2003, 50, 100, 250, "Ultra Rare"),
        # --- Backyard Sports: Big Box Variants ---
        ("PC", "Backyard Baseball (Original Tall Box)", 1997, 80, 200, 800, "Grail"),
        ("PC", "Backyard Baseball (Jewel Case Re-Release)", 1999, 15, 40, 120, "Common"),
        ("PC", "Backyard Baseball (Budget 'Fun Pack' Re-Release)", 2001, 10, 25, 80, "Common"),
        ("PC", "Backyard Baseball 2001 (Big Box Original)", 2000, 50, 130, 400, "Rare"),
        ("PC", "Backyard Baseball 2001 (Jewel Case Re-Release)", 2001, 12, 30, 100, "Common"),
        ("PC", "Backyard Soccer (Original Tall Box)", 1998, 60, 160, 500, "Ultra Rare"),
        ("PC", "Backyard Soccer (Budget Re-Release)", 2001, 10, 25, 80, "Common"),
        ("PC", "Backyard Football (Original Tall Box)", 1999, 60, 160, 500, "Ultra Rare"),
        ("PC", "Backyard Football (Budget Re-Release)", 2001, 10, 25, 80, "Common"),
        ("PC", "Backyard Basketball (Original Tall Box)", 2001, 45, 120, 380, "Rare"),
        ("PC", "Backyard Hockey (Original Tall Box)", 2002, 45, 120, 380, "Rare"),
        ("PC", "Backyard Skateboarding (Original Tall Box)", 2004, 35, 90, 300, "Rare"),
        ("PC", "Backyard Baseball 2003 (Big Box with Holographic Cover)", 2002, 60, 150, 450, "Ultra Rare"),
        ("PC", "Backyard Baseball 2005 (Last Big Box Release)", 2004, 40, 100, 320, "Rare"),
        ("PC", "Backyard Sports Bundle Box (Cardboard Multi-Game Package)", 2005, 50, 130, 400, "Rare"),
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

    # ── Batch: Saturn, Neo Geo AES, TG-16, Jaguar, 3DO, CIB variants (55 items) ──
    items += _additional_retro_2025_expansion()

    # ── Wave 2: More sealed, CIB, console variants, handheld, Dreamcast, PS1/PS2 ──
    items += _wave2_retro_expansion()

    # ── Wave 3: Switch rarities, JP exclusives, arcade, GB/GBA, PS2/PS3, PC big box ──
    items += _wave3_retro_expansion()

    # ── Wave 4: Most-searched titles, sealed grails, GameCube rarities, SNES CIB ──
    items += _wave4_retro_expansion()

    # Deduplicate by ('platform', 'name') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in items:
        _key = (item["platform"], item["name"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)

    # Deduplicate by name (keep first occurrence)
    seen_names: set[str] = set()
    deduped: list[dict] = []
    for item in _deduped:
        key = item.get("name", "")
        if key not in seen_names:
            seen_names.add(key)
            deduped.append(item)

    return deduped


def _wave2_retro_expansion() -> list[dict]:
    """Wave 2 — ~125 items: sealed grails, CIB RPGs, console variants,
    handheld games, Dreamcast, more PS1/PS2, arcade PCBs."""
    items = []

    # ── N64 Sealed Grails ──────────────────────────────────────────
    n64_sealed = [
        ("N64", "Super Mario 64 (Sealed)", 1996, 500, 2000, 15000, "Grail"),
        ("N64", "The Legend of Zelda: Ocarina of Time (Sealed)", 1998, 400, 1500, 12000, "Grail"),
        ("N64", "GoldenEye 007 (Sealed)", 1997, 300, 1000, 8000, "Grail"),
        ("N64", "Mario Kart 64 (Sealed)", 1997, 250, 800, 6000, "Rare"),
        ("N64", "Super Smash Bros. (Sealed)", 1999, 300, 1000, 7000, "Rare"),
        ("N64", "Conker's Bad Fur Day (Sealed)", 2001, 500, 1500, 10000, "Grail"),
        ("N64", "Paper Mario (Sealed)", 2001, 300, 800, 5000, "Rare"),
        ("N64", "Banjo-Kazooie (Sealed)", 1998, 200, 600, 4000, "Rare"),
    ]

    # ── SNES Sealed Grails ─────────────────────────────────────────
    snes_sealed = [
        ("SNES", "Earthbound (Sealed, Big Box)", 1995, 800, 3000, 20000, "Grail"),
        ("SNES", "Chrono Trigger (Sealed)", 1995, 600, 2000, 15000, "Grail"),
        ("SNES", "Final Fantasy III (Sealed)", 1994, 400, 1200, 8000, "Grail"),
        ("SNES", "Secret of Mana (Sealed)", 1993, 300, 800, 5000, "Rare"),
        ("SNES", "Mega Man X (Sealed)", 1994, 300, 800, 5000, "Rare"),
        ("SNES", "Super Metroid (Sealed)", 1994, 400, 1500, 10000, "Grail"),
        ("SNES", "Contra III: The Alien Wars (Sealed)", 1992, 200, 600, 4000, "Rare"),
        ("SNES", "Donkey Kong Country 2 (Sealed)", 1995, 150, 400, 3000, "Rare"),
    ]

    # ── CIB RPG Grails ─────────────────────────────────────────────
    cib_rpgs = [
        ("SNES", "Earthbound (CIB with Guide)", 1995, 500, 2000, 0, "Grail"),
        ("SNES", "Chrono Trigger (CIB)", 1995, 300, 800, 0, "Rare"),
        ("SNES", "Final Fantasy II (CIB with Map)", 1991, 150, 400, 0, "Uncommon"),
        ("SNES", "Breath of Fire II (CIB)", 1995, 100, 280, 0, "Uncommon"),
        ("N64", "The Legend of Zelda: Majora's Mask (CIB Collector's Edition)", 2000, 200, 500, 0, "Rare"),
        ("N64", "Ogre Battle 64 (CIB)", 2000, 150, 350, 0, "Uncommon"),
        ("N64", "Harvest Moon 64 (CIB)", 1999, 150, 400, 0, "Uncommon"),
    ]

    # ── Console Variants ───────────────────────────────────────────
    console_variants = [
        ("N64", "Pikachu N64 Console (CIB)", 2000, 300, 600, 1500, "Rare"),
        ("N64", "Funtastic Ice Blue N64 Console (CIB)", 1999, 200, 450, 1000, "Rare"),
        ("N64", "Funtastic Grape Purple N64 Console (CIB)", 1999, 200, 400, 900, "Rare"),
        ("N64", "Funtastic Fire Orange N64 Console (CIB)", 1999, 180, 380, 850, "Uncommon"),
        ("Xbox", "Halo Edition Xbox Console (CIB)", 2002, 200, 500, 1200, "Rare"),
        ("Xbox", "Halo 3 Edition Xbox 360 Console (CIB)", 2007, 150, 350, 800, "Uncommon"),
        ("GameCube", "Panasonic Q Console (CIB)", 2001, 500, 1200, 3000, "Grail"),
        ("GameCube", "Char's Customized GameCube (CIB, Japan)", 2002, 400, 900, 2000, "Rare"),
        ("PlayStation", "PSone LCD Screen Bundle (CIB)", 2000, 100, 250, 600, "Uncommon"),
        ("Game Boy", "Game Boy Light (Silver, CIB, Japan)", 1998, 200, 500, 1200, "Rare"),
        ("Game Boy", "Game Boy Micro (Famicom Edition, CIB)", 2005, 150, 400, 1000, "Rare"),
    ]

    # ── Game Boy Color / GBA Games ─────────────────────────────────
    handheld_games = [
        ("Game Boy Color", "Pokemon Crystal (CIB)", 2001, 80, 250, 800, "Uncommon"),
        ("Game Boy Color", "The Legend of Zelda: Oracle of Ages (CIB)", 2001, 60, 150, 500, "Uncommon"),
        ("Game Boy Color", "The Legend of Zelda: Oracle of Seasons (CIB)", 2001, 60, 150, 500, "Uncommon"),
        ("Game Boy Color", "Shantae (Loose)", 2002, 400, 1000, 3000, "Grail"),
        ("Game Boy Color", "Metal Gear Solid (CIB)", 2000, 50, 120, 400, "Uncommon"),
        ("Game Boy Color", "Dragon Warrior III (CIB)", 2001, 80, 200, 600, "Uncommon"),
        ("GBA", "Pokemon FireRed (CIB)", 2004, 60, 180, 500, "Uncommon"),
        ("GBA", "Pokemon Emerald (CIB)", 2005, 100, 300, 800, "Rare"),
        ("GBA", "The Legend of Zelda: The Minish Cap (CIB)", 2005, 80, 200, 600, "Uncommon"),
        ("GBA", "Fire Emblem (CIB)", 2003, 80, 200, 600, "Uncommon"),
        ("GBA", "Fire Emblem: The Sacred Stones (CIB)", 2005, 60, 150, 450, "Uncommon"),
        ("GBA", "Castlevania: Aria of Sorrow (CIB)", 2003, 80, 250, 700, "Rare"),
        ("GBA", "Metroid Fusion (CIB)", 2002, 50, 120, 350, "Uncommon"),
        ("GBA", "Mega Man Zero Collection (CIB)", 2004, 40, 100, 300, "Common"),
        ("GBA", "Mother 3 (CIB, Japan)", 2006, 60, 150, 400, "Uncommon"),
    ]

    # ── Dreamcast Games ────────────────────────────────────────────
    dreamcast_games = [
        ("Dreamcast", "Shenmue (CIB)", 2000, 30, 60, 200, "Common"),
        ("Dreamcast", "Shenmue II (CIB)", 2001, 40, 80, 250, "Common"),
        ("Dreamcast", "Sonic Adventure (CIB)", 1999, 25, 50, 150, "Common"),
        ("Dreamcast", "Jet Set Radio (CIB)", 2000, 40, 80, 250, "Common"),
        ("Dreamcast", "Crazy Taxi (CIB)", 2000, 15, 30, 100, "Common"),
        ("Dreamcast", "Power Stone 2 (CIB)", 2000, 80, 200, 500, "Rare"),
        ("Dreamcast", "Skies of Arcadia (CIB)", 2000, 100, 250, 600, "Rare"),
        ("Dreamcast", "Marvel vs Capcom 2 (CIB)", 2000, 150, 350, 800, "Rare"),
        ("Dreamcast", "Ikaruga (CIB)", 2002, 80, 200, 500, "Rare"),
        ("Dreamcast", "Giga Wing 2 (CIB)", 2001, 100, 250, 600, "Rare"),
        ("Dreamcast", "Bangai-O (CIB)", 2000, 120, 280, 700, "Rare"),
        ("Dreamcast", "Project Justice (CIB)", 2001, 100, 250, 600, "Rare"),
    ]

    # ── PS1 RPGs ───────────────────────────────────────────────────
    ps1_games = [
        ("PS1", "Final Fantasy VII (CIB, Black Label)", 1997, 40, 100, 400, "Uncommon"),
        ("PS1", "Final Fantasy Tactics (CIB)", 1998, 30, 80, 300, "Common"),
        ("PS1", "Suikoden II (CIB)", 1999, 200, 500, 1200, "Grail"),
        ("PS1", "Vagrant Story (CIB)", 2000, 50, 120, 350, "Uncommon"),
        ("PS1", "Xenogears (CIB)", 1998, 60, 150, 500, "Uncommon"),
        ("PS1", "Parasite Eve (CIB)", 1998, 40, 100, 300, "Uncommon"),
        ("PS1", "Legend of Mana (CIB)", 2000, 50, 120, 400, "Uncommon"),
        ("PS1", "Brave Fencer Musashi (CIB)", 1998, 40, 100, 300, "Uncommon"),
        ("PS1", "Star Ocean: The Second Story (CIB)", 1999, 40, 100, 300, "Uncommon"),
        ("PS1", "Tail Concerto (CIB)", 1999, 100, 250, 600, "Rare"),
    ]

    # ── PS2 RPGs ───────────────────────────────────────────────────
    ps2_games = [
        ("PS2", "Persona 3 FES (CIB)", 2008, 40, 80, 200, "Uncommon"),
        ("PS2", "Persona 4 (CIB)", 2008, 30, 60, 150, "Common"),
        ("PS2", ".hack//Quarantine (CIB)", 2003, 150, 350, 800, "Rare"),
        ("PS2", ".hack//Mutation (CIB)", 2003, 30, 60, 150, "Common"),
        ("PS2", "Xenosaga Episode III (CIB)", 2006, 80, 200, 500, "Rare"),
        ("PS2", "Rule of Rose (CIB)", 2006, 300, 700, 1500, "Grail"),
        ("PS2", "Haunting Ground (CIB)", 2005, 150, 400, 900, "Rare"),
        ("PS2", "Kuon (CIB)", 2004, 200, 500, 1200, "Grail"),
        ("PS2", "Shadow Hearts: Covenant (CIB)", 2004, 40, 80, 200, "Uncommon"),
        ("PS2", "Odin Sphere (CIB)", 2007, 25, 50, 120, "Common"),
    ]

    # ── Arcade PCBs ────────────────────────────────────────────────
    arcade_pcbs = [
        ("Arcade", "CPS2 Street Fighter III: 3rd Strike PCB", 1999, 500, 0, 0, "Rare"),
        ("Arcade", "CPS2 Super Street Fighter II Turbo PCB", 1994, 300, 0, 0, "Uncommon"),
        ("Arcade", "MVS Metal Slug 3 Cart", 2000, 400, 0, 0, "Rare"),
        ("Arcade", "MVS Garou: Mark of the Wolves Cart", 1999, 500, 0, 0, "Rare"),
        ("Arcade", "Naomi Ikaruga GD-ROM", 2002, 300, 0, 0, "Rare"),
        ("Arcade", "CPS3 JoJo's Bizarre Adventure PCB", 1999, 400, 0, 0, "Rare"),
        ("Arcade", "Sega ST-V Radiant Silvergun Cart", 1998, 600, 0, 0, "Grail"),
        ("Arcade", "CPS2 Vampire Savior PCB", 1997, 350, 0, 0, "Uncommon"),
    ]

    # ── More Neo Geo AES ───────────────────────────────────────────
    neogeo_extra = [
        ("Neo Geo AES", "Matrimelee", 2003, 800, 1500, 3500, "Grail"),
        ("Neo Geo AES", "Rage of the Dragons", 2002, 400, 800, 2000, "Rare"),
        ("Neo Geo AES", "Shock Troopers 2nd Squad", 1998, 350, 700, 1800, "Rare"),
        ("Neo Geo AES", "Windjammers", 1994, 300, 600, 1500, "Rare"),
    ]

    # ── More Saturn ────────────────────────────────────────────────
    saturn_extra = [
        ("Saturn", "Albert Odyssey: Legend of Eldean", 1997, 150, 350, 800, "Rare"),
        ("Saturn", "Magic Knight Rayearth", 1998, 200, 500, 1200, "Rare"),
        ("Saturn", "Astal", 1995, 60, 140, 400, "Uncommon"),
        ("Saturn", "Fighters Megamix", 1997, 20, 50, 150, "Common"),
    ]

    # ── More Dreamcast (additional) ────────────────────────────────
    dreamcast_extra = [
        ("Dreamcast", "Street Fighter III: 3rd Strike (CIB)", 2000, 50, 120, 300, "Uncommon"),
        ("Dreamcast", "Grandia II (CIB)", 2000, 25, 50, 150, "Common"),
        ("Dreamcast", "Soul Calibur (CIB)", 1999, 15, 30, 100, "Common"),
        ("Dreamcast", "Rez (CIB)", 2001, 60, 150, 400, "Uncommon"),
        ("Dreamcast", "Seaman (CIB with Mic)", 2000, 30, 70, 200, "Uncommon"),
        ("Dreamcast", "Tech Romancer (CIB)", 2000, 80, 200, 500, "Rare"),
    ]

    # ── More PS1 (additional) ──────────────────────────────────────
    ps1_extra = [
        ("PS1", "Castlevania: Symphony of the Night (CIB)", 1997, 60, 150, 500, "Uncommon"),
        ("PS1", "Mega Man Legends 2 (CIB)", 2000, 80, 200, 600, "Rare"),
        ("PS1", "Tomba! (CIB)", 1998, 100, 250, 700, "Rare"),
        ("PS1", "Tomba! 2 (CIB)", 1999, 80, 200, 600, "Rare"),
        ("PS1", "Klonoa: Door to Phantomile (CIB)", 1998, 150, 400, 1000, "Rare"),
        ("PS1", "Valkyrie Profile (CIB)", 2000, 80, 200, 600, "Rare"),
        ("PS1", "Alundra (CIB)", 1998, 40, 100, 300, "Uncommon"),
        ("PS1", "Wild Arms 2 (CIB)", 2000, 30, 80, 250, "Common"),
    ]

    # ── More PS2 (additional) ──────────────────────────────────────
    ps2_extra = [
        ("PS2", "Ico (CIB)", 2001, 15, 30, 80, "Common"),
        ("PS2", "Shadow of the Colossus (CIB)", 2005, 15, 30, 80, "Common"),
        ("PS2", "Suikoden V (CIB)", 2006, 60, 150, 400, "Rare"),
        ("PS2", "Radiata Stories (CIB)", 2005, 30, 70, 200, "Uncommon"),
        ("PS2", "Ar Tonelico II (CIB)", 2009, 50, 120, 300, "Rare"),
        ("PS2", "Gitaroo Man (CIB)", 2002, 60, 150, 400, "Rare"),
    ]

    # ── Game Boy (original) ────────────────────────────────────────
    gb_games = [
        ("Game Boy", "Pokemon Red (CIB)", 1996, 50, 200, 800, "Rare"),
        ("Game Boy", "Pokemon Blue (CIB)", 1996, 50, 200, 800, "Rare"),
        ("Game Boy", "Pokemon Yellow (CIB)", 1998, 40, 150, 600, "Uncommon"),
        ("Game Boy", "The Legend of Zelda: Link's Awakening (CIB)", 1993, 30, 80, 300, "Uncommon"),
        ("Game Boy", "Tetris (CIB)", 1989, 15, 40, 150, "Common"),
        ("Game Boy", "Super Mario Land 2 (CIB)", 1992, 20, 50, 200, "Common"),
        ("Game Boy", "Kirby's Dream Land (CIB)", 1992, 15, 40, 150, "Common"),
        ("Game Boy", "Metroid II: Return of Samus (CIB)", 1991, 25, 60, 200, "Common"),
    ]

    # ── NES Additional ──────────────────────────────────────────────
    nes_extra = [
        ("NES", "Little Samson (Loose)", 1992, 800, 2000, 5000, "Grail"),
        ("NES", "Stadium Events (Loose)", 1987, 10000, 30000, 100000, "Grail"),
        ("NES", "Bonk's Adventure (CIB)", 1994, 300, 700, 1500, "Rare"),
        ("NES", "Panic Restaurant (Loose)", 1992, 400, 1000, 2500, "Grail"),
        ("NES", "Snow Brothers (CIB)", 1991, 300, 800, 2000, "Rare"),
        ("NES", "Flintstones: Surprise at Dinosaur Peak (Loose)", 1994, 600, 1500, 4000, "Grail"),
    ]

    # ── DS / 3DS Collectible ─────────────────────────────────────
    ds_games = [
        ("DS", "Pokemon HeartGold (CIB with Pokewalker)", 2010, 80, 250, 600, "Rare"),
        ("DS", "Pokemon SoulSilver (CIB with Pokewalker)", 2010, 80, 250, 600, "Rare"),
        ("DS", "Chrono Trigger DS (CIB)", 2008, 40, 100, 250, "Uncommon"),
        ("DS", "Dragon Quest IX (CIB)", 2010, 20, 50, 120, "Common"),
        ("3DS", "Pokemon Ultra Sun (CIB)", 2017, 30, 60, 150, "Common"),
    ]

    all_games = (n64_sealed + snes_sealed + cib_rpgs + handheld_games
                 + dreamcast_games + ps1_games + ps2_games + neogeo_extra + saturn_extra
                 + dreamcast_extra + ps1_extra + ps2_extra + gb_games + nes_extra + ds_games)
    for platform, title, year, loose, cib, sealed, rarity in all_games:
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

    for platform, title, year, loose, cib, sealed, rarity in console_variants:
        items.append({
            "type": "console",
            "platform": platform,
            "maker": platform.split()[0] if platform else "",
            "name": title,
            "year": year,
            "price_loose": loose,
            "price_cib": cib,
            "price_sealed": sealed,
            "rarity": rarity,
        })

    for platform, title, year, price, _, _, rarity in arcade_pcbs:
        items.append({
            "type": "game",
            "platform": platform,
            "name": title,
            "year": year,
            "price_loose": price,
            "price_cib": 0,
            "price_sealed": 0,
            "rarity": rarity,
        })

    return items


def _wave3_retro_expansion() -> list[dict]:
    """Wave 3 — ~80 items: Switch rarities, JP exclusives, arcade boards,
    Dreamcast/Saturn, GB/GBA, PS2/PS3, PC big box."""
    items = []

    # ── Nintendo Switch Rarities ─────────────────────────────────
    switch_games = [
        ("Switch", "Bayonetta 1 Physical (JP Import)", 2018, 80, 150, 350, "Rare"),
        ("Switch", "Xenoblade Chronicles 2 Special Edition", 2017, 100, 250, 600, "Rare"),
        ("Switch", "Fire Emblem Three Houses Seasons of Warfare Ed.", 2019, 80, 180, 400, "Uncommon"),
        ("Switch", "Metroid Dread Special Edition", 2021, 60, 120, 300, "Uncommon"),
        ("Switch", "Metroid Dread Collector's Edition (EU)", 2021, 100, 220, 500, "Rare"),
        ("Switch", "Astral Chain Collector's Edition", 2019, 80, 180, 400, "Uncommon"),
        ("Switch", "Ring Fit Adventure (CIB)", 2019, 40, 70, 150, "Common"),
        ("Switch", "Pokemon Legends: Arceus (Steelbook)", 2022, 40, 80, 180, "Common"),
        ("Switch", "Octopath Traveler Wayfarer's Edition", 2018, 60, 130, 300, "Uncommon"),
        ("Switch", "Xenoblade Chronicles 3 Special Edition", 2022, 80, 180, 400, "Uncommon"),
        ("Switch", "Bayonetta 3 Trinity Masquerade Edition", 2022, 60, 120, 280, "Uncommon"),
        ("Switch", "No More Heroes III (Limited Run #136)", 2022, 70, 150, 350, "Rare"),
        ("Switch", "Celeste (Limited Run Physical)", 2019, 80, 200, 500, "Rare"),
        ("Switch", "Hollow Knight Physical (Fangamer)", 2019, 50, 120, 300, "Uncommon"),
        ("Switch", "Return of the Obra Dinn (Limited Run)", 2021, 50, 100, 250, "Uncommon"),
    ]

    # ── Japanese Exclusives ──────────────────────────────────────
    jp_exclusives = [
        ("SNES", "Treasure Hunter G (JP)", 1996, 20, 50, 150, "Uncommon"),
        ("SNES", "Bahamut Lagoon (JP)", 1996, 15, 40, 120, "Common"),
        ("SNES", "Seiken Densetsu 3 (JP)", 1995, 25, 60, 200, "Uncommon"),
        ("SNES", "Star Ocean (JP SFC)", 1996, 20, 50, 150, "Common"),
        ("SNES", "Rendering Ranger R2 (JP)", 1995, 500, 1000, 2500, "Grail"),
        ("N64", "Sin & Punishment (JP)", 2000, 30, 70, 200, "Uncommon"),
        ("N64", "Custom Robo V2 (JP)", 2000, 15, 35, 100, "Common"),
        ("N64", "Bangai-O (JP N64)", 1999, 40, 100, 300, "Uncommon"),
        ("PS1", "Vib-Ribbon (JP)", 1999, 30, 60, 180, "Uncommon"),
        ("PS1", "LSD: Dream Emulator (JP)", 1998, 150, 350, 800, "Grail"),
        ("PS1", "Harmful Park (JP)", 1997, 120, 250, 600, "Rare"),
        ("Saturn", "Radiant Silvergun (JP)", 1998, 150, 350, 800, "Rare"),
        ("Saturn", "Princess Crown (JP)", 1997, 60, 130, 350, "Uncommon"),
        ("Game Boy", "For the Frog the Bell Tolls (JP)", 1992, 20, 50, 150, "Uncommon"),
        ("Game Boy", "Kaeru no Tame ni Kane wa Naru (JP CIB)", 1992, 40, 100, 300, "Uncommon"),
    ]

    # ── Arcade Boards & Cabinets ─────────────────────────────────
    arcade_extra = [
        ("Arcade", "CPS2 Marvel vs Capcom PCB", 1998, 600, 0, 0, "Rare"),
        ("Arcade", "CPS2 X-Men vs Street Fighter PCB", 1996, 400, 0, 0, "Rare"),
        ("Arcade", "MVS Samurai Shodown II Cart", 1994, 150, 0, 0, "Uncommon"),
        ("Arcade", "MVS King of Fighters '98 Cart", 1998, 200, 0, 0, "Uncommon"),
        ("Arcade", "MVS Blazing Star Cart", 1998, 250, 0, 0, "Rare"),
        ("Arcade", "Sega Naomi Marvel vs Capcom 2 GD-ROM", 2000, 500, 0, 0, "Rare"),
        ("Arcade", "Sega Naomi Crazy Taxi GD-ROM", 1999, 200, 0, 0, "Uncommon"),
        ("Arcade", "CPS3 Street Fighter III: 2nd Impact PCB", 1997, 400, 0, 0, "Rare"),
        ("Arcade", "MVS Last Blade 2 Cart", 1998, 300, 0, 0, "Rare"),
        ("Arcade", "Taito F3 Darius Gaiden PCB", 1994, 350, 0, 0, "Rare"),
    ]

    # ── Sega Dreamcast / Saturn (additional) ─────────────────────
    dc_saturn_extra = [
        ("Dreamcast", "House of the Dead 2 (CIB)", 1999, 20, 40, 120, "Common"),
        ("Dreamcast", "Space Channel 5 (CIB)", 2000, 15, 30, 100, "Common"),
        ("Dreamcast", "Phantasy Star Online (CIB)", 2001, 25, 50, 150, "Common"),
        ("Dreamcast", "Dynamite Cop (CIB)", 1999, 25, 60, 180, "Uncommon"),
        ("Dreamcast", "Under Defeat (CIB, JP)", 2006, 80, 200, 500, "Rare"),
        ("Saturn", "Burning Rangers (CIB)", 1998, 200, 450, 1100, "Rare"),
        ("Saturn", "Dragon Force (CIB)", 1996, 100, 220, 600, "Uncommon"),
        ("Saturn", "Panzer Dragoon Saga (CIB)", 1998, 600, 1200, 3200, "Grail"),
        ("Saturn", "Shining Force III Scenario 2 (JP)", 1998, 80, 180, 450, "Uncommon"),
        ("Saturn", "Shining Force III Scenario 3 (JP)", 1998, 100, 220, 550, "Rare"),
    ]

    # ── Game Boy / GBA (additional) ──────────────────────────────
    gb_gba_extra = [
        ("Game Boy", "Pokemon Pinball (CIB)", 1999, 20, 50, 150, "Common"),
        ("Game Boy", "Kirby's Pinball Land (CIB)", 1993, 10, 30, 100, "Common"),
        ("Game Boy Color", "Pokemon Trading Card Game (CIB)", 2000, 20, 60, 200, "Common"),
        ("Game Boy Color", "Wario Land 3 (CIB)", 2000, 20, 50, 150, "Common"),
        ("Game Boy Color", "Survival Kids (CIB)", 1999, 40, 100, 300, "Uncommon"),
        ("GBA", "Castlevania: Circle of the Moon (CIB)", 2001, 30, 70, 200, "Common"),
        ("GBA", "Golden Sun (CIB)", 2001, 30, 80, 250, "Common"),
        ("GBA", "Golden Sun: The Lost Age (CIB)", 2003, 40, 100, 300, "Uncommon"),
        ("GBA", "Drill Dozer (CIB)", 2005, 60, 150, 400, "Rare"),
        ("GBA", "Riviera: The Promised Land (CIB)", 2005, 40, 100, 280, "Uncommon"),
    ]

    # ── PS2/PS3 Rarities (additional) ────────────────────────────
    ps2_ps3_extra = [
        ("PS2", "Silent Hill 2 (CIB, Black Label)", 2001, 80, 200, 600, "Rare"),
        ("PS2", ".hack//Infection (CIB)", 2003, 20, 40, 100, "Common"),
        ("PS2", ".hack//Outbreak (CIB)", 2003, 40, 80, 200, "Uncommon"),
        ("PS2", ".hack//Quarantine Complete (CIB w/ DVD)", 2003, 200, 450, 1000, "Grail"),
        ("PS2", "Michigan: Report from Hell (PAL, CIB)", 2004, 60, 150, 400, "Rare"),
        ("PS3", "Folklore (CIB)", 2007, 30, 60, 150, "Uncommon"),
        ("PS3", "Demon's Souls Black Phantom Edition (EU)", 2010, 80, 200, 500, "Rare"),
        ("PS3", "3D Dot Game Heroes (CIB)", 2010, 25, 50, 120, "Common"),
        ("PS3", "Puppeteer (CIB)", 2013, 30, 60, 150, "Uncommon"),
        ("PS3", "Ni no Kuni Wizard's Edition (CIB)", 2013, 80, 180, 400, "Rare"),
    ]

    # ── PC Big Box Games ─────────────────────────────────────────
    pc_bigbox = [
        ("PC", "Baldur's Gate Big Box (CIB)", 1998, 40, 120, 350, "Uncommon"),
        ("PC", "Baldur's Gate II: Shadows of Amn Big Box", 2000, 30, 100, 300, "Uncommon"),
        ("PC", "Ultima VII: The Black Gate Big Box", 1992, 80, 200, 600, "Rare"),
        ("PC", "Ultima Underworld Big Box", 1992, 60, 150, 450, "Rare"),
        ("PC", "Wing Commander Big Box", 1990, 40, 120, 350, "Uncommon"),
        ("PC", "Wing Commander III Big Box", 1994, 30, 80, 250, "Uncommon"),
        ("PC", "System Shock Big Box", 1994, 100, 250, 700, "Rare"),
        ("PC", "Planescape: Torment Big Box (CIB)", 1999, 60, 180, 500, "Rare"),
        ("PC", "Diablo Big Box (CIB)", 1997, 40, 120, 350, "Uncommon"),
        ("PC", "Fallout Big Box (CIB)", 1997, 50, 150, 400, "Rare"),
    ]

    all_games = (switch_games + jp_exclusives + arcade_extra + dc_saturn_extra
                 + gb_gba_extra + ps2_ps3_extra + pc_bigbox)
    for platform, title, year, loose, cib, sealed, rarity in all_games:
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


def _wave4_retro_expansion() -> list[dict]:
    """Wave 4 — ~190 items: most-searched titles, sealed grails, GameCube
    rarities, SNES CIB keys, Sega CD, N64, PS1/PS2 RPG grails."""
    items = []

    # ── SNES — Most Searched CIB/Sealed ────────────────────────────
    snes_keys = [
        ("SNES", "EarthBound CIB", 1995, 800, 2000, 5000, "Grail"),
        ("SNES", "EarthBound Sealed (VGA 85+)", 1995, 0, 0, 15000, "Grail"),
        ("SNES", "Chrono Trigger CIB", 1995, 200, 500, 1500, "Rare"),
        ("SNES", "Chrono Trigger Sealed", 1995, 0, 0, 5000, "Grail"),
        ("SNES", "Super Metroid CIB", 1994, 150, 350, 1000, "Rare"),
        ("SNES", "Super Metroid Sealed", 1994, 0, 0, 3500, "Grail"),
        ("SNES", "Mega Man X CIB", 1993, 100, 250, 800, "Uncommon"),
        ("SNES", "Mega Man X Sealed", 1993, 0, 0, 2500, "Rare"),
        ("SNES", "Mega Man X2 CIB", 1994, 200, 500, 1500, "Rare"),
        ("SNES", "Mega Man X3 CIB", 1995, 500, 1200, 3500, "Grail"),
        ("SNES", "Final Fantasy III (VI) CIB", 1994, 100, 250, 800, "Uncommon"),
        ("SNES", "Final Fantasy II (IV) CIB", 1991, 80, 200, 600, "Uncommon"),
        ("SNES", "Secret of Mana CIB", 1993, 80, 200, 600, "Uncommon"),
        ("SNES", "Secret of Mana Sealed", 1993, 0, 0, 2000, "Rare"),
        ("SNES", "Secret of Evermore CIB", 1995, 60, 150, 400, "Uncommon"),
        ("SNES", "Illusion of Gaia CIB", 1994, 40, 100, 300, "Common"),
        ("SNES", "Terranigma CIB (PAL)", 1996, 250, 600, 1500, "Grail"),
        ("SNES", "Super Castlevania IV CIB", 1991, 80, 200, 550, "Uncommon"),
        ("SNES", "Contra III The Alien Wars CIB", 1992, 80, 180, 500, "Uncommon"),
        ("SNES", "ActRaiser CIB", 1991, 50, 130, 350, "Uncommon"),
        ("SNES", "Breath of Fire II CIB", 1994, 60, 150, 400, "Uncommon"),
        ("SNES", "Super Mario RPG CIB", 1996, 100, 250, 700, "Uncommon"),
        ("SNES", "Harvest Moon CIB", 1996, 150, 400, 1000, "Rare"),
        ("SNES", "Wild Guns CIB", 1994, 400, 900, 2500, "Grail"),
        ("SNES", "Pocky & Rocky CIB", 1992, 300, 700, 2000, "Grail"),
        ("SNES", "Pocky & Rocky 2 CIB", 1994, 600, 1200, 3000, "Grail"),
        ("SNES", "Hagane The Final Conflict CIB", 1994, 800, 1800, 4000, "Grail"),
        ("SNES", "Aero Fighters CIB", 1994, 400, 900, 2500, "Grail"),
    ]

    # ── GameCube — Most Searched Rarities ──────────────────────────
    gc_games = [
        ("GameCube", "Gotcha Force", 2003, 300, 600, 1500, "Grail"),
        ("GameCube", "Cubivore Survival of the Fittest", 2002, 250, 500, 1200, "Grail"),
        ("GameCube", "Chibi-Robo!", 2005, 100, 200, 500, "Rare"),
        ("GameCube", "Pokemon Box Ruby & Sapphire", 2003, 200, 400, 1000, "Grail"),
        ("GameCube", "Fire Emblem Path of Radiance CIB", 2005, 150, 300, 800, "Rare"),
        ("GameCube", "Skies of Arcadia Legends CIB", 2003, 120, 250, 600, "Rare"),
        ("GameCube", "Baten Kaitos Origins CIB", 2006, 100, 220, 550, "Rare"),
        ("GameCube", "Baten Kaitos Eternal Wings CIB", 2003, 60, 130, 350, "Uncommon"),
        ("GameCube", "Phantasy Star Online Episode I & II Plus CIB", 2002, 80, 170, 400, "Uncommon"),
        ("GameCube", "Metal Gear Solid The Twin Snakes CIB", 2004, 80, 180, 450, "Uncommon"),
        ("GameCube", "Eternal Darkness Sanity's Requiem CIB", 2002, 60, 140, 350, "Uncommon"),
        ("GameCube", "Paper Mario The Thousand-Year Door CIB", 2004, 80, 180, 450, "Uncommon"),
        ("GameCube", "Mario Kart Double Dash!! CIB", 2003, 50, 100, 250, "Common"),
        ("GameCube", "F-Zero GX CIB", 2003, 50, 120, 300, "Uncommon"),
        ("GameCube", "Ikaruga CIB", 2003, 60, 140, 350, "Uncommon"),
        ("GameCube", "Twilight Princess CIB (GC)", 2006, 80, 180, 400, "Uncommon"),
        ("GameCube", "Resident Evil 2 CIB (GC)", 2003, 80, 170, 400, "Uncommon"),
        ("GameCube", "Resident Evil 3 Nemesis CIB (GC)", 2003, 60, 140, 350, "Uncommon"),
        ("GameCube", "Custom Robo CIB", 2004, 40, 90, 250, "Common"),
        ("GameCube", "Donkey Konga 2 CIB w/ Bongos", 2004, 30, 80, 200, "Common"),
    ]

    # ── PS1 — RPG Grails ──────────────────────────────────────────
    ps1_games = [
        ("PS1", "Suikoden II CIB", 1999, 200, 400, 1000, "Grail"),
        ("PS1", "Suikoden II Sealed", 1999, 0, 0, 3000, "Grail"),
        ("PS1", "Vagrant Story CIB", 2000, 80, 180, 450, "Uncommon"),
        ("PS1", "Valkyrie Profile CIB", 1999, 150, 350, 900, "Rare"),
        ("PS1", "Xenogears CIB", 1998, 80, 180, 500, "Uncommon"),
        ("PS1", "Castlevania SotN CIB (Black Label)", 1997, 80, 200, 500, "Uncommon"),
        ("PS1", "Castlevania SotN Sealed (Black Label)", 1997, 0, 0, 1500, "Grail"),
        ("PS1", "Persona 2 Eternal Punishment CIB", 2000, 100, 250, 600, "Rare"),
        ("PS1", "Lunar Silver Star Story Complete CIB", 1999, 80, 200, 500, "Uncommon"),
        ("PS1", "Lunar 2 Eternal Blue Complete CIB", 2000, 100, 250, 600, "Rare"),
        ("PS1", "Brave Fencer Musashi CIB", 1998, 60, 140, 350, "Uncommon"),
        ("PS1", "Legend of Mana CIB", 2000, 60, 130, 350, "Uncommon"),
        ("PS1", "Parasite Eve CIB", 1998, 40, 100, 250, "Common"),
        ("PS1", "Parasite Eve II CIB", 1999, 60, 130, 350, "Uncommon"),
        ("PS1", "Mega Man Legends CIB", 1997, 50, 120, 300, "Uncommon"),
        ("PS1", "Mega Man Legends 2 CIB", 2000, 100, 250, 600, "Rare"),
        ("PS1", "Tomba! CIB", 1997, 150, 350, 800, "Rare"),
        ("PS1", "Tomba! 2 CIB", 1999, 120, 280, 700, "Rare"),
        ("PS1", "Einhander CIB", 1998, 80, 180, 450, "Uncommon"),
        ("PS1", "R-Type Delta CIB", 1998, 80, 180, 450, "Uncommon"),
    ]

    # ── Sega CD — Rarities ─────────────────────────────────────────
    scd_games = [
        ("Sega CD", "Snatcher CIB", 1994, 400, 800, 2000, "Grail"),
        ("Sega CD", "Lunar The Silver Star CIB", 1993, 80, 200, 500, "Uncommon"),
        ("Sega CD", "Lunar Eternal Blue CIB", 1994, 100, 250, 600, "Rare"),
        ("Sega CD", "Keio Flying Squadron CIB", 1994, 500, 1000, 2500, "Grail"),
        ("Sega CD", "Popful Mail CIB", 1994, 250, 500, 1200, "Grail"),
        ("Sega CD", "Shining Force CD CIB", 1994, 100, 250, 600, "Rare"),
        ("Sega CD", "Sonic CD CIB", 1993, 30, 70, 200, "Common"),
        ("Sega CD", "Night Trap CIB", 1992, 40, 100, 250, "Common"),
    ]

    # ── N64 — Most Searched ────────────────────────────────────────
    n64_games = [
        ("N64", "Conker's Bad Fur Day CIB", 2001, 120, 280, 700, "Rare"),
        ("N64", "Conker's Bad Fur Day Sealed", 2001, 0, 0, 2500, "Grail"),
        ("N64", "Ogre Battle 64 CIB", 2000, 80, 200, 500, "Uncommon"),
        ("N64", "Harvest Moon 64 CIB", 1999, 80, 180, 450, "Uncommon"),
        ("N64", "Paper Mario CIB", 2000, 60, 140, 350, "Uncommon"),
        ("N64", "Mario Party CIB", 1998, 40, 90, 250, "Common"),
        ("N64", "Mario Party 2 CIB", 1999, 50, 120, 300, "Uncommon"),
        ("N64", "Mario Party 3 CIB", 2000, 60, 150, 400, "Uncommon"),
        ("N64", "Banjo-Kazooie CIB", 1998, 30, 80, 200, "Common"),
        ("N64", "Banjo-Tooie CIB", 2000, 40, 100, 250, "Common"),
        ("N64", "Jet Force Gemini CIB", 1999, 20, 50, 150, "Common"),
        ("N64", "Snowboard Kids 2 CIB", 1999, 150, 350, 800, "Rare"),
        ("N64", "Goemon's Great Adventure CIB", 1999, 100, 250, 600, "Rare"),
        ("N64", "Bomberman 64 The Second Attack CIB", 2000, 120, 280, 700, "Rare"),
        ("N64", "Doom 64 CIB", 1997, 40, 90, 250, "Common"),
        ("N64", "Turok Dinosaur Hunter CIB", 1997, 20, 50, 150, "Common"),
        ("N64", "Turok 2 Seeds of Evil CIB", 1998, 15, 40, 120, "Common"),
        ("N64", "ClayFighter 63 1/3 Sculptor's Cut CIB", 1998, 300, 700, 2000, "Grail"),
        ("N64", "Stunt Racer 64 CIB", 2000, 80, 200, 500, "Rare"),
        ("N64", "Worms Armageddon CIB", 1999, 60, 150, 400, "Uncommon"),
    ]

    # ── Neo Geo AES — Additional ───────────────────────────────────
    neogeo_extra = [
        ("Neo Geo AES", "Matrimelee", 2003, 2000, 3500, 7000, "Grail"),
        ("Neo Geo AES", "Kizuna Encounter Super Tag Battle", 1996, 400, 800, 2000, "Rare"),
        ("Neo Geo AES", "Shock Troopers", 1997, 600, 1100, 2800, "Grail"),
        ("Neo Geo AES", "Pulstar", 1995, 500, 1000, 2500, "Grail"),
        ("Neo Geo AES", "Twinkle Star Sprites", 1996, 400, 800, 2000, "Rare"),
    ]

    # ── Sega Saturn — Additional ───────────────────────────────────
    saturn_extra = [
        ("Saturn", "Ikaruga (JP)", 2002, 60, 130, 350, "Uncommon"),
        ("Saturn", "Thunder Force V (JP)", 1997, 40, 100, 250, "Common"),
        ("Saturn", "Bulk Slash (JP)", 1997, 100, 250, 600, "Rare"),
        ("Saturn", "Soukyugurentai (Terra Diver) JP", 1996, 80, 180, 450, "Uncommon"),
        ("Saturn", "Cotton 2 (JP)", 1997, 100, 220, 550, "Rare"),
        ("Saturn", "Silhouette Mirage (JP)", 1997, 50, 120, 300, "Uncommon"),
        ("Saturn", "Astal CIB", 1995, 60, 140, 350, "Uncommon"),
        ("Saturn", "Sonic R CIB", 1997, 40, 100, 250, "Common"),
    ]

    # ── PS2 — Sought-After RPGs & Rarities ────────────────────────
    ps2_games = [
        ("PS2", "Rule of Rose CIB", 2006, 300, 600, 1500, "Grail"),
        ("PS2", "Haunting Ground CIB", 2005, 200, 400, 1000, "Grail"),
        ("PS2", "Kuon CIB", 2004, 250, 500, 1200, "Grail"),
        ("PS2", ".hack Vol 1 Infection CIB", 2002, 30, 60, 150, "Common"),
        ("PS2", ".hack Vol 4 Quarantine CIB", 2003, 150, 350, 800, "Rare"),
        ("PS2", ".hack//G.U. Vol 3 Redemption CIB", 2007, 40, 90, 250, "Common"),
        ("PS2", "Xenosaga Episode III CIB", 2006, 80, 180, 450, "Uncommon"),
        ("PS2", "Suikoden V CIB", 2006, 60, 140, 350, "Uncommon"),
        ("PS2", "Persona 3 FES CIB", 2007, 40, 80, 200, "Common"),
        ("PS2", "Persona 4 CIB", 2008, 30, 60, 150, "Common"),
        ("PS2", "Shadow Hearts Covenant CIB", 2004, 50, 120, 300, "Uncommon"),
        ("PS2", "Digital Devil Saga 2 CIB", 2005, 40, 90, 250, "Common"),
    ]

    # ── Dreamcast — Must-Search ────────────────────────────────────
    dc_extra = [
        ("Dreamcast", "Ikaruga CIB (JP)", 2001, 60, 130, 350, "Uncommon"),
        ("Dreamcast", "Project Justice CIB", 2001, 80, 180, 450, "Uncommon"),
        ("Dreamcast", "Mars Matrix CIB", 2001, 80, 180, 450, "Uncommon"),
        ("Dreamcast", "Giga Wing CIB", 2000, 60, 140, 350, "Uncommon"),
        ("Dreamcast", "Under Defeat (JP)", 2005, 80, 180, 450, "Uncommon"),
        ("Dreamcast", "Border Down (JP)", 2003, 120, 280, 700, "Rare"),
        ("Dreamcast", "Last Hope Pink Bullets", 2009, 150, 350, 800, "Rare"),
        ("Dreamcast", "Sturmwind", 2013, 60, 140, 350, "Uncommon"),
    ]

    # ── Game Boy / GBA — Most Searched ──────────────────────────
    gb_gba_games = [
        ("Game Boy", "Pokemon Red/Blue (Sealed)", 1998, 0, 0, 3000, "Grail"),
        ("Game Boy", "Pokemon Yellow CIB", 1998, 40, 100, 300, "Uncommon"),
        ("Game Boy", "Tetris CIB (Original)", 1989, 15, 40, 120, "Common"),
        ("Game Boy", "Mega Man V CIB", 1994, 200, 500, 1200, "Grail"),
        ("Game Boy", "Kid Dracula CIB", 1993, 300, 700, 1800, "Grail"),
        ("GBA", "Pokemon Emerald CIB", 2004, 100, 250, 600, "Rare"),
        ("GBA", "Pokemon FireRed CIB", 2004, 60, 150, 350, "Uncommon"),
        ("GBA", "Fire Emblem CIB", 2003, 80, 200, 500, "Uncommon"),
        ("GBA", "Fire Emblem Sacred Stones CIB", 2004, 50, 130, 300, "Uncommon"),
        ("GBA", "Castlevania Aria of Sorrow CIB", 2003, 80, 200, 500, "Uncommon"),
        ("GBA", "Castlevania Circle of the Moon CIB", 2001, 30, 80, 200, "Common"),
        ("GBA", "Golden Sun CIB", 2001, 30, 80, 200, "Common"),
        ("GBA", "Golden Sun The Lost Age CIB", 2003, 40, 100, 250, "Common"),
        ("GBA", "Mega Man Zero CIB", 2002, 30, 80, 200, "Common"),
        ("GBA", "Mega Man Battle Network 3 Blue CIB", 2003, 25, 60, 150, "Common"),
        ("GBA", "Final Fantasy Tactics Advance CIB", 2003, 20, 50, 130, "Common"),
        ("GBA", "Metroid Fusion CIB", 2002, 50, 120, 300, "Uncommon"),
        ("GBA", "Metroid Zero Mission CIB", 2004, 50, 130, 300, "Uncommon"),
        ("GBA", "Kirby & The Amazing Mirror CIB", 2004, 30, 80, 200, "Common"),
        ("GBA", "Advance Wars CIB", 2001, 40, 100, 250, "Uncommon"),
    ]

    # ── NES — Classic Sealed/CIB ─────────────────────────────────
    nes_games = [
        ("NES", "Super Mario Bros CIB", 1985, 20, 80, 300, "Common"),
        ("NES", "Super Mario Bros 3 CIB", 1988, 25, 80, 250, "Common"),
        ("NES", "Mega Man 2 CIB", 1988, 30, 80, 250, "Common"),
        ("NES", "Mega Man 5 CIB", 1992, 100, 250, 600, "Rare"),
        ("NES", "Mega Man 6 CIB", 1993, 80, 200, 500, "Uncommon"),
        ("NES", "Castlevania III Dracula's Curse CIB", 1989, 60, 150, 400, "Uncommon"),
        ("NES", "Ninja Gaiden CIB", 1988, 25, 60, 180, "Common"),
        ("NES", "Ninja Gaiden II CIB", 1990, 25, 60, 180, "Common"),
        ("NES", "Contra CIB", 1988, 50, 120, 350, "Uncommon"),
        ("NES", "Mike Tyson's Punch-Out!! CIB", 1987, 40, 100, 300, "Uncommon"),
        ("NES", "Metroid CIB", 1986, 30, 80, 250, "Common"),
        ("NES", "Zelda II The Adventure of Link CIB (Gold)", 1987, 25, 70, 200, "Common"),
        ("NES", "Little Samson CIB", 1992, 800, 2000, 5000, "Grail"),
        ("NES", "Snow Brothers CIB", 1991, 300, 700, 1800, "Grail"),
        ("NES", "Bubble Bobble Part 2 CIB", 1993, 500, 1200, 3000, "Grail"),
        ("NES", "Power Blade 2 CIB", 1992, 250, 600, 1500, "Grail"),
        ("NES", "Flintstones Surprise at Dinosaur Peak CIB", 1994, 800, 2000, 5000, "Grail"),
        ("NES", "Stadium Events CIB", 1987, 20000, 50000, 100000, "Grail"),
        ("NES", "Dragon Warrior CIB", 1989, 20, 50, 150, "Common"),
        ("NES", "Final Fantasy CIB", 1990, 30, 80, 250, "Common"),
    ]

    # ── Wii / Wii U — Sought-After ────────────────────────────────
    wii_games = [
        ("Wii", "Metroid Prime Trilogy Steelbook CIB", 2009, 80, 180, 400, "Uncommon"),
        ("Wii", "Xenoblade Chronicles CIB (NA)", 2012, 50, 100, 250, "Uncommon"),
        ("Wii", "Fire Emblem Radiant Dawn CIB", 2007, 80, 180, 400, "Uncommon"),
        ("Wii", "Dokapon Kingdom CIB", 2008, 100, 250, 600, "Rare"),
        ("Wii", "Super Mario Galaxy CIB", 2007, 15, 30, 80, "Common"),
        ("Wii U", "Zelda Breath of the Wild CIB (Wii U)", 2017, 25, 50, 120, "Common"),
        ("Wii U", "Devil's Third CIB", 2015, 80, 180, 400, "Uncommon"),
        ("Wii U", "Axiom Verge Multiverse Edition CIB", 2017, 60, 130, 300, "Uncommon"),
    ]

    all_groups = [
        (snes_keys, "SNES"),
        (gc_games, "GameCube"),
        (ps1_games, "PS1"),
        (scd_games, "Sega CD"),
        (n64_games, "N64"),
        (neogeo_extra, "Neo Geo AES"),
        (saturn_extra, "Saturn"),
        (ps2_games, "PS2"),
        (dc_extra, "Dreamcast"),
        (gb_gba_games, "GBA"),
        (nes_games, "NES"),
        (wii_games, "Wii"),
    ]

    for group, default_platform in all_groups:
        for platform, title, year, loose, cib, sealed, rarity in group:
            items.append({
                "type": "game",
                "maker": platform.split()[0] if " " not in platform else platform,
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
