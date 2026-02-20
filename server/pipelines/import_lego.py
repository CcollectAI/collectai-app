"""
Import LEGO set data from Rebrickable API.

Layer 1 (Catalog):  All sets → category_items
Layer 2 (Prices):   Retail prices + estimated market values → train.jsonl

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
    """Fetch all LEGO themes → {theme_id: theme_name}."""
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


def _run_curated_seed(dry_run: bool):
    """Fallback: seed 120+ popular/collectible LEGO sets manually.

    Covers UCS Star Wars, Modular Buildings, Ideas/CUUSOO, Technic flagships,
    Creator Expert/Icons, Harry Potter, vintage/retired themes, GWP/promotional
    sets, and Collectible Minifigures (CMF).

    Format: (set_num, name, theme, year, parts, price_eur)
    Prices are approximate secondary-market EUR values (2026).
    """
    seed_sets = [
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
    ]

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
