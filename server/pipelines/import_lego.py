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


def _run_curated_seed(dry_run: bool):
    """Fallback: seed popular retired sets manually."""
    seed_sets = [
        ("10179-1", "Millennium Falcon UCS", "Star Wars", 2007, 5195, 3500.0),
        ("10188-1", "Death Star", "Star Wars", 2008, 3803, 800.0),
        ("10210-1", "Imperial Flagship", "Pirates", 2010, 1664, 600.0),
        ("10196-1", "Grand Carousel", "Creator Expert", 2009, 3263, 1200.0),
        ("10190-1", "Market Street", "Modular Buildings", 2007, 1248, 900.0),
        ("10182-1", "Cafe Corner", "Modular Buildings", 2007, 2056, 2500.0),
        ("10185-1", "Green Grocer", "Modular Buildings", 2008, 2352, 1500.0),
        ("10224-1", "Town Hall", "Modular Buildings", 2012, 2766, 600.0),
        ("21322-1", "Pirates of Barracuda Bay", "Ideas", 2020, 2545, 350.0),
        ("75192-1", "Millennium Falcon", "Star Wars", 2017, 7541, 850.0),
        ("10294-1", "Titanic", "Creator Expert", 2021, 9090, 680.0),
        ("71043-1", "Hogwarts Castle", "Harry Potter", 2018, 6020, 500.0),
        ("10276-1", "Colosseum", "Creator Expert", 2020, 9036, 550.0),
        ("42115-1", "Lamborghini Sian", "Technic", 2020, 3696, 380.0),
        ("42143-1", "Ferrari Daytona SP3", "Technic", 2022, 3778, 400.0),
    ]

    items = []
    observations = []
    for set_num, name, theme, year, parts, price_eur in seed_sets:
        items.append(CatalogItem(
            category=CATEGORY,
            item_key=slugify(f"{set_num}-{name}"),
            title=f"LEGO {name}",
            set_code=set_num,
            brand="LEGO",
            rarity="Retired Premium",
            notes=f"Set {set_num} | {theme} | {year} | {parts} pcs",
            attributes_json={"set_number": set_num, "theme": theme, "year": str(year), "num_parts": parts},
        ))
        observations.append(PriceObservation(
            features={"condition_score": 0.9, "rarity_score": 0.8, "edition_score": 0.5,
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
