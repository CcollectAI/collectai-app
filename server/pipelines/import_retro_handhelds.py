"""
Import retro handheld consoles & devices catalog (500+ items).

Layer 1 (Catalog):  Curated retro handheld devices -> category_items
Layer 2 (Prices):   Estimated market prices (loose + CIB) -> train.jsonl

Covers:
- Nintendo Game Boy family (DMG, Pocket, Light, Color, Advance, SP, Micro)
- Nintendo DS family (DS Phat, Lite, DSi, 3DS, New 3DS XL)
- Nintendo Switch Lite (limited editions)
- Sony PSP family (PSP-1000/2000/3000, PSP Go, PS Vita)
- Sega handhelds (Game Gear, Nomad)
- Atari Lynx (I and II)
- Neo Geo Pocket Color
- Bandai WonderSwan family
- Nokia N-Gage
- TurboExpress / PC Engine GT
- Tiger Game.com
- Tamagotchi (P1, P2, Connection, Music Star, iD L, 4U, Meets, ON, Smart, Uni)
- Nintendo Game & Watch classics
- Epoch Game Pocket Computer, Microvision
- Watara Supervision, Gamate, GP32
- Modern retro handhelds (Analogue Pocket, Miyoo Mini, RG35XX, RG556, Trimui)
- Tiger Electronics LCD handhelds

Usage:
    python -m pipelines.import_retro_handhelds [--dry-run]
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

CATEGORY = "retro_handhelds"


def get_curated_catalog() -> list[dict]:
    """Curated retro handheld consoles catalog (500+ items)."""

    # (brand, name, platform, variant_note, condition, rarity_tier, price_loose_eur, price_cib_eur)
    # rarity_tier: grail (>200 EUR), high (80-200), mid (30-80), standard (<30)

    items = [
        # ---------------------------------------------------------------
        # Nintendo Game Boy DMG-01
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy DMG-01", "Game Boy", "Original Gray", "Standard", "mid", 40, 90),
        ("Nintendo", "Game Boy DMG-01 Play It Loud Red", "Game Boy", "Play It Loud Red", "Limited Color", "high", 65, 140),
        ("Nintendo", "Game Boy DMG-01 Play It Loud Green", "Game Boy", "Play It Loud Green", "Limited Color", "high", 60, 130),
        ("Nintendo", "Game Boy DMG-01 Play It Loud Yellow", "Game Boy", "Play It Loud Yellow", "Limited Color", "high", 70, 150),
        ("Nintendo", "Game Boy DMG-01 Play It Loud Black", "Game Boy", "Play It Loud Black", "Limited Color", "high", 55, 120),
        ("Nintendo", "Game Boy DMG-01 Play It Loud Clear", "Game Boy", "Play It Loud Clear/Transparent", "Limited Color", "high", 80, 170),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Pocket
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Pocket Silver", "Game Boy Pocket", "Standard Silver", "Standard", "mid", 35, 75),
        ("Nintendo", "Game Boy Pocket Ice Blue", "Game Boy Pocket", "Ice Blue (Japan)", "Japan Exclusive", "high", 90, 180),
        ("Nintendo", "Game Boy Pocket Clear Purple", "Game Boy Pocket", "Clear Purple", "Limited Color", "high", 80, 160),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Light (Japan only)
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Light Gold", "Game Boy Light", "Gold (Japan)", "Japan Exclusive", "grail", 220, 450),
        ("Nintendo", "Game Boy Light Silver", "Game Boy Light", "Silver (Japan)", "Japan Exclusive", "grail", 200, 420),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Color
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Color Grape", "Game Boy Color", "Grape Purple", "Standard", "mid", 40, 85),
        ("Nintendo", "Game Boy Color Berry", "Game Boy Color", "Berry Pink", "Standard", "mid", 40, 85),
        ("Nintendo", "Game Boy Color Teal", "Game Boy Color", "Teal", "Standard", "mid", 38, 80),
        ("Nintendo", "Game Boy Color Dandelion", "Game Boy Color", "Dandelion Yellow", "Standard", "mid", 42, 90),
        ("Nintendo", "Game Boy Color Pokemon Yellow Edition", "Game Boy Color", "Pokemon Yellow Pikachu", "Special Edition", "high", 120, 280),
        ("Nintendo", "Game Boy Color Pokemon Gold/Silver Edition", "Game Boy Color", "Pokemon Gold & Silver", "Special Edition", "high", 130, 300),
        ("Nintendo", "Game Boy Color Cardcaptor Sakura", "Game Boy Color", "Cardcaptor Sakura (Japan)", "Japan Exclusive", "grail", 250, 500),
        ("Nintendo", "Game Boy Color Toys R Us Clear", "Game Boy Color", "Toys R Us Atomic Purple Clear", "Special Edition", "high", 100, 220),
        ("Nintendo", "Game Boy Color Pokemon Center NY", "Game Boy Color", "Pokemon Center New York Orange", "Special Edition", "grail", 280, 550),
        ("Nintendo", "Game Boy Color Hello Kitty", "Game Boy Color", "Hello Kitty Special Box (Japan)", "Japan Exclusive", "grail", 260, 520),
        ("Nintendo", "Game Boy Color Daiei Hawks", "Game Boy Color", "Daiei Hawks Clear Blue (Japan)", "Japan Exclusive", "grail", 300, 600),
        ("Nintendo", "Game Boy Color Tommy Hilfiger", "Game Boy Color", "Tommy Hilfiger Yellow", "Special Edition", "high", 140, 300),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Advance
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Advance Indigo", "Game Boy Advance", "Indigo/Purple", "Standard", "mid", 45, 100),
        ("Nintendo", "Game Boy Advance Glacier", "Game Boy Advance", "Glacier Clear Blue", "Standard", "mid", 50, 110),
        ("Nintendo", "Game Boy Advance Pokemon Center", "Game Boy Advance", "Pokemon Center Exclusive", "Special Edition", "high", 150, 350),
        ("Nintendo", "Game Boy Advance Toys R Us Clear Orange", "Game Boy Advance", "Toys R Us Clear Orange", "Special Edition", "high", 120, 260),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Advance SP
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Advance SP Cobalt Blue", "Game Boy Advance SP", "Cobalt Blue AGS-001", "Standard", "mid", 55, 120),
        ("Nintendo", "Game Boy Advance SP Graphite", "Game Boy Advance SP", "Graphite AGS-001", "Standard", "mid", 55, 115),
        ("Nintendo", "Game Boy Advance SP AGS-101 Backlit", "Game Boy Advance SP", "AGS-101 Backlit Pearl Blue", "Standard", "high", 90, 180),
        ("Nintendo", "Game Boy Advance SP NES Edition", "Game Boy Advance SP", "NES Classic Edition", "Special Edition", "high", 130, 280),
        ("Nintendo", "Game Boy Advance SP Pikachu Edition", "Game Boy Advance SP", "Pikachu Yellow (Japan)", "Japan Exclusive", "high", 160, 350),
        ("Nintendo", "Game Boy Advance SP Tribal", "Game Boy Advance SP", "Tribal Silver", "Limited Color", "high", 100, 220),
        ("Nintendo", "Game Boy Advance SP Final Fantasy Tactics", "Game Boy Advance SP", "FFT Pearl White (Japan)", "Japan Exclusive", "grail", 200, 420),
        ("Nintendo", "Game Boy Advance SP Famicom Anniversary", "Game Boy Advance SP", "Famicom 20th Anniversary (Japan)", "Anniversary", "grail", 220, 450),
        ("Nintendo", "Game Boy Advance SP Pokemon Center Latias", "Game Boy Advance SP", "Pokemon Center Latias/Latios Red (Japan)", "Japan Exclusive", "grail", 280, 550),
        ("Nintendo", "Game Boy Advance SP Pokemon Center Groudon", "Game Boy Advance SP", "Pokemon Center Groudon Red (Japan)", "Japan Exclusive", "grail", 260, 520),
        ("Nintendo", "Game Boy Advance SP Kingdom Hearts Chain of Memories", "Game Boy Advance SP", "Kingdom Hearts CoM (Japan)", "Japan Exclusive", "grail", 240, 480),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Micro
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Micro Silver", "Game Boy Micro", "Silver", "Standard", "high", 130, 280),
        ("Nintendo", "Game Boy Micro 20th Anniversary Famicom", "Game Boy Micro", "20th Anniversary Famicom", "Anniversary", "grail", 250, 500),
        ("Nintendo", "Game Boy Micro Blue", "Game Boy Micro", "Blue", "Standard", "high", 140, 290),
        ("Nintendo", "Game Boy Micro Final Fantasy IV", "Game Boy Micro", "Final Fantasy IV Advance (Japan)", "Japan Exclusive", "grail", 300, 580),
        ("Nintendo", "Game Boy Micro Black", "Game Boy Micro", "Black", "Standard", "high", 135, 275),

        # ---------------------------------------------------------------
        # Nintendo DS Family
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo DS Original Silver", "Nintendo DS", "Titanium Silver (Phat)", "Standard", "standard", 25, 55),
        ("Nintendo", "Nintendo DS Lite White", "Nintendo DS Lite", "Polar White", "Standard", "standard", 25, 55),
        ("Nintendo", "Nintendo DS Lite Crimson/Black", "Nintendo DS Lite", "Crimson/Black", "Standard", "mid", 30, 65),
        ("Nintendo", "Nintendo DS Lite Zelda Phantom Hourglass", "Nintendo DS Lite", "Zelda Gold", "Special Edition", "high", 100, 220),
        ("Nintendo", "Nintendo DS Lite Final Fantasy III", "Nintendo DS Lite", "Crystal White FF III Bundle", "Console Bundle", "high", 80, 180),
        ("Nintendo", "Nintendo DS Lite Pokemon Diamond/Pearl", "Nintendo DS Lite", "Pokemon Dialga/Palkia", "Special Edition", "high", 90, 200),
        ("Nintendo", "Nintendo DS Lite Pikachu Edition", "Nintendo DS Lite", "Pikachu Yellow (Japan)", "Japan Exclusive", "high", 110, 240),
        ("Nintendo", "Nintendo DS Lite Final Fantasy III Crystal", "Nintendo DS Lite", "Crystal Edition FF III (Japan)", "Japan Exclusive", "high", 120, 260),
        ("Nintendo", "Nintendo DSi Black", "Nintendo DSi", "Matte Black", "Standard", "mid", 30, 65),
        ("Nintendo", "Nintendo DSi XL Burgundy", "Nintendo DSi XL", "Burgundy Wine", "Standard", "mid", 40, 80),

        # ---------------------------------------------------------------
        # Nintendo 3DS Family
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo 3DS Aqua Blue", "Nintendo 3DS", "Aqua Blue", "Standard", "mid", 60, 130),
        ("Nintendo", "Nintendo 3DS Zelda 25th Anniversary", "Nintendo 3DS", "Zelda 25th Anniversary", "Special Edition", "high", 140, 300),
        ("Nintendo", "Nintendo 3DS Pikachu Yellow", "Nintendo 3DS", "Pikachu Yellow Limited", "Special Edition", "high", 130, 280),
        ("Nintendo", "Nintendo 3DS XL Monster Hunter 4", "Nintendo 3DS XL", "Monster Hunter 4 (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "New Nintendo 3DS XL SNES Edition", "New Nintendo 3DS XL", "SNES Edition", "Special Edition", "high", 160, 340),
        ("Nintendo", "New Nintendo 3DS XL Monster Hunter Generations", "New Nintendo 3DS XL", "Monster Hunter Generations", "Special Edition", "high", 130, 270),
        ("Nintendo", "New Nintendo 3DS XL Fire Emblem Fates", "New Nintendo 3DS XL", "Fire Emblem Fates", "Special Edition", "high", 150, 320),

        # ---------------------------------------------------------------
        # Sony PlayStation Portable
        # ---------------------------------------------------------------
        ("Sony", "PSP-1000 Black", "PSP-1000", "Piano Black", "Standard", "mid", 40, 85),
        ("Sony", "PSP-1000 Star Wars Battlefront", "PSP-1000", "Star Wars White Bundle", "Console Bundle", "high", 80, 170),
        ("Sony", "PSP-1000 Monster Hunter Portable 3rd", "PSP-1000", "MHP3rd Hunter (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Sony", "PSP-2000 Slim Ice Silver", "PSP-2000", "Ice Silver Slim", "Standard", "mid", 35, 75),
        ("Sony", "PSP-2000 Crisis Core FF VII", "PSP-2000", "Crisis Core FFVII Silver Bundle", "Console Bundle", "high", 90, 200),
        ("Sony", "PSP-3000 Vibrant Blue", "PSP-3000", "Vibrant Blue", "Standard", "mid", 40, 85),
        ("Sony", "PSP Go Pearl White", "PSP Go", "Pearl White (N-1000)", "Standard", "high", 85, 180),
        ("Sony", "PSP Go Piano Black", "PSP Go", "Piano Black (N-1000)", "Standard", "mid", 70, 150),
        ("Sony", "PSP-3000 Monster Hunter 3rd", "PSP-3000", "Monster Hunter Portable 3rd (Japan)", "Japan Exclusive", "high", 95, 200),
        ("Sony", "PSP-3000 Kingdom Hearts Birth By Sleep", "PSP-3000", "Kingdom Hearts BBS Bundle", "Console Bundle", "high", 110, 230),
        ("Sony", "PSP-2000 God of War Red", "PSP-2000", "God of War Red/Black Bundle", "Console Bundle", "high", 85, 180),

        # ---------------------------------------------------------------
        # Sony PS Vita
        # ---------------------------------------------------------------
        ("Sony", "PS Vita OLED Black", "PS Vita 1000", "Black OLED (PCH-1000)", "Standard", "high", 110, 220),
        ("Sony", "PS Vita OLED White", "PS Vita 1000", "Crystal White OLED (Japan)", "Japan Exclusive", "high", 130, 260),
        ("Sony", "PS Vita Slim Black", "PS Vita 2000", "Black Slim (PCH-2000)", "Standard", "high", 100, 200),
        ("Sony", "PS Vita Slim Aqua Blue", "PS Vita 2000", "Aqua Blue Slim (Japan)", "Japan Exclusive", "high", 140, 280),
        ("Sony", "PS Vita OLED Hatsune Miku Limited", "PS Vita 1000", "Hatsune Miku Limited Edition (Japan)", "Japan Exclusive", "grail", 250, 480),
        ("Sony", "PS Vita Slim God Eater 2", "PS Vita 2000", "God Eater 2 Fenrir Edition (Japan)", "Japan Exclusive", "high", 180, 350),
        ("Sony", "PS Vita Slim Persona 4 Dancing", "PS Vita 2000", "Persona 4 Dancing All Night (Japan)", "Japan Exclusive", "high", 190, 370),
        ("Sony", "PS Vita OLED Assassin's Creed Liberation", "PS Vita 1000", "White AC Liberation Bundle", "Console Bundle", "high", 150, 300),

        # ---------------------------------------------------------------
        # Sega Handhelds
        # ---------------------------------------------------------------
        ("Sega", "Game Gear Black", "Game Gear", "Standard Black", "Standard", "mid", 35, 80),
        ("Sega", "Game Gear Blue", "Game Gear", "Sports Edition Blue", "Limited Color", "high", 80, 170),
        ("Sega", "Game Gear White", "Game Gear", "White (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Sega", "Game Gear Coca-Cola Red", "Game Gear", "Coca-Cola Red (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Sega", "Sega Nomad", "Sega Nomad", "Standard Black", "Standard", "high", 150, 320),

        # ---------------------------------------------------------------
        # Atari Lynx
        # ---------------------------------------------------------------
        ("Atari", "Atari Lynx I", "Atari Lynx", "Original (Model PAG-0200)", "Standard", "high", 80, 180),
        ("Atari", "Atari Lynx II", "Atari Lynx II", "Redesigned (Model PAG-0401)", "Standard", "high", 70, 160),
        ("Atari", "Atari Lynx I California Games Bundle", "Atari Lynx", "California Games Pack-In Bundle", "Console Bundle", "high", 120, 260),
        ("Atari", "Atari Lynx II Batman Returns Bundle", "Atari Lynx II", "Batman Returns Bundle", "Console Bundle", "high", 100, 220),

        # ---------------------------------------------------------------
        # Neo Geo Pocket Color
        # ---------------------------------------------------------------
        ("SNK", "Neo Geo Pocket Color Anthracite", "Neo Geo Pocket Color", "Anthracite Black", "Standard", "high", 80, 170),
        ("SNK", "Neo Geo Pocket Color Crystal Blue", "Neo Geo Pocket Color", "Crystal Blue", "Limited Color", "high", 100, 210),
        ("SNK", "Neo Geo Pocket Color Platinum Silver", "Neo Geo Pocket Color", "Platinum Silver", "Standard", "high", 85, 180),
        ("SNK", "Neo Geo Pocket Color Camouflage Blue", "Neo Geo Pocket Color", "Camouflage Blue", "Limited Color", "high", 110, 230),
        ("SNK", "SNK vs. Capcom Card Fighters Clash NGPC", "Neo Geo Pocket Color", "SNK vs. Capcom Card Fighters Clash (Game)", "Standard", "high", 80, 160),
        ("SNK", "Sonic the Hedgehog Pocket Adventure NGPC", "Neo Geo Pocket Color", "Sonic Pocket Adventure (Game)", "Standard", "high", 90, 180),
        ("SNK", "Metal Slug 1st Mission NGPC", "Neo Geo Pocket Color", "Metal Slug 1st Mission (Game)", "Standard", "high", 85, 170),

        # ---------------------------------------------------------------
        # Bandai WonderSwan
        # ---------------------------------------------------------------
        ("Bandai", "WonderSwan Crystal Blue", "WonderSwan Crystal", "Crystal Blue", "Standard", "high", 60, 130),
        ("Bandai", "SwanCrystal Wine Red", "SwanCrystal", "Wine Red", "Standard", "high", 65, 140),
        ("Bandai", "WonderSwan Color Final Fantasy", "WonderSwan Color", "Final Fantasy Limited (Japan)", "Japan Exclusive", "high", 110, 240),
        ("Bandai", "WonderSwan Color Final Fantasy II", "WonderSwan Color", "Final Fantasy II Crystal Blue (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Bandai", "WonderSwan Digimon Adventure", "WonderSwan", "Digimon Adventure Orange (Japan)", "Japan Exclusive", "high", 90, 190),
        ("Bandai", "WonderSwan Gundam Wing", "WonderSwan", "Gundam Wing Metallic Blue (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Bandai", "SwanCrystal Final Fantasy Limited", "SwanCrystal", "Final Fantasy Crystal Limited (Japan)", "Japan Exclusive", "high", 130, 270),

        # ---------------------------------------------------------------
        # Nokia N-Gage
        # ---------------------------------------------------------------
        ("Nokia", "Nokia N-Gage Original", "N-Gage", "Silver/Gray Original", "Standard", "mid", 40, 90),
        ("Nokia", "Nokia N-Gage QD", "N-Gage QD", "Black Redesign", "Standard", "mid", 35, 75),

        # ---------------------------------------------------------------
        # TurboExpress / PC Engine GT
        # ---------------------------------------------------------------
        ("NEC", "TurboExpress", "TurboExpress", "Standard Black (NA)", "Standard", "grail", 220, 450),
        ("NEC", "PC Engine GT", "PC Engine GT", "Standard Black (Japan)", "Japan Exclusive", "grail", 250, 500),

        # ---------------------------------------------------------------
        # Tiger Game.com
        # ---------------------------------------------------------------
        ("Tiger", "Tiger Game.com", "Game.com", "Standard Black", "Standard", "mid", 35, 80),
        ("Tiger", "Tiger Game.com Pocket Pro", "Game.com Pocket Pro", "Silver", "Standard", "mid", 40, 90),

        # ---------------------------------------------------------------
        # Tamagotchi
        # ---------------------------------------------------------------
        ("Bandai", "Tamagotchi P1 Original White", "Tamagotchi", "Original P1 White", "Standard", "mid", 30, 70),
        ("Bandai", "Tamagotchi P2 Blue", "Tamagotchi", "P2 Blue", "Standard", "mid", 30, 65),
        ("Bandai", "Tamagotchi Connection V3", "Tamagotchi", "Connection V3", "Standard", "standard", 20, 45),
        ("Bandai", "Tamagotchi Music Star", "Tamagotchi", "Music Star", "Standard", "mid", 45, 100),
        ("Bandai", "Tamagotchi iD L Princess Spacy", "Tamagotchi", "iD L Princess Spacy (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Bandai", "Tamagotchi Devilgotchi", "Tamagotchi", "Devilgotchi (Japan)", "Japan Exclusive", "grail", 200, 400),

        # ---------------------------------------------------------------
        # Nintendo Game & Watch
        # ---------------------------------------------------------------
        ("Nintendo", "Game & Watch Ball (AC-01)", "Game & Watch", "Ball (1980 Original)", "Standard", "grail", 300, 800),
        ("Nintendo", "Game & Watch Donkey Kong (DK-52)", "Game & Watch", "Donkey Kong Multi Screen", "Standard", "high", 80, 180),
        ("Nintendo", "Game & Watch Octopus (OC-22)", "Game & Watch", "Octopus Wide Screen", "Standard", "high", 70, 160),
        ("Nintendo", "Game & Watch Mario Bros (MW-56)", "Game & Watch", "Mario Bros Multi Screen", "Standard", "high", 90, 200),
        ("Nintendo", "Game & Watch Zelda (ZL-65) Reissue", "Game & Watch", "Zelda 2021 Reissue", "Anniversary", "mid", 40, 70),
        ("Nintendo", "Game & Watch Super Mario Bros Reissue", "Game & Watch", "Super Mario Bros 2020 Reissue", "Anniversary", "mid", 35, 65),
        ("Nintendo", "Game & Watch Donkey Kong Reissue", "Game & Watch", "Donkey Kong 2021 Reissue", "Anniversary", "mid", 38, 68),

        # ---------------------------------------------------------------
        # Epoch / Microvision / Misc Vintage
        # ---------------------------------------------------------------
        ("Epoch", "Epoch Game Pocket Computer", "Game Pocket Computer", "Standard White (Japan)", "Japan Exclusive", "grail", 250, 550),
        ("Milton Bradley", "Microvision", "Microvision", "Standard Black", "Standard", "high", 80, 200),

        # ---------------------------------------------------------------
        # Modern Retro Handhelds (Modded/Custom)
        # ---------------------------------------------------------------
        ("Analogue", "Analogue Pocket White", "Analogue Pocket", "White", "Standard", "high", 180, 250),
        ("Analogue", "Analogue Pocket Classic Limited", "Analogue Pocket", "Classic Limited Edition", "Limited Color", "grail", 280, 380),
        ("Miyoo", "Miyoo Mini Plus", "Miyoo Mini Plus", "White", "Modded/Custom", "mid", 55, 70),
        ("Anbernic", "Anbernic RG35XX", "RG35XX", "Transparent Purple", "Modded/Custom", "mid", 50, 65),
        ("Anbernic", "Anbernic RG353V", "RG353V", "Anodized Gray", "Modded/Custom", "mid", 60, 80),
        ("Analogue", "Analogue Pocket Black", "Analogue Pocket", "Black", "Standard", "high", 190, 260),
        ("Analogue", "Analogue Pocket Transparent", "Analogue Pocket", "Transparent Clear", "Limited Color", "grail", 320, 420),
        ("Miyoo", "Miyoo Mini V2", "Miyoo Mini", "Gray Original", "Modded/Custom", "mid", 40, 55),
        ("Anbernic", "Anbernic RG35XX Plus", "RG35XX Plus", "Transparent Black", "Modded/Custom", "mid", 55, 70),
        ("Retroid", "Retroid Pocket 3 Plus", "Retroid Pocket 3+", "Black 4GB", "Modded/Custom", "mid", 70, 90),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Color — additional variants
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Color Kiwi", "Game Boy Color", "Kiwi Green", "Standard", "mid", 42, 88),
        ("Nintendo", "Game Boy Color Atomic Purple", "Game Boy Color", "Atomic Purple", "Standard", "mid", 45, 95),
        ("Nintendo", "Game Boy Color Sakura Taisen", "Game Boy Color", "Sakura Taisen Pink (Japan)", "Japan Exclusive", "grail", 220, 440),
        ("Nintendo", "Game Boy Color Manchester United", "Game Boy Color", "Manchester United Red (EU)", "Special Edition", "high", 100, 210),
        ("Nintendo", "Game Boy Color Ozzie Ozbourne", "Game Boy Color", "Ozzie Ozbourne Black (Promo)", "Special Edition", "high", 150, 320),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Advance — additional
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Advance Flame Red", "Game Boy Advance", "Flame Red", "Standard", "mid", 48, 105),
        ("Nintendo", "Game Boy Advance White", "Game Boy Advance", "Arctic White", "Standard", "mid", 50, 110),
        ("Nintendo", "Game Boy Advance Spice Orange", "Game Boy Advance", "Spice Orange (Japan)", "Japan Exclusive", "high", 80, 170),
        ("Nintendo", "Game Boy Advance Celebi Green", "Game Boy Advance", "Pokemon Center Celebi Green (Japan)", "Japan Exclusive", "grail", 200, 400),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Advance SP — additional
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Advance SP Flame Red", "Game Boy Advance SP", "Flame Red AGS-001", "Standard", "mid", 55, 115),
        ("Nintendo", "Game Boy Advance SP Pearl Pink", "Game Boy Advance SP", "Pearl Pink AGS-001", "Standard", "mid", 60, 125),
        ("Nintendo", "Game Boy Advance SP Onyx Black", "Game Boy Advance SP", "Onyx Black AGS-001", "Standard", "mid", 50, 110),
        ("Nintendo", "Game Boy Advance SP Surf Blue", "Game Boy Advance SP", "Surf Blue AGS-101 (Japan)", "Japan Exclusive", "high", 140, 300),
        ("Nintendo", "Game Boy Advance SP SpongeBob", "Game Boy Advance SP", "SpongeBob SquarePants Yellow", "Special Edition", "high", 110, 240),
        ("Nintendo", "Game Boy Advance SP Torchic Orange", "Game Boy Advance SP", "Pokemon Center Torchic Orange (Japan)", "Japan Exclusive", "grail", 250, 500),

        # ---------------------------------------------------------------
        # Nintendo DS Family — additional
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo DS Lite Enamel Navy", "Nintendo DS Lite", "Enamel Navy", "Standard", "mid", 30, 65),
        ("Nintendo", "Nintendo DS Lite Metallic Rose", "Nintendo DS Lite", "Metallic Rose", "Standard", "mid", 35, 70),
        ("Nintendo", "Nintendo DSi White", "Nintendo DSi", "Matte White", "Standard", "mid", 30, 60),
        ("Nintendo", "Nintendo DSi Mario Edition", "Nintendo DSi", "Super Mario 25th Anniversary Red", "Anniversary", "high", 80, 170),
        ("Nintendo", "Nintendo DSi XL Mario Edition Red", "Nintendo DSi XL", "New Super Mario Bros Red", "Special Edition", "high", 70, 150),

        # ---------------------------------------------------------------
        # Nintendo 3DS — additional
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo 3DS Cosmo Black", "Nintendo 3DS", "Cosmo Black", "Standard", "mid", 55, 120),
        ("Nintendo", "Nintendo 3DS Flame Red", "Nintendo 3DS", "Flame Red", "Standard", "mid", 55, 120),
        ("Nintendo", "Nintendo 3DS XL Blue/Black", "Nintendo 3DS XL", "Blue/Black", "Standard", "mid", 65, 140),
        ("Nintendo", "Nintendo 3DS XL Zelda A Link Between Worlds", "Nintendo 3DS XL", "Zelda A Link Between Worlds Gold", "Special Edition", "high", 170, 360),
        ("Nintendo", "New Nintendo 3DS Black", "New Nintendo 3DS", "Black (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Nintendo", "New Nintendo 3DS XL Majora's Mask Edition", "New Nintendo 3DS XL", "Majora's Mask 3D Gold/Black", "Special Edition", "high", 180, 380),
        ("Nintendo", "New Nintendo 3DS XL Hyrule Edition", "New Nintendo 3DS XL", "Hyrule Gold", "Special Edition", "high", 160, 340),
        ("Nintendo", "New Nintendo 3DS XL Galaxy Style", "New Nintendo 3DS XL", "Galaxy Purple", "Limited Color", "high", 120, 250),
        ("Nintendo", "New Nintendo 2DS XL Hylian Shield Edition", "New Nintendo 2DS XL", "Hylian Shield", "Special Edition", "high", 140, 290),
        ("Nintendo", "New Nintendo 2DS XL Pokeball Edition", "New Nintendo 2DS XL", "Pokeball Red/White", "Special Edition", "high", 110, 230),

        # ---------------------------------------------------------------
        # Nintendo Switch Lite (limited editions)
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo Switch Lite Zacian & Zamazenta", "Switch Lite", "Pokemon Sword/Shield Edition", "Special Edition", "mid", 70, 130),
        ("Nintendo", "Nintendo Switch Lite Dialga & Palkia", "Switch Lite", "Pokemon Brilliant Diamond/Shining Pearl Edition", "Special Edition", "high", 90, 170),
        ("Nintendo", "Nintendo Switch Lite Coral Pink", "Switch Lite", "Coral Pink", "Standard", "mid", 55, 100),

        # ---------------------------------------------------------------
        # Sony PSP — additional
        # ---------------------------------------------------------------
        ("Sony", "PSP-1000 White", "PSP-1000", "Ceramic White", "Standard", "mid", 45, 90),
        ("Sony", "PSP-2000 Daxter Entertainment Pack", "PSP-2000", "Daxter Silver Bundle", "Console Bundle", "high", 80, 170),
        ("Sony", "PSP-3000 Radiant Red", "PSP-3000", "Radiant Red/Black", "Limited Color", "mid", 50, 105),
        ("Sony", "PSP-3000 Pearl White", "PSP-3000", "Pearl White", "Standard", "mid", 45, 90),
        ("Sony", "PSP-3000 Carnival Colors Blue", "PSP-3000", "Carnival Colors Vibrant Blue", "Limited Color", "mid", 55, 110),
        ("Sony", "PSP-3000 Hatsune Miku Limited", "PSP-3000", "Hatsune Miku Project Diva 2nd (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Sony", "PSP-3000 Metal Gear Solid Peace Walker", "PSP-3000", "MGS Peace Walker Camo Green Bundle", "Console Bundle", "high", 100, 210),

        # ---------------------------------------------------------------
        # Sony PS Vita — additional
        # ---------------------------------------------------------------
        ("Sony", "PS Vita OLED Blue", "PS Vita 1000", "Sapphire Blue OLED (Japan)", "Japan Exclusive", "high", 140, 280),
        ("Sony", "PS Vita Slim Light Blue/White", "PS Vita 2000", "Light Blue/White (Japan)", "Japan Exclusive", "high", 150, 290),
        ("Sony", "PS Vita Slim Lime Green/White", "PS Vita 2000", "Lime Green/White (Japan)", "Japan Exclusive", "high", 150, 300),
        ("Sony", "PS Vita Slim Neon Orange", "PS Vita 2000", "Neon Orange (Japan)", "Japan Exclusive", "high", 160, 310),
        ("Sony", "PS Vita Slim Dragon Quest Builders", "PS Vita 2000", "Dragon Quest Builders Metal Slime (Japan)", "Japan Exclusive", "grail", 220, 430),
        ("Sony", "PS Vita TV", "PS Vita TV", "Standard Black (Japan)", "Japan Exclusive", "mid", 60, 110),

        # ---------------------------------------------------------------
        # Sega Game Gear — additional
        # ---------------------------------------------------------------
        ("Sega", "Game Gear Yellow", "Game Gear", "Yellow (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Sega", "Game Gear Smoke", "Game Gear", "Smoke Transparent (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Sega", "Game Gear Micro Black", "Game Gear Micro", "Micro Black (Japan 2020)", "Japan Exclusive", "mid", 55, 90),
        ("Sega", "Game Gear Micro Blue", "Game Gear Micro", "Micro Blue (Japan 2020)", "Japan Exclusive", "mid", 55, 90),

        # ---------------------------------------------------------------
        # Tamagotchi — additional
        # ---------------------------------------------------------------
        ("Bandai", "Tamagotchi P1 Transparent Blue", "Tamagotchi", "P1 Transparent Blue", "Limited Color", "high", 80, 170),
        ("Bandai", "Tamagotchi Angel White", "Tamagotchi", "Angelgotchi White", "Standard", "mid", 50, 110),
        ("Bandai", "Tamagotchi Osutchi/Mesutchi Pair", "Tamagotchi", "Osutchi & Mesutchi Pair (Japan)", "Japan Exclusive", "high", 90, 200),
        ("Bandai", "Tamagotchi 4U Purple", "Tamagotchi", "4U Purple", "Standard", "mid", 60, 120),
        ("Bandai", "Tamagotchi Meets Magical", "Tamagotchi", "Meets Magical Purple (Japan)", "Japan Exclusive", "mid", 65, 130),
        ("Bandai", "Tamagotchi ON Wonder Garden", "Tamagotchi", "ON Wonder Garden Lavender", "Standard", "mid", 50, 90),
        ("Bandai", "Tamagotchi Smart Mint Blue", "Tamagotchi", "Smart Mint Blue (Japan)", "Japan Exclusive", "mid", 55, 100),
        ("Bandai", "Tamagotchi Uni Purple", "Tamagotchi", "Uni Purple", "Standard", "mid", 45, 80),
        ("Bandai", "Tamagotchi Nano Pac-Man Collab", "Tamagotchi", "Nano Pac-Man Yellow Collab", "Special Edition", "mid", 30, 55),

        # ---------------------------------------------------------------
        # Game & Watch — additional
        # ---------------------------------------------------------------
        ("Nintendo", "Game & Watch Fire (RC-04)", "Game & Watch", "Fire (1980 Silver Series)", "Standard", "high", 100, 250),
        ("Nintendo", "Game & Watch Manhole (MH-06)", "Game & Watch", "Manhole (1981 Gold Series)", "Standard", "high", 90, 220),
        ("Nintendo", "Game & Watch Parachute (PR-21)", "Game & Watch", "Parachute Wide Screen", "Standard", "high", 85, 200),
        ("Nintendo", "Game & Watch Snoopy (SM-73)", "Game & Watch", "Snoopy Panorama Screen", "Standard", "high", 120, 280),
        ("Nintendo", "Game & Watch Mickey Mouse (MC-25)", "Game & Watch", "Mickey Mouse Wide Screen", "Standard", "high", 95, 230),
        ("Nintendo", "Game & Watch Oil Panic (OP-51)", "Game & Watch", "Oil Panic Multi Screen", "Standard", "high", 100, 240),
        ("Nintendo", "Game & Watch Greenhouse (GH-54)", "Game & Watch", "Greenhouse Multi Screen", "Standard", "high", 95, 220),

        # ---------------------------------------------------------------
        # Watara Supervision / Gamate / GP32
        # ---------------------------------------------------------------
        ("Watara", "Watara Supervision", "Supervision", "Standard White", "Standard", "high", 60, 140),
        ("Bit Corp", "Gamate", "Gamate", "Standard Gray", "Standard", "high", 80, 180),
        ("Gamepark", "GP32", "GP32", "Standard Blue/Silver", "Standard", "high", 90, 200),

        # ---------------------------------------------------------------
        # Modern Retro Handhelds — additional
        # ---------------------------------------------------------------
        ("Anbernic", "Anbernic RG556", "RG556", "Space Gray", "Modded/Custom", "mid", 80, 100),
        ("Anbernic", "Anbernic RG353M", "RG353M", "Silver Metal", "Modded/Custom", "mid", 70, 90),
        ("Miyoo", "Miyoo Mini Plus v4", "Miyoo Mini Plus", "Transparent Blue", "Modded/Custom", "mid", 60, 75),
        ("Retroid", "Retroid Pocket 4 Pro", "Retroid Pocket 4 Pro", "Black 8GB", "Modded/Custom", "mid", 90, 110),
        ("Trimui", "Trimui Smart Pro", "Trimui Smart Pro", "Black", "Modded/Custom", "mid", 45, 60),
        ("AYN", "AYN Odin 2", "Odin 2", "Transparent Purple", "Modded/Custom", "mid", 70, 90),
        ("Powkiddy", "Powkiddy RGB30", "RGB30", "Transparent Purple", "Modded/Custom", "standard", 30, 40),

        # ---------------------------------------------------------------
        # Tiger Electronics LCD Handhelds (vintage)
        # ---------------------------------------------------------------
        ("Tiger", "Tiger Electronics X-Men LCD", "Tiger LCD", "X-Men (1991)", "Standard", "mid", 25, 60),
        ("Tiger", "Tiger Electronics Street Fighter II LCD", "Tiger LCD", "Street Fighter II (1992)", "Standard", "mid", 30, 70),
        ("Tiger", "Tiger Electronics Sonic 3 LCD", "Tiger LCD", "Sonic 3 (1994)", "Standard", "mid", 25, 55),
        ("Tiger", "Tiger R-Zone", "R-Zone", "Standard (Head-Mounted)", "Standard", "mid", 40, 95),

        # ---------------------------------------------------------------
        # Nintendo Game Boy DMG-01 — additional Play It Loud / Special
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy DMG-01 Play It Loud White", "Game Boy", "Play It Loud White", "Limited Color", "high", 60, 130),
        ("Nintendo", "Game Boy DMG-01 Play It Loud Blue", "Game Boy", "Play It Loud Blue", "Limited Color", "high", 65, 135),
        ("Nintendo", "Game Boy DMG-01 Play It Loud Ice Blue", "Game Boy", "Play It Loud Ice Blue", "Limited Color", "high", 70, 145),
        ("Nintendo", "Game Boy DMG-01 Manchester United", "Game Boy", "Manchester United (UK)", "Special Edition", "high", 110, 230),
        ("Nintendo", "Game Boy DMG-01 Famitsu Model-F", "Game Boy", "Famitsu 500 Model-F Clear Skeleton (Japan)", "Japan Exclusive", "grail", 350, 700),
        ("Nintendo", "Game Boy DMG-01 Bros. Bundle", "Game Boy", "Tetris + Game Boy Bros. Bundle", "Console Bundle", "mid", 50, 110),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Pocket — additional colors
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Pocket Red", "Game Boy Pocket", "Red", "Standard", "mid", 35, 75),
        ("Nintendo", "Game Boy Pocket Green", "Game Boy Pocket", "Green", "Standard", "mid", 35, 75),
        ("Nintendo", "Game Boy Pocket Yellow", "Game Boy Pocket", "Yellow", "Standard", "mid", 35, 75),
        ("Nintendo", "Game Boy Pocket Pink", "Game Boy Pocket", "Pink", "Standard", "mid", 38, 78),
        ("Nintendo", "Game Boy Pocket Black", "Game Boy Pocket", "Black", "Standard", "mid", 35, 75),
        ("Nintendo", "Game Boy Pocket Gold", "Game Boy Pocket", "Gold Toys R Us (Japan)", "Japan Exclusive", "high", 95, 190),
        ("Nintendo", "Game Boy Pocket Famitsu", "Game Boy Pocket", "Famitsu Model-F Clear (Japan)", "Japan Exclusive", "grail", 220, 440),
        ("Nintendo", "Game Boy Pocket Hello Kitty", "Game Boy Pocket", "Hello Kitty Pink (Japan)", "Japan Exclusive", "high", 110, 220),
        ("Nintendo", "Game Boy Pocket ANA Blue", "Game Boy Pocket", "ANA Airlines Blue (Japan)", "Japan Exclusive", "high", 130, 260),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Light — additional (Japan only)
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Light Astro Boy", "Game Boy Light", "Astro Boy Clear Yellow (Japan)", "Japan Exclusive", "grail", 280, 550),
        ("Nintendo", "Game Boy Light Famitsu", "Game Boy Light", "Famitsu Skeleton (Japan)", "Japan Exclusive", "grail", 300, 600),
        ("Nintendo", "Game Boy Light Tezuka Osamu World Shop", "Game Boy Light", "Tezuka Osamu Clear (Japan)", "Japan Exclusive", "grail", 260, 520),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Color — more variants
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Color Midnight Blue", "Game Boy Color", "Midnight Blue", "Standard", "mid", 38, 80),
        ("Nintendo", "Game Boy Color Clear", "Game Boy Color", "Neotones Clear/Ice", "Limited Color", "high", 65, 140),
        ("Nintendo", "Game Boy Color Toys R Us Gold", "Game Boy Color", "Toys R Us Gold (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Nintendo", "Game Boy Color Lawson", "Game Boy Color", "Lawson Aqua Blue (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Game Boy Color ANA Clear Blue", "Game Boy Color", "ANA Airlines Clear Blue (Japan)", "Japan Exclusive", "high", 130, 260),
        ("Nintendo", "Game Boy Color Jusco Clear", "Game Boy Color", "Jusco Clear (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Nintendo", "Game Boy Color Tsutaya Clear Blue", "Game Boy Color", "Tsutaya Clear Blue (Japan)", "Japan Exclusive", "high", 110, 220),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Advance — more variants
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Advance Black", "Game Boy Advance", "Black", "Standard", "mid", 45, 100),
        ("Nintendo", "Game Boy Advance Fuchsia", "Game Boy Advance", "Fuchsia Pink", "Standard", "mid", 48, 105),
        ("Nintendo", "Game Boy Advance Gold", "Game Boy Advance", "Gold (Japan)", "Japan Exclusive", "high", 85, 175),
        ("Nintendo", "Game Boy Advance Midnight Blue", "Game Boy Advance", "Midnight Blue (Japan)", "Japan Exclusive", "high", 80, 170),
        ("Nintendo", "Game Boy Advance Toys R Us Transparent Red", "Game Boy Advance", "Toys R Us Transparent Red", "Special Edition", "high", 110, 240),
        ("Nintendo", "Game Boy Advance Mario", "Game Boy Advance", "Mario Red (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Game Boy Advance Latias/Latios", "Game Boy Advance", "Pokemon Center Latias/Latios (Japan)", "Japan Exclusive", "grail", 180, 380),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Advance SP — more variants
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Advance SP Pearl Green", "Game Boy Advance SP", "Pearl Green AGS-001", "Standard", "mid", 58, 120),
        ("Nintendo", "Game Boy Advance SP Gold", "Game Boy Advance SP", "Gold AGS-001 (Japan)", "Japan Exclusive", "high", 80, 170),
        ("Nintendo", "Game Boy Advance SP Zelda Minish Cap", "Game Boy Advance SP", "Zelda Minish Cap Gold (EU)", "Special Edition", "high", 140, 300),
        ("Nintendo", "Game Boy Advance SP Who Are You?", "Game Boy Advance SP", "Who Are You? Crystal (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Game Boy Advance SP Naruto", "Game Boy Advance SP", "Naruto Orange (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Nintendo", "Game Boy Advance SP Rayquaza", "Game Boy Advance SP", "Pokemon Center Rayquaza Green (Japan)", "Japan Exclusive", "grail", 260, 520),
        ("Nintendo", "Game Boy Advance SP Venusaur", "Game Boy Advance SP", "Pokemon Center Venusaur Green (Japan)", "Japan Exclusive", "grail", 240, 480),
        ("Nintendo", "Game Boy Advance SP Charizard", "Game Boy Advance SP", "Pokemon Center Charizard Red/Orange (Japan)", "Japan Exclusive", "grail", 270, 540),
        ("Nintendo", "Game Boy Advance SP Pichu Bros", "Game Boy Advance SP", "Pokemon Center Pichu Bros Silver (Japan)", "Japan Exclusive", "grail", 230, 460),
        ("Nintendo", "Game Boy Advance SP Classic NES Gold", "Game Boy Advance SP", "Classic NES Gold Limited", "Special Edition", "high", 140, 290),

        # ---------------------------------------------------------------
        # Nintendo Game Boy Micro — additional faceplates
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Micro Pink", "Game Boy Micro", "Pink", "Standard", "high", 140, 290),
        ("Nintendo", "Game Boy Micro Green", "Game Boy Micro", "Green", "Standard", "high", 140, 290),
        ("Nintendo", "Game Boy Micro Mother 3 Deluxe Box", "Game Boy Micro", "Mother 3 Deluxe Box Red/Blue (Japan)", "Japan Exclusive", "grail", 350, 680),
        ("Nintendo", "Game Boy Micro Happy Mario Faceplate", "Game Boy Micro", "Happy Mario 20th Anniversary Faceplate (Japan)", "Japan Exclusive", "high", 180, 360),

        # ---------------------------------------------------------------
        # Nintendo DS Family — more variants
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo DS Original Blue", "Nintendo DS", "Electric Blue (Phat)", "Standard", "standard", 25, 55),
        ("Nintendo", "Nintendo DS Original Red", "Nintendo DS", "Red (Phat)", "Standard", "standard", 25, 55),
        ("Nintendo", "Nintendo DS Lite Ice Blue", "Nintendo DS Lite", "Ice Blue", "Standard", "mid", 30, 65),
        ("Nintendo", "Nintendo DS Lite Jet Black", "Nintendo DS Lite", "Jet Black", "Standard", "standard", 25, 55),
        ("Nintendo", "Nintendo DS Lite Onyx Black", "Nintendo DS Lite", "Onyx Black/Blue", "Standard", "mid", 30, 65),
        ("Nintendo", "Nintendo DS Lite Coral Pink", "Nintendo DS Lite", "Coral Pink", "Standard", "mid", 30, 65),
        ("Nintendo", "Nintendo DS Lite Guitar Hero Bundle", "Nintendo DS Lite", "Guitar Hero Bundle Silver", "Console Bundle", "high", 70, 150),
        ("Nintendo", "Nintendo DS Lite Gold Zelda", "Nintendo DS Lite", "Triforce Gold Zelda (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Nintendo DS Lite Love Plus+", "Nintendo DS Lite", "Love Plus+ Nene Pink (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Nintendo", "Nintendo DS Lite Dragon Quest IX", "Nintendo DS Lite", "Dragon Quest IX Slime Silver (Japan)", "Japan Exclusive", "high", 90, 190),
        ("Nintendo", "Nintendo DSi Pokemon Black", "Nintendo DSi", "Pokemon Black Reshiram/Zekrom", "Special Edition", "high", 90, 190),
        ("Nintendo", "Nintendo DSi LL Dragon Quest 25th", "Nintendo DSi XL", "Dragon Quest 25th Anniversary (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Nintendo", "Nintendo DSi Lime Green", "Nintendo DSi", "Lime Green", "Standard", "mid", 35, 70),
        ("Nintendo", "Nintendo DSi Pink", "Nintendo DSi", "Metallic Pink", "Standard", "mid", 30, 65),

        # ---------------------------------------------------------------
        # Nintendo 3DS Family — more special editions
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo 3DS Midnight Purple", "Nintendo 3DS", "Midnight Purple", "Standard", "mid", 60, 130),
        ("Nintendo", "Nintendo 3DS Kingdom Hearts 3D DDD", "Nintendo 3DS", "Kingdom Hearts Dream Drop Distance Silver (Japan)", "Japan Exclusive", "high", 150, 320),
        ("Nintendo", "Nintendo 3DS Monster Hunter 3G", "Nintendo 3DS", "Monster Hunter 3G White (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Nintendo", "Nintendo 3DS XL Red/Black", "Nintendo 3DS XL", "Red/Black", "Standard", "mid", 65, 140),
        ("Nintendo", "Nintendo 3DS XL Pikachu Yellow", "Nintendo 3DS XL", "Pikachu Yellow Limited", "Special Edition", "high", 150, 320),
        ("Nintendo", "Nintendo 3DS XL Pokemon XY Blue", "Nintendo 3DS XL", "Pokemon X and Y Blue", "Special Edition", "high", 120, 250),
        ("Nintendo", "Nintendo 3DS XL Year of Luigi", "Nintendo 3DS XL", "Year of Luigi Green (NA)", "Special Edition", "high", 130, 270),
        ("Nintendo", "Nintendo 3DS XL NES Edition", "Nintendo 3DS XL", "NES Retro Edition", "Special Edition", "high", 120, 250),
        ("Nintendo", "New Nintendo 3DS Cover Plates Kisekae", "New Nintendo 3DS", "Cover Plate White (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Nintendo", "New Nintendo 3DS XL Pikachu Yellow", "New Nintendo 3DS XL", "Pikachu Yellow (NA)", "Special Edition", "high", 140, 300),
        ("Nintendo", "New Nintendo 3DS XL Lime Green", "New Nintendo 3DS XL", "Lime Green (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "New Nintendo 3DS XL Pearl White", "New Nintendo 3DS XL", "Pearl White (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Nintendo", "New Nintendo 3DS XL Solgaleo/Lunala", "New Nintendo 3DS XL", "Pokemon Sun/Moon Gold (NA)", "Special Edition", "high", 130, 270),
        ("Nintendo", "New Nintendo 3DS XL Metroid Samus", "New Nintendo 3DS XL", "Metroid Samus Returns (NA)", "Special Edition", "high", 160, 340),
        ("Nintendo", "New Nintendo 3DS XL Minecraft", "New Nintendo 3DS XL", "Minecraft Creeper Green (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Nintendo 2DS Red/White", "Nintendo 2DS", "Red/White Wedge", "Standard", "standard", 25, 55),
        ("Nintendo", "Nintendo 2DS Blue/Black", "Nintendo 2DS", "Blue/Black Wedge", "Standard", "standard", 25, 55),
        ("Nintendo", "Nintendo 2DS Transparent Blue", "Nintendo 2DS", "Transparent Blue Crystal", "Limited Color", "mid", 40, 80),
        ("Nintendo", "Nintendo 2DS Transparent Red", "Nintendo 2DS", "Transparent Red Crystal", "Limited Color", "mid", 40, 80),
        ("Nintendo", "Nintendo 2DS Pokemon Sun/Moon Edition", "Nintendo 2DS", "Pokemon Sun/Moon Orange/Blue (NA)", "Special Edition", "mid", 55, 110),
        ("Nintendo", "New Nintendo 2DS XL Black/Turquoise", "New Nintendo 2DS XL", "Black/Turquoise", "Standard", "mid", 60, 120),
        ("Nintendo", "New Nintendo 2DS XL White/Orange", "New Nintendo 2DS XL", "White/Orange", "Standard", "mid", 60, 120),
        ("Nintendo", "New Nintendo 2DS XL Pikachu Edition", "New Nintendo 2DS XL", "Pikachu Yellow (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Nintendo", "New Nintendo 2DS XL Dragon Quest Liquid Metal", "New Nintendo 2DS XL", "Dragon Quest Metal Slime (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Nintendo", "New Nintendo 2DS XL Minecraft Creeper", "New Nintendo 2DS XL", "Minecraft Creeper (Japan)", "Japan Exclusive", "high", 110, 230),

        # ---------------------------------------------------------------
        # Nintendo Switch Lite — more limited editions
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo Switch Lite Yellow", "Switch Lite", "Yellow", "Standard", "mid", 50, 95),
        ("Nintendo", "Nintendo Switch Lite Gray", "Switch Lite", "Gray", "Standard", "mid", 50, 95),
        ("Nintendo", "Nintendo Switch Lite Turquoise", "Switch Lite", "Turquoise", "Standard", "mid", 50, 95),
        ("Nintendo", "Nintendo Switch Lite Blue", "Switch Lite", "Blue", "Standard", "mid", 55, 100),
        ("Nintendo", "Nintendo Switch Lite Hyrule Edition", "Switch Lite", "Hyrule Gold/Green", "Special Edition", "high", 95, 175),
        ("Nintendo", "Nintendo Switch Lite Animal Crossing", "Switch Lite", "Animal Crossing Timmy & Tommy Aloha", "Special Edition", "high", 85, 160),

        # ---------------------------------------------------------------
        # Sony PSP — more variants
        # ---------------------------------------------------------------
        ("Sony", "PSP-1000 Value Pack Silver", "PSP-1000", "Silver Value Pack", "Console Bundle", "mid", 45, 95),
        ("Sony", "PSP-1000 Giga Pack White", "PSP-1000", "Ceramic White Giga Pack", "Console Bundle", "mid", 50, 100),
        ("Sony", "PSP-2000 Lavender Purple", "PSP-2000", "Lavender Purple (Japan)", "Japan Exclusive", "mid", 45, 90),
        ("Sony", "PSP-2000 Rose Pink", "PSP-2000", "Rose Pink (Japan)", "Japan Exclusive", "mid", 45, 90),
        ("Sony", "PSP-2000 Mint Green", "PSP-2000", "Mint Green (Japan)", "Japan Exclusive", "mid", 50, 100),
        ("Sony", "PSP-2000 Felicia Blue", "PSP-2000", "Felicia Blue (Japan)", "Japan Exclusive", "mid", 50, 100),
        ("Sony", "PSP-3000 Blossom Pink", "PSP-3000", "Blossom Pink (Japan)", "Japan Exclusive", "mid", 45, 90),
        ("Sony", "PSP-3000 Spirited Green", "PSP-3000", "Spirited Green (Japan)", "Japan Exclusive", "mid", 50, 100),
        ("Sony", "PSP-3000 Bright Yellow", "PSP-3000", "Bright Yellow (Japan)", "Japan Exclusive", "mid", 50, 100),
        ("Sony", "PSP-3000 Final Fantasy VII 10th", "PSP-3000", "Final Fantasy VII 10th Anniversary Silver (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Sony", "PSP-3000 Dissidia Final Fantasy", "PSP-3000", "Dissidia Final Fantasy 20th Anniversary (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Sony", "PSP-3000 Gundam vs Gundam", "PSP-3000", "Gundam vs Gundam Red/Gold (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Sony", "PSP Go White", "PSP Go", "Pearl White (N-1000)", "Standard", "high", 90, 185),
        ("Sony", "PSP-3000 One Piece Romance Dawn", "PSP-3000", "One Piece Romance Dawn Gold (Japan)", "Japan Exclusive", "high", 115, 240),

        # ---------------------------------------------------------------
        # Sony PS Vita — more variants
        # ---------------------------------------------------------------
        ("Sony", "PS Vita OLED Red", "PS Vita 1000", "Cosmic Red OLED (Japan)", "Japan Exclusive", "high", 140, 280),
        ("Sony", "PS Vita Slim Pink/Black", "PS Vita 2000", "Pink/Black Slim (Japan)", "Japan Exclusive", "high", 140, 280),
        ("Sony", "PS Vita Slim Silver/White", "PS Vita 2000", "Silver/White Slim (Japan)", "Japan Exclusive", "high", 130, 260),
        ("Sony", "PS Vita Slim Glacier White", "PS Vita 2000", "Glacier White (NA)", "Standard", "high", 110, 220),
        ("Sony", "PS Vita Slim Gundam Breaker", "PS Vita 2000", "Gundam Breaker Starter Pack (Japan)", "Japan Exclusive", "high", 160, 310),
        ("Sony", "PS Vita Slim Final Fantasy X/X-2", "PS Vita 2000", "Final Fantasy X/X-2 HD Resolution Blue (Japan)", "Japan Exclusive", "high", 170, 330),
        ("Sony", "PS Vita Slim Sword Art Online", "PS Vita 2000", "Sword Art Online Hollow Fragment White (Japan)", "Japan Exclusive", "high", 180, 350),
        ("Sony", "PS Vita Slim Soul Sacrifice", "PS Vita 2000", "Soul Sacrifice Red (Japan)", "Japan Exclusive", "high", 170, 330),
        ("Sony", "PS Vita OLED Metal Gear Solid HD", "PS Vita 1000", "Metal Gear Solid HD Camo Gray (Japan)", "Japan Exclusive", "high", 180, 350),
        ("Sony", "PS Vita Slim Minecraft", "PS Vita 2000", "Minecraft Special Edition (Japan)", "Japan Exclusive", "high", 140, 280),

        # ---------------------------------------------------------------
        # Sega Game Gear — more
        # ---------------------------------------------------------------
        ("Sega", "Game Gear Red", "Game Gear", "Red (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Sega", "Game Gear Kids Gear", "Game Gear", "Kids Gear Blue/Purple (Japan)", "Japan Exclusive", "high", 90, 190),
        ("Sega", "Game Gear Majesco Reissue", "Game Gear", "Majesco Core System Reissue (NA)", "Standard", "mid", 40, 85),
        ("Sega", "Game Gear Micro Yellow", "Game Gear Micro", "Micro Yellow (Japan 2020)", "Japan Exclusive", "mid", 55, 90),
        ("Sega", "Game Gear Micro Red", "Game Gear Micro", "Micro Red (Japan 2020)", "Japan Exclusive", "mid", 55, 90),
        ("Sega", "Game Gear Micro 4-Color Set Big Window", "Game Gear Micro", "4-Color Set with Big Window Micro (Japan)", "Japan Exclusive", "high", 200, 350),

        # ---------------------------------------------------------------
        # Neo Geo Pocket Color — more
        # ---------------------------------------------------------------
        ("SNK", "Neo Geo Pocket Color Carbon Black", "Neo Geo Pocket Color", "Carbon Black", "Standard", "high", 80, 170),
        ("SNK", "Neo Geo Pocket Color Crystal Yellow", "Neo Geo Pocket Color", "Crystal Yellow", "Limited Color", "high", 100, 210),
        ("SNK", "Neo Geo Pocket Color Stone Blue", "Neo Geo Pocket Color", "Stone Blue", "Standard", "high", 85, 180),
        ("SNK", "Neo Geo Pocket Color Solid Silver", "Neo Geo Pocket Color", "Solid Silver", "Standard", "high", 85, 180),
        ("SNK", "Neo Geo Pocket (Monochrome)", "Neo Geo Pocket", "Platinum Blue (Monochrome)", "Standard", "high", 90, 190),
        ("SNK", "Neo Geo Pocket Selection Vol.1 Switch", "Switch", "Neo Geo Pocket Color Selection Vol.1 (Game)", "Standard", "mid", 25, 40),

        # ---------------------------------------------------------------
        # Bandai WonderSwan — more
        # ---------------------------------------------------------------
        ("Bandai", "WonderSwan Original Silver", "WonderSwan", "Silver Metallic (Japan)", "Japan Exclusive", "high", 55, 120),
        ("Bandai", "WonderSwan Skeleton Black", "WonderSwan", "Skeleton Black (Japan)", "Japan Exclusive", "high", 60, 130),
        ("Bandai", "WonderSwan Color Crystal Orange", "WonderSwan Color", "Crystal Orange (Japan)", "Japan Exclusive", "high", 65, 140),
        ("Bandai", "WonderSwan Color Crystal Black", "WonderSwan Color", "Crystal Black (Japan)", "Japan Exclusive", "high", 65, 140),
        ("Bandai", "WonderSwan One Piece Limited", "WonderSwan Color", "One Piece Luffy Blue (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Bandai", "SwanCrystal Clear Black", "SwanCrystal", "Clear Black (Japan)", "Japan Exclusive", "high", 70, 150),

        # ---------------------------------------------------------------
        # Tamagotchi — additional virtual pets
        # ---------------------------------------------------------------
        ("Bandai", "Tamagotchi Connection V1", "Tamagotchi", "Connection V1 Blue", "Standard", "standard", 20, 45),
        ("Bandai", "Tamagotchi Connection V2", "Tamagotchi", "Connection V2 Purple", "Standard", "standard", 20, 45),
        ("Bandai", "Tamagotchi Connection V4", "Tamagotchi", "Connection V4", "Standard", "mid", 35, 75),
        ("Bandai", "Tamagotchi Connection V5 Celebrity", "Tamagotchi", "Connection V5 Celebrity", "Standard", "mid", 40, 85),
        ("Bandai", "Tamagotchi Connection V6 Music Star Pink", "Tamagotchi", "V6 Music Star Pink", "Standard", "mid", 50, 105),
        ("Bandai", "Tamagotchi Friends", "Tamagotchi", "Tamagotchi Friends Blue", "Standard", "standard", 18, 40),
        ("Bandai", "Tamagotchi iD Blue", "Tamagotchi", "iD Blue (Japan)", "Japan Exclusive", "mid", 70, 150),
        ("Bandai", "Tamagotchi iD L 15th Anniversary", "Tamagotchi", "iD L 15th Anniversary (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Bandai", "Tamagotchi 4U+ Anniversary", "Tamagotchi", "4U+ Anniversary White (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Bandai", "Tamagotchi m!x Dream", "Tamagotchi", "m!x Dream Pink (Japan)", "Japan Exclusive", "mid", 55, 110),
        ("Bandai", "Tamagotchi Meets Pastel", "Tamagotchi", "Meets Pastel White (Japan)", "Japan Exclusive", "mid", 60, 120),
        ("Bandai", "Tamagotchi ON Magic Purple", "Tamagotchi", "ON Magic Purple", "Standard", "mid", 55, 100),
        ("Bandai", "Tamagotchi ON Fairy Pink", "Tamagotchi", "ON Fairy Pink", "Standard", "mid", 55, 100),
        ("Bandai", "Tamagotchi Pix Nature Green", "Tamagotchi", "Pix Nature Green", "Standard", "mid", 45, 80),
        ("Bandai", "Tamagotchi Pix Party Confetti", "Tamagotchi", "Pix Party Confetti Pink", "Standard", "mid", 50, 90),
        ("Bandai", "Tamagotchi Smart NiziU Collab", "Tamagotchi", "Smart NiziU Special Set (Japan)", "Japan Exclusive", "high", 80, 160),
        ("Bandai", "Tamagotchi Uni Pink", "Tamagotchi", "Uni Pink", "Standard", "mid", 45, 80),
        ("Bandai", "Tamagotchi Nano Eevee", "Tamagotchi", "Nano Eevee Colorful Friends", "Special Edition", "mid", 30, 55),
        ("Bandai", "Tamagotchi Nano Demon Slayer", "Tamagotchi", "Nano Demon Slayer Tanjiro", "Special Edition", "mid", 30, 55),
        ("Bandai", "Tamagotchi Nano One Piece", "Tamagotchi", "Nano One Piece Going Merry", "Special Edition", "mid", 30, 55),
        ("Bandai", "Tamagotchi Nano Star Wars R2-D2", "Tamagotchi", "Nano Star Wars R2-D2 Blue", "Special Edition", "mid", 28, 50),
        ("Bandai", "Tamagotchi Nano Harry Potter", "Tamagotchi", "Nano Harry Potter Hogwarts", "Special Edition", "mid", 28, 50),
        ("Bandai", "Digimon Virtual Pet V1 Brown", "Digimon", "Digivice V1 Original Brown", "Standard", "high", 80, 170),
        ("Bandai", "Digimon Virtual Pet V2 Black", "Digimon", "Digivice V2 Black", "Standard", "high", 80, 170),
        ("Bandai", "Digimon Pendulum Original", "Digimon", "Digimon Pendulum 1.0 Nature Spirits (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Bandai", "Digimon Vital Bracelet BE", "Digimon", "Vital Bracelet BE Black", "Standard", "mid", 45, 80),
        ("Bandai", "Digimon D-3 Digivice", "Digimon", "D-3 Digivice Blue (Japan)", "Japan Exclusive", "high", 90, 190),
        ("Bandai", "Giga Pet Compu Kitty", "Giga Pets", "Compu Kitty Original", "Standard", "mid", 25, 55),
        ("Bandai", "Nano Baby", "Nano Baby", "Nano Baby Pink", "Standard", "mid", 30, 65),

        # ---------------------------------------------------------------
        # Game & Watch — more classics
        # ---------------------------------------------------------------
        ("Nintendo", "Game & Watch Chef (FP-24)", "Game & Watch", "Chef Wide Screen (1981)", "Standard", "high", 85, 200),
        ("Nintendo", "Game & Watch Turtle Bridge (TL-28)", "Game & Watch", "Turtle Bridge Wide Screen (1982)", "Standard", "high", 90, 210),
        ("Nintendo", "Game & Watch Donkey Kong Jr (DJ-101)", "Game & Watch", "Donkey Kong Jr New Wide Screen (1982)", "Standard", "high", 70, 160),
        ("Nintendo", "Game & Watch Popeye (PP-23)", "Game & Watch", "Popeye Wide Screen (1981)", "Standard", "high", 80, 190),
        ("Nintendo", "Game & Watch Mario Cement Factory (CM-72)", "Game & Watch", "Mario's Cement Factory Table Top (1983)", "Standard", "high", 120, 280),
        ("Nintendo", "Game & Watch Boxing (BX-301)", "Game & Watch", "Boxing Micro VS System (1984)", "Standard", "high", 110, 260),
        ("Nintendo", "Game & Watch Lifeboat (TC-58)", "Game & Watch", "Life Boat Multi Screen (1983)", "Standard", "high", 95, 230),
        ("Nintendo", "Game & Watch Climber (DR-106)", "Game & Watch", "Climber Crystal Screen (1986)", "Standard", "high", 130, 300),
        ("Nintendo", "Game & Watch Balloon Fight (BF-107)", "Game & Watch", "Balloon Fight Crystal Screen (1986)", "Standard", "high", 140, 320),
        ("Nintendo", "Game & Watch Super Mario Bros (YM-801)", "Game & Watch", "Super Mario Bros Crystal Screen (1986)", "Standard", "grail", 200, 450),
        ("Nintendo", "Game & Watch Zelda Adventure (ZL-65) Original", "Game & Watch", "Zelda Adventure of Link Multi Screen (1989)", "Standard", "high", 110, 250),
        ("Nintendo", "Game & Watch Black Jack (BJ-60)", "Game & Watch", "Black Jack Multi Screen (1985)", "Standard", "high", 95, 220),

        # ---------------------------------------------------------------
        # Tiger Electronics LCD — more handhelds
        # ---------------------------------------------------------------
        ("Tiger", "Tiger Electronics Batman LCD", "Tiger LCD", "Batman (1989)", "Standard", "mid", 25, 60),
        ("Tiger", "Tiger Electronics Spider-Man LCD", "Tiger LCD", "Spider-Man (1990)", "Standard", "mid", 25, 55),
        ("Tiger", "Tiger Electronics Double Dragon LCD", "Tiger LCD", "Double Dragon (1989)", "Standard", "mid", 25, 55),
        ("Tiger", "Tiger Electronics Mega Man 2 LCD", "Tiger LCD", "Mega Man 2 (1990)", "Standard", "mid", 30, 65),
        ("Tiger", "Tiger Electronics Castlevania II LCD", "Tiger LCD", "Castlevania II (1988)", "Standard", "mid", 30, 65),
        ("Tiger", "Tiger Electronics Gauntlet LCD", "Tiger LCD", "Gauntlet (1990)", "Standard", "mid", 25, 55),
        ("Tiger", "Tiger Electronics Mortal Kombat LCD", "Tiger LCD", "Mortal Kombat (1993)", "Standard", "mid", 25, 55),
        ("Tiger", "Tiger Electronics Power Rangers LCD", "Tiger LCD", "Power Rangers (1994)", "Standard", "mid", 20, 50),
        ("Tiger", "Tiger Electronics Jurassic Park LCD", "Tiger LCD", "Jurassic Park (1993)", "Standard", "mid", 25, 55),
        ("Tiger", "Tiger Electronics Star Wars LCD", "Tiger LCD", "Star Wars (1997)", "Standard", "mid", 25, 55),
        ("Tiger", "Tiger R-Zone XPG", "R-Zone", "XPG Portable (Head Gear)", "Standard", "mid", 45, 100),
        ("Tiger", "Tiger R-Zone Super Screen", "R-Zone", "Super Screen (Tabletop)", "Standard", "mid", 40, 90),

        # ---------------------------------------------------------------
        # Modern Retro Handhelds — more models
        # ---------------------------------------------------------------
        ("Anbernic", "Anbernic RG35XX H", "RG35XX H", "Transparent White", "Modded/Custom", "mid", 55, 70),
        ("Anbernic", "Anbernic RG35XX SP", "RG35XX SP", "Transparent Purple Clamshell", "Modded/Custom", "mid", 60, 75),
        ("Anbernic", "Anbernic RG405M", "RG405M", "Metal Silver", "Modded/Custom", "mid", 75, 95),
        ("Anbernic", "Anbernic RG405V", "RG405V", "Wooden Grain", "Modded/Custom", "mid", 70, 90),
        ("Anbernic", "Anbernic RG505", "RG505", "Gray", "Modded/Custom", "mid", 70, 90),
        ("Anbernic", "Anbernic RG28XX", "RG28XX", "Transparent Purple", "Modded/Custom", "standard", 25, 35),
        ("Anbernic", "Anbernic RG Cube", "RG Cube", "Transparent Purple", "Modded/Custom", "mid", 80, 100),
        ("Retroid", "Retroid Pocket 2S", "Retroid Pocket 2S", "Black", "Modded/Custom", "mid", 50, 65),
        ("Retroid", "Retroid Pocket 3", "Retroid Pocket 3", "Retro Gray", "Modded/Custom", "mid", 60, 80),
        ("Retroid", "Retroid Pocket Flip", "Retroid Pocket Flip", "Black Clamshell", "Modded/Custom", "mid", 65, 85),
        ("Retroid", "Retroid Pocket Mini", "Retroid Pocket Mini", "White Mini", "Modded/Custom", "mid", 40, 55),
        ("Retroid", "Retroid Pocket 5", "Retroid Pocket 5", "Black", "Modded/Custom", "mid", 85, 105),
        ("Miyoo", "Miyoo A30", "Miyoo A30", "White", "Modded/Custom", "mid", 35, 45),
        ("Trimui", "Trimui Smart", "Trimui Smart", "Gray Original", "Modded/Custom", "standard", 20, 30),
        ("Trimui", "Trimui Brick", "Trimui Brick", "Black Vertical", "Modded/Custom", "standard", 25, 35),
        ("Powkiddy", "Powkiddy V90", "V90", "Black Clamshell", "Modded/Custom", "standard", 18, 25),
        ("Powkiddy", "Powkiddy X55", "X55", "Transparent Blue", "Modded/Custom", "mid", 50, 65),
        ("Powkiddy", "Powkiddy RGB10 Max 3", "RGB10 Max 3", "White", "Modded/Custom", "mid", 55, 70),
        ("AYN", "AYN Odin 2 Mini", "Odin 2 Mini", "White", "Modded/Custom", "mid", 60, 80),
        ("AYN", "AYN Odin 2 Max", "Odin 2 Max", "Black", "Modded/Custom", "high", 100, 130),
        ("Analogue", "Analogue Pocket Glow in the Dark", "Analogue Pocket", "Glow in the Dark", "Limited Color", "grail", 350, 450),
        ("Analogue", "Analogue Pocket Aluminium", "Analogue Pocket", "Aluminium Natural", "Limited Color", "grail", 400, 520),

        # ---------------------------------------------------------------
        # Misc Vintage Handhelds
        # ---------------------------------------------------------------
        ("Entex", "Entex Select-A-Game", "Select-A-Game", "Standard White", "Standard", "high", 60, 140),
        ("Entex", "Entex Adventure Vision", "Adventure Vision", "Standard Black", "Standard", "grail", 200, 450),
        ("Mattel", "Mattel Auto Race", "Auto Race", "Electronic Handheld (1976)", "Standard", "high", 80, 180),
        ("Mattel", "Mattel Football", "Football", "Electronic Handheld (1977)", "Standard", "high", 60, 140),
        ("Coleco", "Coleco Head-to-Head Football", "Head-to-Head", "Electronic Tabletop (1980)", "Standard", "high", 70, 160),
        ("Coleco", "Coleco Donkey Kong Mini Arcade", "Mini Arcade", "Tabletop Mini Arcade (1982)", "Standard", "high", 90, 200),
        ("Coleco", "Coleco Ms. Pac-Man Mini Arcade", "Mini Arcade", "Tabletop Mini Arcade (1982)", "Standard", "high", 80, 180),
        ("Tomy", "Tomy Tutor Play Computer", "Tutor", "Portable Computer (Japan)", "Japan Exclusive", "high", 70, 150),
        ("VTech", "VTech CreatiVision", "CreatiVision", "Standard", "Standard", "high", 80, 180),
        ("Palmtex", "Palmtex Super Micro", "Super Micro", "Standard Black", "Standard", "high", 90, 200),
        ("Konami", "Konami Hyperboy", "Hyperboy", "Game Boy Accessory Screen Magnifier", "Standard", "mid", 35, 70),

        # ---------------------------------------------------------------
        # Accessories — retro handheld accessories
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Camera Green", "Game Boy Camera", "Green Camera", "Standard", "mid", 30, 60),
        ("Nintendo", "Game Boy Camera Yellow", "Game Boy Camera", "Yellow Camera", "Standard", "mid", 30, 60),
        ("Nintendo", "Game Boy Camera Red", "Game Boy Camera", "Red Camera", "Standard", "mid", 30, 60),
        ("Nintendo", "Game Boy Camera Gold", "Game Boy Camera", "Gold Zelda Camera (Japan)", "Japan Exclusive", "high", 80, 160),
        ("Nintendo", "Game Boy Printer", "Game Boy Printer", "Standard", "Standard", "mid", 30, 65),
        ("Nintendo", "Game Boy Player GameCube", "Game Boy Player", "Silver GameCube Attachment", "Standard", "mid", 45, 90),
        ("Nintendo", "Game Boy Player GameCube Black", "Game Boy Player", "Black (Start-Up Disc + Unit)", "Standard", "high", 80, 160),
        ("Nintendo", "Super Game Boy SNES", "Super Game Boy", "Original SGB SNES/SFC Adapter", "Standard", "mid", 25, 50),
        ("Nintendo", "Super Game Boy 2 SFC", "Super Game Boy 2", "SFC Adapter with Link Port (Japan)", "Japan Exclusive", "mid", 40, 80),
        ("Sega", "Game Gear TV Tuner", "Game Gear", "TV Tuner Adapter", "Standard", "mid", 25, 55),
        ("Sega", "Game Gear Master Gear Converter", "Game Gear", "Master System Game Converter", "Standard", "mid", 30, 60),
        ("Nintendo", "e-Reader GBA", "e-Reader", "Original GBA Card Reader", "Standard", "mid", 25, 55),

        # ---------------------------------------------------------------
        # More Game & Watch classics & Crystal Screen
        # ---------------------------------------------------------------
        ("Nintendo", "Game & Watch Judge Green (IP-05)", "Game & Watch", "Judge Green Case (1980 Silver)", "Standard", "grail", 350, 900),
        ("Nintendo", "Game & Watch Flagman (FL-02)", "Game & Watch", "Flagman Silver Series (1980)", "Standard", "high", 120, 280),
        ("Nintendo", "Game & Watch Vermin (MT-03)", "Game & Watch", "Vermin Silver Series (1980)", "Standard", "high", 110, 260),
        ("Nintendo", "Game & Watch Helmet (CN-07)", "Game & Watch", "Helmet Gold Series (1981)", "Standard", "high", 95, 220),
        ("Nintendo", "Game & Watch Lion (LN-08)", "Game & Watch", "Lion Gold Series (1981)", "Standard", "high", 95, 220),
        ("Nintendo", "Game & Watch Egg (EG-26)", "Game & Watch", "Egg Wide Screen (1981)", "Standard", "high", 80, 190),
        ("Nintendo", "Game & Watch Tropical Fish (TF-104)", "Game & Watch", "Tropical Fish Crystal Screen (1985)", "Standard", "high", 140, 320),
        ("Nintendo", "Game & Watch Mario The Juggler (MB-108)", "Game & Watch", "Mario The Juggler Crystal Screen (1991)", "Standard", "grail", 250, 550),

        # ---------------------------------------------------------------
        # More Tiger LCD Handhelds
        # ---------------------------------------------------------------
        ("Tiger", "Tiger Electronics The Little Mermaid LCD", "Tiger LCD", "The Little Mermaid (1991)", "Standard", "mid", 20, 50),
        ("Tiger", "Tiger Electronics Ninja Gaiden LCD", "Tiger LCD", "Ninja Gaiden (1990)", "Standard", "mid", 25, 55),
        ("Tiger", "Tiger Electronics Altered Beast LCD", "Tiger LCD", "Altered Beast (1990)", "Standard", "mid", 25, 55),
        ("Tiger", "Tiger Electronics Home Alone LCD", "Tiger LCD", "Home Alone (1992)", "Standard", "mid", 20, 50),
        ("Tiger", "Tiger Electronics Wheel of Fortune LCD", "Tiger LCD", "Wheel of Fortune (1995)", "Standard", "standard", 15, 35),
        ("Tiger", "Tiger Electronics Pinball LCD", "Tiger LCD", "Pinball (1987)", "Standard", "mid", 25, 55),
        ("Tiger", "Tiger Electronics Super Simon", "Tiger LCD", "Super Simon (1979)", "Standard", "mid", 30, 65),

        # ---------------------------------------------------------------
        # More modern retro handhelds & Steam Deck-likes
        # ---------------------------------------------------------------
        ("Valve", "Steam Deck LCD 64GB", "Steam Deck", "64GB LCD", "Standard", "mid", 250, 300),
        ("Valve", "Steam Deck LCD 512GB", "Steam Deck", "512GB LCD Anti-Glare", "Standard", "mid", 350, 420),
        ("Valve", "Steam Deck OLED 512GB", "Steam Deck OLED", "512GB OLED", "Standard", "high", 400, 480),
        ("Valve", "Steam Deck OLED 1TB", "Steam Deck OLED", "1TB OLED Limited Edition", "Limited Color", "high", 480, 560),
        ("ASUS", "ASUS ROG Ally RC71L", "ROG Ally", "White Z1 Extreme", "Standard", "mid", 400, 480),
        ("Lenovo", "Lenovo Legion Go", "Legion Go", "Black 8.8-inch", "Standard", "mid", 380, 450),
        ("AYANEO", "AYANEO 2S", "AYANEO 2S", "Starry Black", "Modded/Custom", "mid", 500, 580),
        ("AYANEO", "AYANEO Air 1S", "AYANEO Air 1S", "Arctic White", "Modded/Custom", "mid", 350, 420),
        ("GPD", "GPD Win 4", "GPD Win 4", "Black 6-inch", "Modded/Custom", "mid", 450, 530),
        ("GPD", "GPD Win Mini", "GPD Win Mini", "Silver 7-inch", "Modded/Custom", "mid", 380, 450),

        # ---------------------------------------------------------------
        # More Atari / miscellaneous vintage
        # ---------------------------------------------------------------
        ("Atari", "Atari Lynx II McWill LCD Mod", "Atari Lynx II", "McWill LCD Modded", "Modded/Custom", "high", 150, 280),
        ("Sega", "Sega Nomad LCD Mod", "Sega Nomad", "LCD Screen Mod", "Modded/Custom", "high", 200, 380),
        ("NEC", "TurboExpress Capacitor Recapped", "TurboExpress", "Recapped/Restored (NA)", "Modded/Custom", "grail", 280, 520),
        ("Nintendo", "Game Boy Color FunnyPlaying Q5 IPS Mod", "Game Boy Color", "FunnyPlaying IPS V2 Modded", "Modded/Custom", "mid", 80, 120),
        ("Nintendo", "Game Boy DMG Backlight Mod", "Game Boy", "Biverted Backlight Modded", "Modded/Custom", "mid", 70, 110),
        ("Nintendo", "Game Boy Advance IPS V2 Mod", "Game Boy Advance", "IPS V2 Modded Shell", "Modded/Custom", "mid", 75, 115),

        # ---------------------------------------------------------------
        # More PSP/Vita JP exclusives
        # ---------------------------------------------------------------
        ("Sony", "PSP-3000 Tales of Versus", "PSP-3000", "Tales of Versus Felicia Blue (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Sony", "PSP-2000 Star Ocean White", "PSP-2000", "Star Ocean First Departure White (Japan)", "Japan Exclusive", "high", 90, 190),
        ("Sony", "PS Vita Slim Caligula Limited", "PS Vita 2000", "Caligula Limited Edition White (Japan)", "Japan Exclusive", "high", 160, 310),
        ("Sony", "PS Vita Slim Toukiden 2", "PS Vita 2000", "Toukiden 2 Gold (Japan)", "Japan Exclusive", "high", 170, 330),
        ("Sony", "PS Vita OLED Initial D", "PS Vita 1000", "Initial D Extreme Stage (Japan)", "Japan Exclusive", "high", 160, 310),

        # ---------------------------------------------------------------
        # More Nintendo DS/3DS limited editions
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo DS Lite Final Fantasy Crystal Chronicles", "Nintendo DS Lite", "Final Fantasy Crystal Chronicles (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Nintendo", "Nintendo DS Lite Dragon Ball Z Harukanaru", "Nintendo DS Lite", "Dragon Ball Z Orange (Japan)", "Japan Exclusive", "high", 90, 190),
        ("Nintendo", "Nintendo 3DS XL Disney Magical World", "Nintendo 3DS XL", "Disney Magical World Pink (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Nintendo", "New Nintendo 3DS XL Dragon Ball Z Extreme Butoden", "New Nintendo 3DS XL", "Dragon Ball Z Orange/Blue (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Nintendo", "New Nintendo 3DS XL Monster Hunter XX", "New Nintendo 3DS XL", "Monster Hunter XX Wolf (Japan)", "Japan Exclusive", "high", 140, 290),
        ("Nintendo", "New Nintendo 3DS XL Animal Crossing Happy Home", "New Nintendo 3DS XL", "Animal Crossing Happy Home Designer (NA)", "Special Edition", "high", 120, 250),
        ("Nintendo", "New Nintendo 2DS XL Mario Kart 7 Bundle", "New Nintendo 2DS XL", "Mario Kart 7 Lime Green (EU)", "Console Bundle", "mid", 70, 140),

        # ---------------------------------------------------------------
        # More GBC/GBA Japan exclusives & accessories
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Color Sakura Tamagotchi Pack", "Game Boy Color", "Sakura Pink Tamagotchi Bundle (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Nintendo", "Game Boy Color Kirby Dream Land 2 Yellow", "Game Boy Color", "Kirby Yellow (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Game Boy Advance SP Mawaru Made in Wario", "Game Boy Advance SP", "Mawaru Made in Wario Banana (Japan)", "Japan Exclusive", "high", 150, 310),
        ("Nintendo", "Game Boy Advance Wireless Adapter", "Game Boy Advance", "Wireless Adapter AGB-015", "Standard", "mid", 20, 40),
        ("Nintendo", "Game Boy Advance Link Cable", "Game Boy Advance", "Official Link Cable AGB-005", "Standard", "standard", 10, 20),
        ("Nintendo", "Game Boy Light (Pikachu Version)", "Game Boy Light", "Pikachu Yellow (Japan)", "Japan Exclusive", "grail", 350, 700),
        ("Nintendo", "Game Boy Pocket Extreme Green", "Game Boy Pocket", "Extreme Green (NA)", "Limited Color", "high", 85, 175),
        ("Nintendo", "Game Boy Color Cardcaptor Sakura 2", "Game Boy Color", "Cardcaptor Sakura Clear (Japan)", "Japan Exclusive", "grail", 240, 480),
        ("Sony", "PS Vita Slim Digimon Story Cyber Sleuth", "PS Vita 2000", "Digimon Story Cyber Sleuth White (Japan)", "Japan Exclusive", "high", 170, 330),
        ("Sony", "PS Vita Slim Phantasy Star Nova", "PS Vita 2000", "Phantasy Star Nova White (Japan)", "Japan Exclusive", "high", 160, 310),
        ("Sony", "PSP-3000 Valkyria Chronicles 3", "PSP-3000", "Valkyria Chronicles 3 Camo (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Sony", "PSP-2000 Final Fantasy VII Crisis Core Silver", "PSP-2000", "Final Fantasy VII CC Silver (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Nintendo", "Nintendo DS Lite Giratina Edition", "Nintendo DS Lite", "Pokemon Platinum Giratina (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Nintendo", "Nintendo 3DS Luigi 30th Anniversary", "Nintendo 3DS", "Luigi 30th Anniversary Green (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "New Nintendo 3DS XL Dragon Quest VIII", "New Nintendo 3DS XL", "Dragon Quest VIII Slime Blue (Japan)", "Japan Exclusive", "high", 140, 290),
        ("Bandai", "Tamagotchi Original Gen 1 Reissue 2018", "Tamagotchi", "Original Gen 1 Reissue (2018)", "Standard", "mid", 15, 30),
        ("Bandai", "Tamagotchi Original Gen 2 Reissue 2018", "Tamagotchi", "Original Gen 2 Reissue (2018)", "Standard", "mid", 15, 30),

        # === ROUND 8 — 100 new items ===

        # Game Boy Limited Editions (+15)
        ("Nintendo", "Game Boy Light Famitsu 500 LE", "Game Boy Light", "Famitsu 500 Limited Edition (Japan)", "Japan Exclusive", "grail", 400, 800),
        ("Nintendo", "Game Boy Color Pokemon Center Gold Version", "Game Boy Color", "Pokemon Center Gold (Japan)", "Japan Exclusive", "grail", 250, 500),
        ("Nintendo", "Game Boy Color Pokemon Center Silver Version", "Game Boy Color", "Pokemon Center Silver (Japan)", "Japan Exclusive", "grail", 250, 500),
        ("Nintendo", "Game Boy Color Pokemon Crystal LE", "Game Boy Color", "Pokemon Crystal Limited (Japan)", "Japan Exclusive", "grail", 280, 560),
        ("Nintendo", "Game Boy Advance SP Kingdom Hearts Chain", "Game Boy Advance SP", "Kingdom Hearts Chain of Memories Silver (NA)", "Special Edition", "high", 150, 310),
        ("Nintendo", "Game Boy Advance SP Tribal Silver", "Game Boy Advance SP", "Tribal Silver AGS-001 (NA)", "Special Edition", "high", 120, 250),
        ("Nintendo", "Game Boy Advance SP Pikachu Yellow", "Game Boy Advance SP", "Pikachu Pokemon Center Yellow (Japan)", "Japan Exclusive", "grail", 200, 400),
        ("Nintendo", "Game Boy Micro Final Fantasy IV Advance", "Game Boy Micro", "Final Fantasy IV Advance Silver (Japan)", "Japan Exclusive", "grail", 280, 560),
        ("Nintendo", "Game Boy Micro Famicom 20th Anniversary", "Game Boy Micro", "Famicom 20th Anni Red/Gold (Japan)", "Japan Exclusive", "grail", 250, 500),
        ("Nintendo", "Game Boy Micro Mother 3 Deluxe Box", "Game Boy Micro", "Mother 3 Red/White Deluxe (Japan)", "Japan Exclusive", "grail", 350, 700),
        ("Nintendo", "Game Boy Color Tommy Hilfiger LE", "Game Boy Color", "Tommy Hilfiger Yellow (NA)", "Special Edition", "high", 180, 360),
        ("Nintendo", "Game Boy Color Hello Kitty Special Box", "Game Boy Color", "Hello Kitty Pink (Japan)", "Japan Exclusive", "high", 160, 320),
        ("Nintendo", "Game Boy Advance SP Pearl Green AGS-101", "Game Boy Advance SP", "Pearl Green AGS-101 Backlit (NA)", "Standard", "high", 100, 210),
        ("Nintendo", "Game Boy Micro Blue", "Game Boy Micro", "Blue Standard (Japan)", "Japan Exclusive", "high", 160, 320),
        ("Nintendo", "Game Boy Micro Pink", "Game Boy Micro", "Pink Standard (Japan)", "Japan Exclusive", "high", 160, 320),

        # DS/3DS Limited (+15)
        ("Nintendo", "Nintendo DS Lite Zelda Phantom Hourglass Gold", "Nintendo DS Lite", "Zelda Phantom Hourglass Gold (NA)", "Special Edition", "high", 130, 270),
        ("Nintendo", "Nintendo DS Lite Pokemon DP Palkia", "Nintendo DS Lite", "Pokemon Diamond Pearl Palkia Pink (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Nintendo", "Nintendo DS Lite Final Fantasy III Crystal", "Nintendo DS Lite", "Final Fantasy III Crystal White (Japan)", "Japan Exclusive", "high", 140, 290),
        ("Nintendo", "Nintendo DSi Pokemon White Reshiram", "Nintendo DS", "Pokemon Black/White Reshiram White (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Nintendo DSi Mario 25th Anniversary Red", "Nintendo DS", "Mario 25th Anniversary Red (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Nintendo", "Nintendo 3DS XL Pikachu Yellow", "Nintendo 3DS XL", "Pikachu Yellow (NA)", "Special Edition", "high", 160, 330),
        ("Nintendo", "Nintendo 3DS XL Zelda A Link Between Worlds Gold", "Nintendo 3DS XL", "Zelda A Link Between Worlds Gold (NA)", "Special Edition", "high", 170, 350),
        ("Nintendo", "Nintendo 3DS XL Monster Hunter 4 Ultimate Blue", "Nintendo 3DS XL", "Monster Hunter 4 Ultimate Blue (NA)", "Special Edition", "high", 140, 290),
        ("Nintendo", "Nintendo 3DS XL Fire Emblem Fates", "Nintendo 3DS XL", "Fire Emblem Fates Special (NA)", "Special Edition", "high", 180, 370),
        ("Nintendo", "New Nintendo 3DS XL Samus Returns", "New Nintendo 3DS XL", "Samus Returns Metroid (NA)", "Special Edition", "high", 200, 410),
        ("Nintendo", "New Nintendo 3DS XL Hyrule Gold Edition", "New Nintendo 3DS XL", "Hyrule Edition Gold (NA)", "Special Edition", "high", 190, 390),
        ("Nintendo", "New Nintendo 3DS Ambassador Edition", "New Nintendo 3DS", "Ambassador Edition Black (EU)", "Special Edition", "grail", 300, 600),
        ("Nintendo", "New Nintendo 3DS Majora's Mask Skull Kid", "New Nintendo 3DS XL", "Majora's Mask 3D Gold/Black (NA)", "Special Edition", "grail", 280, 560),
        ("Nintendo", "New Nintendo 3DS Animal Crossing Happy Home HHD", "New Nintendo 3DS", "Animal Crossing HHD White (NA)", "Special Edition", "high", 130, 270),
        ("Nintendo", "New Nintendo 3DS XL Pokemon Sun Moon Pikachu", "New Nintendo 3DS XL", "Pokemon Sun Moon Pikachu Yellow (NA)", "Special Edition", "high", 160, 330),

        # Switch Limited (+10)
        ("Nintendo", "Switch OLED Pokemon Scarlet Violet", "Switch OLED", "Pokemon Scarlet Violet (EU/NA)", "Special Edition", "high", 350, 450),
        ("Nintendo", "Switch OLED Splatoon 3 Special", "Switch OLED", "Splatoon 3 Special Edition (EU/NA)", "Special Edition", "high", 340, 440),
        ("Nintendo", "Switch OLED Zelda Tears of the Kingdom", "Switch OLED", "Zelda TOTK Special Edition (EU/NA)", "Special Edition", "high", 370, 480),
        ("Nintendo", "Switch Lite Zacian Zamazenta Cyan/Magenta", "Switch Lite", "Pokemon Sword Shield Zacian Zamazenta (NA)", "Special Edition", "high", 180, 270),
        ("Nintendo", "Switch Lite Dialga Palkia BDSP", "Switch Lite", "Pokemon BDSP Dialga Palkia (NA)", "Special Edition", "high", 190, 280),
        ("Nintendo", "Switch Lite Hyrule Edition Gold", "Switch Lite", "Hyrule Edition Gold (EU/NA)", "Special Edition", "high", 200, 300),
        ("Nintendo", "Switch Joy-Con Zelda Skyward Sword LE", "Switch", "Joy-Con Zelda Skyward Sword HD (EU/NA)", "Special Edition", "high", 80, 120),
        ("Nintendo", "Switch Joy-Con Pokemon Let's Go Eevee Pikachu", "Switch", "Joy-Con Pokemon Let's Go Eevee/Pikachu (EU/NA)", "Special Edition", "high", 90, 140),
        ("Nintendo", "Switch Pro Controller Monster Hunter Rise", "Switch", "Pro Controller MH Rise Sunbreak (EU/NA)", "Special Edition", "high", 80, 120),
        ("Nintendo", "Switch Pro Controller Splatoon 3 LE", "Switch", "Pro Controller Splatoon 3 Special (EU/NA)", "Special Edition", "high", 85, 130),

        # PSP/Vita Limited (+10)
        ("Sony", "PSP-3000 Monster Hunter Portable 3rd Hunters Model", "PSP-3000", "Monster Hunter Portable 3rd Hunters Model (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Sony", "PSP-1000 Crisis Core FF7 10th Anni LE", "PSP-1000", "Crisis Core FFVII 10th Anniversary (Japan)", "Japan Exclusive", "high", 150, 310),
        ("Sony", "PSP-3000 Dissidia 012 Duodecim", "PSP-3000", "Dissidia 012 Final Fantasy (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Sony", "PSP-2000 Kingdom Hearts BBS Silver", "PSP-2000", "Kingdom Hearts Birth by Sleep Silver (Japan)", "Japan Exclusive", "high", 140, 290),
        ("Sony", "PS Vita OLED Hatsune Miku LE Crystal White", "PS Vita 1000", "Hatsune Miku LE Crystal White (Japan)", "Japan Exclusive", "grail", 250, 500),
        ("Sony", "PS Vita OLED Soul Sacrifice LE", "PS Vita 1000", "Soul Sacrifice LE White (Japan)", "Japan Exclusive", "high", 180, 370),
        ("Sony", "PS Vita Slim Danganronpa V3 Black White", "PS Vita 2000", "Danganronpa V3 Black/White (Japan)", "Japan Exclusive", "high", 190, 390),
        ("Sony", "PSP-3000 One Piece Romance Dawn Red", "PSP-3000", "One Piece Romance Dawn Red (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Sony", "PSP-3000 God Eater Burst Red", "PSP-3000", "God Eater Burst White/Red (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Sony", "PS Vita Slim Minecraft Special LE White", "PS Vita 2000", "Minecraft Special Edition White (Japan)", "Japan Exclusive", "high", 160, 310),

        # Neo Geo Pocket (+8)
        ("SNK", "Neo Geo Pocket Color Crystal White", "Neo Geo Pocket Color", "Crystal White", "Limited Color", "high", 100, 210),
        ("SNK", "Neo Geo Pocket Color Platinum Silver", "Neo Geo Pocket Color", "Platinum Silver", "Standard", "high", 90, 185),
        ("SNK", "SNK vs Capcom Card Fighters Clash NGPC", "Neo Geo Pocket Color", "SNK vs Capcom Card Fighters Clash (Game)", "Standard", "high", 85, 175),
        ("SNK", "King of Fighters R-2 NGPC", "Neo Geo Pocket Color", "King of Fighters R-2 (Game, New)", "Standard", "high", 80, 165),
        ("SNK", "Neo Geo Pocket Color Stone Blue", "Neo Geo Pocket Color", "Stone Blue (Japan)", "Japan Exclusive", "high", 120, 250),
        ("SNK", "Sonic the Hedgehog Pocket Adventure NGPC", "Neo Geo Pocket Color", "Sonic Pocket Adventure (Game)", "Standard", "high", 75, 155),

        # WonderSwan (+8)
        ("Bandai", "WonderSwan Color Final Fantasy Blue", "WonderSwan Color", "Final Fantasy Blue Crystal (Japan)", "Japan Exclusive", "high", 80, 170),
        ("Bandai", "WonderSwan Color Gundam Wing Zero Custom", "WonderSwan Color", "Gundam Wing Zero White (Japan)", "Japan Exclusive", "high", 90, 190),
        ("Bandai", "SwanCrystal Wine Red", "SwanCrystal", "Wine Red (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Bandai", "SwanCrystal Blue Violet", "SwanCrystal", "Blue Violet (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Bandai", "Final Fantasy I WonderSwan Color", "WonderSwan Color", "Final Fantasy I WSC (Game, Japan)", "Japan Exclusive", "high", 50, 110),
        ("Bandai", "Final Fantasy II WonderSwan Color", "WonderSwan Color", "Final Fantasy II WSC (Game, Japan)", "Japan Exclusive", "high", 50, 110),
        ("Bandai", "Final Fantasy IV WonderSwan Color", "WonderSwan Color", "Final Fantasy IV WSC (Game, Japan)", "Japan Exclusive", "high", 60, 130),
        ("Bandai", "RockMan EXE WonderSwan Color Edition", "WonderSwan Color", "RockMan EXE WSC Console Bundle (Japan)", "Japan Exclusive", "high", 100, 210),

        # Anbernic/Miyoo/Retroid (+10)
        ("Miyoo", "Miyoo Mini Plus v4 White", "Miyoo Mini Plus", "v4 White (Latest)", "Modded/Custom", "mid", 55, 70),
        ("Anbernic", "Anbernic RG35XX Plus Transparent Black", "RG35XX Plus", "Transparent Black", "Modded/Custom", "mid", 50, 65),
        ("Anbernic", "Anbernic RG35XX H Transparent Purple", "RG35XX H", "Transparent Purple Landscape", "Modded/Custom", "mid", 55, 70),
        ("Anbernic", "Anbernic RG35XX SP Transparent Blue", "RG35XX SP", "Transparent Blue Clamshell", "Modded/Custom", "mid", 55, 70),
        ("Retroid", "Retroid Pocket 4 Pro Indigo", "Retroid Pocket 4 Pro", "Indigo 8GB", "Modded/Custom", "mid", 100, 130),
        ("Retroid", "Retroid Pocket 4 Pro White", "Retroid Pocket 4 Pro", "White 8GB", "Modded/Custom", "mid", 100, 130),
        ("Anbernic", "Anbernic RG556 Purple AMOLED", "RG556", "Purple AMOLED", "Modded/Custom", "mid", 90, 115),
        ("Ayn", "Ayn Odin 2 Black", "Ayn Odin 2", "Black 8GB/256GB", "Modded/Custom", "high", 250, 300),
        ("Valve", "Steam Deck OLED 1TB Limited Edition", "Steam Deck OLED", "1TB Limited Edition", "Special Edition", "high", 600, 700),
        ("Analogue", "Analogue Pocket Classic Black", "Analogue Pocket", "Classic Black", "Standard", "high", 250, 330),

        # Accessories & Cases (+10)
        ("Nintendo", "Game Boy Camera Green", "Game Boy", "Game Boy Camera Green MGB-006", "Standard", "mid", 30, 65),
        ("Nintendo", "Game Boy Camera Red", "Game Boy", "Game Boy Camera Red MGB-006", "Standard", "mid", 35, 70),
        ("Nintendo", "Game Boy Printer", "Game Boy", "Game Boy Printer MGB-007", "Standard", "mid", 40, 85),
        ("Nintendo", "Game Boy Link Cable DMG-04", "Game Boy", "Link Cable DMG-04 Original", "Standard", "standard", 10, 20),
        ("Nintendo", "Game Boy Advance e-Reader", "Game Boy Advance", "e-Reader AGB-014", "Standard", "mid", 30, 65),
        ("Nintendo", "Transfer Pak N64", "N64", "Transfer Pak NUS-019 (Stadium/Crystal)", "Standard", "mid", 20, 40),
        ("Nintendo", "Game Boy Advance SP Carrying Case Platinum", "Game Boy Advance SP", "Official Carrying Case Platinum (NA)", "Standard", "standard", 15, 30),
        ("Nintendo", "Game Boy Color Carrying Case (Yellow)", "Game Boy Color", "Official Soft Carrying Case Yellow (NA)", "Standard", "standard", 12, 25),
        ("Nintendo", "Nintendo DS Rumble Pak", "Nintendo DS", "Rumble Pak NTR-008", "Standard", "standard", 10, 20),
        ("Nintendo", "Game Boy Advance Four Player Adapter", "Game Boy Advance", "Four Player Link Cable AGB-011", "Standard", "standard", 15, 30),

        # Additional vintage/rare (+14)
        ("Nintendo", "Game Boy Light Clear Yellow Toys R Us", "Game Boy Light", "Clear Yellow Toys R Us (Japan)", "Japan Exclusive", "grail", 380, 760),
        ("Nintendo", "Game Boy Color Daiei Hawks LE", "Game Boy Color", "Daiei Hawks Orange (Japan)", "Japan Exclusive", "grail", 200, 400),
        ("Nintendo", "Game Boy Advance SP Torchic Orange Pokemon", "Game Boy Advance SP", "Torchic Orange Pokemon (Japan)", "Japan Exclusive", "grail", 220, 440),
        ("Sega", "Sega Nomad (Genesis Nomad)", "Sega Nomad", "Standard Black (NA)", "Standard", "high", 180, 350),
        ("Atari", "Atari Lynx II Clear Case LE", "Atari Lynx II", "Clear Case Limited (NA)", "Limited Color", "grail", 300, 600),
        ("SNK", "Neo Geo Pocket Platinum Silver (Mono)", "Neo Geo Pocket", "Platinum Silver Monochrome", "Standard", "high", 80, 170),
        ("Bandai", "WonderSwan Original Skeleton Black", "WonderSwan", "Skeleton Black (Japan)", "Japan Exclusive", "high", 70, 150),
        ("Bandai", "WonderSwan Original Skeleton Blue", "WonderSwan", "Skeleton Blue (Japan)", "Japan Exclusive", "high", 70, 150),
        ("Nintendo", "Game Boy Advance SP NES Edition AGS-001", "Game Boy Advance SP", "NES Classic Edition Black/Grey (NA)", "Special Edition", "high", 140, 290),
        ("Nintendo", "New Nintendo 3DS XL Super NES Edition", "New Nintendo 3DS XL", "Super NES Edition Grey (NA)", "Special Edition", "high", 170, 350),
        ("Nintendo", "Switch OLED White Standard", "Switch OLED", "White Standard", "Standard", "mid", 280, 350),
        ("Nintendo", "Switch Lite Yellow Standard", "Switch Lite", "Yellow Standard", "Standard", "mid", 120, 180),
        ("Sony", "PS Vita OLED Black 3G/Wi-Fi", "PS Vita 1000", "Crystal Black 3G/Wi-Fi (Japan)", "Standard", "mid", 100, 200),
        ("Sony", "PSP Go Black NA", "PSP Go", "Piano Black (N-1001 NA)", "Standard", "mid", 80, 170),
    ]

    catalog = []
    for brand, name, platform, variant_note, condition, rarity_tier, price_loose, price_cib in items:
        # Determine region from variant note and condition
        if "Japan" in variant_note or condition == "Japan Exclusive":
            region = "JPN"
        elif "NA" in variant_note:
            region = "NA"
        else:
            region = "EU"

        is_limited = condition in ("Limited Color", "Special Edition", "Japan Exclusive", "Anniversary")

        # Estimate release year from platform knowledge
        year = _platform_year(platform, name)

        catalog.append({
            "brand": brand,
            "name": name,
            "platform": platform,
            "variant_note": variant_note,
            "condition": condition,
            "rarity_tier": rarity_tier,
            "price_loose_eur": price_loose,
            "price_cib_eur": price_cib,
            "region": region,
            "is_limited_edition": is_limited,
            "year": year,
        })

    # Round 7 expansion — 50 items
    catalog.extend(_expanded_round7_retro_handhelds())

    # Round 8 expansion — 55 items (Neo Geo Pocket Color, Atari Lynx, Sega Nomad,
    # GBA SP LEs, WonderSwan Color, TurboExpress, N-Gage, Bandai WonderSwan)
    catalog.extend(_expanded_round8_retro_handhelds())

    # Variant expansion — ~115 color/edition variants across major handhelds
    catalog.extend(_variant_expansion())

    # Round 9 expansion — 200 items: LE consoles, modern retro handhelds, trending 2024-2025
    catalog.extend(_round9_handheld_expansion())

    # Deduplicate by ('name',) (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = item["name"]
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _expanded_round7_retro_handhelds() -> list[dict]:
    """50 new retro handheld items: Analogue Pocket LEs, Miyoo Mini Plus variants, Anbernic RG353V/RG405M,
    Game Boy Micro special editions, PSP Go colors, Neo Geo Pocket Color, Panic Playdate."""
    items = [
        # --- Analogue Pocket Limited Editions ---
        ("Analogue", "Analogue Pocket Transparent Smoke", "Analogue Pocket", "Transparent Smoke", "Limited Color", "grail", 340, 440),
        ("Analogue", "Analogue Pocket Transparent Green", "Analogue Pocket", "Transparent Green", "Limited Color", "grail", 330, 430),
        ("Analogue", "Analogue Pocket Transparent Blue", "Analogue Pocket", "Transparent Blue", "Limited Color", "grail", 330, 430),
        ("Analogue", "Analogue Pocket Transparent Orange", "Analogue Pocket", "Transparent Orange", "Limited Color", "grail", 340, 440),
        ("Analogue", "Analogue Pocket Classic LE GLOW", "Analogue Pocket", "Classic Limited Glow Edition", "Limited Color", "grail", 380, 490),
        ("Analogue", "Analogue Pocket Dock", "Analogue Pocket", "Dock HDMI TV Output", "Standard", "mid", 80, 110),

        # --- Miyoo Mini Plus Variants ---
        ("Miyoo", "Miyoo Mini Plus Transparent Black", "Miyoo Mini Plus", "Transparent Black", "Modded/Custom", "mid", 55, 70),
        ("Miyoo", "Miyoo Mini Plus Transparent Purple", "Miyoo Mini Plus", "Transparent Purple", "Modded/Custom", "mid", 55, 70),
        ("Miyoo", "Miyoo Mini Plus Gray", "Miyoo Mini Plus", "Gray", "Modded/Custom", "mid", 50, 65),
        ("Miyoo", "Miyoo Mini Plus Retro Green", "Miyoo Mini Plus", "Retro Green", "Modded/Custom", "mid", 55, 70),
        ("Miyoo", "Miyoo Mini Plus v3 Transparent White", "Miyoo Mini Plus", "v3 Transparent White", "Modded/Custom", "mid", 55, 70),

        # --- Anbernic RG353V / RG405M ---
        ("Anbernic", "Anbernic RG353V Transparent Purple", "RG353V", "Transparent Purple", "Modded/Custom", "mid", 65, 85),
        ("Anbernic", "Anbernic RG353V Transparent White", "RG353V", "Transparent White", "Modded/Custom", "mid", 60, 80),
        ("Anbernic", "Anbernic RG353VS Black", "RG353VS", "Black Single-Stick", "Modded/Custom", "mid", 50, 65),
        ("Anbernic", "Anbernic RG405M Purple", "RG405M", "Anodized Purple", "Modded/Custom", "mid", 80, 100),
        ("Anbernic", "Anbernic RG405M Black", "RG405M", "Matte Black", "Modded/Custom", "mid", 75, 95),

        # --- Game Boy Micro Special Editions ---
        ("Nintendo", "Game Boy Micro Famicom II Faceplate", "Game Boy Micro", "Famicom II Controller Faceplate (Japan)", "Japan Exclusive", "grail", 200, 400),
        ("Nintendo", "Game Boy Micro Mario Faceplate Set", "Game Boy Micro", "Mario 20th Anniversary Faceplate Set (Japan)", "Japan Exclusive", "high", 160, 320),
        ("Nintendo", "Game Boy Micro Purple", "Game Boy Micro", "Purple (Japan)", "Japan Exclusive", "high", 150, 310),
        ("Nintendo", "Game Boy Micro Donkey Kong Faceplate", "Game Boy Micro", "Donkey Kong Faceplate (Japan)", "Japan Exclusive", "high", 140, 280),

        # --- PSP Go Editions ---
        ("Sony", "PSP Go Piano Black (Japan)", "PSP Go", "Piano Black (N-1000 Japan)", "Japan Exclusive", "high", 80, 170),
        ("Sony", "PSP Go Pearl White (Japan)", "PSP Go", "Pearl White (N-1000 Japan)", "Japan Exclusive", "high", 90, 185),
        ("Sony", "PSP Go Carnival Colors Red (Japan)", "PSP Go", "Carnival Colors Red (Japan)", "Japan Exclusive", "high", 110, 220),
        ("Sony", "PSP Go Metallic Blue (Japan)", "PSP Go", "Metallic Blue (Japan)", "Japan Exclusive", "high", 100, 210),

        # --- Neo Geo Pocket Color variants ---
        ("SNK", "Neo Geo Pocket Color Crystal Clear", "Neo Geo Pocket Color", "Crystal Clear", "Limited Color", "high", 105, 220),
        ("SNK", "Neo Geo Pocket Color Aqua Blue", "Neo Geo Pocket Color", "Aqua Blue", "Limited Color", "high", 95, 200),
        ("SNK", "Neo Geo Pocket Color Platinum Blue", "Neo Geo Pocket Color", "Platinum Blue", "Standard", "high", 85, 180),
        ("SNK", "Neo Geo Pocket Color Dark Blue", "Neo Geo Pocket Color", "Dark Blue", "Standard", "high", 85, 175),
        ("SNK", "Neo Geo Pocket Color Selection Vol.2 Switch", "Switch", "Neo Geo Pocket Color Selection Vol.2 (Game)", "Standard", "mid", 25, 40),
        ("SNK", "The Last Blade NGPC", "Neo Geo Pocket Color", "The Last Blade (Game)", "Standard", "high", 90, 180),
        ("SNK", "King of Fighters R-2 NGPC", "Neo Geo Pocket Color", "KoF R-2 (Game)", "Standard", "high", 80, 160),

        # --- Panic Playdate ---
        ("Panic", "Playdate", "Playdate", "Yellow Standard", "Standard", "high", 160, 220),
        ("Panic", "Playdate Stereo Dock", "Playdate", "Stereo Dock Speaker Base", "Standard", "mid", 70, 90),
        ("Panic", "Playdate Cover Orange", "Playdate", "Protective Cover Orange", "Standard", "standard", 25, 35),
        ("Panic", "Playdate Cover Purple", "Playdate", "Protective Cover Purple", "Standard", "standard", 25, 35),

        # --- Additional modern retro handhelds ---
        ("Anbernic", "Anbernic RG Nano", "RG Nano", "Black Keychain-Size", "Modded/Custom", "standard", 20, 28),
        ("Anbernic", "Anbernic RG353P", "RG353P", "Black Landscape", "Modded/Custom", "mid", 55, 70),
        ("Anbernic", "Anbernic RG353PS", "RG353PS", "Transparent Purple Landscape", "Modded/Custom", "mid", 50, 65),
        ("Retroid", "Retroid Pocket 4", "Retroid Pocket 4", "Black 4GB", "Modded/Custom", "mid", 70, 90),
        ("Retroid", "Retroid Pocket 2 Plus", "Retroid Pocket 2+", "Retro Purple", "Modded/Custom", "mid", 45, 60),
        ("Trimui", "Trimui Smart Pro S", "Trimui Smart Pro S", "Gray Pro S", "Modded/Custom", "mid", 50, 65),

        # --- More vintage/rare handhelds ---
        ("Nintendo", "Game Boy Advance SP Char Custom Red (Japan)", "Game Boy Advance SP", "Char Aznable Custom Red Gundam (Japan)", "Japan Exclusive", "grail", 280, 550),
        ("Nintendo", "Game Boy Advance SP Chobits (Japan)", "Game Boy Advance SP", "Chobits Pink (Japan)", "Japan Exclusive", "grail", 220, 440),
        ("Sony", "PS Vita Slim Dangan Ronpa V3", "PS Vita 2000", "Dangan Ronpa V3 Black/White (Japan)", "Japan Exclusive", "high", 180, 350),
        ("Sony", "PS Vita Slim Love Live! Sunshine!!", "PS Vita 2000", "Love Live! Sunshine!! Orange (Japan)", "Japan Exclusive", "high", 170, 330),
        ("Nintendo", "New Nintendo 2DS XL Animal Crossing", "New Nintendo 2DS XL", "Animal Crossing Leaf Green (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Nintendo", "Nintendo 3DS XL Monster Hunter 4G", "Nintendo 3DS XL", "Monster Hunter 4 Ultimate (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Nintendo", "Game Boy DMG-01 Classic DMG Backlight Mod White Shell", "Game Boy", "Custom White Shell IPS Backlight Mod", "Modded/Custom", "mid", 90, 130),
        ("Nintendo", "Game Boy Advance SP IPS V5 Mod Clear Shell", "Game Boy Advance SP", "Custom Clear Shell IPS V5 Mod", "Modded/Custom", "mid", 85, 125),
    ]
    catalog = []
    for brand, name, platform, variant_note, condition, rarity_tier, price_loose, price_cib in items:
        if "Japan" in variant_note or condition == "Japan Exclusive":
            region = "JPN"
        elif "NA" in variant_note:
            region = "NA"
        else:
            region = "EU"
        is_limited = condition in ("Limited Color", "Special Edition", "Japan Exclusive", "Anniversary")
        year = _platform_year(platform, name)
        catalog.append({
            "brand": brand,
            "name": name,
            "platform": platform,
            "variant_note": variant_note,
            "condition": condition,
            "rarity_tier": rarity_tier,
            "price_loose_eur": price_loose,
            "price_cib_eur": price_cib,
            "region": region,
            "is_limited_edition": is_limited,
            "year": year,
        })
    return catalog


def _expanded_round8_retro_handhelds() -> list[dict]:
    """55 new retro handheld items: Neo Geo Pocket Color games, Atari Lynx games,
    Sega Nomad accessories, GBA SP limited editions, WonderSwan Color games,
    TurboExpress/PC Engine GT, Nokia N-Gage games, Bandai WonderSwan."""
    items = [
        # --- Neo Geo Pocket Color Games (+10) ---
        ("SNK", "SNK vs Capcom Match of the Millennium NGPC", "Neo Geo Pocket Color", "SNK vs Capcom MOTM (Game)", "Standard", "high", 95, 200),
        ("SNK", "SNK Gals Fighters NGPC", "Neo Geo Pocket Color", "SNK Gals Fighters (Game)", "Standard", "high", 70, 150),
        ("SNK", "Metal Slug 2nd Mission NGPC", "Neo Geo Pocket Color", "Metal Slug 2nd Mission (Game)", "Standard", "high", 80, 170),
        ("SNK", "Biomotor Unitron NGPC", "Neo Geo Pocket Color", "Biomotor Unitron RPG (Game)", "Standard", "high", 60, 130),
        ("SNK", "Card Fighters Clash SNK Version NGPC", "Neo Geo Pocket Color", "Card Fighters Clash SNK Ver (Game)", "Standard", "high", 75, 155),
        ("SNK", "Card Fighters Clash Capcom Version NGPC", "Neo Geo Pocket Color", "Card Fighters Clash Capcom Ver (Game)", "Standard", "high", 75, 155),
        ("SNK", "Faselei! NGPC", "Neo Geo Pocket Color", "Faselei! (Game, PAL)", "Standard", "grail", 200, 400),
        ("SNK", "Cotton Boomerang NGPC", "Neo Geo Pocket Color", "Cotton Boomerang (Game, Japan)", "Japan Exclusive", "grail", 250, 500),
        ("SNK", "Samurai Shodown! 2 NGPC", "Neo Geo Pocket Color", "Samurai Shodown! 2 (Game)", "Standard", "high", 85, 175),
        ("SNK", "Dark Arms Beast Buster NGPC", "Neo Geo Pocket Color", "Dark Arms Beast Buster 1999 (Game)", "Standard", "high", 90, 185),

        # --- Atari Lynx Games (+8) ---
        ("Atari", "California Games Lynx", "Atari Lynx", "California Games (Game)", "Standard", "mid", 20, 50),
        ("Atari", "Chip's Challenge Lynx", "Atari Lynx", "Chip's Challenge (Game)", "Standard", "mid", 25, 55),
        ("Atari", "Electrocop Lynx", "Atari Lynx", "Electrocop (Game)", "Standard", "mid", 15, 40),
        ("Atari", "Todd's Adventures in Slime World Lynx", "Atari Lynx", "Todd's Adventures in Slime World (Game)", "Standard", "mid", 20, 45),
        ("Atari", "Blue Lightning Lynx", "Atari Lynx", "Blue Lightning (Game)", "Standard", "mid", 15, 35),
        ("Atari", "Ninja Gaiden Lynx", "Atari Lynx", "Ninja Gaiden (Game)", "Standard", "high", 80, 160),
        ("Atari", "Dracula the Undead Lynx", "Atari Lynx", "Dracula the Undead (Game)", "Standard", "mid", 40, 85),
        ("Atari", "Lemmings Lynx", "Atari Lynx", "Lemmings (Game)", "Standard", "mid", 30, 65),

        # --- Sega Nomad Accessories (+5) ---
        ("Sega", "Sega Nomad Battery Pack", "Sega Nomad", "Official Rechargeable Battery Pack", "Standard", "high", 80, 140),
        ("Sega", "Sega Nomad AC Adapter", "Sega Nomad", "Official AC Adapter MK-6501", "Standard", "mid", 35, 60),
        ("Sega", "Sega Nomad AV Cable", "Sega Nomad", "Official AV Out Cable", "Standard", "mid", 30, 55),
        ("Sega", "Sega Nomad Carrying Case", "Sega Nomad", "Official Carrying Case", "Standard", "high", 90, 160),
        ("Sega", "Sega Nomad Link Cable", "Sega Nomad", "2-Player Link Cable", "Standard", "high", 100, 180),

        # --- Game Boy Advance SP Limited Editions (+8) ---
        ("Nintendo", "Game Boy Advance SP Famicom 20th Anniversary", "Game Boy Advance SP", "Famicom 20th Anniversary (Japan)", "Japan Exclusive", "grail", 250, 500),
        ("Nintendo", "Game Boy Advance SP NES Classic Edition", "Game Boy Advance SP", "NES Classic Silver & Black", "Special Edition", "high", 120, 250),
        ("Nintendo", "Game Boy Advance SP Kingdom Hearts", "Game Boy Advance SP", "Kingdom Hearts Chain of Memories (Japan)", "Japan Exclusive", "grail", 300, 600),
        ("Nintendo", "Game Boy Advance SP Tribal Silver", "Game Boy Advance SP", "Tribal Silver Limited Edition", "Special Edition", "high", 140, 280),
        ("Nintendo", "Game Boy Advance SP Zelda Minish Cap Gold", "Game Boy Advance SP", "Zelda Minish Cap Gold (PAL)", "Special Edition", "grail", 280, 550),
        ("Nintendo", "Game Boy Advance SP Who Are You? Pink", "Game Boy Advance SP", "Who Are You? Pink (Japan)", "Japan Exclusive", "high", 130, 260),
        ("Nintendo", "Game Boy Advance SP Pikachu Yellow", "Game Boy Advance SP", "Pokemon Pikachu Yellow (Japan)", "Japan Exclusive", "grail", 260, 520),
        ("Nintendo", "Game Boy Advance SP Onyx Black AGS-101", "Game Boy Advance SP", "Onyx Black AGS-101 Backlit", "Standard", "high", 100, 210),

        # --- WonderSwan Color Games (+8) ---
        ("Bandai", "Final Fantasy WonderSwan Color", "WonderSwan Color", "Final Fantasy (Game, Japan)", "Japan Exclusive", "high", 60, 130),
        ("Bandai", "Final Fantasy II WonderSwan Color", "WonderSwan Color", "Final Fantasy II (Game, Japan)", "Japan Exclusive", "high", 55, 120),
        ("Bandai", "Final Fantasy IV WonderSwan Color", "WonderSwan Color", "Final Fantasy IV (Game, Japan)", "Japan Exclusive", "high", 70, 150),
        ("Bandai", "Riviera WonderSwan Color", "WonderSwan Color", "Riviera: The Promised Land (Game, Japan)", "Japan Exclusive", "high", 80, 170),
        ("Bandai", "Gunpey EX WonderSwan Color", "WonderSwan Color", "Gunpey EX (Game, Japan)", "Japan Exclusive", "mid", 30, 65),
        ("Bandai", "Digimon Tamers Digimon Medley WSC", "WonderSwan Color", "Digimon Tamers: Digimon Medley (Game, Japan)", "Japan Exclusive", "mid", 40, 85),
        ("Bandai", "One Piece Grand Battle Swan Colosseum WSC", "WonderSwan Color", "One Piece Grand Battle Swan Colosseum (Game, Japan)", "Japan Exclusive", "mid", 45, 95),
        ("Bandai", "Judgement Silversword WSC", "WonderSwan Color", "Judgement Silversword (Game, Japan)", "Japan Exclusive", "grail", 350, 700),

        # --- TurboExpress / PC Engine GT (+6) ---
        ("NEC", "TurboExpress Console", "TurboExpress", "TurboExpress Handheld Console (NA)", "Standard", "high", 150, 320),
        ("NEC", "TurboExpress TV Tuner", "TurboExpress", "TurboExpress TV Tuner Accessory (NA)", "Standard", "high", 120, 240),
        ("NEC", "TurboExpress AC Adapter", "TurboExpress", "TurboExpress Official AC Adapter (NA)", "Standard", "mid", 40, 75),
        ("NEC", "PC Engine GT Console", "PC Engine GT", "PC Engine GT Handheld Console (Japan)", "Japan Exclusive", "high", 180, 380),
        ("NEC", "PC Engine GT TV Tuner", "PC Engine GT", "PC Engine GT TV Tuner (Japan)", "Japan Exclusive", "high", 100, 200),
        ("NEC", "PC Engine GT Car Adapter", "PC Engine GT", "PC Engine GT Car Adapter (Japan)", "Japan Exclusive", "mid", 50, 100),

        # --- Nokia N-Gage Games (+5) ---
        ("Nokia", "N-Gage QD Console Graphite", "Nokia N-Gage", "N-Gage QD Graphite Console", "Standard", "mid", 40, 90),
        ("Nokia", "Pathway to Glory N-Gage", "Nokia N-Gage", "Pathway to Glory (Game)", "Standard", "mid", 15, 35),
        ("Nokia", "Tomb Raider N-Gage", "Nokia N-Gage", "Tomb Raider (Game)", "Standard", "mid", 20, 45),
        ("Nokia", "Sonic N N-Gage", "Nokia N-Gage", "Sonic N (Game)", "Standard", "mid", 20, 45),
        ("Nokia", "Elder Scrolls Shadowkey N-Gage", "Nokia N-Gage", "Elder Scrolls Travels: Shadowkey (Game)", "Standard", "high", 80, 160),

        # --- Bandai WonderSwan (+5) ---
        ("Bandai", "WonderSwan Console Crystal Black", "WonderSwan", "Crystal Black Console (Japan)", "Japan Exclusive", "high", 65, 140),
        ("Bandai", "WonderSwan Console Skeleton Blue", "WonderSwan", "Skeleton Blue Console (Japan)", "Japan Exclusive", "high", 70, 150),
        ("Bandai", "WonderSwan Console Sherbet Melon", "WonderSwan", "Sherbet Melon Console (Japan)", "Japan Exclusive", "high", 80, 170),
        ("Bandai", "Gundam WonderSwan Limited Edition", "WonderSwan", "MS Gundam MSVS Limited Edition Console (Japan)", "Japan Exclusive", "grail", 200, 400),
        ("Bandai", "Digimon Adventure Anode/Cathode Tamer WS", "WonderSwan", "Digimon Adventure Anode/Cathode Tamer (Game, Japan)", "Japan Exclusive", "mid", 35, 75),

        # === ROUND 9 — 91 new items to reach 700+ ===

        # --- Game Boy Color Special Editions (+8) ---
        ("Nintendo", "Game Boy Color Ozzy Osbourne Bat", "Game Boy Color", "Ozzy Osbourne Bat Purple (Japan)", "Japan Exclusive", "grail", 300, 600),
        ("Nintendo", "Game Boy Color Toys R Us Clear Purple", "Game Boy Color", "Toys R Us Exclusive Clear Purple (NA)", "Special Edition", "high", 100, 210),
        ("Nintendo", "Game Boy Color Daiei Hawks Orange", "Game Boy Color", "Daiei Hawks Orange (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Game Boy Color Jusco 30th Anniversary", "Game Boy Color", "Jusco 30th Anniversary Clear (Japan)", "Japan Exclusive", "high", 140, 290),
        ("Nintendo", "Game Boy Color Famitsu Limited Gold", "Game Boy Color", "Famitsu 500 Issue Gold (Japan)", "Japan Exclusive", "grail", 250, 500),
        ("Nintendo", "Game Boy Color Manchester United Red", "Game Boy Color", "Manchester United Red (EU)", "Special Edition", "high", 110, 230),
        ("Nintendo", "Game Boy Color ANA Pikachu Blue", "Game Boy Color", "ANA All Nippon Airways Pikachu (Japan)", "Japan Exclusive", "grail", 200, 400),

        # --- Neo Geo Pocket Color Games (+8) ---
        ("SNK", "Sonic Pocket Adventure NGPC", "Neo Geo Pocket Color", "Sonic the Hedgehog Pocket Adventure (Game)", "Standard", "high", 65, 140),
        ("SNK", "Match of the Millennium NGPC (Japanese)", "Neo Geo Pocket Color", "SNK vs Capcom MOTM (Game, Japan)", "Japan Exclusive", "high", 80, 170),
        ("SNK", "Puzzle Bobble Mini NGPC", "Neo Geo Pocket Color", "Puzzle Bobble Mini (Game, Japan)", "Japan Exclusive", "mid", 40, 85),
        ("SNK", "Neo Turf Masters NGPC", "Neo Geo Pocket Color", "Neo Turf Masters / Big Tournament Golf (Game)", "Standard", "high", 85, 175),
        ("SNK", "Crush Roller NGPC", "Neo Geo Pocket Color", "Crush Roller (Game, Japan)", "Japan Exclusive", "mid", 45, 95),
        ("SNK", "Cool Cool Jam NGPC", "Neo Geo Pocket Color", "Cool Cool Jam (Game, Japan)", "Japan Exclusive", "high", 100, 210),
        ("SNK", "Ogre Battle NGPC", "Neo Geo Pocket Color", "Ogre Battle: Legend of the Zenobia Prince (Game, Japan)", "Japan Exclusive", "high", 120, 250),

        # --- Sega Game Gear Games (+8) ---
        ("Sega", "Sonic the Hedgehog Game Gear", "Game Gear", "Sonic the Hedgehog (Game)", "Standard", "mid", 15, 35),
        ("Sega", "Sonic Triple Trouble Game Gear", "Game Gear", "Sonic Triple Trouble (Game)", "Standard", "mid", 20, 45),
        ("Sega", "Shining Force: The Sword of Hajya GG", "Game Gear", "Shining Force: Sword of Hajya (Game)", "Standard", "high", 60, 130),
        ("Sega", "Shinobi Game Gear", "Game Gear", "Shinobi (Game)", "Standard", "mid", 25, 55),
        ("Sega", "GG Shinobi II Game Gear", "Game Gear", "GG Shinobi II: The Silent Fury (Game)", "Standard", "mid", 30, 65),
        ("Sega", "Columns Game Gear", "Game Gear", "Columns (Game)", "Standard", "standard", 10, 25),
        ("Sega", "Defenders of Oasis Game Gear", "Game Gear", "Defenders of Oasis (Game)", "Standard", "high", 70, 150),
        ("Sega", "Dragon Crystal Game Gear", "Game Gear", "Dragon Crystal (Game)", "Standard", "mid", 25, 55),

        # --- Atari Lynx Games (+7) ---
        ("Atari", "Batman Returns Lynx", "Atari Lynx", "Batman Returns (Game)", "Standard", "mid", 30, 65),
        ("Atari", "Shadow of the Beast Lynx", "Atari Lynx", "Shadow of the Beast (Game)", "Standard", "mid", 35, 75),
        ("Atari", "Warbirds Lynx", "Atari Lynx", "Warbirds (Game)", "Standard", "mid", 20, 45),
        ("Atari", "Stun Runner Lynx", "Atari Lynx", "Stun Runner (Game)", "Standard", "mid", 20, 50),
        ("Atari", "Xybots Lynx", "Atari Lynx", "Xybots (Game)", "Standard", "mid", 25, 55),
        ("Atari", "Rygar Lynx", "Atari Lynx", "Rygar (Game)", "Standard", "high", 60, 130),
        ("Atari", "Toki Lynx", "Atari Lynx", "Toki (Game)", "Standard", "mid", 30, 65),

        # --- WonderSwan Color Games (+7) ---
        ("Bandai", "RockMan EXE WonderSwan WSC", "WonderSwan Color", "RockMan EXE WS (Game, Japan)", "Japan Exclusive", "high", 70, 150),
        ("Bandai", "Densha de Go! WSC", "WonderSwan Color", "Densha de Go! (Game, Japan)", "Japan Exclusive", "mid", 30, 65),
        ("Bandai", "Digimon Anode Tamer WSC", "WonderSwan Color", "Digimon Adventure 02 Tag Tamers (Game, Japan)", "Japan Exclusive", "mid", 45, 95),
        ("Bandai", "Naruto Konoha Ninpouchou WSC", "WonderSwan Color", "Naruto Konoha Ninpouchou (Game, Japan)", "Japan Exclusive", "mid", 35, 75),
        ("Bandai", "Star Hearts WSC", "WonderSwan Color", "Star Hearts Hoshi to Daichi no Shisha (Game, Japan)", "Japan Exclusive", "high", 90, 190),
        ("Bandai", "Makai Toushi SaGa WSC", "WonderSwan Color", "Makai Toushi SaGa (Final Fantasy Legend WSC) (Game, Japan)", "Japan Exclusive", "high", 60, 130),
        ("Bandai", "Rhyme Rider Kerorican WSC", "WonderSwan Color", "Rhyme Rider Kerorican (Game, Japan)", "Japan Exclusive", "mid", 40, 85),

        # --- Game Boy Advance SP Limited Editions (+8) ---
        ("Nintendo", "Game Boy Advance SP Rayquaza Green", "Game Boy Advance SP", "Pokemon Rayquaza Green (Japan)", "Japan Exclusive", "grail", 280, 560),
        ("Nintendo", "Game Boy Advance SP Groudon Red", "Game Boy Advance SP", "Pokemon Groudon Red (Japan)", "Japan Exclusive", "grail", 250, 500),
        ("Nintendo", "Game Boy Advance SP Kyogre Blue", "Game Boy Advance SP", "Pokemon Kyogre Blue (Japan)", "Japan Exclusive", "grail", 260, 520),
        ("Nintendo", "Game Boy Advance SP Classic NES Black", "Game Boy Advance SP", "Classic NES Black AGS-001 (NA)", "Special Edition", "high", 100, 210),
        ("Nintendo", "Game Boy Advance SP Pearl Blue AGS-101", "Game Boy Advance SP", "Pearl Blue AGS-101 Backlit (NA)", "Standard", "high", 110, 230),

        # --- DS Lite Special Editions (+8) ---
        ("Nintendo", "Nintendo DS Lite Pokemon Diamond Pearl Dialga Palkia", "Nintendo DS Lite", "Pokemon Diamond Pearl Dialga Palkia (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Nintendo", "Nintendo DS Lite Crimson/Black Mario", "Nintendo DS Lite", "Crimson/Black Mario Limited (NA)", "Special Edition", "high", 80, 170),
        ("Nintendo", "Nintendo DS Lite Pikachu Yellow (JP Edition)", "Nintendo DS Lite", "Pikachu Yellow (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Nintendo DS Lite Love Plus+ Nene", "Nintendo DS Lite", "Love Plus+ Nene Deluxe (Japan)", "Japan Exclusive", "high", 150, 310),
        ("Nintendo", "Nintendo DS Lite Kingdom Hearts 358/2 Days", "Nintendo DS Lite", "Kingdom Hearts 358/2 Days Silver (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Nintendo", "Nintendo DS Lite Guitar Hero On Tour Pack", "Nintendo DS Lite", "Guitar Hero On Tour White Bundle (NA)", "Console Bundle", "mid", 60, 130),

        # --- PSP Limited Consoles (+8) ---
        ("Sony", "PSP-3000 Monster Hunter 3rd Blue", "PSP-3000", "Monster Hunter Portable 3rd Hunter Blue (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Sony", "PSP-3000 Kingdom Hearts Birth by Sleep White", "PSP-3000", "Kingdom Hearts Birth by Sleep White (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Sony", "PSP-3000 Dissidia Final Fantasy Silver", "PSP-3000", "Dissidia Final Fantasy 20th Anniversary Silver (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Sony", "PSP-3000 Gundam vs Gundam Red", "PSP-3000", "Gundam vs Gundam Red Char's Custom (Japan)", "Japan Exclusive", "high", 140, 290),
        ("Sony", "PSP-3000 Gran Turismo Silver", "PSP-3000", "Gran Turismo Racing Pack Silver (EU)", "Console Bundle", "mid", 70, 150),
        ("Sony", "PSP-1000 Metal Gear Solid Platinum Silver", "PSP-1000", "Metal Gear Solid Peace Walker Platinum Silver (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Sony", "PSP-3000 Hatsune Miku Project Diva 2nd", "PSP-3000", "Hatsune Miku Project Diva 2nd Turquoise (Japan)", "Japan Exclusive", "high", 160, 330),

        # --- Analogue Pocket Accessories (+7) ---
        ("Analogue", "Analogue Pocket Adapter GG", "Analogue Pocket", "Game Gear Adapter Cartridge", "Standard", "mid", 30, 45),
        ("Analogue", "Analogue Pocket Adapter NGPC", "Analogue Pocket", "Neo Geo Pocket Color Adapter", "Standard", "mid", 30, 45),
        ("Analogue", "Analogue Pocket Adapter TG16", "Analogue Pocket", "TurboGrafx-16 Adapter", "Standard", "mid", 30, 45),
        ("Analogue", "Analogue Pocket Adapter Lynx", "Analogue Pocket", "Atari Lynx Adapter", "Standard", "mid", 30, 45),
        ("Analogue", "Analogue Pocket Hard Case", "Analogue Pocket", "Official Hard Carrying Case", "Standard", "standard", 20, 30),
        ("Analogue", "Analogue Pocket Screen Protector Set", "Analogue Pocket", "Official Screen Protector (2-pack)", "Standard", "standard", 8, 12),
        ("Analogue", "Analogue Pocket Transparent Red", "Analogue Pocket", "Transparent Red Limited", "Limited Color", "grail", 350, 460),

        # --- More Nintendo Switch Lite Limited Editions (+7) ---
        ("Nintendo", "Switch Lite Zacian and Zamazenta", "Switch Lite", "Pokemon Sword Shield Zacian Zamazenta (EU)", "Special Edition", "high", 160, 250),
        ("Nintendo", "Switch Lite Dialga & Palkia", "Switch Lite", "Pokemon Brilliant Diamond Shining Pearl (EU)", "Special Edition", "high", 170, 260),
        ("Nintendo", "Switch Lite Coral", "Switch Lite", "Coral (Japan/NA)", "Standard", "mid", 120, 180),
        ("Nintendo", "Switch Lite Hyrule Gold", "Switch Lite", "Hyrule Edition Gold (NA)", "Special Edition", "high", 180, 280),
        ("Nintendo", "Switch Lite Isabelle Aloha Green", "Switch Lite", "Animal Crossing Isabelle Aloha (Japan)", "Japan Exclusive", "high", 190, 300),
        ("Nintendo", "Switch Lite Giratina Edition Japan", "Switch Lite", "Pokemon Legends Arceus Giratina (Japan)", "Japan Exclusive", "high", 200, 310),
        ("Nintendo", "Switch Lite Blue", "Switch Lite", "Blue (EU/NA)", "Standard", "mid", 110, 170),

        # --- More Tamagotchi (+6) ---
        ("Bandai", "Tamagotchi Connection V5 Celebrity Blue", "Tamagotchi", "Connection V5 Celebrity Blue (2008)", "Standard", "mid", 25, 55),
        ("Bandai", "Tamagotchi iD L 15th Anniversary Royal Purple", "Tamagotchi", "iD L 15th Anniversary Royal Purple (Japan)", "Japan Exclusive", "high", 80, 170),
        ("Bandai", "Tamagotchi On Wonder Garden Turquoise", "Tamagotchi", "On Wonder Garden Turquoise (NA)", "Standard", "mid", 35, 70),
        ("Bandai", "Tamagotchi Uni Lavender", "Tamagotchi", "Uni Lavender (2023)", "Standard", "mid", 45, 65),
        ("Bandai", "Tamagotchi Smart Niziu Special Set", "Tamagotchi", "Smart NiziU Special Set (Japan)", "Japan Exclusive", "high", 100, 200),

        # --- More Modern Retro Handhelds (+6) ---
        ("Anbernic", "Anbernic RG556 Black", "RG556", "Black AMOLED", "Modded/Custom", "mid", 85, 110),
        ("Anbernic", "Anbernic RG353M Silver Metal", "RG353M", "Silver Metal Body", "Modded/Custom", "mid", 70, 90),
        ("Powkiddy", "Powkiddy RGB30 Clear Purple", "RGB30", "Clear Purple", "Modded/Custom", "mid", 45, 60),
        ("AYANEO", "AYANEO Pocket S", "AYANEO Pocket S", "White 6-inch OLED", "Modded/Custom", "high", 300, 380),
        ("GPD", "GPD Win Max 2 2024", "GPD Win Max 2", "2024 Refresh Silver", "Modded/Custom", "high", 550, 650),

        # --- More Misc Vintage (+3) ---
        ("Epoch", "Epoch Game Pocket Computer Astro Bomber", "Game Pocket Computer", "Astro Bomber Cartridge (Japan)", "Japan Exclusive", "high", 80, 170),
        ("Milton Bradley", "MB Microvision Block Buster", "Microvision", "Block Buster Cartridge", "Standard", "mid", 40, 85),
        ("Watara", "Watara Supervision Green Console", "Supervision", "Green Console (PAL)", "Standard", "mid", 35, 70),
    ]
    catalog = []
    for brand, name, platform, variant_note, condition, rarity_tier, price_loose, price_cib in items:
        if "Japan" in variant_note or condition == "Japan Exclusive":
            region = "JPN"
        elif "NA" in variant_note:
            region = "NA"
        else:
            region = "EU"
        is_limited = condition in ("Limited Color", "Special Edition", "Japan Exclusive", "Anniversary")
        year = _platform_year(platform, name)
        catalog.append({
            "brand": brand,
            "name": name,
            "platform": platform,
            "variant_note": variant_note,
            "condition": condition,
            "rarity_tier": rarity_tier,
            "price_loose_eur": price_loose,
            "price_cib_eur": price_cib,
            "region": region,
            "is_limited_edition": is_limited,
            "year": year,
        })
    return catalog


def _variant_expansion() -> list[dict]:
    """~115 color and edition variants for major retro handhelds.

    Covers shell colors, limited editions, and regional exclusives for:
    Game Boy (Play It Loud), Game Boy Pocket, Game Boy Light, Game Boy Color,
    Game Boy Advance, GBA SP, DS Lite, PSP, 3DS/3DS XL, Neo Geo Pocket Color,
    Sega Game Gear, Atari Lynx, and WonderSwan.
    """
    items = [
        # ---------------------------------------------------------------
        # Game Boy DMG-01 — Play It Loud colors not yet covered
        # (existing: Gray, Red, Green, Yellow, Black, Clear, White, Blue, Ice Blue)
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy DMG-01 Play It Loud Vibrant Yellow", "Game Boy", "Play It Loud Vibrant Yellow (JP)", "Limited Color", "high", 75, 155),
        ("Nintendo", "Game Boy DMG-01 Deep Green", "Game Boy", "Deep Green (Japan)", "Japan Exclusive", "high", 70, 145),

        # ---------------------------------------------------------------
        # Game Boy Pocket — colors not yet listed
        # (existing: Silver, Ice Blue, Clear Purple, Red, Green, Yellow, Pink, Black, Gold, Extreme Green)
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Pocket Clear", "Game Boy Pocket", "Clear/Transparent", "Limited Color", "high", 75, 155),
        ("Nintendo", "Game Boy Pocket Blue", "Game Boy Pocket", "Blue", "Standard", "mid", 35, 75),
        ("Nintendo", "Game Boy Pocket Atomic Purple", "Game Boy Pocket", "Atomic Purple (NA)", "Limited Color", "high", 80, 165),

        # ---------------------------------------------------------------
        # Game Boy Light — additional JP colors
        # (existing: Gold, Silver, Astro Boy, Famitsu, Tezuka Osamu, Pikachu)
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Light Clear Yellow", "Game Boy Light", "Clear Yellow (Japan)", "Japan Exclusive", "grail", 240, 490),

        # ---------------------------------------------------------------
        # Game Boy Color — shell colors not yet covered
        # (existing: Grape, Berry, Teal, Dandelion, Kiwi, Atomic Purple, Clear, Midnight Blue + many JP exclusives)
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Color Teal (NA)", "Game Boy Color", "Teal Jade (NA Release)", "Standard", "mid", 38, 80),
        ("Nintendo", "Game Boy Color Berry (EU)", "Game Boy Color", "Berry Pink (EU Release)", "Standard", "mid", 40, 85),
        ("Nintendo", "Game Boy Color Grape (EU)", "Game Boy Color", "Grape Purple (EU Release)", "Standard", "mid", 40, 85),
        ("Nintendo", "Game Boy Color Dandelion (EU)", "Game Boy Color", "Dandelion Yellow (EU Release)", "Standard", "mid", 42, 90),
        ("Nintendo", "Game Boy Color Kiwi (EU)", "Game Boy Color", "Kiwi Green (EU Release)", "Standard", "mid", 42, 88),
        ("Nintendo", "Game Boy Color Clear Purple", "Game Boy Color", "Clear/Atomic Purple (NA)", "Standard", "mid", 45, 95),
        ("Nintendo", "Game Boy Color Neotones Midnight Blue", "Game Boy Color", "Neotones Midnight Blue (Japan)", "Japan Exclusive", "high", 75, 155),
        ("Nintendo", "Game Boy Color Ice Blue (JP)", "Game Boy Color", "Ice Blue Translucent (Japan)", "Japan Exclusive", "high", 80, 165),

        # ---------------------------------------------------------------
        # Game Boy Advance — all standard colors
        # (existing: Indigo, Glacier, Flame Red, White/Arctic, Spice Orange, Black, Fuchsia, Gold, Midnight Blue)
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Advance Glacier Clear", "Game Boy Advance", "Glacier Clear Milky Blue (NA)", "Standard", "mid", 50, 110),
        ("Nintendo", "Game Boy Advance Arctic White (NA)", "Game Boy Advance", "Arctic White (NA Release)", "Standard", "mid", 50, 110),
        ("Nintendo", "Game Boy Advance Orange (JP)", "Game Boy Advance", "Orange (Japan)", "Japan Exclusive", "high", 80, 170),
        ("Nintendo", "Game Boy Advance Platinum", "Game Boy Advance", "Platinum Silver", "Standard", "mid", 48, 105),
        ("Nintendo", "Game Boy Advance Clear Blue", "Game Boy Advance", "Clear Blue Toys R Us (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Nintendo", "Game Boy Advance Suicune Blue", "Game Boy Advance", "Pokemon Center Suicune Blue (Japan)", "Japan Exclusive", "grail", 190, 390),

        # ---------------------------------------------------------------
        # Game Boy Advance SP — colors & editions
        # (existing: Cobalt, Graphite, AGS-101 Pearl, NES, Pikachu, Tribal, FFT, Famicom, many Pokemon CEs)
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Advance SP Pearl Blue AGS-001", "Game Boy Advance SP", "Pearl Blue AGS-001", "Standard", "mid", 55, 115),
        ("Nintendo", "Game Boy Advance SP Cobalt Blue AGS-101", "Game Boy Advance SP", "Cobalt Blue AGS-101 Backlit", "Standard", "high", 95, 200),
        ("Nintendo", "Game Boy Advance SP Graphite AGS-101", "Game Boy Advance SP", "Graphite AGS-101 Backlit", "Standard", "high", 95, 200),
        ("Nintendo", "Game Boy Advance SP Flame Red AGS-101", "Game Boy Advance SP", "Flame Red AGS-101 Backlit", "Standard", "high", 100, 210),
        ("Nintendo", "Game Boy Advance SP Pearl Pink AGS-101", "Game Boy Advance SP", "Pearl Pink AGS-101 Backlit", "Standard", "high", 100, 210),
        ("Nintendo", "Game Boy Advance SP Famicom Color (JP)", "Game Boy Advance SP", "Famicom Color Wine Red/White (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Game Boy Advance SP Platinum Silver", "Game Boy Advance SP", "Platinum Silver AGS-001", "Standard", "mid", 55, 115),
        ("Nintendo", "Game Boy Advance SP Snow White", "Game Boy Advance SP", "Snow White AGS-001 (EU)", "Standard", "mid", 58, 120),
        ("Nintendo", "Game Boy Advance SP Midnight Blue", "Game Boy Advance SP", "Midnight Blue AGS-001 (Japan)", "Japan Exclusive", "high", 80, 170),
        ("Nintendo", "Game Boy Advance SP Mario vs DK", "Game Boy Advance SP", "Mario vs Donkey Kong Red (EU)", "Special Edition", "high", 130, 270),
        ("Nintendo", "Game Boy Advance SP Famicom Mini 20th Anniversary", "Game Boy Advance SP", "Famicom Mini Vol.2 20th Anniversary (Japan)", "Japan Exclusive", "grail", 230, 460),

        # ---------------------------------------------------------------
        # Nintendo DS Lite — all standard + LE colors
        # (existing: Polar White, Crimson/Black, Enamel Navy, Metallic Rose, Ice Blue, Jet Black, Onyx, Coral Pink)
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo DS Lite Cobalt Blue/Black", "Nintendo DS Lite", "Cobalt Blue/Black", "Standard", "mid", 30, 65),
        ("Nintendo", "Nintendo DS Lite Noble Pink", "Nintendo DS Lite", "Noble Pink", "Standard", "mid", 35, 70),
        ("Nintendo", "Nintendo DS Lite Gloss Silver", "Nintendo DS Lite", "Gloss Silver", "Standard", "mid", 30, 65),
        ("Nintendo", "Nintendo DS Lite Crimson Red", "Nintendo DS Lite", "Crimson Red (Japan)", "Japan Exclusive", "mid", 35, 70),
        ("Nintendo", "Nintendo DS Lite Crystal White", "Nintendo DS Lite", "Crystal White (Japan)", "Japan Exclusive", "mid", 32, 65),
        ("Nintendo", "Nintendo DS Lite Enamel Navy (EU)", "Nintendo DS Lite", "Enamel Navy (EU Release)", "Standard", "mid", 30, 65),
        ("Nintendo", "Nintendo DS Lite Gross White (EU)", "Nintendo DS Lite", "Gross White (EU Release)", "Standard", "standard", 25, 55),
        ("Nintendo", "Nintendo DS Lite Turquoise", "Nintendo DS Lite", "Turquoise (Japan)", "Japan Exclusive", "mid", 35, 75),
        ("Nintendo", "Nintendo DS Lite Lime Green", "Nintendo DS Lite", "Lime Green (Japan)", "Japan Exclusive", "mid", 38, 78),
        ("Nintendo", "Nintendo DS Lite Mario Red", "Nintendo DS Lite", "New Super Mario Bros Red (NA)", "Special Edition", "high", 75, 160),

        # ---------------------------------------------------------------
        # Sony PSP — all colors & editions
        # (existing: Piano Black, Ceramic White, Silver, Ice Silver, Vibrant Blue, Radiant Red, Pearl White, many JP)
        # ---------------------------------------------------------------
        ("Sony", "PSP-1000 Champagne Gold", "PSP-1000", "Champagne Gold (Japan)", "Japan Exclusive", "high", 65, 135),
        ("Sony", "PSP-2000 Piano Black", "PSP-2000", "Piano Black Slim", "Standard", "mid", 35, 75),
        ("Sony", "PSP-2000 Ceramic White", "PSP-2000", "Ceramic White Slim", "Standard", "mid", 35, 75),
        ("Sony", "PSP-2000 Mystic Silver", "PSP-2000", "Mystic Silver Slim", "Standard", "mid", 38, 80),
        ("Sony", "PSP-2000 Deep Red", "PSP-2000", "Deep Red (Japan)", "Japan Exclusive", "mid", 45, 95),
        ("Sony", "PSP-2000 Matt Bronze", "PSP-2000", "Matt Bronze (Japan)", "Japan Exclusive", "mid", 50, 100),
        ("Sony", "PSP-3000 Mystic Silver", "PSP-3000", "Mystic Silver", "Standard", "mid", 42, 88),
        ("Sony", "PSP-3000 Piano Black", "PSP-3000", "Piano Black", "Standard", "mid", 40, 85),
        ("Sony", "PSP-3000 God of War Edition", "PSP-3000", "God of War Ghost of Sparta Red/Black (NA)", "Special Edition", "high", 90, 190),
        ("Sony", "PSP-1000 Crisis Core FF VII Bundle", "PSP-1000", "Crisis Core FFVII Silver Bundle (NA)", "Console Bundle", "high", 95, 200),

        # ---------------------------------------------------------------
        # Nintendo 3DS / 3DS XL — colors & special editions
        # (existing: Aqua Blue, Cosmo Black, Flame Red, Midnight Purple, many SEs)
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo 3DS Pearl Pink", "Nintendo 3DS", "Pearl Pink", "Standard", "mid", 60, 130),
        ("Nintendo", "Nintendo 3DS Ice White", "Nintendo 3DS", "Ice White", "Standard", "mid", 58, 125),
        ("Nintendo", "Nintendo 3DS Cobalt Blue", "Nintendo 3DS", "Cobalt Blue", "Standard", "mid", 60, 130),
        ("Nintendo", "Nintendo 3DS Misty Pink", "Nintendo 3DS", "Misty Pink (Japan)", "Japan Exclusive", "mid", 65, 140),
        ("Nintendo", "Nintendo 3DS Pure White (JP)", "Nintendo 3DS", "Pure White (Japan)", "Japan Exclusive", "mid", 60, 130),
        ("Nintendo", "Nintendo 3DS Pikachu Limited Yellow", "Nintendo 3DS", "Pikachu Limited Edition Yellow (Japan)", "Japan Exclusive", "high", 150, 310),
        ("Nintendo", "Nintendo 3DS Fire Emblem Awakening Cobalt", "Nintendo 3DS", "Fire Emblem Awakening Cobalt Blue (NA)", "Special Edition", "high", 140, 290),
        ("Nintendo", "Nintendo 3DS Monster Hunter 4 White", "Nintendo 3DS", "Monster Hunter 4 Limited White (Japan)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "Nintendo 3DS XL Silver/Black", "Nintendo 3DS XL", "Silver/Black", "Standard", "mid", 65, 140),
        ("Nintendo", "Nintendo 3DS XL White/Pink", "Nintendo 3DS XL", "White/Pink", "Standard", "mid", 68, 145),
        ("Nintendo", "Nintendo 3DS XL Zelda Triforce Gold", "Nintendo 3DS XL", "Zelda Triforce Gold (Japan)", "Japan Exclusive", "high", 160, 340),
        ("Nintendo", "Nintendo 3DS XL Fire Emblem Awakening Blue", "Nintendo 3DS XL", "Fire Emblem Awakening Blue (NA)", "Special Edition", "high", 150, 310),
        ("Nintendo", "Nintendo 3DS XL Monster Hunter 4 Silver", "Nintendo 3DS XL", "Monster Hunter 4 Silver (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Nintendo", "New Nintendo 3DS XL Monster Hunter Cross", "New Nintendo 3DS XL", "Monster Hunter X/Cross Hunting Life (Japan)", "Japan Exclusive", "high", 135, 280),
        ("Nintendo", "New Nintendo 3DS XL Fire Emblem Fates White", "New Nintendo 3DS XL", "Fire Emblem Fates White (Japan)", "Japan Exclusive", "high", 145, 300),

        # ---------------------------------------------------------------
        # Neo Geo Pocket Color — additional shell colors
        # (existing: Anthracite, Crystal Blue, Platinum Silver, Camo Blue, Carbon Black,
        #  Crystal Yellow, Stone Blue, Solid Silver, Crystal Clear, Aqua Blue, Platinum Blue, Dark Blue)
        # ---------------------------------------------------------------
        ("SNK", "Neo Geo Pocket Color Pearl White", "Neo Geo Pocket Color", "Pearl White", "Standard", "high", 90, 190),
        ("SNK", "Neo Geo Pocket Color Crystal Green", "Neo Geo Pocket Color", "Crystal Green", "Limited Color", "high", 100, 210),
        ("SNK", "Neo Geo Pocket Color Camouflage Green", "Neo Geo Pocket Color", "Camouflage Green", "Limited Color", "high", 110, 230),
        ("SNK", "Neo Geo Pocket Color Cotton Candy Blue", "Neo Geo Pocket Color", "Cotton Candy Blue (Japan)", "Japan Exclusive", "high", 105, 220),
        ("SNK", "Neo Geo Pocket Color Capcom Red", "Neo Geo Pocket Color", "Capcom VS SNK Red (Japan)", "Japan Exclusive", "high", 120, 250),

        # ---------------------------------------------------------------
        # Sega Game Gear — special editions
        # (existing: Black, Blue, White, Coca-Cola Red, Yellow, Smoke, Red, Kids Gear, Majesco)
        # ---------------------------------------------------------------
        ("Sega", "Game Gear Crystal Blue", "Game Gear", "Crystal Blue (Japan)", "Japan Exclusive", "high", 115, 240),
        ("Sega", "Game Gear Gunstar Heroes Edition", "Game Gear", "Gunstar Heroes Bundle (Japan)", "Japan Exclusive", "high", 130, 270),
        ("Sega", "Game Gear Black Sega Sports", "Game Gear", "Sports Edition Black", "Special Edition", "high", 70, 150),
        ("Sega", "Game Gear Columns Bundle", "Game Gear", "Columns Pack-In Bundle (NA)", "Console Bundle", "mid", 40, 90),
        ("Sega", "Game Gear TV Tuner Pack Bundle", "Game Gear", "TV Tuner Pack Bundle (NA)", "Console Bundle", "high", 80, 170),

        # ---------------------------------------------------------------
        # Atari Lynx — I and II variants
        # (existing: Lynx I, Lynx II, Lynx I Cal Games Bundle, Lynx II Batman Returns, McWill Mod)
        # ---------------------------------------------------------------
        ("Atari", "Atari Lynx I White Edition", "Atari Lynx", "White Edition PAG-0200", "Limited Color", "high", 100, 220),
        ("Atari", "Atari Lynx II Clear Shell", "Atari Lynx II", "Clear/Transparent Shell (Aftermarket)", "Modded/Custom", "high", 90, 190),
        ("Atari", "Atari Lynx I Sun Visor Bundle", "Atari Lynx", "Sun Visor + Pouch Bundle (NA)", "Console Bundle", "high", 130, 280),
        ("Atari", "Atari Lynx II Todd's Adventures Bundle", "Atari Lynx II", "Todd's Adventures Slime World Bundle", "Console Bundle", "high", 95, 210),
        ("Atari", "Atari Lynx I Chip's Challenge Pack", "Atari Lynx", "Chip's Challenge Pack-In (NA)", "Console Bundle", "high", 110, 240),

        # ---------------------------------------------------------------
        # WonderSwan — color variants
        # (existing: Crystal Blue, Wine Red, Silver, Skeleton Black, Crystal Orange/Black, One Piece, many games)
        # ---------------------------------------------------------------
        ("Bandai", "WonderSwan Color Pearl Blue", "WonderSwan Color", "Pearl Blue (Japan)", "Japan Exclusive", "high", 65, 140),
        ("Bandai", "WonderSwan Color Sherbet Pink", "WonderSwan Color", "Sherbet Pink (Japan)", "Japan Exclusive", "high", 70, 150),
        ("Bandai", "WonderSwan Color Crystal Red", "WonderSwan Color", "Crystal Red (Japan)", "Japan Exclusive", "high", 70, 150),
        ("Bandai", "WonderSwan Color Crystal White", "WonderSwan Color", "Crystal White (Japan)", "Japan Exclusive", "high", 60, 130),
        ("Bandai", "WonderSwan Original Blue Metallic", "WonderSwan", "Blue Metallic (Japan)", "Japan Exclusive", "high", 55, 120),
        ("Bandai", "WonderSwan Original Wine Red", "WonderSwan", "Wine Red (Japan)", "Japan Exclusive", "high", 60, 130),
        ("Bandai", "WonderSwan Original Skeleton Green", "WonderSwan", "Skeleton Green (Japan)", "Japan Exclusive", "high", 65, 140),
        ("Bandai", "WonderSwan Original Sherbet Melon Pink", "WonderSwan", "Sherbet Melon Pink (Japan)", "Japan Exclusive", "high", 70, 150),
        ("Bandai", "WonderSwan Color Gundam SEED", "WonderSwan Color", "Gundam SEED Limited (Japan)", "Japan Exclusive", "high", 110, 230),
        ("Bandai", "SwanCrystal Violet", "SwanCrystal", "Violet (Japan)", "Japan Exclusive", "high", 75, 160),
        ("Bandai", "SwanCrystal Blue", "SwanCrystal", "Blue (Japan)", "Japan Exclusive", "high", 70, 150),

        # ---------------------------------------------------------------
        # Game Boy Advance — more regional/color variants
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Advance Transparent Pink", "Game Boy Advance", "Transparent Milky Pink (Japan)", "Japan Exclusive", "high", 85, 175),
        ("Nintendo", "Game Boy Advance Clear Orange", "Game Boy Advance", "Clear Orange (Japan)", "Japan Exclusive", "high", 90, 185),

        # ---------------------------------------------------------------
        # Game Boy Color — more shell color variants
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Color Lime Green (JP)", "Game Boy Color", "Lime Green (Japan)", "Japan Exclusive", "high", 70, 145),
        ("Nintendo", "Game Boy Color Sakura Pink", "Game Boy Color", "Sakura Pink (Japan)", "Japan Exclusive", "high", 75, 155),

        # ---------------------------------------------------------------
        # DS Lite — more JP colors
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo DS Lite Gross Silver (JP)", "Nintendo DS Lite", "Gross Silver (Japan)", "Japan Exclusive", "mid", 32, 68),
        ("Nintendo", "Nintendo DS Lite Candy Pink", "Nintendo DS Lite", "Candy Pink (Japan)", "Japan Exclusive", "mid", 38, 78),

        # ---------------------------------------------------------------
        # PSP — more editions
        # ---------------------------------------------------------------
        ("Sony", "PSP-2000 Star Wars White Bundle", "PSP-2000", "Star Wars Battlefront Renegade Squadron White (NA)", "Console Bundle", "high", 80, 170),
        ("Sony", "PSP-3000 Final Fantasy Dissidia 012 White", "PSP-3000", "Dissidia 012 Final Fantasy White (Japan)", "Japan Exclusive", "high", 115, 240),
        ("Sony", "PSP-1000 Metal Gear Solid Camo", "PSP-1000", "Metal Gear Solid Portable Ops Camo Green (Japan)", "Japan Exclusive", "high", 110, 230),

        # ---------------------------------------------------------------
        # 3DS — more special editions
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo 3DS Zelda Ocarina of Time 3D", "Nintendo 3DS", "Zelda Ocarina of Time 3D Green (EU)", "Special Edition", "high", 140, 290),
        ("Nintendo", "Nintendo 3DS XL Luigi Mansion Green", "Nintendo 3DS XL", "Luigi's Mansion Dark Moon Green (NA)", "Special Edition", "high", 130, 270),
        ("Nintendo", "Nintendo 3DS XL Animal Crossing New Leaf", "Nintendo 3DS XL", "Animal Crossing New Leaf Pop (NA)", "Special Edition", "high", 120, 250),
        ("Nintendo", "New Nintendo 3DS XL Super NES Edition", "New Nintendo 3DS XL", "Super NES / Super Famicom Edition (NA)", "Special Edition", "high", 170, 350),
        ("Nintendo", "New Nintendo 3DS XL Zelda Hyrule Gold", "New Nintendo 3DS XL", "Legend of Zelda Hyrule Gold (EU)", "Special Edition", "high", 165, 340),

        # ---------------------------------------------------------------
        # Sega Game Gear — more variants
        # ---------------------------------------------------------------
        ("Sega", "Game Gear Sonic Blue Limited", "Game Gear", "Sonic Blue Pack-In (EU)", "Console Bundle", "high", 85, 175),
        ("Sega", "Game Gear Green (JP)", "Game Gear", "Green (Japan)", "Japan Exclusive", "high", 120, 250),

        # ---------------------------------------------------------------
        # Neo Geo Pocket Color — final colors
        # ---------------------------------------------------------------
        ("SNK", "Neo Geo Pocket Color Metallic Blue", "Neo Geo Pocket Color", "Metallic Blue", "Standard", "high", 88, 185),
        ("SNK", "Neo Geo Pocket Color Crystal Red", "Neo Geo Pocket Color", "Crystal Red", "Limited Color", "high", 105, 220),

        # ---------------------------------------------------------------
        # Atari Lynx — more bundles
        # ---------------------------------------------------------------
        ("Atari", "Atari Lynx II Blue Lightning Pack", "Atari Lynx II", "Blue Lightning Pack-In (NA)", "Console Bundle", "high", 90, 200),

        # ---------------------------------------------------------------
        # WonderSwan — final variants
        # ---------------------------------------------------------------
        ("Bandai", "WonderSwan Original Mother Pink", "WonderSwan", "Mother Pink (Japan)", "Japan Exclusive", "high", 75, 160),
        ("Bandai", "WonderSwan Color Gundam Wing Blue", "WonderSwan Color", "Gundam Wing Endless Duel Blue (Japan)", "Japan Exclusive", "high", 100, 210),

        # ---------------------------------------------------------------
        # Game Gear Games — Sonic, Shinobi, Columns
        # ---------------------------------------------------------------
        ("Sega", "Sonic the Hedgehog (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "mid", 20, 45),
        ("Sega", "Sonic the Hedgehog 2 (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "mid", 18, 40),
        ("Sega", "Sonic Chaos (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "mid", 22, 48),
        ("Sega", "Sonic Triple Trouble (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "mid", 25, 55),
        ("Sega", "Sonic Drift 2 (Game Gear) CIB", "Game Gear", "CIB Japan", "Japan Exclusive", "mid", 20, 42),
        ("Sega", "Shinobi (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "mid", 25, 55),
        ("Sega", "Shinobi II (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "mid", 30, 65),
        ("Sega", "The GG Shinobi (Game Gear) CIB", "Game Gear", "CIB Japan", "Japan Exclusive", "mid", 28, 60),
        ("Sega", "Columns (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "standard", 10, 22),
        ("Sega", "Super Columns (Game Gear) CIB", "Game Gear", "CIB Japan", "Japan Exclusive", "standard", 12, 28),
        ("Sega", "Shining Force: Sword of Hajya (GG) CIB", "Game Gear", "CIB NA Release", "Standard", "high", 60, 130),
        ("Sega", "Defenders of Oasis (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "high", 50, 110),
        ("Sega", "Phantasy Star Adventure (Game Gear) CIB", "Game Gear", "CIB Japan", "Japan Exclusive", "high", 40, 90),
        ("Sega", "Gunstar Heroes (Game Gear) CIB", "Game Gear", "CIB Japan", "Japan Exclusive", "high", 55, 120),
        ("Sega", "Streets of Rage (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "mid", 25, 55),

        # ---------------------------------------------------------------
        # Atari Lynx — more games and variants
        # ---------------------------------------------------------------
        ("Atari", "California Games (Lynx) CIB", "Atari Lynx", "CIB NA Release", "Standard", "mid", 15, 35),
        ("Atari", "Chip's Challenge (Lynx) CIB", "Atari Lynx", "CIB NA Release", "Standard", "mid", 18, 40),
        ("Atari", "Rygar (Lynx) CIB", "Atari Lynx", "CIB NA Release", "Standard", "mid", 30, 65),
        ("Atari", "Shadow of the Beast (Lynx) CIB", "Atari Lynx", "CIB NA Release", "Standard", "high", 55, 120),
        ("Atari", "Todd's Adventures in Slime World (Lynx) CIB", "Atari Lynx", "CIB NA Release", "Standard", "mid", 20, 45),
        ("Atari", "Warbirds (Lynx) CIB", "Atari Lynx", "CIB NA Release", "Standard", "mid", 15, 35),
        ("Atari", "Lemmings (Lynx) CIB", "Atari Lynx", "CIB NA Release", "Standard", "mid", 22, 48),
        ("Atari", "Ninja Gaiden III (Lynx) CIB", "Atari Lynx", "CIB NA Release", "Standard", "high", 65, 140),
        ("Atari", "Dracula the Undead (Lynx) CIB", "Atari Lynx", "CIB NA Release", "Standard", "mid", 35, 75),
        ("Atari", "Turbo Sub (Lynx) CIB", "Atari Lynx", "CIB NA Release", "Standard", "mid", 25, 55),

        # ---------------------------------------------------------------
        # TurboExpress / PC Engine GT
        # ---------------------------------------------------------------
        ("NEC", "TurboExpress Black (CIB)", "TurboExpress", "Black CIB (NA)", "Standard", "high", 180, 350),
        ("NEC", "TurboExpress White (CIB)", "TurboExpress", "White CIB (Japan)", "Japan Exclusive", "grail", 220, 400),
        ("NEC", "PC Engine GT (CIB)", "PC Engine GT", "Black CIB (Japan)", "Japan Exclusive", "grail", 250, 450),
        ("NEC", "PC Engine GT Carrying Case Bundle", "PC Engine GT", "Case Bundle (Japan)", "Japan Exclusive", "grail", 300, 520),
        ("NEC", "Bonk's Adventure (TurboExpress HuCard)", "TurboExpress", "HuCard CIB (NA)", "Standard", "high", 40, 80),
        ("NEC", "Blazing Lazers (TurboExpress HuCard)", "TurboExpress", "HuCard CIB (NA)", "Standard", "mid", 25, 55),
        ("NEC", "Military Madness (TurboExpress HuCard)", "TurboExpress", "HuCard CIB (NA)", "Standard", "mid", 30, 65),
        ("NEC", "Alien Crush (TurboExpress HuCard)", "TurboExpress", "HuCard CIB (NA)", "Standard", "mid", 20, 45),

        # ---------------------------------------------------------------
        # Sega Nomad
        # ---------------------------------------------------------------
        ("Sega", "Sega Nomad (CIB NA)", "Sega Nomad", "Black CIB (NA)", "Standard", "high", 150, 300),
        ("Sega", "Sega Nomad Rechargeable Battery Pack", "Sega Nomad", "Official Battery Pack (NA)", "Standard", "high", 60, 120),
        ("Sega", "Sega Nomad AC Adapter (Official)", "Sega Nomad", "Official AC Adapter", "Standard", "mid", 25, 50),
        ("Sega", "Sega Nomad AV Cable (Official)", "Sega Nomad", "Official AV Out Cable", "Standard", "mid", 20, 40),

        # ---------------------------------------------------------------
        # Rare Cartridges per Platform
        # ---------------------------------------------------------------
        ("Nintendo", "Mega Man V (Game Boy) CIB", "Game Boy", "CIB NA Release", "Standard", "grail", 200, 400),
        ("Nintendo", "Kid Dracula (Game Boy) CIB", "Game Boy", "CIB NA Release", "Standard", "grail", 250, 500),
        ("Nintendo", "Trip World (Game Boy) CIB", "Game Boy", "CIB EU Release", "Standard", "grail", 300, 550),
        ("Nintendo", "Shantae (GBC) CIB", "Game Boy Color", "CIB NA Release", "Standard", "grail", 450, 850),
        ("Nintendo", "Metal Gear Solid (GBC) CIB", "Game Boy Color", "CIB NA Release", "Standard", "high", 60, 120),
        ("Nintendo", "Dragon Warrior III (GBC) CIB", "Game Boy Color", "CIB NA Release", "Standard", "high", 80, 160),
        ("Nintendo", "Drill Dozer (GBA) CIB", "Game Boy Advance", "CIB NA Release", "Standard", "high", 70, 140),
        ("Nintendo", "Ninja Five-O (GBA) CIB", "Game Boy Advance", "CIB NA Release", "Standard", "grail", 350, 650),
        ("Nintendo", "Riviera: The Promised Land (GBA) CIB", "Game Boy Advance", "CIB NA Release", "Standard", "high", 55, 110),

        # ---------------------------------------------------------------
        # Modern Handheld Accessories
        # ---------------------------------------------------------------
        ("Analogue", "Analogue Pocket Dock", "Analogue Pocket", "Official Dock (Black)", "Standard", "mid", 60, 80),
        ("Analogue", "Analogue Pocket Dock (White)", "Analogue Pocket", "Official Dock (White)", "Limited Color", "mid", 65, 85),
        ("Analogue", "Analogue DAC", "Analogue DAC", "Digital to Analog Converter", "Standard", "mid", 75, 95),
        ("Retroid", "Retroid Pocket 4 Pro (Obsidian Black)", "Retroid Pocket 4 Pro", "Obsidian Black", "Standard", "mid", 130, 160),
        ("Retroid", "Retroid Pocket 4 Pro (Retro Silver)", "Retroid Pocket 4 Pro", "Retro Silver", "Limited Color", "mid", 135, 165),
        ("Miyoo", "Miyoo Mini Plus v4 (Clear Blue)", "Miyoo Mini Plus", "Clear Blue v4", "Standard", "mid", 55, 70),
        ("Miyoo", "Miyoo Mini Plus v4 (Clear Black)", "Miyoo Mini Plus", "Clear Black v4", "Standard", "mid", 55, 70),
        ("Anbernic", "Anbernic RG556 (Black)", "Anbernic RG556", "Black OLED Edition", "Standard", "mid", 100, 120),
        ("Anbernic", "Anbernic RG556 (Transparent Purple)", "Anbernic RG556", "Transparent Purple OLED", "Limited Color", "mid", 110, 130),
        ("Trimui", "Trimui Smart Pro (Transparent Red)", "Trimui Smart Pro", "Transparent Red", "Standard", "mid", 55, 70),

        # ---------------------------------------------------------------
        # More GBA SP Special Editions
        # ---------------------------------------------------------------
        ("Nintendo", "GBA SP Tribal Edition", "GBA SP", "Tribal Tattoo Design (EU)", "Special Edition", "high", 90, 180),
        ("Nintendo", "GBA SP SpongeBob Edition", "GBA SP", "SpongeBob SquarePants (NA)", "Special Edition", "high", 100, 200),
        ("Nintendo", "GBA SP Surf Blue", "GBA SP", "Surf Blue (Japan)", "Japan Exclusive", "high", 85, 170),
        ("Nintendo", "GBA SP Kingdom Hearts Chain of Memories", "GBA SP", "Kingdom Hearts Silver (NA)", "Special Edition", "high", 120, 240),
        ("Nintendo", "GBA SP Classic NES Edition Black", "GBA SP", "Classic NES Black/Gray (NA)", "Special Edition", "high", 95, 190),
        ("Nintendo", "GBA SP Graphite (AGS-101)", "GBA SP", "Graphite Backlit AGS-101", "Standard", "high", 100, 200),
        ("Nintendo", "GBA SP Pearl Blue (AGS-101)", "GBA SP", "Pearl Blue Backlit AGS-101", "Standard", "high", 95, 190),
        ("Nintendo", "GBA SP Pearl Pink (AGS-101)", "GBA SP", "Pearl Pink Backlit AGS-101", "Standard", "high", 95, 190),

        # ---------------------------------------------------------------
        # DS Lite Special Editions
        # ---------------------------------------------------------------
        ("Nintendo", "DS Lite Crimson/Black", "DS Lite", "Crimson/Black (NA)", "Standard", "mid", 40, 80),
        ("Nintendo", "DS Lite Zelda Gold (Phantom Hourglass)", "DS Lite", "Zelda Gold Triforce (NA)", "Special Edition", "high", 100, 200),
        ("Nintendo", "DS Lite Final Fantasy Crystal Chronicles", "DS Lite", "Crystal Chronicles Blue (Japan)", "Japan Exclusive", "high", 90, 180),
        ("Nintendo", "DS Lite Guitar Hero On Tour Bundle", "DS Lite", "Guitar Hero Grip Bundle (NA)", "Console Bundle", "mid", 50, 100),
        ("Nintendo", "DS Lite Pokemon Diamond Pearl Dialga Palkia", "DS Lite", "Dialga Palkia Edition (Japan)", "Japan Exclusive", "high", 110, 220),

        # ---------------------------------------------------------------
        # PSP Special Editions
        # ---------------------------------------------------------------
        ("Sony", "PSP 3000 Monster Hunter 3rd Edition", "PSP-3000", "Monster Hunter 3rd Hunter Pack (Japan)", "Japan Exclusive", "high", 100, 210),
        ("Sony", "PSP 3000 Kingdom Hearts BBS Edition", "PSP-3000", "Kingdom Hearts BBS Blue (Japan)", "Japan Exclusive", "high", 120, 240),
        ("Sony", "PSP 3000 Dissidia Final Fantasy FF20th", "PSP-3000", "Dissidia FF Silver (Japan)", "Japan Exclusive", "high", 110, 220),
        ("Sony", "PSP 3000 Gundam vs Gundam Edition", "PSP-3000", "Gundam White/Blue (Japan)", "Japan Exclusive", "high", 100, 200),
        ("Sony", "PSP 3000 Carnival Colors Red/Black", "PSP-3000", "Carnival Colors Red/Black (NA)", "Limited Color", "mid", 60, 120),
        ("Sony", "PSP 3000 Carnival Colors Blue/White", "PSP-3000", "Carnival Colors Blue/White (NA)", "Limited Color", "mid", 60, 120),
        ("Sony", "PSP Go Piano Black (CIB)", "PSP Go", "Piano Black CIB (NA)", "Standard", "high", 120, 240),
        ("Sony", "PSP Go Pearl White (CIB)", "PSP Go", "Pearl White CIB (NA)", "Standard", "high", 130, 260),

        # ---------------------------------------------------------------
        # 3DS Special Editions
        # ---------------------------------------------------------------
        ("Nintendo", "New 3DS XL Samus Edition", "New 3DS XL", "Samus Returns Gold (NA)", "Special Edition", "grail", 200, 380),
        ("Nintendo", "New 3DS XL Galaxy Style", "New 3DS XL", "Galaxy Purple (NA)", "Limited Color", "high", 150, 300),
        ("Nintendo", "New 3DS XL SNES Edition", "New 3DS XL", "SNES Controller Design (NA)", "Special Edition", "grail", 180, 350),
        ("Nintendo", "New 3DS Kyogre Edition", "New 3DS", "Kyogre Blue (Japan)", "Japan Exclusive", "high", 130, 260),
        ("Nintendo", "New 3DS Groudon Edition", "New 3DS", "Groudon Red (Japan)", "Japan Exclusive", "high", 130, 260),
        ("Nintendo", "2DS XL Hylian Shield Edition", "2DS XL", "Hylian Shield Gold/Blue (NA)", "Special Edition", "high", 150, 300),
        ("Nintendo", "2DS XL Pikachu Edition", "2DS XL", "Pikachu Yellow (NA)", "Special Edition", "high", 120, 240),

        # ---------------------------------------------------------------
        # N-Gage & Tiger
        # ---------------------------------------------------------------
        ("Nokia", "N-Gage QD (CIB)", "N-Gage QD", "Silver CIB (NA)", "Standard", "mid", 45, 90),
        ("Nokia", "N-Gage (Classic, CIB)", "N-Gage", "Silver Original CIB (NA)", "Standard", "high", 60, 130),
        ("Nokia", "N-Gage Tony Hawks Pro Skater CIB", "N-Gage", "CIB Game (NA)", "Standard", "mid", 20, 40),
        ("Nokia", "N-Gage Tomb Raider CIB", "N-Gage", "CIB Game (NA)", "Standard", "mid", 25, 50),
        ("Tiger", "Tiger Game.com (CIB)", "Tiger Game.com", "Black CIB (NA)", "Standard", "high", 70, 150),
        ("Tiger", "Tiger Game.com Resident Evil 2", "Tiger Game.com", "CIB Game (NA)", "Standard", "high", 40, 80),

        # ---------------------------------------------------------------
        # Game Boy Light (Japan Only)
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Light Gold", "Game Boy Light", "Gold (Japan)", "Japan Exclusive", "grail", 180, 350),
        ("Nintendo", "Game Boy Light Silver", "Game Boy Light", "Silver (Japan)", "Japan Exclusive", "grail", 160, 320),
        ("Nintendo", "Game Boy Light Astro Boy Clear", "Game Boy Light", "Astro Boy Clear (Japan LE)", "Japan Exclusive", "grail", 300, 550),
        ("Nintendo", "Game Boy Light Famitsu 500 Special", "Game Boy Light", "Famitsu Skeleton (Japan LE)", "Japan Exclusive", "grail", 350, 650),
        ("Nintendo", "Game Boy Light Toys R Us Clear Yellow", "Game Boy Light", "Toys R Us Clear Yellow (Japan)", "Japan Exclusive", "grail", 250, 480),

        # ---------------------------------------------------------------
        # Vita Special Editions
        # ---------------------------------------------------------------
        ("Sony", "PS Vita Slim Persona 4 Dancing All Night", "PS Vita Slim", "P4DAN LE (Japan)", "Japan Exclusive", "high", 130, 260),
        ("Sony", "PS Vita Slim God Eater 2 Rage Burst", "PS Vita Slim", "God Eater Fenrir (Japan)", "Japan Exclusive", "high", 120, 240),
        ("Sony", "PS Vita Slim Final Fantasy X/X-2 Edition", "PS Vita Slim", "FFX Resolution Box (Japan)", "Japan Exclusive", "high", 140, 280),
        ("Sony", "PS Vita Slim Minecraft Special Edition", "PS Vita Slim", "Minecraft Creeper Green (Japan)", "Japan Exclusive", "high", 110, 220),
        ("Sony", "PS Vita OLED Assassin's Creed III Liberation", "PS Vita", "AC Liberation Bundle White (NA)", "Console Bundle", "high", 100, 200),

        # ---------------------------------------------------------------
        # More Rare GBC/GBA Cartridges
        # ---------------------------------------------------------------
        ("Nintendo", "Wendy: Every Witch Way (GBC) CIB", "Game Boy Color", "CIB NA Release", "Standard", "high", 80, 160),
        ("Nintendo", "Survival Kids (GBC) CIB", "Game Boy Color", "CIB NA Release", "Standard", "high", 70, 140),
        ("Nintendo", "Harvest Moon GBC 3 (GBC) CIB", "Game Boy Color", "CIB NA Release", "Standard", "mid", 45, 90),
        ("Nintendo", "Mega Man Xtreme 2 (GBC) CIB", "Game Boy Color", "CIB NA Release", "Standard", "high", 65, 130),
        ("Nintendo", "Boktai: The Sun Is in Your Hand (GBA) CIB", "Game Boy Advance", "CIB NA Release w/ Solar Sensor", "Standard", "high", 80, 160),
        ("Nintendo", "Boktai 2: Solar Boy Django (GBA) CIB", "Game Boy Advance", "CIB NA Release w/ Solar Sensor", "Standard", "high", 90, 180),
        ("Nintendo", "Astro Boy: Omega Factor (GBA) CIB", "Game Boy Advance", "CIB NA Release", "Standard", "high", 60, 120),
        ("Nintendo", "Gunstar Super Heroes (GBA) CIB", "Game Boy Advance", "CIB NA Release", "Standard", "high", 55, 110),
        ("Nintendo", "Summon Night: Swordcraft Story (GBA) CIB", "Game Boy Advance", "CIB NA Release", "Standard", "mid", 40, 80),
        ("Nintendo", "Summon Night: Swordcraft Story 2 (GBA) CIB", "Game Boy Advance", "CIB NA Release", "Standard", "high", 60, 120),

        # ---------------------------------------------------------------
        # Playdate (Panic)
        # ---------------------------------------------------------------
        ("Panic", "Playdate Console (CIB)", "Playdate", "Yellow CIB (Standard)", "Standard", "high", 175, 220),
        ("Panic", "Playdate Stereo Dock", "Playdate", "Official Stereo Dock", "Standard", "mid", 60, 80),
        ("Panic", "Playdate Cover (Purple)", "Playdate", "Official Cover Purple", "Standard", "standard", 25, 35),
        ("Panic", "Playdate Season 1 Games (24 titles)", "Playdate", "Pre-Loaded Season 1 Bundle", "Standard", "mid", 50, 70),

        # ---------------------------------------------------------------
        # More Game Gear Rare Games
        # ---------------------------------------------------------------
        ("Sega", "Panzer Dragoon Mini (Game Gear) CIB", "Game Gear", "CIB Japan", "Japan Exclusive", "grail", 80, 180),
        ("Sega", "GG Aleste (Game Gear) CIB", "Game Gear", "CIB Japan", "Japan Exclusive", "high", 60, 130),
        ("Sega", "Vampire: Master of Darkness (GG) CIB", "Game Gear", "CIB NA Release", "Standard", "high", 50, 110),
        ("Sega", "Tail Gator (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "mid", 30, 65),
        ("Sega", "Mega Man (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "high", 55, 120),
        ("Sega", "Baku Baku Animal (Game Gear) CIB", "Game Gear", "CIB NA Release", "Standard", "mid", 25, 55),
        ("Sega", "Royal Stone (Game Gear) CIB", "Game Gear", "CIB Japan", "Japan Exclusive", "high", 65, 140),
        ("Sega", "Sylvan Tale (Game Gear) CIB", "Game Gear", "CIB Japan", "Japan Exclusive", "high", 70, 150),
        ("Sega", "Ax Battler Golden Axe (GG) CIB", "Game Gear", "CIB NA Release", "Standard", "mid", 25, 55),
        ("Sega", "Halley Wars (Game Gear) CIB", "Game Gear", "CIB Japan", "Japan Exclusive", "mid", 35, 75),
    ]
    catalog = []
    for brand, name, platform, variant_note, condition, rarity_tier, price_loose, price_cib in items:
        if "Japan" in variant_note or condition == "Japan Exclusive":
            region = "JPN"
        elif "NA" in variant_note:
            region = "NA"
        else:
            region = "EU"
        is_limited = condition in ("Limited Color", "Special Edition", "Japan Exclusive", "Anniversary")
        year = _platform_year(platform, name)
        catalog.append({
            "brand": brand,
            "name": name,
            "platform": platform,
            "variant_note": variant_note,
            "condition": condition,
            "rarity_tier": rarity_tier,
            "price_loose_eur": price_loose,
            "price_cib_eur": price_cib,
            "region": region,
            "is_limited_edition": is_limited,
            "year": year,
        })
    return catalog


def _round9_handheld_expansion() -> list[dict]:
    """~200 items: Game Boy Color Pokemon eds, GBA SP NES/Famicom, DS Lite LE,
    3DS XL LE, PSP LE, PS Vita LE, Switch OLED LE, Anbernic/Miyoo/Retroid 2024-2025."""
    raw = [
        # ── Game Boy Color — Pokemon & LE ────────────────────────────────
        ("Nintendo", "Game Boy Color Pokemon Pikachu Yellow JP", "Game Boy Color", "Pokemon Pikachu Yellow CGB-001 (Japan)", "Japan Exclusive", "grail", 150, 350),
        ("Nintendo", "Game Boy Color Pokemon 3rd Anniversary JP", "Game Boy Color", "Pokemon 3rd Anniversary Orange (Japan)", "Japan Exclusive", "grail", 300, 650),
        ("Nintendo", "Game Boy Color Cardcaptor Sakura Pink JP", "Game Boy Color", "Cardcaptor Sakura Pink (Japan)", "Japan Exclusive", "grail", 200, 420),
        ("Nintendo", "Game Boy Color Sakura Taisen White JP", "Game Boy Color", "Sakura Taisen White (Japan)", "Japan Exclusive", "grail", 180, 380),
        ("Nintendo", "Game Boy Color Tommy Hilfiger", "Game Boy Color", "Tommy Hilfiger Yellow (USA)", "Special Edition", "grail", 250, 500),
        ("Nintendo", "Game Boy Color Ozzy Osbourne Purple", "Game Boy Color", "Ozzy Osbourne Purple Promo (USA)", "Special Edition", "grail", 500, 1000),
        ("Nintendo", "Game Boy Color Toys R Us Gold", "Game Boy Color", "Toys R Us Gold Limited (USA)", "Special Edition", "grail", 200, 420),
        ("Nintendo", "Game Boy Color Manchester United Red", "Game Boy Color", "Manchester United Red (UK)", "Special Edition", "high", 120, 260),
        ("Nintendo", "Game Boy Color Hello Kitty Pink JP", "Game Boy Color", "Hello Kitty Pink (Japan)", "Japan Exclusive", "high", 140, 300),
        ("Nintendo", "Game Boy Color Daiei Hawks Orange JP", "Game Boy Color", "Daiei Hawks Orange (Japan)", "Japan Exclusive", "high", 130, 280),

        # ── GBA SP — NES/Famicom & Special ───────────────────────────────
        ("Nintendo", "GBA SP AGS-101 Graphite", "Game Boy Advance SP", "Graphite AGS-101 Backlit (NA)", "Standard", "high", 110, 230),
        ("Nintendo", "GBA SP Surf Blue AGS-101", "Game Boy Advance SP", "Surf Blue AGS-101 Backlit", "Standard", "high", 100, 220),
        ("Nintendo", "GBA SP Pearl Green AGS-101", "Game Boy Advance SP", "Pearl Green AGS-101 Backlit", "Limited Color", "high", 120, 250),
        ("Nintendo", "GBA SP Final Fantasy Tactics JP", "Game Boy Advance SP", "Final Fantasy Tactics Advance (Japan)", "Japan Exclusive", "grail", 280, 560),
        ("Nintendo", "GBA SP Naruto Orange JP", "Game Boy Advance SP", "Naruto Orange (Japan)", "Japan Exclusive", "high", 180, 370),
        ("Nintendo", "GBA SP Dragon Ball Z Gold JP", "Game Boy Advance SP", "Dragon Ball Z Gold (Japan)", "Japan Exclusive", "high", 190, 400),

        # ── Nintendo DS Lite — Limited Editions ──────────────────────────
        ("Nintendo", "DS Lite Zelda Phantom Hourglass Gold", "Nintendo DS Lite", "Zelda Phantom Hourglass Gold (NA)", "Special Edition", "grail", 220, 450),
        ("Nintendo", "DS Lite Pokemon Diamond Pearl Palkia/Dialga", "Nintendo DS Lite", "Pokemon Diamond Pearl Palkia/Dialga (JP)", "Japan Exclusive", "high", 120, 260),
        ("Nintendo", "DS Lite Crimson/Black", "Nintendo DS Lite", "Crimson/Black Mario Kart Bundle", "Special Edition", "high", 80, 170),
        ("Nintendo", "DS Lite Final Fantasy III Crystal", "Nintendo DS Lite", "Final Fantasy III Crystal Edition (JP)", "Japan Exclusive", "grail", 200, 420),
        ("Nintendo", "DS Lite Giratina Edition JP", "Nintendo DS Lite", "Pokemon Platinum Giratina (JP)", "Japan Exclusive", "high", 130, 280),
        ("Nintendo", "DS Lite Love Plus+ Nene Deluxe", "Nintendo DS Lite", "Love Plus+ Nene Pink (JP)", "Japan Exclusive", "high", 150, 320),
        ("Nintendo", "DS Lite Dragon Quest IX Metallic Blue JP", "Nintendo DS Lite", "Dragon Quest IX Metallic Blue (JP)", "Japan Exclusive", "high", 140, 290),

        # ── Nintendo 3DS / 3DS XL — Limited Editions ─────────────────────
        ("Nintendo", "3DS XL Zelda A Link Between Worlds Gold", "Nintendo 3DS XL", "Zelda ALBW Gold (NA)", "Special Edition", "grail", 250, 500),
        ("Nintendo", "3DS XL Monster Hunter 4 Ultimate Silver", "Nintendo 3DS XL", "Monster Hunter 4 Ultimate Silver (NA)", "Special Edition", "high", 180, 370),
        ("Nintendo", "3DS XL Pikachu Yellow", "Nintendo 3DS XL", "Pikachu Yellow (NA)", "Special Edition", "high", 160, 340),
        ("Nintendo", "3DS XL Fire Emblem Fates Blue", "Nintendo 3DS XL", "Fire Emblem Fates Blue (NA)", "Special Edition", "high", 170, 360),
        ("Nintendo", "New 3DS XL Majora's Mask Gold", "New Nintendo 3DS XL", "Majora's Mask Gold Edition (NA)", "Special Edition", "grail", 300, 600),
        ("Nintendo", "New 3DS XL SNES Edition", "New Nintendo 3DS XL", "SNES Super Famicom Edition (NA)", "Special Edition", "grail", 280, 550),
        ("Nintendo", "New 3DS XL Hyrule Gold Edition", "New Nintendo 3DS XL", "Hyrule Gold Edition (NA)", "Special Edition", "grail", 260, 520),
        ("Nintendo", "New 3DS XL Solgaleo Lunala Black", "New Nintendo 3DS XL", "Pokemon Sun Moon Solgaleo Lunala (NA)", "Special Edition", "high", 180, 380),
        ("Nintendo", "New 3DS XL Monster Hunter XX JP", "New Nintendo 3DS XL", "Monster Hunter XX Hunter Edition (JP)", "Japan Exclusive", "high", 170, 350),
        ("Nintendo", "New 3DS XL Dragon Quest VIII JP", "New Nintendo 3DS XL", "Dragon Quest VIII Metallic Blue (JP)", "Japan Exclusive", "high", 190, 400),
        ("Nintendo", "3DS Cobalt Blue", "Nintendo 3DS", "Cobalt Blue (NA Launch)", "Standard", "mid", 60, 140),
        ("Nintendo", "3DS Flame Red", "Nintendo 3DS", "Flame Red (NA)", "Standard", "mid", 55, 130),
        ("Nintendo", "3DS Pure White JP", "Nintendo 3DS", "Pure White (JP)", "Japan Exclusive", "mid", 70, 160),
        ("Nintendo", "New 3DS Cover Plates Kyary Pamyu JP", "New Nintendo 3DS", "Kyary Pamyu Pamyu Cover Plates (JP)", "Japan Exclusive", "high", 120, 250),
        ("Nintendo", "New 2DS XL Pikachu Edition", "New Nintendo 2DS XL", "Pikachu Yellow Edition (NA)", "Special Edition", "high", 140, 300),
        ("Nintendo", "New 2DS XL Pokeball Edition", "New Nintendo 2DS XL", "Pokeball Red/White (NA)", "Special Edition", "high", 130, 280),
        ("Nintendo", "New 2DS XL Hylian Shield Edition", "New Nintendo 2DS XL", "Hylian Shield Edition (NA)", "Special Edition", "high", 150, 320),
        ("Nintendo", "New 2DS XL Mario Kart 7 White/Orange", "New Nintendo 2DS XL", "Mario Kart 7 White/Orange (NA)", "Special Edition", "high", 100, 220),

        # ── Sony PSP — Limited Editions ──────────────────────────────────
        ("Sony", "PSP-3000 God of War Red/Black", "PSP-3000", "God of War Ghost of Sparta Red/Black (NA)", "Special Edition", "high", 120, 260),
        ("Sony", "PSP-3000 Crisis Core Silver", "PSP-3000", "Crisis Core FF VII Silver (NA)", "Special Edition", "high", 130, 280),
        ("Sony", "PSP-2000 Star Wars White", "PSP-2000", "Star Wars Battlefront White (NA)", "Special Edition", "high", 110, 240),
        ("Sony", "PSP-3000 Monster Hunter 3rd JP", "PSP-3000", "Monster Hunter Portable 3rd Hunter (JP)", "Japan Exclusive", "high", 140, 300),
        ("Sony", "PSP-3000 Kingdom Hearts BbS Silver", "PSP-3000", "Kingdom Hearts Birth by Sleep Silver (NA)", "Special Edition", "high", 130, 280),
        ("Sony", "PSP-2000 Felicia Blue JP", "PSP-2000", "Felicia Blue (JP)", "Japan Exclusive", "high", 100, 220),
        ("Sony", "PSP-1000 Metal Gear Solid Peace Walker JP", "PSP-1000", "MGS Peace Walker Camo (JP)", "Japan Exclusive", "high", 150, 320),
        ("Sony", "PSP-3000 Dissidia Final Fantasy Silver", "PSP-3000", "Dissidia FF 20th Anniversary Silver (JP)", "Japan Exclusive", "high", 120, 260),
        ("Sony", "PSP Go Pearl White", "PSP Go", "Pearl White N-1000", "Standard", "high", 130, 270),
        ("Sony", "PSP Go Piano Black", "PSP Go", "Piano Black N-1000", "Standard", "high", 110, 240),

        # ── Sony PS Vita — Limited Editions ──────────────────────────────
        ("Sony", "PS Vita Hatsune Miku Crystal White LE", "PS Vita 1000", "Hatsune Miku Limited Edition Crystal White (JP)", "Japan Exclusive", "grail", 350, 700),
        ("Sony", "PS Vita Hatsune Miku Project Diva f Ice Silver", "PS Vita 1000", "Project Diva f Ice Silver (JP)", "Japan Exclusive", "grail", 300, 600),
        ("Sony", "PS Vita Slim God Eater 2 Red/Black JP", "PS Vita 2000", "God Eater 2 Fenrir Red/Black (JP)", "Japan Exclusive", "high", 180, 380),
        ("Sony", "PS Vita Slim Persona 4 DAN White JP", "PS Vita 2000", "Persona 4 Dancing All Night White (JP)", "Japan Exclusive", "high", 200, 420),
        ("Sony", "PS Vita Slim Gundam Breaker White/Blue JP", "PS Vita 2000", "Gundam Breaker Starter White/Blue (JP)", "Japan Exclusive", "high", 160, 340),
        ("Sony", "PS Vita Soul Sacrifice Red/Black JP", "PS Vita 1000", "Soul Sacrifice Red/Black (JP)", "Japan Exclusive", "high", 170, 360),
        ("Sony", "PS Vita Slim Final Fantasy X/X-2 Blue JP", "PS Vita 2000", "Final Fantasy X/X-2 HD Resolution Blue (JP)", "Japan Exclusive", "high", 190, 400),
        ("Sony", "PS Vita Slim Minecraft White/Lime Green JP", "PS Vita 2000", "Minecraft Special Edition White/Lime (JP)", "Japan Exclusive", "high", 140, 300),
        ("Sony", "PS Vita Slim Caligula White/Blue JP", "PS Vita 2000", "The Caligula Effect White/Blue (JP)", "Japan Exclusive", "high", 150, 320),
        ("Sony", "PS Vita OLED 3G Crystal Black Launch", "PS Vita 1000", "3G Crystal Black Launch Edition (NA)", "Special Edition", "high", 120, 260),

        # ── Nintendo Switch — Limited OLED & Standard ────────────────────
        ("Nintendo", "Switch OLED Zelda TotK Edition", "Nintendo Switch OLED", "Zelda Tears of the Kingdom Green/Gold", "Special Edition", "high", 180, 380),
        ("Nintendo", "Switch OLED Splatoon 3 Edition", "Nintendo Switch OLED", "Splatoon 3 Gradient Purple/Green/Yellow", "Special Edition", "high", 150, 320),
        ("Nintendo", "Switch OLED Pokemon Scarlet Violet Edition", "Nintendo Switch OLED", "Pokemon SV Red/Purple Koraidon/Miraidon", "Special Edition", "high", 160, 340),
        ("Nintendo", "Switch OLED Super Smash Bros Ultimate Edition", "Nintendo Switch OLED", "Super Smash Bros Ultimate Gray (JP)", "Japan Exclusive", "high", 170, 360),
        ("Nintendo", "Switch Animal Crossing New Horizons", "Nintendo Switch", "Animal Crossing NH Pastel Blue/Green", "Special Edition", "high", 160, 340),
        ("Nintendo", "Switch Let's Go Pikachu/Eevee", "Nintendo Switch", "Let's Go Pikachu/Eevee Yellow/Brown", "Special Edition", "high", 180, 380),
        ("Nintendo", "Switch Monster Hunter Rise Deluxe", "Nintendo Switch", "Monster Hunter Rise Grey/Magnamalo", "Special Edition", "high", 140, 300),
        ("Nintendo", "Switch Fortnite Wildcat Yellow/Blue", "Nintendo Switch", "Fortnite Wildcat Bundle Yellow/Blue", "Special Edition", "high", 130, 280),
        ("Nintendo", "Switch Diablo III Eternal Collection", "Nintendo Switch", "Diablo III Black/Red", "Special Edition", "high", 150, 320),
        ("Nintendo", "Switch Dragon Quest XI S Loto Edition JP", "Nintendo Switch", "Dragon Quest XI S Loto Edition (JP)", "Japan Exclusive", "grail", 350, 700),
        ("Nintendo", "Switch Lite Zacian/Zamazenta", "Nintendo Switch Lite", "Pokemon Sword/Shield Cyan/Magenta", "Special Edition", "high", 120, 260),
        ("Nintendo", "Switch Lite Dialga/Palkia", "Nintendo Switch Lite", "Pokemon BDSP Dialga/Palkia Grey", "Special Edition", "high", 130, 280),
        ("Nintendo", "Switch Lite Hyrule Edition Gold", "Nintendo Switch Lite", "Hyrule Gold Edition", "Special Edition", "high", 140, 300),
        ("Nintendo", "Switch Lite Isabelle Aloha Edition", "Nintendo Switch Lite", "Animal Crossing Isabelle Aloha", "Special Edition", "high", 120, 260),

        # ── Modern Retro Handhelds — Anbernic 2024-2025 ─────────────────
        ("Anbernic", "Anbernic RG556", "RG556", "Black 5.48in AMOLED", "Modded/Custom", "mid", 80, 100),
        ("Anbernic", "Anbernic RG556 Transparent Purple", "RG556", "Transparent Purple AMOLED", "Modded/Custom", "mid", 85, 105),
        ("Anbernic", "Anbernic RG406V", "RG406V", "Black Vertical", "Modded/Custom", "mid", 55, 70),
        ("Anbernic", "Anbernic RG406H", "RG406H", "Transparent Blue Horizontal", "Modded/Custom", "mid", 55, 70),
        ("Anbernic", "Anbernic RG405V", "RG405V", "Transparent Purple Vertical", "Modded/Custom", "mid", 60, 75),
        ("Anbernic", "Anbernic RG405M", "RG405M", "Metal Shell Silver CNC", "Modded/Custom", "mid", 70, 90),
        ("Anbernic", "Anbernic RG35XX Plus", "RG35XX Plus", "Transparent White", "Modded/Custom", "mid", 40, 55),
        ("Anbernic", "Anbernic RG35XX H", "RG35XX H", "Transparent Orange Horizontal", "Modded/Custom", "mid", 42, 58),
        ("Anbernic", "Anbernic RG35XX SP", "RG35XX SP", "Transparent Blue Clamshell", "Modded/Custom", "mid", 50, 65),
        ("Anbernic", "Anbernic RG28XX", "RG28XX", "Transparent Purple Nano", "Modded/Custom", "standard", 25, 35),
        ("Anbernic", "Anbernic RG CubeXX", "RG CubeXX", "Black Cube Docking", "Modded/Custom", "mid", 70, 90),
        ("Anbernic", "Anbernic RG556 Gray", "RG556", "Space Gray AMOLED", "Modded/Custom", "mid", 80, 100),
        ("Anbernic", "Anbernic RG353M", "RG353M", "Metal Shell Anodized", "Modded/Custom", "mid", 65, 85),

        # ── Modern Retro Handhelds — Miyoo 2024-2025 ────────────────────
        ("Miyoo", "Miyoo Mini Plus", "Miyoo Mini Plus", "Transparent Black", "Modded/Custom", "mid", 45, 60),
        ("Miyoo", "Miyoo Mini Plus Retro Grey", "Miyoo Mini Plus", "Retro DMG Grey", "Modded/Custom", "mid", 48, 63),
        ("Miyoo", "Miyoo Mini V4", "Miyoo Mini V4", "White V4", "Modded/Custom", "mid", 35, 50),
        ("Miyoo", "Miyoo A30", "Miyoo A30", "Transparent Blue 2.8in", "Modded/Custom", "mid", 30, 42),
        ("Miyoo", "Miyoo Flip", "Miyoo Flip", "Black Clamshell", "Modded/Custom", "mid", 55, 70),

        # ── Modern Retro Handhelds — Retroid 2024-2025 ──────────────────
        ("Retroid", "Retroid Pocket 4 Pro", "Retroid Pocket 4 Pro", "Black 4GB/128GB", "Modded/Custom", "mid", 100, 125),
        ("Retroid", "Retroid Pocket 4 Pro Retro", "Retroid Pocket 4 Pro", "Retro SNES Color", "Modded/Custom", "mid", 105, 130),
        ("Retroid", "Retroid Pocket Mini", "Retroid Pocket Mini", "Gray Mini Clamshell", "Modded/Custom", "mid", 70, 90),
        ("Retroid", "Retroid Pocket 3 Plus", "Retroid Pocket 3+", "Black 3.5in Touchscreen", "Modded/Custom", "mid", 80, 100),
        ("Retroid", "Retroid Pocket Flip", "Retroid Pocket Flip", "Black Clamshell", "Modded/Custom", "mid", 90, 115),

        # ── Modern Retro Handhelds — Trimui / Others 2024-2025 ──────────
        ("Trimui", "Trimui Smart Pro", "Trimui Smart Pro", "Gray PSP-Style", "Modded/Custom", "mid", 45, 60),
        ("Trimui", "Trimui Brick", "Trimui Brick", "Transparent Green NES-Style", "Modded/Custom", "standard", 22, 30),
        ("Trimui", "Trimui Model S", "Trimui Model S", "White Ultra-Thin", "Modded/Custom", "standard", 20, 28),
        ("AYN", "AYN Odin 2 Portal", "Odin 2 Portal", "Transparent Black 7in", "Modded/Custom", "high", 180, 220),
        ("AYN", "AYN Odin 2 Mini", "Odin 2 Mini", "White Mini", "Modded/Custom", "high", 150, 185),
        ("AYN", "AYN Odin 2", "Odin 2", "Black Pro 6in", "Modded/Custom", "high", 200, 250),
        ("Powkiddy", "Powkiddy V10", "Powkiddy V10", "Black Vertical", "Modded/Custom", "standard", 25, 35),
        ("Powkiddy", "Powkiddy RGB30", "Powkiddy RGB30", "Transparent Purple 4in", "Modded/Custom", "mid", 40, 55),
        ("Powkiddy", "Powkiddy X55", "Powkiddy X55", "Black 5.5in", "Modded/Custom", "mid", 50, 65),
        ("Ayaneo", "AYANEO Pocket S", "AYANEO Pocket S", "Black Android Handheld", "Modded/Custom", "high", 200, 250),
        ("Ayaneo", "AYANEO Pocket EVO", "AYANEO Pocket EVO", "White Android Premium", "Modded/Custom", "high", 250, 310),

        # ── Game Boy Micro — All Colors ──────────────────────────────────
        ("Nintendo", "Game Boy Micro Blue", "Game Boy Micro", "Blue (NA)", "Standard", "high", 160, 320),
        ("Nintendo", "Game Boy Micro Green", "Game Boy Micro", "Green (NA)", "Standard", "high", 170, 340),
        ("Nintendo", "Game Boy Micro Pink", "Game Boy Micro", "Pink (JP)", "Japan Exclusive", "high", 180, 360),
        ("Nintendo", "Game Boy Micro Famicom Anniversary", "Game Boy Micro", "Famicom 20th Anniversary (JP)", "Japan Exclusive", "grail", 350, 700),
        ("Nintendo", "Game Boy Micro Mother 3 Deluxe", "Game Boy Micro", "Mother 3 Red/Blue (JP)", "Japan Exclusive", "grail", 500, 1000),
        ("Nintendo", "Game Boy Micro Final Fantasy IV JP", "Game Boy Micro", "Final Fantasy IV Advance (JP)", "Japan Exclusive", "grail", 400, 800),

        # ── Rare Tamagotchi Editions ─────────────────────────────────────
        ("Bandai", "Tamagotchi P1 Transparent Red 1997", "Tamagotchi P1", "Transparent Red Original (1997)", "Standard", "high", 60, 150),
        ("Bandai", "Tamagotchi P1 White 1996 JP", "Tamagotchi P1", "White Japanese Original (1996)", "Japan Exclusive", "high", 80, 200),
        ("Bandai", "Tamagotchi Angel (Angelgotchi)", "Tamagotchi Angel", "Silver Angel Edition", "Standard", "high", 60, 140),
        ("Bandai", "Tamagotchi Devilgotchi JP", "Tamagotchi Devil", "Devil Edition (JP Only)", "Japan Exclusive", "grail", 200, 500),
        ("Bandai", "Tamagotchi Ocean (Umino)", "Tamagotchi Ocean", "Blue Ocean Tamagotchi", "Standard", "high", 100, 250),
        ("Bandai", "Tamagotchi Yasashii Blue JP", "Tamagotchi Yasashii", "Yasashii Blue (JP Only)", "Japan Exclusive", "grail", 250, 600),
        ("Bandai", "Tamagotchi iD L 15th Anniversary", "Tamagotchi iD L", "15th Anniversary LE (JP)", "Japan Exclusive", "high", 130, 280),
        ("Bandai", "Tamagotchi Uni Purple", "Tamagotchi Uni", "Tamagotchi Uni Purple 2023", "Standard", "mid", 50, 65),
        ("Bandai", "Tamagotchi Pix Party Confetti", "Tamagotchi Pix Party", "Confetti Camera 2022", "Standard", "mid", 40, 55),

        # ── Game & Watch — Collectible Reissues ──────────────────────────
        ("Nintendo", "Game & Watch Super Mario Bros 2020", "Game & Watch", "Super Mario Bros 35th Anniversary (2020)", "Anniversary", "high", 80, 150),
        ("Nintendo", "Game & Watch Zelda 2021", "Game & Watch", "Legend of Zelda 35th Anniversary (2021)", "Anniversary", "high", 80, 150),
        ("Nintendo", "Game & Watch Mario Bros 1983 Original", "Game & Watch", "Original Multi Screen Mario Bros MW-56 (1983)", "Standard", "grail", 200, 500),
        ("Nintendo", "Game & Watch Donkey Kong 1982 Original", "Game & Watch", "Original Multi Screen Donkey Kong DK-52 (1982)", "Standard", "grail", 180, 450),
        ("Nintendo", "Game & Watch Octopus 1981 Original", "Game & Watch", "Original Wide Screen Octopus OC-22 (1981)", "Standard", "high", 120, 300),
        ("Nintendo", "Game & Watch Fire 1980 Original", "Game & Watch", "Original Silver Series Fire RC-04 (1980)", "Standard", "grail", 250, 600),
        ("Nintendo", "Game & Watch Oil Panic 1982 Original", "Game & Watch", "Original Multi Screen Oil Panic OP-51 (1982)", "Standard", "high", 150, 380),
        ("Nintendo", "Game & Watch Ball 1980 Original", "Game & Watch", "Original Silver Series Ball AC-01 (1980)", "Standard", "grail", 350, 800),

        # ── DSi / DSi XL — Limited Editions ──────────────────────────────
        ("Nintendo", "DSi Mario 25th Anniversary Red", "Nintendo DSi", "Mario 25th Anniversary Red (JP)", "Japan Exclusive", "high", 100, 220),
        ("Nintendo", "DSi White", "Nintendo DSi", "Matte White (NA)", "Standard", "mid", 40, 100),
        ("Nintendo", "DSi XL Mario 25th Anniversary Red", "Nintendo DSi XL", "Mario 25th Anniversary Red (JP)", "Japan Exclusive", "high", 120, 260),
        ("Nintendo", "DSi XL Burgundy", "Nintendo DSi XL", "Burgundy Wine Red (NA)", "Standard", "mid", 50, 120),
        ("Nintendo", "DSi XL Zelda 25th Anniversary Gold JP", "Nintendo DSi XL", "Zelda 25th Anniversary Gold (JP)", "Japan Exclusive", "grail", 250, 500),

        # ── Analogue Premium Handhelds ───────────────────────────────────
        ("Analogue", "Analogue Pocket White", "Analogue Pocket", "White Launch Edition", "Standard", "high", 200, 250),
        ("Analogue", "Analogue Pocket Black", "Analogue Pocket", "Black Edition", "Standard", "high", 200, 250),
        ("Analogue", "Analogue Pocket Classic Limited", "Analogue Pocket", "Classic Limited GLOW Edition", "Special Edition", "grail", 350, 450),
        ("Analogue", "Analogue Pocket Transparent", "Analogue Pocket", "Transparent Clear Edition", "Special Edition", "grail", 300, 400),
        ("Analogue", "Analogue Pocket Dock", "Analogue Pocket", "Dock Accessory HDMI Output", "Standard", "high", 80, 100),

        # ── PC Engine / TurboExpress ─────────────────────────────────────
        ("NEC", "PC Engine GT / TurboExpress", "TurboExpress", "TurboExpress PI-TG6 Handheld", "Standard", "grail", 250, 500),
        ("NEC", "PC Engine GT AC Adapter", "TurboExpress", "Official AC Adapter PAD-124", "Standard", "high", 60, 120),
        ("NEC", "PC Engine GT TV Tuner", "TurboExpress", "TV Tuner Accessory PI-AD12", "Standard", "high", 80, 160),
        ("NEC", "PC Engine LT", "PC Engine LT", "PC Engine LT Portable (JP)", "Japan Exclusive", "grail", 400, 800),

        # ── Sega Game Gear — Colors & Bundles ────────────────────────────
        ("Sega", "Game Gear Blue Sports Edition", "Sega Game Gear", "Blue Sports Edition (NA)", "Special Edition", "high", 80, 170),
        ("Sega", "Game Gear Yellow", "Sega Game Gear", "Yellow (JP)", "Japan Exclusive", "high", 100, 220),
        ("Sega", "Game Gear White", "Sega Game Gear", "White (JP)", "Japan Exclusive", "high", 90, 200),
        ("Sega", "Game Gear Red", "Sega Game Gear", "Red Coca-Cola Edition (JP)", "Japan Exclusive", "grail", 200, 420),
        ("Sega", "Game Gear Micro Black", "Sega Game Gear Micro", "Game Gear Micro Black (JP 2020)", "Japan Exclusive", "high", 60, 130),
        ("Sega", "Game Gear Micro Blue", "Sega Game Gear Micro", "Game Gear Micro Blue (JP 2020)", "Japan Exclusive", "high", 60, 130),
        ("Sega", "Game Gear Micro Yellow", "Sega Game Gear Micro", "Game Gear Micro Yellow (JP 2020)", "Japan Exclusive", "high", 60, 130),
        ("Sega", "Game Gear Micro Complete Set", "Sega Game Gear Micro", "Complete 4-Color Set + Big Window Micro (JP)", "Japan Exclusive", "grail", 350, 600),

        # ── Steam Deck & PC Handhelds ────────────────────────────────────
        ("Valve", "Steam Deck OLED 1TB Limited Edition", "Steam Deck OLED", "1TB OLED Translucent LE", "Special Edition", "high", 600, 700),
        ("Valve", "Steam Deck LCD 512GB", "Steam Deck", "512GB Anti-Glare LCD", "Standard", "mid", 300, 380),
        ("ASUS", "ROG Ally X", "ROG Ally X", "Black 2024 Refresh", "Standard", "high", 600, 700),
        ("Lenovo", "Legion Go S", "Legion Go S", "2025 Model Stealth Gray", "Standard", "high", 400, 480),
        ("MSI", "MSI Claw A1M", "MSI Claw", "Intel Core Ultra 7in", "Standard", "high", 500, 600),

        # ── Panic Playdate ───────────────────────────────────────────────
        ("Panic", "Playdate Yellow", "Playdate", "Yellow Crank Handheld 2022", "Standard", "high", 170, 200),
        ("Panic", "Playdate Stereo Dock", "Playdate", "Stereo Dock Speaker/Pen Holder", "Standard", "mid", 60, 80),
        ("Panic", "Playdate Cover Orange", "Playdate", "Protective Cover Orange", "Standard", "standard", 25, 30),
    ]

    catalog: list[dict] = []
    for brand, name, platform, variant_note, condition, rarity_tier, price_loose, price_cib in raw:
        if "Japan" in variant_note or "JP" in variant_note or condition == "Japan Exclusive":
            region = "JPN"
        elif "NA" in variant_note:
            region = "NA"
        else:
            region = "EU"
        is_limited = condition in ("Limited Color", "Special Edition", "Japan Exclusive", "Anniversary")
        year = _platform_year(platform, name)
        catalog.append({
            "brand": brand,
            "name": name,
            "platform": platform,
            "variant_note": variant_note,
            "condition": condition,
            "rarity_tier": rarity_tier,
            "price_loose_eur": price_loose,
            "price_cib_eur": price_cib,
            "region": region,
            "is_limited_edition": is_limited,
            "year": year,
        })
    return catalog


def _platform_year(platform: str, name: str) -> int:
    """Estimate release year from platform and name."""
    year_map = {
        "Game Boy": 1989,
        "Game Boy Pocket": 1996,
        "Game Boy Light": 1998,
        "Game Boy Color": 1998,
        "Game Boy Advance": 2001,
        "Game Boy Advance SP": 2003,
        "Game Boy Micro": 2005,
        "Nintendo DS": 2004,
        "Nintendo DS Lite": 2006,
        "Nintendo DSi": 2008,
        "Nintendo DSi XL": 2009,
        "Nintendo 3DS": 2011,
        "Nintendo 3DS XL": 2012,
        "New Nintendo 3DS XL": 2015,
        "PSP-1000": 2004,
        "PSP-2000": 2007,
        "PSP-3000": 2008,
        "PSP Go": 2009,
        "PS Vita 1000": 2011,
        "PS Vita 2000": 2013,
        "Game Gear": 1990,
        "Sega Nomad": 1995,
        "Atari Lynx": 1989,
        "Atari Lynx II": 1991,
        "Neo Geo Pocket Color": 1999,
        "WonderSwan Crystal": 2002,
        "WonderSwan Color": 2000,
        "SwanCrystal": 2002,
        "N-Gage": 2003,
        "N-Gage QD": 2004,
        "TurboExpress": 1990,
        "PC Engine GT": 1990,
        "Game.com": 1997,
        "Game.com Pocket Pro": 1999,
        "Tamagotchi": 1996,
        "Game & Watch": 1980,
        "Game Pocket Computer": 1984,
        "Microvision": 1979,
        "Analogue Pocket": 2021,
        "Miyoo Mini Plus": 2023,
        "RG35XX": 2023,
        "RG353V": 2022,
        "RG35XX Plus": 2023,
        "WonderSwan": 1999,
        "Miyoo Mini": 2022,
        "Retroid Pocket 3+": 2023,
        "Switch Lite": 2019,
        "Game Gear Micro": 2020,
        "New Nintendo 3DS": 2014,
        "New Nintendo 2DS XL": 2017,
        "PS Vita TV": 2013,
        "Supervision": 1992,
        "Gamate": 1990,
        "GP32": 2001,
        "RG556": 2024,
        "RG353M": 2023,
        "Retroid Pocket 4 Pro": 2024,
        "Trimui Smart Pro": 2024,
        "Odin 2": 2023,
        "RGB30": 2023,
        "Tiger LCD": 1991,
        "R-Zone": 1995,
        "Nintendo 2DS": 2013,
        "Game Boy Camera": 1998,
        "Game Boy Printer": 1998,
        "Game Boy Player": 2003,
        "Super Game Boy": 1994,
        "Super Game Boy 2": 1998,
        "e-Reader": 2002,
        "Digimon": 1997,
        "Giga Pets": 1997,
        "Nano Baby": 1997,
        "Neo Geo Pocket": 1998,
        "Switch": 2017,
        "RG35XX H": 2024,
        "RG35XX SP": 2024,
        "RG405M": 2024,
        "RG405V": 2023,
        "RG505": 2023,
        "RG28XX": 2024,
        "RG Cube": 2024,
        "Retroid Pocket 2S": 2022,
        "Retroid Pocket 3": 2023,
        "Retroid Pocket Flip": 2024,
        "Retroid Pocket Mini": 2024,
        "Retroid Pocket 5": 2024,
        "Miyoo A30": 2024,
        "Trimui Smart": 2023,
        "Trimui Brick": 2024,
        "V90": 2020,
        "X55": 2023,
        "RGB10 Max 3": 2023,
        "Odin 2 Mini": 2024,
        "Odin 2 Max": 2024,
        "Select-A-Game": 1981,
        "Adventure Vision": 1982,
        "Auto Race": 1976,
        "Football": 1977,
        "Head-to-Head": 1980,
        "Mini Arcade": 1982,
        "Tutor": 1983,
        "CreatiVision": 1981,
        "Super Micro": 1991,
        "Hyperboy": 1992,
        "Steam Deck": 2022,
        "Steam Deck OLED": 2023,
        "ROG Ally": 2023,
        "Legion Go": 2023,
        "AYANEO 2S": 2023,
        "AYANEO Air 1S": 2023,
        "GPD Win 4": 2023,
        "GPD Win Mini": 2023,
        "Playdate": 2022,
        "RG353VS": 2023,
        "RG353PS": 2023,
        "RG353P": 2022,
        "RG Nano": 2024,
        "Retroid Pocket 4": 2024,
        "Retroid Pocket 2+": 2022,
        "Trimui Smart Pro S": 2024,
        "Nokia N-Gage": 2003,
    }
    # Check for reissue years in name
    if "2020 Reissue" in name or "2020" in name:
        return 2020
    if "2021 Reissue" in name or "2021" in name:
        return 2021
    return year_map.get(platform, 2000)


# Edition score map for price observations
EDITION_SCORES = {
    "Standard": 0.30,
    "Limited Color": 0.55,
    "Special Edition": 0.70,
    "Japan Exclusive": 0.80,
    "Modded/Custom": 0.40,
    "Prototype/Dev": 0.95,
    "Anniversary": 0.75,
    "Console Bundle": 0.50,
}


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    name = item["name"]
    platform = item["platform"]
    variant_note = item["variant_note"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}-{variant_note}"),
        title=f"{name} ({variant_note})",
        set_code=slugify(platform),
        brand=brand,
        rarity=item["rarity_tier"].title(),
        notes=f"{brand} | {platform} | {variant_note} | {item['condition']}",
        attributes_json={
            "platform": platform,
            "variant": variant_note,
            "region": item["region"],
            "is_limited_edition": item["is_limited_edition"],
            "year": item["year"],
        },
    )


def item_to_price_observations(item: dict) -> list[PriceObservation]:
    """Create two observations per item: loose and CIB/boxed."""
    tier = item["rarity_tier"]
    condition = item["condition"]
    observations = []

    # Loose observation
    observations.append(PriceObservation(
        features={
            "condition_score": 0.50,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": EDITION_SCORES.get(condition, 0.30),
            "completeness": 0.50,
        },
        price=float(item["price_loose_eur"]),
    ))

    # CIB / Complete-in-box observation
    observations.append(PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": EDITION_SCORES.get(condition, 0.30),
            "completeness": 0.90,
        },
        price=float(item["price_cib_eur"]),
    ))

    return observations


def main():
    parser = argparse.ArgumentParser(description="Import retro handhelds catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Retro Handhelds Import ===")

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

    logger.info(f"\n=== Retro Handhelds Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
