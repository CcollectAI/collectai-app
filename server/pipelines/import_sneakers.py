"""
Sneaker Import Pipeline — Curated Collectible Sneakers Catalog.

Layer 1 (Catalog):  850+ curated sneakers → category_items
Layer 2 (Prices):   Estimated resale prices → train.jsonl

Covers:
- Air Jordan 1 High (Chicago, Bred, Royal, Shadow, Fragment x Travis Scott,
  Off-White UNC, Travis Scott Mocha, Dior, Union LA, Shattered Backboard, etc.)
- Air Jordan Retros 3-14 (Black Cement, Bred, Off-White Sail, Infrared,
  Concord, Space Jam, Flu Game, Travis Scott Purple, etc.)
- Nike Dunk (Panda, Kentucky, Travis Scott, Stussy Cherry, Off-White Lot,
  Heineken, Pigeon, Paris, De La Soul, Tiffany, etc.)
- Nike SB (Travis Scott, Strangelove, Chunky Dunky, Grateful Dead, Raygun, etc.)
- Yeezy (350 V2 Zebra/Bred, 350 V1 Turtle Dove/Pirate Black, 700 Wave Runner,
  750 OG, Foam Runner, Slide, 500 Utility Black, etc.)
- New Balance (550 ALD, 2002R Protection Pack, 990v3, 992 Grey, JJJJound, etc.)
- Nike Air Max (OG Red, Infrared, Silver Bullet, Patta, Sean Wotherspoon, etc.)
- Nike Collaborations (Off-White AF1, Travis Scott AF1, sacai LDWaffle,
  Tom Sachs Mars Yard, CPFM Vapormax, etc.)
- Adidas non-Yeezy (Bad Bunny Forum, Campus 00s, Samba OG, Wales Bonner, etc.)
- Other Brands (ASICS Kith, Salomon XT-6, Converse Chuck 70, Reebok, etc.)
- Grails / Ultra-Rare (Nike Air Mag, 1985 OG Chicago, SB Dunk Paris,
  Eminem AJ4, Undefeated AJ4, etc.)

Usage:
    python -m pipelines.import_sneakers [--dry-run] [--jsonl-only] [--cache-images]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem,
    PriceObservation,
    SupabaseIngest,
    write_training_jsonl,
    write_catalog_sql,
    cache_catalog_images,
    log_progress,
    slugify,
    logger,
    close_http_client,
    MAX_PRICE_EUR,
)

CATEGORY = "sneakers"

# ---------------------------------------------------------------------------
# Sneaker type scores — how collectible / desirable a release type is
# ---------------------------------------------------------------------------
SNEAKER_TYPE_SCORES: dict[str, float] = {
    "OG Colorway": 0.90,
    "Collaboration": 0.95,
    "Limited Release": 0.85,
    "Retro": 0.70,
    "GR (General Release)": 0.25,
    "Player Exclusive": 0.98,
    "Sample": 0.95,
    "F&F (Friends & Family)": 0.98,
    "Quickstrike": 0.80,
    "Hyperstrike": 0.90,
}

# ---------------------------------------------------------------------------
# Condition scores — sneaker-specific condition grading
# ---------------------------------------------------------------------------
CONDITION_SCORES: dict[str, float] = {
    "DS (Deadstock)": 1.0,
    "VNDS (Very Near Deadstock)": 0.90,
    "Excellent": 0.75,
    "Good": 0.55,
    "Used": 0.35,
    "Beater": 0.10,
}

# ---------------------------------------------------------------------------
# Brand premium multipliers (for ML features)
# ---------------------------------------------------------------------------
_BRAND_PREMIUM: dict[str, float] = {
    "Nike": 0.70,
    "Jordan": 0.85,
    "Adidas": 0.50,
    "New Balance": 0.55,
    "Yeezy": 0.65,
    "ASICS": 0.40,
    "Puma": 0.30,
    "Salomon": 0.45,
    "Converse": 0.35,
    "Reebok": 0.30,
    "Vans": 0.25,
}


def _brand_premium(brand: str) -> float:
    """Return a 0-1 brand premium score."""
    return _BRAND_PREMIUM.get(brand, 0.30)


def _is_collab(sneaker_type: str) -> bool:
    """Return True if the sneaker type indicates a collaboration."""
    return sneaker_type in ("Collaboration", "F&F (Friends & Family)")


# ---------------------------------------------------------------------------
# Curated catalog — 130+ sneakers
# Each tuple: (brand, model, colorway, sneaker_type, sku, price_eur)
# ---------------------------------------------------------------------------


def _air_jordan_1_high() -> list[tuple]:
    """15 iconic Air Jordan 1 High colorways."""
    return [
        ("Jordan", "Air Jordan 1 High", "Chicago", "OG Colorway",
         "555088-101", 1800),
        ("Jordan", "Air Jordan 1 High", "Bred / Banned", "OG Colorway",
         "555088-001", 450),
        ("Jordan", "Air Jordan 1 High", "Royal Blue", "OG Colorway",
         "555088-007", 380),
        ("Jordan", "Air Jordan 1 High", "Shadow", "OG Colorway",
         "555088-013", 350),
        ("Jordan", "Air Jordan 1 High", "Fragment x Travis Scott", "Collaboration",
         "DH3227-105", 2200),
        ("Jordan", "Air Jordan 1 High", "Off-White UNC", "Collaboration",
         "AQ0818-148", 1800),
        ("Jordan", "Air Jordan 1 High", "Travis Scott Mocha", "Collaboration",
         "CD4487-100", 1500),
        ("Jordan", "Air Jordan 1 High", "Dior", "Collaboration",
         "CN8607-002", 8500),
        ("Jordan", "Air Jordan 1 High", "Union LA Black Toe", "Collaboration",
         "BV1300-106", 1200),
        ("Jordan", "Air Jordan 1 High", "Shattered Backboard", "OG Colorway",
         "555088-005", 650),
        ("Jordan", "Air Jordan 1 High", "Pine Green", "OG Colorway",
         "555088-302", 280),
        ("Jordan", "Air Jordan 1 High", "Court Purple", "OG Colorway",
         "555088-500", 300),
        ("Jordan", "Air Jordan 1 High", "Turbo Green", "OG Colorway",
         "555088-311", 320),
        ("Jordan", "Air Jordan 1 High", "Off-White Chicago", "Collaboration",
         "AA3834-101", 3500),
        ("Jordan", "Air Jordan 1 High", "Union LA Storm Blue", "Collaboration",
         "BV1300-146", 1100),
    ]


def _air_jordan_retros() -> list[tuple]:
    """15 Air Jordan Retro models (3-14)."""
    return [
        ("Jordan", "Air Jordan 3", "Black Cement", "OG Colorway",
         "854262-001", 380),
        ("Jordan", "Air Jordan 3", "White Cement Reimagined", "Retro",
         "DN3707-100", 280),
        ("Jordan", "Air Jordan 4", "Bred", "OG Colorway",
         "308497-060", 420),
        ("Jordan", "Air Jordan 4", "Off-White Sail", "Collaboration",
         "CV9388-100", 1200),
        ("Jordan", "Air Jordan 4", "Travis Scott Purple", "Collaboration",
         "AQ9129-500", 1400),
        ("Jordan", "Air Jordan 5", "Off-White Muslin", "Collaboration",
         "DH8565-100", 550),
        ("Jordan", "Air Jordan 5", "Fire Red", "OG Colorway",
         "DA1911-102", 250),
        ("Jordan", "Air Jordan 6", "Infrared", "OG Colorway",
         "384664-060", 280),
        ("Jordan", "Air Jordan 11", "Bred", "OG Colorway",
         "378037-061", 350),
        ("Jordan", "Air Jordan 11", "Concord", "OG Colorway",
         "378037-100", 320),
        ("Jordan", "Air Jordan 11", "Space Jam", "OG Colorway",
         "378037-003", 300),
        ("Jordan", "Air Jordan 12", "Flu Game", "OG Colorway",
         "130690-002", 350),
        ("Jordan", "Air Jordan 13", "Bred", "OG Colorway",
         "414571-004", 250),
        ("Jordan", "Air Jordan 4", "Military Black", "Retro",
         "DH6927-111", 280),
        ("Jordan", "Air Jordan 14", "Last Shot", "OG Colorway",
         "487471-003", 220),
    ]


def _nike_dunks() -> list[tuple]:
    """15 Nike Dunk colorways."""
    return [
        ("Nike", "Dunk Low", "Panda Black/White", "GR (General Release)",
         "DD1391-100", 110),
        ("Nike", "Dunk Low", "Kentucky", "Retro",
         "CU1726-100", 140),
        ("Nike", "Dunk Low", "Travis Scott", "Collaboration",
         "CT5053-001", 1600),
        ("Nike", "Dunk Low", "Stussy Cherry", "Collaboration",
         "DM0602-600", 450),
        ("Nike", "Dunk Low", "Off-White Lot 01 of 50", "Collaboration",
         "DM1602-127", 650),
        ("Nike", "Dunk High", "Heineken", "Quickstrike",
         "305050-302", 3000),
        ("Nike", "Dunk Low", "Pigeon (Staple)", "Hyperstrike",
         "304292-011", 5500),
        ("Nike", "Dunk Low", "Paris", "Hyperstrike",
         "308270-111", 15000),
        ("Nike", "Dunk Low", "De La Soul (2005)", "Limited Release",
         "304292-171", 1800),
        ("Nike", "Dunk Low", "Tiffany (Diamond Supply)", "Collaboration",
         "304292-402", 2500),
        ("Nike", "Dunk Low", "Syracuse", "Retro",
         "CU1726-101", 130),
        ("Nike", "Dunk Low", "UNC", "Retro",
         "DD1391-102", 120),
        ("Nike", "Dunk Low", "Grey Fog", "GR (General Release)",
         "DD1391-103", 100),
        ("Nike", "Dunk Low", "Medium Curry", "Limited Release",
         "DD1390-100", 250),
        ("Nike", "Dunk Low", "Cacao Wow", "GR (General Release)",
         "DD1503-124", 100),
    ]


def _nike_sb() -> list[tuple]:
    """10 Nike SB Dunk models."""
    return [
        ("Nike", "SB Dunk Low", "Travis Scott (Cactus Jack)", "Collaboration",
         "CT5053-001", 1500),
        ("Nike", "SB Dunk Low", "Strangelove Skateboards", "Collaboration",
         "CT2552-800", 1400),
        ("Nike", "SB Dunk Low", "Ben & Jerry's Chunky Dunky", "Collaboration",
         "CU3244-100", 2200),
        ("Nike", "SB Dunk Low", "Grateful Dead Green Bear", "Collaboration",
         "CJ5378-300", 1800),
        ("Nike", "SB Dunk Low", "Raygun (Away)", "Limited Release",
         "304292-802", 900),
        ("Nike", "SB Dunk Low", "Supreme Red Cement", "Collaboration",
         "DH3228-161", 800),
        ("Nike", "SB Dunk Low", "Lobster Purple", "Collaboration",
         "BV1310-555", 1200),
        ("Nike", "SB Dunk Low", "Tiffany (Diamond 2005)", "Collaboration",
         "304292-402", 2800),
        ("Nike", "SB Dunk Low", "Safari (Atmos)", "Collaboration",
         "313170-220", 1100),
        ("Nike", "SB Dunk Low", "What The Dunk", "Quickstrike",
         "318403-141", 2000),
    ]


def _yeezy() -> list[tuple]:
    """15 Yeezy models."""
    return [
        ("Yeezy", "Yeezy Boost 350 V2", "Zebra", "Limited Release",
         "CP9654", 280),
        ("Yeezy", "Yeezy Boost 350 V2", "Bred (Core Black Red)", "Limited Release",
         "CP9652", 350),
        ("Yeezy", "Yeezy Boost 350 V1", "Turtle Dove", "OG Colorway",
         "AQ4832", 1200),
        ("Yeezy", "Yeezy Boost 350 V1", "Pirate Black", "OG Colorway",
         "AQ2659", 900),
        ("Yeezy", "Yeezy Boost 350 V1", "Oxford Tan", "OG Colorway",
         "AQ2661", 1000),
        ("Yeezy", "Yeezy Boost 350 V1", "Moonrock", "OG Colorway",
         "AQ2660", 850),
        ("Yeezy", "Yeezy Boost 700", "Wave Runner", "OG Colorway",
         "B75571", 380),
        ("Yeezy", "Yeezy Boost 750", "OG Light Brown", "OG Colorway",
         "B35309", 1400),
        ("Yeezy", "Yeezy Foam Runner", "Onyx", "GR (General Release)",
         "HP8739", 120),
        ("Yeezy", "Yeezy Slide", "Onyx", "GR (General Release)",
         "HQ6448", 100),
        ("Yeezy", "Yeezy 500", "Utility Black", "Limited Release",
         "F36640", 280),
        ("Yeezy", "Yeezy Boost 350 V2", "Beluga", "OG Colorway",
         "BB1826", 400),
        ("Yeezy", "Yeezy Boost 350 V2", "Cream White / Triple White", "Limited Release",
         "CP9366", 220),
        ("Yeezy", "Yeezy Boost 350 V2", "Static Reflective", "Limited Release",
         "EF2367", 350),
        ("Yeezy", "Yeezy Boost 700 V2", "Static", "Limited Release",
         "EF2829", 320),
    ]


def _new_balance() -> list[tuple]:
    """10 New Balance models."""
    return [
        ("New Balance", "NB 550", "ALD Green", "Collaboration",
         "BB550ALD", 350),
        ("New Balance", "NB 2002R", "Protection Pack Rain Cloud", "Limited Release",
         "M2002RDA", 280),
        ("New Balance", "NB 990v3", "Grey", "OG Colorway",
         "M990GY3", 200),
        ("New Balance", "NB 992", "Grey", "OG Colorway",
         "M992GR", 320),
        ("New Balance", "NB 2002R", "JJJJound Grey", "Collaboration",
         "M2002RFA", 450),
        ("New Balance", "NB 550", "White Green", "Retro",
         "BB550WT1", 130),
        ("New Balance", "NB 993", "Made in USA Grey", "OG Colorway",
         "MR993GL", 200),
        ("New Balance", "NB 550", "ALD Natural Green", "Collaboration",
         "BB550A1", 380),
        ("New Balance", "NB 2002R", "Protection Pack Sea Salt", "Limited Release",
         "M2002RDC", 260),
        ("New Balance", "NB 1906R", "Protection Pack Silver Metallic", "Limited Release",
         "M1906REE", 180),
    ]


def _nike_air_max() -> list[tuple]:
    """10 Nike Air Max models."""
    return [
        ("Nike", "Air Max 1", "OG Red (Sport Red)", "OG Colorway",
         "DM9484-100", 180),
        ("Nike", "Air Max 90", "Infrared", "OG Colorway",
         "CT1685-100", 160),
        ("Nike", "Air Max 97", "Silver Bullet", "OG Colorway",
         "DM0028-002", 200),
        ("Nike", "Air Max 1", "Patta Waves Monarch", "Collaboration",
         "DH1348-001", 350),
        ("Nike", "Air Max 1/97", "Sean Wotherspoon", "Collaboration",
         "AJ4219-400", 1200),
        ("Nike", "Air Max Plus", "OG Hyper Blue", "OG Colorway",
         "BQ4629-003", 180),
        ("Nike", "Air Max 1", "Patta Waves Aqua Noise", "Collaboration",
         "DQ0299-100", 320),
        ("Nike", "Air Max 90", "Off-White Desert Ore", "Collaboration",
         "AA7293-200", 550),
        ("Nike", "Air Max 1", "Concepts Mellow", "Collaboration",
         "DN1803-300", 380),
        ("Nike", "Air Max 95", "Neon / Volt", "OG Colorway",
         "CT1689-001", 190),
    ]


def _nike_collaborations() -> list[tuple]:
    """15 Nike collaboration sneakers."""
    return [
        ("Nike", "Air Force 1 Low", "Off-White Volt", "Collaboration",
         "AO4606-700", 750),
        ("Nike", "Air Force 1 Low", "Off-White MCA University Blue", "Collaboration",
         "CI1173-400", 1800),
        ("Nike", "Air Presto", "Off-White White", "Collaboration",
         "AA3830-100", 650),
        ("Nike", "Air Force 1 Low", "Travis Scott Cactus Jack Sail", "Collaboration",
         "AQ4211-101", 600),
        ("Nike", "LDWaffle", "sacai Green Gusto", "Collaboration",
         "BV0073-300", 450),
        ("Nike", "Vaporwaffle", "sacai Sail", "Collaboration",
         "CV1363-100", 350),
        ("Nike", "Vapormax", "CPFM Smile", "Collaboration",
         "CD7001-300", 500),
        ("Nike", "Mars Yard 2.0", "Tom Sachs", "Collaboration",
         "AA2261-100", 5500),
        ("Nike", "Air Force 1 Low", "Virgil x Louis Vuitton White", "Collaboration",
         "1A9VAS", 3500),
        ("Nike", "Blazer Mid", "Off-White Grim Reaper", "Collaboration",
         "AA3832-001", 550),
        ("Nike", "Air Force 1 Low", "Travis Scott Utopia", "Collaboration",
         "DX4290-200", 400),
        ("Nike", "LD Waffle", "sacai Fragment Blue Void", "Collaboration",
         "DH2684-400", 380),
        ("Nike", "Air Presto", "Off-White Black", "Collaboration",
         "AA3830-002", 700),
        ("Nike", "Blazer Mid", "Off-White All Hallows Eve", "Collaboration",
         "AA3832-700", 600),
        ("Nike", "Air Rubber Dunk", "Off-White Green Strike", "Collaboration",
         "CU6015-001", 350),
    ]


def _adidas_non_yeezy() -> list[tuple]:
    """10 Adidas (non-Yeezy) models."""
    return [
        ("Adidas", "Forum Low", "Bad Bunny First Cafe", "Collaboration",
         "GW0264", 300),
        ("Adidas", "Campus 00s", "Grey", "Retro",
         "HQ8707", 110),
        ("Adidas", "Samba OG", "White/Black", "OG Colorway",
         "B75806", 100),
        ("Adidas", "Gazelle", "Bold Green", "OG Colorway",
         "BB5477", 90),
        ("Adidas", "Superstar", "Prada White", "Collaboration",
         "FW6683", 500),
        ("Adidas", "Samba", "Wales Bonner Cream White", "Collaboration",
         "GY4344", 380),
        ("Adidas", "Forum Low", "Bad Bunny Blue Tint", "Collaboration",
         "GY4900", 280),
        ("Adidas", "Gazelle", "Gucci", "Collaboration",
         "707848", 750),
        ("Adidas", "Campus 00s", "Korn Follow the Leader", "Collaboration",
         "IG0792", 200),
        ("Adidas", "Samba OG", "Sporty & Rich White", "Collaboration",
         "HP3354", 220),
    ]


def _other_brands() -> list[tuple]:
    """10 sneakers from other brands."""
    return [
        ("ASICS", "Gel-Lyte III", "Kith Palette Tokyo Trio", "Collaboration",
         "1201A224-400", 400),
        ("Puma", "Suede VTG", "Classic Black/White", "OG Colorway",
         "374921-01", 75),
        ("Salomon", "XT-6", "Black/Phantom", "Limited Release",
         "L41086600", 200),
        ("Converse", "Chuck 70", "CDG Play Multi Heart", "Collaboration",
         "171849C", 180),
        ("Reebok", "Question Mid", "Allen Iverson Blue Toe", "OG Colorway",
         "GX5260", 150),
        ("Vans", "Old Skool", "Black/White", "OG Colorway",
         "VN000D3HY28", 65),
        ("ASICS", "Gel-Lyte III", "Sean Wotherspoon x Atmos", "Collaboration",
         "1203A019-000", 350),
        ("Salomon", "XT-6", "MM6 Maison Margiela", "Collaboration",
         "S98765", 550),
        ("Converse", "Chuck 70", "Off-White Stripe", "Collaboration",
         "163862C", 450),
        ("Reebok", "Instapump Fury", "Vetements", "Collaboration",
         "BS7031", 500),
    ]


def _jordan_1_expansion() -> list[tuple]:
    """5 additional Air Jordan 1 High colorways."""
    return [
        ("Jordan", "Air Jordan 1 Low", "Travis Scott Reverse Mocha", "Collaboration",
         "DM7866-162", 1400),
        ("Jordan", "Air Jordan 1 High", "A Ma Maniere", "Collaboration",
         "DO7097-100", 450),
        ("Jordan", "Air Jordan 1 High", "Lost & Found (Chicago Reimagined)", "Retro",
         "DZ5485-612", 250),
        ("Jordan", "Air Jordan 1 High", "Rebellionaire", "Limited Release",
         "555088-036", 200),
        ("Jordan", "Air Jordan 1 High", "Heritage", "Retro",
         "555088-161", 150),
    ]


def _nike_dunk_expansion() -> list[tuple]:
    """5 additional Nike Dunk collaborations."""
    return [
        ("Nike", "Dunk Low", "Off-White Lot 50 of 50 (Dear Summer)", "Collaboration",
         "DM1602-001", 550),
        ("Nike", "Dunk Low", "Union LA Passport Pack Pistachio", "Collaboration",
         "DJ9649-301", 350),
        ("Nike", "Dunk Low", "Union LA Passport Pack Argon", "Collaboration",
         "DJ9649-400", 320),
        ("Nike", "SB Dunk Low", "Concepts Orange Lobster", "Collaboration",
         "FD8776-800", 400),
        ("Nike", "SB Dunk Low", "Concepts Green Lobster", "Collaboration",
         "BV1310-337", 1000),
    ]


def _new_balance_expansion() -> list[tuple]:
    """5 additional New Balance models."""
    return [
        ("New Balance", "NB 993", "Joe Freshgoods Performance Art", "Collaboration",
         "MR993JF1", 500),
        ("New Balance", "NB 993", "Aime Leon Dore Taupe", "Collaboration",
         "MR993ALD", 550),
        ("New Balance", "NB 550", "Teddy Santis Sea Salt", "Collaboration",
         "BB550TS1", 200),
        ("New Balance", "NB 990v6", "JJJJound Navy", "Collaboration",
         "M990JJ6", 400),
        ("New Balance", "NB 1000", "Joe Freshgoods Arctic Blue", "Collaboration",
         "M1000JF", 350),
    ]


def _asics_salomon() -> list[tuple]:
    """5 ASICS and Salomon models."""
    return [
        ("ASICS", "Gel-Lyte III", "Kith Marvel X-Men Cyclops", "Collaboration",
         "1203A535-400", 350),
        ("ASICS", "Gel-Lyte III", "atmos Nexkin Pack", "Collaboration",
         "1203A270-100", 280),
        ("Salomon", "XT-6", "Sandy Liang", "Collaboration",
         "L47385400", 280),
        ("Salomon", "XT-6", "BEAMS", "Collaboration",
         "L41735400", 250),
        ("ASICS", "Gel-Kayano 14", "JJJJound Silver", "Collaboration",
         "1203A459-020", 300),
    ]


def _adidas_expansion() -> list[tuple]:
    """5 additional Adidas models."""
    return [
        ("Adidas", "Forum Low", "Bad Bunny Back to School", "Collaboration",
         "HQ2153", 250),
        ("Adidas", "AE1", "Anthony Edwards Low", "Limited Release",
         "IF1863", 150),
        ("Adidas", "Samba", "Wales Bonner Pony Leopard", "Collaboration",
         "IE0580", 500),
        ("Adidas", "Campus 80s", "Bad Bunny Olive", "Collaboration",
         "ID7950", 220),
        ("Adidas", "Response CL", "Bad Bunny Wonder White", "Collaboration",
         "GY0102", 200),
    ]


def _grails_ultra_rare() -> list[tuple]:
    """10 ultra-rare grail sneakers."""
    return [
        ("Nike", "Air Mag", "Back to the Future (2011)", "F&F (Friends & Family)",
         "417744-001", 30000),
        ("Nike", "Air Mag", "Self-Lacing (2016)", "Limited Release",
         "HO15-MNOTHR", 45000),
        ("Jordan", "Air Jordan 1 High", "1985 OG Chicago (New Old Stock)", "OG Colorway",
         "AJ1-85-OG", 25000),
        ("Nike", "SB Dunk Low", "Paris (Musee)", "Sample",
         "308270-111", 18000),
        ("Jordan", "Air Jordan 4", "Eminem Encore", "F&F (Friends & Family)",
         "EMINEM-AJ4", 20000),
        ("Jordan", "Air Jordan 4", "Undefeated (2005)", "F&F (Friends & Family)",
         "UNDFTD-AJ4", 12000),
        ("Nike", "Air Yeezy 2", "Red October", "Limited Release",
         "508214-660", 8000),
        ("Nike", "Air Yeezy 1", "Blink", "Player Exclusive",
         "366164-003", 6000),
        ("Nike", "SB Dunk Low", "Freddy Krueger (Nightmare)", "Sample",
         "313170-202", 10000),
        ("Jordan", "Air Jordan 12", "OVO White (Drake)", "F&F (Friends & Family)",
         "456985-090", 5000),
    ]


def _jordan_retro_expansion() -> list[tuple]:
    """10 additional Air Jordan retro models."""
    return [
        ("Jordan", "Air Jordan 1 High", "University Blue", "Retro",
         "555088-134", 280),
        ("Jordan", "Air Jordan 1 High", "Hyper Royal", "Retro",
         "555088-402", 220),
        ("Jordan", "Air Jordan 3", "A Ma Maniere", "Collaboration",
         "DH3434-110", 500),
        ("Jordan", "Air Jordan 4", "Red Thunder", "Retro",
         "CT8527-016", 300),
        ("Jordan", "Air Jordan 5", "Black Metallic Reimagined", "Retro",
         "DV0564-004", 220),
        ("Jordan", "Air Jordan 6", "Travis Scott British Khaki", "Collaboration",
         "DH0690-200", 450),
        ("Jordan", "Air Jordan 11", "Cherry", "Retro",
         "CT8012-116", 250),
        ("Jordan", "Air Jordan 11", "Cool Grey", "Retro",
         "CT8012-005", 280),
        ("Jordan", "Air Jordan 4", "Seafoam", "Retro",
         "AQ9129-103", 250),
        ("Jordan", "Air Jordan 1 Low", "Fragment", "Collaboration",
         "CU3244-104", 800),
    ]


def _nike_general_expansion() -> list[tuple]:
    """10 additional Nike models (AF1, Cortez, etc.)."""
    return [
        ("Nike", "Air Force 1 Low", "White", "GR (General Release)",
         "315122-111", 100),
        ("Nike", "Air Force 1 Low", "Tiffany & Co. 1837", "Collaboration",
         "DZ1382-001", 450),
        ("Nike", "Cortez", "Forrest Gump", "OG Colorway",
         "819720-100", 100),
        ("Nike", "Air Max 1", "Anniversary Red (2017)", "Retro",
         "908375-103", 300),
        ("Nike", "Air Max 90", "Bacon (Dave's Quality Meats)", "Collaboration",
         "CU1816-100", 350),
        ("Nike", "Dunk Low", "Setsubun", "Limited Release",
         "DQ5009-268", 200),
        ("Nike", "Dunk Low", "Jarritos", "Collaboration",
         "FD0860-001", 350),
        ("Nike", "Zoom Vomero 5", "Oatmeal", "Retro",
         "HF1553-200", 180),
        ("Nike", "Air Max Plus", "Tuned 1 OG Tiger", "OG Colorway",
         "604133-886", 200),
        ("Nike", "Air Max 97", "Undefeated White", "Collaboration",
         "AJ1986-100", 350),
    ]


def _puma_vans_expansion() -> list[tuple]:
    """10 additional Puma, Vans, and other brand models."""
    return [
        ("Puma", "Clyde", "Rhuigi Villasenor", "Collaboration",
         "391104-01", 250),
        ("Puma", "RS-X", "Toys", "Collaboration",
         "369449-02", 120),
        ("Vans", "Sk8-Hi", "Supreme x Skull Pile", "Collaboration",
         "VN0A5HXV", 400),
        ("Vans", "Old Skool", "Fear of God", "Collaboration",
         "VN0A3DPCII7", 500),
        ("Converse", "Chuck Taylor", "CDG Play High Black", "Collaboration",
         "150204C", 160),
        ("ASICS", "Gel-Lyte V", "Ronnie Fieg Volcano", "Collaboration",
         "H51EK-9090", 600),
        ("Reebok", "Club C 85", "Vintage White/Green", "OG Colorway",
         "AR0456", 80),
        ("Salomon", "XT-4 OG", "White/Ebony", "Retro",
         "L47133100", 200),
        ("Converse", "One Star", "Tyler the Creator Golf Le Fleur Vanilla", "Collaboration",
         "160325C", 200),
        ("New Balance", "NB 574", "Grey Day", "Limited Release",
         "ML574EGG", 140),
    ]


def _yeezy_expansion() -> list[tuple]:
    """10 additional Yeezy models."""
    return [
        ("Yeezy", "Yeezy Boost 350 V2", "MX Oat", "Limited Release",
         "GW3773", 250),
        ("Yeezy", "Yeezy Boost 350 V2", "Onyx", "Limited Release",
         "HQ4540", 280),
        ("Yeezy", "Yeezy Boost 350 V2", "Bone", "Limited Release",
         "HQ6316", 260),
        ("Yeezy", "Yeezy 450", "Cloud White", "Limited Release",
         "H68038", 220),
        ("Yeezy", "Yeezy Boost 700 V3", "Alvah", "Limited Release",
         "H67799", 300),
        ("Yeezy", "Yeezy 500", "Blush", "OG Colorway",
         "DB2908", 280),
        ("Yeezy", "Yeezy Foam Runner", "MX Clay", "Limited Release",
         "GV7908", 150),
        ("Yeezy", "Yeezy Boost 380", "Alien", "Limited Release",
         "FV3260", 280),
        ("Yeezy", "Yeezy Slide", "Bone", "GR (General Release)",
         "FW6345", 110),
        ("Yeezy", "Yeezy Boost 700", "Analog", "Limited Release",
         "EG7596", 320),
    ]


def _travis_scott_collabs() -> list[tuple]:
    """12 Travis Scott collaborations beyond those already listed."""
    return [
        ("Jordan", "Air Jordan 1 Low", "Travis Scott Black Phantom", "Collaboration",
         "DM7866-001", 1100),
        ("Jordan", "Air Jordan 4", "Travis Scott Cactus Jack Olive", "Collaboration",
         "FB9927-200", 550),
        ("Jordan", "Air Jordan 1 Low", "Travis Scott Canary", "Collaboration",
         "DZ4137-700", 650),
        ("Nike", "Air Max 1", "Travis Scott Saturn Gold", "Collaboration",
         "DO9392-700", 400),
        ("Nike", "Air Max 1", "Travis Scott Wheat", "Collaboration",
         "DO9392-101", 380),
        ("Nike", "Air Max 1", "Travis Scott Baroque Brown", "Collaboration",
         "DO9392-200", 420),
        ("Nike", "Air Trainer 1", "Travis Scott Grey Haze", "Collaboration",
         "DR7515-001", 350),
        ("Jordan", "Air Jordan 6", "Travis Scott Olive", "Collaboration",
         "DH0690-300", 480),
        ("Nike", "Air Force 1 Low", "Travis Scott Fossil", "Collaboration",
         "AQ4211-002", 550),
        ("Jordan", "Air Jordan 2 Low", "Travis Scott Cement Grey", "Collaboration",
         "DV7128-010", 350),
        ("Jordan", "Air Jordan 1 Low", "Travis Scott Olive", "Collaboration",
         "DZ4137-106", 600),
        ("Nike", "Mac Attack", "Travis Scott OG", "Collaboration",
         "FB8938-001", 300),
    ]


def _off_white_collabs() -> list[tuple]:
    """10 Off-White x Nike beyond those already listed."""
    return [
        ("Nike", "Air Jordan 2 Low", "Off-White White Red", "Collaboration",
         "DJ4375-106", 550),
        ("Nike", "Air Jordan 4", "Off-White Bred", "Collaboration",
         "CV9388-001", 1100),
        ("Nike", "Air Force 1 Low", "Off-White Brooklyn", "Collaboration",
         "DX1419-300", 400),
        ("Nike", "Air Force 1 Low", "Off-White Light Green Spark", "Collaboration",
         "DX1419-300", 380),
        ("Nike", "Air Force 1 Mid", "Off-White Graffiti White", "Collaboration",
         "DO6290-100", 650),
        ("Nike", "Zoom Fly", "Off-White Tulip Pink", "Collaboration",
         "AJ4588-600", 400),
        ("Nike", "Air Max 90", "Off-White Black", "Collaboration",
         "AA7293-001", 600),
        ("Nike", "Dunk Low", "Off-White Lot 20 of 50", "Collaboration",
         "DJ0950-115", 450),
        ("Nike", "Dunk Low", "Off-White University Gold", "Collaboration",
         "CT0856-700", 500),
        ("Nike", "Blazer Low", "Off-White White University Red", "Collaboration",
         "DH7863-100", 350),
    ]


def _a_ma_maniere_union() -> list[tuple]:
    """10 A Ma Maniere and Union LA collaborations."""
    return [
        ("Jordan", "Air Jordan 4", "A Ma Maniere Violet Ore", "Collaboration",
         "DV6773-220", 400),
        ("Jordan", "Air Jordan 5", "A Ma Maniere Dawn", "Collaboration",
         "FN5032-100", 350),
        ("Jordan", "Air Jordan 2", "A Ma Maniere Airness", "Collaboration",
         "DO7216-100", 380),
        ("Jordan", "Air Jordan 12", "A Ma Maniere White", "Collaboration",
         "DV6989-100", 350),
        ("Nike", "Air Ship", "A Ma Maniere Game Royal", "Collaboration",
         "FQ2942-401", 300),
        ("Jordan", "Air Jordan 1 High", "Union LA Neutral Grey", "Collaboration",
         "BV1300-100", 1000),
        ("Jordan", "Air Jordan 2", "Union LA Grey Fog", "Collaboration",
         "DN3802-001", 350),
        ("Jordan", "Air Jordan 2", "Union LA Rattan", "Collaboration",
         "DN3802-200", 320),
        ("Jordan", "Air Jordan 4", "Union LA Guava Ice", "Collaboration",
         "DC9533-800", 650),
        ("Jordan", "Air Jordan 4", "Union LA Desert Moss", "Collaboration",
         "DC9533-200", 600),
    ]


def _sb_dunk_grails() -> list[tuple]:
    """12 Nike SB Dunk grails and classics."""
    return [
        ("Nike", "SB Dunk Low", "Lobster Red", "Collaboration",
         "313170-661", 2500),
        ("Nike", "SB Dunk Low", "Lobster Yellow", "Collaboration",
         "313170-137", 8000),
        ("Nike", "SB Dunk Low", "Lobster Blue", "Collaboration",
         "313170-342", 1500),
        ("Nike", "SB Dunk Low", "Stussy Cherry", "Collaboration",
         "304292-671", 3500),
        ("Nike", "SB Dunk Low", "Paris Special Box", "Hyperstrike",
         "308270-111S", 20000),
        ("Nike", "SB Dunk Low", "Supreme Black Cement", "Collaboration",
         "304292-131", 2000),
        ("Nike", "SB Dunk Low", "Reese Forbes Denim", "Quickstrike",
         "304292-441", 2800),
        ("Nike", "SB Dunk Low", "Pushead", "Collaboration",
         "313170-001", 3000),
        ("Nike", "SB Dunk Low", "FLOM (For Love or Money)", "F&F (Friends & Family)",
         "313170-F", 6000),
        ("Nike", "SB Dunk Low", "Jedi (Star Wars)", "Limited Release",
         "304292-222", 1200),
        ("Nike", "SB Dunk Low", "MF Doom", "Quickstrike",
         "314170-004", 4000),
        ("Nike", "SB Dunk High", "Tiffany (Diamond)", "Collaboration",
         "653599-400", 1500),
    ]


def _fear_of_god_sacai() -> list[tuple]:
    """10 Fear of God and sacai collaborations."""
    return [
        ("Nike", "Air Fear of God 1", "Black", "Collaboration",
         "AR4237-001", 600),
        ("Nike", "Air Fear of God 1", "Oatmeal", "Collaboration",
         "AR4237-900", 700),
        ("Nike", "Air Fear of God 1", "Triple Black", "Collaboration",
         "AR4237-005", 550),
        ("Nike", "Air Fear of God Moc", "Particle Beige", "Collaboration",
         "AT8086-200", 300),
        ("Nike", "Air Fear of God Raid", "Light Bone", "Collaboration",
         "AT8087-001", 250),
        ("Nike", "LDWaffle", "sacai Green Multi", "Collaboration",
         "BV0073-300", 420),
        ("Nike", "LDWaffle", "sacai Black Nylon", "Collaboration",
         "BV0073-002", 380),
        ("Nike", "Blazer Mid", "sacai White Grey", "Collaboration",
         "BV0072-100", 350),
        ("Nike", "Cortez", "sacai White University Red", "Collaboration",
         "DQ0581-100", 200),
        ("Nike", "Vaporwaffle", "sacai Sport Fuchsia", "Collaboration",
         "DD3035-200", 300),
    ]


def _kobe_lebron_pe() -> list[tuple]:
    """12 Kobe and LeBron grails / PEs."""
    return [
        ("Nike", "Kobe 6 Protro", "Grinch", "Retro",
         "CW2190-300", 380),
        ("Nike", "Kobe 6 Protro", "Mambacita Sweet 16", "Collaboration",
         "CW2190-002", 600),
        ("Nike", "Kobe 5 Protro", "Bruce Lee", "Retro",
         "CD4991-700", 350),
        ("Nike", "Kobe 4 Protro", "Wizenard", "Limited Release",
         "CV3469-001", 500),
        ("Nike", "Kobe 8 Protro", "Venice Beach", "Retro",
         "FQ3549-001", 280),
        ("Nike", "Kobe 6 Protro", "Reverse Grinch", "Limited Release",
         "FV4921-600", 350),
        ("Nike", "LeBron 20", "Stussy Berry", "Collaboration",
         "DV3786-600", 250),
        ("Nike", "LeBron 4", "Fruity Pebbles", "Retro",
         "DQ1470-100", 320),
        ("Nike", "Kobe 5 Protro", "5x Champ (Lakers)", "Player Exclusive",
         "386429-702", 1200),
        ("Nike", "LeBron 2", "Beast", "Retro",
         "DR0826-001", 280),
        ("Nike", "Kobe 6 Protro", "All-Star", "Retro",
         "CW2190-500", 350),
        ("Nike", "Kobe 4 Protro", "Undftd Milwaukee Bucks", "Collaboration",
         "CQ3869-300", 450),
    ]


def _womens_exclusives() -> list[tuple]:
    """8 women's exclusive sneakers."""
    return [
        ("Jordan", "Air Jordan 1 High", "Satin Black Toe (W)", "Limited Release",
         "CD0461-016", 500),
        ("Jordan", "Air Jordan 1 High", "Satin Bred (W)", "Limited Release",
         "CD0461-601", 650),
        ("Jordan", "Air Jordan 1 High", "Twist (W)", "Retro",
         "CD0461-007", 200),
        ("Nike", "Dunk Low", "Rose Whisper (W)", "GR (General Release)",
         "DD1503-118", 100),
        ("Jordan", "Air Jordan 4", "A Ma Maniere (W)", "Collaboration",
         "DV6773-220W", 380),
        ("Jordan", "Air Jordan 11", "Neapolitan (W)", "Retro",
         "AR0715-101", 220),
        ("Jordan", "Air Jordan 3", "Lucky Green (W)", "Retro",
         "CK9246-136", 250),
        ("Nike", "Air Max Plus", "Atlanta (W)", "Limited Release",
         "DZ3670-001", 180),
    ]


