"""
Import Yu-Gi-Oh card data from YGOProDeck API.

Layer 1 (Catalog):  All cards → category_items
Layer 2 (Prices):   TCGPlayer/Cardmarket prices from API → train.jsonl + market_hits
Layer 3 (Fallback): Curated seed of 100+ iconic/high-value cards when API is unavailable

API: https://ygoprodeck.com/api-guide/
Rate limit: 20 requests/second, no API key needed.
Endpoint: https://db.ygoprodeck.com/api/v7/cardinfo.php (returns ALL cards at once)

Usage:
    python -m pipelines.import_yugioh [--dry-run]
    python -m pipelines.import_yugioh [--dry-run] [--curated-only]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem, PriceObservation, MarketHit, SupabaseIngest,
    write_training_jsonl, write_catalog_sql, fetch_json,
    log_progress, slugify, to_eur,
    rarity_score as shared_rarity_score,
    RARITY_SCORE_MAP,
    logger,
    close_http_client,
)

API_BASE = "https://db.ygoprodeck.com/api/v7"
CATEGORY = "yugioh"

# ---------------------------------------------------------------------------
# Rarity & edition scoring maps for curated catalog
# ---------------------------------------------------------------------------

YUGIOH_RARITY_SCORES: dict[str, float] = {
    "Common": 0.10,
    "Rare": 0.40,
    "Super Rare": 0.55,
    "Ultra Rare": 0.70,
    "Secret Rare": 0.80,
    "Ultimate Rare": 0.85,
    "Ghost Rare": 0.90,
    "Starlight Rare": 0.95,
    "Quarter Century Secret Rare": 0.98,
    "Prize Card": 0.99,
    "Collector's Rare": 0.82,
    "Prismatic Secret Rare": 0.88,
    "Gold Rare": 0.65,
    "Gold Secret Rare": 0.75,
    "Platinum Secret Rare": 0.85,
    "Sealed Product": 0.70,
}

EDITION_SCORES: dict[str, float] = {
    "1st Edition": 0.90,
    "Limited Edition": 0.80,
    "Unlimited": 0.40,
    "Promo": 0.60,
}


def _rarity_score(rarity: str) -> float:
    """Look up rarity score for curated catalog entries."""
    return YUGIOH_RARITY_SCORES.get(rarity, 0.50)


def _edition_score(edition: str) -> float:
    """Look up edition score for curated catalog entries."""
    return EDITION_SCORES.get(edition, 0.50)


# ---------------------------------------------------------------------------
# Curated seed catalog — 100+ iconic/high-value Yu-Gi-Oh cards
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[dict]:
    """Curated Yu-Gi-Oh catalog covering the most collectible cards in the hobby.

    Returns a list of dicts with keys:
        set_code, card_name, set_name, rarity, is_first_edition, price_eur,
        card_type, attribute
    """

    # Format: (set_code, card_name, set_name, rarity, is_first_edition, price_eur,
    #          card_type, attribute)
    # card_type: Monster / Spell / Trap / Sealed Product
    # attribute: LIGHT / DARK / EARTH / WIND / WATER / FIRE / DIVINE / "" (spells/traps)

    cards: list[tuple] = [
        # =================================================================
        # Legend of Blue-Eyes White Dragon (LOB) — the original set
        # =================================================================
        ("LOB-001", "Blue-Eyes White Dragon", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", True, 8500.00, "Monster", "LIGHT"),
        ("LOB-001", "Blue-Eyes White Dragon", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", False, 450.00, "Monster", "LIGHT"),
        ("LOB-005", "Dark Magician", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", True, 3200.00, "Monster", "DARK"),
        ("LOB-005", "Dark Magician", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", False, 180.00, "Monster", "DARK"),
        ("LOB-124", "Exodia the Forbidden One", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", True, 4500.00, "Monster", "DARK"),
        ("LOB-120", "Left Leg of the Forbidden One", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", True, 1200.00, "Monster", "DARK"),
        ("LOB-121", "Left Arm of the Forbidden One", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", True, 1200.00, "Monster", "DARK"),
        ("LOB-122", "Right Leg of the Forbidden One", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", True, 1200.00, "Monster", "DARK"),
        ("LOB-123", "Right Arm of the Forbidden One", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", True, 1200.00, "Monster", "DARK"),
        ("LOB-118", "Monster Reborn", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", True, 600.00, "Spell", ""),
        ("LOB-053", "Raigeki", "Legend of Blue-Eyes White Dragon",
         "Super Rare", True, 350.00, "Spell", ""),
        ("LOB-119", "Pot of Greed", "Legend of Blue-Eyes White Dragon",
         "Rare", True, 85.00, "Spell", ""),
        ("LOB-042", "Red-Eyes Black Dragon", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", True, 2800.00, "Monster", "DARK"),
        ("LOB-006", "Gaia The Fierce Knight", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", True, 400.00, "Monster", "EARTH"),
        ("LOB-007", "Curse of Dragon", "Legend of Blue-Eyes White Dragon",
         "Super Rare", True, 120.00, "Monster", "DARK"),

        # =================================================================
        # Metal Raiders (MRD)
        # =================================================================
        ("MRD-138", "Mirror Force", "Metal Raiders",
         "Ultra Rare", True, 950.00, "Trap", ""),
        ("MRD-142", "Heavy Storm", "Metal Raiders",
         "Super Rare", True, 180.00, "Spell", ""),
        ("MRD-127", "Solemn Judgment", "Metal Raiders",
         "Ultra Rare", True, 700.00, "Trap", ""),
        ("MRD-143", "Change of Heart", "Metal Raiders",
         "Ultra Rare", True, 350.00, "Spell", ""),
        ("MRD-126", "Barrel Dragon", "Metal Raiders",
         "Ultra Rare", True, 800.00, "Monster", "DARK"),
        ("MRD-000", "Gate Guardian", "Metal Raiders",
         "Secret Rare", True, 1600.00, "Monster", "DARK"),
        ("MRD-024", "Summoned Skull", "Metal Raiders",
         "Ultra Rare", True, 250.00, "Monster", "DARK"),
        ("MRD-140", "Ring of Destruction", "Metal Raiders",
         "Ultra Rare", True, 400.00, "Trap", ""),
        ("MRD-131", "Delinquent Duo", "Metal Raiders",
         "Ultra Rare", True, 220.00, "Spell", ""),
        ("MRD-141", "Magic Jammer", "Metal Raiders",
         "Ultra Rare", True, 150.00, "Trap", ""),

        # =================================================================
        # Pharaoh's Servant (PSV)
        # =================================================================
        ("PSV-000", "Jinzo", "Pharaoh's Servant",
         "Secret Rare", True, 1200.00, "Monster", "DARK"),
        ("PSV-104", "Imperial Order", "Pharaoh's Servant",
         "Ultra Rare", True, 650.00, "Trap", ""),
        ("PSV-012", "Call of the Haunted", "Pharaoh's Servant",
         "Ultra Rare", True, 350.00, "Trap", ""),
        ("PSV-037", "Premature Burial", "Pharaoh's Servant",
         "Ultra Rare", True, 280.00, "Spell", ""),
        ("PSV-036", "Nobleman of Crossout", "Pharaoh's Servant",
         "Ultra Rare", True, 180.00, "Spell", ""),
        ("PSV-003", "Thousand-Eyes Restrict", "Pharaoh's Servant",
         "Ultra Rare", True, 450.00, "Monster", "DARK"),
        ("PSV-006", "Limiter Removal", "Pharaoh's Servant",
         "Ultra Rare", True, 200.00, "Spell", ""),

        # =================================================================
        # Magic Ruler / Spell Ruler (MRL/SRL)
        # =================================================================
        ("SRL-EN000", "Serpent Night Dragon", "Spell Ruler",
         "Secret Rare", True, 600.00, "Monster", "DARK"),
        ("SRL-EN043", "Mystical Space Typhoon", "Spell Ruler",
         "Ultra Rare", True, 220.00, "Spell", ""),
        ("SRL-EN042", "Snatch Steal", "Spell Ruler",
         "Ultra Rare", True, 180.00, "Spell", ""),
        ("SRL-EN036", "Toon World", "Spell Ruler",
         "Super Rare", True, 90.00, "Spell", ""),

        # =================================================================
        # Invasion of Chaos (IOC)
        # =================================================================
        ("IOC-025", "Black Luster Soldier - Envoy of the Beginning", "Invasion of Chaos",
         "Ultra Rare", True, 2200.00, "Monster", "LIGHT"),
        ("IOC-000", "Chaos Emperor Dragon - Envoy of the End", "Invasion of Chaos",
         "Secret Rare", True, 3500.00, "Monster", "DARK"),
        ("IOC-065", "Dark Magician of Chaos", "Invasion of Chaos",
         "Ultra Rare", True, 450.00, "Monster", "DARK"),
        ("IOC-067", "Manticore of Darkness", "Invasion of Chaos",
         "Ultra Rare", True, 150.00, "Monster", "FIRE"),
        ("IOC-053", "Dimension Fusion", "Invasion of Chaos",
         "Ultra Rare", True, 300.00, "Spell", ""),
        ("IOC-035", "Smashing Ground", "Invasion of Chaos",
         "Super Rare", True, 75.00, "Spell", ""),

        # =================================================================
        # Dark Beginning / Legacy sets
        # =================================================================
        ("DB1-EN094", "Harpie's Feather Duster", "Dark Beginning 1",
         "Ultra Rare", False, 120.00, "Spell", ""),
        ("DB2-EN042", "Tribe-Infecting Virus", "Dark Beginning 2",
         "Ultra Rare", False, 60.00, "Monster", "WATER"),

        # =================================================================
        # Pharaonic Guardian (PGD)
        # =================================================================
        ("PGD-000", "Ring of Destruction", "Pharaonic Guardian",
         "Secret Rare", True, 900.00, "Trap", ""),
        ("PGD-071", "Lava Golem", "Pharaonic Guardian",
         "Ultra Rare", True, 200.00, "Monster", "FIRE"),

        # =================================================================
        # Tournament / Championship Exclusives & Promos
        # =================================================================
        ("MFC-000", "Dark Magician Girl", "Magician's Force",
         "Secret Rare", True, 2800.00, "Monster", "DARK"),
        ("JMP-EN005", "Blue-Eyes Ultimate Dragon", "Shonen Jump Promo",
         "Ultra Rare", False, 380.00, "Monster", "LIGHT"),
        ("CRV-EN016", "Cyber Dragon", "Cybernetic Revolution",
         "Ultra Rare", True, 350.00, "Monster", "LIGHT"),
        ("SOD-EN035", "Mobius the Frost Monarch", "Soul of the Duelist",
         "Ultra Rare", True, 180.00, "Monster", "WATER"),
        ("FET-EN031", "Sacred Phoenix of Nephthys", "Flaming Eternity",
         "Ultra Rare", True, 200.00, "Monster", "FIRE"),
        ("TLM-EN006", "Ancient Gear Golem", "The Lost Millennium",
         "Ultra Rare", True, 150.00, "Monster", "EARTH"),

        # =================================================================
        # Ghost Rares — most iconic ghost rares in the game
        # =================================================================
        ("TAEV-EN006", "Rainbow Dragon", "Tactical Evolution",
         "Ghost Rare", True, 1800.00, "Monster", "LIGHT"),
        ("TDGS-EN040", "Stardust Dragon", "The Duelist Genesis",
         "Ghost Rare", True, 2500.00, "Monster", "WIND"),
        ("CSOC-EN039", "Black Rose Dragon", "Crossroads of Chaos",
         "Ghost Rare", True, 2200.00, "Monster", "FIRE"),
        ("ANPR-EN040", "Ancient Fairy Dragon", "Ancient Prophecy",
         "Ghost Rare", True, 1500.00, "Monster", "LIGHT"),
        ("RGBT-EN043", "Power Tool Dragon", "Raging Battle",
         "Ghost Rare", True, 800.00, "Monster", "EARTH"),
        ("PTDN-EN044", "Rainbow Neos", "Phantom Darkness",
         "Ghost Rare", True, 1400.00, "Monster", "LIGHT"),
        ("SOVR-EN044", "Majestic Star Dragon", "Stardust Overdrive",
         "Ghost Rare", True, 600.00, "Monster", "WIND"),
        ("DREV-EN020", "Black-Winged Dragon", "Duelist Revolution",
         "Ghost Rare", True, 500.00, "Monster", "DARK"),
        ("STOR-EN041", "Shooting Star Dragon", "Storm of Ragnarok",
         "Ghost Rare", True, 700.00, "Monster", "WIND"),
        ("GLD5-EN053", "Ghost Rare Blue-Eyes White Dragon", "Gold Series: Haunted Mine",
         "Ghost Rare", False, 1100.00, "Monster", "LIGHT"),

        # =================================================================
        # Starlight Rares — modern chase cards
        # =================================================================
        ("ETCO-EN045", "Accesscode Talker", "Eternity Code",
         "Starlight Rare", True, 1200.00, "Monster", "DARK"),
        ("RIRA-EN048", "Apollousa, Bow of the Goddess", "Rising Rampage",
         "Starlight Rare", True, 800.00, "Monster", "WIND"),
        ("MYFI-EN020", "Chamber Dragonmaid", "Mystic Fighters",
         "Starlight Rare", True, 900.00, "Monster", "LIGHT"),  # technically Secret; proxy
        ("BLVO-EN065", "Pot of Prosperity", "Blazing Vortex",
         "Starlight Rare", True, 750.00, "Spell", ""),
        ("DUDE-EN004", "Ghost Belle & Haunted Mansion", "Duel Devastator",
         "Ultra Rare", False, 85.00, "Monster", "EARTH"),  # DUDE printing
        ("IGAS-EN000", "Ash Blossom & Joyous Spring", "Ignition Assault",
         "Starlight Rare", True, 600.00, "Monster", "FIRE"),
        ("PHRA-EN000", "Tri-Brigade Shuraig the Ominous Omen", "Phantom Rage",
         "Starlight Rare", True, 550.00, "Monster", "DARK"),
        ("MP20-EN028", "Nibiru, the Primal Being", "2020 Tin of Lost Memories",
         "Prismatic Secret Rare", False, 120.00, "Monster", "LIGHT"),
        ("ROTD-EN004", "Dogmatika Ecclesia, the Virtuous", "Rise of the Duelist",
         "Starlight Rare", True, 700.00, "Monster", "LIGHT"),
        ("BROL-EN039", "Forbidden Droplet", "Brothers of Legend",
         "Ultra Rare", True, 95.00, "Spell", ""),

        # =================================================================
        # Prize Cards & Ultra-Premium Exclusives
        # =================================================================
        ("T3-01", "Tyler the Great Warrior", "One-of-a-Kind",
         "Prize Card", False, 250000.00, "Monster", "EARTH"),
        ("SJC-EN001", "Crush Card Virus (SJC Prize)", "Shonen Jump Championship",
         "Prize Card", False, 15000.00, "Trap", ""),
        ("YCSW-EN001", "Minerva, the Exalted Lightsworn", "YCS Prize",
         "Prize Card", False, 12000.00, "Monster", "LIGHT"),
        ("WCS-001", "Gold Sarcophagus (WCS)", "World Championship Series",
         "Prize Card", False, 8000.00, "Spell", ""),
        ("WCPS-EN801", "Cyber-Stein (SJC)", "Shonen Jump Championship",
         "Prize Card", False, 18000.00, "Monster", "DARK"),
        ("YCSW-EN005", "Ascension Sky Dragon (YCSW)", "YCS Prize",
         "Prize Card", False, 5000.00, "Monster", "LIGHT"),

        # =================================================================
        # Iconic GX / 5Ds / Zexal era cards
        # =================================================================
        ("SOI-EN035", "Elemental HERO Neos", "Shadow of Infinity",
         "Ultra Rare", True, 250.00, "Monster", "LIGHT"),
        ("STON-EN034", "Neo-Spacian Grand Mole", "Strike of Neos",
         "Ultra Rare", True, 120.00, "Monster", "EARTH"),
        ("DP03-EN011", "Elemental HERO Stratos", "Duelist Pack: Jaden Yuki 2",
         "Ultra Rare", True, 100.00, "Monster", "WIND"),
        ("LCGX-EN033", "Yubel", "Legendary Collection 2",
         "Ultra Rare", False, 60.00, "Monster", "DARK"),
        ("CT05-EN002", "Stardust Dragon", "Collectible Tin 2008",
         "Secret Rare", False, 150.00, "Monster", "WIND"),
        ("ORCS-EN040", "Number 39: Utopia", "Order of Chaos",
         "Ultra Rare", True, 80.00, "Monster", "LIGHT"),
        ("GAOV-EN041", "Number C39: Utopia Ray", "Galactic Overlord",
         "Ultra Rare", True, 65.00, "Monster", "LIGHT"),

        # =================================================================
        # Arc-V / VRAINS / Modern meta staples
        # =================================================================
        ("DUEA-EN049", "Dante, Traveler of the Burning Abyss", "Duelist Alliance",
         "Secret Rare", True, 120.00, "Monster", "LIGHT"),
        ("MACR-EN081", "Firewall Dragon", "Maximum Crisis",
         "Secret Rare", True, 85.00, "Monster", "LIGHT"),
        ("FLOD-EN043", "Knightmare Unicorn", "Flames of Destruction",
         "Secret Rare", True, 65.00, "Monster", "DARK"),
        ("DUOV-EN001", "Lightning Storm", "Duel Overload",
         "Ultra Rare", True, 90.00, "Spell", ""),
        ("LIOV-EN050", "Baronne de Fleur", "Lightning Overdrive",
         "Secret Rare", True, 110.00, "Monster", "WIND"),
        ("BODE-EN009", "Swordsoul Grandmaster - Chixiao", "Burst of Destiny",
         "Secret Rare", True, 70.00, "Monster", "WATER"),

        # =================================================================
        # Quarter Century Secret Rares (25th anniversary)
        # =================================================================
        ("RA02-EN001", "Blue-Eyes White Dragon (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 1800.00, "Monster", "LIGHT"),
        ("RA02-EN006", "Dark Magician (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 1600.00, "Monster", "DARK"),
        ("RA01-EN030", "Exodia the Forbidden One (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 2000.00, "Monster", "DARK"),
        ("RA01-EN076", "Ash Blossom & Joyous Spring (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 900.00, "Monster", "FIRE"),
        ("RA01-EN050", "Called by the Grave (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 400.00, "Spell", ""),
        ("RA02-EN050", "Nibiru, the Primal Being (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 500.00, "Monster", "LIGHT"),

        # =================================================================
        # Collector's Rares / Prismatic Secret Rares (modern premium)
        # =================================================================
        ("TOCH-EN010", "Ice Dragon's Prison", "Toon Chaos",
         "Collector's Rare", True, 180.00, "Trap", ""),
        ("GFTP-EN001", "Ghost Mourner & Moonlit Chill", "Ghosts From the Past",
         "Ultra Rare", True, 45.00, "Monster", "DARK"),
        ("MP21-EN003", "Triple Tactics Talent", "2021 Tin of Ancient Battles",
         "Prismatic Secret Rare", False, 120.00, "Spell", ""),
        ("MP22-EN264", "Branded Fusion", "2022 Tin of the Pharaoh's Gods",
         "Prismatic Secret Rare", False, 80.00, "Spell", ""),
        ("GRCR-EN001", "Blue-Eyes White Dragon (Collector's Rare)", "The Grand Creators",
         "Collector's Rare", True, 250.00, "Monster", "LIGHT"),
        ("AMDE-EN001", "Tearlaments Kitkallos", "Amazing Defenders",
         "Ultra Rare", True, 60.00, "Monster", "DARK"),

        # =================================================================
        # Sealed Product — booster boxes, packs, starter decks
        # =================================================================
        ("LOB-BOX", "LOB Unlimited Booster Box", "Legend of Blue-Eyes White Dragon",
         "Sealed Product", False, 25000.00, "Sealed Product", ""),
        ("LOB-1ST-PACK", "LOB 1st Edition Booster Pack", "Legend of Blue-Eyes White Dragon",
         "Sealed Product", True, 8000.00, "Sealed Product", ""),
        ("MRD-BOX", "MRD Unlimited Booster Box", "Metal Raiders",
         "Sealed Product", False, 12000.00, "Sealed Product", ""),
        ("MRD-1ST-BOX", "MRD 1st Edition Booster Box", "Metal Raiders",
         "Sealed Product", True, 35000.00, "Sealed Product", ""),
        ("PSV-BOX", "PSV Unlimited Booster Box", "Pharaoh's Servant",
         "Sealed Product", False, 8000.00, "Sealed Product", ""),
        ("PSV-1ST-PACK", "PSV 1st Edition Booster Pack", "Pharaoh's Servant",
         "Sealed Product", True, 1500.00, "Sealed Product", ""),
        ("IOC-BOX", "IOC Unlimited Booster Box", "Invasion of Chaos",
         "Sealed Product", False, 10000.00, "Sealed Product", ""),
        ("IOC-1ST-BOX", "IOC 1st Edition Booster Box", "Invasion of Chaos",
         "Sealed Product", True, 45000.00, "Sealed Product", ""),
        ("SDK-1ST", "Starter Deck Kaiba 1st Edition", "Starter Deck Kaiba",
         "Sealed Product", True, 3500.00, "Sealed Product", ""),
        ("SDY-1ST", "Starter Deck Yugi 1st Edition", "Starter Deck Yugi",
         "Sealed Product", True, 4000.00, "Sealed Product", ""),
        ("DB1-BOX", "Dark Beginning 1 Booster Box", "Dark Beginning 1",
         "Sealed Product", False, 2500.00, "Sealed Product", ""),
        ("LOB-1ST-BOX", "LOB 1st Edition Booster Box", "Legend of Blue-Eyes White Dragon",
         "Sealed Product", True, 120000.00, "Sealed Product", ""),

        # =================================================================
        # Additional high-value staples & fan favorites
        # =================================================================
        ("MFC-094", "Breaker the Magical Warrior", "Magician's Force",
         "Ultra Rare", True, 250.00, "Monster", "DARK"),
        ("DCR-026", "Vampire Lord", "Dark Crisis",
         "Ultra Rare", True, 180.00, "Monster", "DARK"),
        ("DCR-000", "Ring of Destruction (Secret)", "Dark Crisis",
         "Secret Rare", True, 350.00, "Trap", ""),
        ("AST-034", "Zaborg the Thunder Monarch", "Ancient Sanctuary",
         "Ultra Rare", True, 80.00, "Monster", "LIGHT"),
        ("RDS-ENSE1", "Phoenix Wing Wind Blast", "Rise of Destiny",
         "Ultra Rare", True, 45.00, "Trap", ""),
        ("SOD-EN033", "Mystic Swordsman LV2", "Soul of the Duelist",
         "Ultra Rare", True, 60.00, "Monster", "EARTH"),
        ("TLM-ENSE2", "Ojamagic", "The Lost Millennium",
         "Super Rare", True, 35.00, "Spell", ""),
        ("LON-EN000", "Gemini Elf", "Labyrinth of Nightmare",
         "Secret Rare", True, 400.00, "Monster", "EARTH"),
    ]

    catalog = []
    for entry in cards:
        (set_code, card_name, set_name, rarity, is_first_edition,
         price_eur, card_type, attribute) = entry

        edition = "1st Edition" if is_first_edition else "Unlimited"
        if "Promo" in set_name or "Prize" in set_name or "Shonen Jump" in set_name:
            edition = "Promo"
        if "Limited" in rarity or "Limited" in set_name:
            edition = "Limited Edition"

        catalog.append({
            "set_code": set_code,
            "card_name": card_name,
            "set_name": set_name,
            "rarity": rarity,
            "is_first_edition": is_first_edition,
            "price_eur": price_eur,
            "card_type": card_type,
            "attribute": attribute,
            "edition": edition,
        })

    return catalog


# ---------------------------------------------------------------------------
# Curated catalog → CatalogItem / PriceObservation converters
# ---------------------------------------------------------------------------

def _curated_to_catalog_item(entry: dict) -> CatalogItem:
    """Convert a curated catalog entry to a CatalogItem."""
    set_code = entry["set_code"]
    card_name = entry["card_name"]
    set_name = entry["set_name"]
    rarity = entry["rarity"]
    edition = entry["edition"]

    set_prefix = set_code.split("-")[0] if "-" in set_code else set_code

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{set_code}-{card_name}-{edition}"),
        title=card_name,
        set_code=set_prefix,
        brand="Yu-Gi-Oh",
        rarity=rarity,
        notes=f"{set_name} ({set_code}) [{edition}]",
        image_url="",
        attributes_json={
            "set_name": set_name,
            "card_number": set_code,
            "rarity": rarity,
            "is_first_edition": entry["is_first_edition"],
            "card_type": entry["card_type"],
            "attribute": entry["attribute"],
        },
    )


def _curated_to_price_observation(entry: dict) -> PriceObservation:
    """Convert a curated catalog entry to a PriceObservation."""
    return PriceObservation(
        features={
            "condition_score": 0.9,  # Near Mint default
            "rarity_score": _rarity_score(entry["rarity"]),
            "edition_score": _edition_score(entry["edition"]),
        },
        price=entry["price_eur"],
    )


def _curated_to_market_hit(entry: dict) -> MarketHit:
    """Convert a curated catalog entry to a MarketHit."""
    set_code = entry["set_code"]
    card_name = entry["card_name"]
    edition = entry["edition"]

    return MarketHit(
        provider="curated-seed",
        listing_id=f"ygo-seed-{slugify(f'{set_code}-{card_name}-{edition}')}",
        title=f"{card_name} ({set_code}) [{edition}]",
        price=entry["price_eur"],
        currency="EUR",
        condition="NM",
        normalized_key=slugify(f"{set_code}-{card_name}-{edition}"),
        category=CATEGORY,
    )


def _run_curated_seed(dry_run: bool = False) -> tuple[list[CatalogItem], list[PriceObservation], list[MarketHit]]:
    """Process the curated seed catalog. Used as fallback when the API is unavailable."""
    logger.info("Running curated seed catalog (100+ iconic Yu-Gi-Oh cards)...")

    catalog = get_curated_catalog()
    log_progress(CATEGORY, "curated entries loaded", len(catalog))

    all_items = [_curated_to_catalog_item(e) for e in catalog]
    all_observations = [_curated_to_price_observation(e) for e in catalog]
    all_hits = [_curated_to_market_hit(e) for e in catalog]

    # Deduplicate by item_key
    seen: set[str] = set()
    deduped: list[CatalogItem] = []
    for item in all_items:
        if item.item_key not in seen:
            seen.add(item.item_key)
            deduped.append(item)
    all_items = deduped

    log_progress(CATEGORY, "curated catalog items", len(all_items))
    log_progress(CATEGORY, "curated price observations", len(all_observations))
    log_progress(CATEGORY, "curated market hits", len(all_hits))

    return all_items, all_observations, all_hits


# ---------------------------------------------------------------------------
# YGOProDeck API-based import (original flow)
# ---------------------------------------------------------------------------

def fetch_all_cards() -> list[dict]:
    """Fetch entire Yu-Gi-Oh card database (single request)."""
    logger.info("Fetching all Yu-Gi-Oh cards (single API call)...")
    data = fetch_json(f"{API_BASE}/cardinfo.php")
    cards = data.get("data", [])
    log_progress(CATEGORY, "cards fetched", len(cards))
    return cards


def card_to_catalog_items(card: dict) -> list[CatalogItem]:
    """One card can have multiple sets/printings."""
    items = []
    name = card.get("name", "")
    card_type = card.get("type", "")
    race = card.get("race", "")

    card_sets = card.get("card_sets", [])
    if not card_sets:
        # Card with no set info - still add it
        items.append(CatalogItem(
            category=CATEGORY,
            item_key=slugify(f"{card.get('id', '')}-{name}"),
            title=name,
            set_code="",
            brand="Yu-Gi-Oh",
            rarity="",
            notes=f"{card_type} - {race}",
            image_url=card.get("card_images", [{}])[0].get("image_url_small", ""),
            attributes_json={
                "type": card_type,
                "race": race,
                "atk": card.get("atk"),
                "def": card.get("def"),
                "level": card.get("level"),
            },
        ))
    else:
        for cs in card_sets:
            set_code = cs.get("set_code", "")
            set_name = cs.get("set_name", "")
            rarity = cs.get("set_rarity", "")

            items.append(CatalogItem(
                category=CATEGORY,
                item_key=slugify(f"{set_code}-{name}"),
                title=name,
                set_code=set_code.split("-")[0] if "-" in set_code else set_code,
                brand="Yu-Gi-Oh",
                rarity=rarity,
                notes=f"{set_name} ({set_code})",
                image_url=card.get("card_images", [{}])[0].get("image_url_small", ""),
                attributes_json={
                    "set": set_name,
                    "number": set_code,
                    "rarity": rarity,
                    "type": card_type,
                },
            ))
    return items


def card_to_price_observations(card: dict) -> list[PriceObservation]:
    observations = []
    prices = card.get("card_prices", [{}])[0] if card.get("card_prices") else {}

    cardmarket_price = prices.get("cardmarket_price", "0")
    try:
        cm_price = float(cardmarket_price)
    except (ValueError, TypeError):
        cm_price = 0.0

    if cm_price > 0:
        rarity_scores = {}
        for cs in card.get("card_sets", []):
            r = cs.get("set_rarity", "Common")
            if r == "Common":
                rarity_scores[r] = 0.1
            elif r == "Rare":
                rarity_scores[r] = 0.4
            elif "Super" in r:
                rarity_scores[r] = 0.55
            elif "Ultra" in r:
                rarity_scores[r] = 0.7
            elif "Secret" in r:
                rarity_scores[r] = 0.8
            elif "Ultimate" in r or "Ghost" in r:
                rarity_scores[r] = 0.9
            elif "Starlight" in r:
                rarity_scores[r] = 0.95
            else:
                rarity_scores[r] = 0.5

        avg_rarity = sum(rarity_scores.values()) / max(len(rarity_scores), 1)
        observations.append(PriceObservation(
            features={
                "condition_score": 0.9,
                "rarity_score": avg_rarity,
                "edition_score": 0.5,
            },
            price=cm_price,  # already EUR from Cardmarket
        ))

    tcg_price = prices.get("tcgplayer_price", "0")
    try:
        tcg_float = float(tcg_price)
    except (ValueError, TypeError):
        tcg_float = 0.0

    if tcg_float > 0:
        observations.append(PriceObservation(
            features={
                "condition_score": 0.9,
                "rarity_score": 0.5,
                "edition_score": 0.5,
            },
            price=to_eur(tcg_float, "USD"),
        ))

    return observations


def card_to_market_hits(card: dict) -> list[MarketHit]:
    hits = []
    prices = card.get("card_prices", [{}])[0] if card.get("card_prices") else {}
    name = card.get("name", "")

    for source, key, currency in [
        ("cardmarket", "cardmarket_price", "EUR"),
        ("tcgplayer", "tcgplayer_price", "USD"),
    ]:
        price_str = prices.get(key, "0")
        try:
            price_float = float(price_str)
        except (ValueError, TypeError):
            continue
        if price_float <= 0:
            continue

        hits.append(MarketHit(
            provider=source,
            listing_id=f"ygo-{card.get('id', '')}-{source}",
            title=name,
            price=to_eur(price_float, currency),
            currency="EUR",
            condition="NM",
            normalized_key=slugify(f"{card.get('id', '')}-{name}"),
            category=CATEGORY,
        ))
    return hits


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Import Yu-Gi-Oh catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--curated-only", action="store_true",
                        help="Skip API fetch and only use the curated seed catalog")
    args = parser.parse_args()

    logger.info("=== Yu-Gi-Oh Import (YGOProDeck) ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    all_items: list[CatalogItem] = []
    all_observations: list[PriceObservation] = []
    all_hits: list[MarketHit] = []

    if args.curated_only:
        # Use curated seed catalog only
        items, obs, hits = _run_curated_seed(dry_run=args.dry_run)
        all_items.extend(items)
        all_observations.extend(obs)
        all_hits.extend(hits)
    else:
        # Try API first, fall back to curated seed on failure
        try:
            cards = fetch_all_cards()

            for i, card in enumerate(cards):
                all_items.extend(card_to_catalog_items(card))
                all_observations.extend(card_to_price_observations(card))
                all_hits.extend(card_to_market_hits(card))

                if (i + 1) % 2000 == 0:
                    log_progress(CATEGORY, "processing", i + 1, len(cards))

            # Deduplicate by item_key
            seen: set[str] = set()
            deduped: list[CatalogItem] = []
            for item in all_items:
                if item.item_key not in seen:
                    seen.add(item.item_key)
                    deduped.append(item)
            all_items = deduped

        except Exception as e:
            logger.warning(f"YGOProDeck API failed: {e}")
            logger.info("Falling back to curated seed catalog...")
            all_items.clear()
            all_observations.clear()
            all_hits.clear()

            items, obs, hits = _run_curated_seed(dry_run=args.dry_run)
            all_items.extend(items)
            all_observations.extend(obs)
            all_hits.extend(hits)

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    if all_observations:
        write_training_jsonl(CATEGORY, all_observations)
        log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)
        if all_hits:
            hits_inserted = ingest.upsert_market_hits(all_hits)
            log_progress(CATEGORY, "market_hits upserted", hits_inserted)

    ingest.close()

    logger.info(f"\n=== Yu-Gi-Oh Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")
    logger.info(f"  Market hits:        {len(all_hits)}")


if __name__ == "__main__":
    main()
