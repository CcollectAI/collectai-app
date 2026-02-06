"""
Import Yu-Gi-Oh card data from YGOProDeck API.

Layer 1 (Catalog):  All cards → category_items
Layer 2 (Prices):   TCGPlayer/Cardmarket prices from API → train.jsonl + market_hits

API: https://ygoprodeck.com/api-guide/
Rate limit: 20 requests/second, no API key needed.
Endpoint: https://db.ygoprodeck.com/api/v7/cardinfo.php (returns ALL cards at once)

Usage:
    python -m pipelines.import_yugioh [--dry-run]
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
)

API_BASE = "https://db.ygoprodeck.com/api/v7"
CATEGORY = "yugioh"


def fetch_all_cards() -> list[dict]:
    """Fetch entire Yu-Gi-Oh card database (single request)."""
    print("Fetching all Yu-Gi-Oh cards (single API call)...")
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

    rarity_score_map = {
        "Common": 0.1, "Rare": 0.4, "Super Rare": 0.55,
        "Ultra Rare": 0.7, "Secret Rare": 0.8,
        "Ultimate Rare": 0.85, "Ghost Rare": 0.9,
        "Starlight Rare": 0.95, "Collector's Rare": 0.85,
        "Prismatic Secret Rare": 0.9, "Quarter Century Secret Rare": 0.95,
        "Short Print": 0.6,
    }

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


def main():
    parser = argparse.ArgumentParser(description="Import Yu-Gi-Oh catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Yu-Gi-Oh Import (YGOProDeck) ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    cards = fetch_all_cards()

    all_items: list[CatalogItem] = []
    all_observations: list[PriceObservation] = []
    all_hits: list[MarketHit] = []

    for i, card in enumerate(cards):
        all_items.extend(card_to_catalog_items(card))
        all_observations.extend(card_to_price_observations(card))
        all_hits.extend(card_to_market_hits(card))

        if (i + 1) % 2000 == 0:
            log_progress(CATEGORY, "processing", i + 1, len(cards))

    # Deduplicate by item_key
    seen = set()
    deduped = []
    for item in all_items:
        if item.item_key not in seen:
            seen.add(item.item_key)
            deduped.append(item)
    all_items = deduped

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

    print(f"\n=== Yu-Gi-Oh Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")
    print(f"  Market hits:        {len(all_hits)}")


if __name__ == "__main__":
    main()