def _regional_exclusives() -> list[tuple]:
    """8 regional exclusive sneakers."""
    return [
        ("Nike", "Air Max 90", "Tokyo (City Pack)", "Limited Release",
         "CW1409-101", 300),
        ("Nike", "Dunk Low", "Brazil", "Limited Release",
         "CU1727-700", 250),
        ("Nike", "Air Force 1 Low", "Seoul (Korea)", "Limited Release",
         "CJ1607-100", 280),
        ("Nike", "Dunk Low", "Veneer (Australia)", "Limited Release",
         "DA1469-200", 200),
        ("Nike", "Air Max 1", "Amsterdam (City Pack)", "Limited Release",
         "CV1638-200", 350),
        ("Nike", "Air Max 1", "London (City Pack)", "Limited Release",
         "CV1639-001", 320),
        ("Nike", "SB Dunk Low", "Ishod Wair (NYC)", "Limited Release",
         "895969-006", 180),
        ("Nike", "Dunk Low", "Shanghai (China)", "Limited Release",
         "309242-113", 1800),
    ]


def _2025_2026_releases() -> list[tuple]:
    """15 notable 2025-2026 releases and upcoming drops."""
    return [
        ("Jordan", "Air Jordan 1 High", "Bred Reimagined", "Retro",
         "DV0564-601", 250),
        ("Jordan", "Air Jordan 4", "Bred Reimagined", "Retro",
         "FV5029-006", 280),
        ("Jordan", "Air Jordan 5", "Burgundy", "Retro",
         "DZ4131-600", 200),
        ("Jordan", "Air Jordan 11", "Columbia (2025)", "Retro",
         "CT8012-114", 260),
        ("Nike", "Dunk Low", "Reverse Panda", "GR (General Release)",
         "DJ6188-002", 110),
        ("Nike", "Air Max Dn", "White/Black", "GR (General Release)",
         "DV3337-100", 160),
        ("Nike", "Air Max 1", "Big Bubble Sport Red (2025)", "Retro",
         "DQ3989-100", 180),
        ("Adidas", "Samba OG", "Navy Gum", "Retro",
         "IE3437", 110),
        ("New Balance", "NB 1000", "Grey (2025)", "Retro",
         "M1000GR", 180),
        ("Nike", "Zoom Vomero 5", "Supersonic", "Retro",
         "FN7649-110", 170),
        ("Jordan", "Air Jordan 1 Low", "Year of the Snake", "Limited Release",
         "FN3722-100", 180),
        ("Nike", "Air Max 95", "Neon (2025)", "Retro",
         "FQ0235-001", 190),
        ("Jordan", "Air Jordan 3", "Black Cement Reimagined (2025)", "Retro",
         "FN0516-001", 240),
        ("Nike", "Air Max 90", "Infrared (2025)", "Retro",
         "FQ2568-100", 170),
        ("Adidas", "Gazelle", "Indoor Bold Green (2025)", "Retro",
         "IF3226", 100),
    ]


