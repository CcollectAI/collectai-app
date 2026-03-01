"""
Curated Whiskey Import Pipeline — Collectible & Investment-Grade Bottles.

Imports a curated catalog of 80+ collectible whiskey bottles across 6 subcategories:
  - Japanese Whisky (Yamazaki, Hibiki, Nikka, Taketsuru, Chichibu, Karuizawa)
  - Scotch Single Malt (Macallan, Glenfiddich, Lagavulin, Ardbeg, Laphroaig, etc.)
  - Bourbon / American (Pappy Van Winkle, Buffalo Trace Antique, Eagle Rare, etc.)
  - Irish Whiskey (Redbreast, Midleton, Jameson, Spot Series)
  - Limited / Special Editions (Macallan editions, Yamazaki Limited, annual releases)
  - Vintage / Closed Distilleries (Port Ellen, Brora, Karuizawa single cask)

Each entry has a real distillery, region, age statement, ABV, bottling year,
realistic EUR secondary-market price, and rarity tier.

Pattern follows import_watches.py (get_curated_catalog, item_to_catalog_item,
item_to_price_observation).

Usage:
    python -m pipelines.import_whiskey [--dry-run] [--jsonl-only] [--cache-images]
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
    rarity_score as shared_rarity_score,
    logger,
    close_http_client,
)

CATEGORY = "whiskey"

# ---------------------------------------------------------------------------
# Brand-tier scoring for ML features
# ---------------------------------------------------------------------------
BRAND_TIER: dict[str, float] = {
    # Grail-tier distilleries (1.0)
    "Karuizawa": 1.0,
    "Port Ellen": 1.0,
    "Brora": 1.0,
    # Premium / Japanese (0.9)
    "Yamazaki": 0.9,
    "Hibiki": 0.9,
    "Hakushu": 0.9,
    "Chichibu": 0.9,
    "Macallan": 0.9,
    "Pappy Van Winkle": 0.9,
    "Old Rip Van Winkle": 0.9,
    "Midleton": 0.9,
    # High-end (0.8)
    "Nikka": 0.8,
    "Taketsuru": 0.8,
    "Glenfiddich": 0.8,
    "Lagavulin": 0.8,
    "Ardbeg": 0.8,
    "Highland Park": 0.8,
    "Laphroaig": 0.8,
    "Balvenie": 0.8,
    "Springbank": 0.8,
    "Redbreast": 0.8,
    "Buffalo Trace": 0.8,
    "Eagle Rare": 0.8,
    "W.L. Weller": 0.8,
    # Mid-range (0.7)
    "Blanton's": 0.7,
    "Four Roses": 0.7,
    "Bruichladdich": 0.7,
    "Port Charlotte": 0.7,
    "Jameson": 0.7,
    "Green Spot": 0.7,
    "Yellow Spot": 0.7,
    "Red Spot": 0.7,
    "Woodford Reserve": 0.7,
    "Maker's Mark": 0.7,
    "Wild Turkey": 0.7,
    "GlenDronach": 0.7,
    "Clynelish": 0.7,
}


def _brand_tier(distillery: str) -> float:
    """Map distillery to a 0-1 brand tier score."""
    return BRAND_TIER.get(distillery, 0.7)


# ---------------------------------------------------------------------------
# Curated catalog — 80+ collectible whiskey bottles
# Each dict: name, distillery, region, age_statement, abv, bottling_year,
#            price_eur, is_limited, rarity, notes
# ---------------------------------------------------------------------------


def _japanese_whisky() -> list[dict]:
    """16 Japanese whisky bottles — Yamazaki, Hibiki, Nikka, Chichibu, Karuizawa."""
    return [
        {"name": "Yamazaki 12 Year Old", "distillery": "Yamazaki",
         "region": "Japan", "age_statement": 12, "abv": 43.0,
         "bottling_year": 2024, "price_eur": 150,
         "is_limited": False, "rarity": "Premium",
         "notes": "Single malt, Suntory flagship, sherry & Mizunara oak"},
        {"name": "Yamazaki 18 Year Old", "distillery": "Yamazaki",
         "region": "Japan", "age_statement": 18, "abv": 43.0,
         "bottling_year": 2024, "price_eur": 550,
         "is_limited": False, "rarity": "Rare",
         "notes": "Single malt, deep sherry influence, highly allocated"},
        {"name": "Yamazaki 25 Year Old", "distillery": "Yamazaki",
         "region": "Japan", "age_statement": 25, "abv": 43.0,
         "bottling_year": 2023, "price_eur": 5500,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Single malt, extremely limited annual release"},
        {"name": "Hibiki 17 Year Old", "distillery": "Hibiki",
         "region": "Japan", "age_statement": 17, "abv": 43.0,
         "bottling_year": 2018, "price_eur": 650,
         "is_limited": True, "rarity": "Rare",
         "notes": "Blended, discontinued age statement, highly sought"},
        {"name": "Hibiki 21 Year Old", "distillery": "Hibiki",
         "region": "Japan", "age_statement": 21, "abv": 43.0,
         "bottling_year": 2023, "price_eur": 1200,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Blended, ultra-premium Suntory, limited allocation"},
        {"name": "Hibiki 30 Year Old", "distillery": "Hibiki",
         "region": "Japan", "age_statement": 30, "abv": 43.0,
         "bottling_year": 2022, "price_eur": 4500,
         "is_limited": True, "rarity": "Grail",
         "notes": "Blended, extremely rare, Baccarat crystal decanter editions"},
        {"name": "Nikka From The Barrel", "distillery": "Nikka",
         "region": "Japan", "age_statement": 0, "abv": 51.4,
         "bottling_year": 2024, "price_eur": 45,
         "is_limited": False, "rarity": "Standard",
         "notes": "Blended, cask strength, iconic square bottle"},
        {"name": "Nikka Coffey Grain", "distillery": "Nikka",
         "region": "Japan", "age_statement": 0, "abv": 45.0,
         "bottling_year": 2024, "price_eur": 55,
         "is_limited": False, "rarity": "Standard",
         "notes": "Single grain, Coffey still, sweet and creamy"},
        {"name": "Taketsuru Pure Malt", "distillery": "Taketsuru",
         "region": "Japan", "age_statement": 0, "abv": 43.0,
         "bottling_year": 2024, "price_eur": 60,
         "is_limited": False, "rarity": "Standard",
         "notes": "Pure malt, Yoichi + Miyagikyo blend, no age statement"},
        {"name": "Taketsuru 17 Year Old", "distillery": "Taketsuru",
         "region": "Japan", "age_statement": 17, "abv": 43.0,
         "bottling_year": 2018, "price_eur": 450,
         "is_limited": True, "rarity": "Rare",
         "notes": "Pure malt, discontinued, award-winning"},
        {"name": "Chichibu The Peated 2022", "distillery": "Chichibu",
         "region": "Japan", "age_statement": 0, "abv": 53.5,
         "bottling_year": 2022, "price_eur": 350,
         "is_limited": True, "rarity": "Rare",
         "notes": "Single malt, peated, micro-distillery, limited annual"},
        {"name": "Chichibu Ichiro's Malt & Grain", "distillery": "Chichibu",
         "region": "Japan", "age_statement": 0, "abv": 46.5,
         "bottling_year": 2024, "price_eur": 120,
         "is_limited": False, "rarity": "Premium",
         "notes": "Blended, world whiskies blend, widely available"},
        {"name": "Chichibu On The Way 2023", "distillery": "Chichibu",
         "region": "Japan", "age_statement": 0, "abv": 51.5,
         "bottling_year": 2023, "price_eur": 500,
         "is_limited": True, "rarity": "Rare",
         "notes": "Single malt, annual limited edition, cult following"},
        {"name": "Karuizawa 1983 Single Cask #7576", "distillery": "Karuizawa",
         "region": "Japan", "age_statement": 30, "abv": 58.6,
         "bottling_year": 2013, "price_eur": 25000,
         "is_limited": True, "rarity": "Grail",
         "notes": "Single cask, closed distillery, legendary status"},
        {"name": "Hakushu 12 Year Old", "distillery": "Hakushu",
         "region": "Japan", "age_statement": 12, "abv": 43.0,
         "bottling_year": 2024, "price_eur": 120,
         "is_limited": False, "rarity": "Premium",
         "notes": "Single malt, forest distillery, herbal & fresh"},
        {"name": "Hakushu 18 Year Old", "distillery": "Hakushu",
         "region": "Japan", "age_statement": 18, "abv": 43.0,
         "bottling_year": 2024, "price_eur": 500,
         "is_limited": False, "rarity": "Rare",
         "notes": "Single malt, smoky complexity, highly allocated"},
    ]


def _scotch_single_malt() -> list[dict]:
    """22 Scotch single malt whiskies — iconic distilleries across Scotland."""
    return [
        {"name": "Macallan 18 Sherry Oak", "distillery": "Macallan",
         "region": "Speyside", "age_statement": 18, "abv": 43.0,
         "bottling_year": 2024, "price_eur": 350,
         "is_limited": False, "rarity": "Premium",
         "notes": "Single malt, sherry cask, benchmark luxury Scotch"},
        {"name": "Macallan 25 Sherry Oak", "distillery": "Macallan",
         "region": "Speyside", "age_statement": 25, "abv": 43.0,
         "bottling_year": 2023, "price_eur": 2200,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Single malt, deeply sherried, very limited allocation"},
        {"name": "Macallan 30 Sherry Oak", "distillery": "Macallan",
         "region": "Speyside", "age_statement": 30, "abv": 43.0,
         "bottling_year": 2022, "price_eur": 6500,
         "is_limited": True, "rarity": "Grail",
         "notes": "Single malt, collectors benchmark, Lalique decanter"},
        {"name": "Macallan Rare Cask", "distillery": "Macallan",
         "region": "Speyside", "age_statement": 0, "abv": 43.0,
         "bottling_year": 2024, "price_eur": 380,
         "is_limited": False, "rarity": "Premium",
         "notes": "Single malt, NAS, less than 1% of casks selected"},
        {"name": "Glenfiddich 18 Year Old", "distillery": "Glenfiddich",
         "region": "Speyside", "age_statement": 18, "abv": 40.0,
         "bottling_year": 2024, "price_eur": 80,
         "is_limited": False, "rarity": "Standard",
         "notes": "Single malt, Oloroso sherry cask finish"},
        {"name": "Glenfiddich 21 Reserva Rum Cask", "distillery": "Glenfiddich",
         "region": "Speyside", "age_statement": 21, "abv": 40.0,
         "bottling_year": 2024, "price_eur": 180,
         "is_limited": False, "rarity": "Premium",
         "notes": "Single malt, Caribbean rum cask finish, exotic spice"},
        {"name": "Glenfiddich 30 Year Old", "distillery": "Glenfiddich",
         "region": "Speyside", "age_statement": 30, "abv": 43.0,
         "bottling_year": 2023, "price_eur": 800,
         "is_limited": True, "rarity": "Rare",
         "notes": "Single malt, Oloroso & bourbon cask, rare old"},
        {"name": "Lagavulin 16 Year Old", "distillery": "Lagavulin",
         "region": "Islay", "age_statement": 16, "abv": 43.0,
         "bottling_year": 2024, "price_eur": 75,
         "is_limited": False, "rarity": "Standard",
         "notes": "Single malt, iconic Islay peat, rich and smoky"},
        {"name": "Lagavulin 12 Year Old Cask Strength", "distillery": "Lagavulin",
         "region": "Islay", "age_statement": 12, "abv": 57.3,
         "bottling_year": 2024, "price_eur": 130,
         "is_limited": True, "rarity": "Premium",
         "notes": "Single malt, annual Special Release, cask strength"},
        {"name": "Ardbeg Uigeadail", "distillery": "Ardbeg",
         "region": "Islay", "age_statement": 0, "abv": 54.2,
         "bottling_year": 2024, "price_eur": 75,
         "is_limited": False, "rarity": "Standard",
         "notes": "Single malt, NAS, peated + sherry cask, cask strength"},
        {"name": "Ardbeg Corryvreckan", "distillery": "Ardbeg",
         "region": "Islay", "age_statement": 0, "abv": 57.1,
         "bottling_year": 2024, "price_eur": 85,
         "is_limited": False, "rarity": "Standard",
         "notes": "Single malt, NAS, deep peat with French oak"},
        {"name": "Ardbeg 25 Year Old", "distillery": "Ardbeg",
         "region": "Islay", "age_statement": 25, "abv": 46.0,
         "bottling_year": 2023, "price_eur": 900,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Single malt, very old Islay peat, limited annual"},
        {"name": "Laphroaig 10 Year Old", "distillery": "Laphroaig",
         "region": "Islay", "age_statement": 10, "abv": 40.0,
         "bottling_year": 2024, "price_eur": 40,
         "is_limited": False, "rarity": "Standard",
         "notes": "Single malt, medicinal peat, love-or-hate classic"},
        {"name": "Laphroaig 25 Year Old Cask Strength", "distillery": "Laphroaig",
         "region": "Islay", "age_statement": 25, "abv": 51.4,
         "bottling_year": 2023, "price_eur": 750,
         "is_limited": True, "rarity": "Rare",
         "notes": "Single malt, cask strength, extremely limited"},
        {"name": "Highland Park 18 Viking Pride", "distillery": "Highland Park",
         "region": "Islands", "age_statement": 18, "abv": 43.0,
         "bottling_year": 2024, "price_eur": 130,
         "is_limited": False, "rarity": "Premium",
         "notes": "Single malt, heather honey peat, Orkney"},
        {"name": "Highland Park 25 Year Old", "distillery": "Highland Park",
         "region": "Islands", "age_statement": 25, "abv": 46.0,
         "bottling_year": 2023, "price_eur": 600,
         "is_limited": True, "rarity": "Rare",
         "notes": "Single malt, sherry cask, complex and rare"},
        {"name": "Port Charlotte 10 Heavily Peated", "distillery": "Port Charlotte",
         "region": "Islay", "age_statement": 10, "abv": 50.0,
         "bottling_year": 2024, "price_eur": 60,
         "is_limited": False, "rarity": "Standard",
         "notes": "Single malt, Bruichladdich distillery, heavily peated"},
        {"name": "Balvenie 14 Caribbean Cask", "distillery": "Balvenie",
         "region": "Speyside", "age_statement": 14, "abv": 43.0,
         "bottling_year": 2024, "price_eur": 80,
         "is_limited": False, "rarity": "Standard",
         "notes": "Single malt, rum cask finish, tropical sweetness"},
        {"name": "Balvenie 21 PortWood", "distillery": "Balvenie",
         "region": "Speyside", "age_statement": 21, "abv": 40.0,
         "bottling_year": 2024, "price_eur": 280,
         "is_limited": False, "rarity": "Premium",
         "notes": "Single malt, port pipe finish, rich and fruity"},
        {"name": "Springbank 15 Year Old", "distillery": "Springbank",
         "region": "Campbeltown", "age_statement": 15, "abv": 46.0,
         "bottling_year": 2024, "price_eur": 150,
         "is_limited": True, "rarity": "Rare",
         "notes": "Single malt, 100% sherry cask, cult Campbeltown"},
        {"name": "Springbank 21 Year Old", "distillery": "Springbank",
         "region": "Campbeltown", "age_statement": 21, "abv": 46.0,
         "bottling_year": 2023, "price_eur": 550,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Single malt, rum cask, extremely limited annual"},
        {"name": "GlenDronach 18 Allardice", "distillery": "GlenDronach",
         "region": "Highland", "age_statement": 18, "abv": 46.0,
         "bottling_year": 2024, "price_eur": 120,
         "is_limited": False, "rarity": "Premium",
         "notes": "Single malt, Oloroso sherry cask, rich and sherried"},
    ]


def _bourbon_american() -> list[dict]:
    """16 bourbon and American whiskey bottles."""
    return [
        {"name": "Pappy Van Winkle 15 Year Old", "distillery": "Pappy Van Winkle",
         "region": "Kentucky", "age_statement": 15, "abv": 53.5,
         "bottling_year": 2024, "price_eur": 1800,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Bourbon, Old Rip Van Winkle distillery, unicorn status"},
        {"name": "Pappy Van Winkle 20 Year Old", "distillery": "Pappy Van Winkle",
         "region": "Kentucky", "age_statement": 20, "abv": 45.2,
         "bottling_year": 2024, "price_eur": 3500,
         "is_limited": True, "rarity": "Grail",
         "notes": "Bourbon, extreme rarity, lottery-only allocation"},
        {"name": "Pappy Van Winkle 23 Year Old", "distillery": "Pappy Van Winkle",
         "region": "Kentucky", "age_statement": 23, "abv": 47.8,
         "bottling_year": 2024, "price_eur": 6000,
         "is_limited": True, "rarity": "Grail",
         "notes": "Bourbon, holy grail of bourbon, sub-1000 bottles/year"},
        {"name": "Old Rip Van Winkle 10 Year Old", "distillery": "Old Rip Van Winkle",
         "region": "Kentucky", "age_statement": 10, "abv": 53.5,
         "bottling_year": 2024, "price_eur": 800,
         "is_limited": True, "rarity": "Rare",
         "notes": "Bourbon, entry-level Van Winkle, still extremely allocated"},
        {"name": "Buffalo Trace Antique Collection Eagle Rare 17",
         "distillery": "Eagle Rare", "region": "Kentucky",
         "age_statement": 17, "abv": 50.5, "bottling_year": 2024,
         "price_eur": 900,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Bourbon, BTAC annual release, 17-year single barrel"},
        {"name": "Buffalo Trace Antique Collection George T. Stagg",
         "distillery": "Buffalo Trace", "region": "Kentucky",
         "age_statement": 15, "abv": 65.0, "bottling_year": 2024,
         "price_eur": 1200,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Bourbon, BTAC, barrel proof, legendary power"},
        {"name": "Buffalo Trace Antique Collection William Larue Weller",
         "distillery": "W.L. Weller", "region": "Kentucky",
         "age_statement": 12, "abv": 62.0, "bottling_year": 2024,
         "price_eur": 1100,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Wheated bourbon, BTAC, barrel proof, incredibly scarce"},
        {"name": "Blanton's Gold", "distillery": "Blanton's",
         "region": "Kentucky", "age_statement": 0, "abv": 51.5,
         "bottling_year": 2024, "price_eur": 120,
         "is_limited": True, "rarity": "Premium",
         "notes": "Bourbon, single barrel, iconic horseshoe stopper"},
        {"name": "Blanton's Straight From The Barrel", "distillery": "Blanton's",
         "region": "Kentucky", "age_statement": 0, "abv": 65.0,
         "bottling_year": 2024, "price_eur": 200,
         "is_limited": True, "rarity": "Rare",
         "notes": "Bourbon, single barrel, uncut & unfiltered, export only"},
        {"name": "W.L. Weller 12 Year Old", "distillery": "W.L. Weller",
         "region": "Kentucky", "age_statement": 12, "abv": 45.0,
         "bottling_year": 2024, "price_eur": 80,
         "is_limited": True, "rarity": "Premium",
         "notes": "Wheated bourbon, poor man's Pappy, heavily allocated"},
        {"name": "W.L. Weller Full Proof", "distillery": "W.L. Weller",
         "region": "Kentucky", "age_statement": 0, "abv": 57.0,
         "bottling_year": 2024, "price_eur": 150,
         "is_limited": True, "rarity": "Rare",
         "notes": "Wheated bourbon, barrel proof, limited release"},
        {"name": "Four Roses Limited Edition Small Batch 2024",
         "distillery": "Four Roses", "region": "Kentucky",
         "age_statement": 0, "abv": 55.7, "bottling_year": 2024,
         "price_eur": 250,
         "is_limited": True, "rarity": "Rare",
         "notes": "Bourbon, annual limited edition, multi-recipe blend"},
        {"name": "Four Roses Single Barrel", "distillery": "Four Roses",
         "region": "Kentucky", "age_statement": 0, "abv": 50.0,
         "bottling_year": 2024, "price_eur": 45,
         "is_limited": False, "rarity": "Standard",
         "notes": "Bourbon, OBSV recipe, approachable single barrel"},
        {"name": "Woodford Reserve Batch Proof 2024", "distillery": "Woodford Reserve",
         "region": "Kentucky", "age_statement": 0, "abv": 60.3,
         "bottling_year": 2024, "price_eur": 180,
         "is_limited": True, "rarity": "Rare",
         "notes": "Bourbon, annual release, uncut at barrel proof"},
        {"name": "Wild Turkey Master's Keep Voyage", "distillery": "Wild Turkey",
         "region": "Kentucky", "age_statement": 10, "abv": 53.5,
         "bottling_year": 2023, "price_eur": 200,
         "is_limited": True, "rarity": "Rare",
         "notes": "Bourbon, jamaican rum cask finish, Master's Keep series"},
        {"name": "Maker's Mark Wood Finishing Series 2024",
         "distillery": "Maker's Mark", "region": "Kentucky",
         "age_statement": 0, "abv": 54.5, "bottling_year": 2024,
         "price_eur": 70,
         "is_limited": True, "rarity": "Premium",
         "notes": "Wheated bourbon, limited stave-profile release"},
    ]


def _irish_whiskey() -> list[dict]:
    """9 Irish whiskey bottles — Redbreast, Midleton, Jameson, Spot Series."""
    return [
        {"name": "Redbreast 21 Year Old", "distillery": "Redbreast",
         "region": "Ireland", "age_statement": 21, "abv": 46.0,
         "bottling_year": 2024, "price_eur": 260,
         "is_limited": False, "rarity": "Premium",
         "notes": "Single pot still, sherry cask, benchmark Irish whiskey"},
        {"name": "Redbreast 27 Year Old", "distillery": "Redbreast",
         "region": "Ireland", "age_statement": 27, "abv": 53.4,
         "bottling_year": 2023, "price_eur": 550,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Single pot still, ruby port & bourbon cask, very rare"},
        {"name": "Midleton Very Rare 2024", "distillery": "Midleton",
         "region": "Ireland", "age_statement": 0, "abv": 40.0,
         "bottling_year": 2024, "price_eur": 200,
         "is_limited": True, "rarity": "Rare",
         "notes": "Blended, annual release, master distiller selection"},
        {"name": "Midleton Very Rare Dair Ghaelach Knockrath Forest",
         "distillery": "Midleton", "region": "Ireland",
         "age_statement": 0, "abv": 56.6, "bottling_year": 2023,
         "price_eur": 350,
         "is_limited": True, "rarity": "Rare",
         "notes": "Single pot still, virgin Irish oak finish, limited"},
        {"name": "Jameson 18 Year Old", "distillery": "Jameson",
         "region": "Ireland", "age_statement": 18, "abv": 40.0,
         "bottling_year": 2024, "price_eur": 85,
         "is_limited": False, "rarity": "Standard",
         "notes": "Blended, first-fill bourbon & sherry cask"},
        {"name": "Green Spot Chateau Montelena", "distillery": "Green Spot",
         "region": "Ireland", "age_statement": 0, "abv": 46.0,
         "bottling_year": 2024, "price_eur": 80,
         "is_limited": True, "rarity": "Premium",
         "notes": "Single pot still, Zinfandel wine cask finish"},
        {"name": "Yellow Spot 12 Year Old", "distillery": "Yellow Spot",
         "region": "Ireland", "age_statement": 12, "abv": 46.0,
         "bottling_year": 2024, "price_eur": 95,
         "is_limited": False, "rarity": "Premium",
         "notes": "Single pot still, malaga/sherry/bourbon triple cask"},
        {"name": "Red Spot 15 Year Old", "distillery": "Red Spot",
         "region": "Ireland", "age_statement": 15, "abv": 46.0,
         "bottling_year": 2023, "price_eur": 200,
         "is_limited": True, "rarity": "Rare",
         "notes": "Single pot still, marsala cask, top of Spot range"},
        {"name": "Redbreast 12 Cask Strength", "distillery": "Redbreast",
         "region": "Ireland", "age_statement": 12, "abv": 58.6,
         "bottling_year": 2024, "price_eur": 80,
         "is_limited": True, "rarity": "Premium",
         "notes": "Single pot still, batch-variable cask strength"},
    ]


def _limited_special_editions() -> list[dict]:
    """13 limited and special edition bottles — annual releases and collector items."""
    return [
        {"name": "Macallan Edition No. 1", "distillery": "Macallan",
         "region": "Speyside", "age_statement": 0, "abv": 48.0,
         "bottling_year": 2015, "price_eur": 1200,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "First in Edition series, 8 sherry cask types, discontinued"},
        {"name": "Macallan Edition No. 6", "distillery": "Macallan",
         "region": "Speyside", "age_statement": 0, "abv": 48.6,
         "bottling_year": 2021, "price_eur": 400,
         "is_limited": True, "rarity": "Rare",
         "notes": "Final Edition series, natural color collaboration"},
        {"name": "Macallan Harmony Collection Rich Cacao",
         "distillery": "Macallan", "region": "Speyside",
         "age_statement": 0, "abv": 44.0, "bottling_year": 2023,
         "price_eur": 350,
         "is_limited": True, "rarity": "Rare",
         "notes": "Chocolate-inspired Harmony series, sherry-seasoned"},
        {"name": "Yamazaki Limited Edition 2023", "distillery": "Yamazaki",
         "region": "Japan", "age_statement": 0, "abv": 43.0,
         "bottling_year": 2023, "price_eur": 800,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Annual Japan-only limited release, NAS, highly allocated"},
        {"name": "Yamazaki Tsukuriwake Selection Peated Malt 2023",
         "distillery": "Yamazaki", "region": "Japan",
         "age_statement": 0, "abv": 48.0, "bottling_year": 2023,
         "price_eur": 450,
         "is_limited": True, "rarity": "Rare",
         "notes": "Exploration series, peated, Japan travel retail"},
        {"name": "Ardbeg Supernova 2019", "distillery": "Ardbeg",
         "region": "Islay", "age_statement": 0, "abv": 53.8,
         "bottling_year": 2019, "price_eur": 350,
         "is_limited": True, "rarity": "Rare",
         "notes": "Committee Release, super-heavily peated, cult favourite"},
        {"name": "Lagavulin 26 Year Old Special Release 2021",
         "distillery": "Lagavulin", "region": "Islay",
         "age_statement": 26, "abv": 44.2, "bottling_year": 2021,
         "price_eur": 1000,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Diageo Special Release, very old Islay peat, travel retail"},
        {"name": "Highland Park 50 Year Old", "distillery": "Highland Park",
         "region": "Islands", "age_statement": 50, "abv": 44.8,
         "bottling_year": 2021, "price_eur": 30000,
         "is_limited": True, "rarity": "Grail",
         "notes": "274 bottles worldwide, refill sherry hogshead, half-century"},
        {"name": "Balvenie 30 Year Old Rare Marriages", "distillery": "Balvenie",
         "region": "Speyside", "age_statement": 30, "abv": 44.2,
         "bottling_year": 2023, "price_eur": 1200,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "David Stewart final selection, traditional oak & sherry"},
        {"name": "Clynelish 1993 Special Release 2022", "distillery": "Clynelish",
         "region": "Highland", "age_statement": 28, "abv": 58.7,
         "bottling_year": 2022, "price_eur": 600,
         "is_limited": True, "rarity": "Rare",
         "notes": "Diageo Special Release, 28yo, wax-coated Highland"},
        {"name": "Springbank 25 Year Old 2023", "distillery": "Springbank",
         "region": "Campbeltown", "age_statement": 25, "abv": 46.0,
         "bottling_year": 2023, "price_eur": 1500,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Ultra-limited Campbeltown, 800 bottles, sherry cask"},
        {"name": "Laphroaig 32 Year Old", "distillery": "Laphroaig",
         "region": "Islay", "age_statement": 32, "abv": 46.6,
         "bottling_year": 2022, "price_eur": 1800,
         "is_limited": True, "rarity": "Grail",
         "notes": "Oldest regular Laphroaig, Oloroso sherry, 4000 bottles"},
        {"name": "Nikka Yoichi Single Malt 2024 Limited", "distillery": "Nikka",
         "region": "Japan", "age_statement": 0, "abv": 47.0,
         "bottling_year": 2024, "price_eur": 200,
         "is_limited": True, "rarity": "Rare",
         "notes": "Single malt, peated, Hokkaido distillery, Japan-only"},
    ]


def _vintage_closed_distilleries() -> list[dict]:
    """11 bottles from vintage stocks and closed distilleries."""
    return [
        {"name": "Port Ellen 40 Year Old 1979", "distillery": "Port Ellen",
         "region": "Islay", "age_statement": 40, "abv": 50.9,
         "bottling_year": 2020, "price_eur": 8000,
         "is_limited": True, "rarity": "Grail",
         "notes": "Closed 1983, 9th Release, legendary Islay ghost distillery"},
        {"name": "Port Ellen 32 Year Old 11th Release", "distillery": "Port Ellen",
         "region": "Islay", "age_statement": 32, "abv": 53.3,
         "bottling_year": 2011, "price_eur": 4500,
         "is_limited": True, "rarity": "Grail",
         "notes": "Closed distillery, Diageo annual Special Release"},
        {"name": "Brora 40 Year Old 1978", "distillery": "Brora",
         "region": "Highland", "age_statement": 40, "abv": 49.2,
         "bottling_year": 2019, "price_eur": 7000,
         "is_limited": True, "rarity": "Grail",
         "notes": "Closed 1983, reopened 2021, extremely rare old stock"},
        {"name": "Brora 35 Year Old 14th Release", "distillery": "Brora",
         "region": "Highland", "age_statement": 35, "abv": 49.9,
         "bottling_year": 2015, "price_eur": 3500,
         "is_limited": True, "rarity": "Grail",
         "notes": "Highland ghost distillery, annual Special Release"},
        {"name": "Karuizawa 1981 Noh Series Single Cask", "distillery": "Karuizawa",
         "region": "Japan", "age_statement": 35, "abv": 56.2,
         "bottling_year": 2016, "price_eur": 35000,
         "is_limited": True, "rarity": "Grail",
         "notes": "Closed 2000, Noh mask label, single sherry cask, 400 bottles"},
        {"name": "Karuizawa 1984 Single Cask #3032", "distillery": "Karuizawa",
         "region": "Japan", "age_statement": 28, "abv": 57.8,
         "bottling_year": 2012, "price_eur": 18000,
         "is_limited": True, "rarity": "Grail",
         "notes": "Closed distillery, single sherry butt, samurai label"},
        {"name": "Karuizawa 1972 Geisha Single Cask", "distillery": "Karuizawa",
         "region": "Japan", "age_statement": 40, "abv": 61.0,
         "bottling_year": 2012, "price_eur": 50000,
         "is_limited": True, "rarity": "Grail",
         "notes": "Iconic geisha label, record auction prices, ~40 bottles"},
        {"name": "Rosebank 30 Year Old 2020 Release", "distillery": "Rosebank",
         "region": "Lowland", "age_statement": 30, "abv": 48.6,
         "bottling_year": 2020, "price_eur": 3000,
         "is_limited": True, "rarity": "Grail",
         "notes": "Closed 1993, triple-distilled Lowland, reopening planned"},
        {"name": "Convalmore 36 Year Old 1977", "distillery": "Convalmore",
         "region": "Speyside", "age_statement": 36, "abv": 58.0,
         "bottling_year": 2013, "price_eur": 2500,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Closed 1985, Diageo Special Release, extremely rare Speyside"},
        {"name": "St Magdalene 1982 Signatory Vintage", "distillery": "St Magdalene",
         "region": "Lowland", "age_statement": 30, "abv": 51.5,
         "bottling_year": 2013, "price_eur": 1500,
         "is_limited": True, "rarity": "Ultra Rare",
         "notes": "Closed 1983, independent bottling, vanishingly rare Lowland"},
        {"name": "Imperial 1995 Gordon & MacPhail 25yo",
         "distillery": "Imperial", "region": "Speyside",
         "age_statement": 25, "abv": 43.0, "bottling_year": 2020,
         "price_eur": 300,
         "is_limited": True, "rarity": "Rare",
         "notes": "Closed 1998 / demolished, independent bottling, ghost Speyside"},
    ]


# ---------------------------------------------------------------------------
# Assemble full catalog
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[dict]:
    """Return the full curated whiskey catalog as a list of dicts.

    Each dict has keys: name, distillery, region, age_statement, abv,
    bottling_year, price_eur, is_limited, rarity, notes.
    """
    catalog: list[dict] = []
    catalog.extend(_japanese_whisky())
    catalog.extend(_scotch_single_malt())
    catalog.extend(_bourbon_american())
    catalog.extend(_irish_whiskey())
    catalog.extend(_limited_special_editions())
    catalog.extend(_vintage_closed_distilleries())
    return catalog


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------

def item_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a whiskey dict to a CatalogItem.

    Sets category='whiskey', item_key from slugify(distillery-name),
    brand from the distillery name.
    """
    name = item["name"]
    distillery = item["distillery"]
    region = item["region"]
    age_statement = item["age_statement"]
    abv = item["abv"]
    is_limited = item["is_limited"]
    rarity = item["rarity"]
    notes = item["notes"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{distillery}-{name}"),
        title=f"{name}",
        set_code=region,
        brand=distillery,
        rarity=rarity,
        notes=notes,
        attributes_json={
            "distillery": distillery,
            "region": region,
            "age_statement": age_statement,
            "abv": abv,
            "is_limited": is_limited,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    """Convert a whiskey dict to a PriceObservation.

    Features:
    - condition_score: 0.95 (bottles are mostly sealed/unopened)
    - rarity_score: from shared_rarity_score() using the rarity tier string
    - brand_tier: 0.9 for premium/Japanese, 0.7 for standard, 1.0 for grail
    - age_score: min(1.0, age_statement / 30) if age_statement > 0, else 0.3
    - is_limited: 1.0 or 0.0
    """
    distillery = item["distillery"]
    age_statement = item["age_statement"]
    rarity = item["rarity"]
    is_limited = item["is_limited"]
    price = item["price_eur"]

    # Age score: normalized 0-1, capped at 30 years
    if age_statement and age_statement > 0:
        age_sc = min(1.0, age_statement / 30)
    else:
        age_sc = 0.3  # NAS (no age statement) bottles get a baseline

    return PriceObservation(
        features={
            "condition_score": 0.95,
            "rarity_score": shared_rarity_score(rarity),
            "brand_tier": _brand_tier(distillery),
            "age_score": round(age_sc, 4),
            "is_limited": 1.0 if is_limited else 0.0,
        },
        price=float(price),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import curated whiskey catalog + prices"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase upsert")
    parser.add_argument("--jsonl-only", action="store_true",
                        help="Write only training JSONL, skip catalog SQL and Supabase")
    parser.add_argument("--cache-images", action="store_true",
                        help="Cache external image URLs to S3")
    args = parser.parse_args()

    logger.info("=== Whiskey Import Pipeline ===")

    catalog = get_curated_catalog()
    logger.info(f"Curated catalog: {len(catalog)} bottles")

    # Transform to CatalogItem / PriceObservation
    items = [item_to_catalog_item(w) for w in catalog]
    observations = [item_to_price_observation(w) for w in catalog]

    log_progress(CATEGORY, "items transformed", len(items))
    log_progress(CATEGORY, "price observations", len(observations))

    # Write training JSONL (always)
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

    logger.info(f"\n=== Whiskey Import Complete ===")
    logger.info(f"  Total catalog items:  {len(items)}")
    logger.info(f"  Price observations:   {len(observations)}")
    logger.info(f"  Price range:          EUR {min(o.price for o in observations):.0f} "
                f"- EUR {max(o.price for o in observations):.0f}")

    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")


if __name__ == "__main__":
    main()
