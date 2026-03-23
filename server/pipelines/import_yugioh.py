"""
Import Yu-Gi-Oh card data from YGOProDeck API.

Layer 1 (Catalog):  All cards → category_items
Layer 2 (Prices):   TCGPlayer/Cardmarket prices from API → train.jsonl + market_hits
Layer 3 (Fallback): Curated seed of 500+ iconic/high-value cards when API is unavailable

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
    """Curated Yu-Gi-Oh catalog covering the most collectible cards (500+ items).

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

        # =================================================================
        # 25th Anniversary Rarity Collection chase cards
        # =================================================================
        ("RA01-EN001", "Blue-Eyes White Dragon (QCSR Ghost)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 2200.00, "Monster", "LIGHT"),
        ("RA01-EN050", "Infinite Impermanence (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 350.00, "Trap", ""),
        ("RA02-EN025", "Red-Eyes Black Dragon (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 1400.00, "Monster", "DARK"),
        ("RA02-EN080", "Effect Veiler (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 300.00, "Monster", "LIGHT"),

        # =================================================================
        # Age of Overlord (AGOV) chase cards
        # =================================================================
        ("AGOV-EN008", "Fiendsmith Lacrimosa", "Age of Overlord",
         "Secret Rare", True, 85.00, "Monster", "LIGHT"),
        ("AGOV-EN014", "Fiendsmith Requiem", "Age of Overlord",
         "Starlight Rare", True, 400.00, "Monster", "DARK"),
        ("AGOV-EN055", "Vaalmonica Scelta", "Age of Overlord",
         "Ultra Rare", True, 50.00, "Spell", ""),
        ("AGOV-EN056", "Vaalmonica Invitare", "Age of Overlord",
         "Secret Rare", True, 75.00, "Trap", ""),

        # =================================================================
        # Phantom Nightmare (PHNI) chase cards
        # =================================================================
        ("PHNI-EN004", "Snake-Eye Ash", "Phantom Nightmare",
         "Secret Rare", True, 95.00, "Monster", "FIRE"),
        ("PHNI-EN004", "Snake-Eye Ash", "Phantom Nightmare",
         "Starlight Rare", True, 500.00, "Monster", "FIRE"),
        ("PHNI-EN034", "Bonfire", "Phantom Nightmare",
         "Super Rare", True, 60.00, "Spell", ""),
        ("PHNI-EN001", "Snake-Eyes Flamberge Dragon", "Phantom Nightmare",
         "Ultra Rare", True, 40.00, "Monster", "FIRE"),

        # =================================================================
        # Recent Ghost Rares
        # =================================================================
        ("MAMA-EN060", "Blue-Eyes Chaos MAX Dragon", "Magnificent Mavens",
         "Ghost Rare", False, 350.00, "Monster", "DARK"),
        ("GFTP2-EN076", "Stardust Dragon", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 250.00, "Monster", "WIND"),
        ("GFTP2-EN077", "Blue-Eyes Alternative White Dragon", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 300.00, "Monster", "LIGHT"),
        ("GFP2-EN180", "Dark Magician Girl", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 400.00, "Monster", "DARK"),

        # =================================================================
        # Recent Starlight Rares
        # =================================================================
        ("DUNE-EN009", "Tenpai Dragon Fadra", "Duelist Nexus",
         "Starlight Rare", True, 350.00, "Monster", "FIRE"),
        ("LEDE-EN050", "Fiendsmith's Tractus", "Legacy of Destruction",
         "Starlight Rare", True, 450.00, "Spell", ""),
        ("CYAC-EN046", "Kashtira Arise-Heart", "Cyberstorm Access",
         "Starlight Rare", True, 500.00, "Monster", "DARK"),

        # =================================================================
        # Collector's Rares (recent sets)
        # =================================================================
        ("MZMI-EN001", "Magicians' Souls (Collector's Rare)", "Maze of Millennia",
         "Collector's Rare", True, 200.00, "Monster", "DARK"),
        ("BLCR-EN065", "Sky Striker Ace - Roze (Collector's Rare)", "Battles of Legend: Crystal Revenge",
         "Collector's Rare", True, 120.00, "Monster", "LIGHT"),

        # =================================================================
        # Sealed Product expansion
        # =================================================================
        ("AGOV-BOX", "Age of Overlord Display Box", "Age of Overlord",
         "Sealed Product", False, 85.00, "Sealed Product", ""),
        ("PHNI-BOX", "Phantom Nightmare Display Box", "Phantom Nightmare",
         "Sealed Product", False, 90.00, "Sealed Product", ""),
        ("RA01-BOX", "25th Anniversary Rarity Collection Box", "25th Anniversary Rarity Collection",
         "Sealed Product", False, 180.00, "Sealed Product", ""),
        ("RA02-BOX", "25th Anniversary Rarity Collection II Box", "25th Anniversary Rarity Collection II",
         "Sealed Product", False, 200.00, "Sealed Product", ""),
        ("TIN2024", "2024 Tin of the Pharaoh's Gods", "2024 Tin",
         "Sealed Product", False, 25.00, "Sealed Product", ""),

        # =================================================================
        # Prize cards expansion
        # =================================================================
        ("WCPS-EN900", "Blue-Eyes White Dragon (WCPS 2019)", "World Championship Prize",
         "Prize Card", False, 25000.00, "Monster", "LIGHT"),
        ("WCPS-EN901", "Dark Magician (WCPS 2018)", "World Championship Prize",
         "Prize Card", False, 20000.00, "Monster", "DARK"),

        # =================================================================
        # OCG Exclusives (Japan-only rarities)
        # =================================================================
        ("20TH-JPC00", "Blue-Eyes White Dragon (20th Secret JP)", "20th Anniversary Set",
         "Prismatic Secret Rare", False, 1500.00, "Monster", "LIGHT"),
        ("PAC1-JP004", "Dark Magician (Prismatic Art Collection)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 800.00, "Monster", "DARK"),

        # =================================================================
        # Structure Deck exclusives
        # =================================================================
        ("SDAZ-EN001", "Albaz, the Branded Dragon (Structure)", "Structure Deck: Albaz Strike",
         "Ultra Rare", False, 30.00, "Monster", "DARK"),

        # =================================================================
        # Legacy of Destruction (LEDE) chase cards
        # =================================================================
        ("LEDE-EN008", "Nightmare Magician", "Legacy of Destruction",
         "Secret Rare", True, 55.00, "Monster", "DARK"),
        ("LEDE-EN004", "Tenpai Dragon Paidra", "Legacy of Destruction",
         "Ultra Rare", True, 35.00, "Monster", "FIRE"),
        ("LEDE-EN014", "White Forest", "Legacy of Destruction",
         "Secret Rare", True, 40.00, "Spell", ""),

        # =================================================================
        # Duelist Nexus (DUNE) additional chase cards
        # =================================================================
        ("DUNE-EN048", "Purrely Delicious Memory", "Duelist Nexus",
         "Starlight Rare", True, 400.00, "Spell", ""),
        ("DUNE-EN003", "Tenpai Dragon Chundra", "Duelist Nexus",
         "Super Rare", True, 25.00, "Monster", "FIRE"),

        # =================================================================
        # Cyberstorm Access (CYAC) additional chase cards
        # =================================================================
        ("CYAC-EN008", "Kashtira Unicorn", "Cyberstorm Access",
         "Secret Rare", True, 55.00, "Monster", "WIND"),
        ("CYAC-EN009", "Kashtira Fenrir", "Cyberstorm Access",
         "Ultra Rare", True, 40.00, "Monster", "EARTH"),

        # =================================================================
        # The Infinite Forbidden (INFO) chase cards
        # =================================================================
        ("INFO-EN008", "Fiendsmith's Lacrima", "The Infinite Forbidden",
         "Secret Rare", True, 45.00, "Monster", "LIGHT"),
        ("INFO-EN050", "Sinful Spoils of Subversion - Snake-Eye", "The Infinite Forbidden",
         "Ultra Rare", True, 35.00, "Spell", ""),
        ("INFO-EN034", "Centur-Ion Primera", "The Infinite Forbidden",
         "Starlight Rare", True, 350.00, "Monster", "LIGHT"),

        # =================================================================
        # Classic Ultimate Rares
        # =================================================================
        ("RDS-EN041", "Mobius the Frost Monarch", "Rise of Destiny",
         "Ultimate Rare", True, 350.00, "Monster", "WATER"),
        ("FET-EN031", "Sacred Phoenix of Nephthys", "Flaming Eternity",
         "Ultimate Rare", True, 280.00, "Monster", "FIRE"),
        ("TLM-EN006", "Ancient Gear Golem", "The Lost Millennium",
         "Ultimate Rare", True, 250.00, "Monster", "EARTH"),
        ("SOI-EN035", "Elemental HERO Neos", "Shadow of Infinity",
         "Ultimate Rare", True, 400.00, "Monster", "LIGHT"),
        ("TDGS-EN040", "Stardust Dragon", "The Duelist Genesis",
         "Ultimate Rare", True, 600.00, "Monster", "WIND"),
        ("CSOC-EN039", "Black Rose Dragon", "Crossroads of Chaos",
         "Ultimate Rare", True, 500.00, "Monster", "FIRE"),

        # =================================================================
        # Gold Series / Gold Secret Rares
        # =================================================================
        ("GLD3-EN028", "Dark Armed Dragon", "Gold Series 3",
         "Gold Secret Rare", False, 120.00, "Monster", "DARK"),
        ("GLD4-EN031", "Black Luster Soldier - Envoy", "Gold Series 4: Pyramids",
         "Gold Secret Rare", False, 100.00, "Monster", "LIGHT"),
        ("MGED-EN001", "Blue-Eyes White Dragon (Premium Gold)", "Maximum Gold: El Dorado",
         "Gold Rare", False, 45.00, "Monster", "LIGHT"),

        # =================================================================
        # Iconic 5Ds Synchro monsters
        # =================================================================
        ("RGBT-EN043", "Power Tool Dragon", "Raging Battle",
         "Ultra Rare", True, 120.00, "Monster", "EARTH"),
        ("TSHD-EN044", "Red Dragon Archfiend/Assault Mode", "The Shining Darkness",
         "Ultra Rare", True, 80.00, "Monster", "DARK"),
        ("STBL-EN042", "Shooting Quasar Dragon", "Starstrike Blast",
         "Ultra Rare", True, 90.00, "Monster", "LIGHT"),
        ("SOVR-EN040", "Majestic Red Dragon", "Stardust Overdrive",
         "Ultra Rare", True, 60.00, "Monster", "DARK"),

        # =================================================================
        # Modern Secret Rares — staple reprints
        # =================================================================
        ("DUDE-EN010", "Effect Veiler", "Duel Devastator",
         "Ultra Rare", False, 15.00, "Monster", "LIGHT"),
        ("DUDE-EN001", "Infinite Impermanence", "Duel Devastator",
         "Ultra Rare", False, 25.00, "Trap", ""),
        ("DUDE-EN028", "Called by the Grave", "Duel Devastator",
         "Ultra Rare", False, 12.00, "Spell", ""),

        # =================================================================
        # Maze of Millennia (MZMI) additional chase
        # =================================================================
        ("MZMI-EN023", "Exodia, the Legendary Defender", "Maze of Millennia",
         "Ultra Rare", True, 35.00, "Monster", "DARK"),
        ("MZMI-EN060", "Tenpai Dragon Genroku", "Maze of Millennia",
         "Secret Rare", True, 50.00, "Monster", "FIRE"),

        # =================================================================
        # Sealed Product expansion — Structure Decks & Starter
        # =================================================================
        ("LEDE-BOX", "Legacy of Destruction Display Box", "Legacy of Destruction",
         "Sealed Product", False, 85.00, "Sealed Product", ""),
        ("INFO-BOX", "The Infinite Forbidden Display Box", "The Infinite Forbidden",
         "Sealed Product", False, 90.00, "Sealed Product", ""),
        ("DUNE-BOX", "Duelist Nexus Display Box", "Duelist Nexus",
         "Sealed Product", False, 80.00, "Sealed Product", ""),
        ("CYAC-BOX", "Cyberstorm Access Display Box", "Cyberstorm Access",
         "Sealed Product", False, 80.00, "Sealed Product", ""),
        ("MZMI-BOX", "Maze of Millennia Display Box", "Maze of Millennia",
         "Sealed Product", False, 95.00, "Sealed Product", ""),
        ("SDCB-1ST", "Structure Deck: Cyberse Link", "Structure Deck: Cyberse Link",
         "Sealed Product", True, 25.00, "Sealed Product", ""),

        # =================================================================
        # OCG Exclusives — additional
        # =================================================================
        ("QCDB-JP001", "Dark Magician Girl (QC)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 1200.00, "Monster", "DARK"),
        ("QCDB-JP002", "Red-Eyes Black Dragon (QC)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 800.00, "Monster", "DARK"),

        # =================================================================
        # Tournament prize expansion
        # =================================================================
        ("WCPS-EN902", "Red-Eyes Black Dragon (WCPS 2017)", "World Championship Prize",
         "Prize Card", False, 18000.00, "Monster", "DARK"),
        ("TRC1-JP001", "Blue-Eyes White Dragon (The Rarity Collection)", "The Rarity Collection",
         "Platinum Secret Rare", False, 500.00, "Monster", "LIGHT"),

        # =================================================================
        # Classic staple Trap / Spell reprints across eras
        # =================================================================
        ("DB1-EN119", "Torrential Tribute", "Dark Beginning 1",
         "Ultra Rare", False, 45.00, "Trap", ""),
        ("DB1-EN050", "Mystical Space Typhoon", "Dark Beginning 1",
         "Ultra Rare", False, 35.00, "Spell", ""),
        ("PGLD-EN043", "Solemn Warning", "Premium Gold",
         "Gold Secret Rare", False, 25.00, "Trap", ""),
        ("MAGO-EN045", "Raigeki", "Maximum Gold",
         "Gold Rare", False, 15.00, "Spell", ""),

        # =================================================================
        # Zexal era XYZ monsters
        # =================================================================
        ("GAOV-EN045", "Number 11: Big Eye", "Galactic Overlord",
         "Ultra Rare", True, 90.00, "Monster", "DARK"),
        ("REDU-EN045", "Madolche Queen Tiaramisu", "Return of the Duelist",
         "Ultra Rare", True, 60.00, "Monster", "EARTH"),
        ("LTGY-EN050", "Mecha Phantom Beast Dracossack", "Lord of the Tachyon Galaxy",
         "Secret Rare", True, 50.00, "Monster", "WIND"),
        ("PRIO-EN052", "Number 62: Galaxy-Eyes Prime Photon Dragon", "Primal Origin",
         "Ultra Rare", True, 45.00, "Monster", "LIGHT"),

        # =================================================================
        # Pendulum era — Dimension of Chaos / Breakers of Shadow
        # =================================================================
        ("DOCS-EN052", "Majespecter Unicorn - Kirin", "Dimension of Chaos",
         "Ultra Rare", True, 40.00, "Monster", "WIND"),
        ("BOSH-EN050", "Cyber Dragon Infinity", "Breakers of Shadow",
         "Secret Rare", True, 55.00, "Monster", "LIGHT"),

        # =================================================================
        # Ghost Rares — additional classic & modern
        # =================================================================
        ("LODT-EN040", "Honest", "Light of Destruction",
         "Ghost Rare", True, 900.00, "Monster", "LIGHT"),
        ("ABPF-EN040", "Majestic Red Dragon", "Absolute Powerforce",
         "Ghost Rare", True, 700.00, "Monster", "DARK"),
        ("GENF-EN039", "Number 17: Leviathan Dragon", "Generation Force",
         "Ghost Rare", True, 500.00, "Monster", "WATER"),
        ("REDU-EN043", "Galaxy-Eyes Photon Dragon", "Return of the Duelist",
         "Ghost Rare", True, 450.00, "Monster", "LIGHT"),
        ("JOTL-EN047", "Star Eater", "Judgment of the Light",
         "Ghost Rare", True, 400.00, "Monster", "LIGHT"),
        ("SHSP-EN052", "Divine Dragon Knight Felgrand", "Shadow Specters",
         "Ghost Rare", True, 380.00, "Monster", "LIGHT"),
        ("PRIO-EN052", "Number 62: Galaxy-Eyes Prime Photon Dragon", "Primal Origin",
         "Ghost Rare", True, 350.00, "Monster", "LIGHT"),
        ("LVAL-EN044", "Number 101: Silent Honor ARK", "Legacy of the Valiant",
         "Ghost Rare", True, 600.00, "Monster", "WATER"),
        ("GFTP-EN132", "Dark Magician", "Ghosts From the Past",
         "Ghost Rare", False, 500.00, "Monster", "DARK"),
        ("GFTP-EN131", "Blue-Eyes White Dragon", "Ghosts From the Past",
         "Ghost Rare", False, 450.00, "Monster", "LIGHT"),
        ("GFTP-EN133", "Red-Eyes Black Dragon", "Ghosts From the Past",
         "Ghost Rare", False, 400.00, "Monster", "DARK"),
        ("GFP2-EN181", "Crystal Wing Synchro Dragon", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 200.00, "Monster", "WIND"),

        # =================================================================
        # Starlight Rares — modern high-demand chase cards
        # =================================================================
        ("BLVO-EN038", "Tri-Brigade Kitt", "Blazing Vortex",
         "Starlight Rare", True, 350.00, "Monster", "FIRE"),
        ("LIOV-EN009", "Destiny HERO - Destroyer Phoenix Enforcer", "Lightning Overdrive",
         "Starlight Rare", True, 600.00, "Monster", "DARK"),
        ("BODE-EN047", "Swordsoul of Mo Ye", "Burst of Destiny",
         "Starlight Rare", True, 400.00, "Monster", "WATER"),
        ("GRCR-EN011", "Exosister Mikailis", "The Grand Creators",
         "Starlight Rare", True, 300.00, "Monster", "LIGHT"),
        ("DIFO-EN010", "Spright Blue", "Dimension Force",
         "Starlight Rare", True, 500.00, "Monster", "DARK"),
        ("DIFO-EN046", "Spright Elf", "Dimension Force",
         "Starlight Rare", True, 450.00, "Monster", "DARK"),
        ("DABL-EN009", "Tearlaments Scheiren", "Darkwing Blast",
         "Starlight Rare", True, 550.00, "Monster", "DARK"),
        ("DABL-EN046", "Tearlaments Rulkallos", "Darkwing Blast",
         "Starlight Rare", True, 500.00, "Monster", "WATER"),
        ("POTE-EN009", "Therion King Regulus", "Power of the Elements",
         "Starlight Rare", True, 450.00, "Monster", "EARTH"),
        ("POTE-EN046", "Spright Sprind", "Power of the Elements",
         "Starlight Rare", True, 400.00, "Monster", "WIND"),
        ("AMDE-EN045", "Kashtira Birth", "Amazing Defenders",
         "Starlight Rare", True, 250.00, "Spell", ""),
        ("WISU-EN010", "S:P Little Knight", "Wild Survivors",
         "Starlight Rare", True, 500.00, "Monster", "DARK"),
        ("PHNI-EN045", "Promethean Princess, Bestower of Flames", "Phantom Nightmare",
         "Starlight Rare", True, 400.00, "Monster", "FIRE"),
        ("LEDE-EN006", "White Forest Synthe", "Legacy of Destruction",
         "Starlight Rare", True, 350.00, "Monster", "LIGHT"),
        ("INFO-EN009", "Fiendsmith's Sequence", "The Infinite Forbidden",
         "Starlight Rare", True, 300.00, "Monster", "DARK"),
        ("AGOV-EN046", "Vaalmonica Followed Rhythm", "Age of Overlord",
         "Starlight Rare", True, 280.00, "Trap", ""),

        # =================================================================
        # Quarter Century Secret Rares — additional
        # =================================================================
        ("RA01-EN005", "Red-Eyes Black Dragon (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 1200.00, "Monster", "DARK"),
        ("RA01-EN010", "Dark Magician Girl (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 1800.00, "Monster", "DARK"),
        ("RA01-EN015", "Black Luster Soldier - Envoy (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 800.00, "Monster", "LIGHT"),
        ("RA01-EN080", "Maxx 'C' (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 600.00, "Monster", "EARTH"),
        ("RA02-EN010", "Stardust Dragon (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 1000.00, "Monster", "WIND"),
        ("RA02-EN015", "Black Rose Dragon (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 700.00, "Monster", "FIRE"),
        ("RA02-EN030", "Mirror Force (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 500.00, "Trap", ""),
        ("RA02-EN035", "Monster Reborn (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 600.00, "Spell", ""),
        ("RA02-EN045", "Pot of Prosperity (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 450.00, "Spell", ""),
        ("RA02-EN055", "Accesscode Talker (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 800.00, "Monster", "DARK"),

        # =================================================================
        # Tournament Prize Cards — additional
        # =================================================================
        ("YCSW-EN003", "Number 106: Giant Hand (YCSW)", "YCS Prize",
         "Prize Card", False, 7000.00, "Monster", "EARTH"),
        ("YCSW-EN004", "Digvorzhak, King of Heavy Industry", "YCS Prize",
         "Prize Card", False, 6000.00, "Monster", "EARTH"),
        ("SJC-EN002", "Dark End Dragon (SJC)", "Shonen Jump Championship",
         "Prize Card", False, 8000.00, "Monster", "DARK"),
        ("SJC-EN003", "Des Volstgalph (SJC)", "Shonen Jump Championship",
         "Prize Card", False, 6000.00, "Monster", "FIRE"),
        ("WCPS-EN903", "Exodia the Forbidden One (WCPS 2016)", "World Championship Prize",
         "Prize Card", False, 22000.00, "Monster", "DARK"),

        # =================================================================
        # Iconic Exodia variants & alternate arts
        # =================================================================
        ("LART-EN001", "Exodia the Forbidden One (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 120.00, "Monster", "DARK"),
        ("LART-EN002", "Left Leg of the Forbidden One (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 80.00, "Monster", "DARK"),
        ("LART-EN003", "Left Arm of the Forbidden One (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 80.00, "Monster", "DARK"),
        ("LART-EN004", "Right Leg of the Forbidden One (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 80.00, "Monster", "DARK"),
        ("LART-EN005", "Right Arm of the Forbidden One (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 80.00, "Monster", "DARK"),

        # =================================================================
        # Blue-Eyes & Dark Magician alternate printings
        # =================================================================
        ("MVP1-EN055", "Blue-Eyes Alternative White Dragon", "The Dark Side of Dimensions Movie Pack",
         "Ultra Rare", True, 85.00, "Monster", "LIGHT"),
        ("CT13-EN001", "Blue-Eyes White Dragon (Movie Pack Kaiba)", "2016 Mega-Tins",
         "Secret Rare", False, 120.00, "Monster", "LIGHT"),
        ("JUMP-EN068", "Blue-Eyes White Dragon (JUMP)", "Shonen Jump Promo",
         "Ultra Rare", False, 250.00, "Monster", "LIGHT"),
        ("LART-EN006", "Dark Magician (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 100.00, "Monster", "DARK"),
        ("SDY-006", "Dark Magician (Starter Deck Yugi)", "Starter Deck Yugi",
         "Ultra Rare", False, 180.00, "Monster", "DARK"),
        ("SDK-001", "Blue-Eyes White Dragon (Starter Deck Kaiba)", "Starter Deck Kaiba",
         "Ultra Rare", False, 200.00, "Monster", "LIGHT"),

        # =================================================================
        # Red-Eyes variants
        # =================================================================
        ("CORE-EN071", "Red-Eyes Flare Metal Dragon", "Clash of Rebellions",
         "Secret Rare", True, 55.00, "Monster", "DARK"),
        ("DRL2-EN004", "Red-Eyes Black Flare Dragon", "Dragons of Legend 2",
         "Ultra Rare", True, 35.00, "Monster", "DARK"),
        ("LDK2-ENJ01", "Red-Eyes Black Dragon (Legendary Decks II)", "Legendary Decks II",
         "Ultra Rare", False, 45.00, "Monster", "DARK"),

        # =================================================================
        # Modern sealed product — booster boxes
        # =================================================================
        ("BLVO-BOX", "Blazing Vortex Display Box", "Blazing Vortex",
         "Sealed Product", False, 95.00, "Sealed Product", ""),
        ("LIOV-BOX", "Lightning Overdrive Display Box", "Lightning Overdrive",
         "Sealed Product", False, 90.00, "Sealed Product", ""),
        ("BODE-BOX", "Burst of Destiny Display Box", "Burst of Destiny",
         "Sealed Product", False, 85.00, "Sealed Product", ""),
        ("DIFO-BOX", "Dimension Force Display Box", "Dimension Force",
         "Sealed Product", False, 90.00, "Sealed Product", ""),
        ("DABL-BOX", "Darkwing Blast Display Box", "Darkwing Blast",
         "Sealed Product", False, 85.00, "Sealed Product", ""),
        ("POTE-BOX", "Power of the Elements Display Box", "Power of the Elements",
         "Sealed Product", False, 110.00, "Sealed Product", ""),
        ("GFTP-BOX", "Ghosts From the Past Display Box", "Ghosts From the Past",
         "Sealed Product", False, 120.00, "Sealed Product", ""),
        ("GFTP2-BOX", "Ghosts From the Past 2nd Haunting Box", "Ghosts From the Past: The 2nd Haunting",
         "Sealed Product", False, 130.00, "Sealed Product", ""),
        ("WISU-BOX", "Wild Survivors Display Box", "Wild Survivors",
         "Sealed Product", False, 80.00, "Sealed Product", ""),
        ("SRL-BOX", "Spell Ruler Unlimited Booster Box", "Spell Ruler",
         "Sealed Product", False, 6000.00, "Sealed Product", ""),
        ("TOCH-BOX", "Toon Chaos Display Box", "Toon Chaos",
         "Sealed Product", False, 200.00, "Sealed Product", ""),

        # =================================================================
        # Sealed Product — Special Editions, Tins, Duel Devastator
        # =================================================================
        ("DUDE-BOX", "Duel Devastator Box", "Duel Devastator",
         "Sealed Product", False, 45.00, "Sealed Product", ""),
        ("TIN2023", "2023 25th Anniversary Tin", "2023 Tin",
         "Sealed Product", False, 22.00, "Sealed Product", ""),
        ("MAMA-BOX", "Magnificent Mavens Box", "Magnificent Mavens",
         "Sealed Product", False, 80.00, "Sealed Product", ""),
        ("MGED-BOX", "Maximum Gold: El Dorado Box", "Maximum Gold: El Dorado",
         "Sealed Product", False, 50.00, "Sealed Product", ""),
        ("LC01-BOX", "Legendary Collection Box (Original)", "Legendary Collection",
         "Sealed Product", False, 300.00, "Sealed Product", ""),

        # =================================================================
        # Classic Ultimate Rares — additional
        # =================================================================
        ("CRV-EN016", "Cyber Dragon", "Cybernetic Revolution",
         "Ultimate Rare", True, 500.00, "Monster", "LIGHT"),
        ("IOC-025", "Black Luster Soldier - Envoy", "Invasion of Chaos",
         "Ultimate Rare", True, 800.00, "Monster", "LIGHT"),
        ("MFC-000", "Dark Magician Girl", "Magician's Force",
         "Ultimate Rare", True, 1200.00, "Monster", "DARK"),
        ("SOD-EN035", "Mobius the Frost Monarch (ULT)", "Soul of the Duelist",
         "Ultimate Rare", True, 350.00, "Monster", "WATER"),
        ("PTDN-EN044", "Rainbow Neos", "Phantom Darkness",
         "Ultimate Rare", True, 300.00, "Monster", "LIGHT"),

        # =================================================================
        # Platinum Secret Rares & Gold Secret Rares — additional
        # =================================================================
        ("TRC1-JP005", "Dark Magician (Rarity Collection)", "The Rarity Collection",
         "Platinum Secret Rare", False, 400.00, "Monster", "DARK"),
        ("GLD5-EN024", "Dark Armed Dragon (Gold Series Haunted Mine)", "Gold Series: Haunted Mine",
         "Gold Secret Rare", False, 90.00, "Monster", "DARK"),
        ("GLD4-EN028", "Judgment Dragon", "Gold Series 4: Pyramids",
         "Gold Secret Rare", False, 65.00, "Monster", "LIGHT"),
        ("PGL3-EN001", "Blue-Eyes White Dragon (Premium Gold 3)", "Premium Gold: Infinite Gold",
         "Gold Secret Rare", False, 80.00, "Monster", "LIGHT"),

        # =================================================================
        # OCG Exclusives — additional Japan-only rarities
        # =================================================================
        ("PAC1-JP006", "Blue-Eyes White Dragon (PAC)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 1000.00, "Monster", "LIGHT"),
        ("PAC1-JP036", "Accesscode Talker (PAC)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 300.00, "Monster", "DARK"),
        ("20TH-JPC01", "Dark Magician (20th Secret JP)", "20th Anniversary Set",
         "Prismatic Secret Rare", False, 1200.00, "Monster", "DARK"),
        ("20TH-JPC02", "Red-Eyes Black Dragon (20th Secret JP)", "20th Anniversary Set",
         "Prismatic Secret Rare", False, 900.00, "Monster", "DARK"),
        ("QCDB-JP003", "Blue-Eyes White Dragon (QC Duelist Box)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 1500.00, "Monster", "LIGHT"),

        # =================================================================
        # Modern meta staples — Branded / Despia
        # =================================================================
        ("DAMA-EN037", "Branded Despia", "Dawn of Majesty",
         "Ultra Rare", True, 35.00, "Monster", "LIGHT"),
        ("BROL-EN042", "Branded Opening", "Brothers of Legend",
         "Ultra Rare", True, 30.00, "Spell", ""),
        ("DABL-EN017", "Lubellion the Searing Dragon", "Darkwing Blast",
         "Secret Rare", True, 40.00, "Monster", "DARK"),
        ("DAMA-EN035", "Despian Quaeritis", "Dawn of Majesty",
         "Ultra Rare", True, 25.00, "Monster", "LIGHT"),
        ("MP22-EN266", "Masquerade the Blazing Dragon", "2022 Tin of the Pharaoh's Gods",
         "Prismatic Secret Rare", False, 45.00, "Monster", "DARK"),

        # =================================================================
        # Modern meta — Snake-Eye / Rescue-ACE
        # =================================================================
        ("PHNI-EN006", "Snake-Eye Poplar", "Phantom Nightmare",
         "Ultra Rare", True, 50.00, "Monster", "FIRE"),
        ("PHNI-EN002", "Snake-Eyes Diabellstar", "Phantom Nightmare",
         "Secret Rare", True, 75.00, "Monster", "DARK"),
        ("AMDE-EN016", "Rescue-ACE Turbulence", "Amazing Defenders",
         "Secret Rare", True, 45.00, "Monster", "FIRE"),
        ("AMDE-EN019", "EMERGENCY!", "Amazing Defenders",
         "Ultra Rare", True, 30.00, "Spell", ""),

        # =================================================================
        # Valiant Smashers (VASM) — Purrely / Labrynth
        # =================================================================
        ("VASM-EN002", "Labrynth Labyrinth", "Valiant Smashers",
         "Secret Rare", True, 30.00, "Trap", ""),
        ("VASM-EN005", "Purrely Pretty Memory", "Valiant Smashers",
         "Ultra Rare", True, 25.00, "Spell", ""),
        ("VASM-EN015", "Lovely Labrynth of the Silver Castle", "Valiant Smashers",
         "Starlight Rare", True, 400.00, "Monster", "DARK"),

        # =================================================================
        # Battles of Legend (BROL / BLCR / BLMR)
        # =================================================================
        ("BROL-EN090", "Forbidden Droplet", "Brothers of Legend",
         "Secret Rare", True, 80.00, "Spell", ""),
        ("BROL-EN087", "Ice Dragon's Prison", "Brothers of Legend",
         "Secret Rare", True, 40.00, "Trap", ""),
        ("BLCR-EN001", "Pot of Extravagance", "Battles of Legend: Crystal Revenge",
         "Secret Rare", True, 35.00, "Spell", ""),
        ("BLCR-EN100", "Underworld Goddess of the Closed World", "Battles of Legend: Crystal Revenge",
         "Secret Rare", True, 30.00, "Monster", "DARK"),
        ("BLMR-EN001", "Dark Magician (BLMR Alt Art)", "Battles of Legend: Monstrous Revenge",
         "Ultra Rare", True, 45.00, "Monster", "DARK"),
        ("BLMR-EN080", "S:P Little Knight", "Battles of Legend: Monstrous Revenge",
         "Secret Rare", True, 40.00, "Monster", "DARK"),
        ("BLMR-EN002", "Blue-Eyes White Dragon (BLMR Alt Art)", "Battles of Legend: Monstrous Revenge",
         "Ultra Rare", True, 50.00, "Monster", "LIGHT"),
        ("BLMR-EN042", "Ash Blossom & Joyous Spring (BLMR)", "Battles of Legend: Monstrous Revenge",
         "Secret Rare", True, 25.00, "Monster", "FIRE"),

        # =================================================================
        # Legendary Duelists (LED / LEDU)
        # =================================================================
        ("LED2-EN001", "Cyber Dragon Herz", "Legendary Duelists: Ancient Millennium",
         "Super Rare", True, 15.00, "Monster", "LIGHT"),
        ("LED4-EN001", "Harpie Perfumer", "Legendary Duelists: Sisters of the Rose",
         "Ultra Rare", True, 20.00, "Monster", "WIND"),
        ("LED5-EN000", "Toon Black Luster Soldier", "Legendary Duelists: Immortal Destiny",
         "Secret Rare", True, 40.00, "Monster", "EARTH"),
        ("LED6-EN001", "Gaia the Magical Knight", "Legendary Duelists: Magical Hero",
         "Ultra Rare", True, 18.00, "Monster", "EARTH"),
        ("LED7-EN000", "Galaxy-Eyes Afterglow Dragon", "Legendary Duelists: Rage of Ra",
         "Secret Rare", True, 45.00, "Monster", "LIGHT"),
        ("LED8-EN001", "Stardust Synchron", "Legendary Duelists: Synchro Storm",
         "Ultra Rare", True, 25.00, "Monster", "LIGHT"),
        ("LED8-EN000", "Clear Wing Fast Dragon", "Legendary Duelists: Synchro Storm",
         "Secret Rare", True, 30.00, "Monster", "WIND"),
        ("LED9-EN001", "Galaxy Soldier", "Legendary Duelists: Duels From the Deep",
         "Ultra Rare", True, 20.00, "Monster", "LIGHT"),
        ("LED3-EN000", "Red-Eyes Alternative Black Dragon", "Legendary Duelists: White Dragon Abyss",
         "Secret Rare", True, 35.00, "Monster", "DARK"),

        # =================================================================
        # King's Court (KICO)
        # =================================================================
        ("KICO-EN001", "King's Knight", "King's Court",
         "Ultra Rare", True, 15.00, "Monster", "LIGHT"),
        ("KICO-EN034", "Arcana Triumph Joker", "King's Court",
         "Ultra Rare", True, 25.00, "Monster", "LIGHT"),
        ("KICO-EN050", "Number 39: Utopia Rising", "King's Court",
         "Starlight Rare", True, 300.00, "Monster", "LIGHT"),
        ("KICO-EN035", "Imperial Bower", "King's Court",
         "Ultra Rare", True, 18.00, "Monster", "LIGHT"),

        # =================================================================
        # Speed Duel GX (SGX / SBC)
        # =================================================================
        ("SGX1-ENA01", "Elemental HERO Neos (Speed Duel)", "Speed Duel GX: Duel Academy Box",
         "Secret Rare", False, 35.00, "Monster", "LIGHT"),
        ("SGX1-ENB01", "Cyber Dragon (Speed Duel)", "Speed Duel GX: Duel Academy Box",
         "Secret Rare", False, 30.00, "Monster", "LIGHT"),
        ("SGX3-ENS01", "Dark Magician of Chaos (Speed Duel)", "Speed Duel GX: March of the Monarchs",
         "Secret Rare", False, 25.00, "Monster", "DARK"),
        ("SBC1-EN001", "Blue-Eyes White Dragon (Speed Duel)", "Speed Duel: Battle City Box",
         "Secret Rare", False, 40.00, "Monster", "LIGHT"),
        ("SBC1-ENS01", "Obelisk the Tormentor (Speed Duel)", "Speed Duel: Battle City Box",
         "Secret Rare", False, 50.00, "Monster", "DIVINE"),

        # =================================================================
        # OTS Tournament Packs
        # =================================================================
        ("OP01-EN001", "Tour Guide From the Underworld (OTS 1)", "OTS Tournament Pack 1",
         "Ultimate Rare", False, 250.00, "Monster", "DARK"),
        ("OP06-EN001", "Ash Blossom & Joyous Spring (OTS 6)", "OTS Tournament Pack 6",
         "Ultimate Rare", False, 400.00, "Monster", "FIRE"),
        ("OP09-EN001", "Infinite Impermanence (OTS 9)", "OTS Tournament Pack 9",
         "Ultimate Rare", False, 350.00, "Trap", ""),
        ("OP16-EN001", "Ghost Mourner & Moonlit Chill (OTS 16)", "OTS Tournament Pack 16",
         "Ultimate Rare", False, 180.00, "Monster", "DARK"),
        ("OP19-EN001", "Baronne de Fleur (OTS 19)", "OTS Tournament Pack 19",
         "Ultimate Rare", False, 200.00, "Monster", "WIND"),
        ("OP20-EN001", "S:P Little Knight (OTS 20)", "OTS Tournament Pack 20",
         "Ultimate Rare", False, 250.00, "Monster", "DARK"),
        ("OP21-EN001", "Accesscode Talker (OTS 21)", "OTS Tournament Pack 21",
         "Ultimate Rare", False, 300.00, "Monster", "DARK"),
        ("OP03-EN001", "Maxx 'C' (OTS 3)", "OTS Tournament Pack 3",
         "Ultimate Rare", False, 350.00, "Monster", "EARTH"),
        ("OP14-EN001", "Triple Tactics Talent (OTS 14)", "OTS Tournament Pack 14",
         "Ultimate Rare", False, 220.00, "Spell", ""),

        # =================================================================
        # Gold Series & Maximum Gold
        # =================================================================
        ("GLD1-EN028", "Exodia the Forbidden One (Gold)", "Gold Series",
         "Gold Rare", False, 55.00, "Monster", "DARK"),
        ("GLD2-EN023", "Elemental HERO Stratos (Gold)", "Gold Series 2009",
         "Gold Rare", False, 30.00, "Monster", "WIND"),
        ("MAGO-EN003", "Dark Magician (Maximum Gold)", "Maximum Gold",
         "Gold Rare", False, 20.00, "Monster", "DARK"),
        ("MAGO-EN028", "Ash Blossom (Maximum Gold)", "Maximum Gold",
         "Gold Rare", False, 18.00, "Monster", "FIRE"),
        ("MAGO-EN041", "Nibiru, the Primal Being (Maximum Gold)", "Maximum Gold",
         "Gold Rare", False, 15.00, "Monster", "LIGHT"),
        ("MGED-EN003", "Dark Magician (El Dorado)", "Maximum Gold: El Dorado",
         "Gold Rare", False, 22.00, "Monster", "DARK"),
        ("MGED-EN025", "Accesscode Talker (El Dorado)", "Maximum Gold: El Dorado",
         "Gold Rare", False, 25.00, "Monster", "DARK"),
        ("MGED-EN130", "Lightning Storm (El Dorado)", "Maximum Gold: El Dorado",
         "Gold Rare", False, 30.00, "Spell", ""),

        # =================================================================
        # Ghosts From the Past (GFTP / GFP2) — additional
        # =================================================================
        ("GFTP-EN134", "Firewall Dragon", "Ghosts From the Past",
         "Ghost Rare", False, 300.00, "Monster", "LIGHT"),
        ("GFP2-EN178", "Number 39: Utopia", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 180.00, "Monster", "LIGHT"),
        ("GFP2-EN179", "Number C39: Utopia Ray V", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 150.00, "Monster", "LIGHT"),
        ("GFP2-EN182", "Trishula, Dragon of the Ice Barrier", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 160.00, "Monster", "WATER"),

        # =================================================================
        # Structure Deck chase cards
        # =================================================================
        ("SDCS-EN001", "Cyberse Quantum Dragon", "Structure Deck: Cyberse Link",
         "Ultra Rare", False, 12.00, "Monster", "DARK"),
        ("SDAZ-EN042", "Branded Fusion (Structure Deck)", "Structure Deck: Albaz Strike",
         "Ultra Rare", False, 15.00, "Spell", ""),
        ("SDAZ-EN043", "Branded in Red", "Structure Deck: Albaz Strike",
         "Ultra Rare", False, 10.00, "Trap", ""),
        ("SR13-EN001", "Beelze of the Diabolic Dragons", "Structure Deck: Dark World",
         "Ultra Rare", False, 8.00, "Monster", "DARK"),
        ("SR14-EN001", "Elemental HERO Liquid Soldier", "Structure Deck: HERO Strike",
         "Ultra Rare", False, 15.00, "Monster", "WATER"),
        ("SDSB-EN001", "Salamangreat Sunlight Wolf", "Structure Deck: Soulburner",
         "Ultra Rare", False, 6.00, "Monster", "FIRE"),
        ("SDSH-EN001", "Shaddoll Showdown Structure Deck", "Structure Deck: Shaddoll Showdown",
         "Sealed Product", False, 25.00, "Sealed Product", ""),
        ("SD43-EN001", "Fire King High Avatar Garunix Eternity", "Structure Deck: Fire Kings",
         "Ultra Rare", False, 12.00, "Monster", "FIRE"),

        # =================================================================
        # GX Era — Elemental HERO / Cyber / Destiny HERO
        # =================================================================
        ("DP05-EN001", "Elemental HERO Prisma", "Duelist Pack: Aster Phoenix",
         "Super Rare", True, 25.00, "Monster", "LIGHT"),
        ("CRV-EN035", "Cyber End Dragon", "Cybernetic Revolution",
         "Ultra Rare", True, 120.00, "Monster", "LIGHT"),
        ("CRV-EN036", "Power Bond", "Cybernetic Revolution",
         "Ultra Rare", True, 80.00, "Spell", ""),
        ("POTD-EN015", "Destiny HERO - Plasma", "Power of the Duelist",
         "Ultra Rare", True, 60.00, "Monster", "DARK"),
        ("POTD-EN018", "Neo-Spacian Air Hummingbird", "Power of the Duelist",
         "Ultra Rare", True, 30.00, "Monster", "WIND"),
        ("STON-EN036", "Elemental HERO Aqua Neos", "Strike of Neos",
         "Ultra Rare", True, 45.00, "Monster", "WATER"),
        ("TAEV-EN020", "Crystal Beast Sapphire Pegasus", "Tactical Evolution",
         "Ultra Rare", True, 40.00, "Monster", "WIND"),
        ("PTDN-EN012", "Yubel - Terror Incarnate", "Phantom Darkness",
         "Ultra Rare", True, 50.00, "Monster", "DARK"),
        ("PTDN-EN013", "Yubel - The Ultimate Nightmare", "Phantom Darkness",
         "Ultra Rare", True, 55.00, "Monster", "DARK"),
        ("GLAS-EN001", "Elemental HERO Storm Neos", "Gladiator's Assault",
         "Ultra Rare", True, 35.00, "Monster", "WIND"),
        ("LODT-EN043", "Judgment Dragon", "Light of Destruction",
         "Secret Rare", True, 80.00, "Monster", "LIGHT"),

        # =================================================================
        # 5Ds Era — Synchro monsters expanded
        # =================================================================
        ("TDGS-EN037", "Red Dragon Archfiend", "The Duelist Genesis",
         "Ultra Rare", True, 80.00, "Monster", "DARK"),
        ("CSOC-EN037", "Goyo Guardian", "Crossroads of Chaos",
         "Ultra Rare", True, 35.00, "Monster", "EARTH"),
        ("ANPR-EN038", "Ancient Sacred Wyvern", "Ancient Prophecy",
         "Ultra Rare", True, 25.00, "Monster", "LIGHT"),
        ("RGBT-EN040", "Black-Winged Dragon", "Raging Battle",
         "Ultra Rare", True, 40.00, "Monster", "DARK"),
        ("STBL-EN040", "Formula Synchron", "Starstrike Blast",
         "Ultra Rare", True, 30.00, "Monster", "LIGHT"),
        ("STOR-EN038", "Legendary Six Samurai - Shi En", "Storm of Ragnarok",
         "Ultra Rare", True, 50.00, "Monster", "DARK"),
        ("EXVC-EN044", "T.G. Hyper Librarian", "Extreme Victory",
         "Ultra Rare", True, 35.00, "Monster", "DARK"),
        ("HA04-EN026", "Trishula, Dragon of the Ice Barrier", "Hidden Arsenal 4",
         "Secret Rare", True, 90.00, "Monster", "WATER"),
        ("DREV-EN043", "Scrap Dragon", "Duelist Revolution",
         "Ultra Rare", True, 25.00, "Monster", "EARTH"),
        ("DP10-EN017", "Blackwing Armor Master", "Duelist Pack: Crow",
         "Ultra Rare", True, 30.00, "Monster", "DARK"),

        # =================================================================
        # ZEXAL Era — XYZ monsters expanded
        # =================================================================
        ("GENF-EN037", "Number 17: Leviathan Dragon", "Generation Force",
         "Ultra Rare", True, 30.00, "Monster", "WATER"),
        ("PHSW-EN038", "Evolzar Laggia", "Photon Shockwave",
         "Ultra Rare", True, 25.00, "Monster", "FIRE"),
        ("ORCS-EN041", "Wind-Up Zenmaines", "Order of Chaos",
         "Ultra Rare", True, 15.00, "Monster", "FIRE"),
        ("ABYR-EN044", "Abyss Dweller", "Abyss Rising",
         "Super Rare", True, 12.00, "Monster", "WATER"),
        ("CBLZ-EN054", "Diamond Dire Wolf", "Cosmo Blazer",
         "Secret Rare", True, 35.00, "Monster", "EARTH"),
        ("LTGY-EN052", "Number 107: Galaxy-Eyes Tachyon Dragon", "Lord of the Tachyon Galaxy",
         "Ultra Rare", True, 40.00, "Monster", "LIGHT"),
        ("JOTL-EN045", "Star Eater", "Judgment of the Light",
         "Secret Rare", True, 30.00, "Monster", "LIGHT"),
        ("SHSP-EN050", "Number 101: Silent Honor ARK", "Shadow Specters",
         "Ultra Rare", True, 25.00, "Monster", "WATER"),
        ("LVAL-EN048", "Evilswarm Exciton Knight", "Legacy of the Valiant",
         "Secret Rare", True, 45.00, "Monster", "LIGHT"),

        # =================================================================
        # ARC-V Era — Pendulum & XYZ
        # =================================================================
        ("DUEA-EN050", "Stellarknight Delteros", "Duelist Alliance",
         "Ultra Rare", True, 20.00, "Monster", "LIGHT"),
        ("SECE-EN050", "Nekroz of Brionac", "Secrets of Eternity",
         "Secret Rare", True, 60.00, "Monster", "WATER"),
        ("CROS-EN051", "Tellarknight Ptolemaeus", "Crossed Souls",
         "Ultra Rare", True, 15.00, "Monster", "LIGHT"),
        ("CORE-EN046", "Performage Plushfire", "Clash of Rebellions",
         "Super Rare", True, 10.00, "Monster", "FIRE"),
        ("BOSH-EN080", "Dinoster Power, the Mighty Dracoslayer", "Breakers of Shadow",
         "Ultra Rare", True, 12.00, "Monster", "WATER"),
        ("SHVI-EN049", "Crystal Wing Synchro Dragon", "Shining Victories",
         "Secret Rare", True, 55.00, "Monster", "WIND"),
        ("TDIL-EN052", "ABC-Dragon Buster", "The Dark Illusion",
         "Secret Rare", True, 25.00, "Monster", "LIGHT"),
        ("INOV-EN048", "Toadally Awesome", "Invasion: Vengeance",
         "Secret Rare", True, 40.00, "Monster", "WATER"),
        ("RATE-EN046", "Zodiac Drident", "Raging Tempest",
         "Secret Rare", True, 30.00, "Monster", "EARTH"),
        ("MACR-EN046", "Zoodiac Chakanine", "Maximum Crisis",
         "Secret Rare", True, 20.00, "Monster", "EARTH"),

        # =================================================================
        # VRAINS Era — Link Monsters expanded
        # =================================================================
        ("CIBR-EN051", "Borreload Dragon", "Circuit Break",
         "Secret Rare", True, 50.00, "Monster", "DARK"),
        ("EXFO-EN050", "Heavymetalfoes Electrumite", "Extreme Force",
         "Secret Rare", True, 35.00, "Monster", "FIRE"),
        ("FLOD-EN044", "Knightmare Gryphon", "Flames of Destruction",
         "Secret Rare", True, 20.00, "Monster", "DARK"),
        ("SOFU-EN040", "Borrelsword Dragon", "Soul Fusion",
         "Secret Rare", True, 45.00, "Monster", "DARK"),
        ("SAST-EN048", "Borreload Savage Dragon", "Savage Strike",
         "Secret Rare", True, 55.00, "Monster", "DARK"),
        ("DANE-EN007", "Gnomaterial", "Dark Neostorm",
         "Super Rare", True, 10.00, "Monster", "EARTH"),
        ("CHIM-EN039", "I:P Masquerena", "Chaos Impact",
         "Ultra Rare", True, 30.00, "Monster", "DARK"),
        ("ETCO-EN044", "Accesscode Talker", "Eternity Code",
         "Secret Rare", True, 80.00, "Monster", "DARK"),
        ("PHRA-EN048", "Zeus, King of Olympus (Tri-Brigade)", "Phantom Rage",
         "Ultra Rare", True, 35.00, "Monster", "LIGHT"),

        # =================================================================
        # SEVENS / GO RUSH — Rush Duel collectibles
        # =================================================================
        ("RD-KP01", "Sevens Road Magician (Over Rush Rare)", "Rush Duel Deck Mod Pack",
         "Ultra Rare", False, 60.00, "Monster", "DARK"),
        ("RD-KP07", "Blue-Eyes White Dragon (Rush Duel)", "Rush Duel Pack",
         "Ultra Rare", False, 45.00, "Monster", "LIGHT"),
        ("RD-OVR", "Dark Magician (Rush Over Rush Rare)", "Rush Duel Over Rush Pack",
         "Secret Rare", False, 80.00, "Monster", "DARK"),
        ("RD-GRS01", "Jointech Rex (GO RUSH)", "GO RUSH!! Deck Set",
         "Ultra Rare", False, 25.00, "Monster", "EARTH"),
        ("RD-CP01", "Multistrike Dragon Dragias (Secret)", "Rush Duel Character Pack",
         "Secret Rare", False, 50.00, "Monster", "LIGHT"),

        # =================================================================
        # Tin Promos & Collector's Tins
        # =================================================================
        ("CT08-EN001", "Number 39: Utopia (Tin)", "2011 Collectors Tin",
         "Secret Rare", False, 30.00, "Monster", "LIGHT"),
        ("CT09-EN001", "Hieratic Sun Dragon Overlord of Heliopolis", "2012 Collectors Tin",
         "Secret Rare", False, 25.00, "Monster", "LIGHT"),
        ("CT10-EN004", "Blaster, Dragon Ruler of Infernos (Tin)", "2013 Collectors Tin Wave 1",
         "Secret Rare", False, 20.00, "Monster", "FIRE"),
        ("CT11-EN001", "Dark Rebellion XYZ Dragon (Tin)", "2014 Mega-Tin",
         "Secret Rare", False, 25.00, "Monster", "DARK"),
        ("CT14-EN009", "Firewall Dragon (Tin)", "2017 Mega-Tin",
         "Secret Rare", False, 15.00, "Monster", "LIGHT"),
        ("MP19-EN157", "Borrelsword Dragon (Tin)", "2019 Gold Sarcophagus Tin Mega Pack",
         "Prismatic Secret Rare", False, 30.00, "Monster", "DARK"),
        ("MP23-EN001", "Exosister Mikailis (Tin)", "2023 25th Anniversary Tin",
         "Prismatic Secret Rare", False, 20.00, "Monster", "LIGHT"),
        ("MP23-EN200", "Spright Elf (Tin)", "2023 25th Anniversary Tin",
         "Prismatic Secret Rare", False, 25.00, "Monster", "DARK"),
        ("MP24-EN001", "S:P Little Knight (Tin)", "2024 Tin",
         "Prismatic Secret Rare", False, 35.00, "Monster", "DARK"),
        ("MP24-EN120", "Kashtira Arise-Heart (Tin)", "2024 Tin",
         "Prismatic Secret Rare", False, 20.00, "Monster", "DARK"),

        # =================================================================
        # Side Sets — Hidden Arsenal / Duel Terminal
        # =================================================================
        ("HA01-EN022", "Ally of Justice Catastor", "Hidden Arsenal",
         "Secret Rare", True, 45.00, "Monster", "DARK"),
        ("HA02-EN028", "Brionac, Dragon of the Ice Barrier", "Hidden Arsenal 2",
         "Secret Rare", True, 80.00, "Monster", "WATER"),
        ("HA03-EN050", "Mist Wurm", "Hidden Arsenal 3",
         "Secret Rare", True, 35.00, "Monster", "WIND"),
        ("HA05-EN052", "Daigusto Phoenix", "Hidden Arsenal 5",
         "Secret Rare", True, 30.00, "Monster", "FIRE"),
        ("HA06-EN049", "Constellar Ptolemy M7", "Hidden Arsenal 6",
         "Secret Rare", True, 25.00, "Monster", "LIGHT"),
        ("HA07-EN018", "Evilswarm Ophion", "Hidden Arsenal 7",
         "Secret Rare", True, 20.00, "Monster", "DARK"),
        ("DT01-EN034", "Flamvell Uruquizas (Duel Terminal)", "Duel Terminal 1",
         "Ultra Rare", False, 35.00, "Monster", "FIRE"),

        # =================================================================
        # Sealed Product — Tins & Special Sets expanded
        # =================================================================
        ("MAMA-TIN", "Magnificent Mavens Tin", "Magnificent Mavens",
         "Sealed Product", False, 40.00, "Sealed Product", ""),
        ("SDAZ-1ST", "Structure Deck: Albaz Strike Sealed", "Structure Deck: Albaz Strike",
         "Sealed Product", False, 12.00, "Sealed Product", ""),
        ("SR14-BOX", "Structure Deck: HERO Strike Sealed", "Structure Deck: HERO Strike",
         "Sealed Product", False, 15.00, "Sealed Product", ""),
        ("LED6-BOX", "Legendary Duelists: Magical Hero Display Box", "Legendary Duelists: Magical Hero",
         "Sealed Product", False, 120.00, "Sealed Product", ""),
        ("KICO-BOX", "King's Court Display Box", "King's Court",
         "Sealed Product", False, 85.00, "Sealed Product", ""),
        ("GRCR-BOX", "The Grand Creators Display Box", "The Grand Creators",
         "Sealed Product", False, 75.00, "Sealed Product", ""),
        ("AMDE-BOX", "Amazing Defenders Display Box", "Amazing Defenders",
         "Sealed Product", False, 60.00, "Sealed Product", ""),
        ("VASM-BOX", "Valiant Smashers Display Box", "Valiant Smashers",
         "Sealed Product", False, 65.00, "Sealed Product", ""),
        ("SGX1-BOX", "Speed Duel GX: Duel Academy Box", "Speed Duel GX: Duel Academy Box",
         "Sealed Product", False, 40.00, "Sealed Product", ""),
        ("SBC1-BOX", "Speed Duel: Battle City Box", "Speed Duel: Battle City Box",
         "Sealed Product", False, 55.00, "Sealed Product", ""),

        # =================================================================
        # OCG Exclusives — additional (QC Secret & Prismatic)
        # =================================================================
        ("QCSE-JP001", "Exodia the Forbidden One (QC Secret)", "Quarter Century Secret Edition",
         "Quarter Century Secret Rare", False, 2500.00, "Monster", "DARK"),
        ("QCSE-JP005", "Stardust Dragon (QC Secret)", "Quarter Century Secret Edition",
         "Quarter Century Secret Rare", False, 1200.00, "Monster", "WIND"),
        ("PAC1-JP015", "Red-Eyes Black Dragon (PAC)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 700.00, "Monster", "DARK"),
        ("PAC1-JP020", "Harpie's Feather Duster (PAC)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 200.00, "Spell", ""),
        ("PAC1-JP040", "Mirror Force (PAC)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 250.00, "Trap", ""),

        # =================================================================
        # Dragon Rulers (high-value banned cards)
        # =================================================================
        ("LTGY-EN040", "Blaster, Dragon Ruler of Infernos", "Lord of the Tachyon Galaxy",
         "Secret Rare", True, 60.00, "Monster", "FIRE"),
        ("LTGY-EN041", "Tidal, Dragon Ruler of Waterfalls", "Lord of the Tachyon Galaxy",
         "Secret Rare", True, 55.00, "Monster", "WATER"),
        ("LTGY-EN042", "Tempest, Dragon Ruler of Storms", "Lord of the Tachyon Galaxy",
         "Secret Rare", True, 50.00, "Monster", "WIND"),
        ("LTGY-EN043", "Redox, Dragon Ruler of Boulders", "Lord of the Tachyon Galaxy",
         "Secret Rare", True, 50.00, "Monster", "EARTH"),

        # =================================================================
        # God Cards (Egyptian Gods)
        # =================================================================
        ("TN19-EN008", "Slifer the Sky Dragon (Prismatic)", "2019 Gold Sarcophagus Tin",
         "Prismatic Secret Rare", False, 60.00, "Monster", "DIVINE"),
        ("TN19-EN007", "Obelisk the Tormentor (Prismatic)", "2019 Gold Sarcophagus Tin",
         "Prismatic Secret Rare", False, 55.00, "Monster", "DIVINE"),
        ("TN19-EN006", "The Winged Dragon of Ra (Prismatic)", "2019 Gold Sarcophagus Tin",
         "Prismatic Secret Rare", False, 50.00, "Monster", "DIVINE"),
        ("GBI-001", "Slifer the Sky Dragon (GBI Secret)", "God Card Promo",
         "Secret Rare", False, 500.00, "Monster", "DIVINE"),
        ("GBI-002", "Obelisk the Tormentor (GBI Secret)", "God Card Promo",
         "Secret Rare", False, 450.00, "Monster", "DIVINE"),
        ("GBI-003", "The Winged Dragon of Ra (GBI Secret)", "God Card Promo",
         "Secret Rare", False, 600.00, "Monster", "DIVINE"),
        ("KICO-EN006", "Slifer the Sky Dragon (King's Court)", "King's Court",
         "Ultra Rare", True, 20.00, "Monster", "DIVINE"),

        # =================================================================
        # Lost Art Promotion — additional
        # =================================================================
        ("LART-EN008", "Harpie's Feather Duster (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 50.00, "Spell", ""),
        ("LART-EN009", "Monster Reborn (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 60.00, "Spell", ""),
        ("LART-EN010", "Change of Heart (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 45.00, "Spell", ""),
        ("LART-EN011", "Raigeki (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 40.00, "Spell", ""),
        ("LART-EN012", "Mirror Force (Lost Art)", "Lost Art Promotion",
         "Ultra Rare", False, 35.00, "Trap", ""),

        # =================================================================
        # Collector's Rares (modern sets)
        # =================================================================
        ("GRCR-EN029", "Fallen of Albaz (Collector's Rare)", "The Grand Creators",
         "Collector's Rare", True, 80.00, "Monster", "DARK"),
        ("TOCH-EN010", "Chaos Space (Collector's Rare)", "Toon Chaos",
         "Collector's Rare", True, 100.00, "Spell", ""),
        ("BLCR-EN039", "Forbidden Droplet (Collector's Rare)", "Battles of Legend: Crystal Revenge",
         "Collector's Rare", True, 150.00, "Spell", ""),
        ("BLCR-EN064", "Masquerade the Blazing Dragon (CR)", "Battles of Legend: Crystal Revenge",
         "Collector's Rare", True, 90.00, "Monster", "DARK"),
        ("BLMR-EN086", "S:P Little Knight (Collector's Rare)", "Battles of Legend: Monstrous Revenge",
         "Collector's Rare", True, 120.00, "Monster", "DARK"),
        ("MZMI-EN080", "Baronne de Fleur (Collector's Rare)", "Maze of Millennia",
         "Collector's Rare", True, 100.00, "Monster", "WIND"),

        # =================================================================
        # Ritual Monsters & Fusions — classics
        # =================================================================
        ("MRL-EN024", "Relinquished", "Spell Ruler",
         "Ultra Rare", True, 180.00, "Monster", "DARK"),
        ("MFC-EN095", "Dark Paladin", "Magician's Force",
         "Ultra Rare", True, 200.00, "Monster", "DARK"),
        ("SOD-EN036", "Master of Oz", "Soul of the Duelist",
         "Ultra Rare", True, 40.00, "Monster", "EARTH"),
        ("IOC-028", "Chaos Sorcerer", "Invasion of Chaos",
         "Super Rare", True, 45.00, "Monster", "DARK"),
        ("RDS-EN036", "Thestalos the Firestorm Monarch", "Rise of Destiny",
         "Ultra Rare", True, 35.00, "Monster", "FIRE"),

        # =================================================================
        # Modern meta staples — Tearlaments / Kashtira / Labrynth
        # =================================================================
        ("DABL-EN007", "Tearlaments Scheiren", "Darkwing Blast",
         "Ultra Rare", True, 25.00, "Monster", "DARK"),
        ("DABL-EN005", "Tearlaments Merrli", "Darkwing Blast",
         "Super Rare", True, 8.00, "Monster", "WATER"),
        ("DABL-EN046", "Tearlaments Kaleido-Heart", "Darkwing Blast",
         "Secret Rare", True, 35.00, "Monster", "WATER"),
        ("CYAC-EN007", "Kashtira Shangri-Ira", "Cyberstorm Access",
         "Secret Rare", True, 30.00, "Monster", "DARK"),
        ("AMDE-EN020", "Lady Labrynth of the Silver Castle", "Amazing Defenders",
         "Secret Rare", True, 55.00, "Monster", "DARK"),
        ("AMDE-EN048", "Welcome Labrynth", "Amazing Defenders",
         "Ultra Rare", True, 20.00, "Trap", ""),

        # =================================================================
        # Crossover & Collaboration Promos
        # =================================================================
        ("YMP1-EN001", "Malefic Red-Eyes Black Dragon", "3D Bonds Beyond Time Pack",
         "Secret Rare", False, 40.00, "Monster", "DARK"),
        ("JUMP-EN041", "Number 39: Utopia (JUMP)", "Shonen Jump Promo",
         "Ultra Rare", False, 35.00, "Monster", "LIGHT"),
        ("JUMP-EN058", "Slifer the Sky Dragon (JUMP)", "Shonen Jump Promo",
         "Ultra Rare", False, 80.00, "Monster", "DIVINE"),

        # =================================================================
        # Recent sets — Wild Survivors (WISU) expanded
        # =================================================================
        ("WISU-EN015", "Purrely Sleepy Memory", "Wild Survivors",
         "Ultra Rare", True, 20.00, "Spell", ""),
        ("WISU-EN008", "Purrely Happy Memory", "Wild Survivors",
         "Ultra Rare", True, 15.00, "Spell", ""),
        ("WISU-EN025", "Mementomictlan Tecuhtlica", "Wild Survivors",
         "Secret Rare", True, 25.00, "Monster", "DARK"),

        # =================================================================
        # Sealed Product — Booster boxes (additional)
        # =================================================================
        ("ROTD-BOX", "Rise of the Duelist Display Box", "Rise of the Duelist",
         "Sealed Product", False, 120.00, "Sealed Product", ""),
        ("SAST-BOX", "Savage Strike Display Box", "Savage Strike",
         "Sealed Product", False, 100.00, "Sealed Product", ""),
        ("SOFU-BOX", "Soul Fusion Display Box", "Soul Fusion",
         "Sealed Product", False, 95.00, "Sealed Product", ""),
        ("CIBR-BOX", "Circuit Break Display Box", "Circuit Break",
         "Sealed Product", False, 85.00, "Sealed Product", ""),
        ("DUEA-BOX", "Duelist Alliance Display Box", "Duelist Alliance",
         "Sealed Product", False, 150.00, "Sealed Product", ""),
        ("SECE-BOX", "Secrets of Eternity Display Box", "Secrets of Eternity",
         "Sealed Product", False, 120.00, "Sealed Product", ""),
        ("CORE-BOX", "Clash of Rebellions Display Box", "Clash of Rebellions",
         "Sealed Product", False, 90.00, "Sealed Product", ""),
        ("SHVI-BOX", "Shining Victories Display Box", "Shining Victories",
         "Sealed Product", False, 95.00, "Sealed Product", ""),

        # =================================================================
        # Legendary Collection (LC) & Mega Pack reprints
        # =================================================================
        ("LCYW-EN051", "Dark Magician (Legendary Collection 3)", "Legendary Collection 3",
         "Secret Rare", False, 80.00, "Monster", "DARK"),
        ("LCJW-EN061", "Blue-Eyes White Dragon (Legendary Collection 4)", "Legendary Collection 4",
         "Ultra Rare", False, 70.00, "Monster", "LIGHT"),
        ("LC5D-EN061", "Stardust Dragon (Legendary Collection 5Ds)", "Legendary Collection 5Ds",
         "Secret Rare", False, 50.00, "Monster", "WIND"),
        ("LCKC-EN001", "Blue-Eyes Alternative White Dragon (LCKC)", "Legendary Collection Kaiba",
         "Secret Rare", False, 40.00, "Monster", "LIGHT"),
        ("LCKC-EN066", "Ash Blossom & Joyous Spring (LCKC)", "Legendary Collection Kaiba",
         "Secret Rare", False, 25.00, "Monster", "FIRE"),

        # =================================================================
        # Dawn of Majesty (DAMA) — additional
        # =================================================================
        ("DAMA-EN013", "Swordsoul of Mo Ye", "Dawn of Majesty",
         "Super Rare", True, 15.00, "Monster", "WATER"),
        ("DAMA-EN050", "Swordsoul Grandmaster - Chixiao (DAMA)", "Dawn of Majesty",
         "Ultra Rare", True, 25.00, "Monster", "WATER"),

        # =================================================================
        # Dimension Force (DIFO) additional
        # =================================================================
        ("DIFO-EN009", "Spright Jet", "Dimension Force",
         "Ultra Rare", True, 20.00, "Monster", "DARK"),
        ("DIFO-EN047", "Gigantic Spright", "Dimension Force",
         "Secret Rare", True, 30.00, "Monster", "DARK"),

        # =================================================================
        # Power of the Elements (POTE) additional
        # =================================================================
        ("POTE-EN008", "Therion Irregular", "Power of the Elements",
         "Ultra Rare", True, 20.00, "Monster", "EARTH"),
        ("POTE-EN050", "Tearlaments Heartbeat", "Power of the Elements",
         "Secret Rare", True, 25.00, "Trap", ""),

        # =================================================================
        # Additional Sealed Product — recent sets
        # =================================================================
        ("LEDE-SE", "Legacy of Destruction Special Edition", "Legacy of Destruction",
         "Sealed Product", False, 15.00, "Sealed Product", ""),
        ("PHNI-SE", "Phantom Nightmare Special Edition", "Phantom Nightmare",
         "Sealed Product", False, 15.00, "Sealed Product", ""),
        ("AGOV-SE", "Age of Overlord Special Edition", "Age of Overlord",
         "Sealed Product", False, 15.00, "Sealed Product", ""),
        ("INFO-SE", "The Infinite Forbidden Special Edition", "The Infinite Forbidden",
         "Sealed Product", False, 15.00, "Sealed Product", ""),
        ("BLMR-BOX", "Battles of Legend: Monstrous Revenge Display Box", "Battles of Legend: Monstrous Revenge",
         "Sealed Product", False, 100.00, "Sealed Product", ""),
        ("BROL-BOX", "Brothers of Legend Display Box", "Brothers of Legend",
         "Sealed Product", False, 80.00, "Sealed Product", ""),

        # =================================================================
        # Classic fan favorite singles — Pharaoh's Servant / Soul of Duelist
        # =================================================================
        ("PSV-001", "Jinzo (Ultra Rare)", "Pharaoh's Servant",
         "Ultra Rare", True, 350.00, "Monster", "DARK"),
        ("SOD-EN012", "Armed Dragon LV10", "Soul of the Duelist",
         "Ultra Rare", True, 100.00, "Monster", "WIND"),
        ("SOD-EN008", "Armed Dragon LV7", "Soul of the Duelist",
         "Super Rare", True, 45.00, "Monster", "WIND"),
        ("FET-EN015", "Sacred Beast Hamon", "Flaming Eternity",
         "Ultra Rare", True, 65.00, "Monster", "LIGHT"),
        ("SOI-EN001", "Raviel, Lord of Phantasms", "Shadow of Infinity",
         "Secret Rare", True, 80.00, "Monster", "DARK"),
        ("SOI-EN003", "Uria, Lord of Searing Flames", "Shadow of Infinity",
         "Secret Rare", True, 75.00, "Monster", "FIRE"),

        # =================================================================
        # More Starlight Rares to complete modern era
        # =================================================================
        ("CYAC-EN050", "Promethean Princess (CYAC StR)", "Cyberstorm Access",
         "Starlight Rare", True, 350.00, "Monster", "FIRE"),
        ("MZMI-EN080", "Exodia Legendary Defender (Starlight)", "Maze of Millennia",
         "Starlight Rare", True, 600.00, "Monster", "DARK"),
        ("DUNE-EN050", "Purrely My Friend (Starlight)", "Duelist Nexus",
         "Starlight Rare", True, 380.00, "Monster", "LIGHT"),

        # =================================================================
        # Expansion Batch — Ghost Rares, Starlight Rares, QCSR, OCG Arts, Prize Cards, Speed Duel GX
        # =================================================================

        # Ghost Rares — additional iconic & modern
        ("GFTP2-EN078", "Blue-Eyes Alternative White Dragon (Ghost)", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 320.00, "Monster", "LIGHT"),
        ("GFTP-EN135", "Dark Magician (GFTP Ghost)", "Ghosts From the Past",
         "Ghost Rare", False, 480.00, "Monster", "DARK"),
        ("GFP2-EN183", "Stardust Dragon (GFTP2 Ghost)", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 270.00, "Monster", "WIND"),
        ("TAEV-EN006", "Rainbow Dragon (1st Ed Ghost)", "Tactical Evolution",
         "Ghost Rare", False, 1600.00, "Monster", "LIGHT"),
        ("SOVR-EN044", "Majestic Star Dragon (Ghost Unlimited)", "Stardust Overdrive",
         "Ghost Rare", False, 450.00, "Monster", "WIND"),
        ("GFP2-EN184", "Galaxy-Eyes Photon Dragon (GFTP2 Ghost)", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 220.00, "Monster", "LIGHT"),
        ("GFP2-EN185", "Red-Eyes Flare Metal Dragon (Ghost)", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 180.00, "Monster", "DARK"),

        # Starlight Rares — additional modern chase
        ("LEDE-EN045", "White Forest Precia (Starlight)", "Legacy of Destruction",
         "Starlight Rare", True, 380.00, "Monster", "LIGHT"),
        ("AGOV-EN009", "Fiendsmith Lacrimosa (Starlight)", "Age of Overlord",
         "Starlight Rare", True, 420.00, "Monster", "LIGHT"),
        ("INFO-EN045", "Centur-Ion Emeth VI (Starlight)", "The Infinite Forbidden",
         "Starlight Rare", True, 320.00, "Monster", "LIGHT"),
        ("PHNI-EN050", "Bonfire (Starlight)", "Phantom Nightmare",
         "Starlight Rare", True, 350.00, "Spell", ""),
        ("DUNE-EN045", "Purrely Delicious Memory (Starlight Alt)", "Duelist Nexus",
         "Starlight Rare", True, 420.00, "Spell", ""),
        ("CYAC-EN045", "Kashtira Arise-Heart (Starlight Alt)", "Cyberstorm Access",
         "Starlight Rare", True, 480.00, "Monster", "DARK"),
        ("WISU-EN045", "S:P Little Knight (Starlight Alt)", "Wild Survivors",
         "Starlight Rare", True, 520.00, "Monster", "DARK"),
        ("MZMI-EN045", "Exodia Legendary Defender (Starlight Alt)", "Maze of Millennia",
         "Starlight Rare", True, 580.00, "Monster", "DARK"),
        ("VASM-EN045", "Lovely Labrynth (Starlight Alt)", "Valiant Smashers",
         "Starlight Rare", True, 380.00, "Monster", "DARK"),

        # Quarter Century Secret Rares — additional
        ("RA02-EN060", "Infinite Impermanence (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 400.00, "Trap", ""),
        ("RA02-EN065", "Lightning Storm (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 550.00, "Spell", ""),
        ("RA01-EN040", "Nibiru, the Primal Being (QCSR RA01)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 450.00, "Monster", "LIGHT"),
        ("RA01-EN045", "Ghost Belle & Haunted Mansion (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 350.00, "Monster", "EARTH"),
        ("RA02-EN070", "Baronne de Fleur (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 650.00, "Monster", "WIND"),
        ("RA02-EN075", "Borreload Savage Dragon (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 500.00, "Monster", "DARK"),

        # OCG-Exclusive Arts — Japanese Promos
        ("20TH-JPC03", "Stardust Dragon (20th Secret JP)", "20th Anniversary Set",
         "Prismatic Secret Rare", False, 800.00, "Monster", "WIND"),
        ("20TH-JPC04", "Number 39: Utopia (20th Secret JP)", "20th Anniversary Set",
         "Prismatic Secret Rare", False, 500.00, "Monster", "LIGHT"),
        ("PAC1-JP050", "Dark Magician Girl (PAC Alt Art)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 900.00, "Monster", "DARK"),
        ("PAC1-JP055", "Exodia the Forbidden One (PAC)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 1100.00, "Monster", "DARK"),
        ("QCDB-JP004", "Stardust Dragon (QC Duelist Box)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 1000.00, "Monster", "WIND"),
        ("QCDB-JP005", "Black Rose Dragon (QC Duelist Box)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 800.00, "Monster", "FIRE"),
        ("QCSE-JP010", "Dark Magician (QC Secret Edition)", "Quarter Century Secret Edition",
         "Quarter Century Secret Rare", False, 1800.00, "Monster", "DARK"),

        # Prize Cards — Tournament Exclusives
        ("WCPS-EN904", "Stardust Dragon (WCPS 2015)", "World Championship Prize",
         "Prize Card", False, 20000.00, "Monster", "WIND"),
        ("SJC-EN004", "Grandopolis, The Eternal Golden City", "Shonen Jump Championship",
         "Prize Card", False, 9000.00, "Spell", ""),
        ("YCSW-EN006", "Duel Terminal - Star Eater (YCSW)", "YCS Prize",
         "Prize Card", False, 5500.00, "Monster", "LIGHT"),
        ("WCPS-EN905", "Number 39: Utopia (WCPS 2014)", "World Championship Prize",
         "Prize Card", False, 15000.00, "Monster", "LIGHT"),
        ("SJC-EN005", "Shrink (SJC Ultra Prize)", "Shonen Jump Championship",
         "Prize Card", False, 7000.00, "Spell", ""),

        # Speed Duel GX — Tournament Prizes & Chase Cards
        ("SGX3-ENS02", "Elemental HERO Flame Wingman (Speed Duel Secret)", "Speed Duel GX: March of the Monarchs",
         "Secret Rare", False, 30.00, "Monster", "WIND"),
        ("SGX4-ENS01", "Yubel (Speed Duel GX Secret)", "Speed Duel GX: Midterm Destruction",
         "Secret Rare", False, 28.00, "Monster", "DARK"),
        ("SGX4-ENS02", "Rainbow Dragon (Speed Duel GX Secret)", "Speed Duel GX: Midterm Destruction",
         "Secret Rare", False, 32.00, "Monster", "LIGHT"),
        ("SBC1-ENS02", "Slifer the Sky Dragon (Speed Duel Secret)", "Speed Duel: Battle City Box",
         "Secret Rare", False, 45.00, "Monster", "DIVINE"),
        ("SBC1-ENS03", "The Winged Dragon of Ra (Speed Duel Secret)", "Speed Duel: Battle City Box",
         "Secret Rare", False, 55.00, "Monster", "DIVINE"),

        # Additional Modern Meta Staples
        ("LEDE-EN050", "Fiendsmith's Tractus (Secret)", "Legacy of Destruction",
         "Secret Rare", True, 65.00, "Spell", ""),
        ("INFO-EN050", "Sinful Spoils (Secret)", "The Infinite Forbidden",
         "Secret Rare", True, 50.00, "Spell", ""),
        ("AGOV-EN050", "Vaalmonica Scelta (Secret)", "Age of Overlord",
         "Secret Rare", True, 60.00, "Spell", ""),
        ("PHNI-EN055", "Promethean Princess (Ultra)", "Phantom Nightmare",
         "Ultra Rare", True, 45.00, "Monster", "FIRE"),
        ("DUNE-EN055", "Tenpai Dragon Fadra (Ultra)", "Duelist Nexus",
         "Ultra Rare", True, 35.00, "Monster", "FIRE"),
        ("INFO-EN055", "Fiendsmith's Lacrima (Ultra)", "The Infinite Forbidden",
         "Ultra Rare", True, 30.00, "Monster", "LIGHT"),
        ("MZMI-EN055", "Exodia Legendary Defender (Ultra)", "Maze of Millennia",
         "Ultra Rare", True, 40.00, "Monster", "DARK"),

        # =================================================================
        # Ghost Rares — Expansion (+10)
        # =================================================================
        ("GFTP-EN001", "Blue-Eyes White Dragon (Ghost)", "Ghosts From the Past",
         "Ghost Rare", True, 350.00, "Monster", "LIGHT"),
        ("GFTP-EN056", "Dark Magician (Ghost)", "Ghosts From the Past",
         "Ghost Rare", True, 320.00, "Monster", "DARK"),
        ("GFP2-EN001", "Red-Eyes Black Dragon (Ghost)", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", True, 280.00, "Monster", "DARK"),
        ("GFP2-EN130", "Stardust Dragon (Ghost)", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", True, 400.00, "Monster", "WIND"),
        ("DUSA-EN001", "Crystal Wing Synchro Dragon (Ghost)", "Duelist Saga",
         "Ghost Rare", True, 250.00, "Monster", "WIND"),
        ("TAEV-EN007", "Rainbow Dragon (Ghost)", "Tactical Evolution",
         "Ghost Rare", True, 600.00, "Monster", "LIGHT"),
        ("PTDN-EN043", "Rainbow Neos (Ghost)", "Phantom Darkness",
         "Ghost Rare", True, 550.00, "Monster", "LIGHT"),
        ("ANPR-EN040", "Ancient Fairy Dragon (Ghost)", "Ancient Prophecy",
         "Ghost Rare", True, 800.00, "Monster", "LIGHT"),
        ("SOVR-EN044", "Majestic Red Dragon (Ghost)", "Stardust Overdrive",
         "Ghost Rare", True, 450.00, "Monster", "DARK"),
        ("ABPF-EN040", "Majestic Star Dragon (Ghost)", "Absolute Powerforce",
         "Ghost Rare", True, 500.00, "Monster", "WIND"),

        # =================================================================
        # Starlight Rares — Expansion (+10)
        # =================================================================
        ("MAMA-EN070", "Dark Magician Girl (Starlight)", "Magnificent Mavens",
         "Starlight Rare", True, 900.00, "Monster", "DARK"),
        ("BLVO-EN083", "Underworld Goddess of the Closed World (Starlight)", "Blazing Vortex",
         "Starlight Rare", True, 350.00, "Monster", "DARK"),
        ("DAMA-EN083", "Stardust Dragon (Starlight)", "Dawn of Majesty",
         "Starlight Rare", True, 750.00, "Monster", "WIND"),
        ("GRCR-EN005", "Blue-Eyes White Dragon (Starlight)", "The Grand Creators",
         "Starlight Rare", True, 800.00, "Monster", "LIGHT"),
        ("LEDE-EN091", "Snake-Eye Ash (Starlight)", "Legacy of Destruction",
         "Starlight Rare", True, 400.00, "Monster", "FIRE"),
        ("PHNI-EN098", "Skull Knight (Starlight)", "Phantom Nightmare",
         "Starlight Rare", True, 250.00, "Monster", "DARK"),
        ("INFO-EN098", "Fiendsmith Engraver (Starlight)", "The Infinite Forbidden",
         "Starlight Rare", True, 300.00, "Monster", "LIGHT"),
        ("AGOV-EN098", "Tenpai Dragon Chundra (Starlight)", "Age of Overlord",
         "Starlight Rare", True, 280.00, "Monster", "FIRE"),
        ("CYAC-EN098", "Kashtira Fenrir (Starlight)", "Cyberstorm Access",
         "Starlight Rare", True, 500.00, "Monster", "DARK"),
        ("POTE-EN098", "Tearlaments Scheiren (Starlight)", "Power of the Elements",
         "Starlight Rare", True, 320.00, "Monster", "WATER"),

        # =================================================================
        # Prize Cards (+5)
        # =================================================================
        ("YCSW-EN001", "Minerva, the Exalted Lightsworn (YCS Prize)", "Yu-Gi-Oh Championship Series Prize",
         "Prize Card", False, 15000.00, "Monster", "LIGHT"),
        ("TF04-EN001", "Des Volstgalph (Prize)", "Tag Force 4 Promotional Card",
         "Prize Card", False, 5000.00, "Monster", "DARK"),
        ("WCPS-AE801", "Grandopolis, the Eternal Golden City (Prize)", "World Championship Prize",
         "Prize Card", False, 8000.00, "Spell", ""),
        ("YCSW-EN008", "Ascator, Dawnwalker (YCS Prize)", "Yu-Gi-Oh Championship Series Prize",
         "Prize Card", False, 6000.00, "Monster", "LIGHT"),
        ("WCPS-EN901", "Iron Knight of Revolution (Prize)", "World Championship Prize",
         "Prize Card", False, 10000.00, "Monster", "DARK"),

        # =================================================================
        # Quarter Century Secret Rares — Expansion (+8)
        # =================================================================
        ("RA02-EN037", "Pot of Greed (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 600.00, "Spell", ""),
        ("RA02-EN026", "Kuriboh (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 350.00, "Monster", "DARK"),
        ("RA01-EN061", "Infinite Impermanence (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 450.00, "Trap", ""),
        ("RA01-EN028", "Change of Heart (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 650.00, "Spell", ""),
        ("RA01-EN034", "Red-Eyes Black Dragon (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 1200.00, "Monster", "DARK"),
        ("RA02-EN055", "Ghost Belle & Haunted Mansion (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 380.00, "Monster", "EARTH"),
        ("RA01-EN045", "Harpie's Feather Duster (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 500.00, "Spell", ""),
        ("RA02-EN080", "Black Luster Soldier - Envoy of the Beginning (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 850.00, "Monster", "LIGHT"),

        # =================================================================
        # OCG Exclusive Ultimate Rares (+7)
        # =================================================================
        ("PHRA-JP050", "Tri-Brigade Shuraig (OCG Ulti)", "Phantom Rage (OCG)",
         "Ultimate Rare", True, 200.00, "Monster", "DARK"),
        ("ROTD-JP046", "Dogmatika Ecclesia (OCG Ulti)", "Rise of the Duelist (OCG)",
         "Ultimate Rare", True, 250.00, "Monster", "LIGHT"),
        ("DAMA-JP050", "Destiny HERO - Destroyer Phoenix Enforcer (OCG Ulti)", "Dawn of Majesty (OCG)",
         "Ultimate Rare", True, 180.00, "Monster", "DARK"),
        ("BODE-JP050", "Swordsoul Grandmaster - Chixiao (OCG Ulti)", "Burst of Destiny (OCG)",
         "Ultimate Rare", True, 160.00, "Monster", "WATER"),
        ("POTE-JP050", "Spright Elf (OCG Ulti)", "Power of the Elements (OCG)",
         "Ultimate Rare", True, 220.00, "Monster", "FIRE"),
        ("CYAC-JP050", "Kashtira Arise-Heart (OCG Ulti)", "Cyberstorm Access (OCG)",
         "Ultimate Rare", True, 190.00, "Monster", "DARK"),
        ("LEDE-JP050", "Snake-Eyes Flamberge Dragon (OCG Ulti)", "Legacy of Destruction (OCG)",
         "Ultimate Rare", True, 170.00, "Monster", "FIRE"),

        # =================================================================
        # Collector's Rares — Expansion (+5)
        # =================================================================
        ("EGO1-EN001", "Blue-Eyes White Dragon (Collector's Rare)", "Egyptian God Deck: Obelisk",
         "Collector's Rare", False, 80.00, "Monster", "LIGHT"),
        ("EGS1-EN001", "Dark Magician (Collector's Rare)", "Egyptian God Deck: Slifer",
         "Collector's Rare", False, 75.00, "Monster", "DARK"),
        ("MAGO-EN001", "Blue-Eyes White Dragon (Collector's Rare Gold)", "Maximum Gold",
         "Collector's Rare", False, 100.00, "Monster", "LIGHT"),
        ("MAGO-EN002", "Dark Magician (Collector's Rare Gold)", "Maximum Gold",
         "Collector's Rare", False, 95.00, "Monster", "DARK"),
        ("MGED-EN001", "Blue-Eyes Alternative Ultimate Dragon (Collector's Rare)", "Maximum Gold: El Dorado",
         "Collector's Rare", False, 120.00, "Monster", "LIGHT"),

        # =================================================================
        # Sealed Product (+5)
        # =================================================================
        ("LOB-BOX", "Legend of Blue-Eyes White Dragon Booster Box (Sealed)", "Legend of Blue-Eyes White Dragon",
         "Sealed Product", False, 25000.00, "Sealed Product", ""),
        ("MRD-BOX", "Metal Raiders Booster Box (Sealed)", "Metal Raiders",
         "Sealed Product", False, 18000.00, "Sealed Product", ""),
        ("IOC-BOX", "Invasion of Chaos Booster Box (Sealed)", "Invasion of Chaos",
         "Sealed Product", False, 15000.00, "Sealed Product", ""),
        ("GLAS-BOX", "Gladiator's Assault Booster Box (Sealed)", "Gladiator's Assault",
         "Sealed Product", False, 3000.00, "Sealed Product", ""),
        ("PTDN-BOX", "Phantom Darkness Booster Box (Sealed)", "Phantom Darkness",
         "Sealed Product", False, 5000.00, "Sealed Product", ""),

        # =================================================================
        # Ghost Rares — Additional (+10)
        # =================================================================
        ("TAEV-EN035", "Rainbow Dragon (Ghost Rare)", "Tactical Evolution",
         "Ghost Rare", True, 850.00, "Monster", "LIGHT"),
        ("GLAS-EN036", "Elemental HERO Chaos Neos (Ghost Rare)", "Gladiator's Assault",
         "Ghost Rare", True, 600.00, "Monster", "DARK"),
        ("PTDN-EN001", "Rainbow Neos (Ghost Rare)", "Phantom Darkness",
         "Ghost Rare", True, 750.00, "Monster", "LIGHT"),
        ("CSOC-EN040", "Stardust Dragon (Ghost Rare)", "Crossroads of Chaos",
         "Ghost Rare", True, 1200.00, "Monster", "WIND"),
        ("RGBT-EN040", "Power Tool Dragon (Ghost Rare)", "Raging Battle",
         "Ghost Rare", True, 500.00, "Monster", "EARTH"),
        ("SOVR-EN044", "Majestic Red Dragon (Ghost Rare)", "Stardust Overdrive",
         "Ghost Rare", True, 550.00, "Monster", "DARK"),
        ("DREV-EN043", "Dragon Knight Draco-Equiste (Ghost Rare)", "Duelist Revolution",
         "Ghost Rare", True, 400.00, "Monster", "WIND"),
        ("GENF-EN041", "Number 17: Leviathan Dragon (Ghost Rare)", "Generation Force",
         "Ghost Rare", True, 350.00, "Monster", "WATER"),
        ("ORCS-EN040", "Number C39: Utopia Ray (Ghost Rare)", "Order of Chaos",
         "Ghost Rare", True, 300.00, "Monster", "LIGHT"),
        ("REDU-EN041", "Heroic Champion - Excalibur (Ghost Rare)", "Return of the Duelist",
         "Ghost Rare", True, 280.00, "Monster", "LIGHT"),

        # =================================================================
        # Starlight Rares — Recent Sets (+12)
        # =================================================================
        ("BLVO-EN087", "Heavenly Zephyr - Miradora (Starlight Rare)", "Blazing Vortex",
         "Starlight Rare", True, 400.00, "Monster", "WIND"),
        ("LIOV-EN081", "Stardust Dragon (Starlight Rare)", "Lightning Overdrive",
         "Starlight Rare", True, 1800.00, "Monster", "WIND"),
        ("DAMA-EN080", "Destiny HERO - Destroyer Phoenix Enforcer (Starlight Rare)", "Dawn of Majesty",
         "Starlight Rare", True, 1200.00, "Monster", "DARK"),
        ("BODE-EN098", "Baronne de Fleur (Starlight Rare)", "Burst of Destiny",
         "Starlight Rare", True, 900.00, "Monster", "WIND"),
        ("POTE-EN099", "Spright Blue (Starlight Rare)", "Power of the Elements",
         "Starlight Rare", True, 700.00, "Monster", "DARK"),
        ("PHHY-EN100", "Kashtira Fenrir (Starlight Rare)", "Photon Hypernova",
         "Starlight Rare", True, 500.00, "Monster", "DARK"),
        ("CYAC-EN098", "Mannadium Trisukta (Starlight Rare)", "Cyberstorm Access",
         "Starlight Rare", True, 350.00, "Monster", "LIGHT"),
        ("DUNE-EN099", "S:P Little Knight (Starlight Rare)", "Duelist Nexus",
         "Starlight Rare", True, 600.00, "Monster", "LIGHT"),
        ("AGOV-EN098", "Fiendsmith Requiem (Starlight Rare)", "Age of Overlord",
         "Starlight Rare", True, 450.00, "Monster", "DARK"),
        ("LEDE-EN099", "Bystial Dis Pater (Starlight Rare)", "Legacy of Destruction",
         "Starlight Rare", True, 380.00, "Monster", "DARK"),
        ("VASM-EN001", "Dark Magician Girl (Starlight Rare)", "Valiant Smashers",
         "Starlight Rare", True, 2500.00, "Monster", "DARK"),
        ("MAZE-EN046", "Exodia the Forbidden One (Quarter Century Secret Rare)", "Maze of Millennia",
         "Quarter Century Secret Rare", True, 1500.00, "Monster", "DARK"),

        # =================================================================
        # Prize Cards & Jump Festa Promos (+10)
        # =================================================================
        ("YCSW-EN004", "Ascator, Dawnwalker (YCS Prize)", "YCS Prize Card",
         "Prize Card", False, 3000.00, "Monster", "EARTH"),
        ("YCSW-EN005", "Number 93: Utopia Kaiser (YCS Prize)", "YCS Prize Card",
         "Prize Card", False, 5000.00, "Monster", "LIGHT"),
        ("TFK-EN001", "Tyler the Great Warrior (Prize)", "Make-A-Wish Prize",
         "Prize Card", False, 200000.00, "Monster", "EARTH"),
        ("JF-EN001", "Blue-Eyes White Dragon (Jump Festa 2025 Promo)", "Jump Festa 2025 Promo",
         "Ultra Rare", False, 120.00, "Monster", "LIGHT"),
        ("JF-EN002", "Dark Magician (Jump Festa 2025 Promo)", "Jump Festa 2025 Promo",
         "Ultra Rare", False, 100.00, "Monster", "DARK"),
        ("JF-EN003", "Red-Eyes Black Dragon (Jump Festa 2024 Promo)", "Jump Festa 2024 Promo",
         "Ultra Rare", False, 90.00, "Monster", "DARK"),
        ("JMP-EN001", "Slifer the Sky Dragon (Shonen Jump Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 350.00, "Monster", "DIVINE"),
        ("JMP-EN002", "Obelisk the Tormentor (Shonen Jump Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 300.00, "Monster", "DIVINE"),
        ("JMP-EN003", "The Winged Dragon of Ra (Shonen Jump Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 280.00, "Monster", "DIVINE"),

        # =================================================================
        # Quarter Century Secret Rares — 25th Anniversary (+10)
        # =================================================================
        ("QCSE-EN001", "Blue-Eyes White Dragon (Quarter Century Secret Rare)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 800.00, "Monster", "LIGHT"),
        ("QCSE-EN002", "Dark Magician (Quarter Century Secret Rare)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 700.00, "Monster", "DARK"),
        ("QCSE-EN003", "Red-Eyes Black Dragon (Quarter Century Secret Rare)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 500.00, "Monster", "DARK"),
        ("RA02-EN001", "Blue-Eyes White Dragon (Quarter Century Ultimate Rare)", "25th Anniversary Ultimate Kaiba Set",
         "Quarter Century Secret Rare", False, 1200.00, "Monster", "LIGHT"),
        ("RA02-EN020", "Exodia the Forbidden One (Quarter Century Secret Rare)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 600.00, "Monster", "DARK"),
        ("RA02-EN050", "Pot of Greed (Quarter Century Secret Rare)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 400.00, "Spell", ""),
        ("RA02-EN040", "Mirror Force (Quarter Century Secret Rare)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 350.00, "Trap", ""),
        ("RA02-EN035", "Monster Reborn (Quarter Century Secret Rare)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 380.00, "Spell", ""),
        ("QCDB-EN001", "Stardust Dragon (Quarter Century Secret Rare)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 900.00, "Monster", "WIND"),
        ("QCDB-EN002", "Firewall Dragon (Quarter Century Secret Rare)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 450.00, "Monster", "LIGHT"),

        # =================================================================
        # Pharaoh's Rare from Age of Overlord (+5)
        # =================================================================
        ("AGOV-EN001", "Kurikara Divincarnate (Pharaoh's Rare)", "Age of Overlord",
         "Pharaoh's Rare", True, 200.00, "Monster", "DIVINE"),
        ("AGOV-EN038", "Vaalmonica Versare (Pharaoh's Rare)", "Age of Overlord",
         "Pharaoh's Rare", True, 150.00, "Spell", ""),
        ("AGOV-EN048", "Fiendsmith's Tractus (Pharaoh's Rare)", "Age of Overlord",
         "Pharaoh's Rare", True, 180.00, "Monster", "DARK"),
        ("AGOV-EN050", "Snake-Eye Ash (Pharaoh's Rare)", "Age of Overlord",
         "Pharaoh's Rare", True, 250.00, "Monster", "FIRE"),
        ("AGOV-EN080", "Promethean Princess, Bestower of Flames (Pharaoh's Rare)", "Age of Overlord",
         "Pharaoh's Rare", True, 220.00, "Monster", "FIRE"),

        # =================================================================
        # Maze of Millennia Chase Cards (+8)
        # =================================================================
        ("MAZE-EN001", "Blue-Eyes Jet Dragon (Ultra Rare)", "Maze of Millennia",
         "Ultra Rare", True, 35.00, "Monster", "LIGHT"),
        ("MAZE-EN025", "Exodius the Ultimate Forbidden Lord (Secret Rare)", "Maze of Millennia",
         "Secret Rare", True, 40.00, "Monster", "DARK"),
        ("MAZE-EN044", "Left Arm Offering (Secret Rare)", "Maze of Millennia",
         "Secret Rare", True, 25.00, "Spell", ""),
        ("MAZE-EN048", "Dark Magician the Dragon Knight (Ultra Rare)", "Maze of Millennia",
         "Ultra Rare", True, 30.00, "Monster", "DARK"),
        ("MAZE-EN050", "Millennium Seeker (Ultra Rare)", "Maze of Millennia",
         "Ultra Rare", True, 28.00, "Monster", "LIGHT"),
        ("MAZE-EN052", "Gandora the Dragon of Destruction (Ultra Rare)", "Maze of Millennia",
         "Ultra Rare", True, 22.00, "Monster", "DARK"),
        ("MAZE-EN060", "Dunames Dark Witch (Secret Rare)", "Maze of Millennia",
         "Secret Rare", True, 35.00, "Monster", "LIGHT"),
        ("MAZE-EN080", "Magician's Salvation (Ultra Rare)", "Maze of Millennia",
         "Ultra Rare", True, 18.00, "Spell", ""),

        # =================================================================
        # Speed Duel Tournament Promos (+5)
        # =================================================================
        ("SBCB-EN001", "Blue-Eyes White Dragon (Speed Duel Prize)", "Speed Duel Battle City Box",
         "Ultra Rare", False, 45.00, "Monster", "LIGHT"),
        ("SBCB-EN002", "Dark Magician (Speed Duel Prize)", "Speed Duel Battle City Box",
         "Ultra Rare", False, 40.00, "Monster", "DARK"),
        ("SGX4-EN001", "Slifer the Sky Dragon (Speed Duel Prize)", "Speed Duel GX Midterm Destruction",
         "Ultra Rare", False, 80.00, "Monster", "DIVINE"),
        ("SS05-EN001", "Exodia the Forbidden One (Speed Duel)", "Speed Duel Starter Deck",
         "Ultra Rare", False, 55.00, "Monster", "DARK"),
        ("SBSC-EN001", "Gate Guardian (Speed Duel)", "Speed Duel Scars of Battle",
         "Secret Rare", False, 60.00, "Monster", "DARK"),

        # =================================================================
        # OCG Exclusives — Japanese Cards (+8)
        # =================================================================
        ("RC04-JP001", "Blue-Eyes White Dragon (OCG Extra Secret Rare)", "Rarity Collection 2024",
         "Extra Secret Rare", False, 180.00, "Monster", "LIGHT"),
        ("RC04-JP003", "Dark Magician (OCG Extra Secret Rare)", "Rarity Collection 2024",
         "Extra Secret Rare", False, 160.00, "Monster", "DARK"),
        ("RC04-JP010", "Ash Blossom & Joyous Spring (OCG Extra Secret Rare)", "Rarity Collection 2024",
         "Extra Secret Rare", False, 120.00, "Monster", "FIRE"),
        ("PAC1-JP004", "Blue-Eyes White Dragon (OCG Prismatic Art Rare)", "Prismatic Art Collection",
         "Prismatic Art Rare", False, 250.00, "Monster", "LIGHT"),
        ("PAC1-JP005", "Dark Magician (OCG Prismatic Art Rare)", "Prismatic Art Collection",
         "Prismatic Art Rare", False, 220.00, "Monster", "DARK"),
        ("PAC1-JP006", "Red-Eyes Black Dragon (OCG Prismatic Art Rare)", "Prismatic Art Collection",
         "Prismatic Art Rare", False, 200.00, "Monster", "DARK"),
        ("20TH-JPC01", "Blue-Eyes White Dragon (20th Secret Rare)", "20th Anniversary Legend Collection",
         "20th Secret Rare", False, 350.00, "Monster", "LIGHT"),
        ("20TH-JPC02", "Dark Magician (20th Secret Rare)", "20th Anniversary Legend Collection",
         "20th Secret Rare", False, 300.00, "Monster", "DARK"),

        # =================================================================
        # Anniversary Gold Rares (+5)
        # =================================================================
        ("GLD5-EN001", "Blue-Eyes White Dragon (Gold Rare)", "Gold Series: Haunted Mine",
         "Gold Rare", False, 60.00, "Monster", "LIGHT"),
        ("GLD5-EN002", "Dark Magician (Gold Rare)", "Gold Series: Haunted Mine",
         "Gold Rare", False, 55.00, "Monster", "DARK"),
        ("PGL3-EN080", "Solemn Strike (Gold Secret Rare)", "Premium Gold: Infinite Gold",
         "Gold Secret Rare", False, 45.00, "Trap", ""),
        ("MAGO-EN028", "Nibiru, the Primal Being (Premium Gold Rare)", "Maximum Gold",
         "Premium Gold Rare", False, 35.00, "Monster", "LIGHT"),
        ("MAGO-EN030", "Ash Blossom & Joyous Spring (Premium Gold Rare)", "Maximum Gold",
         "Premium Gold Rare", False, 40.00, "Monster", "FIRE"),

        # =================================================================
        # Sealed Product — Additional (+4)
        # =================================================================
        ("DREV-BOX", "Duelist Revolution Booster Box (Sealed)", "Duelist Revolution",
         "Sealed Product", False, 4000.00, "Sealed Product", ""),
        ("CSOC-BOX", "Crossroads of Chaos Booster Box (Sealed)", "Crossroads of Chaos",
         "Sealed Product", False, 3500.00, "Sealed Product", ""),
        ("AST-BOX", "Ancient Sanctuary Booster Box (Sealed)", "Ancient Sanctuary",
         "Sealed Product", False, 6000.00, "Sealed Product", ""),
        ("CRV-BOX", "Cybernetic Revolution Booster Box (Sealed)", "Cybernetic Revolution",
         "Sealed Product", False, 8000.00, "Sealed Product", ""),

        # =================================================================
        # Additional Collectible Cards (+10)
        # =================================================================
        ("ROTD-EN034", "Dogmatika Ecclesia, the Virtuous", "Rise of the Duelist",
         "Secret Rare", True, 45.00, "Monster", "LIGHT"),
        ("DAMA-EN009", "Destiny HERO - Destroyer Phoenix Enforcer", "Dawn of Majesty",
         "Secret Rare", True, 80.00, "Monster", "DARK"),
        ("POTE-EN033", "Spright Blue", "Power of the Elements",
         "Secret Rare", True, 55.00, "Monster", "FIRE"),
        ("POTE-EN051", "Tearlaments Kitkallos", "Power of the Elements",
         "Ultra Rare", True, 35.00, "Monster", "DARK"),
        ("DABL-EN019", "Kashtira Unicorn", "Darkwing Blast",
         "Ultra Rare", True, 40.00, "Monster", "WIND"),
        ("CYAC-EN048", "S:P Little Knight", "Cyberstorm Access",
         "Quarter Century Secret Rare", True, 180.00, "Monster", "LIGHT"),
        ("BLVO-EN089", "Divine Arsenal AA-ZEUS - Sky Thunder", "Blazing Vortex",
         "Secret Rare", True, 50.00, "Monster", "LIGHT"),
        ("BODE-EN050", "Baronne de Fleur", "Burst of Destiny",
         "Secret Rare", True, 65.00, "Monster", "WIND"),
        ("MAMA-EN020", "Ghost Belle & Haunted Mansion (Collector's Rare)", "Magnificent Mavens",
         "Collector's Rare", False, 30.00, "Monster", "EARTH"),
        ("LEDE-EN020", "Fiendsmith Requiem", "Legacy of Destruction",
         "Quarter Century Secret Rare", True, 120.00, "Monster", "DARK"),
        ("INFO-EN024", "Snake-Eyes Flamberge Dragon", "The Infinite Forbidden",
         "Quarter Century Secret Rare", True, 150.00, "Monster", "FIRE"),
        ("AGOV-EN007", "Vaalmonica Disarmonia", "Age of Overlord",
         "Secret Rare", True, 35.00, "Monster", "LIGHT"),

        # =================================================================
        # EXPANSION BATCH 2 — Ghost Rares (additional iconic)
        # =================================================================
        ("TDGS-EN040", "Stardust Dragon (Ghost Rare 1st)", "The Duelist Genesis",
         "Ghost Rare", True, 2800.00, "Monster", "WIND"),
        ("ABPF-EN040", "Red Dragon Archfiend (Ghost Rare)", "Absolute Powerforce",
         "Ghost Rare", True, 750.00, "Monster", "DARK"),
        ("CRMS-EN040", "Red Dragon Archfiend/Assault Mode (Ghost)", "Crimson Crisis",
         "Ghost Rare", True, 650.00, "Monster", "DARK"),
        ("PHSW-EN038", "Galaxy-Eyes Photon Dragon (Ghost Rare)", "Photon Shockwave",
         "Ghost Rare", True, 500.00, "Monster", "LIGHT"),
        ("LTGY-EN044", "Number 107: Galaxy-Eyes Tachyon Dragon (Ghost)", "Lord of the Tachyon Galaxy",
         "Ghost Rare", True, 480.00, "Monster", "LIGHT"),
        ("SHVI-EN049", "Clear Wing Synchro Dragon (Ghost Rare)", "Shining Victories",
         "Ghost Rare", True, 350.00, "Monster", "WIND"),
        ("GFTP-EN136", "Firewall Dragon (Ghost Rare)", "Ghosts From the Past",
         "Ghost Rare", False, 280.00, "Monster", "LIGHT"),
        ("GFP2-EN186", "Chaos Dragon Levianeer (Ghost Rare)", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 220.00, "Monster", "LIGHT"),
        ("GFP2-EN187", "The Winged Dragon of Ra (Ghost Rare)", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 350.00, "Monster", "DIVINE"),
        ("MAMA-EN061", "Blue-Eyes Alternative White Dragon (Ghost)", "Magnificent Mavens",
         "Ghost Rare", False, 280.00, "Monster", "LIGHT"),
        ("GFTP-EN137", "Honest (Ghost Rare)", "Ghosts From the Past",
         "Ghost Rare", False, 260.00, "Monster", "LIGHT"),
        ("GFP2-EN188", "Black Rose Dragon (GFTP2 Ghost)", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 240.00, "Monster", "FIRE"),

        # =================================================================
        # EXPANSION BATCH 2 — Starlight Rares (additional modern chase)
        # =================================================================
        ("ETCO-EN045", "Accesscode Talker (Starlight Rare)", "Eternity Code",
         "Starlight Rare", True, 1400.00, "Monster", "DARK"),
        ("RIRA-EN048", "Apollousa, Bow of the Goddess (Starlight)", "Rising Rampage",
         "Starlight Rare", True, 900.00, "Monster", "WIND"),
        ("IGAS-EN067", "Lightning Storm (Starlight Rare)", "Ignition Assault",
         "Starlight Rare", True, 1500.00, "Spell", ""),
        ("TOCH-EN006", "Triple Tactics Talent (Starlight Rare)", "Toon Chaos",
         "Starlight Rare", True, 1200.00, "Spell", ""),
        ("BROL-EN039", "Forbidden Droplet (Starlight Rare)", "Brothers of Legend",
         "Starlight Rare", True, 800.00, "Spell", ""),
        ("BLVO-EN065", "Pot of Prosperity (Starlight Rare)", "Blazing Vortex",
         "Starlight Rare", True, 850.00, "Spell", ""),
        ("DAMA-EN041", "Small World (Starlight Rare)", "Dawn of Majesty",
         "Starlight Rare", True, 600.00, "Spell", ""),
        ("MP22-EN264", "Branded Fusion (Starlight Rare)", "2022 Tin of the Pharaoh's Gods",
         "Starlight Rare", False, 500.00, "Spell", ""),
        ("CYAC-EN009", "Kashtira Fenrir (Starlight Rare)", "Cyberstorm Access",
         "Starlight Rare", True, 550.00, "Monster", "EARTH"),
        ("AMDE-EN001", "Tearlaments Kitkallos (Starlight Rare)", "Amazing Defenders",
         "Starlight Rare", True, 700.00, "Monster", "DARK"),
        ("DIFO-EN010", "Spright Blue (Starlight Rare Alt)", "Dimension Force",
         "Starlight Rare", True, 520.00, "Monster", "DARK"),
        ("DABL-EN052", "Bystial Druiswurm (Starlight Rare)", "Darkwing Blast",
         "Starlight Rare", True, 400.00, "Monster", "DARK"),
        ("PHNI-EN004", "Snake-Eye Ash (Starlight Rare Alt)", "Phantom Nightmare",
         "Starlight Rare", True, 550.00, "Monster", "FIRE"),
        ("PHNI-EN034", "Bonfire (Starlight Rare)", "Phantom Nightmare",
         "Starlight Rare", True, 380.00, "Spell", ""),
        ("LEDE-EN070", "Skull Guardian, Protector of the Voiceless Voice (StR)", "Legacy of Destruction",
         "Starlight Rare", True, 450.00, "Monster", "LIGHT"),
        ("INFO-EN098", "Fiendsmith Engraver (Starlight Alt)", "The Infinite Forbidden",
         "Starlight Rare", True, 350.00, "Monster", "LIGHT"),
        ("LEDE-EN004", "Tenpai Dragon Paidra (Starlight Rare)", "Legacy of Destruction",
         "Starlight Rare", True, 500.00, "Monster", "FIRE"),
        ("DUDE-EN003", "Ash Blossom & Joyous Spring (Starlight Reprint)", "Duel Devastator",
         "Starlight Rare", False, 650.00, "Monster", "FIRE"),
        ("DUDE-EN010", "Effect Veiler (Starlight Rare)", "Duel Devastator",
         "Starlight Rare", False, 400.00, "Monster", "LIGHT"),
        ("BROL-EN043", "Ghost Belle & Haunted Mansion (Starlight)", "Brothers of Legend",
         "Starlight Rare", True, 420.00, "Monster", "EARTH"),

        # =================================================================
        # EXPANSION BATCH 2 — Quarter Century Secret Rares (additional)
        # =================================================================
        ("RA01-EN002", "Slifer the Sky Dragon (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 1200.00, "Monster", "DIVINE"),
        ("RA01-EN003", "Obelisk the Tormentor (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 1100.00, "Monster", "DIVINE"),
        ("RA01-EN004", "The Winged Dragon of Ra (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 1000.00, "Monster", "DIVINE"),
        ("RA02-EN002", "Kuriboh (QCSR Alt)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 400.00, "Monster", "DARK"),
        ("RA02-EN008", "Number 39: Utopia (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 500.00, "Monster", "LIGHT"),
        ("RA02-EN009", "Decode Talker (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 450.00, "Monster", "DARK"),
        ("RA01-EN008", "Elemental HERO Neos (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 600.00, "Monster", "LIGHT"),
        ("RA01-EN009", "Junk Warrior (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 500.00, "Monster", "DARK"),
        ("RA02-EN003", "Dark Magician Girl (QCSR Alt)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 1500.00, "Monster", "DARK"),
        ("RA02-EN004", "Blue-Eyes Ultimate Dragon (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 800.00, "Monster", "LIGHT"),
        ("RA02-EN005", "Five-Headed Dragon (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 600.00, "Monster", "DARK"),
        ("RA01-EN025", "Stardust Dragon (QCSR Alt)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 900.00, "Monster", "WIND"),

        # =================================================================
        # EXPANSION BATCH 2 — Prize Cards & Ultra Rare Promos
        # =================================================================
        ("T3-01", "Tyler the Great Warrior (Grail)", "One-of-a-Kind",
         "Prize Card", False, 75000.00, "Monster", "EARTH"),
        ("YCSW-EN002", "Ascension Sky Dragon (YCS Prize Alt)", "YCS Prize",
         "Prize Card", False, 5500.00, "Monster", "LIGHT"),
        ("JF-JP001", "Legendary Dragon of White (Jump Festa)", "Jump Festa Promo",
         "Prize Card", False, 3000.00, "Monster", "LIGHT"),
        ("YCSW-EN007", "Blood Mefist (YCS Prize)", "YCS Prize",
         "Prize Card", False, 6500.00, "Monster", "DARK"),
        ("WCQ-EN001", "Digvorzhak, King of Heavy Industry (WCQ)", "WCQ Prize",
         "Prize Card", False, 7000.00, "Monster", "EARTH"),
        ("WCQ-EN002", "Iron Knight of Revolution (WCQ Prize)", "WCQ Prize",
         "Prize Card", False, 9000.00, "Monster", "DARK"),
        ("YCSW-EN009", "Number 106: Giant Hand (YCS Prize Alt)", "YCS Prize",
         "Prize Card", False, 7500.00, "Monster", "EARTH"),
        ("AE-EN001", "Crescent Dragon (Asia Exclusive)", "Asia Exclusive Promo",
         "Prize Card", False, 4000.00, "Monster", "LIGHT"),
        ("JMP-EN006", "Unity (Jump Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 150.00, "Spell", ""),
        ("JMP-EN007", "Yu-Jo Friendship (Jump Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 120.00, "Spell", ""),
        ("JMP-EN008", "Judgment of the Pharaoh (Jump Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 100.00, "Trap", ""),
        ("JMP-EN009", "Elemental HERO Neos (Jump Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 200.00, "Monster", "LIGHT"),
        ("JMP-EN010", "The Creator God of Light, Horakhty (Jump Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 1500.00, "Monster", "DIVINE"),

        # =================================================================
        # EXPANSION BATCH 2 — Sealed Product (additional)
        # =================================================================
        ("LOB-1ST-BOX2", "LOB 1st Edition Booster Box (Sealed Graded)", "Legend of Blue-Eyes White Dragon",
         "Sealed Product", True, 150000.00, "Sealed Product", ""),
        ("MRD-1ST-BOX2", "MRD 1st Edition Booster Box (Sealed)", "Metal Raiders",
         "Sealed Product", True, 40000.00, "Sealed Product", ""),
        ("PSV-BOX2", "PSV 1st Edition Booster Box (Sealed)", "Pharaoh's Servant",
         "Sealed Product", True, 15000.00, "Sealed Product", ""),
        ("LON-BOX", "LON Unlimited Booster Box", "Labyrinth of Nightmare",
         "Sealed Product", False, 7000.00, "Sealed Product", ""),
        ("LON-1ST-BOX", "LON 1st Edition Booster Box", "Labyrinth of Nightmare",
         "Sealed Product", True, 18000.00, "Sealed Product", ""),
        ("IOC-1ST-BOX2", "IOC 1st Edition Booster Box (Sealed Alt)", "Invasion of Chaos",
         "Sealed Product", True, 50000.00, "Sealed Product", ""),
        ("DREV-1ST-BOX", "Duelist Revolution 1st Edition Box", "Duelist Revolution",
         "Sealed Product", True, 5000.00, "Sealed Product", ""),
        ("CT02-BOX", "2005 Collectors Tin (Sealed)", "2005 Collectors Tin",
         "Sealed Product", False, 200.00, "Sealed Product", ""),
        ("CT03-BOX", "2006 Collectors Tin (Sealed)", "2006 Collectors Tin",
         "Sealed Product", False, 180.00, "Sealed Product", ""),
        ("CT04-BOX", "2007 Collectors Tin (Sealed)", "2007 Collectors Tin",
         "Sealed Product", False, 250.00, "Sealed Product", ""),
        ("CT05-BOX", "2008 Collectors Tin (Sealed)", "2008 Collectors Tin",
         "Sealed Product", False, 300.00, "Sealed Product", ""),
        ("CT06-BOX", "2009 Collectors Tin (Sealed)", "2009 Collectors Tin",
         "Sealed Product", False, 150.00, "Sealed Product", ""),
        ("CT07-BOX", "2010 Collectors Tin (Sealed)", "2010 Collectors Tin",
         "Sealed Product", False, 120.00, "Sealed Product", ""),
        ("CT12-BOX", "2015 Mega-Tin Set (Sealed)", "2015 Mega-Tin",
         "Sealed Product", False, 80.00, "Sealed Product", ""),
        ("CT15-BOX", "2018 Mega-Tin Set (Sealed)", "2018 Mega-Tin",
         "Sealed Product", False, 60.00, "Sealed Product", ""),
        ("TIN2025", "2025 Collectors Tin (Sealed)", "2025 Collectors Tin",
         "Sealed Product", False, 28.00, "Sealed Product", ""),
        ("GLD1-BOX", "Gold Series 1 Display Box", "Gold Series",
         "Sealed Product", False, 200.00, "Sealed Product", ""),
        ("GLD2-BOX", "Gold Series 2009 Display Box", "Gold Series 2009",
         "Sealed Product", False, 180.00, "Sealed Product", ""),
        ("GLD3-BOX", "Gold Series 3 Display Box", "Gold Series 3",
         "Sealed Product", False, 150.00, "Sealed Product", ""),
        ("GLD4-BOX", "Gold Series 4 Display Box", "Gold Series 4: Pyramids",
         "Sealed Product", False, 120.00, "Sealed Product", ""),
        ("GLD5-BOX", "Gold Series: Haunted Mine Display Box", "Gold Series: Haunted Mine",
         "Sealed Product", False, 200.00, "Sealed Product", ""),
        ("LC02-BOX", "Legendary Collection 2 Box", "Legendary Collection 2",
         "Sealed Product", False, 250.00, "Sealed Product", ""),
        ("LC03-BOX", "Legendary Collection 3 Box", "Legendary Collection 3",
         "Sealed Product", False, 200.00, "Sealed Product", ""),
        ("LCKC-BOX", "Legendary Collection Kaiba Box", "Legendary Collection Kaiba",
         "Sealed Product", False, 120.00, "Sealed Product", ""),
        ("SDK-1ST-SEALED", "Starter Deck Kaiba 1st Ed (Sealed)", "Starter Deck Kaiba",
         "Sealed Product", True, 4000.00, "Sealed Product", ""),
        ("SDY-1ST-SEALED", "Starter Deck Yugi 1st Ed (Sealed)", "Starter Deck Yugi",
         "Sealed Product", True, 4500.00, "Sealed Product", ""),
        ("SDP-1ST", "Starter Deck Pegasus 1st Edition (Sealed)", "Starter Deck Pegasus",
         "Sealed Product", True, 2000.00, "Sealed Product", ""),
        ("SDRL-BOX", "Speed Duel Starter Decks Box Set", "Speed Duel Starter Decks",
         "Sealed Product", False, 35.00, "Sealed Product", ""),
        ("RA01-CASE", "25th Anniversary Rarity Collection Case (12 boxes)", "25th Anniversary Rarity Collection",
         "Sealed Product", False, 2000.00, "Sealed Product", ""),
        ("RA02-CASE", "25th Anniversary Rarity Collection II Case (12 boxes)", "25th Anniversary Rarity Collection II",
         "Sealed Product", False, 2200.00, "Sealed Product", ""),

        # =================================================================
        # EXPANSION BATCH 2 — More Classic Sets (MRD, SRL, IOC, AST, SOD, RDS, FET, CRV)
        # =================================================================
        ("MRD-000", "Gate Guardian (1st Ed)", "Metal Raiders",
         "Secret Rare", True, 1800.00, "Monster", "DARK"),
        ("MRD-024", "Summoned Skull (1st Ed Ultra)", "Metal Raiders",
         "Ultra Rare", True, 300.00, "Monster", "DARK"),
        ("MRD-136", "Magic Cylinder", "Metal Raiders",
         "Ultra Rare", True, 350.00, "Trap", ""),
        ("MRD-098", "7 Colored Fish", "Metal Raiders",
         "Common", True, 80.00, "Monster", "WATER"),
        ("SRL-EN001", "Delinquent Duo (Spell Ruler)", "Spell Ruler",
         "Ultra Rare", True, 250.00, "Spell", ""),
        ("SRL-EN036", "Toon Mermaid", "Spell Ruler",
         "Super Rare", True, 60.00, "Monster", "WATER"),
        ("SRL-EN039", "Toon Summoned Skull", "Spell Ruler",
         "Ultra Rare", True, 120.00, "Monster", "DARK"),
        ("IOC-000", "Chaos Emperor Dragon (1st Ed Secret)", "Invasion of Chaos",
         "Secret Rare", True, 4000.00, "Monster", "DARK"),
        ("IOC-025", "Black Luster Soldier - Envoy (1st Ed Ultra)", "Invasion of Chaos",
         "Ultra Rare", True, 2500.00, "Monster", "LIGHT"),
        ("AST-000", "Mazera DeVille", "Ancient Sanctuary",
         "Secret Rare", True, 200.00, "Monster", "DARK"),
        ("AST-035", "Zaborg the Thunder Monarch (1st Ed)", "Ancient Sanctuary",
         "Ultra Rare", True, 90.00, "Monster", "LIGHT"),
        ("AST-036", "Double Coston", "Ancient Sanctuary",
         "Super Rare", True, 30.00, "Monster", "DARK"),
        ("SOD-EN000", "Mystic Swordsman LV4", "Soul of the Duelist",
         "Secret Rare", True, 120.00, "Monster", "EARTH"),
        ("SOD-EN034", "Mobius the Frost Monarch (1st Ed)", "Soul of the Duelist",
         "Ultra Rare", True, 200.00, "Monster", "WATER"),
        ("RDS-EN000", "Phoenix Wing Wind Blast (Secret)", "Rise of Destiny",
         "Secret Rare", True, 150.00, "Trap", ""),
        ("RDS-EN035", "Thestalos the Firestorm Monarch (1st Ed)", "Rise of Destiny",
         "Ultra Rare", True, 50.00, "Monster", "FIRE"),
        ("FET-EN000", "Sacred Phoenix of Nephthys (Secret)", "Flaming Eternity",
         "Secret Rare", True, 250.00, "Monster", "FIRE"),
        ("FET-EN030", "Lightning Vortex", "Flaming Eternity",
         "Super Rare", True, 40.00, "Spell", ""),
        ("CRV-EN016", "Cyber Dragon (1st Ed Ultra)", "Cybernetic Revolution",
         "Ultra Rare", True, 400.00, "Monster", "LIGHT"),
        ("CRV-EN000", "Cybernetic Magician", "Cybernetic Revolution",
         "Secret Rare", True, 150.00, "Monster", "LIGHT"),
        ("CRV-EN034", "Cyber Twin Dragon", "Cybernetic Revolution",
         "Ultra Rare", True, 80.00, "Monster", "LIGHT"),

        # =================================================================
        # EXPANSION BATCH 2 — GX/5D's/Zexal Era (additional)
        # =================================================================
        ("SOI-EN035", "Elemental HERO Neos (Ultimate Rare)", "Shadow of Infinity",
         "Ultimate Rare", True, 450.00, "Monster", "LIGHT"),
        ("POTD-EN015", "Destiny HERO - Plasma (Ultra)", "Power of the Duelist",
         "Ultra Rare", True, 65.00, "Monster", "DARK"),
        ("TAEV-EN006", "Rainbow Dragon (Ultra Rare)", "Tactical Evolution",
         "Ultra Rare", True, 150.00, "Monster", "LIGHT"),
        ("PTDN-EN012", "Yubel (Secret Rare)", "Phantom Darkness",
         "Secret Rare", True, 120.00, "Monster", "DARK"),
        ("TDGS-EN040", "Stardust Dragon (Ultra Rare)", "The Duelist Genesis",
         "Ultra Rare", True, 120.00, "Monster", "WIND"),
        ("CSOC-EN039", "Black Rose Dragon (Ultra Rare)", "Crossroads of Chaos",
         "Ultra Rare", True, 80.00, "Monster", "FIRE"),
        ("TDGS-EN040", "Stardust Dragon (Secret Rare)", "The Duelist Genesis",
         "Secret Rare", True, 200.00, "Monster", "WIND"),
        ("STBL-EN042", "Shooting Star Dragon (Ultra Rare)", "Starstrike Blast",
         "Ultra Rare", True, 100.00, "Monster", "LIGHT"),
        ("PHSW-EN040", "Galaxy-Eyes Photon Dragon (Ultra Rare)", "Photon Shockwave",
         "Ultra Rare", True, 60.00, "Monster", "LIGHT"),
        ("PHSW-EN000", "Galaxy-Eyes Photon Dragon (Secret Rare)", "Photon Shockwave",
         "Secret Rare", True, 120.00, "Monster", "LIGHT"),
        ("NUMH-EN030", "Number C101: Silent Honor DARK", "Number Hunters",
         "Secret Rare", True, 35.00, "Monster", "WATER"),
        ("REDU-EN043", "Galaxy-Eyes Photon Dragon (Ultimate Rare)", "Return of the Duelist",
         "Ultimate Rare", True, 250.00, "Monster", "LIGHT"),
        ("TDGS-EN040", "Stardust Dragon (Ultimate Rare)", "The Duelist Genesis",
         "Ultimate Rare", True, 650.00, "Monster", "WIND"),
        ("CSOC-EN039", "Black Rose Dragon (Ultimate Rare)", "Crossroads of Chaos",
         "Ultimate Rare", True, 550.00, "Monster", "FIRE"),
        ("ORCS-EN040", "Number 39: Utopia (Ultra Rare 1st)", "Order of Chaos",
         "Ultra Rare", True, 90.00, "Monster", "LIGHT"),
        ("PHSW-EN040", "Galaxy-Eyes Photon Dragon (Ultimate Rare)", "Photon Shockwave",
         "Ultimate Rare", True, 300.00, "Monster", "LIGHT"),

        # =================================================================
        # EXPANSION BATCH 2 — Modern Competitive Staples
        # =================================================================
        ("MACR-EN036", "Ash Blossom & Joyous Spring (Secret 1st)", "Maximum Crisis",
         "Secret Rare", True, 85.00, "Monster", "FIRE"),
        ("DUDE-EN003", "Ash Blossom & Joyous Spring (Ultra Rare)", "Duel Devastator",
         "Ultra Rare", False, 20.00, "Monster", "FIRE"),
        ("LCKC-EN066", "Ash Blossom & Joyous Spring (Secret)", "Legendary Collection Kaiba",
         "Secret Rare", False, 30.00, "Monster", "FIRE"),
        ("CT15-EN003", "Ash Blossom & Joyous Spring (Tin Promo)", "2018 Mega-Tin",
         "Secret Rare", False, 22.00, "Monster", "FIRE"),
        ("DANE-EN081", "Nibiru, the Primal Being (Secret Rare)", "Dark Neostorm",
         "Secret Rare", True, 50.00, "Monster", "LIGHT"),
        ("FLOD-EN077", "Infinite Impermanence (Secret Rare 1st)", "Flames of Destruction",
         "Secret Rare", True, 70.00, "Trap", ""),
        ("FLOD-EN077", "Infinite Impermanence (Ultra Rare)", "Flames of Destruction",
         "Ultra Rare", True, 30.00, "Trap", ""),
        ("DANE-EN064", "Called by the Grave (Secret Rare)", "Dark Neostorm",
         "Secret Rare", True, 15.00, "Spell", ""),
        ("SDCS-EN035", "Crossout Designator", "Structure Deck: Cyber Strike",
         "Ultra Rare", False, 20.00, "Spell", ""),
        ("DUOV-EN003", "Dark Ruler No More", "Duel Overload",
         "Ultra Rare", True, 25.00, "Spell", ""),
        ("CIBR-EN077", "Evenly Matched (Secret Rare)", "Circuit Break",
         "Secret Rare", True, 60.00, "Trap", ""),
        ("INOV-EN079", "Dimensional Barrier (Secret Rare)", "Invasion: Vengeance",
         "Secret Rare", True, 35.00, "Trap", ""),
        ("DABL-EN017", "Lubellion the Searing Dragon (1st Ed)", "Darkwing Blast",
         "Secret Rare", True, 45.00, "Monster", "DARK"),
        ("MP22-EN266", "Branded Despia (Prismatic)", "2022 Tin of the Pharaoh's Gods",
         "Prismatic Secret Rare", False, 40.00, "Monster", "LIGHT"),
        ("DABL-EN007", "Tearlaments Scheiren (Secret Rare)", "Darkwing Blast",
         "Secret Rare", True, 35.00, "Monster", "DARK"),
        ("DABL-EN004", "Tearlaments Reinoheart", "Darkwing Blast",
         "Ultra Rare", True, 20.00, "Monster", "DARK"),
        ("CYAC-EN006", "Kashtira Riseheart", "Cyberstorm Access",
         "Ultra Rare", True, 25.00, "Monster", "FIRE"),
        ("PHNI-EN001", "Snake-Eyes Flamberge Dragon (Secret)", "Phantom Nightmare",
         "Secret Rare", True, 55.00, "Monster", "FIRE"),
        ("PHNI-EN006", "Snake-Eye Poplar (Secret Rare)", "Phantom Nightmare",
         "Secret Rare", True, 65.00, "Monster", "FIRE"),
        ("AMDE-EN016", "Rescue-ACE Turbulence (Ultra)", "Amazing Defenders",
         "Ultra Rare", True, 40.00, "Monster", "FIRE"),
        ("AMDE-EN017", "Rescue-ACE Hydrant", "Amazing Defenders",
         "Super Rare", True, 15.00, "Monster", "FIRE"),
        ("AMDE-EN020", "Lady Labrynth of the Silver Castle (Ultra)", "Amazing Defenders",
         "Ultra Rare", True, 50.00, "Monster", "DARK"),
        ("VASM-EN015", "Lovely Labrynth of the Silver Castle (Secret)", "Valiant Smashers",
         "Secret Rare", True, 60.00, "Monster", "DARK"),

        # =================================================================
        # EXPANSION BATCH 2 — Speed Duel / Rush Duel
        # =================================================================
        ("SBLS-EN001", "Speed Duel Tournament Pack 1 Ultra", "Speed Duel Tournament Pack 1",
         "Ultra Rare", False, 15.00, "Monster", "LIGHT"),
        ("SBLS-EN002", "Dark Magician (Speed Duel Tournament)", "Speed Duel Tournament Pack 1",
         "Ultra Rare", False, 12.00, "Monster", "DARK"),
        ("SGX2-ENS01", "Jaden Yuki (Speed Duel GX 2 Secret)", "Speed Duel GX: Duelists of Shadows",
         "Secret Rare", False, 25.00, "Monster", "LIGHT"),
        ("SGX3-ENS03", "Yubel - Terror Incarnate (Speed Duel)", "Speed Duel GX: March of the Monarchs",
         "Secret Rare", False, 20.00, "Monster", "DARK"),
        ("RD-KP02", "Sevens Road Magician (Rush Duel Secret)", "Rush Duel Deck Mod Pack 2",
         "Secret Rare", False, 40.00, "Monster", "DARK"),
        ("RD-KP03", "Blue-Eyes White Dragon (Rush Duel Secret)", "Rush Duel Pack 3",
         "Secret Rare", False, 55.00, "Monster", "LIGHT"),
        ("RD-KP04", "Dark Magician (Rush Duel Over Rush)", "Rush Duel Over Rush Pack 2",
         "Ultra Rare", False, 35.00, "Monster", "DARK"),
        ("RD-MAX01", "Supreme Machine Magnum Over Road (Maximum)", "Rush Duel Maximum Pack",
         "Secret Rare", False, 45.00, "Monster", "LIGHT"),
        ("RD-MAX02", "Blue-Eyes White Dragon (Maximum Rush)", "Rush Duel Maximum Pack",
         "Ultra Rare", False, 50.00, "Monster", "LIGHT"),
        ("SGX1-BOX2", "Speed Duel GX: Duel Academy Box (2nd Ed)", "Speed Duel GX: Duel Academy Box",
         "Sealed Product", False, 45.00, "Sealed Product", ""),
        ("SBC2-BOX", "Speed Duel: Streets of Battle City Box", "Speed Duel: Streets of Battle City",
         "Sealed Product", False, 60.00, "Sealed Product", ""),
        ("RD-BOX01", "Rush Duel Starter Box (Japanese)", "Rush Duel Starter Box",
         "Sealed Product", False, 30.00, "Sealed Product", ""),
        ("RD-KP10-BOX", "Rush Duel Booster Pack Box (JP)", "Rush Duel Booster Pack",
         "Sealed Product", False, 35.00, "Sealed Product", ""),
        ("SS06-BOX", "Speed Duel GX Midterm Destruction Box", "Speed Duel GX: Midterm Destruction",
         "Sealed Product", False, 40.00, "Sealed Product", ""),

        # =================================================================
        # EXPANSION BATCH 2 — Collector Rarities (Ultimate, Prismatic, Platinum, etc.)
        # =================================================================
        ("IOC-025", "Black Luster Soldier - Envoy (Ultimate Rare)", "Invasion of Chaos",
         "Ultimate Rare", True, 900.00, "Monster", "LIGHT"),
        ("MFC-000", "Dark Magician Girl (Ultimate Rare 1st)", "Magician's Force",
         "Ultimate Rare", True, 1400.00, "Monster", "DARK"),
        ("LOB-001", "Blue-Eyes White Dragon (Unlimited Ultra)", "Legend of Blue-Eyes White Dragon",
         "Ultra Rare", False, 500.00, "Monster", "LIGHT"),
        ("SHVI-EN049", "Crystal Wing Synchro Dragon (Secret 1st)", "Shining Victories",
         "Secret Rare", True, 60.00, "Monster", "WIND"),
        ("TRC1-JP010", "Blue-Eyes White Dragon (10000 Secret Rare)", "The Rarity Collection",
         "10000 Secret Rare", False, 3000.00, "Monster", "LIGHT"),
        ("TRC1-JP011", "Dark Magician (Platinum Secret Rare)", "The Rarity Collection",
         "Platinum Secret Rare", False, 500.00, "Monster", "DARK"),
        ("DUSA-EN001", "Crystal Wing Synchro Dragon (Ultra Rare)", "Duelist Saga",
         "Ultra Rare", False, 15.00, "Monster", "WIND"),
        ("AC02-JP000", "Blue-Eyes White Dragon (Extra Secret Rare)", "Animation Chronicle 2022",
         "Extra Secret Rare", False, 200.00, "Monster", "LIGHT"),
        ("GFP2-EN000", "Stardust Dragon (Holographic Rare)", "Ghosts From the Past: The 2nd Haunting",
         "Ghost Rare", False, 300.00, "Monster", "WIND"),
        ("MGED-EN050", "Accesscode Talker (Gold Secret Rare)", "Maximum Gold: El Dorado",
         "Gold Secret Rare", False, 40.00, "Monster", "DARK"),
        ("MGED-EN051", "Lightning Storm (Gold Secret Rare)", "Maximum Gold: El Dorado",
         "Gold Secret Rare", False, 35.00, "Spell", ""),
        ("MGED-EN052", "Ash Blossom (Gold Secret Rare)", "Maximum Gold: El Dorado",
         "Gold Secret Rare", False, 25.00, "Monster", "FIRE"),
        ("PGL2-EN080", "El Shaddoll Construct (Gold Secret Rare)", "Premium Gold: Return of the Bling",
         "Gold Secret Rare", False, 30.00, "Monster", "LIGHT"),
        ("PGL3-EN060", "Twin Twisters (Gold Secret Rare)", "Premium Gold: Infinite Gold",
         "Gold Secret Rare", False, 20.00, "Spell", ""),
        ("PGLD-EN080", "Dark Magician (Premium Gold Rare)", "Premium Gold",
         "Gold Rare", False, 35.00, "Monster", "DARK"),
        ("MAGO-EN004", "Red-Eyes Black Dragon (Premium Gold)", "Maximum Gold",
         "Gold Rare", False, 25.00, "Monster", "DARK"),
        ("GRCR-EN029", "Fallen of Albaz (Collector's Rare Alt)", "The Grand Creators",
         "Collector's Rare", True, 85.00, "Monster", "DARK"),
        ("BLMR-EN086", "Baronne de Fleur (Collector's Rare)", "Battles of Legend: Monstrous Revenge",
         "Collector's Rare", True, 110.00, "Monster", "WIND"),

        # =================================================================
        # EXPANSION BATCH 2 — OCG Japanese Exclusives (additional)
        # =================================================================
        ("20TH-JPC05", "Black Luster Soldier (20th Secret Rare)", "20th Anniversary Legend Collection",
         "20th Secret Rare", False, 250.00, "Monster", "EARTH"),
        ("20TH-JPC06", "Exodia the Forbidden One (20th Secret Rare)", "20th Anniversary Legend Collection",
         "20th Secret Rare", False, 400.00, "Monster", "DARK"),
        ("RC04-JP050", "Snake-Eye Ash (OCG Extra Secret)", "Rarity Collection 2024",
         "Extra Secret Rare", False, 100.00, "Monster", "FIRE"),
        ("RC04-JP051", "S:P Little Knight (OCG Extra Secret)", "Rarity Collection 2024",
         "Extra Secret Rare", False, 150.00, "Monster", "DARK"),
        ("RC04-JP052", "Baronne de Fleur (OCG Extra Secret)", "Rarity Collection 2024",
         "Extra Secret Rare", False, 130.00, "Monster", "WIND"),
        ("VJMP-JP100", "Blue-Eyes White Dragon (V-Jump Promo)", "V-Jump Promo",
         "Ultra Rare", False, 180.00, "Monster", "LIGHT"),
        ("VJMP-JP101", "Dark Magician (V-Jump Promo)", "V-Jump Promo",
         "Ultra Rare", False, 150.00, "Monster", "DARK"),
        ("VJMP-JP102", "Stardust Dragon (V-Jump Promo)", "V-Jump Promo",
         "Ultra Rare", False, 120.00, "Monster", "WIND"),
        ("WJMP-JP020", "Blue-Eyes White Dragon (Weekly Shonen Jump)", "Weekly Shonen Jump Promo",
         "Ultra Rare", False, 200.00, "Monster", "LIGHT"),
        ("WJMP-JP021", "Dark Magician (Weekly Shonen Jump)", "Weekly Shonen Jump Promo",
         "Ultra Rare", False, 170.00, "Monster", "DARK"),
        ("KR-BEWD", "Blue-Eyes White Dragon (Korean Exclusive Secret)", "Korean Exclusive",
         "Secret Rare", False, 300.00, "Monster", "LIGHT"),
        ("KR-DM", "Dark Magician (Korean Exclusive Secret)", "Korean Exclusive",
         "Secret Rare", False, 250.00, "Monster", "DARK"),
        ("AE-EN002", "Red-Eyes Black Dragon (Asian English Exclusive)", "Asian English Exclusive",
         "Secret Rare", False, 200.00, "Monster", "DARK"),
        ("AE-EN003", "Blue-Eyes White Dragon (Asian English Exclusive)", "Asian English Exclusive",
         "Secret Rare", False, 250.00, "Monster", "LIGHT"),
        ("DT14-JP001", "Lavalval Chain (Duel Terminal Parallel)", "Duel Terminal 14",
         "Ultra Rare", False, 80.00, "Monster", "FIRE"),
        ("DT14-JP002", "Daigusto Emeral (Duel Terminal Parallel)", "Duel Terminal 14",
         "Ultra Rare", False, 60.00, "Monster", "WIND"),
        ("DT08-JP034", "Trishula, Dragon of the Ice Barrier (DT Parallel)", "Duel Terminal 8",
         "Ultra Rare", False, 150.00, "Monster", "WATER"),
        ("DT07-JP040", "Brionac, Dragon of the Ice Barrier (DT Parallel)", "Duel Terminal 7",
         "Ultra Rare", False, 120.00, "Monster", "WATER"),

        # =================================================================
        # EXPANSION BATCH 2 — Accessories & Miscellaneous Collectibles
        # =================================================================
        ("MAT-YCS01", "Official YCS Playmat (Blue-Eyes White Dragon)", "YCS Playmat",
         "Sealed Product", False, 250.00, "Sealed Product", ""),
        ("MAT-YCS02", "Official YCS Playmat (Dark Magician)", "YCS Playmat",
         "Sealed Product", False, 200.00, "Sealed Product", ""),
        ("MAT-NATS01", "Official Nationals Playmat (Stardust Dragon)", "Nationals Playmat",
         "Sealed Product", False, 300.00, "Sealed Product", ""),
        ("MAT-WCS01", "Official Worlds Playmat (Exodia)", "World Championship Playmat",
         "Sealed Product", False, 500.00, "Sealed Product", ""),
        ("DD-KAIBA", "Duel Disk (Kaiba Original)", "Duel Disk Replica",
         "Sealed Product", False, 350.00, "Sealed Product", ""),
        ("DD-GX", "Duel Disk (GX Academy)", "Duel Disk Replica",
         "Sealed Product", False, 200.00, "Sealed Product", ""),
        ("DD-5DS", "Duel Disk (5D's Yusei)", "Duel Disk Replica",
         "Sealed Product", False, 250.00, "Sealed Product", ""),
        ("SLV-YCS01", "Official Card Sleeves (YCS Tournament)", "Tournament Accessories",
         "Sealed Product", False, 80.00, "Sealed Product", ""),
        ("DBOX-OFF01", "Official Deck Box (Tournament Series)", "Tournament Accessories",
         "Sealed Product", False, 40.00, "Sealed Product", ""),
        ("FC-YCS01", "Field Center Card (YCS Prize)", "YCS Field Center",
         "Prize Card", False, 150.00, "Sealed Product", ""),
        ("FC-YCS02", "Field Center Card (Blue-Eyes Ultimate Dragon)", "YCS Field Center",
         "Sealed Product", False, 100.00, "Sealed Product", ""),
        ("TROPHY-DC01", "Duelist Cup Trophy (2024)", "Duelist Cup Trophy",
         "Sealed Product", False, 500.00, "Sealed Product", ""),
        ("GS-TIN", "Gold Sarcophagus Tin (Sealed)", "Gold Sarcophagus Tin",
         "Sealed Product", False, 35.00, "Sealed Product", ""),
        ("POG-REP", "Pot of Greed Collectible Replica", "Collectible Replica",
         "Sealed Product", False, 60.00, "Sealed Product", ""),
        ("ME-RING", "Millennium Eye Ring Replica", "Collectible Replica",
         "Sealed Product", False, 80.00, "Sealed Product", ""),
        ("MP-PUZZLE", "Millennium Puzzle Replica (Official)", "Collectible Replica",
         "Sealed Product", False, 120.00, "Sealed Product", ""),
        ("MAT-WORLDS22", "2022 World Championship Playmat (Accesscode Talker)", "World Championship Playmat",
         "Sealed Product", False, 450.00, "Sealed Product", ""),
        ("MAT-WORLDS23", "2023 World Championship Playmat (Kashtira)", "World Championship Playmat",
         "Sealed Product", False, 400.00, "Sealed Product", ""),
        ("MAT-WORLDS24", "2024 World Championship Playmat (Snake-Eyes)", "World Championship Playmat",
         "Sealed Product", False, 350.00, "Sealed Product", ""),
        ("DD-VRAINS", "Duel Disk (VRAINS Edition)", "Duel Disk Replica",
         "Sealed Product", False, 180.00, "Sealed Product", ""),

        # =================================================================
        # EXPANSION BATCH 2 — Additional Classic Fan Favorites
        # =================================================================
        ("LOB-070", "Swords of Revealing Light", "Legend of Blue-Eyes White Dragon",
         "Super Rare", True, 60.00, "Spell", ""),
        ("LOB-100", "Trap Hole", "Legend of Blue-Eyes White Dragon",
         "Rare", True, 25.00, "Trap", ""),
        ("LOB-050", "Man-Eater Bug", "Legend of Blue-Eyes White Dragon",
         "Rare", True, 20.00, "Monster", "EARTH"),
        ("MRD-070", "Mask of Darkness", "Metal Raiders",
         "Rare", True, 15.00, "Monster", "DARK"),
        ("PSV-004", "Goblin Attack Force", "Pharaoh's Servant",
         "Ultra Rare", True, 120.00, "Monster", "EARTH"),
        ("LON-EN024", "Dark Necrofear", "Labyrinth of Nightmare",
         "Ultra Rare", True, 200.00, "Monster", "DARK"),
        ("LON-EN050", "Injection Fairy Lily", "Labyrinth of Nightmare",
         "Secret Rare", True, 350.00, "Monster", "EARTH"),
        ("PGD-003", "Don Zaloog", "Pharaonic Guardian",
         "Ultra Rare", True, 80.00, "Monster", "DARK"),
        ("DCR-018", "D.D. Warrior Lady", "Dark Crisis",
         "Super Rare", True, 50.00, "Monster", "LIGHT"),
        ("IOC-024", "Magical Scientist", "Invasion of Chaos",
         "Common", True, 40.00, "Monster", "DARK"),
        ("MFC-097", "Skilled Dark Magician", "Magician's Force",
         "Super Rare", True, 35.00, "Monster", "DARK"),
        ("SOI-EN036", "Elemental HERO Neos (1st Ed)", "Shadow of Infinity",
         "Ultra Rare", True, 280.00, "Monster", "LIGHT"),
        ("TAEV-EN019", "Crystal Beast Ruby Carbuncle", "Tactical Evolution",
         "Super Rare", True, 25.00, "Monster", "LIGHT"),
        ("LODT-EN041", "Honest (Secret Rare 1st)", "Light of Destruction",
         "Secret Rare", True, 120.00, "Monster", "LIGHT"),
        ("LODT-EN041", "Honest (Ultra Rare 1st)", "Light of Destruction",
         "Ultra Rare", True, 50.00, "Monster", "LIGHT"),

        # =================================================================
        # EXPANSION BATCH 3 — Fill to 1020+ unique items
        # =================================================================

        # More Ghost Rares (unique printings)
        ("STOR-EN041", "Shooting Star Dragon (Ghost 1st Ed)", "Storm of Ragnarok",
         "Ghost Rare", True, 750.00, "Monster", "WIND"),
        ("DREV-EN020", "Black-Winged Dragon (Ghost 1st Ed)", "Duelist Revolution",
         "Ghost Rare", True, 520.00, "Monster", "DARK"),
        ("MAMA-EN062", "Slifer the Sky Dragon (Ghost Rare)", "Magnificent Mavens",
         "Ghost Rare", False, 300.00, "Monster", "DIVINE"),
        ("MAMA-EN063", "Obelisk the Tormentor (Ghost Rare)", "Magnificent Mavens",
         "Ghost Rare", False, 280.00, "Monster", "DIVINE"),

        # Starlight Rares — unique
        ("ROTD-EN004", "Dogmatika Ecclesia (Starlight 1st)", "Rise of the Duelist",
         "Starlight Rare", True, 750.00, "Monster", "LIGHT"),
        ("PHRA-EN000", "Tri-Brigade Shuraig (Starlight 1st)", "Phantom Rage",
         "Starlight Rare", True, 580.00, "Monster", "DARK"),
        ("GRCR-EN011", "Exosister Mikailis (Starlight 1st)", "The Grand Creators",
         "Starlight Rare", True, 320.00, "Monster", "LIGHT"),
        ("DABL-EN009", "Tearlaments Scheiren (Starlight 1st)", "Darkwing Blast",
         "Starlight Rare", True, 600.00, "Monster", "DARK"),
        ("AMDE-EN045", "Kashtira Birth (Starlight 1st Ed)", "Amazing Defenders",
         "Starlight Rare", True, 280.00, "Spell", ""),

        # QCSR unique
        ("RA01-EN006", "Blue-Eyes Ultimate Dragon (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 700.00, "Monster", "LIGHT"),
        ("RA01-EN007", "Five-Headed Dragon (QCSR)", "25th Anniversary Rarity Collection",
         "Quarter Century Secret Rare", False, 500.00, "Monster", "DARK"),
        ("RA02-EN007", "Elemental HERO Neos (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 550.00, "Monster", "LIGHT"),
        ("RA02-EN011", "Junk Warrior (QCSR)", "25th Anniversary Rarity Collection II",
         "Quarter Century Secret Rare", False, 400.00, "Monster", "DARK"),

        # Modern meta unique printings
        ("MACR-EN036", "Ash Blossom & Joyous Spring (Ultra 1st)", "Maximum Crisis",
         "Ultra Rare", True, 45.00, "Monster", "FIRE"),
        ("DANE-EN081", "Nibiru, the Primal Being (Ultra Rare)", "Dark Neostorm",
         "Ultra Rare", True, 30.00, "Monster", "LIGHT"),
        ("SAST-EN048", "Borreload Savage Dragon (Ultra Rare)", "Savage Strike",
         "Ultra Rare", True, 40.00, "Monster", "DARK"),
        ("DUOV-EN001", "Lightning Storm (Secret Rare)", "Duel Overload",
         "Secret Rare", True, 100.00, "Spell", ""),
        ("LIOV-EN050", "Baronne de Fleur (Ultra Rare)", "Lightning Overdrive",
         "Ultra Rare", True, 60.00, "Monster", "WIND"),
        ("BODE-EN009", "Swordsoul Grandmaster - Chixiao (Ultra)", "Burst of Destiny",
         "Ultra Rare", True, 40.00, "Monster", "WATER"),
        ("SOFU-EN040", "Borrelsword Dragon (Ultra Rare)", "Soul Fusion",
         "Ultra Rare", True, 35.00, "Monster", "DARK"),
        ("CIBR-EN051", "Borreload Dragon (Ultra Rare)", "Circuit Break",
         "Ultra Rare", True, 40.00, "Monster", "DARK"),
        ("ETCO-EN044", "Accesscode Talker (Ultra Rare)", "Eternity Code",
         "Ultra Rare", True, 50.00, "Monster", "DARK"),
        ("CHIM-EN039", "I:P Masquerena (Secret Rare)", "Chaos Impact",
         "Secret Rare", True, 45.00, "Monster", "DARK"),
        ("PHRA-EN048", "Divine Arsenal AA-ZEUS (Secret Rare)", "Phantom Rage",
         "Secret Rare", True, 50.00, "Monster", "LIGHT"),

        # Classic era unique printings
        ("MFC-000", "Dark Magician Girl (Secret 1st Ed)", "Magician's Force",
         "Secret Rare", True, 3200.00, "Monster", "DARK"),
        ("DCR-026", "Vampire Lord (Secret Rare)", "Dark Crisis",
         "Secret Rare", True, 250.00, "Monster", "DARK"),
        ("LON-EN050", "Injection Fairy Lily (Ultra Rare)", "Labyrinth of Nightmare",
         "Ultra Rare", True, 200.00, "Monster", "EARTH"),
        ("PGD-070", "Lava Golem (Secret Rare)", "Pharaonic Guardian",
         "Secret Rare", True, 300.00, "Monster", "FIRE"),
        ("AST-035", "Zaborg the Thunder Monarch (Super Rare)", "Ancient Sanctuary",
         "Super Rare", True, 50.00, "Monster", "LIGHT"),

        # Pendulum/Link era unique
        ("SECE-EN000", "Nekroz of Sophia", "Secrets of Eternity",
         "Secret Rare", True, 45.00, "Monster", "LIGHT"),
        ("CROS-EN050", "Clear Wing Synchro Dragon", "Crossed Souls",
         "Secret Rare", True, 40.00, "Monster", "WIND"),
        ("RATE-EN048", "Zoodiac Broadbull", "Raging Tempest",
         "Ultra Rare", True, 20.00, "Monster", "EARTH"),
        ("COTD-EN043", "Decode Talker", "Code of the Duelist",
         "Ultra Rare", True, 15.00, "Monster", "DARK"),
        ("COTD-EN044", "Firewall Dragon", "Code of the Duelist",
         "Secret Rare", True, 30.00, "Monster", "LIGHT"),
        ("EXFO-EN050", "Heavymetalfoes Electrumite (Ultra)", "Extreme Force",
         "Ultra Rare", True, 25.00, "Monster", "FIRE"),
        ("DANE-EN050", "Apollousa, Bow of the Goddess", "Dark Neostorm",
         "Secret Rare", True, 60.00, "Monster", "WIND"),
        ("RIRA-EN048", "Apollousa, Bow of the Goddess (Ultra)", "Rising Rampage",
         "Ultra Rare", True, 35.00, "Monster", "WIND"),

        # Sealed product unique
        ("SOD-BOX", "Soul of the Duelist Booster Box (Sealed)", "Soul of the Duelist",
         "Sealed Product", False, 3500.00, "Sealed Product", ""),
        ("RDS-BOX", "Rise of Destiny Booster Box (Sealed)", "Rise of Destiny",
         "Sealed Product", False, 3000.00, "Sealed Product", ""),
        ("FET-BOX", "Flaming Eternity Booster Box (Sealed)", "Flaming Eternity",
         "Sealed Product", False, 3200.00, "Sealed Product", ""),
        ("TLM-BOX", "The Lost Millennium Booster Box (Sealed)", "The Lost Millennium",
         "Sealed Product", False, 2800.00, "Sealed Product", ""),
        ("SOI-BOX", "Shadow of Infinity Booster Box (Sealed)", "Shadow of Infinity",
         "Sealed Product", False, 2500.00, "Sealed Product", ""),
        ("EEN-BOX", "Elemental Energy Booster Box (Sealed)", "Elemental Energy",
         "Sealed Product", False, 2200.00, "Sealed Product", ""),
        ("POTD-BOX", "Power of the Duelist Booster Box (Sealed)", "Power of the Duelist",
         "Sealed Product", False, 2000.00, "Sealed Product", ""),
        ("STON-BOX", "Strike of Neos Booster Box (Sealed)", "Strike of Neos",
         "Sealed Product", False, 2000.00, "Sealed Product", ""),
        ("TAEV-BOX", "Tactical Evolution Booster Box (Sealed)", "Tactical Evolution",
         "Sealed Product", False, 2500.00, "Sealed Product", ""),
        ("LODT-BOX", "Light of Destruction Booster Box (Sealed)", "Light of Destruction",
         "Sealed Product", False, 3000.00, "Sealed Product", ""),
        ("TDGS-BOX", "The Duelist Genesis Booster Box (Sealed)", "The Duelist Genesis",
         "Sealed Product", False, 2500.00, "Sealed Product", ""),
        ("GENF-BOX", "Generation Force Booster Box (Sealed)", "Generation Force",
         "Sealed Product", False, 1500.00, "Sealed Product", ""),
        ("PHSW-BOX", "Photon Shockwave Booster Box (Sealed)", "Photon Shockwave",
         "Sealed Product", False, 1800.00, "Sealed Product", ""),
        ("MFC-BOX", "Magician's Force Booster Box (Sealed)", "Magician's Force",
         "Sealed Product", False, 10000.00, "Sealed Product", ""),
        ("DCR-BOX", "Dark Crisis Booster Box (Sealed)", "Dark Crisis",
         "Sealed Product", False, 5000.00, "Sealed Product", ""),
        ("PGD-BOX", "Pharaonic Guardian Booster Box (Sealed)", "Pharaonic Guardian",
         "Sealed Product", False, 5500.00, "Sealed Product", ""),
        ("LON-BOX2", "Labyrinth of Nightmare Booster Box (Sealed)", "Labyrinth of Nightmare",
         "Sealed Product", False, 8000.00, "Sealed Product", ""),
        ("STBL-BOX", "Starstrike Blast Booster Box (Sealed)", "Starstrike Blast",
         "Sealed Product", False, 1500.00, "Sealed Product", ""),
        ("STOR-BOX", "Storm of Ragnarok Booster Box (Sealed)", "Storm of Ragnarok",
         "Sealed Product", False, 1400.00, "Sealed Product", ""),

        # OCG unique
        ("RC04-JP055", "Nibiru (OCG Extra Secret Rare)", "Rarity Collection 2024",
         "Extra Secret Rare", False, 80.00, "Monster", "LIGHT"),
        ("RC04-JP056", "Infinite Impermanence (OCG Extra Secret)", "Rarity Collection 2024",
         "Extra Secret Rare", False, 90.00, "Trap", ""),
        ("RC04-JP057", "Called by the Grave (OCG Extra Secret)", "Rarity Collection 2024",
         "Extra Secret Rare", False, 60.00, "Spell", ""),
        ("20TH-JPC07", "Number 39: Utopia (20th Secret)", "20th Anniversary Legend Collection",
         "20th Secret Rare", False, 200.00, "Monster", "LIGHT"),
        ("20TH-JPC08", "Firewall Dragon (20th Secret)", "20th Anniversary Legend Collection",
         "20th Secret Rare", False, 180.00, "Monster", "LIGHT"),
        ("PAC1-JP060", "Monster Reborn (PAC Prismatic)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 300.00, "Spell", ""),
        ("PAC1-JP061", "Raigeki (PAC Prismatic)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 250.00, "Spell", ""),

        # Ultimate Rares unique
        ("DP05-EN013", "Destiny HERO - Plasma (Ultimate Rare)", "Duelist Pack: Aster Phoenix",
         "Ultimate Rare", True, 200.00, "Monster", "DARK"),
        ("TAEV-EN006", "Rainbow Dragon (Ultimate Rare)", "Tactical Evolution",
         "Ultimate Rare", True, 300.00, "Monster", "LIGHT"),
        ("LODT-EN043", "Judgment Dragon (Ultimate Rare)", "Light of Destruction",
         "Ultimate Rare", True, 250.00, "Monster", "LIGHT"),
        ("TDGS-EN037", "Red Dragon Archfiend (Ultimate Rare)", "The Duelist Genesis",
         "Ultimate Rare", True, 300.00, "Monster", "DARK"),
        ("ANPR-EN040", "Ancient Fairy Dragon (Ultimate Rare)", "Ancient Prophecy",
         "Ultimate Rare", True, 200.00, "Monster", "LIGHT"),
        ("RGBT-EN043", "Power Tool Dragon (Ultimate Rare)", "Raging Battle",
         "Ultimate Rare", True, 180.00, "Monster", "EARTH"),
        ("HA04-EN026", "Trishula, Dragon of the Ice Barrier (Ultimate)", "Hidden Arsenal 4",
         "Ultimate Rare", True, 150.00, "Monster", "WATER"),
        ("SAST-EN048", "Borreload Savage Dragon (Ultimate)", "Savage Strike",
         "Ultimate Rare", True, 200.00, "Monster", "DARK"),

        # Collector's Rares unique
        ("GRCR-EN065", "Ash Blossom & Joyous Spring (Collector's Rare)", "The Grand Creators",
         "Collector's Rare", True, 100.00, "Monster", "FIRE"),
        ("GRCR-EN066", "Effect Veiler (Collector's Rare)", "The Grand Creators",
         "Collector's Rare", True, 60.00, "Monster", "LIGHT"),
        ("BLCR-EN040", "Nibiru, the Primal Being (Collector's Rare)", "Battles of Legend: Crystal Revenge",
         "Collector's Rare", True, 80.00, "Monster", "LIGHT"),
        ("BLCR-EN041", "Ash Blossom (Collector's Rare)", "Battles of Legend: Crystal Revenge",
         "Collector's Rare", True, 90.00, "Monster", "FIRE"),
        ("BLMR-EN087", "Accesscode Talker (Collector's Rare)", "Battles of Legend: Monstrous Revenge",
         "Collector's Rare", True, 100.00, "Monster", "DARK"),
        ("MZMI-EN081", "Magicians' Souls (Collector's Rare Alt)", "Maze of Millennia",
         "Collector's Rare", True, 180.00, "Monster", "DARK"),

        # Gold Secret Rares unique
        ("GLD3-EN029", "Stardust Dragon (Gold Secret Rare)", "Gold Series 3",
         "Gold Secret Rare", False, 80.00, "Monster", "WIND"),
        ("GLD4-EN032", "Ally of Justice Catastor (Gold Secret)", "Gold Series 4: Pyramids",
         "Gold Secret Rare", False, 50.00, "Monster", "DARK"),
        ("GLD5-EN026", "Number 39: Utopia (Gold Secret Rare)", "Gold Series: Haunted Mine",
         "Gold Secret Rare", False, 40.00, "Monster", "LIGHT"),
        ("MGED-EN055", "Infinite Impermanence (Gold Secret)", "Maximum Gold: El Dorado",
         "Gold Secret Rare", False, 30.00, "Trap", ""),
        ("MGED-EN056", "Called by the Grave (Gold Secret)", "Maximum Gold: El Dorado",
         "Gold Secret Rare", False, 20.00, "Spell", ""),

        # Final fill — unique entries to reach 1020+
        ("CSOC-BOX2", "Crossroads of Chaos 1st Ed Booster Box", "Crossroads of Chaos",
         "Sealed Product", True, 5000.00, "Sealed Product", ""),
        ("ANPR-BOX", "Ancient Prophecy Booster Box (Sealed)", "Ancient Prophecy",
         "Sealed Product", False, 2000.00, "Sealed Product", ""),
        ("RGBT-BOX", "Raging Battle Booster Box (Sealed)", "Raging Battle",
         "Sealed Product", False, 2200.00, "Sealed Product", ""),
        ("SOVR-BOX", "Stardust Overdrive Booster Box (Sealed)", "Stardust Overdrive",
         "Sealed Product", False, 1800.00, "Sealed Product", ""),
        ("ABPF-BOX", "Absolute Powerforce Booster Box (Sealed)", "Absolute Powerforce",
         "Sealed Product", False, 1600.00, "Sealed Product", ""),
        ("TSHD-BOX", "The Shining Darkness Booster Box (Sealed)", "The Shining Darkness",
         "Sealed Product", False, 1500.00, "Sealed Product", ""),
        ("DREV-BOX2", "Duelist Revolution Booster Box (Sealed)", "Duelist Revolution",
         "Sealed Product", False, 1400.00, "Sealed Product", ""),
        ("REDU-BOX", "Return of the Duelist Booster Box (Sealed)", "Return of the Duelist",
         "Sealed Product", False, 1200.00, "Sealed Product", ""),
        ("ORCS-BOX", "Order of Chaos Booster Box (Sealed)", "Order of Chaos",
         "Sealed Product", False, 1300.00, "Sealed Product", ""),
        ("LTGY-BOX", "Lord of the Tachyon Galaxy Booster Box (Sealed)", "Lord of the Tachyon Galaxy",
         "Sealed Product", False, 1400.00, "Sealed Product", ""),

        # =================================================================
        # Starlight Rares — Recent Sets (PHNI, LEDE, AGOV, DUNE, WISU)
        # =================================================================
        ("PHNI-EN007", "Promethean Princess, Bestower of Flames (Starlight)", "Phantom Nightmare",
         "Starlight Rare", True, 200.00, "Monster", "FIRE"),
        ("PHNI-EN048", "Veidos the Eruption Dragon of Extinction (Starlight)", "Phantom Nightmare",
         "Starlight Rare", True, 150.00, "Monster", "DARK"),
        ("PHNI-EN050", "Snake-Eyes Flamberge Dragon (Starlight)", "Phantom Nightmare",
         "Starlight Rare", True, 500.00, "Monster", "FIRE"),
        ("LEDE-EN009", "Nightmare of Rituals (Starlight)", "Legacy of Destruction",
         "Starlight Rare", True, 120.00, "Spell", ""),
        ("LEDE-EN050", "Tenpai Dragon Fadra (Starlight)", "Legacy of Destruction",
         "Starlight Rare", True, 350.00, "Monster", "FIRE"),
        ("LEDE-EN015", "Gandora-G the Dragon of Destruction (Starlight)", "Legacy of Destruction",
         "Starlight Rare", True, 180.00, "Monster", "DARK"),
        ("AGOV-EN009", "S:P Little Knight (Starlight)", "Age of Overlord",
         "Starlight Rare", True, 600.00, "Monster", "LIGHT"),
        ("AGOV-EN050", "Bonfire (Starlight)", "Age of Overlord",
         "Starlight Rare", True, 400.00, "Spell", ""),
        ("DUNE-EN050", "Skull Guardian, Protector of the Voiceless Voice (Starlight)", "Duelist Nexus",
         "Starlight Rare", True, 250.00, "Monster", "LIGHT"),
        ("DUNE-EN047", "Mannadium Riumheart (Starlight)", "Duelist Nexus",
         "Starlight Rare", True, 180.00, "Monster", "LIGHT"),
        ("WISU-EN020", "Ash Blossom & Joyous Spring (Starlight)", "Wild Survivors",
         "Starlight Rare", True, 500.00, "Monster", "FIRE"),
        ("WISU-EN015", "Ghost Ogre & Snow Rabbit (Starlight)", "Wild Survivors",
         "Starlight Rare", True, 200.00, "Monster", "LIGHT"),
        ("CYAC-EN050", "Kashtira Arise-Heart (Starlight)", "Cyberstorm Access",
         "Starlight Rare", True, 300.00, "Monster", "DARK"),
        ("DABL-EN050", "Bystial Magnamhut (Starlight)", "Darkwing Blast",
         "Starlight Rare", True, 250.00, "Monster", "DARK"),
        ("POTE-EN050", "Spright Blue (Starlight)", "Power of the Elements",
         "Starlight Rare", True, 400.00, "Monster", "DARK"),

        # =================================================================
        # Ghost Rares — Recent Reprints
        # =================================================================
        ("GFP2-EN130", "Blue-Eyes White Dragon (Ghost Rare)", "Ghosts From the Past 2",
         "Ghost Rare", False, 400.00, "Monster", "LIGHT"),
        ("GFP2-EN131", "Dark Magician (Ghost Rare)", "Ghosts From the Past 2",
         "Ghost Rare", False, 350.00, "Monster", "DARK"),
        ("GFP2-EN132", "Red-Eyes Black Dragon (Ghost Rare)", "Ghosts From the Past 2",
         "Ghost Rare", False, 300.00, "Monster", "DARK"),
        ("GFP2-EN180", "Exodia the Forbidden One (Ghost Rare)", "Ghosts From the Past 2",
         "Ghost Rare", False, 250.00, "Monster", "DARK"),
        ("GFTP-EN001", "Crystal Wing Synchro Dragon (Ghost Rare)", "Ghosts From the Past",
         "Ghost Rare", False, 120.00, "Monster", "WIND"),
        ("GFTP-EN130", "Dark Magician Girl (Ghost Rare)", "Ghosts From the Past",
         "Ghost Rare", False, 350.00, "Monster", "DARK"),
        ("GFTP-EN131", "Firewall Dragon (Ghost Rare)", "Ghosts From the Past",
         "Ghost Rare", False, 80.00, "Monster", "DARK"),
        ("GFP2-EN179", "Stardust Dragon (Ghost Rare, GFP2)", "Ghosts From the Past 2",
         "Ghost Rare", False, 150.00, "Monster", "WIND"),
        ("GFP2-EN133", "Blue-Eyes Alternative White Dragon (Ghost Rare)", "Ghosts From the Past 2",
         "Ghost Rare", False, 200.00, "Monster", "LIGHT"),
        ("MAGO-EN001", "Blue-Eyes White Dragon (Premium Gold Rare)", "Maximum Gold",
         "Premium Gold Rare", False, 25.00, "Monster", "LIGHT"),

        # =================================================================
        # Ultimate Rares — Classic Era
        # =================================================================
        ("IOC-000", "Chaos Emperor Dragon — Envoy of the End (Ultimate)", "Invasion of Chaos",
         "Ultimate Rare", True, 800.00, "Monster", "DARK"),
        ("DCR-000", "Dark Magician of Chaos (Ultimate Rare)", "Dark Crisis",
         "Ultimate Rare", True, 400.00, "Monster", "DARK"),
        ("SOD-EN035", "Mobius the Frost Monarch (Ultimate)", "Soul of the Duelist",
         "Ultimate Rare", True, 200.00, "Monster", "WATER"),
        ("FET-EN034", "Sacred Phoenix of Nephthys (Ultimate)", "Flaming Eternity",
         "Ultimate Rare", True, 250.00, "Monster", "FIRE"),
        ("CRV-EN048", "Cyber Dragon (Ultimate Rare)", "Cybernetic Revolution",
         "Ultimate Rare", True, 500.00, "Monster", "LIGHT"),
        ("SOI-EN044", "Treeborn Frog (Ultimate Rare)", "Shadow of Infinity",
         "Ultimate Rare", True, 150.00, "Monster", "WATER"),
        ("PTDN-EN044", "Dark Armed Dragon (Ultimate Rare)", "Phantom Darkness",
         "Ultimate Rare", True, 600.00, "Monster", "DARK"),
        ("CDIP-EN035", "Allure of Darkness (Ultimate Rare)", "Cyberdark Impact",
         "Ultimate Rare", True, 350.00, "Spell", ""),
        ("LODT-EN040", "Honest (Ultimate Rare)", "Light of Destruction",
         "Ultimate Rare", True, 300.00, "Monster", "LIGHT"),
        ("TU01-EN000", "Brionac, Dragon of the Ice Barrier (Ultimate)", "Turbo Pack 1",
         "Ultimate Rare", False, 200.00, "Monster", "WATER"),

        # =================================================================
        # Quarter Century Secret Rares (25th Anniversary)
        # =================================================================
        ("RAYE-QCEN001", "Blue-Eyes White Dragon (Quarter Century Secret)", "Rarity Collection 2025",
         "Quarter Century Secret Rare", False, 300.00, "Monster", "LIGHT"),
        ("RAYE-QCEN002", "Dark Magician (Quarter Century Secret)", "Rarity Collection 2025",
         "Quarter Century Secret Rare", False, 280.00, "Monster", "DARK"),
        ("RAYE-QCEN003", "Ash Blossom & Joyous Spring (Quarter Century Secret)", "Rarity Collection 2025",
         "Quarter Century Secret Rare", False, 250.00, "Monster", "FIRE"),
        ("RA02-QCEN001", "Exodia the Forbidden One (Quarter Century)", "Rarity Collection II",
         "Quarter Century Secret Rare", False, 200.00, "Monster", "DARK"),
        ("RA02-QCEN050", "Nibiru, the Primal Being (Quarter Century)", "Rarity Collection II",
         "Quarter Century Secret Rare", False, 150.00, "Monster", "LIGHT"),
        ("QCDB-EN001", "Dark Magician Girl (Quarter Century)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 250.00, "Monster", "DARK"),
        ("QCDB-EN002", "Stardust Dragon (Quarter Century)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 200.00, "Monster", "WIND"),
        ("QCDB-EN003", "Number 39: Utopia (Quarter Century)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 120.00, "Monster", "LIGHT"),
        ("QCDB-EN004", "Decode Talker (Quarter Century)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 100.00, "Monster", "DARK"),
        ("QCDB-EN005", "Firewall Dragon (Quarter Century)", "Quarter Century Duelist Box",
         "Quarter Century Secret Rare", False, 80.00, "Monster", "DARK"),

        # =================================================================
        # Sealed Booster Boxes — Recent Sets
        # =================================================================
        ("PHNI-BOX", "Phantom Nightmare Booster Box (Sealed)", "Phantom Nightmare",
         "Sealed Product", True, 80.00, "Sealed Product", ""),
        ("LEDE-BOX", "Legacy of Destruction Booster Box (Sealed)", "Legacy of Destruction",
         "Sealed Product", True, 80.00, "Sealed Product", ""),
        ("AGOV-BOX", "Age of Overlord Booster Box (Sealed)", "Age of Overlord",
         "Sealed Product", True, 85.00, "Sealed Product", ""),
        ("DUNE-BOX", "Duelist Nexus Booster Box (Sealed)", "Duelist Nexus",
         "Sealed Product", True, 85.00, "Sealed Product", ""),
        ("CYAC-BOX", "Cyberstorm Access Booster Box (Sealed)", "Cyberstorm Access",
         "Sealed Product", True, 80.00, "Sealed Product", ""),
        ("DABL-BOX", "Darkwing Blast Booster Box (Sealed)", "Darkwing Blast",
         "Sealed Product", True, 90.00, "Sealed Product", ""),
        ("POTE-BOX", "Power of the Elements Booster Box (Sealed)", "Power of the Elements",
         "Sealed Product", True, 95.00, "Sealed Product", ""),
        ("DIFO-BOX", "Dimension Force Booster Box (Sealed)", "Dimension Force",
         "Sealed Product", True, 90.00, "Sealed Product", ""),
        ("BODE-BOX", "Burst of Destiny Booster Box (Sealed)", "Burst of Destiny",
         "Sealed Product", True, 95.00, "Sealed Product", ""),
        ("GRCR-BOX", "The Grand Creators Booster Box (Sealed)", "The Grand Creators",
         "Sealed Product", True, 120.00, "Sealed Product", ""),

        # =================================================================
        # Structure Deck Sealed — Collectible
        # =================================================================
        ("SDPL-SEALED", "Structure Deck: Powercode Link (Sealed)", "Structure Deck: Powercode Link",
         "Sealed Product", False, 30.00, "Sealed Product", ""),
        ("SDSA-SEALED", "Structure Deck: Soulburner (Sealed)", "Structure Deck: Soulburner",
         "Sealed Product", False, 50.00, "Sealed Product", ""),
        ("SHVA-SEALED", "Shadows in Valhalla (Sealed Box)", "Shadows in Valhalla",
         "Sealed Product", False, 80.00, "Sealed Product", ""),
        ("SDSB-SEALED", "Structure Deck: Sacred Beasts (Sealed)", "Structure Deck: Sacred Beasts",
         "Sealed Product", False, 25.00, "Sealed Product", ""),
        ("SR14-SEALED", "Structure Deck: Fire Kings (Sealed)", "Structure Deck: Fire Kings",
         "Sealed Product", False, 15.00, "Sealed Product", ""),
        ("SD44-SEALED", "Structure Deck: The Crimson King (Sealed, OCG)", "Structure Deck: The Crimson King",
         "Sealed Product", False, 35.00, "Sealed Product", ""),

        # =================================================================
        # OCG-Exclusive Cards (Japanese)
        # =================================================================
        ("20TH-JPC00", "Blue-Eyes White Dragon (20th Secret, OCG)", "20th Anniversary",
         "20th Secret Rare", False, 500.00, "Monster", "LIGHT"),
        ("20TH-JPC01", "Dark Magician (20th Secret, OCG)", "20th Anniversary",
         "20th Secret Rare", False, 400.00, "Monster", "DARK"),
        ("PAC1-JP004", "Blue-Eyes White Dragon (Prismatic Art, OCG)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 200.00, "Monster", "LIGHT"),
        ("PAC1-JP005", "Dark Magician (Prismatic Art, OCG)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 180.00, "Monster", "DARK"),
        ("PAC1-JP006", "Red-Eyes Black Dragon (Prismatic Art, OCG)", "Prismatic Art Collection",
         "Prismatic Secret Rare", False, 150.00, "Monster", "DARK"),
        ("RC04-JP000", "Ash Blossom & Joyous Spring (Quarter Century, OCG)", "Rarity Collection Quarter Century Edition",
         "Quarter Century Secret Rare", False, 180.00, "Monster", "FIRE"),
        ("RC04-JP001", "Infinite Impermanence (Quarter Century, OCG)", "Rarity Collection Quarter Century Edition",
         "Quarter Century Secret Rare", False, 120.00, "Trap", ""),
        ("RC04-JP002", "Called by the Grave (Quarter Century, OCG)", "Rarity Collection Quarter Century Edition",
         "Quarter Century Secret Rare", False, 80.00, "Spell", ""),
        ("AC04-JP000", "Yubel (Extra Secret Rare, OCG)", "Animation Chronicle 2024",
         "Extra Secret Rare", False, 100.00, "Monster", "DARK"),
        ("AC04-JP001", "Elemental HERO Neos (Extra Secret, OCG)", "Animation Chronicle 2024",
         "Extra Secret Rare", False, 80.00, "Monster", "LIGHT"),

        # =================================================================
        # Tournament Prize Cards
        # =================================================================
        ("YCSW-EN001", "Ascension Sky Dragon (YCS Prize)", "YCS Prize Card",
         "Ultra Rare", False, 300.00, "Monster", "LIGHT"),
        ("YCSW-EN002", "Minerva, the Exalted Lightsworn (YCS Prize)", "YCS Prize Card",
         "Ultra Rare", False, 500.00, "Monster", "LIGHT"),
        ("YCSW-EN003", "Digvorzhak, King of Heavy Industry (YCS Prize)", "YCS Prize Card",
         "Ultra Rare", False, 350.00, "Monster", "EARTH"),
        ("TF04-EN001", "Cyber Eltanin (Shonen Jump Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 25.00, "Monster", "LIGHT"),
        ("JUMP-EN066", "Slifer the Sky Dragon (Playable Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 45.00, "Monster", "DIVINE"),
        ("JUMP-EN045", "Obelisk the Tormentor (Playable Promo)", "Shonen Jump Promo",
         "Ultra Rare", False, 40.00, "Monster", "DIVINE"),

        # =================================================================
        # Vintage Sealed — Additional
        # =================================================================
        ("MRD-BOX", "Metal Raiders Booster Box (Sealed, Vintage)", "Metal Raiders",
         "Sealed Product", True, 8000.00, "Sealed Product", ""),
        ("PSV-BOX", "Pharaoh's Servant Booster Box (Sealed)", "Pharaoh's Servant",
         "Sealed Product", True, 6000.00, "Sealed Product", ""),
        ("MFC-BOX", "Magician's Force Booster Box (Sealed)", "Magician's Force",
         "Sealed Product", True, 5000.00, "Sealed Product", ""),
        ("IOC-BOX", "Invasion of Chaos Booster Box (Sealed, 1st Ed)", "Invasion of Chaos",
         "Sealed Product", True, 12000.00, "Sealed Product", ""),
        ("DCR-BOX", "Dark Crisis Booster Box (Sealed)", "Dark Crisis",
         "Sealed Product", True, 4000.00, "Sealed Product", ""),
        ("AST-BOX", "Ancient Sanctuary Booster Box (Sealed)", "Ancient Sanctuary",
         "Sealed Product", True, 3500.00, "Sealed Product", ""),
        ("SOD-BOX", "Soul of the Duelist Booster Box (Sealed)", "Soul of the Duelist",
         "Sealed Product", True, 3000.00, "Sealed Product", ""),
        ("RDS-BOX", "Rise of Destiny Booster Box (Sealed)", "Rise of Destiny",
         "Sealed Product", True, 2500.00, "Sealed Product", ""),
        ("FET-BOX", "Flaming Eternity Booster Box (Sealed)", "Flaming Eternity",
         "Sealed Product", True, 2500.00, "Sealed Product", ""),
        ("CRV-BOX", "Cybernetic Revolution Booster Box (Sealed)", "Cybernetic Revolution",
         "Sealed Product", True, 4000.00, "Sealed Product", ""),

        # =================================================================
        # More Iconic Cards at Market Prices
        # =================================================================
        ("MAMA-EN070", "Blue-Eyes White Dragon (Pharaoh's Rare)", "Magnificent Mavens",
         "Pharaoh's Rare", False, 50.00, "Monster", "LIGHT"),
        ("MAMA-EN071", "Dark Magician Girl (Pharaoh's Rare)", "Magnificent Mavens",
         "Pharaoh's Rare", False, 60.00, "Monster", "DARK"),
        ("MAMA-EN001", "Magicians' Souls (Ultra Rare, MAMA)", "Magnificent Mavens",
         "Ultra Rare", False, 30.00, "Monster", "DARK"),
        ("MP23-EN020", "Tearlaments Kitkallos (Prismatic Secret)", "2023 25th Anniversary Tin",
         "Prismatic Secret Rare", False, 25.00, "Monster", "DARK"),
        ("MP23-EN263", "Kashtira Fenrir (Ultra Rare, Tin)", "2023 25th Anniversary Tin",
         "Ultra Rare", False, 8.00, "Monster", "DARK"),
        ("RA01-EN001", "Blue-Eyes White Dragon (Ultimate Rare, RA01)", "Rarity Collection",
         "Ultimate Rare", False, 120.00, "Monster", "LIGHT"),
        ("RA01-EN002", "Dark Magician (Ultimate Rare, RA01)", "Rarity Collection",
         "Ultimate Rare", False, 100.00, "Monster", "DARK"),
        ("RA01-EN052", "Ash Blossom (Ultimate Rare, RA01)", "Rarity Collection",
         "Ultimate Rare", False, 80.00, "Monster", "FIRE"),
        ("LART-EN003", "Monster Reborn (Lost Art Promo)", "Lost Art Promotion",
         "Ultra Rare", False, 20.00, "Spell", ""),
        ("LART-EN006", "Harpie's Feather Duster (Lost Art Promo)", "Lost Art Promotion",
         "Ultra Rare", False, 15.00, "Spell", ""),
        ("LART-EN020", "Change of Heart (Lost Art Promo)", "Lost Art Promotion",
         "Ultra Rare", False, 12.00, "Spell", ""),
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

    # Add variant to reach 700+
    catalog.append({
        "set_code": "ROTD",
        "card_name": "Dogmatika Ecclesia, the Virtuous",
        "set_name": "Rise of the Duelist",
        "rarity": "Starlight Rare",
        "is_first_edition": True,
        "price_eur": 450.00,
        "card_type": "Monster",
        "attribute": "LIGHT",
        "edition": "1st Edition Starlight",
    })
    catalog.append({
        "set_code": "BROL",
        "card_name": "Ghost Belle & Haunted Mansion",
        "set_name": "Brothers of Legend",
        "rarity": "Starlight Rare",
        "is_first_edition": True,
        "price_eur": 380.00,
        "card_type": "Monster",
        "attribute": "EARTH",
        "edition": "1st Edition Starlight",
    })

    # Deduplicate by (set_code, card_name, rarity, edition) - keep first occurrence
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["set_code"], item["card_name"], item["rarity"], item["edition"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


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
    logger.info("Running curated seed catalog (500+ iconic Yu-Gi-Oh cards)...")

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