def _nb_asics_salomon_expansion() -> list[tuple]:
    """12 additional New Balance, ASICS, Salomon picks."""
    return [
        ("New Balance", "NB 2002R", "Bape Grey", "Collaboration",
         "M2002RBP", 380),
        ("New Balance", "NB 990v4", "Kith United Arrows Navy", "Collaboration",
         "M990KT4", 450),
        ("New Balance", "NB 992", "JJJJound Grey", "Collaboration",
         "M992J2", 500),
        ("New Balance", "NB 990v3", "Joe Freshgoods Outside Clothes", "Collaboration",
         "M990JF3", 450),
        ("ASICS", "Gel-Lyte III", "Ronnie Fieg Super Gold", "Collaboration",
         "1201A067-750", 500),
        ("ASICS", "Gel-Kayano 14", "Cecilie Bahnsen Mary Jane", "Collaboration",
         "1203A566-100", 350),
        ("ASICS", "GT-2160", "Joe Freshgoods Below Clouds", "Collaboration",
         "1203A465-200", 300),
        ("Salomon", "XT-6", "Salehe Bembury Sand", "Collaboration",
         "L47454400", 350),
        ("Salomon", "XT-6", "Palace Black", "Collaboration",
         "L47456700", 280),
        ("Salomon", "ACS Pro", "11 by BBS White", "Collaboration",
         "L41744300", 400),
        ("ASICS", "Gel-Lyte III", "Kith Tokyo Trio Yoshino Rose", "Collaboration",
         "1201A224-700", 450),
        ("New Balance", "NB 530", "White Silver", "Retro",
         "MR530SG", 110),
    ]


def _grails_expansion() -> list[tuple]:
    """10 additional ultra-rare / PE grails."""
    return [
        ("Nike", "Air Yeezy 2", "Pure Platinum", "Limited Release",
         "508214-010", 6000),
        ("Nike", "Air Yeezy 1", "Net Tan", "Limited Release",
         "366164-111", 5000),
        ("Jordan", "Air Jordan 4", "Wahlburgers (F&F)", "F&F (Friends & Family)",
         "WAHL-AJ4", 8000),
        ("Jordan", "Air Jordan 3", "Oregon Ducks PE", "Player Exclusive",
         "AJ3-OREGON", 5000),
        ("Nike", "SB Dunk Low", "Staple Pigeon Black", "Hyperstrike",
         "BV1310-013", 4000),
        ("Jordan", "Air Jordan 11", "Derek Jeter Promo Sample", "Sample",
         "AJ11-JETER", 15000),
        ("Nike", "Air Max 1", "Parra (2018 Friends & Family)", "F&F (Friends & Family)",
         "AT3057-F&F", 8000),
        ("Jordan", "Air Jordan 1 High", "Nigel Sylvester (Destroyed)", "Collaboration",
         "BV1803-106", 1200),
        ("Nike", "Air Force 1 Low", "Entourage (Friends & Family)", "F&F (Friends & Family)",
         "ENT-AF1", 5000),
        ("Jordan", "Air Jordan 4", "Kaws Grey", "Collaboration",
         "930155-003", 2500),
    ]


def _adidas_puma_reebok_expansion() -> list[tuple]:
    """12 additional Adidas, Puma, Reebok, Converse, Vans picks."""
    return [
        ("Adidas", "Samba", "Wales Bonner Silver", "Collaboration",
         "IG8181", 400),
        ("Adidas", "Handball Spezial", "Blue/Gum", "Retro",
         "BD7632", 100),
        ("Adidas", "SL 72", "OG Vintage", "Retro",
         "IE3427", 90),
        ("Adidas", "Gazelle", "Wales Bonner Green", "Collaboration",
         "GY4344G", 350),
        ("Puma", "Lamelo Ball MB.01", "Rick & Morty", "Collaboration",
         "376682-01", 200),
        ("Puma", "Clyde", "Extra Butter Kings of New York", "Collaboration",
         "362320-01", 300),
        ("Reebok", "Question Mid", "Packer Shoes SNS Token 38", "Collaboration",
         "GX0047", 300),
        ("Reebok", "Pump Omni Zone II", "Dee Brown (Retro)", "OG Colorway",
         "G57539", 150),
        ("Converse", "Chuck 70", "Comme des Garcons Low Polka Dot", "Collaboration",
         "157249C", 170),
        ("Vans", "Half Cab", "Supreme x CDG", "Collaboration",
         "VN0A5HY1", 350),
        ("Puma", "RS-Dreamer", "J. Cole", "Collaboration",
         "194602-01", 180),
        ("Converse", "Weapon", "Undefeated White Purple", "Collaboration",
         "A04458C", 200),
    ]


def _jordan_2_thru_10_retros() -> list[tuple]:
    """20 Air Jordan 2-10 key retro colorways."""
    return [
        ("Jordan", "Air Jordan 2", "Chicago OG", "OG Colorway",
         "DX2454-106", 200),
        ("Jordan", "Air Jordan 2", "Italy Blue", "Retro",
         "DR8884-400", 180),
        ("Jordan", "Air Jordan 2", "Lucky Green", "Retro",
         "DR8884-103", 170),
        ("Jordan", "Air Jordan 3", "True Blue (2016)", "Retro",
         "854262-106", 280),
        ("Jordan", "Air Jordan 3", "Fire Red (2022)", "Retro",
         "DN3707-160", 230),
        ("Jordan", "Air Jordan 3", "Palomino", "Retro",
         "CT8532-102", 220),
        ("Jordan", "Air Jordan 3", "Muslin", "Retro",
         "DH7139-100", 210),
        ("Jordan", "Air Jordan 4", "White Oreo", "Retro",
         "CT8527-100", 350),
        ("Jordan", "Air Jordan 4", "Thunder (2023)", "Retro",
         "DH6927-017", 280),
        ("Jordan", "Air Jordan 4", "Frozen Moments (W)", "Limited Release",
         "AQ9129-001", 320),
        ("Jordan", "Air Jordan 5", "Grape (2013)", "Retro",
         "136027-108", 250),
        ("Jordan", "Air Jordan 5", "Raging Bull (2021)", "Retro",
         "DD0587-600", 280),
        ("Jordan", "Air Jordan 6", "UNC", "Retro",
         "384664-410", 250),
        ("Jordan", "Air Jordan 6", "Black Infrared (2019)", "Retro",
         "384664-060B", 300),
        ("Jordan", "Air Jordan 7", "Olympic (2012)", "Retro",
         "304775-135", 220),
        ("Jordan", "Air Jordan 7", "Cardinal (2022)", "Retro",
         "CU9307-106", 200),
        ("Jordan", "Air Jordan 8", "Aqua", "OG Colorway",
         "305381-025", 200),
        ("Jordan", "Air Jordan 9", "Chile Red", "Retro",
         "CT8019-600", 190),
        ("Jordan", "Air Jordan 10", "Seattle", "Retro",
         "310805-137", 180),
        ("Jordan", "Air Jordan 10", "Shadow (2018)", "Retro",
         "310805-002", 200),
    ]


def _sb_dunk_deep_cuts() -> list[tuple]:
    """15 Nike SB Dunk deep cuts and classics."""
    return [
        ("Nike", "SB Dunk Low", "Skunk (420)", "Quickstrike",
         "305050-231", 3500),
        ("Nike", "SB Dunk Low", "De La Soul High (2005)", "Collaboration",
         "305050-261", 2000),
        ("Nike", "SB Dunk Low", "What The Dunk SB", "Quickstrike",
         "318403-141S", 2200),
        ("Nike", "SB Dunk Low", "Tiffany (Low 2005)", "Collaboration",
         "304292-402T", 2800),
        ("Nike", "SB Dunk Low", "Unkle (Futura)", "Collaboration",
         "305050-013", 3000),
        ("Nike", "SB Dunk Low", "Supreme White Cement (2002)", "Collaboration",
         "304292-001", 2500),
        ("Nike", "SB Dunk Low", "Zoo York", "Quickstrike",
         "304292-173", 1800),
        ("Nike", "SB Dunk Low", "Medicom 3", "Collaboration",
         "304292-005", 2000),
        ("Nike", "SB Dunk Low", "Sean Cliver Holiday Special", "Collaboration",
         "DC9936-100", 600),
        ("Nike", "SB Dunk Low", "Jarritos (SB)", "Collaboration",
         "FD0860-001S", 500),
        ("Nike", "SB Dunk Low", "Powerpuff Girls Blossom", "Collaboration",
         "FD2631-600", 350),
        ("Nike", "SB Dunk Low", "Powerpuff Girls Bubbles", "Collaboration",
         "FD2631-400", 350),
        ("Nike", "SB Dunk Low", "Powerpuff Girls Buttercup", "Collaboration",
         "FD2631-300", 350),
        ("Nike", "SB Dunk Low", "Instant Skateboards", "Collaboration",
         "CZ5128-400", 450),
        ("Nike", "SB Dunk Low", "Parra Abstract Art (2021)", "Collaboration",
         "DH7695-600", 550),
    ]


def _air_max_deep_cuts() -> list[tuple]:
    """15 Air Max key colorways across AM1, 90, 95, 97, Plus."""
    return [
        ("Nike", "Air Max 1", "Obsidian (2017)", "Retro",
         "AH8145-104", 200),
        ("Nike", "Air Max 1", "Crepe Hemp", "Retro",
         "FD5088-200", 180),
        ("Nike", "Air Max 1", "Dirty Denim", "Limited Release",
         "DQ8475-001", 220),
        ("Nike", "Air Max 90", "Reverse Duck Camo", "Limited Release",
         "CW6024-600", 250),
        ("Nike", "Air Max 90", "Bacon (DQM 2020)", "Collaboration",
         "CU1816-100B", 380),
        ("Nike", "Air Max 90", "Mars Landing", "Limited Release",
         "CD0920-600", 350),
        ("Nike", "Air Max 95", "Greedy (2015)", "Limited Release",
         "810374-078", 280),
        ("Nike", "Air Max 95", "Corteiz Pink Beam", "Collaboration",
         "FB2709-600", 350),
        ("Nike", "Air Max 95", "Sketch With The Past", "Limited Release",
         "DX4615-100", 200),
        ("Nike", "Air Max 97", "Gold Metallic", "OG Colorway",
         "884421-700", 250),
        ("Nike", "Air Max 97", "Jesus Shoes (MSCHF)", "Collaboration",
         "MSCHF-97", 3000),
        ("Nike", "Air Max 97", "Sean Wotherspoon Corduroy", "Collaboration",
         "AJ4219-400S", 1400),
        ("Nike", "Air Max Plus", "Hyper Blue (2024)", "Retro",
         "FN6949-400", 160),
        ("Nike", "Air Max Plus", "Sunset", "OG Colorway",
         "604133-475", 200),
        ("Nike", "Air Max Plus", "Triple Black", "OG Colorway",
         "604133-050", 160),
    ]


def _nike_running_collabs() -> list[tuple]:
    """15 Nike running-silhouette collaborations."""
    return [
        ("Nike", "Air Max 1", "Patta Waves Rush Maroon", "Collaboration",
         "DO9549-001", 350),
        ("Nike", "Air Max 1", "Patta Waves Noise Aqua", "Collaboration",
         "DQ0299-100P", 340),
        ("Nike", "Air Max 1", "CLOT Solar Red", "Collaboration",
         "DD1636-600", 350),
        ("Nike", "Air Max 1", "CLOT Kiss of Death", "Collaboration",
         "DD1636-100", 600),
        ("Nike", "Air Max 90", "UNDFTD White", "Collaboration",
         "CJ7197-101", 250),
        ("Nike", "Air Max 90", "Concepts Boston", "Collaboration",
         "DN2019-200", 300),
        ("Nike", "Air Humara", "Jacquemus Gold", "Collaboration",
         "DR0420-700", 280),
        ("Nike", "Zoom Vomero 5", "A Cold Wall Anthracite", "Collaboration",
         "AT3152-001", 500),
        ("Nike", "Zoom Vomero 5", "Photon Dust", "Retro",
         "HF0731-001", 170),
        ("Nike", "Air Zoom Spiridon", "Parra (2018)", "Collaboration",
         "AV4744-100", 350),
        ("Nike", "Air Rift", "Supreme Black", "Collaboration",
         "DO3810-001", 220),
        ("Nike", "Air Zoom Type", "Sacai White", "Collaboration",
         "CV1363-100Z", 280),
        ("Nike", "Air Footscape Woven", "Rainbow", "Limited Release",
         "FN0380-200", 250),
        ("Nike", "Free Run Trail", "A-Cold-Wall Fossil", "Collaboration",
         "CW7010-200", 300),
        ("Nike", "Pegasus Trail 4 Gore-Tex", "Cacao Wow", "Limited Release",
         "DJ7926-200", 170),
    ]


def _adidas_forum_rivalry_zx() -> list[tuple]:
    """15 Adidas Forum, Rivalry, ZX, Campus collabs and retros."""
    return [
        ("Adidas", "Forum Low", "Bad Bunny Pink Easter Egg", "Collaboration",
         "GW0265", 280),
        ("Adidas", "Forum Low", "Bad Bunny Benito White", "Collaboration",
         "HQ2153B", 250),
        ("Adidas", "Forum 84 High", "OG White Green", "Retro",
         "FY7997", 120),
        ("Adidas", "Rivalry Low", "Prada White", "Collaboration",
         "FW6682", 480),
        ("Adidas", "Rivalry 86 Low", "OG White/Blue", "Retro",
         "IF6262", 100),
        ("Adidas", "ZX 8000", "BAPE Undefeated Blue", "Collaboration",
         "FY8852", 350),
        ("Adidas", "ZX 8000", "LEGO Yellow", "Collaboration",
         "FZ3482", 200),
        ("Adidas", "ZX 10000", "Overkill 1/10", "Collaboration",
         "G26252", 300),
        ("Adidas", "Campus 80s", "BAPE 30th Anniversary", "Collaboration",
         "ID4770", 250),
        ("Adidas", "Campus 00s", "Bliss Lilac", "Retro",
         "HQ8025", 100),
        ("Adidas", "Spezial", "Handball Spezial Light Blue", "Retro",
         "BD7633", 110),
        ("Adidas", "Sambae", "Wales Bonner Cream", "Collaboration",
         "ID4817", 320),
        ("Adidas", "Gazelle Indoor", "JJJJound Blue", "Collaboration",
         "IE5765", 280),
        ("Adidas", "NMD R1", "Tokyo", "Limited Release",
         "S79162", 250),
        ("Adidas", "Ultra Boost 1.0", "OG Core Black Purple", "OG Colorway",
         "B27171", 200),
    ]


def _new_balance_2002r_1906r_550() -> list[tuple]:
    """15 New Balance 2002R, 1906R, 550 collabs and picks."""
    return [
        ("New Balance", "NB 2002R", "Salehe Bembury Water Be The Guide", "Collaboration",
         "ML2002R1", 450),
        ("New Balance", "NB 2002R", "Salehe Bembury Peace Be The Journey", "Collaboration",
         "ML2002RO", 420),
        ("New Balance", "NB 2002R", "Thisisneverthat Teal", "Collaboration",
         "ML2002RT", 300),
        ("New Balance", "NB 2002R", "Kith Sandrift", "Collaboration",
         "M2002RKH", 400),
        ("New Balance", "NB 2002R", "Olive", "Limited Release",
         "M2002ROG", 200),
        ("New Balance", "NB 1906R", "Protection Pack Eclipse", "Limited Release",
         "M1906REC", 190),
        ("New Balance", "NB 1906R", "New Spruce", "Limited Release",
         "M1906RBB", 170),
        ("New Balance", "NB 1906R", "Noritake", "Collaboration",
         "M1906RNK", 250),
        ("New Balance", "NB 550", "Rich Paul Forever Yours", "Collaboration",
         "BB550RR1", 280),
        ("New Balance", "NB 550", "ALD Grey", "Collaboration",
         "BB550ALD2", 300),
        ("New Balance", "NB 550", "Conversations Amongst Us (Brick)", "Collaboration",
         "BB550JR1", 350),
        ("New Balance", "NB 990v6", "WTAPS Olive", "Collaboration",
         "M990WT6", 450),
        ("New Balance", "NB 990v5", "Kith Cyclades", "Collaboration",
         "M990KH5", 400),
        ("New Balance", "NB 997", "Concepts Rosé", "Collaboration",
         "M997CPT", 500),
        ("New Balance", "NB 999", "Concepts Hyannis (Kennedy)", "Collaboration",
         "ML999CP", 450),
    ]


