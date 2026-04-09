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
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem, PriceObservation, MarketHit, SupabaseIngest,
    write_training_jsonl, write_catalog_sql, fetch_json,
    log_progress, slugify, to_eur, close_http_client,
    rarity_score as shared_rarity_score,
    RARITY_SCORE_MAP,
    logger,
)

API_BASE = "https://api.pokemontcg.io/v2"
CATEGORY = "pokemon"
API_KEY = os.getenv("POKEMONTCG_API_KEY", "")
_HEADERS = {"X-Api-Key": API_KEY} if API_KEY else {}


def fetch_sets(limit: int | None = None) -> list[dict]:
    """Fetch all Pokemon TCG sets."""
    sets = []
    page = 1
    max_pages = 100  # safety guard against infinite pagination
    while page <= max_pages:
        data = fetch_json(f"{API_BASE}/sets", headers=_HEADERS, params={
            "page": page,
            "pageSize": 250,
            "orderBy": "-releaseDate",
        })
        page_data = data.get("data", [])
        if not page_data:
            break
        sets.extend(page_data)
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
    max_pages = 200  # safety guard against infinite pagination
    while page <= max_pages:
        data = fetch_json(f"{API_BASE}/cards", headers=_HEADERS, params={
            "q": f"set.id:{set_id}",
            "page": page,
            "pageSize": 250,
        })
        page_data = data.get("data", [])
        if not page_data:
            break
        cards.extend(page_data)
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
    """Extract price observations from TCGPlayer + Cardmarket data embedded in card."""
    observations = []
    rarity = card.get("rarity", "") or "Common"
    rarity_sc = shared_rarity_score(rarity)

    # TCGPlayer prices (USD → EUR)
    tcgplayer = card.get("tcgplayer", {})
    if tcgplayer:
        prices = tcgplayer.get("prices", {})
        for variant, price_data in prices.items():
            market_price = price_data.get("market")
            if not market_price or market_price <= 0:
                continue

            is_foil = "holofoil" in variant.lower() or "reverseholofoil" in variant.lower()
            eur_price = to_eur(market_price, "USD")
            observations.append(PriceObservation(
                features={
                    "condition_score": 0.9,  # TCGPlayer market = NM average
                    "rarity_score": rarity_sc,
                    "edition_score": 0.7 if is_foil else 0.5,
                    "is_foil": 1.0 if is_foil else 0.0,
                    "variant": variant,
                },
                price=eur_price,
            ))

    # Cardmarket prices (already EUR)
    cardmarket = card.get("cardmarket", {})
    if cardmarket:
        cm_prices = cardmarket.get("prices", {})
        avg_price = cm_prices.get("averageSellPrice") or cm_prices.get("avg30")
        if avg_price:
            try:
                price_eur = float(avg_price)
                if price_eur > 0:
                    observations.append(PriceObservation(
                        features={
                            "condition_score": 0.85,
                            "rarity_score": rarity_sc,
                            "edition_score": 0.5,
                            "is_foil": 0.0,
                            "variant": "cardmarket",
                        },
                        price=price_eur,
                    ))
            except (ValueError, TypeError):
                pass

    return observations


def card_to_market_hits(card: dict) -> list[MarketHit]:
    """Convert card price data to market hits (TCGPlayer + Cardmarket)."""
    hits = []
    nkey = slugify(f"{card.get('set', {}).get('id', '')}-{card.get('id', '')}")

    # TCGPlayer prices
    tcgplayer = card.get("tcgplayer", {})
    if tcgplayer:
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
                normalized_key=nkey,
                category=CATEGORY,
                sold_at=updated,
            ))

    # Cardmarket prices
    cardmarket = card.get("cardmarket", {})
    if cardmarket:
        cm_prices = cardmarket.get("prices", {})
        avg_price = cm_prices.get("averageSellPrice") or cm_prices.get("avg30")
        if avg_price:
            try:
                price_eur = float(avg_price)
                if price_eur > 0:
                    hits.append(MarketHit(
                        provider="cardmarket",
                        listing_id=f"{card.get('id', '')}-cm",
                        title=f"{card.get('name', '')} (Cardmarket)",
                        price=price_eur,
                        currency="EUR",
                        condition="NM",
                        normalized_key=nkey,
                        category=CATEGORY,
                        sold_at=cardmarket.get("updatedAt", ""),
                    ))
            except (ValueError, TypeError):
                pass

    return hits


def set_to_collection_row(tcg_set: dict) -> dict:
    """Convert a pokemontcg.io set to a collections table row for set tracking."""
    images = tcg_set.get("images", {})
    return {
        "category": CATEGORY,
        "collection_key": tcg_set.get("id", ""),
        "display_name": tcg_set.get("name", ""),
        "release_date": tcg_set.get("releaseDate"),
        "total_items": tcg_set.get("total", tcg_set.get("printedTotal", 0)),
        "image_url": images.get("logo", images.get("symbol", "")),
        "notes": f"{tcg_set.get('series', '')} series",
    }


def main():
    parser = argparse.ArgumentParser(description="Import Pokemon TCG catalog + prices")
    parser.add_argument("--limit-sets", type=int, default=None,
                        help="Limit number of sets to import (for testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only write local files, skip Supabase")
    args = parser.parse_args()

    logger.info(f"=== Pokemon TCG Import ===")
    logger.info(f"Limit sets: {args.limit_sets or 'ALL'}")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    # Fetch all sets
    sets = fetch_sets(limit=args.limit_sets)

    all_items: list[CatalogItem] = []
    all_observations: list[PriceObservation] = []
    all_hits: list[MarketHit] = []

    failed_sets = []
    for i, s in enumerate(sets):
        set_id = s.get("id", "")
        set_name = s.get("name", "")
        log_progress(CATEGORY, f"set {i+1}/{len(sets)}", i + 1, len(sets))

        try:
            cards = fetch_cards_for_set(set_id)
            log_progress(CATEGORY, f"  cards in {set_id}", len(cards))

            for card in cards:
                all_items.append(card_to_catalog_item(card, set_name))
                all_observations.extend(card_to_price_observations(card))
                all_hits.extend(card_to_market_hits(card))
        except Exception as e:
            logger.error(f"Failed to import set {set_id} ({set_name}): {e}")
            failed_sets.append(set_id)

        time.sleep(0.5)  # rate limit courtesy

    if failed_sets:
        logger.warning(f"Failed sets ({len(failed_sets)}): {', '.join(failed_sets)}")

    # In-memory dedup on item_key (the DB unique constraint catches dupes too,
    # but only after wasting a network roundtrip per duplicate batch row).
    # The pokemontcg.io API occasionally returns the same card under two
    # set entries (e.g. ex10/ex10 promo). This collapses them in O(n).
    # See R47 task #65 / catalog_dedup_check.py limitation note.
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
    close_http_client()

    logger.info(f"=== Pokemon Import Complete ===")
    logger.info(f"  Catalog items:     {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")
    logger.info(f"  Market hits:       {len(all_hits)}")


if __name__ == "__main__":
    main()
