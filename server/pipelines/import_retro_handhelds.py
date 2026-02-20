"""
Import retro handheld consoles & devices catalog.

Layer 1 (Catalog):  Curated retro handheld devices -> category_items
Layer 2 (Prices):   Estimated market prices (loose + CIB) -> train.jsonl

Covers:
- Nintendo Game Boy family (DMG, Pocket, Light, Color, Advance, SP, Micro)
- Nintendo DS family (DS Phat, Lite, DSi, 3DS, New 3DS XL)
- Sony PSP family (PSP-1000/2000/3000, PSP Go, PS Vita)
- Sega handhelds (Game Gear, Nomad)
- Atari Lynx (I and II)
- Neo Geo Pocket Color
- Bandai WonderSwan family
- Nokia N-Gage
- TurboExpress / PC Engine GT
- Tiger Game.com
- Tamagotchi (P1, P2, Connection, Music Star, iD L)
- Nintendo Game & Watch classics
- Epoch Game Pocket Computer, Microvision
- Modern retro handhelds (Analogue Pocket, Miyoo Mini, RG35XX)

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
    """Curated retro handheld consoles catalog."""

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

        # ---------------------------------------------------------------
        # Nintendo Game Boy Micro
        # ---------------------------------------------------------------
        ("Nintendo", "Game Boy Micro Silver", "Game Boy Micro", "Silver", "Standard", "high", 130, 280),
        ("Nintendo", "Game Boy Micro 20th Anniversary Famicom", "Game Boy Micro", "20th Anniversary Famicom", "Anniversary", "grail", 250, 500),

        # ---------------------------------------------------------------
        # Nintendo DS Family
        # ---------------------------------------------------------------
        ("Nintendo", "Nintendo DS Original Silver", "Nintendo DS", "Titanium Silver (Phat)", "Standard", "standard", 25, 55),
        ("Nintendo", "Nintendo DS Lite White", "Nintendo DS Lite", "Polar White", "Standard", "standard", 25, 55),
        ("Nintendo", "Nintendo DS Lite Crimson/Black", "Nintendo DS Lite", "Crimson/Black", "Standard", "mid", 30, 65),
        ("Nintendo", "Nintendo DS Lite Zelda Phantom Hourglass", "Nintendo DS Lite", "Zelda Gold", "Special Edition", "high", 100, 220),
        ("Nintendo", "Nintendo DS Lite Final Fantasy III", "Nintendo DS Lite", "Crystal White FF III Bundle", "Console Bundle", "high", 80, 180),
        ("Nintendo", "Nintendo DS Lite Pokemon Diamond/Pearl", "Nintendo DS Lite", "Pokemon Dialga/Palkia", "Special Edition", "high", 90, 200),
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

        # ---------------------------------------------------------------
        # Sony PS Vita
        # ---------------------------------------------------------------
        ("Sony", "PS Vita OLED Black", "PS Vita 1000", "Black OLED (PCH-1000)", "Standard", "high", 110, 220),
        ("Sony", "PS Vita OLED White", "PS Vita 1000", "Crystal White OLED (Japan)", "Japan Exclusive", "high", 130, 260),
        ("Sony", "PS Vita Slim Black", "PS Vita 2000", "Black Slim (PCH-2000)", "Standard", "high", 100, 200),
        ("Sony", "PS Vita Slim Aqua Blue", "PS Vita 2000", "Aqua Blue Slim (Japan)", "Japan Exclusive", "high", 140, 280),

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

        # ---------------------------------------------------------------
        # Neo Geo Pocket Color
        # ---------------------------------------------------------------
        ("SNK", "Neo Geo Pocket Color Anthracite", "Neo Geo Pocket Color", "Anthracite Black", "Standard", "high", 80, 170),
        ("SNK", "Neo Geo Pocket Color Crystal Blue", "Neo Geo Pocket Color", "Crystal Blue", "Limited Color", "high", 100, 210),
        ("SNK", "Neo Geo Pocket Color Platinum Silver", "Neo Geo Pocket Color", "Platinum Silver", "Standard", "high", 85, 180),

        # ---------------------------------------------------------------
        # Bandai WonderSwan
        # ---------------------------------------------------------------
        ("Bandai", "WonderSwan Crystal Blue", "WonderSwan Crystal", "Crystal Blue", "Standard", "high", 60, 130),
        ("Bandai", "SwanCrystal Wine Red", "SwanCrystal", "Wine Red", "Standard", "high", 65, 140),
        ("Bandai", "WonderSwan Color Final Fantasy", "WonderSwan Color", "Final Fantasy Limited (Japan)", "Japan Exclusive", "high", 110, 240),
        ("Bandai", "WonderSwan Color Final Fantasy II", "WonderSwan Color", "Final Fantasy II Crystal Blue (Japan)", "Japan Exclusive", "high", 120, 250),

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