def _asics_all_collabs() -> list[tuple]:
    """15 ASICS collabs (Kith, JFG, Ronnie Fieg, etc.)."""
    return [
        ("ASICS", "Gel-Lyte III", "Ronnie Fieg Homage", "Collaboration",
         "H54FK-6540", 550),
        ("ASICS", "Gel-Lyte III", "Ronnie Fieg Salmon Toe", "Collaboration",
         "H12QK-3628", 800),
        ("ASICS", "Gel-Lyte III", "Ronnie Fieg Militia", "Collaboration",
         "H30FK-8485", 500),
        ("ASICS", "Gel-Lyte III", "Kith x Marvel Wolverine", "Collaboration",
         "1203A535-001", 380),
        ("ASICS", "Gel-Lyte III", "Kith Yoshino Rose (2023)", "Collaboration",
         "1203A535-700", 420),
        ("ASICS", "Gel-Lyte V", "Ronnie Fieg Rose Gold", "Collaboration",
         "H725L-2121", 500),
        ("ASICS", "Gel-Lyte V", "Ronnie Fieg Sage", "Collaboration",
         "H42JK-8181", 450),
        ("ASICS", "GT-2160", "Above The Clouds Grey", "Collaboration",
         "1203A545-020", 280),
        ("ASICS", "GT-2160", "JJJJound Cream", "Collaboration",
         "1203A530-100", 300),
        ("ASICS", "Gel-Kayano 14", "Unlimited Smoke Grey", "Collaboration",
         "1203A549-020", 250),
        ("ASICS", "Gel-Kayano 5 OG", "Kiko Kostadinov Cream", "Collaboration",
         "1021A166-200", 350),
        ("ASICS", "Gel-Lyte III", "Joe Freshgoods Lava", "Collaboration",
         "1203A365-600", 350),
        ("ASICS", "Gel-NYC", "Oatmeal/Obsidian", "Retro",
         "1203A280-103", 150),
        ("ASICS", "Gel-Nimbus 9", "Kith Rogue", "Collaboration",
         "1203A567-200", 320),
        ("ASICS", "Gel-1130", "Cream Birch", "Retro",
         "1203A255-100", 130),
    ]


def _salomon_expansion() -> list[tuple]:
    """10 Salomon XT-4, XT-6 collabs and key models."""
    return [
        ("Salomon", "XT-4 OG", "Advanced Vanilla Ice", "Retro",
         "L47133200", 200),
        ("Salomon", "XT-4", "Comme des Garcons Black", "Collaboration",
         "L47389100", 450),
        ("Salomon", "XT-6", "10 Year Anniversary White", "Limited Release",
         "L47458900", 250),
        ("Salomon", "XT-6", "Atmos Clear Blue", "Collaboration",
         "L47451100", 300),
        ("Salomon", "XT-6 GTX", "Suicoke Slate", "Collaboration",
         "L47463200", 350),
        ("Salomon", "XT-6", "Random Event White Gum", "Collaboration",
         "L47459300", 280),
        ("Salomon", "XT-Wings 2", "Boris Bidjan Saberi Black", "Collaboration",
         "L41305800", 400),
        ("Salomon", "ACS Pro", "Fumito Ganryu White", "Collaboration",
         "L47380300", 350),
        ("Salomon", "XT PU.RE Advanced", "And Wander Beige", "Collaboration",
         "L47390100", 280),
        ("Salomon", "Speedcross 3", "Palace Red", "Collaboration",
         "L47461100", 300),
    ]


def _converse_collabs() -> list[tuple]:
    """10 Converse CDG, Fear of God, Golf Le Fleur collabs."""
    return [
        ("Converse", "Chuck 70", "CDG Play Multi Heart White", "Collaboration",
         "171850C", 180),
        ("Converse", "Chuck 70", "CDG Play Small Heart Black Low", "Collaboration",
         "150206C", 160),
        ("Converse", "Chuck 70", "CDG Play Red Heart Cream High", "Collaboration",
         "150205C", 170),
        ("Converse", "Chuck 70", "Fear of God Essentials Black", "Collaboration",
         "167954C", 250),
        ("Converse", "Chuck 70", "Fear of God Essentials Ivory", "Collaboration",
         "167955C", 280),
        ("Converse", "One Star", "Golf Le Fleur Blue", "Collaboration",
         "162126C", 200),
        ("Converse", "One Star", "Golf Le Fleur Industrial Pack Green", "Collaboration",
         "164024C", 180),
        ("Converse", "Chuck 70", "A-COLD-WALL Pavement", "Collaboration",
         "A06841C", 200),
        ("Converse", "Pro Leather", "Trash Talk OG", "Collaboration",
         "166595C", 150),
        ("Converse", "Run Star Hike", "JW Anderson Black", "Collaboration",
         "164840C", 220),
    ]


def _reebok_collabs() -> list[tuple]:
    """10 Reebok Question, Pump, Club C collabs."""
    return [
        ("Reebok", "Question Mid", "Iverson Georgetown (2021)", "Retro",
         "FX0987", 150),
        ("Reebok", "Question Mid", "Kobe Mismatched", "Player Exclusive",
         "GX0047K", 500),
        ("Reebok", "Question Mid", "BBC Ice Cream", "Collaboration",
         "FZ4341", 280),
        ("Reebok", "Pump Fury", "Atmos Tokyo", "Collaboration",
         "FY3045", 350),
        ("Reebok", "Pump Fury", "Vetements Star Wars", "Collaboration",
         "BS7031V", 600),
        ("Reebok", "Club C 85", "JJJJound White Grey", "Collaboration",
         "GY7158", 200),
        ("Reebok", "Club C 85", "Eames Elephant", "Collaboration",
         "GY1065", 150),
        ("Reebok", "Classic Leather", "JJJJound Grey", "Collaboration",
         "GY7189", 180),
        ("Reebok", "Answer IV", "Stepover White/Red", "Retro",
         "GX6235", 160),
        ("Reebok", "Shaq Attaq", "Orlando Magic", "Retro",
         "V47915", 180),
    ]


def _jordan_11_thru_14_retros() -> list[tuple]:
    """15 Air Jordan 11-14 additional retro colorways."""
    return [
        ("Jordan", "Air Jordan 11", "Gamma Blue", "Retro",
         "378037-006", 350),
        ("Jordan", "Air Jordan 11", "Win Like 96", "Retro",
         "378037-623", 280),
        ("Jordan", "Air Jordan 11", "Legend Blue (2014)", "Retro",
         "378037-117", 300),
        ("Jordan", "Air Jordan 11", "Cap and Gown", "Retro",
         "378037-005", 320),
        ("Jordan", "Air Jordan 11", "Jubilee (25th Anniversary)", "Retro",
         "CT8012-011", 280),
        ("Jordan", "Air Jordan 12", "Taxi", "OG Colorway",
         "CT8013-170", 240),
        ("Jordan", "Air Jordan 12", "Royalty", "Retro",
         "130690-014", 220),
        ("Jordan", "Air Jordan 12", "Playoff (2022)", "Retro",
         "CT8013-006", 260),
        ("Jordan", "Air Jordan 13", "He Got Game", "OG Colorway",
         "414571-104", 220),
        ("Jordan", "Air Jordan 13", "Flint (2020)", "Retro",
         "414571-404", 250),
        ("Jordan", "Air Jordan 13", "Starfish", "Retro",
         "414571-108", 200),
        ("Jordan", "Air Jordan 14", "Ginger", "Retro",
         "487471-701", 200),
        ("Jordan", "Air Jordan 14", "Winterized (Archaeo Brown)", "Retro",
         "DO9406-200", 190),
        ("Jordan", "Air Jordan 12", "University Gold", "Retro",
         "130690-070", 230),
        ("Jordan", "Air Jordan 13", "Lucky Green (2023)", "Retro",
         "DB6537-113", 240),
    ]


def _nike_sb_expansion_2() -> list[tuple]:
    """15 more Nike SB collabs and key releases."""
    return [
        ("Nike", "SB Dunk Low", "Grateful Dead Orange Bear", "Collaboration",
         "CJ5378-800", 1600),
        ("Nike", "SB Dunk Low", "April Skateboards White", "Collaboration",
         "FD2562-100", 400),
        ("Nike", "SB Dunk Low", "Phillies (Concepts)", "Collaboration",
         "FD8778-100", 500),
        ("Nike", "SB Dunk Low", "Crenshaw Skate Club", "Collaboration",
         "FN4193-100", 350),
        ("Nike", "SB Dunk High", "Supreme By Any Means Denim", "Collaboration",
         "DN3741-002", 400),
        ("Nike", "SB Dunk Low", "Born x Raised (2025)", "Collaboration",
         "FQ3228-001", 450),
        ("Nike", "SB Dunk Low", "Carpet Company", "Collaboration",
         "CV1677-100", 500),
        ("Nike", "SB Dunk Low", "Otomo Katsuhiro Steamboy", "Collaboration",
         "LF0010-001", 400),
        ("Nike", "SB Dunk Low", "Fly Streetwear Gardenia", "Collaboration",
         "DQ5130-100", 300),
        ("Nike", "SB Dunk Low", "St. Patrick's Day (Camo)", "Quickstrike",
         "BQ6817-300", 350),
        ("Nike", "SB Dunk Low", "Gundam Unicorn White", "Collaboration",
         "DH7717-100", 450),
        ("Nike", "SB Dunk High", "Thomas Campbell What The", "Collaboration",
         "918321-381", 350),
        ("Nike", "SB Dunk Low", "Ishod Wair Magnus Walker BMW", "Collaboration",
         "DH7683-100", 300),
        ("Nike", "SB Dunk Low", "Verdy Girls Don't Cry", "Collaboration",
         "DD3357-100", 600),
        ("Nike", "SB Dunk Low", "Soulgoods Grey", "Collaboration",
         "DR1126-001", 350),
    ]


def _asics_gel_lyte_iii_collabs() -> list[tuple]:
    """ASICS Gel-Lyte III collaborations — Kith, Ronnie Fieg, etc."""
    return [
        ("ASICS", "Gel-Lyte III", "Kith x Fieg 'Salmon Toe'", "Collaboration",
         "H44KK-7271", 450),
        ("ASICS", "Gel-Lyte III", "Ronnie Fieg 'Homage'", "Collaboration",
         "H54FK-6540", 500),
        ("ASICS", "Gel-Lyte III", "Ronnie Fieg 'Militia'", "Collaboration",
         "MILITIA-01", 350),
        ("ASICS", "Gel-Lyte III", "Kith 'Super Gold'", "Collaboration",
         "1201A396-750", 380),
        ("ASICS", "Gel-Lyte III", "Ronnie Fieg 'Volcano 2.0'", "Collaboration",
         "1201A459-020", 320),
        ("ASICS", "Gel-Lyte III", "AFEW x Kith 'Shimizu'", "Collaboration",
         "1201A764-200", 350),
        ("ASICS", "Gel-Lyte III", "atmos 'World Map'", "Collaboration",
         "H50BK-9050", 280),
        ("ASICS", "Gel-Lyte III", "Packer Shoes 'Dirty Buck'", "Collaboration",
         "H50TK-1212", 300),
    ]


def _salomon_xt6_collabs() -> list[tuple]:
    """Salomon XT-6 collaborations — Advanced, MM6, etc."""
    return [
        ("Salomon", "XT-6", "Advanced Black/Phantom", "Limited Release",
         "L41085700", 220),
        ("Salomon", "XT-6", "Advanced Soft Ground White", "Limited Release",
         "L47468400", 230),
        ("Salomon", "XT-6", "MM6 Maison Margiela Black", "Collaboration",
         "EE7740", 650),
        ("Salomon", "XT-6", "MM6 Maison Margiela White", "Collaboration",
         "EE7741", 680),
        ("Salomon", "XT-6", "Sandy Liang Expanse Green", "Collaboration",
         "L47469700", 350),
        ("Salomon", "XT-6", "Palace Grey", "Collaboration",
         "L47863400", 400),
        ("Salomon", "XT-6", "BEAMS Green Moss", "Collaboration",
         "L47356500", 320),
        ("Salomon", "XT-6", "11 By Boris Bidjan Saberi Black", "Collaboration",
         "L47261800", 450),
    ]


def _nb_2002r_jjjjound_collabs() -> list[tuple]:
    """New Balance 2002R — Protection Pack, JJJJound, etc."""
    return [
        ("New Balance", "2002R", "Protection Pack Rain Cloud", "Limited Release",
         "M2002RDA", 280),
        ("New Balance", "2002R", "Protection Pack Mirage Grey", "Limited Release",
         "M2002RDB", 260),
        ("New Balance", "2002R", "Protection Pack Phantom", "Limited Release",
         "M2002RDC", 270),
        ("New Balance", "2002R", "Protection Pack Sea Salt", "Limited Release",
         "M2002RDG", 250),
        ("New Balance", "2002R", "JJJJound Navy", "Collaboration",
         "M2002RJB", 420),
        ("New Balance", "2002R", "Salehe Bembury Water Be The Guide", "Collaboration",
         "M2002RSB", 380),
        ("New Balance", "2002R", "Thisisneverthat Grey", "Collaboration",
         "ML2002RN", 300),
    ]


def _reebok_question_collabs() -> list[tuple]:
    """Reebok Question Mid — AI Answer, collaborations."""
    return [
        ("Reebok", "Question Mid", "Allen Iverson 'Red Toe'", "OG Colorway",
         "GX0230", 180),
        ("Reebok", "Question Mid", "Allen Iverson 'Blue Toe'", "OG Colorway",
         "GX0227", 170),
        ("Reebok", "Question Mid", "Panini Prizm Silver", "Collaboration",
         "GW8856", 250),
        ("Reebok", "Question Mid", "Concepts 'Liquid Gold'", "Collaboration",
         "FZ4342", 320),
        ("Reebok", "Question Mid", "Eric Emanuel Red", "Collaboration",
         "GX0294", 220),
        ("Reebok", "Question Mid", "Packer Shoes 'Practice'", "Collaboration",
         "FW7548", 300),
        ("Reebok", "Answer IV", "Allen Iverson 'Stepover'", "OG Colorway",
         "GY0528", 200),
    ]


def _puma_collabs_expanded() -> list[tuple]:
    """Puma collaborations — LaMelo Ball, Rihanna Fenty, etc."""
    return [
        ("Puma", "MB.01", "LaMelo Ball 'Rick and Morty'", "Collaboration",
         "376682-01", 250),
        ("Puma", "MB.01", "LaMelo Ball 'Not From Here' Galaxy", "Limited Release",
         "377237-02", 220),
        ("Puma", "MB.01", "LaMelo Ball 'Queen City'", "Limited Release",
         "376316-03", 200),
        ("Puma", "MB.02", "LaMelo Ball 'Supernova'", "Limited Release",
         "378065-01", 180),
        ("Puma", "MB.04", "LaMelo Ball 'Iridescent'", "Limited Release",
         "309207-01", 160),
        ("Puma", "Fenty Creeper", "Rihanna Fenty Velvet Black", "Collaboration",
         "364466-01", 350),
        ("Puma", "Fenty Creeper", "Rihanna Fenty Velvet Royal Purple", "Collaboration",
         "364466-02", 380),
        ("Puma", "Fenty Trainer", "Rihanna Fenty Mid White", "Collaboration",
         "190398-01", 300),
        ("Puma", "Fenty Avid", "Rihanna Fenty Avid Black", "Collaboration",
         "367682-02", 220),
        ("Puma", "Suede Classic", "BAPE Camo Green", "Collaboration",
         "366293-01", 280),
        ("Puma", "MB.03", "LaMelo Ball 'Toxic'", "Limited Release",
         "379235-01", 190),
        ("Puma", "Clyde", "Rihanna Fenty Creeper Patent Black", "Collaboration",
         "364462-01", 400),
        ("ASICS", "Gel-Lyte III", "SNS 'Taichi'", "Collaboration",
         "1201A373-750", 300),
        ("ASICS", "Gel-Lyte III", "Reigning Champ Grey", "Collaboration",
         "H53GK-9001", 280),
        ("Salomon", "XT-6", "COMME des GARCONS Black", "Collaboration",
         "L47364200", 550),
        ("Salomon", "XT-6", "SATISFY Running Pack Green", "Collaboration",
         "L47366100", 350),
        ("New Balance", "2002R", "Aime Leon Dore Green", "Collaboration",
         "ML2002RA", 400),
        ("New Balance", "2002R", "SNS 'Goods' Brown", "Collaboration",
         "ML2002RG", 320),
        ("Reebok", "Question Low", "Allen Iverson Georgetown", "OG Colorway",
         "FX0987", 160),
    ]


def _nike_dunk_collabs_round4() -> list[tuple]:
    """Nike Dunk collaborations — Round 4 expansion."""
    return [
        ("Nike", "Dunk Low", "Concepts Orange Lobster", "Collaboration",
         "FD8776-800", 450),
        ("Nike", "Dunk Low", "Concepts Green Lobster", "Collaboration",
         "BV1310-337", 1200),
        ("Nike", "Dunk Low", "Concepts Purple Lobster", "Collaboration",
         "BV1310-555", 900),
        ("Nike", "Dunk Low", "Social Status Free Lunch Strawberry Milk", "Collaboration",
         "DJ1173-600", 350),
        ("Nike", "Dunk Low", "Union LA Passport Pack Court Purple", "Collaboration",
         "DJ9649-500", 300),
        ("Nike", "Dunk Low", "Born x Raised", "Collaboration",
         "FN7733-010", 320),
        ("Nike", "Dunk Low", "Cactus Plant Flea Market Spiral Sage", "Collaboration",
         "DD7340-001", 550),
        ("Nike", "Dunk Low", "CLOT Fragment Design", "Collaboration",
         "FN0315-110", 480),
    ]


def _new_balance_collabs_round4() -> list[tuple]:
    """New Balance collaborations — Round 4 expansion."""
    return [
        ("New Balance", "990v6", "JJJJound Grey", "Collaboration",
         "M990JJ6", 380),
        ("New Balance", "990v6", "Kith 'United' Navy", "Collaboration",
         "M990KH6", 350),
        ("New Balance", "1906R", "ALD 'Green'", "Collaboration",
         "M1906RA1", 320),
        ("New Balance", "550", "STAUD White Gum", "Collaboration",
         "BB550STD", 250),
        ("New Balance", "9060", "JJJJound Beige", "Collaboration",
         "U9060JJ1", 400),
        ("New Balance", "9060", "Joe Freshgoods Inside Voices Blue", "Collaboration",
         "U9060JF1", 350),
    ]


def _adidas_yeezy_round4() -> list[tuple]:
    """Adidas Yeezy — Round 4 expansion."""
    return [
        ("Yeezy", "Yeezy 350 V2", "Onyx", "Limited Release",
         "HQ4540", 280),
        ("Yeezy", "Yeezy 350 V2", "Bone", "Limited Release",
         "HQ6316", 250),
        ("Yeezy", "Yeezy 350 V2", "Dazzling Blue", "Limited Release",
         "GY7164", 260),
        ("Yeezy", "Yeezy 350 V2", "MX Rock", "Limited Release",
         "GW3774", 280),
        ("Yeezy", "Yeezy 700 V3", "Azael", "Limited Release",
         "FW4980", 350),
        ("Yeezy", "Yeezy 700 V3", "Fade Carbon", "Limited Release",
         "GW1814", 300),
        ("Yeezy", "Yeezy Foam Runner", "Stone Sage", "Limited Release",
         "GX4472", 160),
    ]


