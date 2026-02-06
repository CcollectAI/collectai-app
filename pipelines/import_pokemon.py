"""
Import Pokemon TCG data from pokemontcg.io API.

Layer 1 (Catalog):  All cards from all sets → category_items
Layer 2 (Prices):   TCGPlayer market prices → train.jsonl + market_hits
Layer 3 (Feedback): Enabled via existing feedback tables

API: https://docs.pokemontcg.io/
Rate limit: 20,000 requests/day (with API key), 1,000 without
No API key required for basic usage.

Usage:
    python -m pipelines.import_pokemon [--limit-sets 5] [--dry-run]
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
)

API_BASE = "https://api.pokemontcg.io/v2"
CATEGORY = "pokemon"


def fetch_sets(limit: int | None = None) -> list[dict]:
    """Fetch all Pokemon TCG sets."""
    sets = []
    page = 1
    while True:
        data = fetch_json(f"{API_BASE}/sets", params={
            "page": page,
            "pageSize": 250,
            "orderBy": "-releaseDate",
        })
        sets.extend(data.get("data", []))
        if len(sets) >= data.get("totalCount", 0):
            break
        page += 1
        time.sleep(0.5)
    if limit:
        sets = sets[:limit]
    log_progress(CATEGORY, "sets fetched", len(sets))
    return sets


def fetch_cards_for_set(set_id: str) -> list[dict]:
    """Fetch all cards in a set."""
    cards = []
    page = 1
    while True:
        data = fetch_json(f"{API_BASE}/cards", params={
            "q": f"set.id:{set_id}",
            "page": page,
            "pageSize": 250,
        })
        cards.extend(data.get("data", []))
        if len(cards) >= data.get("totalCount", 0):
            break
        page += 1
        time.sleep(0.3)
    return cards


def card_to_catalog_item(card: dict, set_name: str) -> CatalogItem:
    """Convert API card to CatalogItem."""
    number = card.get("number", "")
    set_total = card.get("set", {}).get("printedTotal", "")
    number_display = f"{number}/{set_total}" if set_total else number

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{card.get('set', {}).get('id', '')}-{card.get('id', '')}"),
        title=card.get("name", ""),
        set_code=card.get("set", {}).get("id", ""),
        brand="Pokemon TCG",
        rarity=card.get("rarity", "") or "",
        notes=f"{set_name} #{number_display}",
        image_url=card.get("images", {}).get("small", ""),
        attributes_json={
            "set": set_name,
            "number": number_display,
            "rarity": card.get("rarity", ""),
            "supertype": card.get("supertype", ""),
            "subtypes": card.get("subtypes", []),
            "artist": card.get("artist", ""),
        },
    )


def card_to_price_observations(card: dict) -> list[PriceObservation]:
    """Extract price observations from TCGPlayer data embedded in card."""
    observations = []
    tcgplayer = card.get("tcgplayer", {})
    if not tcgplayer:
        return observations

    prices = tcgplayer.get("prices", {})
    rarity = card.get("rarity", "") or "Common"

    rarity_score_map = {
        "Common": 0.1, "Uncommon": 0.3, "Rare": 0.5,
        "Rare Holo": 0.65, "Rare Holo EX": 0.7, "Rare Ultra": 0.8,
        "Rare Secret": 0.9, "Rare Holo V": 0.7, "Rare Holo VMAX": 0.75,
        "Rare Holo VSTAR": 0.75, "Amazing Rare": 0.8,
        "Illustration Rare": 0.85, "Special Art Rare": 0.9,
        "Hyper Rare": 0.95, "Rare Shiny": 0.8,
        "LEGEND": 0.85, "Promo": 0.4,
    }
    rarity_score = rarity_score_map.get(rarity, 0.5)

    for variant, price_data in prices.items():
        market_price = price_data.get("market")
        if not market_price or market_price <= 0:
            continue

        is_foil = "holofoil" in variant.lower() or "reverseHolofoil" in variant.lower()
        condition_score = 0.9  # TCGPlayer market = NM average

        eur_price = to_eur(market_price, "USD")
        observations.append(PriceObservation(
            features={
                "condition_score": condition_score,
                "rarity_score": rarity_score,
                "edition_score": 0.7 if is_foil else 0.5,
                "is_foil": 1.0 if is_foil else 0.0,
                "variant": variant,
            },
            price=eur_price,
        ))
    return observations


def card_to_market_hits(card: dict) -> list[MarketHit]:
    """Convert card price data to market hits."""
    hits = []
    tcgplayer = card.get("tcgplayer", {})
    if not tcgplayer:
        return hits

    prices = tcgplayer.get("prices", {})
    updated = tcgplayer.get("updatedAt", "")

    for variant, price_data in prices.items():
        market_price = price_data.get("market")
        if not market_price or market_price <= 0:
            continue

        hits.append(MarketHit(
            provider="tcgplayer",
            listing_id=f"{card.get('id', '')}-{variant}",
            title=f"{card.get('name', '')} ({variant})",
            price=to_eur(market_price, "USD"),
            currency="EUR",
            condition="NM",
            normalized_key=slugify(f"{card.get('set', {}).get('id', '')}-{card.get('id', '')}"),
            category=CATEGORY,
            sold_at=updated,
        ))
    return hits


def main():
    parser = argparse.ArgumentParser(description="Import Pokemon TCG catalog + prices")
    parser.add_argument("--limit-sets", type=int, default=None,
                        help="Limit number of sets to import (for testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only write local files, skip Supabase")
    args = parser.parse_args()

    print(f"=== Pokemon TCG Import ===")
    print(f"Limit sets: {args.limit_sets or 'ALL'}")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    # Fetch all sets
    sets = fetch_sets(limit=args.limit_sets)

    all_items: list[CatalogItem] = []
    all_observations: list[PriceObservation] = []
    all_hits: list[MarketHit] = []

    for i, s in enumerate(sets):
        set_id = s.get("id", "")
        set_name = s.get("name", "")
        log_progress(CATEGORY, f"set {i+1}/{len(sets)}", i + 1, len(sets))

        cards = fetch_cards_for_set(set_id)
        log_progress(CATEGORY, f"  cards in {set_id}", len(cards))

        for card in cards:
            all_items.append(card_to_catalog_item(card, set_name))
            all_observations.extend(card_to_price_observations(card))
            all_hits.extend(card_to_market_hits(card))

        time.sleep(0.5)  # rate limit courtesy

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

    print(f"\n=== Pokemon Import Complete ===")
    print(f"  Catalog items:     {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")
    print(f"  Market hits:       {len(all_hits)}")


if __name__ == "__main__":
    main()
