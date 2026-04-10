"""
Import Magic: The Gathering data from Scryfall API.

Layer 1 (Catalog):  All cards → category_items
Layer 2 (Prices):   Scryfall price data (USD/EUR, paper/foil) → train.jsonl + market_hits

API: https://scryfall.com/docs/api
Rate limit: 10 requests/second, no API key needed.
Bulk data available at: https://api.scryfall.com/bulk-data

Usage:
    python -m pipelines.import_mtg [--use-bulk] [--limit 5000] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
import time
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

API_BASE = "https://api.scryfall.com"
CATEGORY = "mtg"


def fetch_bulk_cards() -> list[dict]:
    """Fetch all cards via Scryfall bulk data endpoint."""
    logger.info("Fetching bulk data manifest...")
    bulk_info = fetch_json(f"{API_BASE}/bulk-data")
    # Find the "default_cards" bulk file (smaller, no variations)
    default_cards_url = None
    for item in bulk_info.get("data", []):
        if item.get("type") == "default_cards":
            default_cards_url = item.get("download_uri")
            break

    if not default_cards_url:
        logger.info("ERROR: Could not find default_cards bulk data URL")
        return []

    logger.info(f"Downloading bulk data from: {default_cards_url}")
    import httpx
    client = httpx.Client(timeout=120.0)
    resp = client.get(default_cards_url)
    resp.raise_for_status()
    cards = resp.json()
    client.close()
    log_progress(CATEGORY, "bulk cards fetched", len(cards))
    return cards


def fetch_cards_paginated(limit: int | None = None) -> list[dict]:
    """Fetch cards via paginated search (slower, for testing)."""
    cards = []
    url = f"{API_BASE}/cards/search"
    params = {"q": "game:paper", "order": "released", "dir": "desc"}
    page_count = 0

    while url:
        data = fetch_json(url, params=params if page_count == 0 else None)
        cards.extend(data.get("data", []))
        page_count += 1
        log_progress(CATEGORY, f"page {page_count}", len(cards))

        if limit and len(cards) >= limit:
            cards = cards[:limit]
            break

        if data.get("has_more"):
            url = data.get("next_page")
            time.sleep(0.1)  # rate limit
        else:
            break

    return cards


def card_to_catalog_item(card: dict) -> CatalogItem:
    set_code = card.get("set", "")
    collector_no = card.get("collector_number", "")
    name = card.get("name", "")
    set_name = card.get("set_name", "")
    rarity = card.get("rarity", "") or ""

    image_url = ""
    image_uris = card.get("image_uris", {})
    if image_uris:
        image_url = image_uris.get("small", image_uris.get("normal", ""))

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{set_code}-{collector_no}-{name}"),
        title=name,
        set_code=set_code,
        brand="Magic: The Gathering",
        rarity=rarity,
        notes=f"{set_name} #{collector_no}",
        image_url=image_url,
        attributes_json={
            "set": set_name,
            "collector_no": collector_no,
            "rarity": rarity,
            "type_line": card.get("type_line", ""),
            "mana_cost": card.get("mana_cost", ""),
            "colors": card.get("colors", []),
            "foil": card.get("foil", False),
            "nonfoil": card.get("nonfoil", True),
            "reserved": card.get("reserved", False),
        },
    )


def card_to_price_observations(card: dict) -> list[PriceObservation]:
    observations = []
    prices = card.get("prices", {})
    rarity = card.get("rarity", "common")
    rarity_score = shared_rarity_score(rarity)
    is_reserved = card.get("reserved", False)

    for price_key in ["eur", "eur_foil"]:
        price_val = prices.get(price_key)
        if not price_val:
            continue
        try:
            price_float = float(price_val)
        except (ValueError, TypeError):
            continue
        if price_float <= 0:
            continue

        is_foil = "foil" in price_key
        observations.append(PriceObservation(
            features={
                "condition_score": 0.9,  # Scryfall = NM market average
                "rarity_score": rarity_score,
                "edition_score": 0.9 if is_reserved else 0.5,
                "is_foil": 1.0 if is_foil else 0.0,
                "is_reserved_list": 1.0 if is_reserved else 0.0,
            },
            price=price_float,
        ))
    return observations


def card_to_market_hits(card: dict) -> list[MarketHit]:
    hits = []
    prices = card.get("prices", {})
    name = card.get("name", "")
    set_code = card.get("set", "")
    collector_no = card.get("collector_number", "")

    for price_key in ["eur", "eur_foil"]:
        price_val = prices.get(price_key)
        if not price_val:
            continue
        try:
            price_float = float(price_val)
        except (ValueError, TypeError):
            continue
        if price_float <= 0:
            continue

        variant = "foil" if "foil" in price_key else "nonfoil"
        hits.append(MarketHit(
            provider="scryfall",
            listing_id=f"{card.get('id', '')}-{variant}",
            title=f"{name} ({variant})",
            price=price_float,
            currency="EUR",
            condition="NM",
            normalized_key=slugify(f"{set_code}-{collector_no}-{name}"),
            category=CATEGORY,
        ))
    return hits


def main():
    parser = argparse.ArgumentParser(description="Import MTG catalog + prices from Scryfall")
    parser.add_argument("--use-bulk", action="store_true",
                        help="Use bulk data download (faster, gets ALL cards)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of cards (paginated mode only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only write local files, skip Supabase")
    args = parser.parse_args()

    logger.info(f"=== MTG Import (Scryfall) ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    if args.use_bulk:
        cards = fetch_bulk_cards()
    else:
        cards = fetch_cards_paginated(limit=args.limit)

    # Filter to paper cards only
    cards = [c for c in cards if "paper" in c.get("games", [])]
    log_progress(CATEGORY, "paper cards", len(cards))

    all_items: list[CatalogItem] = []
    all_observations: list[PriceObservation] = []
    all_hits: list[MarketHit] = []

    for i, card in enumerate(cards):
        all_items.append(card_to_catalog_item(card))
        all_observations.extend(card_to_price_observations(card))
        all_hits.extend(card_to_market_hits(card))

        if (i + 1) % 5000 == 0:
            log_progress(CATEGORY, "processing", i + 1, len(cards))

    # R47 — In-memory dedup on item_key. Scryfall occasionally returns the
    # same card under multiple set entries (basic lands, art variants), and
    # the DB unique constraint catches dupes only after wasting a network
    # roundtrip per duplicate batch row. Same pattern as import_pokemon.py.
    seen_keys: set[str] = set()
    deduped_items: list[CatalogItem] = []
    dropped_dupe_count = 0
    for item in all_items:
        if item.item_key in seen_keys:
            dropped_dupe_count += 1
            continue
        seen_keys.add(item.item_key)
        deduped_items.append(item)
    if dropped_dupe_count:
        logger.info(
            "[%s] in-memory dedup: dropped %d duplicate item_keys (kept %d)",
            CATEGORY, dropped_dupe_count, len(deduped_items),
        )
    all_items = deduped_items

    # Write local files
    sql_path = write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    if all_observations:
        jsonl_path = write_training_jsonl(CATEGORY, all_observations)
        log_progress(CATEGORY, "training JSONL written", len(all_observations))

    # Upsert to Supabase
    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)
        if all_hits:
            hits_inserted = ingest.upsert_market_hits(all_hits)
            log_progress(CATEGORY, "market_hits upserted", hits_inserted)

    ingest.close()

    logger.info(f"\n=== MTG Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")
    logger.info(f"  Market hits:        {len(all_hits)}")


if __name__ == "__main__":
    main()