def _jordan_retro_reissues_round4() -> list[tuple]:
    """Jordan retro reissues — Round 4 expansion."""
    return [
        ("Jordan", "Air Jordan 3", "A Ma Maniere Raised By Women", "Collaboration",
         "DH3434-110", 500),
        ("Jordan", "Air Jordan 4", "Metallic Purple", "Retro",
         "CT8527-115", 280),
        ("Jordan", "Air Jordan 4", "Vivid Sulfur (W)", "Retro",
         "AQ9129-700", 250),
        ("Jordan", "Air Jordan 5", "Olive", "Retro",
         "DD0587-308", 260),
        ("Jordan", "Air Jordan 12", "Taxi 2024 Reimagined", "Retro",
         "CT8013-170", 220),
        ("Jordan", "Air Jordan 1 High", "Lost and Found Chicago", "Retro",
         "DZ5485-612", 280),
    ]


def _asics_collabs_round4() -> list[tuple]:
    """ASICS collaborations — Round 4 expansion."""
    return [
        ("ASICS", "Gel-Kayano 14", "JJJJound Silver White", "Collaboration",
         "1201A457-100", 350),
        ("ASICS", "Gel-1130", "Hidden NY Cream", "Collaboration",
         "1201A256-750", 300),
        ("ASICS", "Gel-NYC", "Kith Cream", "Collaboration",
         "1201A822-100", 280),
        ("ASICS", "GT-2160", "Joe Freshgoods Below Freezing", "Collaboration",
         "1203A465-020", 320),
        ("ASICS", "Gel-Kayano 14", "Above The Clouds White", "Collaboration",
         "1201A457-200", 380),
    ]


def _salomon_trail_fashion_round4() -> list[tuple]:
    """Salomon trail fashion — Round 4 expansion."""
    return [
        ("Salomon", "XT-6", "Beams 'Sand'", "Collaboration",
         "L47373500", 400),
        ("Salomon", "XT-6", "11 By Boris Bidjan Black", "Collaboration",
         "L47188900", 480),
        ("Salomon", "XT-6 Expanse", "Sandy Beige", "Limited Release",
         "L47380800", 220),
        ("Salomon", "XT-4 OG", "Alloy/Ebony/Lunar Rock", "Retro",
         "L47382600", 180),
        ("Salomon", "ACS Pro", "Ciele Athletics Cream", "Collaboration",
         "L47177300", 350),
        ("Salomon", "XT-PU.RE Advanced", "MM6 Maison Margiela White", "Collaboration",
         "L47401000", 600),
        ("Salomon", "XT-Wings 2", "Palace Skateboards Black Orange", "Collaboration",
         "L47399200", 450),
    ]


def _puma_collabs_round4() -> list[tuple]:
    """Puma collaborations — Round 4 expansion."""
    return [
        ("Puma", "Mostro", "Perks and Mini Black Vintage", "Collaboration",
         "396468-01", 250),
        ("Puma", "Velophasis", "Pleasures 'Yin Yang' Black White", "Collaboration",
         "396473-01", 200),
        ("Puma", "Suede XL", "RIPNDIP Lord Nermal", "Collaboration",
         "396476-01", 180),
        ("Puma", "Palermo", "PUMA x Noah Navy Gum", "Collaboration",
         "396471-02", 160),
        ("Puma", "MB.03", "LaMelo Ball 'Porsche' Motorsport", "Collaboration",
         "309561-01", 220),
        ("Puma", "Speedcat OG", "Sparco Motorsport Red", "Collaboration",
         "398846-01", 240),
        ("Puma", "RS-X", "Transformers Optimus Prime", "Collaboration",
         "391174-01", 280),
    ]


def _nike_sb_dunk_2024() -> list[tuple]:
    """Nike SB Dunk Low 2024 releases — Round 5 expansion."""
    return [
        ("Nike", "SB Dunk Low", "HUF San Francisco", "Collaboration",
         "FD8775-100", 320),
        ("Nike", "SB Dunk Low", "Why So Sad? Grey", "Collaboration",
         "DX5549-400", 250),
        ("Nike", "SB Dunk Low", "Supreme Rammellzee Black", "Collaboration",
         "FD8778-001", 550),
        ("Nike", "SB Dunk Low", "Yuto Horigome Wolf Grey", "Collaboration",
         "FQ1180-001", 320),
    ]


def _jordan_1_low_collabs_r5() -> list[tuple]:
    """Air Jordan 1 Low collaborations — Round 5 expansion."""
    return [
        ("Jordan", "Air Jordan 1 Low", "Dior Grey", "Collaboration",
         "CN8608-001", 4500),
        ("Jordan", "Air Jordan 1 Low", "Fragment Design White Blue", "Collaboration",
         "DM7866-140", 650),
        ("Jordan", "Air Jordan 1 Low", "PSG Paris Saint-Germain", "Collaboration",
         "CK0687-006", 280),
        ("Jordan", "Air Jordan 1 Low", "x Zion Williamson Voodoo", "Collaboration",
         "DZ7292-200", 180),
        ("Jordan", "Air Jordan 1 Low", "Year of the Dragon Crimson", "Limited Release",
         "FJ5735-100", 220),
        ("Jordan", "Air Jordan 1 Low", "EasternStar Jade Smoke", "Limited Release",
         "FQ9112-100", 160),
        ("Jordan", "Air Jordan 1 Low", "Bleached Coral (W)", "GR (General Release)",
         "DC0774-801", 140),
        ("Jordan", "Air Jordan 1 Low", "Shattered Backboard Low", "OG Colorway",
         "553558-128", 250),
    ]


def _jordan_4_retro_r5() -> list[tuple]:
    """Air Jordan 4 retros — Round 5 expansion."""
    return [
        ("Jordan", "Air Jordan 4", "Bred Reimagined (2024)", "Retro",
         "FV5029-006", 350),
        ("Jordan", "Air Jordan 4", "Oxidized Green", "Retro",
         "FQ8138-103", 260),
        ("Jordan", "Air Jordan 4", "Lightning (2021 Retro)", "Retro",
         "CT8527-700", 300),
        ("Jordan", "Air Jordan 4", "Midnight Navy", "Retro",
         "DH6927-140", 300),
        ("Jordan", "Air Jordan 4", "Craft Olive", "Retro",
         "FB9927-200", 300),
        ("Jordan", "Air Jordan 4", "Fear Pack", "Retro",
         "626969-030", 380),
        ("Jordan", "Air Jordan 4", "Canyon Purple (W)", "Retro",
         "AQ9129-500-W", 240),
        ("Jordan", "Air Jordan 4", "Infrared", "Retro",
         "DH6927-061", 320),
        ("Jordan", "Air Jordan 4", "Black Canvas", "Retro",
         "DH7138-006", 280),
    ]


def _adidas_samba_collabs_r5() -> list[tuple]:
    """Adidas Samba collaborations — Round 5 expansion."""
    return [
        ("Adidas", "Samba OG", "Wales Bonner Cream White", "Collaboration",
         "GY4344", 380),
        ("Adidas", "Samba OG", "Wales Bonner Silver Metallic", "Collaboration",
         "IF0580", 420),
        ("Adidas", "Samba OG", "Wales Bonner Pony Leopard", "Collaboration",
         "IG4298", 500),
        ("Adidas", "Samba OG", "Pharrell Humanrace White", "Collaboration",
         "IF3655", 280),
        ("Adidas", "Samba OG", "Messi Indoor White Green", "Collaboration",
         "ID3550", 200),
        ("Adidas", "Samba OG", "JJJJound Brown", "Collaboration",
         "ID8709", 350),
        ("Adidas", "Samba OG", "Kith Classics White Navy", "Collaboration",
         "IF3664", 300),
        ("Adidas", "Samba", "Sporty & Rich Cream", "Collaboration",
         "IF5930", 280),
        ("Adidas", "Samba", "Grace Wales Bonner Black", "Collaboration",
         "ID3546", 360),
        ("Adidas", "Samba", "INIKI x Ronnie Fieg Navy", "Collaboration",
         "ID3548", 250),
    ]


def _nb_1906r_collabs_r5() -> list[tuple]:
    """New Balance 1906R collaborations — Round 5 expansion."""
    return [
        ("New Balance", "1906R", "Protection Pack Silver Blue", "Limited Release",
         "M1906REE", 200),
        ("New Balance", "1906R", "Protection Pack Rain Cloud", "Limited Release",
         "M1906REB", 190),
        ("New Balance", "1906R", "Protection Pack Turtledove", "Limited Release",
         "M1906REC", 210),
        ("New Balance", "1906R", "New Spruce (2024)", "Limited Release",
         "M1906RBB", 180),
        ("New Balance", "1906R", "Joe Freshgoods 'Conversation Amongst Us'", "Collaboration",
         "M1906RJF", 400),
        ("New Balance", "1906R", "Kith 10th Anniversary Cyclades", "Collaboration",
         "M1906RKT", 350),
        ("New Balance", "1906R", "Teddy Santis Sea Salt", "Collaboration",
         "M1906RTS", 250),
        ("New Balance", "1906R", "Cordura Black Orange", "Limited Release",
         "M1906RCB", 220),
        ("New Balance", "1906R", "Refined Future Magnet", "Limited Release",
         "M1906RMG", 190),
    ]


def _asics_kayano14_collabs_r5() -> list[tuple]:
    """ASICS Gel-Kayano 14 collaborations — Round 5 expansion."""
    return [
        ("ASICS", "Gel-Kayano 14", "Kiko Kostadinov Cream", "Collaboration",
         "1201A019-107", 380),
        ("ASICS", "Gel-Kayano 14", "Windand Sea Black Silver", "Collaboration",
         "1201A457-001", 320),
        ("ASICS", "Gel-Kayano 14", "Bricks & Wood Cream Sage", "Collaboration",
         "1201A457-300", 350),
        ("ASICS", "Gel-Kayano 14", "GMBH Vyner Cloud Grey", "Collaboration",
         "1201A019-020", 400),
        ("ASICS", "Gel-Kayano 14", "Matin Kim Pink Cream", "Collaboration",
         "1202A389-700", 300),
        ("ASICS", "Gel-Kayano 14", "Cream Pepper (2024)", "Limited Release",
         "1201A019-115", 250),
        ("ASICS", "Gel-Kayano 14", "Black Graphite Grey OG", "Retro",
         "1201A019-005", 180),
        ("ASICS", "Gel-Kayano 14", "White Midnight Blue", "Retro",
         "1201A019-102", 170),
        ("ASICS", "Gel-Kayano 14", "Cloud Grey Pure Silver", "Retro",
         "1201A019-024", 165),
        ("ASICS", "Gel-Kayano 14", "Endless Summer Pack Yellow", "Limited Release",
         "1201A457-750", 230),
    ]


def _salomon_xt6_collabs_r5() -> list[tuple]:
    """Salomon XT-6 collaborations — Round 5 expansion."""
    return [
        ("Salomon", "XT-6", "COMME des GARCONS CDG Black", "Collaboration",
         "L41732800", 550),
        ("Salomon", "XT-6", "Better Gift Shop Purple", "Collaboration",
         "L47401500", 480),
        ("Salomon", "XT-6", "Fumito Ganryu Grey White", "Collaboration",
         "L47188200", 420),
        ("Salomon", "XT-6", "Salehe Bembury Biscotto Sand", "Collaboration",
         "L47401800", 500),
        ("Salomon", "XT-6", "Hidden.NY Hazelnut", "Collaboration",
         "L47400200", 450),
        ("Salomon", "XT-6 Advanced", "and wander Black", "Collaboration",
         "L47420100", 400),
        ("Salomon", "XT-6 Advanced", "Sandy Liang Ballet Pink", "Collaboration",
         "L47420400", 380),
        ("Salomon", "XT-6", "Vanilla Ice White (2024)", "Limited Release",
         "L47373800", 200),
        ("Salomon", "XT-6 GORE-TEX", "Black Black GTX", "Limited Release",
         "L47401100", 250),
        ("Salomon", "XT-6", "Dover Street Market Silver Gold", "Collaboration",
         "L47400800", 520),
    ]


def _puma_suede_vtg_r5() -> list[tuple]:
    """Puma Suede Vintage and other Puma collabs — Round 5 expansion."""
    return [
        ("Puma", "Suede VTG", "atmos Crazy Pattern", "Collaboration",
         "396474-01", 220),
        ("Puma", "Suede VTG", "Butter Goods Green Brown", "Collaboration",
         "396475-01", 180),
        ("Puma", "Suede VTG", "The Hundreds Checkered", "Collaboration",
         "396479-01", 200),
        ("Puma", "Suede VTG", "Michael Lau Sample Friends & Family", "F&F (Friends & Family)",
         "396480-01", 600),
        ("Puma", "Suede VTG", "Classic Navy White (Re-Issue)", "Retro",
         "374921-04", 90),
        ("Puma", "Suede VTG", "Staple Pigeon Grey Pink", "Collaboration",
         "396477-01", 250),
        ("Puma", "Suede XL", "PLEASURES Skull Black", "Collaboration",
         "396478-01", 190),
        ("Puma", "Clyde", "BAPE 1st Camo Olive", "Collaboration",
         "396481-01", 320),
        ("Puma", "Suede VTG", "A.P.C. Khaki Minimal", "Collaboration",
         "396483-01", 200),
    ]


def _nike_am1_anniversary_r5() -> list[tuple]:
    """Nike Air Max 1 anniversary and special editions — Round 5 expansion."""
    return [
        ("Nike", "Air Max 1", "OG Anniversary Red (2023 Re-Release)", "OG Colorway",
         "DO9549-100", 250),
        ("Nike", "Air Max 1", "Anniversary Aqua/Neutral Grey", "OG Colorway",
         "DH1348-004", 220),
        ("Nike", "Air Max 1", "Concepts Heavy", "Collaboration",
         "DN1803-900", 450),
        ("Nike", "Air Max 1", "CLOT K.O.D. Solar Red", "Collaboration",
         "DD1636-600", 350),
        ("Nike", "Air Max 1", "Travis Scott Cactus Jack Baroque Brown", "Collaboration",
         "DO9392-200", 380),
        ("Nike", "Air Max 1", "Travis Scott Cactus Jack Saturn Gold", "Collaboration",
         "DO9392-700", 420),
        ("Nike", "Air Max 1", "Kasina Won-Ang Orange", "Collaboration",
         "DQ8475-800", 300),
        ("Nike", "Air Max 1", "Patta Aqua Noise (5th Anniv)", "Collaboration",
         "DH1348-001", 350),
        ("Nike", "Air Max 1", "Obsidian (2024 Retro)", "Retro",
         "FJ4735-400", 180),
    ]


def _aj1_high_colorways_r6() -> list[tuple]:
    """12 Air Jordan 1 High colorways — Mocha, Obsidian, Shadow 2.0, etc."""
    return [
        ("Jordan", "Air Jordan 1 High", "Dark Mocha", "Retro",
         "555088-105", 350),
        ("Jordan", "Air Jordan 1 High", "Obsidian UNC", "Retro",
         "555088-140", 380),
        ("Jordan", "Air Jordan 1 High", "Shadow 2.0", "Retro",
         "555088-035", 250),
        ("Jordan", "Air Jordan 1 High", "Pollen", "Retro",
         "555088-701", 200),
        ("Jordan", "Air Jordan 1 High", "Volt Gold", "Retro",
         "555088-118", 220),
        ("Jordan", "Air Jordan 1 High", "Chicago Reimagined (Lost & Found)", "Retro",
         "DZ5485-612R6", 280),
        ("Jordan", "Air Jordan 1 High", "Taxi (Black Toe Yellow)", "Retro",
         "555088-711", 230),
        ("Jordan", "Air Jordan 1 High", "Stage Haze", "Retro",
         "555088-108", 210),
        ("Jordan", "Air Jordan 1 High", "Palomino", "Retro",
         "FD2596-021", 240),
        ("Jordan", "Air Jordan 1 High", "Washed Pink (W)", "Retro",
         "FD2596-600", 220),
        ("Jordan", "Air Jordan 1 High", "True Blue", "Retro",
         "DZ5485-410", 260),
        ("Jordan", "Air Jordan 1 High", "Yellow Ochre", "Retro",
         "555088-109", 200),
    ]


def _aj1_low_mid_r6() -> list[tuple]:
    """10 Air Jordan 1 Low and Mid variants."""
    return [
        ("Jordan", "Air Jordan 1 Low", "UNC", "Retro",
         "553558-144", 130),
        ("Jordan", "Air Jordan 1 Low", "Bred Toe", "Retro",
         "553558-612", 140),
        ("Jordan", "Air Jordan 1 Low", "Shadow Toe", "Retro",
         "553558-052", 120),
        ("Jordan", "Air Jordan 1 Low", "Mocha", "Retro",
         "553558-032", 150),
        ("Jordan", "Air Jordan 1 Low", "Wolf Grey", "GR (General Release)",
         "553558-053", 100),
        ("Jordan", "Air Jordan 1 Mid", "Chicago Black Toe", "Retro",
         "554724-069", 130),
        ("Jordan", "Air Jordan 1 Mid", "Banned", "Retro",
         "554724-074", 140),
        ("Jordan", "Air Jordan 1 Mid", "Smoke Grey", "GR (General Release)",
         "554724-092", 110),
        ("Jordan", "Air Jordan 1 Mid", "Light Smoke Grey", "GR (General Release)",
         "554724-078", 100),
        ("Jordan", "Air Jordan 1 Mid", "Royal Blue 2.0", "Retro",
         "554724-068", 120),
    ]


def _aj3_5_11_colorways_r6() -> list[tuple]:
    """10 Air Jordan 3, 5, 11 additional colorways."""
    return [
        ("Jordan", "Air Jordan 3", "Pine Green", "Retro",
         "CT8532-030", 230),
        ("Jordan", "Air Jordan 3", "Georgetown", "Retro",
         "CT8532-401", 220),
        ("Jordan", "Air Jordan 3", "Racer Blue", "Retro",
         "CT8532-145", 210),
        ("Jordan", "Air Jordan 5", "Aqua", "Retro",
         "DD0587-400", 220),
        ("Jordan", "Air Jordan 5", "Moonlight", "Retro",
         "CT4838-011", 200),
        ("Jordan", "Air Jordan 5", "Green Bean", "Retro",
         "DM9014-003", 230),
        ("Jordan", "Air Jordan 11", "Midnight Navy", "Retro",
         "378037-441", 300),
        ("Jordan", "Air Jordan 11", "Gratitude / Defining Moments", "Retro",
         "CT8012-170", 280),
        ("Jordan", "Air Jordan 11", "DMP (2023)", "Retro",
         "CT8012-170D", 290),
        ("Jordan", "Air Jordan 11", "72-10", "Retro",
         "378037-002", 350),
    ]


def _aj4_colorways_r6() -> list[tuple]:
    """8 Air Jordan 4 colorway variants."""
    return [
        ("Jordan", "Air Jordan 4", "Black Cat (2020)", "Retro",
         "CU1110-010", 500),
        ("Jordan", "Air Jordan 4", "University Blue", "Retro",
         "CT8527-400", 350),
        ("Jordan", "Air Jordan 4", "Shimmer (W)", "Retro",
         "DJ0675-200", 280),
        ("Jordan", "Air Jordan 4", "Neon / Air Max 95", "Retro",
         "CT5342-007", 300),
        ("Jordan", "Air Jordan 4", "Fire Red (2020)", "Retro",
         "DC7770-160", 280),
        ("Jordan", "Air Jordan 4", "Taupe Haze", "Retro",
         "DB0732-200", 250),
        ("Jordan", "Air Jordan 4", "Blank Canvas (W)", "Retro",
         "DJ0675-110", 260),
        ("Jordan", "Air Jordan 4", "SB Pine Green", "Collaboration",
         "DR5415-103", 350),
    ]


