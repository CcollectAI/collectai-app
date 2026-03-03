"""
Import LEGO set data from Rebrickable API.

Layer 1 (Catalog):  All sets -> category_items
Layer 2 (Prices):   Retail prices + estimated market values -> train.jsonl

API: https://rebrickable.com/api/v3/docs/
Rate limit: 1 request/second, API key required (free registration)
Get key at: https://rebrickable.com/users/merle/settings/#api

Usage:
    python -m pipelines.import_lego [--limit 5000] [--dry-run]

    Set REBRICKABLE_API_KEY env var before running.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem, PriceObservation, SupabaseIngest,
    write_training_jsonl, write_catalog_sql, fetch_json,
    log_progress, slugify, to_eur,
    rarity_score as shared_rarity_score,
    RARITY_SCORE_MAP,
    logger,
    close_http_client,
)

CATEGORY = "lego"
API_BASE = "https://rebrickable.com/api/v3/lego"
API_KEY = os.getenv("REBRICKABLE_API_KEY", "")


def _api_headers() -> dict:
    return {"Authorization": f"key {API_KEY}"}


def fetch_themes() -> dict[int, str]:
    """Fetch all LEGO themes -> {theme_id: theme_name}."""
    themes = {}
    url = f"{API_BASE}/themes/"
    params = {"page_size": 1000}
    while url:
        data = fetch_json(url, params=params, headers=_api_headers())
        for t in data.get("results", []):
            themes[t["id"]] = t["name"]
        url = data.get("next")
        params = None
        time.sleep(0.5)
    log_progress(CATEGORY, "themes fetched", len(themes))
    return themes


def fetch_sets(themes: dict[int, str], limit: int | None = None) -> list[dict]:
    """Fetch all LEGO sets with theme names resolved."""
    sets = []
    url = f"{API_BASE}/sets/"
    params = {"page_size": 1000, "ordering": "-year"}
    while url:
        data = fetch_json(url, params=params, headers=_api_headers())
        for s in data.get("results", []):
            s["theme_name"] = themes.get(s.get("theme_id", 0), "Unknown")
            sets.append(s)
        log_progress(CATEGORY, "sets page", len(sets))
        url = data.get("next")
        params = None
        time.sleep(1.0)  # strict rate limit

        if limit and len(sets) >= limit:
            sets = sets[:limit]
            break

    log_progress(CATEGORY, "sets fetched", len(sets))
    return sets


def set_to_catalog_item(s: dict) -> CatalogItem:
    set_num = s.get("set_num", "")
    name = s.get("name", "")
    year = s.get("year", 0)
    num_parts = s.get("num_parts", 0)
    theme_name = s.get("theme_name", "")
    img_url = s.get("set_img_url", "")

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{set_num}-{name}"),
        title=f"LEGO {name}",
        set_code=set_num,
        brand="LEGO",
        rarity=_estimate_rarity(year, num_parts, theme_name),
        notes=f"Set {set_num} | {theme_name} | {year} | {num_parts} pcs",
        image_url=img_url,
        attributes_json={
            "set_number": set_num,
            "theme": theme_name,
            "year": str(year),
            "num_parts": num_parts,
        },
    )


def _estimate_rarity(year: int, num_parts: int, theme: str) -> str:
    """Estimate rarity/collectibility tier."""
    premium_themes = {"Star Wars", "Harry Potter", "Icons", "Creator Expert",
                      "Modular Buildings", "Ultimate Collector Series", "Ideas",
                      "Technic", "Architecture"}
    age = 2026 - year
    if age >= 15 and num_parts > 1000:
        return "Vintage Premium"
    if age >= 10:
        return "Retired"
    if any(t in theme for t in premium_themes):
        return "Premium Theme"
    if num_parts > 2000:
        return "Large Set"
    return "Standard"


def set_to_price_observation(s: dict) -> PriceObservation | None:
    """Estimate price from piece count and age (Rebrickable doesn't have prices)."""
    num_parts = s.get("num_parts", 0)
    year = s.get("year", 2020)
    theme_name = s.get("theme_name", "")

    if num_parts == 0:
        return None

    # Price estimation formula (LEGO ~$0.10-0.14 per piece, retired sets gain value)
    base_ppp = 0.11  # base price per piece in USD
    age = max(0, 2026 - year)

    # Theme premium
    premium_themes = {"Star Wars": 1.3, "Harry Potter": 1.2, "Icons": 1.4,
                      "Creator Expert": 1.3, "Ideas": 1.2, "Technic": 1.1}
    theme_mult = 1.0
    for t, mult in premium_themes.items():
        if t in theme_name:
            theme_mult = mult
            break

    # Age premium (retired sets appreciate)
    age_mult = 1.0 + (age * 0.08) if age > 2 else 1.0

    estimated_usd = num_parts * base_ppp * theme_mult * age_mult
    estimated_eur = to_eur(max(5.0, estimated_usd), "USD")

    sealed_mult = 1.3  # sealed premium
    theme_pop = min(1.0, theme_mult / 1.5)

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": min(1.0, (age * 0.05 + theme_pop * 0.3 + (1 if num_parts > 1000 else 0) * 0.2)),
            "edition_score": 0.5,
            "piece_count": num_parts,
            "year": year,
            "theme_popularity": theme_pop,
            "sealed": 0.0,  # default to used, user will override
        },
        price=estimated_eur,
    )


