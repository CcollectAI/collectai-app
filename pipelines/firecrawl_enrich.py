"""
Firecrawl Catalog Enrichment Pipeline for CollectAI.

Batch pipeline that uses Firecrawl to scrape Tier 2 catalog sites and populate
category_items + training.jsonl for categories without dedicated APIs.

Targets:
  - Scalemates.com (scale_models)
  - MyFigureCollection.net (anime_figures)
  - HobbySearch JP (gunpla)
  - VGMdb (anime_soundtrack, anime_ost_vinyl)
  - Ktown4u / Weverse (kpop_merch — BTS, Stray Kids, etc.)
  - StockX / Mercari (taylor_swift — Eras Tour merch, signed vinyl, etc.)
  - BrickLink (lego — additional sets)
  - 130point / COMC (sportscards)

Usage:
    python -m pipelines.firecrawl_enrich [options]

Options:
    --dry-run          Parse and display without DB writes
    --category CAT     Only enrich a specific category
    --limit N          Max items per site (default: 50)
    --verbose          Extra logging
    --output FILE      Write enriched items to JSON file
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from pipelines.import_common import (
    CatalogItem,
    IngestStats,
    PriceObservation,
    SupabaseIngest,
    close_http_client,
    log_progress,
    setup_logging,
    slugify,
    to_eur,
    write_training_jsonl,
)

logger = setup_logging("collectai.firecrawl_enrich")

# ---------------------------------------------------------------------------
# Site-specific enrichment configs
# ---------------------------------------------------------------------------

ENRICHMENT_TARGETS: dict[str, dict[str, Any]] = {
    "scale_models": {
        "site": "scalemates.com",
        "search_queries": [
            "1/48 aircraft model kit",
            "1/35 tank model kit",
            "1/72 military model kit",
            "Tamiya model kit new release",
            "Hasegawa limited edition kit",
        ],
        "brand": "Various",
    },
    "anime_figures": {
        "site": "myfigurecollection.net",
        "search_queries": [
            "nendoroid new release price",
            "scale figure preorder 2026",
            "figma new release",
            "pop up parade figure",
            "prize figure ichiban kuji",
        ],
        "brand": "Various",
    },
    "gunpla": {
        "site": "hlj.com",
        "search_queries": [
            "master grade gunpla new release",
            "perfect grade gundam kit",
            "real grade RG gundam",
            "p-bandai exclusive gunpla",
            "HG gundam kit 2026",
        ],
        "brand": "Bandai",
    },
    "anime_soundtrack": {
        "site": "vgmdb.net",
        "search_queries": [
            "anime soundtrack CD new release 2026",
            "anime OST limited edition",
            "anime soundtrack vinyl release",
            "vgmdb anime album",
        ],
        "brand": "Various",
    },
    "anime_ost_vinyl": {
        "site": "vgmdb.net",
        "search_queries": [
            "anime vinyl record release",
            "anime OST vinyl pressing",
            "game soundtrack vinyl",
            "Studio Ghibli vinyl",
        ],
        "brand": "Various",
    },
    "kpop_merch": {
        "site": "ktown4u.com",
        "search_queries": [
            "BTS official merchandise new",
            "BTS album photocard",
            "Stray Kids merch 2026",
            "SEVENTEEN official goods",
            "Blackpink merchandise price",
            "TWICE official merch",
            "BTS army bomb lightstick",
            "weverse shop BTS exclusive",
            "kpop signed album price",
        ],
        "brand": "Various",
    },
    "taylor_swift": {
        "site": "mercari.com",
        "search_queries": [
            "Taylor Swift Eras Tour merchandise price",
            "Taylor Swift signed vinyl sold",
            "Taylor Swift exclusive merch value",
            "Eras Tour poster limited edition",
            "Taylor Swift CD signed price",
            "Taylor Swift cardigan merch",
            "swiftie collectible rare",
        ],
        "brand": "Taylor Swift",
    },
    "lego": {
        "site": "bricklink.com",
        "search_queries": [
            "LEGO retired set value 2026",
            "LEGO exclusive set price",
            "LEGO modular building sealed",
            "LEGO Star Wars UCS price",
        ],
        "brand": "LEGO",
    },
    "sportscards": {
        "site": "130point.com",
        "search_queries": [
            "sports card Prizm sold price",
            "Topps Chrome rookie card value",
            "Panini basketball card sold",
            "sports card PSA 10 price",
        ],
        "brand": "Various",
    },
    "keycaps": {
        "site": "reddit.com/r/mechmarket",
        "search_queries": [
            "artisan keycap price",
            "GMK keycap set sold",
            "mechanical keyboard keycap aftermarket",
        ],
        "brand": "Various",
    },
    "kpop_lightsticks": {
        "site": "ktown4u.com",
        "search_queries": [
            "kpop lightstick official price",
            "BTS army bomb price",
            "Stray Kids lightstick",
            "TWICE candybong price",
        ],
        "brand": "Various",
    },
}

# Extraction schema for catalog items
CATALOG_EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "price": {"type": "number"},
        "currency": {"type": "string"},
        "brand": {"type": "string"},
        "rarity": {"type": "string"},
        "condition": {"type": "string"},
        "image_url": {"type": "string"},
        "release_date": {"type": "string"},
        "description": {"type": "string"},
    },
}


# ---------------------------------------------------------------------------
# Price extraction from markdown
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(
    r"(?:[\$€£¥]|USD|EUR|GBP|JPY)\s*(\d[\d,]*\.?\d*)"
    r"|(\d[\d,]*\.?\d*)\s*(?:USD|EUR|GBP|JPY|yen)",
    re.IGNORECASE,
)


def _extract_price_from_text(text: str) -> tuple[Optional[float], str]:
    """Extract a price from text. Returns (price, currency)."""
    if not text:
        return None, "EUR"

    m = _PRICE_RE.search(text)
    if not m:
        return None, "EUR"

    raw = (m.group(1) or m.group(2) or "").replace(",", "")
    try:
        price = float(raw)
    except ValueError:
        return None, "EUR"

    full = m.group(0)
    if "$" in full or "USD" in full.upper():
        return price, "USD"
    if "€" in full or "EUR" in full.upper():
        return price, "EUR"
    if "£" in full or "GBP" in full.upper():
        return price, "GBP"
    if "¥" in full or "￥" in full or "JPY" in full.upper() or "yen" in full.lower():
        return price, "JPY"

    return price, "USD"


# ---------------------------------------------------------------------------
# Enrichment logic
# ---------------------------------------------------------------------------

async def _enrich_category(
    category: str,
    config: dict[str, Any],
    limit: int,
    stats: IngestStats,
) -> list[CatalogItem]:
    """Run enrichment for a single category using Firecrawl search."""
    from app.lib.firecrawl_client import search_web, configured

    if not configured():
        logger.warning("Firecrawl not configured — skipping %s", category)
        return []

    items: list[CatalogItem] = []
    seen_keys: set[str] = set()
    site = config["site"]
    brand = config.get("brand", "Various")

    for query in config["search_queries"]:
        if len(items) >= limit:
            break

        search_query = f"{query} site:{site}"
        try:
            results = await search_web(search_query, limit=5)
        except Exception as e:
            logger.error("Search failed for '%s': %s", search_query, e)
            stats.transform_errors += 1
            continue

        for result in results:
            if len(items) >= limit:
                break

            title = result.get("title") or result.get("metadata", {}).get("title", "")
            if not title:
                continue

            item_key = slugify(title)
            if not item_key or item_key in seen_keys:
                continue
            seen_keys.add(item_key)

            # Extract price from markdown/description
            markdown = result.get("markdown", "")
            description = result.get("description", "")
            price, currency = _extract_price_from_text(f"{title} {description} {markdown[:500]}")

            image_url = ""
            metadata = result.get("metadata", {})
            if metadata.get("og:image"):
                image_url = metadata["og:image"]

            notes = ""
            if price is not None:
                eur_price = to_eur(price, currency)
                notes = f"EUR {eur_price:.2f}"

            try:
                item = CatalogItem(
                    category=category,
                    item_key=item_key[:255],
                    title=title[:500],
                    brand=brand,
                    notes=notes,
                    image_url=image_url,
                    attributes_json={
                        "source": "firecrawl",
                        "source_url": result.get("url", ""),
                        "enriched_at": "auto",
                    },
                )
                items.append(item)
            except Exception as e:
                logger.debug("Skipping invalid item '%s': %s", title[:50], e)
                stats.transform_errors += 1
                continue

    log_progress(category, "firecrawl_enrich", len(items))
    return items


async def _run_enrichment(
    categories: list[str],
    limit: int,
    dry_run: bool,
    output_file: Optional[str],
) -> None:
    """Run the full enrichment pipeline."""
    stats = IngestStats()
    all_items: list[CatalogItem] = []

    for category in categories:
        if category not in ENRICHMENT_TARGETS:
            logger.info("No enrichment target for category '%s' — skipping", category)
            continue

        config = ENRICHMENT_TARGETS[category]
        items = await _enrich_category(category, config, limit, stats)
        all_items.extend(items)

        # Write training observations
        observations: list[PriceObservation] = []
        for item in items:
            if item.notes and item.notes.startswith("EUR "):
                try:
                    price_eur = float(item.notes.replace("EUR ", ""))
                    observations.append(PriceObservation(
                        features={
                            "category": category,
                            "item_key": item.item_key,
                            "title": item.title,
                            "brand": item.brand,
                            "rarity_score": 0.5,
                            "condition_score": 0.8,
                            "source": "firecrawl",
                        },
                        price=price_eur,
                    ))
                except (ValueError, Exception):
                    pass

        if observations:
            path = write_training_jsonl(category, observations)
            logger.info("Wrote %d training observations to %s", len(observations), path)

    logger.info("Total enriched items: %d", len(all_items))
    logger.info("Stats:\n%s", stats.summary())

    # Output JSON
    if output_file:
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in all_items]
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info("Wrote %d items to %s", len(all_items), out_path)

    # Upsert to DB
    if not dry_run and all_items:
        ingest = SupabaseIngest(stats=stats)
        ingest.upsert_catalog(all_items)
        logger.info("DB upsert complete")
    elif dry_run:
        for item in all_items[:10]:
            logger.info(
                "  [%s] %s — %s (%s)",
                item.category, item.item_key, item.title[:60], item.notes,
            )
        if len(all_items) > 10:
            logger.info("  ... and %d more items", len(all_items) - 10)

    close_http_client()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="firecrawl_enrich",
        description="Enrich CollectAI catalog using Firecrawl web scraping.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Display without DB writes")
    parser.add_argument("--category", type=str, default=None, help="Only enrich one category")
    parser.add_argument("--limit", type=int, default=50, help="Max items per category (default: 50)")
    parser.add_argument("--verbose", action="store_true", help="DEBUG-level logging")
    parser.add_argument("--output", type=str, default=None, help="Write items to JSON file")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.category:
        categories = [args.category]
    else:
        categories = list(ENRICHMENT_TARGETS.keys())

    logger.info(
        "Starting Firecrawl enrichment: %d categories, limit=%d, dry_run=%s",
        len(categories), args.limit, args.dry_run,
    )

    asyncio.run(_run_enrichment(
        categories=categories,
        limit=args.limit,
        dry_run=args.dry_run,
        output_file=args.output,
    ))


if __name__ == "__main__":
    main()