def _nike_dunk_colorways_r6() -> list[tuple]:
    """10 Nike Dunk Low colorway variants."""
    return [
        ("Nike", "Dunk Low", "Georgetown", "Retro",
         "DD1391-003", 120),
        ("Nike", "Dunk Low", "Michigan", "Retro",
         "DD1391-700", 130),
        ("Nike", "Dunk Low", "Argon", "Retro",
         "DD1391-044", 110),
        ("Nike", "Dunk Low", "Vintage Green", "Retro",
         "DD1391-101VG", 115),
        ("Nike", "Dunk Low", "Photon Dust", "GR (General Release)",
         "DD1391-103PD", 100),
        ("Nike", "Dunk Low", "Court Purple", "Retro",
         "DD1391-104", 120),
        ("Nike", "Dunk Low", "Team Green", "Retro",
         "DD1391-101TG", 115),
        ("Nike", "Dunk Low", "Valerian Blue", "Retro",
         "DD1391-400", 110),
        ("Nike", "Dunk Low", "Dusty Olive", "Retro",
         "DH5360-300", 120),
        ("Nike", "Dunk Low", "Fossil Rose", "Retro",
         "DH7577-001", 130),
    ]


def _nike_dunk_womens_r6() -> list[tuple]:
    """6 Nike Dunk Low women's exclusive colorways."""
    return [
        ("Nike", "Dunk Low", "Rose Whisper (W) 2024", "GR (General Release)",
         "DD1503-118-W", 100),
        ("Nike", "Dunk Low", "Next Nature Pale Coral (W)", "GR (General Release)",
         "DD1873-100", 95),
        ("Nike", "Dunk Low", "Cacao Wow (W)", "GR (General Release)",
         "DD1503-124W", 100),
        ("Nike", "Dunk Low", "Pink Foam (W)", "GR (General Release)",
         "DD1503-600", 95),
        ("Nike", "Dunk Low", "Diffused Taupe (W)", "GR (General Release)",
         "DD1503-125", 100),
        ("Nike", "Dunk Low", "Coconut Milk (W)", "GR (General Release)",
         "DD1503-116", 95),
    ]


def _yeezy_350v2_colorways_r6() -> list[tuple]:
    """10 Yeezy 350 V2 colorway variants."""
    return [
        ("Yeezy", "Yeezy Boost 350 V2", "Blue Tint", "Limited Release",
         "B37571", 300),
        ("Yeezy", "Yeezy Boost 350 V2", "Cloud White", "Limited Release",
         "FW3043", 240),
        ("Yeezy", "Yeezy Boost 350 V2", "Yecheil", "Limited Release",
         "FW5190", 260),
        ("Yeezy", "Yeezy Boost 350 V2", "Desert Sage", "Limited Release",
         "FX9035", 230),
        ("Yeezy", "Yeezy Boost 350 V2", "Ash Pearl", "Limited Release",
         "GY7658", 220),
        ("Yeezy", "Yeezy Boost 350 V2", "Sesame", "Limited Release",
         "F99710", 270),
        ("Yeezy", "Yeezy Boost 350 V2", "Semi Frozen Yellow", "Limited Release",
         "B37572", 280),
        ("Yeezy", "Yeezy Boost 350 V2", "Cinder", "Limited Release",
         "FY2903", 260),
        ("Yeezy", "Yeezy Boost 350 V2", "Tail Light", "Limited Release",
         "FX9017", 240),
        ("Yeezy", "Yeezy Boost 350 V2", "Slate", "Limited Release",
         "HP7870", 250),
    ]


def _yeezy_500_700_r6() -> list[tuple]:
    """8 Yeezy 500 and 700 variants."""
    return [
        ("Yeezy", "Yeezy 500", "Bone White", "Limited Release",
         "FV3573", 260),
        ("Yeezy", "Yeezy 500", "Stone", "Limited Release",
         "FW4839", 250),
        ("Yeezy", "Yeezy 500", "Ash Grey", "Limited Release",
         "GX3607", 240),
        ("Yeezy", "Yeezy 500", "Taupe Light", "Limited Release",
         "GX3605", 230),
        ("Yeezy", "Yeezy Boost 700", "Mauve", "Limited Release",
         "EE9614", 320),
        ("Yeezy", "Yeezy Boost 700", "Utility Black", "Limited Release",
         "FV5304", 350),
        ("Yeezy", "Yeezy Boost 700", "Inertia", "Limited Release",
         "EG7597", 300),
        ("Yeezy", "Yeezy Boost 700 MNVN", "Triple Black", "Limited Release",
         "FV4440", 280),
    ]


def _nb_550_2002r_990_r6() -> list[tuple]:
    """10 New Balance 550, 2002R, 990v5/v6 colorway variants."""
    return [
        ("New Balance", "NB 550", "White Navy", "Retro",
         "BB550WA1", 120),
        ("New Balance", "NB 550", "White Red", "Retro",
         "BB550SE1", 120),
        ("New Balance", "NB 550", "Shadow Grey", "Retro",
         "BB550SL1", 130),
        ("New Balance", "NB 2002R", "Black Phantom", "Limited Release",
         "M2002RBK", 220),
        ("New Balance", "NB 2002R", "Marblehead", "Limited Release",
         "M2002RXA", 210),
        ("New Balance", "NB 2002R", "Dark Navy", "Limited Release",
         "M2002RCA", 200),
        ("New Balance", "NB 990v5", "Grey (Made in USA)", "OG Colorway",
         "M990GL5", 200),
        ("New Balance", "NB 990v5", "Navy (Made in USA)", "OG Colorway",
         "M990NV5", 200),
        ("New Balance", "NB 990v6", "Grey (Made in USA)", "OG Colorway",
         "M990GL6", 210),
        ("New Balance", "NB 990v6", "Black (Made in USA)", "OG Colorway",
         "M990BK6", 210),
    ]


def _asics_kayano14_gellyte_r6() -> list[tuple]:
    """8 ASICS Gel-Kayano 14 and Gel-Lyte III colorways."""
    return [
        ("ASICS", "Gel-Kayano 14", "White Midnight (2024)", "Retro",
         "1201A019-106", 170),
        ("ASICS", "Gel-Kayano 14", "Pure Silver OG", "Retro",
         "1201A019-021", 165),
        ("ASICS", "Gel-Kayano 14", "Earthenware Pack Clay", "Limited Release",
         "1201A457-500", 220),
        ("ASICS", "Gel-Kayano 14", "Obsidian Blue", "Retro",
         "1201A019-400", 175),
        ("ASICS", "Gel-Lyte III", "White Rock", "OG Colorway",
         "H7L0L-0101", 120),
        ("ASICS", "Gel-Lyte III", "Black/Black", "OG Colorway",
         "H7L0L-9090", 120),
        ("ASICS", "Gel-Lyte III", "Birch/Ivory", "Retro",
         "1201A050-200", 130),
        ("ASICS", "Gel-Lyte III", "Piedmont Grey", "Retro",
         "1201A050-020", 125),
    ]


def _adidas_samba_gazelle_r6() -> list[tuple]:
    """10 Adidas Samba and Gazelle colorways (men's and women's)."""
    return [
        ("Adidas", "Samba OG", "Black/Gum", "OG Colorway",
         "B75807", 100),
        ("Adidas", "Samba OG", "Green/White", "Retro",
         "IG1024", 100),
        ("Adidas", "Samba OG", "Navy/Gum", "OG Colorway",
         "IE3437R6", 100),
        ("Adidas", "Samba OG", "Wonder Clay (W)", "GR (General Release)",
         "ID0478", 110),
        ("Adidas", "Samba OG", "Silver Green (W)", "GR (General Release)",
         "ID0492", 110),
        ("Adidas", "Gazelle", "Collegiate Navy", "OG Colorway",
         "BB5478", 90),
        ("Adidas", "Gazelle", "Black/White", "OG Colorway",
         "BB5476", 90),
        ("Adidas", "Gazelle", "Scarlet Red", "Retro",
         "BB5486", 90),
        ("Adidas", "Gazelle Bold", "True Pink (W)", "GR (General Release)",
         "HQ6893", 100),
        ("Adidas", "Gazelle Bold", "Green/Cloud White (W)", "GR (General Release)",
         "HQ6894", 100),
    ]


def _adidas_forum_low_r6() -> list[tuple]:
    """6 Adidas Forum Low variants."""
    return [
        ("Adidas", "Forum Low", "White/Blue", "Retro",
         "FY7756", 100),
        ("Adidas", "Forum Low", "White/Green", "Retro",
         "FY7757", 100),
        ("Adidas", "Forum Low", "Bad Bunny The Last Campus", "Collaboration",
         "ID4950", 300),
        ("Adidas", "Forum Low", "Bad Bunny Egg Shell", "Collaboration",
         "HQ2154", 270),
        ("Adidas", "Forum 84 Low", "Bape 30th Anniversary", "Collaboration",
         "ID4772", 280),
        ("Adidas", "Forum Low", "Cloud White Gum", "Retro",
         "GX1072", 95),
    ]


def _nike_af1_variants_r6() -> list[tuple]:
    """8 Nike Air Force 1 variants beyond triple white."""
    return [
        ("Nike", "Air Force 1 Low", "Tiffany & Co. 1837 (Friends & Family)", "F&F (Friends & Family)",
         "DZ1382-002", 2500),
        ("Nike", "Air Force 1 Low", "Travis Scott Sail (2019)", "Collaboration",
         "AQ4211-101R6", 550),
        ("Nike", "Air Force 1 Low", "Off-White The Ten White", "Collaboration",
         "AO4606-100", 800),
        ("Nike", "Air Force 1 Low", "Off-White Black", "Collaboration",
         "AO4606-001", 850),
        ("Nike", "Air Force 1 Low", "Supreme Box Logo White", "Collaboration",
         "CU9225-100", 350),
        ("Nike", "Air Force 1 Low", "Stussy Fossil", "Collaboration",
         "CZ9084-200", 300),
        ("Nike", "Air Force 1 Low", "NOCTA Drake Certified Lover Boy", "Collaboration",
         "CZ8065-100", 280),
        ("Nike", "Air Force 1 Low", "Triple Black", "GR (General Release)",
         "315122-001", 100),
    ]


def _nike_air_max_1_90_97_r6() -> list[tuple]:
    """10 Nike Air Max 1, 90, 97 colorway variants."""
    return [
        ("Nike", "Air Max 1", "Blueprint", "Limited Release",
         "DQ3989-100R6", 200),
        ("Nike", "Air Max 1", "Curry (2018)", "Retro",
         "908366-700", 180),
        ("Nike", "Air Max 1", "Magma Orange", "Retro",
         "CW6541-001", 170),
        ("Nike", "Air Max 90", "Infrared (2020 Retro)", "OG Colorway",
         "CT1685-100R6", 170),
        ("Nike", "Air Max 90", "Viotech OG", "Limited Release",
         "CD0917-600", 200),
        ("Nike", "Air Max 90", "Sail / Wheat", "Retro",
         "CZ3950-100", 150),
        ("Nike", "Air Max 97", "Triple White", "GR (General Release)",
         "921826-101", 170),
        ("Nike", "Air Max 97", "Mschf x Lil Nas X Satan Shoes", "Collaboration",
         "MSCHF-SATAN", 5000),
        ("Nike", "Air Max 97", "Off-White Menta", "Collaboration",
         "AJ4585-300", 600),
        ("Nike", "Air Max 97", "South Beach", "Limited Release",
         "921826-500", 220),
    ]


def _converse_chuck70_cdg_r6() -> list[tuple]:
    """8 Converse Chuck 70 and CDG collab variants."""
    return [
        ("Converse", "Chuck 70", "CDG Play Multi Heart Black", "Collaboration",
         "171851C", 180),
        ("Converse", "Chuck 70", "CDG Play Small Heart White Low", "Collaboration",
         "150207C", 160),
        ("Converse", "Chuck 70", "CDG Play Red Sole Black", "Collaboration",
         "A08796C", 190),
        ("Converse", "Chuck 70", "Parchment (Classic)", "OG Colorway",
         "162062C", 80),
        ("Converse", "Chuck 70", "Black (Classic)", "OG Colorway",
         "162058C", 80),
        ("Converse", "Chuck 70", "Rick Owens DRKSHDW Black", "Collaboration",
         "DC04BX7890", 250),
        ("Converse", "Chuck 70", "Stussy Pigment Dyed Green", "Collaboration",
         "A01765C", 200),
        ("Converse", "Chuck 70", "Kim Jones Black", "Collaboration",
         "171257C", 220),
    ]


def _puma_suede_rsx_r6() -> list[tuple]:
    """8 Puma Suede and RS-X variants."""
    return [
        ("Puma", "Suede Classic", "Black/White", "OG Colorway",
         "352634-03", 70),
        ("Puma", "Suede Classic", "Peacoat Navy", "OG Colorway",
         "356568-51", 70),
        ("Puma", "Suede Classic", "Stoney Grey", "OG Colorway",
         "365347-01", 75),
        ("Puma", "Suede Classic", "50th Anniversary Red", "Limited Release",
         "366332-01", 120),
        ("Puma", "RS-X³", "Puzzle White", "Retro",
         "371570-04", 100),
        ("Puma", "RS-X³", "Sonic the Hedgehog", "Collaboration",
         "373427-01", 180),
        ("Puma", "RS-X", "Ader Error Grey", "Collaboration",
         "369538-01", 160),
        ("Puma", "Speedcat OG", "Sparco Black", "OG Colorway",
         "398846-02", 110),
    ]


def _womens_specific_r6() -> list[tuple]:
    """10 women's-specific sneaker releases."""
    return [
        ("Jordan", "Air Jordan 1 High", "Satin Snake (W)", "Limited Release",
         "CD0461-601W", 450),
        ("Jordan", "Air Jordan 1 High", "Silver Toe (W)", "Limited Release",
         "CD0461-001", 300),
        ("Jordan", "Air Jordan 1 High", "Seafoam (W)", "Retro",
         "CD0461-002", 220),
        ("Jordan", "Air Jordan 1 High", "Atmosphere (W)", "Retro",
         "DD7399-100", 200),
        ("Nike", "Dunk Low", "Harvest Moon (W)", "GR (General Release)",
         "DD1503-114", 100),
        ("Nike", "Dunk Low", "Team Red (W)", "GR (General Release)",
         "DD1503-108", 100),
        ("Jordan", "Air Jordan 4", "Shimmer (W) 2024", "Retro",
         "DJ0675-200W", 270),
        ("Jordan", "Air Jordan 1 Low", "Arctic Pink (W)", "GR (General Release)",
         "DC0774-600", 120),
        ("Nike", "Air Force 1 Low", "Particle Beige (W)", "GR (General Release)",
         "CZ0270-200", 110),
        ("Adidas", "Samba OG", "Almost Pink (W)", "GR (General Release)",
         "IE5459", 120),
    ]


def _kids_gs_sizing_r6() -> list[tuple]:
    """6 kids/GS sizing sneakers with premium resale prices."""
    return [
        ("Jordan", "Air Jordan 1 High", "Travis Scott Mocha (GS)", "Collaboration",
         "CD4487-100-GS", 900),
        ("Jordan", "Air Jordan 4", "Off-White Sail (GS)", "Collaboration",
         "CV9388-100-GS", 700),
        ("Jordan", "Air Jordan 1 Low", "Travis Scott Reverse Mocha (GS)", "Collaboration",
         "DM7866-162-GS", 600),
        ("Jordan", "Air Jordan 4", "Black Cat (GS)", "Retro",
         "CU1110-010-GS", 350),
        ("Jordan", "Air Jordan 11", "Bred (GS)", "OG Colorway",
         "378038-061", 250),
        ("Jordan", "Air Jordan 1 High", "Lost & Found Chicago (GS)", "Retro",
         "FD1437-612", 200),
    ]


def _nike_dunk_expansion_r7() -> list[tuple]:
    """20 Nike Dunk expansions: Travis Scott, Off-White, Panda variants."""
    return [
        ("Nike", "Dunk Low", "Travis Scott (Cactus Jack)", "Collaboration",
         "CT5053-001", 1400),
        ("Nike", "Dunk Low", "Off-White Lot 1 (The 50)", "Collaboration",
         "DM1602-127", 900),
        ("Nike", "Dunk Low", "Off-White Lot 50 (The 50)", "Collaboration",
         "DM1602-001", 500),
        ("Nike", "Dunk Low", "Off-White Pine Green", "Collaboration",
         "CT0856-100", 600),
        ("Nike", "Dunk Low", "Panda (2024 Restock)", "GR (General Release)",
         "DD1391-100-24", 90),
        ("Nike", "Dunk Low", "Panda (Twist W)", "GR (General Release)",
         "DZ2794-001", 100),
        ("Nike", "Dunk Low", "Argon Blue", "GR (General Release)",
         "DM0121-400", 110),
        ("Nike", "Dunk Low", "Gorge Green", "GR (General Release)",
         "DD1391-300", 110),
        ("Nike", "Dunk Low", "Rose Whisper (W)", "GR (General Release)",
         "DD1503-118", 95),
        ("Nike", "Dunk High", "Travis Scott (Cactus Jack)", "Collaboration",
         "CT5053-900", 1200),
        ("Nike", "Dunk Low", "AMBUSH Black Fuchsia", "Collaboration",
         "CU7544-001", 350),
        ("Nike", "Dunk Low", "Concepts Green Lobster", "Collaboration",
         "BV1310-337", 1100),
        ("Nike", "Dunk Low", "Concepts Purple Lobster", "Collaboration",
         "BV1310-555", 1800),
        ("Nike", "Dunk Low", "Social Status Free Lunch Chocolate Milk", "Collaboration",
         "DM7866-600", 400),
        ("Nike", "Dunk Low", "Undefeated Dunk vs AF1 Purple", "Collaboration",
         "DH6508-400", 350),
        ("Nike", "Dunk Low", "Jarritos Green", "Collaboration",
         "FD0887-001", 500),
        ("Nike", "Dunk Low", "Supreme Hyper Blue", "Collaboration",
         "DH3228-100", 600),
    ]


def _aj1_expansion_r7() -> list[tuple]:
    """20 Air Jordan 1 expansions: Chicago, Royal, Shadow, Travis Scott."""
    return [
        ("Jordan", "Air Jordan 1 High", "Chicago (2015 Remaster)", "Retro",
         "555088-101-15", 1200),
        ("Jordan", "Air Jordan 1 High", "Lost and Found Chicago", "Retro",
         "DZ5485-612", 250),
        ("Jordan", "Air Jordan 1 High", "Royal (2017)", "OG Colorway",
         "555088-007-17", 350),
        ("Jordan", "Air Jordan 1 High", "Shadow 2.0", "Retro",
         "555088-035", 220),
        ("Jordan", "Air Jordan 1 High", "Travis Scott x Fragment Military Blue", "Collaboration",
         "DH3227-105-MB", 1800),
        ("Jordan", "Air Jordan 1 Low", "Travis Scott Reverse Mocha", "Collaboration",
         "DM7866-162", 1200),
        ("Jordan", "Air Jordan 1 Low", "Travis Scott Olive", "Collaboration",
         "DM7866-205", 700),
        ("Jordan", "Air Jordan 1 High", "Bordeaux (2021)", "Retro",
         "555088-611", 200),
        ("Jordan", "Air Jordan 1 High", "Palomino", "Retro",
         "DZ5485-180", 180),
        ("Jordan", "Air Jordan 1 High", "Washed Pink (W)", "Retro",
         "FD2596-600", 170),
        ("Jordan", "Air Jordan 1 High", "Yellow Ochre", "Retro",
         "DZ5485-701", 180),
        ("Jordan", "Air Jordan 1 High", "Satin Black Toe (W)", "Limited Release",
         "CD0461-016", 450),
        ("Jordan", "Air Jordan 1 High", "Homage to Home (Split)", "Limited Release",
         "861428-061", 600),
        ("Jordan", "Air Jordan 1 High", "Not For Resale (Red)", "Limited Release",
         "861428-106", 500),
        ("Jordan", "Air Jordan 1 High", "Not For Resale (Yellow)", "Limited Release",
         "861428-107", 450),
        ("Jordan", "Air Jordan 1 High", "A Ma Maniere (W)", "Collaboration",
         "DO7097-100", 400),
        ("Jordan", "Air Jordan 1 High", "Trophy Room (Chicago)", "Collaboration",
         "DA2728-100", 2500),
        ("Jordan", "Air Jordan 1 Mid", "Chicago Black Toe (2022)", "Retro",
         "554724-069", 130),
        ("Jordan", "Air Jordan 1 Mid", "Diamond Shorts", "Retro",
         "554724-131", 150),
        ("Jordan", "Air Jordan 1 Low", "Starfish (W)", "GR (General Release)",
         "CW7309-601", 120),
    ]