def main():
    parser = argparse.ArgumentParser(description="Import LEGO catalog from Rebrickable")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== LEGO Import (Rebrickable) ===")

    if not API_KEY:
        logger.info("WARNING: REBRICKABLE_API_KEY not set.")
        logger.info("Get a free key at https://rebrickable.com/users/merle/settings/#api")
        logger.info("Falling back to curated seed data...")
        _run_curated_seed(args.dry_run)
        return

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    themes = fetch_themes()
    sets = fetch_sets(themes, limit=args.limit)

    all_items = [set_to_catalog_item(s) for s in sets]
    all_observations = [obs for s in sets if (obs := set_to_price_observation(s))]

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    if all_observations:
        write_training_jsonl(CATEGORY, all_observations)
        log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()

    logger.info(f"\n=== LEGO Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


def _curated_rarity(year: int, parts: int, theme: str) -> tuple[str, float]:
    """Calculate rarity label and score based on age, theme, and piece count.

    Returns:
        (rarity_label, rarity_score) tuple.

    Rules (evaluated in priority order):
        1. Sets > 15 years old with 1000+ pieces  -> "Vintage Premium"  (0.9)
        2. Premium themes (UCS Star Wars, Modular) -> "Premium Theme"   (0.8)
        3. Sets > 10 years old                     -> "Retired"         (0.7)
        4. Large sets (2000+ pieces)               -> "Large Set"       (0.6)
        5. Everything else                         -> "Standard"        (0.4)
    """
    premium_themes = {
        "Star Wars", "UCS", "Ultimate Collector Series",
        "Modular Buildings", "Harry Potter", "Creator Expert",
        "Icons", "Ideas",
    }
    age = 2026 - year

    if age >= 15 and parts >= 1000:
        return "Vintage Premium", 0.9
    # Check premium theme before age-based retired so a 2016 UCS set gets 0.8
    if any(t.lower() in theme.lower() for t in premium_themes):
        return "Premium Theme", 0.8
    if age >= 10:
        return "Retired", 0.7
    if parts >= 2000:
        return "Large Set", 0.6
    return "Standard", 0.4


# ---------------------------------------------------------------------------
# Curated seed data  (500+ real LEGO sets)
# ---------------------------------------------------------------------------
# Format: (set_num, name, theme, year, parts, price_eur)
# Prices are approximate secondary-market EUR values (2026).
# ---------------------------------------------------------------------------

def _seed_sets() -> list[tuple]:
    """Return the full curated list of 500+ LEGO sets."""
    return [
        # ── UCS Star Wars (16 sets) ──────────────────────────────────────
        ("10179-1", "Millennium Falcon UCS", "Star Wars", 2007, 5195, 3500.0),
        ("10188-1", "Death Star", "Star Wars", 2008, 3803, 800.0),
        ("75192-1", "Millennium Falcon", "Star Wars", 2017, 7541, 850.0),
        ("75252-1", "Imperial Star Destroyer UCS", "Star Wars", 2019, 4784, 900.0),
        ("75060-1", "Slave I UCS", "Star Wars", 2015, 1996, 550.0),
        ("10143-1", "Death Star II UCS", "Star Wars", 2005, 3449, 1400.0),
        ("10221-1", "Super Star Destroyer UCS", "Star Wars", 2011, 3152, 1500.0),
        ("75159-1", "Death Star (2016)", "Star Wars", 2016, 4016, 700.0),
        ("75275-1", "A-wing Starfighter UCS", "Star Wars", 2020, 1673, 350.0),
        ("75313-1", "AT-AT UCS", "Star Wars", 2021, 6785, 750.0),
        ("10240-1", "Red Five X-wing Starfighter UCS", "Star Wars", 2013, 1559, 500.0),
        ("75309-1", "Republic Gunship UCS", "Star Wars", 2021, 3292, 400.0),
        ("10026-1", "Naboo Starfighter UCS", "Star Wars", 2002, 187, 350.0),
        ("7194-1", "Yoda UCS", "Star Wars", 2002, 1075, 600.0),
        ("10030-1", "Imperial Star Destroyer UCS (OG)", "Star Wars", 2002, 3104, 1800.0),
        ("75290-1", "Mos Eisley Cantina", "Star Wars", 2020, 3187, 400.0),

        # ── Modular Buildings (16 sets) ──────────────────────────────────
        ("10190-1", "Market Street", "Modular Buildings", 2007, 1248, 900.0),
        ("10182-1", "Cafe Corner", "Modular Buildings", 2007, 2056, 2500.0),
        ("10185-1", "Green Grocer", "Modular Buildings", 2008, 2352, 1500.0),
        ("10224-1", "Town Hall", "Modular Buildings", 2012, 2766, 600.0),
        ("10197-1", "Fire Brigade", "Modular Buildings", 2009, 2231, 800.0),
        ("10211-1", "Grand Emporium", "Modular Buildings", 2010, 2182, 700.0),
        ("10218-1", "Pet Shop", "Modular Buildings", 2011, 2032, 450.0),
        ("10232-1", "Palace Cinema", "Modular Buildings", 2013, 2196, 500.0),
        ("10243-1", "Parisian Restaurant", "Modular Buildings", 2014, 2469, 450.0),
        ("10246-1", "Detective's Office", "Modular Buildings", 2015, 2262, 500.0),
        ("10255-1", "Assembly Square", "Modular Buildings", 2017, 4002, 500.0),
        ("10264-1", "Corner Garage", "Modular Buildings", 2019, 2569, 380.0),
        ("10270-1", "Bookshop", "Modular Buildings", 2020, 2504, 250.0),
        ("10278-1", "Police Station", "Modular Buildings", 2021, 2923, 250.0),
        ("10297-1", "Boutique Hotel", "Modular Buildings", 2022, 3066, 280.0),
        ("10312-1", "Jazz Club", "Modular Buildings", 2023, 2899, 250.0),

        # ── Ideas / CUUSOO (9 sets) ──────────────────────────────────────
        ("21322-1", "Pirates of Barracuda Bay", "Ideas", 2020, 2545, 350.0),
        ("21301-1", "Birds", "Ideas", 2015, 580, 120.0),
        ("21309-1", "NASA Apollo Saturn V", "Ideas", 2017, 1969, 250.0),
        ("21310-1", "Old Fishing Store", "Ideas", 2017, 2049, 450.0),
        ("21318-1", "Tree House", "Ideas", 2019, 3036, 280.0),
        ("21327-1", "Typewriter", "Ideas", 2021, 2079, 250.0),
        ("92176-1", "NASA Apollo 11 Lunar Lander", "Ideas", 2019, 1087, 180.0),
        ("21323-1", "Grand Piano", "Ideas", 2020, 3662, 380.0),
        ("21330-1", "Home Alone", "Ideas", 2021, 3957, 300.0),

        # ── Technic Flagships (10 sets) ──────────────────────────────────
        ("42115-1", "Lamborghini Sian FKP 37", "Technic", 2020, 3696, 380.0),
        ("42143-1", "Ferrari Daytona SP3", "Technic", 2022, 3778, 400.0),
        ("42056-1", "Porsche 911 GT3 RS", "Technic", 2016, 2704, 550.0),
        ("42083-1", "Bugatti Chiron", "Technic", 2018, 3599, 450.0),
        ("42110-1", "Land Rover Defender", "Technic", 2019, 2573, 280.0),
        ("42096-1", "Porsche 911 RSR", "Technic", 2019, 1580, 200.0),
        ("42125-1", "Ferrari 488 GTE", "Technic", 2021, 1677, 200.0),
        ("42145-1", "Airbus H175 Rescue Helicopter", "Technic", 2022, 2001, 220.0),
        ("42151-1", "Bugatti Bolide", "Technic", 2023, 905, 180.0),
        ("42141-1", "McLaren Formula 1 Race Car", "Technic", 2022, 1432, 200.0),

        # ── Creator Expert / Icons (13 sets) ─────────────────────────────
        ("10196-1", "Grand Carousel", "Creator Expert", 2009, 3263, 1200.0),
        ("10294-1", "Titanic", "Creator Expert", 2021, 9090, 680.0),
        ("10276-1", "Colosseum", "Creator Expert", 2020, 9036, 550.0),
        ("10261-1", "Roller Coaster", "Creator Expert", 2018, 4124, 500.0),
        ("10247-1", "Ferris Wheel", "Creator Expert", 2015, 2464, 400.0),
        ("10256-1", "Taj Mahal (Reissue)", "Creator Expert", 2017, 5923, 500.0),
        ("10295-1", "Porsche 911", "Creator Expert", 2021, 1458, 180.0),
        ("10283-1", "NASA Space Shuttle Discovery", "Creator Expert", 2021, 2354, 250.0),
        ("10266-1", "NASA Apollo 11 Lunar Lander", "Creator Expert", 2019, 1087, 200.0),
        ("10274-1", "Ghostbusters ECTO-1", "Creator Expert", 2020, 2352, 280.0),
        ("10290-1", "Pickup Truck", "Creator Expert", 2021, 1677, 180.0),
        ("10280-1", "Flower Bouquet", "Creator Expert", 2021, 756, 60.0),
        ("10311-1", "Orchid", "Icons", 2022, 608, 55.0),

        # ── Harry Potter (8 sets) ────────────────────────────────────────
        ("71043-1", "Hogwarts Castle", "Harry Potter", 2018, 6020, 500.0),
        ("75978-1", "Diagon Alley", "Harry Potter", 2020, 5544, 500.0),
        ("76391-1", "Hogwarts Icons Collectors' Edition", "Harry Potter", 2021, 3010, 280.0),
        ("76405-1", "Hogwarts Express Collectors' Edition", "Harry Potter", 2022, 5129, 500.0),
        ("76389-1", "Hogwarts Chamber of Secrets", "Harry Potter", 2021, 1176, 150.0),
        ("71042-1", "Hogwarts Express (Original)", "Harry Potter", 2004, 233, 180.0),
        ("4842-1", "Hogwarts Castle (2010)", "Harry Potter", 2010, 1290, 350.0),
        ("10217-1", "Diagon Alley (Original)", "Harry Potter", 2011, 2025, 500.0),

        # ── Pirates (flagship) ───────────────────────────────────────────
        ("10210-1", "Imperial Flagship", "Pirates", 2010, 1664, 600.0),

        # ── Retired Themes / Vintage (10 sets) ───────────────────────────
        ("6285-1", "Black Seas Barracuda", "Pirates", 1989, 909, 700.0),
        ("6276-1", "Eldorado Fortress", "Pirates", 1989, 504, 500.0),
        ("6990-1", "Monorail Transport System", "Space", 1987, 725, 1200.0),
        ("6086-1", "Black Knight's Castle", "Castle", 1992, 588, 400.0),
        ("6277-1", "Imperial Trading Post", "Pirates", 1992, 608, 350.0),
        ("6080-1", "King's Castle", "Castle", 1984, 682, 500.0),
        ("8880-1", "Super Car", "Technic", 1994, 1343, 450.0),
        ("5571-1", "Black Cat (Giant Truck)", "Model Team", 1996, 1445, 500.0),
        ("6399-1", "Airport Shuttle", "Town", 1990, 767, 600.0),
        ("6395-1", "Victory Lap Raceway", "Town", 1988, 517, 250.0),

        # ── GWP / Promotional (6 sets) ───────────────────────────────────
        ("40516-1", "Everyone is Awesome", "Promotional", 2021, 346, 50.0),
        ("40567-1", "Forest Hideout", "Promotional", 2022, 258, 60.0),
        ("40533-1", "Cosmic Cardboard Adventures", "Promotional", 2022, 203, 35.0),
        ("40568-1", "Paris Postcard", "Promotional", 2022, 274, 40.0),
        ("40578-1", "Sandwich Shop", "Promotional", 2022, 254, 45.0),
        ("40580-1", "Blacktron Cruiser", "Promotional", 2023, 356, 55.0),

        # ── CMF (Collectible Minifigures) (6 items) ──────────────────────
        ("8683-1", "Collectible Minifigures Series 1 Complete Set", "Collectible Minifigures", 2010, 16, 450.0),
        ("71001-1", "Mr. Gold (Series 10 CMF)", "Collectible Minifigures", 2013, 9, 3000.0),
        ("71005-1", "Simpsons Series 1 Complete Set", "Collectible Minifigures", 2014, 16, 120.0),
        ("71012-1", "Disney Series 1 Complete Set", "Collectible Minifigures", 2016, 18, 150.0),
        ("71031-1", "Marvel Studios Series 1 Complete Set", "Collectible Minifigures", 2021, 12, 80.0),
        ("66764-1", "Marvel Series 2 Complete Set", "Collectible Minifigures", 2023, 12, 60.0),

        # ── Additional Iconic / Gap-Fillers (5 sets) ─────────────────────
        ("10234-1", "Sydney Opera House", "Creator Expert", 2013, 2989, 450.0),
        ("10181-1", "Eiffel Tower (Large)", "Creator Expert", 2007, 3428, 1200.0),
        ("10189-1", "Taj Mahal (Original)", "Creator Expert", 2008, 5922, 1500.0),
        ("10258-1", "London Bus", "Creator Expert", 2017, 1686, 200.0),
        ("75308-1", "R2-D2 UCS", "Star Wars", 2021, 2314, 250.0),

        # ==================================================================
        # NEW ADDITIONS (~420 sets)
        # ==================================================================

        # ── More Star Wars: Battle Packs & Playsets (25 sets) ─────────────
        ("75372-1", "Clone Trooper & Battle Droid Battle Pack", "Star Wars", 2024, 215, 30.0),
        ("75345-1", "501st Clone Troopers Battle Pack", "Star Wars", 2023, 119, 25.0),
        ("75320-1", "Snowtrooper Battle Pack", "Star Wars", 2022, 105, 20.0),
        ("75280-1", "501st Legion Clone Troopers", "Star Wars", 2020, 285, 80.0),
        ("75283-1", "Armored Assault Tank (AAT)", "Star Wars", 2020, 286, 50.0),
        ("75292-1", "The Razor Crest", "Star Wars", 2020, 1023, 200.0),
        ("75331-1", "The Razor Crest UCS", "Star Wars", 2022, 6187, 550.0),
        ("75257-1", "Millennium Falcon (Rise of Skywalker)", "Star Wars", 2019, 1353, 180.0),
        ("75255-1", "Yoda", "Star Wars", 2019, 1771, 120.0),
        ("75300-1", "Imperial TIE Fighter", "Star Wars", 2021, 432, 45.0),
        ("75301-1", "Luke Skywalker's X-wing Fighter", "Star Wars", 2021, 474, 55.0),
        ("75312-1", "Boba Fett's Starship", "Star Wars", 2021, 593, 55.0),
        ("75341-1", "Luke Skywalker's Landspeeder UCS", "Star Wars", 2022, 1890, 250.0),
        ("75342-1", "Republic Fighter Tank", "Star Wars", 2022, 262, 40.0),
        ("75337-1", "AT-TE Walker", "Star Wars", 2022, 1082, 140.0),
        ("75348-1", "Mandalorian Fang Fighter vs TIE Interceptor", "Star Wars", 2023, 957, 100.0),
        ("75350-1", "Clone Commander Cody Helmet", "Star Wars", 2023, 766, 70.0),
        ("75351-1", "Princess Leia (Boushh) Helmet", "Star Wars", 2023, 670, 65.0),
        ("75352-1", "Emperor's Throne Room Diorama", "Star Wars", 2023, 807, 100.0),
        ("75353-1", "Endor Speeder Chase Diorama", "Star Wars", 2023, 608, 80.0),
        ("75339-1", "Death Star Trash Compactor Diorama", "Star Wars", 2022, 802, 90.0),
        ("75329-1", "Death Star Trench Run Diorama", "Star Wars", 2022, 665, 70.0),
        ("75330-1", "Dagobah Jedi Training Diorama", "Star Wars", 2022, 1000, 90.0),
        ("75349-1", "Captain Rex Helmet", "Star Wars", 2023, 854, 70.0),
        ("75343-1", "Dark Trooper Helmet", "Star Wars", 2022, 693, 65.0),

        # ── Star Wars Helmets Collection (10 sets) ────────────────────────
        ("75277-1", "Boba Fett Helmet", "Star Wars", 2020, 625, 70.0),
        ("75276-1", "Stormtrooper Helmet", "Star Wars", 2020, 647, 70.0),
        ("75274-1", "TIE Fighter Pilot Helmet", "Star Wars", 2020, 686, 70.0),
        ("75304-1", "Darth Vader Helmet", "Star Wars", 2021, 834, 80.0),
        ("75305-1", "Scout Trooper Helmet", "Star Wars", 2021, 471, 55.0),
        ("75328-1", "The Mandalorian Helmet", "Star Wars", 2022, 584, 65.0),
        ("75327-1", "Luke Skywalker (Red Five) Helmet", "Star Wars", 2022, 675, 65.0),
        ("75369-1", "Boba Fett Helmet (2024)", "Star Wars", 2024, 625, 60.0),
        ("75381-1", "Droideka", "Star Wars", 2024, 583, 75.0),
        ("75367-1", "Venator-Class Republic Attack Cruiser", "Star Wars", 2023, 5374, 650.0),

        # ── Star Wars Advent Calendars (6 sets) ───────────────────────────
        ("75340-1", "Star Wars Advent Calendar 2022", "Star Wars", 2022, 329, 45.0),
        ("75366-1", "Star Wars Advent Calendar 2023", "Star Wars", 2023, 320, 40.0),
        ("75056-1", "Star Wars Advent Calendar 2014", "Star Wars", 2014, 274, 80.0),
        ("75097-1", "Star Wars Advent Calendar 2015", "Star Wars", 2015, 292, 70.0),
        ("75184-1", "Star Wars Advent Calendar 2017", "Star Wars", 2017, 309, 55.0),
        ("75213-1", "Star Wars Advent Calendar 2018", "Star Wars", 2018, 307, 50.0),

        # ── More Harry Potter (20 sets) ───────────────────────────────────
        ("76388-1", "Hogsmeade Village Visit", "Harry Potter", 2021, 851, 85.0),
        ("76395-1", "Hogwarts: First Flying Lesson", "Harry Potter", 2021, 264, 35.0),
        ("76396-1", "Hogwarts Moment: Divination Class", "Harry Potter", 2021, 297, 35.0),
        ("76382-1", "Hogwarts Moment: Transfiguration Class", "Harry Potter", 2021, 241, 35.0),
        ("76383-1", "Hogwarts Moment: Potions Class", "Harry Potter", 2021, 271, 35.0),
        ("76385-1", "Hogwarts Moment: Charms Class", "Harry Potter", 2021, 256, 35.0),
        ("76386-1", "Hogwarts: Polyjuice Potion Mistake", "Harry Potter", 2021, 217, 25.0),
        ("76387-1", "Hogwarts: Fluffy Encounter", "Harry Potter", 2021, 397, 45.0),
        ("76392-1", "Hogwarts Wizard's Chess", "Harry Potter", 2021, 876, 80.0),
        ("76390-1", "Harry Potter Advent Calendar 2021", "Harry Potter", 2021, 274, 40.0),
        ("76407-1", "The Shrieking Shack & Whomping Willow", "Harry Potter", 2023, 777, 85.0),
        ("76402-1", "Dumbledore's Office", "Harry Potter", 2023, 654, 55.0),
        ("76408-1", "12 Grimmauld Place", "Harry Potter", 2023, 1083, 120.0),
        ("76403-1", "The Ministry of Magic", "Harry Potter", 2023, 990, 110.0),
        ("76419-1", "Hogwarts Castle and Grounds", "Harry Potter", 2023, 2660, 170.0),
        ("75979-1", "Hedwig", "Harry Potter", 2020, 630, 50.0),
        ("75980-1", "Attack on The Burrow", "Harry Potter", 2020, 1047, 120.0),
        ("75969-1", "Hogwarts Astronomy Tower", "Harry Potter", 2020, 971, 100.0),
        ("75968-1", "4 Privet Drive", "Harry Potter", 2020, 797, 80.0),
        ("76421-1", "Dobby the House-Elf", "Harry Potter", 2024, 403, 30.0),

        # ── Lord of the Rings / The Hobbit (12 sets) ──────────────────────
        ("10316-1", "Rivendell", "Icons", 2023, 6167, 500.0),
        ("10237-1", "Tower of Orthanc", "Lord of the Rings", 2013, 2359, 600.0),
        ("10199-1", "Bag End (Original 2012 prototype concept)", "The Hobbit", 2012, 0, 0.0),
        ("79003-1", "An Unexpected Gathering", "The Hobbit", 2012, 652, 200.0),
        ("9474-1", "The Battle of Helm's Deep", "Lord of the Rings", 2012, 1368, 500.0),
        ("9473-1", "The Mines of Moria", "Lord of the Rings", 2012, 776, 250.0),
        ("9471-1", "Uruk-hai Army", "Lord of the Rings", 2012, 257, 120.0),
        ("79007-1", "Battle at the Black Gate", "Lord of the Rings", 2013, 364, 180.0),
        ("79008-1", "Pirate Ship Ambush", "Lord of the Rings", 2013, 756, 280.0),
        ("79010-1", "The Goblin King Battle", "The Hobbit", 2012, 841, 200.0),
        ("79014-1", "Dol Guldur Battle", "The Hobbit", 2013, 797, 180.0),
        ("79018-1", "The Lonely Mountain", "The Hobbit", 2014, 866, 250.0),

        # ── Marvel Super Heroes (25 sets) ─────────────────────────────────
        ("76178-1", "Daily Bugle", "Marvel", 2021, 3772, 350.0),
        ("76218-1", "Sanctum Sanctorum", "Marvel", 2022, 2708, 250.0),
        ("76269-1", "Avengers Tower", "Marvel", 2024, 5201, 500.0),
        ("76153-1", "Avengers Helicarrier", "Marvel", 2020, 1244, 150.0),
        ("76042-1", "The SHIELD Helicarrier UCS", "Marvel", 2015, 2996, 500.0),
        ("76105-1", "The Hulkbuster: Ultron Edition", "Marvel", 2018, 1363, 200.0),
        ("76161-1", "1989 Batwing", "DC", 2020, 2363, 250.0),
        ("76139-1", "1989 Batmobile", "DC", 2019, 3306, 300.0),
        ("76240-1", "Batmobile Tumbler", "DC", 2021, 2049, 270.0),
        ("76252-1", "Batcave Shadow Box", "DC", 2022, 3981, 400.0),
        ("76023-1", "The Tumbler UCS", "DC", 2014, 1869, 400.0),
        ("7785-1", "Arkham Asylum", "DC", 2006, 860, 300.0),
        ("76239-1", "Batmobile Tumbler: Scarecrow Showdown", "DC", 2021, 422, 50.0),
        ("76183-1", "Batcave: The Riddler Face-Off", "DC", 2022, 581, 80.0),
        ("76224-1", "Batmobile: Batman vs The Joker Chase", "DC", 2023, 438, 45.0),
        ("76248-1", "The Avengers Quinjet", "Marvel", 2023, 795, 100.0),
        ("76243-1", "Rocket Mech Armor", "Marvel", 2023, 98, 12.0),
        ("76247-1", "The Hulkbuster: The Battle of Wakanda", "Marvel", 2023, 385, 35.0),
        ("10318-1", "Concorde", "Icons", 2023, 2083, 200.0),
        ("76257-1", "Wolverine Construction Figure", "Marvel", 2024, 327, 35.0),
        ("76261-1", "Spider-Man Final Battle", "Marvel", 2023, 900, 100.0),
        ("76215-1", "Black Panther", "Marvel", 2022, 2961, 350.0),
        ("76209-1", "Thor's Hammer", "Marvel", 2022, 979, 100.0),
        ("76191-1", "Infinity Gauntlet", "Marvel", 2021, 590, 80.0),
        ("76210-1", "Iron Man Hulkbuster", "Marvel", 2022, 4049, 550.0),

        # ── Speed Champions (25 sets) ─────────────────────────────────────
        ("76916-1", "Porsche 963", "Speed Champions", 2023, 280, 30.0),
        ("76917-1", "2 Fast 2 Furious Nissan Skyline GT-R (R34)", "Speed Champions", 2023, 319, 30.0),
        ("76918-1", "McLaren Solus GT & McLaren F1 LM", "Speed Champions", 2023, 581, 50.0),
        ("76911-1", "007 Aston Martin DB5", "Speed Champions", 2022, 298, 25.0),
        ("76912-1", "Fast & Furious 1970 Dodge Charger R/T", "Speed Champions", 2022, 345, 30.0),
        ("76910-1", "Aston Martin Valkyrie AMR Pro & Vantage GT3", "Speed Champions", 2022, 592, 50.0),
        ("76908-1", "Lamborghini Countach", "Speed Champions", 2022, 262, 25.0),
        ("76907-1", "Lotus Evija", "Speed Champions", 2022, 247, 25.0),
        ("76906-1", "1970 Ferrari 512 M", "Speed Champions", 2022, 291, 25.0),
        ("76909-1", "Mercedes-AMG F1 W12 & Project One", "Speed Champions", 2022, 564, 50.0),
        ("76900-1", "Koenigsegg Jesko", "Speed Champions", 2021, 280, 25.0),
        ("76901-1", "Toyota GR Supra", "Speed Champions", 2021, 299, 25.0),
        ("76902-1", "McLaren Elva", "Speed Champions", 2021, 263, 25.0),
        ("76903-1", "Chevrolet Corvette C8.R & 1968 Corvette", "Speed Champions", 2021, 512, 50.0),
        ("76895-1", "Ferrari F8 Tributo", "Speed Champions", 2020, 275, 25.0),
        ("76896-1", "Nissan GT-R NISMO", "Speed Champions", 2020, 298, 30.0),
        ("76897-1", "1985 Audi Sport Quattro S1", "Speed Champions", 2020, 250, 25.0),
        ("75893-1", "2018 Dodge Challenger SRT Demon & 1970 Charger R/T", "Speed Champions", 2019, 478, 55.0),
        ("75892-1", "McLaren Senna", "Speed Champions", 2019, 219, 20.0),
        ("75891-1", "Chevrolet Camaro ZL1 Race Car", "Speed Champions", 2019, 198, 20.0),
        ("76919-1", "2024 McLaren F1 Race Car", "Speed Champions", 2024, 245, 30.0),
        ("76920-1", "Ford Mustang Dark Horse", "Speed Champions", 2024, 344, 30.0),
        ("76921-1", "Audi S1 e-tron quattro Race Car", "Speed Champions", 2024, 274, 30.0),
        ("76922-1", "BMW M4 GT3 & BMW M Hybrid V8", "Speed Champions", 2024, 676, 55.0),
        ("76924-1", "Mercedes-AMG GT3 & Mercedes-AMG SL 63", "Speed Champions", 2024, 792, 55.0),

        # ── Architecture (30 sets) ────────────────────────────────────────
        ("21054-1", "The White House", "Architecture", 2020, 1483, 120.0),
        ("21060-1", "Himeji Castle", "Architecture", 2023, 2125, 180.0),
        ("21058-1", "Great Pyramid of Giza", "Architecture", 2022, 1476, 130.0),
        ("21056-1", "Taj Mahal", "Architecture", 2021, 2022, 120.0),
        ("21057-1", "Singapore", "Architecture", 2022, 827, 65.0),
        ("21055-1", "Guggenheim Museum (Bilbao)", "Architecture", 2021, 0, 0.0),
        ("21051-1", "Tokyo", "Architecture", 2020, 547, 65.0),
        ("21052-1", "Dubai", "Architecture", 2020, 740, 65.0),
        ("21044-1", "Paris", "Architecture", 2019, 649, 55.0),
        ("21046-1", "Empire State Building", "Architecture", 2019, 1767, 130.0),
        ("21042-1", "Statue of Liberty", "Architecture", 2018, 1685, 130.0),
        ("21034-1", "London", "Architecture", 2017, 468, 45.0),
        ("21028-1", "New York City", "Architecture", 2016, 598, 60.0),
        ("21030-1", "United States Capitol Building", "Architecture", 2016, 1032, 100.0),
        ("21024-1", "Louvre", "Architecture", 2015, 695, 70.0),
        ("21019-1", "Eiffel Tower", "Architecture", 2014, 321, 40.0),
        ("21010-1", "Robie House", "Architecture", 2011, 2276, 350.0),
        ("21005-1", "Fallingwater", "Architecture", 2009, 811, 250.0),
        ("21050-1", "Studio", "Architecture", 2013, 1210, 180.0),
        ("21004-1", "Solomon R. Guggenheim Museum", "Architecture", 2009, 208, 120.0),
        ("21035-1", "Solomon R. Guggenheim Museum (2017)", "Architecture", 2017, 744, 90.0),
        ("21041-1", "Great Wall of China", "Architecture", 2018, 551, 55.0),
        ("21043-1", "San Francisco", "Architecture", 2019, 565, 55.0),
        ("21047-1", "Las Vegas", "Architecture", 2019, 501, 45.0),
        ("21045-1", "Trafalgar Square", "Architecture", 2019, 1197, 90.0),
        ("21036-1", "Arc de Triomphe", "Architecture", 2017, 386, 50.0),
        ("21039-1", "Shanghai", "Architecture", 2018, 597, 55.0),
        ("21032-1", "Sydney", "Architecture", 2017, 361, 40.0),
        ("21026-1", "Venice", "Architecture", 2016, 212, 35.0),
        ("21061-1", "Notre-Dame de Paris", "Architecture", 2024, 4383, 230.0),

        # ── City (20 sets) ────────────────────────────────────────────────
        ("60337-1", "Express Passenger Train", "City", 2022, 764, 180.0),
        ("60336-1", "Freight Train", "City", 2022, 1153, 200.0),
        ("60198-1", "Cargo Train", "City", 2018, 1226, 250.0),
        ("60197-1", "Passenger Train", "City", 2018, 677, 150.0),
        ("60052-1", "Cargo Train (2014)", "City", 2014, 888, 200.0),
        ("60051-1", "High-Speed Passenger Train", "City", 2014, 610, 150.0),
        ("60350-1", "Lunar Research Base", "City", 2022, 786, 100.0),
        ("60351-1", "Rocket Launch Center", "City", 2022, 1010, 120.0),
        ("60349-1", "Lunar Space Station", "City", 2022, 500, 65.0),
        ("60228-1", "Deep Space Rocket and Launch Control", "City", 2019, 837, 100.0),
        ("60141-1", "Police Station (2017)", "City", 2017, 894, 100.0),
        ("60110-1", "Fire Station (2016)", "City", 2016, 919, 120.0),
        ("60204-1", "City Hospital", "City", 2018, 861, 100.0),
        ("60271-1", "Main Square", "City", 2021, 1517, 150.0),
        ("60317-1", "Police Chase at the Bank", "City", 2022, 915, 100.0),
        ("60380-1", "Downtown", "City", 2023, 2010, 200.0),
        ("60346-1", "Barn & Farm Animals", "City", 2022, 230, 50.0),
        ("60316-1", "Police Station", "City", 2022, 668, 60.0),
        ("60292-1", "Town Center", "City", 2021, 790, 100.0),
        ("60200-1", "Capital City", "City", 2018, 1211, 140.0),

        # ── Ninjago (20 sets) ─────────────────────────────────────────────
        ("71741-1", "Ninjago City Gardens", "Ninjago", 2021, 5685, 350.0),
        ("71799-1", "Ninjago City Markets", "Ninjago", 2023, 6163, 400.0),
        ("70620-1", "Ninjago City", "Ninjago", 2017, 4867, 500.0),
        ("70657-1", "Ninjago City Docks", "Ninjago", 2018, 3553, 400.0),
        ("71767-1", "Ninja Dojo Temple", "Ninjago", 2022, 1394, 120.0),
        ("71765-1", "Ninja Ultra Combo Mech", "Ninjago", 2022, 1104, 100.0),
        ("71738-1", "Zane's Titan Mech Battle", "Ninjago", 2021, 840, 80.0),
        ("70751-1", "Temple of Airjitzu", "Ninjago", 2015, 2028, 400.0),
        ("71753-1", "Fire Dragon Attack", "Ninjago", 2021, 563, 50.0),
        ("70618-1", "Destiny's Bounty", "Ninjago", 2017, 2295, 280.0),
        ("71705-1", "Destiny's Bounty", "Ninjago", 2020, 1781, 150.0),
        ("71756-1", "Hydro Bounty", "Ninjago", 2021, 1159, 80.0),
        ("70612-1", "Green Ninja Mech Dragon", "Ninjago", 2017, 544, 80.0),
        ("70655-1", "The Dragon Pit", "Ninjago", 2018, 1660, 180.0),
        ("71746-1", "Jungle Dragon", "Ninjago", 2021, 506, 40.0),
        ("71737-1", "X-1 Ninja Charger", "Ninjago", 2021, 599, 55.0),
        ("71774-1", "Lloyd's Golden Ultra Dragon", "Ninjago", 2022, 989, 80.0),
        ("71766-1", "Lloyd's Legendary Dragon", "Ninjago", 2022, 747, 60.0),
        ("71775-1", "Nya's Samurai X MECH", "Ninjago", 2022, 1003, 80.0),
        ("71794-1", "Lloyd and Arin's Ninja Team Mechs", "Ninjago", 2023, 764, 70.0),

        # ── Friends (15 sets) ─────────────────────────────────────────────
        ("41318-1", "Heartlake Hospital", "Friends", 2017, 871, 100.0),
        ("41347-1", "Heartlake City Resort", "Friends", 2018, 1017, 120.0),
        ("41340-1", "Friendship House", "Friends", 2018, 722, 70.0),
        ("41395-1", "Friendship Bus", "Friends", 2020, 778, 65.0),
        ("41450-1", "Heartlake City Shopping Mall", "Friends", 2021, 1032, 90.0),
        ("41684-1", "Heartlake City Grand Hotel", "Friends", 2021, 1308, 110.0),
        ("41711-1", "Emma's Art School", "Friends", 2022, 844, 75.0),
        ("41732-1", "Downtown Flower and Design Stores", "Friends", 2023, 2010, 160.0),
        ("41130-1", "Amusement Park Roller Coaster", "Friends", 2016, 1124, 150.0),
        ("41375-1", "Heartlake City Amusement Pier", "Friends", 2019, 1251, 120.0),
        ("41369-1", "Mia's House", "Friends", 2019, 715, 65.0),
        ("41314-1", "Stephanie's House", "Friends", 2017, 622, 55.0),
        ("41379-1", "Heartlake City Restaurant", "Friends", 2020, 624, 55.0),
        ("41735-1", "Mobile Tiny House", "Friends", 2023, 785, 60.0),
        ("42604-1", "Heartlake City Shopping Mall (2024)", "Friends", 2024, 1237, 100.0),

        # ── Elves (8 sets) ────────────────────────────────────────────────
        ("41078-1", "Skyra's Mysterious Sky Castle", "Elves", 2015, 808, 120.0),
        ("41180-1", "Ragana's Magic Shadow Castle", "Elves", 2016, 1014, 150.0),
        ("41176-1", "The Secret Market Place", "Elves", 2016, 691, 80.0),
        ("41196-1", "The Elvenstar Tree Bat Attack", "Elves", 2018, 883, 100.0),
        ("41188-1", "Breakout from the Goblin King's Fortress", "Elves", 2017, 695, 90.0),
        ("41187-1", "Rosalyn's Healing Hideout", "Elves", 2017, 460, 60.0),
        ("41175-1", "Fire Dragon's Lava Cave", "Elves", 2016, 441, 70.0),
        ("41194-1", "Noctura's Tower & the Earth Fox Rescue", "Elves", 2018, 646, 85.0),

        # ── BrickHeadz (20 sets) ──────────────────────────────────────────
        ("41585-1", "Batman BrickHeadz", "BrickHeadz", 2017, 93, 15.0),
        ("41586-1", "Batgirl BrickHeadz", "BrickHeadz", 2017, 119, 15.0),
        ("41587-1", "Robin BrickHeadz", "BrickHeadz", 2017, 101, 15.0),
        ("41588-1", "The Joker BrickHeadz", "BrickHeadz", 2017, 151, 20.0),
        ("41589-1", "Captain America BrickHeadz", "BrickHeadz", 2017, 79, 15.0),
        ("41590-1", "Iron Man BrickHeadz", "BrickHeadz", 2017, 96, 15.0),
        ("41591-1", "Black Widow BrickHeadz", "BrickHeadz", 2017, 143, 18.0),
        ("41592-1", "The Hulk BrickHeadz", "BrickHeadz", 2017, 93, 15.0),
        ("41596-1", "Beast BrickHeadz", "BrickHeadz", 2017, 116, 15.0),
        ("41597-1", "Go Brick Me", "BrickHeadz", 2018, 708, 40.0),
        ("40539-1", "Ahsoka Tano BrickHeadz", "BrickHeadz", 2022, 164, 12.0),
        ("40540-1", "Lion Dance Guy BrickHeadz", "BrickHeadz", 2022, 239, 12.0),
        ("40541-1", "Manchester United Go Brick Me", "BrickHeadz", 2022, 530, 30.0),
        ("40542-1", "FC Barcelona Go Brick Me", "BrickHeadz", 2022, 530, 30.0),
        ("40543-1", "Spider-Man & Venom BrickHeadz", "BrickHeadz", 2022, 318, 20.0),
        ("40544-1", "French Bulldog Pets BrickHeadz", "BrickHeadz", 2022, 252, 15.0),
        ("40552-1", "Buzz Lightyear & Sox BrickHeadz", "BrickHeadz", 2022, 252, 15.0),
        ("40615-1", "Tuxedo Cat BrickHeadz", "BrickHeadz", 2023, 145, 12.0),
        ("40619-1", "EVE & WALL-E BrickHeadz", "BrickHeadz", 2023, 155, 20.0),
        ("40622-1", "Disney 100th Celebration BrickHeadz", "BrickHeadz", 2023, 330, 15.0),

        # ── Seasonal / Winter Village (15 sets) ──────────────────────────
        ("10199-1", "Winter Toy Shop", "Winter Village", 2009, 815, 250.0),
        ("10216-1", "Winter Village Bakery", "Winter Village", 2010, 687, 200.0),
        ("10222-1", "Winter Village Post Office", "Winter Village", 2011, 822, 250.0),
        ("10229-1", "Winter Village Cottage", "Winter Village", 2012, 1490, 300.0),
        ("10235-1", "Winter Village Market", "Winter Village", 2013, 1261, 200.0),
        ("10245-1", "Santa's Workshop", "Winter Village", 2014, 883, 150.0),
        ("10249-1", "Winter Toy Shop (2015)", "Winter Village", 2015, 898, 120.0),
        ("10254-1", "Winter Holiday Train", "Winter Village", 2016, 734, 150.0),
        ("10259-1", "Winter Village Station", "Winter Village", 2017, 902, 130.0),
        ("10263-1", "Winter Village Fire Station", "Winter Village", 2018, 1166, 120.0),
        ("10267-1", "Gingerbread House", "Winter Village", 2019, 1477, 120.0),
        ("10275-1", "Elf Club House", "Winter Village", 2020, 1197, 100.0),
        ("10293-1", "Santa's Visit", "Winter Village", 2021, 1445, 110.0),
        ("10308-1", "Christmas High Street", "Winter Village", 2022, 1514, 110.0),
        ("10325-1", "Alpine Lodge", "Winter Village", 2023, 1517, 110.0),

        # ── Chinese New Year / Spring Festival (10 sets) ──────────────────
        ("80104-1", "Lion Dance", "Chinese New Year", 2020, 882, 120.0),
        ("80105-1", "Chinese New Year Temple Fair", "Chinese New Year", 2020, 1664, 150.0),
        ("80106-1", "Story of Nian", "Chinese New Year", 2021, 1067, 90.0),
        ("80107-1", "Spring Lantern Festival", "Chinese New Year", 2021, 1793, 130.0),
        ("80108-1", "Lunar New Year Traditions", "Chinese New Year", 2022, 1066, 90.0),
        ("80109-1", "Lunar New Year Ice Festival", "Chinese New Year", 2022, 1519, 120.0),
        ("80110-1", "Lunar New Year Display", "Chinese New Year", 2023, 872, 100.0),
        ("80111-1", "Lunar New Year Parade", "Chinese New Year", 2023, 1653, 130.0),
        ("80113-1", "Family Reunion Celebration", "Chinese New Year", 2024, 1823, 150.0),
        ("80112-1", "Auspicious Dragon", "Chinese New Year", 2024, 1171, 100.0),

        # ── Botanical Collection (12 sets) ────────────────────────────────
        ("10281-1", "Bonsai Tree", "Botanical Collection", 2021, 878, 50.0),
        ("10289-1", "Bird of Paradise", "Botanical Collection", 2021, 1173, 100.0),
        ("10313-1", "Wildflower Bouquet", "Botanical Collection", 2023, 939, 55.0),
        ("10314-1", "Dried Flower Centerpiece", "Botanical Collection", 2023, 812, 50.0),
        ("10309-1", "Succulents", "Botanical Collection", 2022, 771, 50.0),
        ("40460-1", "Roses", "Botanical Collection", 2021, 120, 15.0),
        ("40461-1", "Tulips", "Botanical Collection", 2021, 111, 15.0),
        ("40524-1", "Sunflowers", "Botanical Collection", 2022, 191, 15.0),
        ("40647-1", "Lotus Flowers", "Botanical Collection", 2023, 220, 15.0),
        ("40725-1", "Cherry Blossoms", "Botanical Collection", 2024, 438, 15.0),
        ("10329-1", "Tiny Plants", "Botanical Collection", 2023, 758, 50.0),
        ("10344-1", "Flower Bouquet (2024)", "Botanical Collection", 2024, 1050, 60.0),

        # ── Art / Mosaic (10 sets) ────────────────────────────────────────
        ("31197-1", "Andy Warhol's Marilyn Monroe", "Art", 2020, 3341, 130.0),
        ("31198-1", "The Beatles", "Art", 2020, 2933, 130.0),
        ("31199-1", "Marvel Studios Iron Man", "Art", 2020, 3167, 130.0),
        ("31200-1", "Star Wars The Sith", "Art", 2020, 3395, 130.0),
        ("31201-1", "Harry Potter Hogwarts Crests", "Art", 2020, 4249, 130.0),
        ("31202-1", "Disney's Mickey Mouse", "Art", 2021, 2658, 120.0),
        ("31203-1", "World Map", "Art", 2021, 11695, 300.0),
        ("31204-1", "Elvis Presley The King", "Art", 2022, 3445, 130.0),
        ("31205-1", "Jim Lee Batman Collection", "Art", 2022, 4167, 130.0),
        ("31209-1", "The Amazing Spider-Man", "Art", 2023, 2099, 80.0),

        # ── Bionicle (15 sets) ────────────────────────────────────────────
        ("8534-1", "Tahu", "Bionicle", 2001, 33, 40.0),
        ("8535-1", "Lewa", "Bionicle", 2001, 36, 35.0),
        ("8536-1", "Kopaka", "Bionicle", 2001, 33, 35.0),
        ("8537-1", "Nui-Rama", "Bionicle", 2001, 138, 50.0),
        ("8538-1", "Muaka & Kane-Ra", "Bionicle", 2001, 633, 120.0),
        ("8557-1", "Exo-Toa", "Bionicle", 2002, 360, 100.0),
        ("8558-1", "Cahdok & Gahdok", "Bionicle", 2002, 399, 100.0),
        ("10204-1", "Vezon & Kardas", "Bionicle", 2006, 670, 250.0),
        ("8998-1", "Toa Mata Nui", "Bionicle", 2009, 366, 150.0),
        ("8943-1", "Axalara T9", "Bionicle", 2008, 693, 200.0),
        ("8941-1", "Rockoh T3", "Bionicle", 2008, 390, 120.0),
        ("8942-1", "Jetrax T6", "Bionicle", 2008, 422, 130.0),
        ("8953-1", "Makuta Icarax", "Bionicle", 2008, 159, 80.0),
        ("8733-1", "Axonn", "Bionicle", 2006, 196, 70.0),
        ("8734-1", "Brutaka", "Bionicle", 2006, 193, 80.0),

        # ── Mindstorms (8 sets) ───────────────────────────────────────────
        ("9797-1", "Mindstorms Education NXT Base Set", "Mindstorms", 2006, 431, 200.0),
        ("8547-1", "Mindstorms NXT 2.0", "Mindstorms", 2009, 619, 350.0),
        ("31313-1", "Mindstorms EV3", "Mindstorms", 2013, 601, 400.0),
        ("45544-1", "Mindstorms Education EV3 Core Set", "Mindstorms", 2013, 541, 300.0),
        ("51515-1", "Robot Inventor", "Mindstorms", 2020, 949, 380.0),
        ("8527-1", "Mindstorms NXT", "Mindstorms", 2006, 577, 250.0),
        ("9841-1", "Mindstorms RCX Intelligent Brick", "Mindstorms", 1998, 1, 150.0),
        ("3804-1", "Mindstorms Robotics Invention System 2.0", "Mindstorms", 2001, 718, 200.0),

        # ── Duplo (Rare/Retired Collector Sets) (10 sets) ─────────────────
        ("10214-1", "Tower Bridge (regular set reclassified)", "Creator Expert", 2010, 4287, 400.0),
        ("10505-1", "Play House", "Duplo", 2013, 83, 50.0),
        ("10827-1", "Mickey & Friends Beach House", "Duplo", 2016, 48, 45.0),
        ("10903-1", "Fire Station", "Duplo", 2019, 76, 55.0),
        ("10840-1", "Big Fair", "Duplo", 2018, 106, 80.0),
        ("10906-1", "Tropical Island", "Duplo", 2019, 73, 55.0),
        ("10935-1", "Alphabet Town", "Duplo", 2023, 87, 40.0),
        ("10929-1", "Modular Playhouse", "Duplo", 2020, 129, 65.0),
        ("10956-1", "Amusement Park", "Duplo", 2021, 95, 100.0),
        ("10994-1", "3in1 Family House", "Duplo", 2023, 218, 100.0),

        # ── Classic Space (10 sets) ───────────────────────────────────────
        ("928-1", "Galaxy Explorer", "Classic Space", 1979, 338, 400.0),
        ("497-1", "Galaxy Explorer (US)", "Classic Space", 1979, 338, 400.0),
        ("6929-1", "Starfleet Voyager", "Classic Space", 1981, 235, 250.0),
        ("6980-1", "Galaxy Commander", "Classic Space", 1983, 361, 300.0),
        ("6985-1", "Cosmic Fleet Voyager", "Classic Space", 1986, 455, 400.0),
        ("6891-1", "Gamma V Laser Craft", "Classic Space", 1985, 172, 120.0),
        ("6971-1", "Inter-Galactic Command Base", "Classic Space", 1984, 462, 350.0),
        ("6930-1", "Space Supply Station", "Classic Space", 1983, 270, 200.0),
        ("6952-1", "Solar Power Transporter", "Classic Space", 1985, 192, 150.0),
        ("10497-1", "Galaxy Explorer (2022 Reissue)", "Icons", 2022, 1254, 100.0),

        # ── Classic Castle (10 sets) ──────────────────────────────────────
        ("375-1", "Castle", "Castle", 1978, 767, 600.0),
        ("6074-1", "Black Falcon's Fortress", "Castle", 1986, 435, 350.0),
        ("6090-1", "Royal Knight's Castle", "Castle", 1995, 743, 300.0),
        ("6081-1", "King's Mountain Fortress", "Castle", 1990, 435, 280.0),
        ("6075-1", "Wolfpack Tower", "Castle", 1992, 252, 150.0),
        ("6098-1", "King Leo's Castle", "Castle", 2000, 524, 200.0),
        ("10176-1", "Royal King's Castle", "Castle", 2006, 996, 300.0),
        ("7094-1", "King's Castle Siege", "Castle", 2007, 973, 250.0),
        ("70404-1", "King's Castle", "Castle", 2013, 996, 200.0),
        ("10305-1", "Lion Knights' Castle", "Icons", 2022, 4514, 400.0),

        # ── Classic Town & Adventurers (12 sets) ──────────────────────────
        ("6394-1", "Metro Park & Service Tower", "Town", 1988, 537, 250.0),
        ("6392-1", "Airport", "Town", 1985, 623, 300.0),
        ("6386-1", "Police Command Base", "Town", 1986, 604, 250.0),
        ("6541-1", "Intercoastal Seaport", "Town", 1991, 488, 200.0),
        ("6542-1", "Launch & Load Seaport", "Town", 1991, 788, 250.0),
        ("5988-1", "Pharaoh's Forbidden Ruins", "Adventurers", 1998, 727, 300.0),
        ("5986-1", "Amazon Ancient Ruins", "Adventurers", 1999, 736, 250.0),
        ("5975-1", "T-Rex Transport", "Adventurers", 2000, 414, 180.0),
        ("7418-1", "Scorpion Palace", "Adventurers", 2003, 547, 200.0),
        ("5978-1", "Sphinx Secret Surprise", "Adventurers", 1998, 327, 150.0),
        ("5987-1", "Dino Research Compound", "Adventurers", 2000, 697, 250.0),
        ("7419-1", "Dragon Fortress", "Adventurers", 2003, 393, 150.0),

        # ── Rock Raiders & Aquanauts (8 sets) ─────────────────────────────
        ("4990-1", "Rock Raiders HQ", "Rock Raiders", 1999, 422, 200.0),
        ("4970-1", "Chrome Crusher", "Rock Raiders", 1999, 285, 100.0),
        ("4980-1", "Tunnel Transport", "Rock Raiders", 1999, 270, 90.0),
        ("6195-1", "Neptune Discovery Lab", "Aquanauts", 1995, 418, 200.0),
        ("6175-1", "Crystal Explorer Sub", "Aquanauts", 1995, 215, 100.0),
        ("6190-1", "Shark's Crystal Cave", "Aquazone", 1996, 244, 100.0),
        ("6159-1", "Crystal Detector", "Aquazone", 1998, 117, 50.0),
        ("6155-1", "Deep Sea Predator", "Aquazone", 1995, 324, 120.0),

        # ── Recent 2023-2025 Popular Sets (40 sets) ───────────────────────
        ("10300-1", "Back to the Future Time Machine (DeLorean)", "Icons", 2022, 1872, 180.0),
        ("10307-1", "Eiffel Tower", "Icons", 2022, 10001, 630.0),
        ("10302-1", "Optimus Prime", "Icons", 2022, 1508, 180.0),
        ("10306-1", "Atari 2600", "Icons", 2022, 2532, 250.0),
        ("10317-1", "Land Rover Classic Defender 90", "Icons", 2023, 2336, 230.0),
        ("10321-1", "Corvette", "Icons", 2023, 1210, 150.0),
        ("10322-1", "Fender Stratocaster", "Ideas", 2021, 1074, 120.0),
        ("10298-1", "Vespa 125", "Icons", 2022, 1106, 100.0),
        ("10299-1", "Real Madrid Santiago Bernabeu Stadium", "Icons", 2022, 5876, 350.0),
        ("10284-1", "Camp Nou FC Barcelona", "Icons", 2021, 5509, 350.0),
        ("10323-1", "PAC-MAN Arcade", "Icons", 2023, 2651, 270.0),
        ("21335-1", "Motorized Lighthouse", "Ideas", 2022, 2065, 300.0),
        ("21334-1", "Jazz Quartet", "Ideas", 2022, 1606, 100.0),
        ("21333-1", "Vincent van Gogh - The Starry Night", "Ideas", 2022, 2316, 180.0),
        ("21332-1", "The Globe", "Ideas", 2022, 2585, 230.0),
        ("21331-1", "Sonic the Hedgehog - Green Hill Zone", "Ideas", 2022, 1125, 80.0),
        ("21336-1", "The Office", "Ideas", 2022, 1164, 120.0),
        ("21337-1", "Table Football", "Ideas", 2022, 2339, 250.0),
        ("21338-1", "A-Frame Cabin", "Ideas", 2023, 2082, 180.0),
        ("21339-1", "BTS Dynamite", "Ideas", 2023, 749, 100.0),
        ("21340-1", "Tales of the Space Age", "Ideas", 2023, 688, 50.0),
        ("21341-1", "Disney Hocus Pocus: The Sanderson Sisters' Cottage", "Ideas", 2023, 2316, 230.0),
        ("21342-1", "The Insect Collection", "Ideas", 2023, 1111, 80.0),
        ("21343-1", "Viking Village", "Ideas", 2024, 2103, 130.0),
        ("21344-1", "The Orient Express Train", "Ideas", 2024, 2540, 300.0),
        ("10327-1", "Dune Atreides Royal Ornithopter", "Icons", 2024, 1369, 165.0),
        ("10328-1", "Bouquet of Roses", "Botanical Collection", 2024, 822, 60.0),
        ("10330-1", "McLaren MP4/4 & Ayrton Senna", "Icons", 2024, 693, 90.0),
        ("10331-1", "Kingfisher Bird", "Icons", 2024, 834, 50.0),
        ("10332-1", "Medieval Town Square", "Icons", 2024, 3304, 230.0),
        ("10333-1", "The Lord of the Rings: Barad-dur", "Icons", 2024, 5471, 460.0),
        ("10334-1", "Jazz Club (2024)", "Icons", 2024, 2899, 240.0),
        ("75371-1", "Chewbacca", "Star Wars", 2024, 2319, 200.0),
        ("75378-1", "BARC Speeder Escape", "Star Wars", 2024, 221, 30.0),
        ("75379-1", "R2-D2 (2024)", "Star Wars", 2024, 1050, 90.0),
        ("75380-1", "Mos Espa Podrace Diorama", "Star Wars", 2024, 718, 80.0),
        ("75382-1", "TIE Interceptor", "Star Wars", 2024, 1931, 240.0),
        ("42160-1", "Audi RS Q e-tron", "Technic", 2023, 914, 180.0),
        ("42159-1", "Yamaha MT-10 SP", "Technic", 2023, 1478, 200.0),
        ("42156-1", "PEUGEOT 9X8 24H Le Mans Hybrid Hypercar", "Technic", 2023, 1775, 200.0),

        # ── More Ideas / CUUSOO (10 sets) ─────────────────────────────────
        ("21303-1", "WALL-E", "Ideas", 2015, 676, 200.0),
        ("21313-1", "Ship in a Bottle", "Ideas", 2018, 962, 120.0),
        ("21314-1", "TRON: Legacy", "Ideas", 2018, 230, 80.0),
        ("21315-1", "Pop-Up Book", "Ideas", 2018, 859, 120.0),
        ("21316-1", "The Flintstones", "Ideas", 2019, 748, 80.0),
        ("21317-1", "Steamboat Willie", "Ideas", 2019, 751, 120.0),
        ("21319-1", "Central Perk", "Ideas", 2019, 1070, 100.0),
        ("21320-1", "Dinosaur Fossils", "Ideas", 2019, 910, 70.0),
        ("21324-1", "123 Sesame Street", "Ideas", 2020, 1367, 150.0),
        ("21326-1", "Winnie the Pooh", "Ideas", 2021, 1265, 120.0),

        # ── More Creator Expert / Icons (10 sets) ─────────────────────────
        ("10248-1", "Ferrari F40", "Creator Expert", 2015, 1158, 200.0),
        ("10252-1", "Volkswagen Beetle", "Creator Expert", 2016, 1167, 180.0),
        ("10262-1", "James Bond Aston Martin DB5", "Creator Expert", 2018, 1295, 200.0),
        ("10269-1", "Harley-Davidson Fat Boy", "Creator Expert", 2019, 1023, 120.0),
        ("10271-1", "Fiat 500", "Creator Expert", 2020, 960, 90.0),
        ("10265-1", "Ford Mustang", "Creator Expert", 2019, 1471, 170.0),
        ("10242-1", "MINI Cooper", "Creator Expert", 2014, 1077, 180.0),
        ("10220-1", "Volkswagen T1 Camper Van", "Creator Expert", 2011, 1334, 250.0),
        ("10187-1", "Volkswagen Beetle (Vintage)", "Creator Expert", 2008, 1626, 350.0),
        ("10279-1", "Volkswagen T2 Camper Van", "Creator Expert", 2021, 2207, 180.0),

        # ── More Technic (10 sets) ────────────────────────────────────────
        ("42100-1", "Liebherr R 9800 Excavator", "Technic", 2019, 4108, 500.0),
        ("42055-1", "Bucket Wheel Excavator", "Technic", 2016, 3929, 400.0),
        ("42030-1", "Volvo L350F Wheel Loader", "Technic", 2014, 1636, 250.0),
        ("42009-1", "Mobile Crane MK II", "Technic", 2013, 2606, 400.0),
        ("42043-1", "Mercedes-Benz Arocs 3245", "Technic", 2015, 2793, 350.0),
        ("42082-1", "Rough Terrain Crane", "Technic", 2018, 4057, 300.0),
        ("42131-1", "Cat D11 Bulldozer", "Technic", 2021, 3854, 450.0),
        ("42146-1", "Liebherr LR 13000 Crawler Crane", "Technic", 2023, 2883, 600.0),
        ("42128-1", "Heavy-Duty Tow Truck", "Technic", 2021, 2017, 180.0),
        ("42114-1", "Volvo 6x6 Articulated Hauler", "Technic", 2020, 2193, 250.0),

        # ── Disney (15 sets) ──────────────────────────────────────────────
        ("71040-1", "Disney Castle", "Disney", 2016, 4080, 400.0),
        ("43222-1", "Disney Castle (2023)", "Disney", 2023, 4837, 380.0),
        ("43197-1", "The Ice Castle", "Disney Princess", 2021, 1709, 200.0),
        ("43227-1", "Villain Icons", "Disney", 2024, 464, 50.0),
        ("43230-1", "Walt Disney Tribute Camera", "Disney", 2023, 811, 90.0),
        ("43217-1", "Up House", "Disney", 2023, 598, 50.0),
        ("43232-1", "Peter Pan & Wendy's Flight Over London", "Disney", 2023, 466, 70.0),
        ("43211-1", "Aurora's Castle", "Disney Princess", 2023, 187, 35.0),
        ("40521-1", "Mini Disney The Haunted Mansion", "Disney", 2022, 680, 35.0),
        ("21329-1", "Fender Stratocaster", "Ideas", 2021, 1074, 120.0),
        ("40622-2", "Disney 100th Celebration", "Disney", 2023, 330, 15.0),
        ("43181-1", "Raya and the Heart Palace", "Disney", 2021, 610, 80.0),
        ("43196-1", "Belle and the Beast's Castle", "Disney Princess", 2021, 505, 70.0),
        ("10196-2", "Grand Carousel (Creator Expert)", "Creator Expert", 2009, 3263, 1200.0),
        ("71044-1", "Disney Train and Station", "Disney", 2019, 2925, 350.0),

        # ── Super Mario (10 sets) ─────────────────────────────────────────
        ("71374-1", "Nintendo Entertainment System", "Super Mario", 2020, 2646, 270.0),
        ("71395-1", "Super Mario 64 Question Mark Block", "Super Mario", 2021, 2064, 200.0),
        ("71411-1", "The Mighty Bowser", "Super Mario", 2022, 2807, 270.0),
        ("71387-1", "Adventures with Luigi Starter Course", "Super Mario", 2021, 280, 55.0),
        ("71360-1", "Adventures with Mario Starter Course", "Super Mario", 2020, 231, 55.0),
        ("71369-1", "Bowser's Castle Boss Battle Expansion", "Super Mario", 2020, 1010, 100.0),
        ("71390-1", "Reznor Knockdown Expansion Set", "Super Mario", 2021, 862, 70.0),
        ("71391-1", "Bowser's Airship Expansion Set", "Super Mario", 2021, 1152, 100.0),
        ("71408-1", "Peach's Castle Expansion Set", "Super Mario", 2022, 1216, 120.0),
        ("71431-1", "Bowser's Muscle Car Expansion", "Super Mario", 2024, 458, 35.0),

        # ── More GWP / Promotional (10 sets) ──────────────────────────────
        ("40597-1", "Scary Pirate Island", "Promotional", 2023, 265, 40.0),
        ("40598-1", "Harry Potter Platform 9 3/4 Polybag", "Promotional", 2023, 36, 10.0),
        ("40583-1", "Houses of the World 1", "Promotional", 2023, 317, 35.0),
        ("40590-1", "Houses of the World 2", "Promotional", 2023, 326, 35.0),
        ("40594-1", "Houses of the World 3", "Promotional", 2023, 303, 35.0),
        ("40563-1", "Tribute to LEGO House", "Promotional", 2022, 583, 80.0),
        ("40601-1", "Majisto's Magical Workshop", "Promotional", 2023, 355, 45.0),
        ("5006746-1", "Ulysses Space Probe VIP Reward", "Promotional", 2021, 91, 50.0),
        ("40586-1", "Moving Truck", "Promotional", 2022, 301, 35.0),
        ("40588-1", "LEGO Flowerpot", "Promotional", 2022, 261, 25.0),

        # ── More CMF Complete Sets (6 sets) ───────────────────────────────
        ("8684-1", "Collectible Minifigures Series 2 Complete Set", "Collectible Minifigures", 2010, 16, 300.0),
        ("8803-1", "Collectible Minifigures Series 3 Complete Set", "Collectible Minifigures", 2011, 16, 250.0),
        ("8804-1", "Collectible Minifigures Series 4 Complete Set", "Collectible Minifigures", 2011, 16, 200.0),
        ("8805-1", "Collectible Minifigures Series 5 Complete Set", "Collectible Minifigures", 2011, 16, 200.0),
        ("71039-1", "Marvel Studios Series 2 Complete Set", "Collectible Minifigures", 2023, 12, 55.0),
        ("71046-1", "Series 26 Complete Set", "Collectible Minifigures", 2024, 12, 55.0),

        # ── Jurassic World / Park (10 sets) ───────────────────────────────
        ("75936-1", "Jurassic Park: T. rex Rampage", "Jurassic World", 2019, 3120, 350.0),
        ("76956-1", "T. rex Breakout", "Jurassic World", 2022, 1212, 100.0),
        ("75919-1", "Indominus Rex Breakout", "Jurassic World", 2015, 1156, 250.0),
        ("75930-1", "Indoraptor Rampage at Lockwood Estate", "Jurassic World", 2018, 1019, 120.0),
        ("76961-1", "Visitor Center: T. rex & Raptor Attack", "Jurassic World", 2023, 693, 100.0),
        ("76949-1", "Giganotosaurus & Therizinosaurus Attack", "Jurassic World", 2022, 810, 100.0),
        ("75940-1", "Gallimimus and Pteranodon Breakout", "Jurassic World", 2020, 391, 60.0),
        ("75941-1", "Indominus Rex vs Ankylosaurus", "Jurassic World", 2020, 537, 70.0),
        ("76960-1", "Brachiosaurus Discovery", "Jurassic World", 2023, 512, 90.0),
        ("75938-1", "T. rex vs Dino-Mech Battle", "Jurassic World", 2019, 716, 80.0),

        # ── Indiana Jones (8 sets) ────────────────────────────────────────
        ("77015-1", "Temple of the Golden Idol", "Indiana Jones", 2023, 1545, 150.0),
        ("77013-1", "Escape from the Lost Tomb", "Indiana Jones", 2023, 600, 40.0),
        ("77012-1", "Fighter Plane Chase", "Indiana Jones", 2023, 387, 35.0),
        ("7621-1", "Indiana Jones and the Lost Tomb", "Indiana Jones", 2008, 263, 80.0),
        ("7627-1", "Temple of the Crystal Skull", "Indiana Jones", 2008, 929, 200.0),
        ("7623-1", "Temple Escape", "Indiana Jones", 2008, 554, 120.0),
        ("7199-1", "Temple of Doom", "Indiana Jones", 2009, 652, 200.0),
        ("77014-1", "Race for the Stolen Treasure", "Indiana Jones", 2023, 271, 30.0),

        # ── Minecraft (8 sets) ────────────────────────────────────────────
        ("21137-1", "The Mountain Cave", "Minecraft", 2017, 2863, 350.0),
        ("21155-1", "The Creeper Mine", "Minecraft", 2019, 834, 80.0),
        ("21244-1", "The Sword Outpost", "Minecraft", 2023, 427, 35.0),
        ("21246-1", "The Deep Dark Battle", "Minecraft", 2023, 584, 40.0),
        ("21189-1", "The Skeleton Dungeon", "Minecraft", 2022, 364, 30.0),
        ("21188-1", "The Llama Village", "Minecraft", 2022, 1252, 120.0),
        ("21187-1", "The Red Barn", "Minecraft", 2022, 799, 80.0),
        ("21185-1", "The Nether Bastion", "Minecraft", 2022, 300, 35.0),

        # ── Icons / Recent Large (10 sets) ────────────────────────────────
        ("10303-1", "Loop Coaster", "Icons", 2022, 3756, 400.0),
        ("10304-1", "Chevrolet Camaro Z28", "Icons", 2022, 1456, 170.0),
        ("10315-1", "Tranquil Garden", "Icons", 2023, 1363, 110.0),
        ("10281-2", "Bonsai Tree (Reissue)", "Botanical Collection", 2021, 878, 50.0),
        ("10320-1", "Eldorado Fortress (Reissue)", "Icons", 2023, 2509, 200.0),
        ("10326-1", "Natural History Museum", "Icons", 2023, 4014, 300.0),
        ("10319-1", "McLaren P1", "Technic", 2024, 3893, 450.0),
        ("42176-1", "Porsche GT4 e-Performance", "Technic", 2024, 834, 55.0),
        ("42177-1", "Mercedes-AMG F1 W14", "Technic", 2024, 1642, 200.0),
        ("10340-1", "LEGO Christmas Story", "Icons", 2024, 3078, 250.0),

        # ── LEGO Icons 2024-2025 ─────────────────────────────────────────
        ("10318-1", "Concorde", "Icons", 2023, 2083, 200.0),
        ("10298-1", "Vespa 125", "Icons", 2022, 1106, 100.0),
        ("10306-1", "Atari 2600", "Icons", 2023, 2532, 240.0),
        ("10341-1", "NASA Artemis Space Launch System", "Icons", 2024, 3601, 260.0),
        ("10331-1", "Kingfisher Bird", "Icons", 2024, 834, 50.0),
        ("10336-1", "Orient Express Train", "Icons", 2024, 2540, 300.0),
        ("10330-1", "McLaren MP4/4 & Ayrton Senna", "Icons", 2024, 693, 90.0),
        ("10327-1", "Dune Atreides Royal Ornithopter", "Icons", 2024, 1369, 165.0),

        # ── LEGO Art ─────────────────────────────────────────────────────
        ("31208-1", "Hokusai - The Great Wave", "Art", 2023, 1810, 100.0),
        ("31199-1", "Marvel Studios Iron Man", "Art", 2020, 3167, 120.0),
        ("31200-1", "Star Wars The Sith", "Art", 2020, 3395, 120.0),
        ("31197-1", "Andy Warhol's Marilyn Monroe", "Art", 2020, 3341, 120.0),
        ("31209-1", "The Amazing Spider-Man", "Art", 2023, 2099, 150.0),
        ("31210-1", "Modern Art", "Art", 2024, 805, 50.0),
        ("31213-1", "Mona Lisa", "Art", 2024, 1503, 80.0),

        # ── LEGO Ideas ───────────────────────────────────────────────────
        ("21326-1", "Winnie the Pooh", "Ideas", 2021, 1265, 100.0),
        ("21329-1", "Fender Stratocaster", "Ideas", 2021, 1074, 100.0),
        ("21345-1", "Polaroid OneStep SX-70 Camera", "Ideas", 2024, 516, 80.0),
        ("21333-1", "Vincent van Gogh - The Starry Night", "Ideas", 2022, 2316, 170.0),
        ("21344-1", "Orient Express", "Ideas", 2023, 2540, 300.0),
        ("21343-1", "Viking Village", "Ideas", 2024, 2103, 130.0),
        ("21342-1", "The Insect Collection", "Ideas", 2024, 1111, 80.0),
        ("21340-1", "Tales of the Space Age", "Ideas", 2023, 688, 50.0),
        ("21339-1", "BTS Dynamite", "Ideas", 2023, 749, 100.0),
        ("21338-1", "A-Frame Cabin", "Ideas", 2023, 2082, 180.0),

        # ── LEGO Speed Champions ─────────────────────────────────────────
        ("76915-1", "Pagani Utopia", "Speed Champions", 2023, 249, 25.0),
        ("76918-1", "McLaren Solus GT & McLaren F1 LM", "Speed Champions", 2023, 581, 45.0),
        ("76916-1", "Porsche 963", "Speed Champions", 2023, 280, 25.0),
        ("76917-1", "2 Fast 2 Furious Nissan Skyline GT-R R34", "Speed Champions", 2023, 319, 25.0),
        ("76919-1", "McLaren F1 Race Car 2023", "Speed Champions", 2024, 245, 25.0),
        ("76920-1", "Ford Mustang Dark Horse", "Speed Champions", 2024, 344, 25.0),
        ("76921-1", "Audi S1 e-tron quattro", "Speed Champions", 2024, 274, 25.0),
        ("76914-1", "Ferrari 812 Competizione", "Speed Champions", 2023, 261, 25.0),
        ("76912-1", "Fast & Furious 1970 Dodge Charger R/T", "Speed Champions", 2023, 345, 25.0),
        ("42143-1", "Ferrari Daytona SP3", "Technic", 2022, 3778, 400.0),

        # ── LEGO Architecture ────────────────────────────────────────────
        ("21056-1", "Taj Mahal", "Architecture", 2021, 2022, 120.0),
        ("21058-1", "Great Pyramid of Giza", "Architecture", 2022, 1476, 130.0),
        ("21060-1", "Himeji Castle", "Architecture", 2024, 2125, 140.0),
        ("21057-1", "Singapore", "Architecture", 2022, 827, 60.0),
        ("21034-1", "London", "Architecture", 2017, 468, 40.0),
        ("21044-1", "Paris", "Architecture", 2019, 649, 50.0),
    ]


def get_curated_catalog() -> list[dict]:
    """Return the full curated LEGO catalog as a list of dicts.

    Each dict has keys: set_number, name, theme, year, parts, price_eur.
    Used by catalog_crawler and model_retrain workers.
    """
    catalog: list[dict] = []
    for set_num, name, theme, year, parts, price_eur in _seed_sets():
        catalog.append({
            "set_number": set_num,
            "name": name,
            "theme": theme,
            "year": year,
            "parts": parts,
            "price_eur": price_eur,
        })
    return catalog


def _run_curated_seed(dry_run: bool):
    """Fallback: seed 500+ popular/collectible LEGO sets manually.

    Covers UCS Star Wars, Modular Buildings, Ideas/CUUSOO, Technic flagships,
    Creator Expert/Icons, Harry Potter, Lord of the Rings, Marvel/DC,
    Speed Champions, Architecture, City, Ninjago, Friends, Elves, BrickHeadz,
    Seasonal/Winter Village, Chinese New Year, Botanical Collection, Art/Mosaic,
    Bionicle, Mindstorms, Duplo, Classic Space/Castle/Town, Adventurers,
    Rock Raiders, Aquanauts, Disney, Super Mario, Jurassic World, Indiana Jones,
    Minecraft, vintage/retired themes, GWP/promotional sets, and CMF.

    Format: (set_num, name, theme, year, parts, price_eur)
    Prices are approximate secondary-market EUR values (2026).
    """
    seed_sets = _seed_sets()

    items = []
    observations = []
    for set_num, name, theme, year, parts, price_eur in seed_sets:
        rarity_label, rarity_val = _curated_rarity(year, parts, theme)
        items.append(CatalogItem(
            category=CATEGORY,
            item_key=slugify(f"{set_num}-{name}"),
            title=f"LEGO {name}",
            set_code=set_num,
            brand="LEGO",
            rarity=rarity_label,
            notes=f"Set {set_num} | {theme} | {year} | {parts} pcs",
            attributes_json={"set_number": set_num, "theme": theme, "year": str(year), "num_parts": parts},
        ))
        observations.append(PriceObservation(
            features={"condition_score": 0.9, "rarity_score": rarity_val, "edition_score": 0.5,
                       "piece_count": parts, "year": year, "sealed": 1.0},
            price=price_eur,
        ))

    write_catalog_sql(CATEGORY, items)
    write_training_jsonl(CATEGORY, observations)

    ingest = SupabaseIngest()
    if dry_run:
        ingest.enabled = False
    if ingest.enabled:
        ingest.upsert_catalog(items)
    ingest.close()

    logger.info(f"  Seeded {len(items)} curated LEGO sets")


if __name__ == "__main__":
    main()
