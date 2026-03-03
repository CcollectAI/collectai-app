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
        ("TurboGrafx-16", "Air Zonk", 1992, 80, 180, 500, "Uncommon"),
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
        ("2600", "Atlantis", 1982, 3, 10, 60, "Common"),
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