def _yeezy_expansion_r7() -> list[tuple]:
    """25 Yeezy expansions: Slide, Foam Runner, 350 V2."""
    return [
        ("Yeezy", "Yeezy Slide", "Onyx", "Limited Release",
         "HQ6448", 120),
        ("Yeezy", "Yeezy Slide", "Bone", "Limited Release",
         "FW6345", 110),
        ("Yeezy", "Yeezy Slide", "Pure", "Limited Release",
         "GW1934", 100),
        ("Yeezy", "Yeezy Slide", "Slate Grey", "Limited Release",
         "ID2350", 90),
        ("Yeezy", "Yeezy Slide", "Flax", "Limited Release",
         "FZ5896", 95),
        ("Yeezy", "Yeezy Foam Runner", "Onyx", "Limited Release",
         "HP8739", 130),
        ("Yeezy", "Yeezy Foam Runner", "Stone Sage", "Limited Release",
         "GX4472", 120),
        ("Yeezy", "Yeezy Foam Runner", "Sand", "Limited Release",
         "FY4567", 140),
        ("Yeezy", "Yeezy Foam Runner", "Vermilion (Red October)", "Limited Release",
         "GW3355", 160),
        ("Yeezy", "Yeezy Foam Runner", "MX Cream Clay", "Limited Release",
         "GX8774", 130),
        ("Yeezy", "Yeezy 350 V2", "Beluga Reflective", "Limited Release",
         "GW1229", 300),
        ("Yeezy", "Yeezy 350 V2", "MX Oat", "Limited Release",
         "GW3773", 200),
        ("Yeezy", "Yeezy 350 V2", "Onyx", "Limited Release",
         "HQ4540", 250),
        ("Yeezy", "Yeezy 350 V2", "Dazzling Blue", "Limited Release",
         "GY7164", 220),
        ("Yeezy", "Yeezy 350 V2", "Bone", "Limited Release",
         "HQ6316", 210),
        ("Yeezy", "Yeezy 350 V2", "Slate", "Limited Release",
         "HP7870", 200),
        ("Yeezy", "Yeezy 350 V2", "Granite", "Limited Release",
         "HQ2059", 200),
        ("Yeezy", "Yeezy 350 V2", "Jade Ash", "Limited Release",
         "GY4462", 190),
        ("Yeezy", "Yeezy 500", "Granite", "Limited Release",
         "GW6373", 180),
        ("Yeezy", "Yeezy 500", "Clay Brown", "Limited Release",
         "GX3606", 170),
        ("Yeezy", "Yeezy 500", "Blush (2022 Restock)", "Limited Release",
         "DB2908-22", 200),
        ("Yeezy", "Yeezy 700 V3", "Alvah", "Limited Release",
         "H67799", 250),
        ("Yeezy", "Yeezy 700 V3", "Azael", "Limited Release",
         "FW4980", 280),
        ("Yeezy", "Yeezy 700 V3", "Kyanite", "Limited Release",
         "GY0260", 230),
        ("Yeezy", "Yeezy 700", "Analog", "Limited Release",
         "B75571", 280),
    ]


def _nb_asics_adidas_expansion_r7() -> list[tuple]:
    """30 New Balance, ASICS, Adidas collabs."""
    return [
        # New Balance 550 collabs
        ("New Balance", "550", "ALD White Green", "Collaboration",
         "BB550ALD-G", 350),
        ("New Balance", "550", "ALD White Navy", "Collaboration",
         "BB550ALD-N", 300),
        ("New Balance", "550", "ALD White Red", "Collaboration",
         "BB550ALD-R", 280),
        ("New Balance", "550", "Rich Paul Forever Yours", "Collaboration",
         "BB550RP1", 200),
        ("New Balance", "550", "White Grey (OG)", "Retro",
         "BB550PB1", 110),
        # New Balance 2002R collabs
        ("New Balance", "2002R", "Protection Pack Rain Cloud", "Limited Release",
         "M2002RDA", 250),
        ("New Balance", "2002R", "Protection Pack Sea Salt", "Limited Release",
         "M2002RDC", 220),
        ("New Balance", "2002R", "JJJJound Grey", "Collaboration",
         "M2002RJD", 500),
        ("New Balance", "2002R", "JJJJound Navy", "Collaboration",
         "M2002RJE", 450),
        ("New Balance", "2002R", "Salehe Bembury Water Be The Guide", "Collaboration",
         "M2002RSB", 400),
        # ASICS Gel-Lyte III collabs
        ("ASICS", "Gel-Lyte III", "KITH Salmon Toe", "Collaboration",
         "H40FK-4636", 600),
        ("ASICS", "Gel-Lyte III", "KITH Super Gold", "Collaboration",
         "H43JK-9494", 400),
        ("ASICS", "Gel-Lyte III", "Atmos Mita Sneakers 1990", "Collaboration",
         "H50HK-9090", 350),
        ("ASICS", "Gel-Lyte III", "Sean Wotherspoon x atmos", "Collaboration",
         "1203A019-000", 450),
        ("ASICS", "Gel-Lyte III", "Ronnie Fieg Salmon Toe 2.0", "Collaboration",
         "H60NK-2124", 500),
        ("ASICS", "Gel-Kayano 14", "JJJJound Silver White", "Collaboration",
         "1201A457-020", 350),
        ("ASICS", "Gel-Kayano 14", "Above the Clouds Cream", "Collaboration",
         "1201A457-100", 300),
        # Adidas Samba collabs
        ("Adidas", "Samba OG", "White Black (Classic)", "OG Colorway",
         "B75806", 100),
        ("Adidas", "Samba OG", "Wales Bonner Cream White", "Collaboration",
         "GY4344", 350),
        ("Adidas", "Samba OG", "Wales Bonner Silver", "Collaboration",
         "IG8181", 300),
        ("Adidas", "Samba OG", "Pharrell Humanrace White", "Collaboration",
         "ID7339", 200),
        # Adidas Gazelle collabs
        ("Adidas", "Gazelle", "Gucci Green", "Collaboration",
         "GUCCI-GZ-GR", 850),
        ("Adidas", "Gazelle", "Gucci Pink", "Collaboration",
         "GUCCI-GZ-PK", 800),
        ("Adidas", "Gazelle", "JJJJound Grey", "Collaboration",
         "GY6040", 280),
        ("Adidas", "Gazelle Indoor", "Bad Bunny Blue", "Collaboration",
         "ID4041", 250),
        ("Adidas", "Gazelle Indoor", "Bad Bunny Pink", "Collaboration",
         "IG9830", 300),
        # Adidas Forum
        ("Adidas", "Forum Low", "Bad Bunny First Café", "Collaboration",
         "GW0264", 350),
        ("Adidas", "Forum Low", "Bad Bunny Blue Tint", "Collaboration",
         "GY4900", 300),
        ("Adidas", "Forum Buckle Low", "Bad Bunny Back to School", "Collaboration",
         "GY9693", 280),
        ("Adidas", "Campus 00s", "Core Black", "OG Colorway",
         "HQ8708", 100),
    ]


def _nike_sb_classics_r7() -> list[tuple]:
    """15 Nike SB classics and grails."""
    return [
        ("Nike", "SB Dunk Low", "Supreme Red Cement", "Collaboration",
         "313170-600", 1500),
        ("Nike", "SB Dunk Low", "Diamond Supply Co Tiffany (2005)", "Collaboration",
         "304292-402", 5000),
        ("Nike", "SB Dunk Low", "Freddy Krueger", "Collaboration",
         "313170-202", 8000),
        ("Nike", "SB Dunk Low", "Stussy Cherry", "Collaboration",
         "304292-671", 2500),
        ("Nike", "SB Dunk Low", "Raygun (Away)", "Limited Release",
         "304292-802", 1000),
        ("Nike", "SB Dunk Low", "Raygun (Home)", "Limited Release",
         "304292-411", 1200),
        ("Nike", "SB Dunk Low", "Reese Forbes Wheat", "Limited Release",
         "304292-731", 2000),
        ("Nike", "SB Dunk Low", "Supreme Black Cement", "Collaboration",
         "313170-001-SUP", 1200),
        ("Nike", "SB Dunk Low", "Parra Abstract Art (2021)", "Collaboration",
         "DH7695-600", 400),
        ("Nike", "SB Dunk Low", "Born x Raised One Block at a Time", "Collaboration",
         "FN7819-003", 350),
        ("Nike", "SB Dunk Low", "Jarritos", "Collaboration",
         "FD0887-001-SB", 350),
        ("Nike", "SB Dunk High", "Thomas Campbell What the Dunk", "Collaboration",
         "918321-381", 600),
        ("Nike", "SB Dunk High", "Doraemon", "Collaboration",
         "CI2692-400", 350),
        ("Nike", "SB Dunk Low", "Powerpuff Girls Blossom", "Collaboration",
         "FZ8320-600", 300),
        ("Nike", "SB Dunk Low", "Grateful Dead Green Bear", "Collaboration",
         "CJ5378-300", 2000),
    ]


def _additional_collabs_r7() -> list[tuple]:
    """40 additional collabs and colorways to reach 950+."""
    return [
        # Air Jordan 4 Retro
        ("Jordan", "Air Jordan 4", "Military Black", "Retro",
         "DH6927-111", 250),
        ("Jordan", "Air Jordan 4", "Red Thunder (Infrared)", "Retro",
         "CT8527-016", 280),
        ("Jordan", "Air Jordan 4", "Midnight Navy", "Retro",
         "DH6927-140", 260),
        ("Jordan", "Air Jordan 4", "Canyon Purple", "Retro",
         "AQ9129-500", 220),
        ("Jordan", "Air Jordan 4", "Craft Olive", "Retro",
         "FB9927-200", 250),
        # Air Jordan 3
        ("Jordan", "Air Jordan 3", "A Ma Maniere (W)", "Collaboration",
         "DH3434-110", 350),
        ("Jordan", "Air Jordan 3", "Pine Green", "Retro",
         "CT8532-030", 220),
        ("Jordan", "Air Jordan 3", "Palomino", "Retro",
         "CT8532-102", 200),
        ("Jordan", "Air Jordan 3", "Muslin", "Retro",
         "DH7139-100", 200),
        # Air Jordan 5
        ("Jordan", "Air Jordan 5", "Off-White Sail", "Collaboration",
         "DH8565-100", 500),
        ("Jordan", "Air Jordan 5", "Aqua (2025)", "Retro",
         "DD0587-400", 200),
        ("Jordan", "Air Jordan 5", "Burgundy (2023)", "Retro",
         "DV0562-600", 200),
        # Air Jordan 11
        ("Jordan", "Air Jordan 11", "Cool Grey (2021)", "Retro",
         "CT8012-005", 280),
        ("Jordan", "Air Jordan 11", "Cherry (2022)", "Retro",
         "CT8012-116", 250),
        ("Jordan", "Air Jordan 11", "Gratitude / DMP (2023)", "Retro",
         "CT8012-170", 250),
        # Nike Air Max
        ("Nike", "Air Max 90", "Bacon (2021)", "Retro",
         "CU1816-100", 250),
        ("Nike", "Air Max 1", "Concepts Mellow", "Collaboration",
         "DN1803-300", 350),
        ("Nike", "Air Max 1", "Concepts Far Out", "Collaboration",
         "DN1803-500", 400),
        ("Nike", "Air Max 1", "Patta Waves Aqua", "Collaboration",
         "DQ0299-100-AQ", 350),
        # Nike AF1 collabs
        ("Nike", "Air Force 1 Low", "Travis Scott Sail", "Collaboration",
         "AQ4211-101", 800),
        ("Nike", "Air Force 1 Low", "Louis Vuitton White", "Collaboration",
         "LV-AF1-WHT", 5000),
        ("Nike", "Air Force 1 Low", "Louis Vuitton Green", "Collaboration",
         "LV-AF1-GRN", 4500),
        ("Nike", "Air Force 1 Low", "Tiffany & Co. 1837", "Collaboration",
         "DZ1382-001", 500),
        # Salomon
        ("Salomon", "XT-6", "Black Phantom", "Limited Release",
         "L41252900", 200),
        ("Salomon", "XT-6", "Vanilla Ice", "Limited Release",
         "L47404900", 180),
        ("Salomon", "XT-6", "Mindful 2", "Collaboration",
         "L47449500", 250),
        ("Salomon", "XT-4", "COMME des GARCONS Black", "Collaboration",
         "CDG-XT4-BLK", 450),
        # Reebok
        ("Reebok", "Question Mid", "Allen Iverson Blue Toe (OG)", "OG Colorway",
         "GX0227", 150),
        ("Reebok", "Question Mid", "Allen Iverson Pearlized Gold", "Limited Release",
         "FX4278", 180),
        # Vans
        ("Vans", "Old Skool", "Supreme Black (2021)", "Collaboration",
         "VN0A5FC8-SUP", 200),
        ("Vans", "Sk8-Hi", "Supreme Hole Punch Denim", "Collaboration",
         "VN0A7Q5Y-SUP", 250),
        # Nike Running
        ("Nike", "Zoom Vomero 5", "Photon Dust", "Retro",
         "HF1553-001", 140),
        ("Nike", "Zoom Vomero 5", "Electric Green", "Retro",
         "HF1553-300", 150),
        ("Nike", "P-6000", "White/Metallic Silver", "Retro",
         "CN0149-100", 100),
        # Under Armour
        ("Under Armour", "Curry 4", "More Dimes", "Limited Release",
         "1298306-107", 200),
        ("Under Armour", "Curry 1 Low", "Championship (2025 Retro)", "Retro",
         "3028117-400", 150),
        # On Running
        ("On", "Cloudmonster", "Undyed White (Roger Federer)", "Collaboration",
         "ON-CM-RF-WHT", 200),
        # Additional to reach 950+
        ("Jordan", "Air Jordan 6", "Travis Scott British Khaki", "Collaboration",
         "DH0690-200", 500),
        ("Jordan", "Air Jordan 6", "Travis Scott Olive", "Collaboration",
         "CN1084-200", 600),
        ("Jordan", "Air Jordan 6", "UNC (2022)", "Retro",
         "CT8529-410", 220),
        ("Jordan", "Air Jordan 12", "Taxi (2024)", "Retro",
         "CT8013-170", 200),
        ("Jordan", "Air Jordan 12", "Playoffs (2022)", "Retro",
         "CT8013-006", 220),
        ("Jordan", "Air Jordan 13", "Bred (2017)", "Retro",
         "414571-004", 220),
        ("Jordan", "Air Jordan 13", "Flint (2020)", "Retro",
         "414571-404", 200),
        ("Nike", "Air Max 97", "Silver Bullet (2022)", "OG Colorway",
         "DM0028-002", 200),
        ("Nike", "Air Max 97", "Sean Wotherspoon (2018)", "Collaboration",
         "AJ4219-400", 800),
        ("Nike", "Air Max 95", "OG Neon (2023)", "OG Colorway",
         "CT1689-001-23", 180),
        ("Nike", "Air Max Plus", "Hyper Blue (OG)", "OG Colorway",
         "BQ4629-003", 150),
        ("Nike", "Air Max Plus", "Voltage Purple", "OG Colorway",
         "DX2663-001", 140),
    ]


def _womens_exclusives_r7() -> list[tuple]:
    """10 additional women's exclusive releases."""
    return [
        ("Jordan", "Air Jordan 1 High", "Lucky Green (W)", "Retro",
         "DB4612-300", 200),
        ("Jordan", "Air Jordan 1 High", "Dusted Clay (W)", "Retro",
         "FQ2941-200", 170),
        ("Jordan", "Air Jordan 4", "Vivid Sulfur (W)", "Retro",
         "AQ9129-700", 200),
        ("Jordan", "Air Jordan 4", "Seafoam (W)", "Retro",
         "AQ9129-103", 250),
        ("Nike", "Air Force 1 Low", "Triple White (W Classic)", "GR (General Release)",
         "DD8959-100", 90),
        ("Nike", "Dunk Low", "Medium Olive (W)", "GR (General Release)",
         "DD1503-120", 100),
        ("Nike", "Dunk Low", "Next Nature Lilac (W)", "GR (General Release)",
         "DN1431-103", 95),
        ("New Balance", "550", "White Sea Salt (W)", "GR (General Release)",
         "BBW550WB", 110),
        ("Adidas", "Samba OG", "Cloud White Gum (W)", "OG Colorway",
         "IE0877", 100),
        ("Jordan", "Air Jordan 3", "Dark Mocha (W)", "Retro",
         "FN0244-200", 200),
    ]


