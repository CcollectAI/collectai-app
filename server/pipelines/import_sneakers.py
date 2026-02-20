"""
Sneaker Import Pipeline — Curated Collectible Sneakers Catalog.

Layer 1 (Catalog):  130+ curated sneakers → category_items
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


# ---------------------------------------------------------------------------
# Aggregate catalog
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[tuple]:
    """Return the full curated sneaker catalog (130+ items)."""
    catalog: list[tuple] = []
    catalog.extend(_air_jordan_1_high())
    catalog.extend(_air_jordan_retros())
    catalog.extend(_nike_dunks())
    catalog.extend(_nike_sb())
    catalog.extend(_yeezy())
    catalog.extend(_new_balance())
    catalog.extend(_nike_air_max())
    catalog.extend(_nike_collaborations())
    catalog.extend(_adidas_non_yeezy())
    catalog.extend(_other_brands())
    catalog.extend(_grails_ultra_rare())
    return catalog


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