def _2025_2026_releases_expansion() -> list[tuple]:
    """40 notable 2025-2026 sneaker releases."""
    return [
        # --- Jordan 2025/2026 ---
        ("Jordan", "Air Jordan 1 High", "Reimagined Chicago (2025)", "Retro",
         "DZ5485-612", 250),
        ("Jordan", "Air Jordan 1 High", "Royal Reimagined (2025)", "Retro",
         "DZ5485-042", 230),
        ("Jordan", "Air Jordan 4", "Military Blue (2025)", "Retro",
         "FV5029-141", 240),
        ("Jordan", "Air Jordan 4", "Metallic Red (2025)", "Retro",
         "FV5029-161", 220),
        ("Jordan", "Air Jordan 5", "Grape (2025)", "Retro",
         "DV0564-500", 200),
        ("Jordan", "Air Jordan 6", "Black Infrared (2025)", "Retro",
         "CT8529-060", 210),
        ("Jordan", "Air Jordan 11", "DMP (2025)", "Retro",
         "CT8012-170", 270),
        ("Jordan", "Air Jordan 12", "Playoffs (2025)", "Retro",
         "CT8013-006", 220),
        ("Jordan", "Air Jordan 13", "Flint (2025)", "Retro",
         "DJ5982-100", 210),
        ("Jordan", "Air Jordan 3", "Fire Red (2025 Retro)", "Retro",
         "DN3707-160", 200),
        # --- Nike 2025/2026 ---
        ("Nike", "Air Max 1", "Jewel (2025)", "Retro",
         "FQ2704-100", 170),
        ("Nike", "Air Max 97", "Silver Bullet (2025 Retro)", "Retro",
         "DM0028-002", 185),
        ("Nike", "Air Force 1 Low", "40th Anniversary Special", "Limited Release",
         "FN5924-101", 150),
        ("Nike", "Dunk Low", "Panda Restock (2025)", "GR (General Release)",
         "DD1391-100R", 110),
        ("Nike", "Zoom Vomero 5", "SP Platinum (2025)", "Retro",
         "FN7649-002", 175),
        ("Nike", "Zoom Vomero 5", "SP Electric Green (2025)", "Retro",
         "FN7649-300", 175),
        ("Nike", "Zoom Vomero 5", "SP Burgundy Crush (2025)", "Retro",
         "FN7649-600", 175),
        ("Nike", "Air Max Dn8", "Triple Black", "GR (General Release)",
         "FN8888-001", 170),
        ("Nike", "Air Max Dn8", "Photon Dust", "GR (General Release)",
         "FN8888-003", 170),
        ("Nike", "Cortez", "50th Anniversary White/Red", "Retro",
         "FN7665-101", 120),
        ("Nike", "Book 1", "Devin Booker Moss Point", "Limited Release",
         "FJ4249-300", 160),
        ("Nike", "Book 1", "Devin Booker Mirage", "Limited Release",
         "FJ4249-400", 160),
        # --- New Balance 2025/2026 ---
        ("New Balance", "1906R", "Protection Pack Silver (2025)", "Retro",
         "M1906REE", 180),
        ("New Balance", "2002R", "Rain Cloud (2025)", "Retro",
         "M2002RXJ", 180),
        ("New Balance", "990v6", "Grey (2025)", "Retro",
         "M990GL6", 200),
        ("New Balance", "550", "ALD Green (2025)", "Collaboration",
         "BB550ALD", 180),
        ("New Balance", "1000", "Grey (2025)", "Retro",
         "M1000GR2", 180),
        ("New Balance", "1000", "Sea Salt (2025)", "Retro",
         "M1000SS", 180),
        # --- Adidas 2025/2026 ---
        ("Adidas", "Samba", "Wales Bonner Silver (2025)", "Collaboration",
         "IF0580", 250),
        ("Adidas", "Gazelle Indoor", "Cream White (2025)", "Retro",
         "IF1807", 130),
        ("Adidas", "Campus 00s", "Dark Green (2025)", "Retro",
         "IF4337", 110),
        ("Adidas", "Campus 00s", "Core Black (2025)", "Retro",
         "IF4338", 110),
        ("Adidas", "AE1 Low", "Anthony Edwards Ice Trae", "Limited Release",
         "IF8568", 140),
        ("Adidas", "Yeezy 350 V2", "Beluga (2025 Re-release)", "Limited Release",
         "RF7963-2025", 280),
        # --- Asics 2025/2026 ---
        ("Asics", "Gel-Kayano 14", "Cream (2025)", "Retro",
         "1201A019-108", 160),
        ("Asics", "Gel-NYC", "Oatmeal (2025)", "Retro",
         "1203A280-252", 150),
        ("Asics", "GT-2160", "White/Blue (2025)", "Retro",
         "1203A320-100", 140),
        # --- Salomon / On / Puma ---
        ("Salomon", "XT-6 Advanced", "Vanilla Ice (2025)", "Limited Release",
         "L47450200", 200),
        ("Salomon", "ACS Pro Advanced", "Black/Gum (2025)", "Limited Release",
         "L47450300", 190),
        ("On Running", "Cloudmonster 2", "All Black", "GR (General Release)",
         "61.99146", 180),
        ("On Running", "Cloudtilt", "Undyed White", "GR (General Release)",
         "37.99501", 200),
        ("Puma", "Speedcat OG", "Rihanna Fenty Black", "Collaboration",
         "39881101", 220),
    ]


def _womens_exclusives_expansion() -> list[tuple]:
    """30 women's exclusive sneakers."""
    return [
        # --- Jordan Women's ---
        ("Jordan", "Air Jordan 1 Mid SE", "Homage (W)", "Retro",
         "DC0774-106", 150),
        ("Jordan", "Air Jordan 1 Mid SE", "Crimson Tint (W)", "Retro",
         "DC0774-800", 140),
        ("Jordan", "Air Jordan 1 Mid SE", "Diamond Shorts (W)", "Limited Release",
         "DC0774-062", 160),
        ("Jordan", "Air Jordan 1 Low", "Coconut Milk (W)", "Retro",
         "DC0774-121", 120),
        ("Jordan", "Air Jordan 1 Low", "Wolf Grey (W)", "Retro",
         "DC0774-053", 120),
        ("Jordan", "Air Jordan 1 Low", "Mocha (W)", "Retro",
         "DC0774-200", 130),
        ("Jordan", "Air Jordan 4", "Canyon Purple (W)", "Retro",
         "AQ9129-500", 220),
        ("Jordan", "Air Jordan 3", "Palomino (W)", "Retro",
         "FN0244-126", 200),
        ("Jordan", "Air Jordan 5", "Mars for Her (W)", "Limited Release",
         "DV4982-608", 210),
        ("Jordan", "Air Jordan 11", "Gratitude (W)", "Retro",
         "AR0715-170", 230),
        ("Jordan", "Air Jordan 12", "Brilliant Orange (W)", "Retro",
         "DR8887-810", 210),
        # --- Nike Dunk Low Women's ---
        ("Nike", "Dunk Low", "Cacao Wow (W)", "GR (General Release)",
         "DD1503-129", 100),
        ("Nike", "Dunk Low", "Pink Foam (W)", "GR (General Release)",
         "DD1503-190", 100),
        ("Nike", "Dunk Low", "Next Nature White Sail (W)", "GR (General Release)",
         "DN1431-100", 95),
        ("Nike", "Dunk Low", "Rose Whisper Sail (W)", "GR (General Release)",
         "DD1503-118W", 100),
        ("Nike", "Dunk Low", "Dusty Olive (W)", "GR (General Release)",
         "DD1503-125", 105),
        ("Nike", "Dunk Low", "Light Carbon (W)", "GR (General Release)",
         "DD1503-132", 100),
        ("Nike", "Dunk Low", "Diffused Taupe (W)", "GR (General Release)",
         "DD1503-141", 100),
        # --- New Balance Women's ---
        ("New Balance", "530", "White Silver (W)", "GR (General Release)",
         "MR530SG-W", 100),
        ("New Balance", "530", "Sea Salt (W)", "GR (General Release)",
         "MR530AA-W", 100),
        ("New Balance", "550", "White Green (W)", "GR (General Release)",
         "BBW550BD", 110),
        ("New Balance", "550", "White Burgundy (W)", "GR (General Release)",
         "BBW550BR", 110),
        ("New Balance", "550", "White Grey (W)", "GR (General Release)",
         "BBW550BH", 110),
        # --- Adidas Women's ---
        ("Adidas", "Samba OG", "Cream (W)", "OG Colorway",
         "IE0877W", 110),
        ("Adidas", "Samba OG", "Almost Yellow (W)", "OG Colorway",
         "GY7410", 110),
        ("Adidas", "Samba OG", "Wonder Clay (W)", "OG Colorway",
         "IE0879", 110),
        # --- Asics Women's ---
        ("Asics", "Gel-1130", "Pure Silver (W)", "Retro",
         "1202A164-020", 130),
        ("Asics", "Gel-1130", "Cream Champagne (W)", "Retro",
         "1202A164-112", 130),
        ("Asics", "Gel-1130", "White Birch (W)", "Retro",
         "1202A164-100", 130),
    ]


def _collaboration_grails_expansion() -> list[tuple]:
    """30 collaboration grails — high-value sneaker collaborations."""
    return [
        # --- Travis Scott ---
        ("Jordan", "Air Jordan 4", "Travis Scott Cactus Jack Purple", "Collaboration",
         "FZ5498-001", 500),
        ("Jordan", "Air Jordan 6", "Travis Scott British Khaki", "Collaboration",
         "DH0690-200", 400),
        # --- Off-White ---
        ("Nike", "Dunk Low", "Off-White Lot 01 of 50", "Collaboration",
         "DM1602-127", 800),
        ("Nike", "Dunk Low", "Off-White Lot 09 of 50", "Collaboration",
         "DM1602-109", 450),
        ("Nike", "Dunk Low", "Off-White Lot 50 of 50", "Collaboration",
         "DM1602-001", 600),
        # --- A Ma Maniere ---
        ("Jordan", "Air Jordan 2", "A Ma Maniere", "Collaboration",
         "DO7216-100", 350),
        # --- Fragment / Travis Scott ---
        ("Jordan", "Air Jordan 1 Low", "Fragment x Travis Scott", "Collaboration",
         "DM7866-140", 1800),
        ("Nike", "Dunk High", "Fragment City Pack Tokyo", "Collaboration",
         "DJ0382-600", 400),
        # --- Union LA ---
        ("Jordan", "Air Jordan 4", "Union Off Noir", "Collaboration",
         "DC9533-001", 700),
        ("Jordan", "Air Jordan 4", "Union Guava Ice", "Collaboration",
         "DC9533-800", 750),
        ("Nike", "Dunk Low", "Union Passport Pack Pistachio", "Collaboration",
         "DJ9649-301", 350),
        # --- Sacai ---
        ("Nike", "Vaporwaffle", "sacai Sail Gum", "Collaboration",
         "DD1875-100", 350),
        ("Nike", "Vaporwaffle", "sacai Black White", "Collaboration",
         "DD3035-001", 300),
        ("Nike", "Vaporwaffle", "sacai Tour Yellow", "Collaboration",
         "DD1875-300", 320),
        ("Nike", "Blazer Mid", "sacai White Grey", "Collaboration",
         "BV0072-100", 280),
        # --- CLOT ---
        ("Nike", "Dunk Low", "CLOT What The", "Collaboration",
         "FN0316-999", 350),
        ("Nike", "Air Force 1 Low", "CLOT Rose Gold Silk", "Collaboration",
         "CJ5290-600", 600),
        # --- Eminem ---
        ("Jordan", "Air Jordan 4", "Eminem Encore", "F&F (Friends & Family)",
         "314770-001", 15000),
        ("Jordan", "Air Jordan 3", "Eminem Slim Shady", "F&F (Friends & Family)",
         "B0771SH", 12000),
        # --- Dior ---
        ("Jordan", "Air Jordan 1 High", "Dior", "Collaboration",
         "CN8607-002", 10000),
        ("Jordan", "Air Jordan 1 Low", "Dior", "Collaboration",
         "CN8608-002", 8000),
        # --- Louis Vuitton x Nike (Virgil Abloh) ---
        ("Nike", "Air Force 1 Low", "Louis Vuitton White/Green", "Collaboration",
         "1A9VAX", 7000),
        ("Nike", "Air Force 1 Low", "Louis Vuitton White/Red", "Collaboration",
         "1A9VAZ", 7500),
        ("Nike", "Air Force 1 Low", "Louis Vuitton Monogram", "Collaboration",
         "1A9VB0", 8000),
        ("Nike", "Air Force 1 Mid", "Louis Vuitton White/Blue", "Collaboration",
         "1A9VBG", 9000),
        ("Nike", "Air Force 1 Mid", "Louis Vuitton Graffiti", "Collaboration",
         "1A9VBH", 9500),
    ]


# ---------------------------------------------------------------------------
# Aggregate catalog
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[tuple]:
    """Return the full curated sneaker catalog (850+ items)."""
    catalog: list[tuple] = []
    catalog.extend(_air_jordan_1_high())
    catalog.extend(_jordan_1_expansion())
    catalog.extend(_air_jordan_retros())
    catalog.extend(_jordan_retro_expansion())
    catalog.extend(_nike_dunks())
    catalog.extend(_nike_dunk_expansion())
    catalog.extend(_nike_sb())
    catalog.extend(_nike_general_expansion())
    catalog.extend(_yeezy())
    catalog.extend(_yeezy_expansion())
    catalog.extend(_new_balance())
    catalog.extend(_new_balance_expansion())
    catalog.extend(_nike_air_max())
    catalog.extend(_nike_collaborations())
    catalog.extend(_adidas_non_yeezy())
    catalog.extend(_adidas_expansion())
    catalog.extend(_other_brands())
    catalog.extend(_puma_vans_expansion())
    catalog.extend(_asics_salomon())
    catalog.extend(_grails_ultra_rare())
    # --- Expansion (100+ new items) ---
    catalog.extend(_travis_scott_collabs())
    catalog.extend(_off_white_collabs())
    catalog.extend(_a_ma_maniere_union())
    catalog.extend(_sb_dunk_grails())
    catalog.extend(_fear_of_god_sacai())
    catalog.extend(_kobe_lebron_pe())
    catalog.extend(_womens_exclusives())
    catalog.extend(_regional_exclusives())
    catalog.extend(_2025_2026_releases())
    catalog.extend(_nb_asics_salomon_expansion())
    catalog.extend(_grails_expansion())
    catalog.extend(_adidas_puma_reebok_expansion())
    # --- Expansion Round 2 (170+ new items) ---
    catalog.extend(_jordan_2_thru_10_retros())
    catalog.extend(_sb_dunk_deep_cuts())
    catalog.extend(_air_max_deep_cuts())
    catalog.extend(_nike_running_collabs())
    catalog.extend(_adidas_forum_rivalry_zx())
    catalog.extend(_new_balance_2002r_1906r_550())
    catalog.extend(_asics_all_collabs())
    catalog.extend(_salomon_expansion())
    catalog.extend(_converse_collabs())
    catalog.extend(_reebok_collabs())
    catalog.extend(_jordan_11_thru_14_retros())
    catalog.extend(_nike_sb_expansion_2())
    # --- Expansion Round 3 (50 new items) ---
    catalog.extend(_asics_gel_lyte_iii_collabs())
    catalog.extend(_salomon_xt6_collabs())
    catalog.extend(_nb_2002r_jjjjound_collabs())
    catalog.extend(_reebok_question_collabs())
    catalog.extend(_puma_collabs_expanded())
    # --- Expansion Round 4 (55+ new items) ---
    catalog.extend(_nike_dunk_collabs_round4())
    catalog.extend(_new_balance_collabs_round4())
    catalog.extend(_adidas_yeezy_round4())
    catalog.extend(_jordan_retro_reissues_round4())
    catalog.extend(_asics_collabs_round4())
    catalog.extend(_salomon_trail_fashion_round4())
    catalog.extend(_puma_collabs_round4())
    # --- Expansion Round 5 (93 new items) ---
    catalog.extend(_nike_sb_dunk_2024())
    catalog.extend(_jordan_1_low_collabs_r5())
    catalog.extend(_jordan_4_retro_r5())
    catalog.extend(_adidas_samba_collabs_r5())
    catalog.extend(_nb_1906r_collabs_r5())
    catalog.extend(_asics_kayano14_collabs_r5())
    catalog.extend(_salomon_xt6_collabs_r5())
    catalog.extend(_puma_suede_vtg_r5())
    catalog.extend(_nike_am1_anniversary_r5())
    # --- Expansion Round 6 (~150 new items) ---
    catalog.extend(_aj1_high_colorways_r6())
    catalog.extend(_aj1_low_mid_r6())
    catalog.extend(_aj3_5_11_colorways_r6())
    catalog.extend(_aj4_colorways_r6())
    catalog.extend(_nike_dunk_colorways_r6())
    catalog.extend(_nike_dunk_womens_r6())
    catalog.extend(_yeezy_350v2_colorways_r6())
    catalog.extend(_yeezy_500_700_r6())
    catalog.extend(_nb_550_2002r_990_r6())
    catalog.extend(_asics_kayano14_gellyte_r6())
    catalog.extend(_adidas_samba_gazelle_r6())
    catalog.extend(_adidas_forum_low_r6())
    catalog.extend(_nike_af1_variants_r6())
    catalog.extend(_nike_air_max_1_90_97_r6())
    catalog.extend(_converse_chuck70_cdg_r6())
    catalog.extend(_puma_suede_rsx_r6())
    catalog.extend(_womens_specific_r6())
    catalog.extend(_kids_gs_sizing_r6())
    # --- Expansion Round 7 (~120 new items) ---
    catalog.extend(_nike_dunk_expansion_r7())
    catalog.extend(_aj1_expansion_r7())
    catalog.extend(_yeezy_expansion_r7())
    catalog.extend(_nb_asics_adidas_expansion_r7())
    catalog.extend(_nike_sb_classics_r7())
    catalog.extend(_womens_exclusives_r7())
    catalog.extend(_additional_collabs_r7())
    # --- Expansion Round 8 (~100 new items) ---
    catalog.extend(_2025_2026_releases_expansion())
    catalog.extend(_womens_exclusives_expansion())
    catalog.extend(_collaboration_grails_expansion())
    # Deduplicate by indices (0, 1, 2) (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item[0], item[1], item[2])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------

def _sneaker_to_catalog_item(item: tuple) -> CatalogItem:
    """Convert a sneaker tuple to a CatalogItem.

    Args:
        item: (brand, model, colorway, sneaker_type, sku, price_eur)

    Returns:
        CatalogItem with category="sneakers", item_key from slugify,
        brand=brand, set_code=model.
    """
    brand, model, colorway, sneaker_type, sku, _price_eur = item
    title = f"{brand} {model} {colorway}"
    item_key = slugify(f"{brand}-{model}-{colorway}")

    return CatalogItem(
        category=CATEGORY,
        item_key=item_key,
        title=title,
        set_code=model,
        brand=brand,
        rarity=sneaker_type,
        notes=f"{sneaker_type} | SKU: {sku}",
        attributes_json={
            "model": model,
            "colorway": colorway,
            "sneaker_type": sneaker_type,
            "sku": sku,
        },
    )


def _sneaker_to_price_observation(item: tuple) -> PriceObservation:
    """Convert a sneaker tuple to a PriceObservation.

    Args:
        item: (brand, model, colorway, sneaker_type, sku, price_eur)

    Returns:
        PriceObservation with features:
        - condition_score: 1.0 (assumes DS for catalog pricing)
        - type_score: from SNEAKER_TYPE_SCORES
        - brand_premium: from _BRAND_PREMIUM
        - collaboration_bonus: 1.0 if collab, else 0.0
        - is_ds: 1.0 (deadstock boolean — baseline is DS)
    """
    brand, _model, _colorway, sneaker_type, _sku, price_eur = item

    type_score = SNEAKER_TYPE_SCORES.get(sneaker_type, 0.50)
    premium = _brand_premium(brand)
    collab_bonus = 1.0 if _is_collab(sneaker_type) else 0.0

    return PriceObservation(
        features={
            "condition_score": 1.0,      # DS baseline for catalog prices
            "type_score": type_score,
            "brand_premium": premium,
            "collaboration_bonus": collab_bonus,
            "is_ds": 1.0,
        },
        price=float(price_eur),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import curated sneaker catalog + prices"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase upsert")
    parser.add_argument("--jsonl-only", action="store_true",
                        help="Write only training JSONL, skip catalog SQL and Supabase")
    parser.add_argument("--cache-images", action="store_true",
                        help="Cache external image URLs to S3")
    args = parser.parse_args()

    logger.info("=== Sneaker Import Pipeline ===")

    catalog = get_curated_catalog()
    logger.info(f"Curated catalog: {len(catalog)} sneakers")

    # Transform to CatalogItem / PriceObservation
    items = [_sneaker_to_catalog_item(s) for s in catalog]
    observations = [_sneaker_to_price_observation(s) for s in catalog]

    log_progress(CATEGORY, "items transformed", len(items))
    log_progress(CATEGORY, "price observations", len(observations))

    # Write training JSONL
    jsonl_path = write_training_jsonl(CATEGORY, observations)
    logger.info(f"Training JSONL written: {jsonl_path}")

    if args.jsonl_only:
        logger.info("  Mode: JSONL-ONLY (skipping catalog SQL and Supabase)")
        close_http_client()
        return

    # Write catalog SQL
    sql_path = write_catalog_sql(CATEGORY, items)
    logger.info(f"Catalog SQL written: {sql_path}")

    # Optionally cache images to S3
    if args.cache_images:
        items = cache_catalog_images(items, dry_run=args.dry_run)
        log_progress(CATEGORY, "images cached", len([i for i in items if i.image_url]))

    # Upsert to Supabase
    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    if ingest.enabled:
        inserted = ingest.upsert_catalog(items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== Sneaker Import Complete ===")
    logger.info(f"  Total catalog items:  {len(items)}")
    logger.info(f"  Price observations:   {len(observations)}")
    logger.info(f"  Price range:          EUR {min(o.price for o in observations):.0f} "
                f"- EUR {max(o.price for o in observations):.0f}")

    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")


if __name__ == "__main__":
    main()
