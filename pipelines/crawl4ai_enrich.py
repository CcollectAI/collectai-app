"""
Crawl4AI Catalog Enrichment Pipeline for CollectAI.

Batch pipeline that uses Crawl4AI (local Playwright crawler) to scrape Tier 2
catalog sites and populate category_items + training.jsonl for categories
without dedicated APIs.

Functionally equivalent to firecrawl_enrich.py but uses Crawl4AI instead of
Firecrawl, avoiding per-request billing. Constructs search URLs and crawls
them directly (Crawl4AI has no /search endpoint).

Targets same categories as firecrawl_enrich:
  - Scalemates.com (scale_models)
  - MyFigureCollection.net (anime_figures)
  - HobbySearch JP (gunpla)
  - VGMdb (anime_soundtrack, anime_ost_vinyl)
  - Ktown4u / Weverse (kpop_merch)
  - StockX / Mercari (taylor_swift)
  - BrickLink (lego)
  - 130point / COMC (sportscards)

Usage:
    python -m pipelines.crawl4ai_enrich [options]

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
from urllib.parse import quote_plus

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

logger = setup_logging("collectai.crawl4ai_enrich")

# ---------------------------------------------------------------------------
# Site-specific enrichment configs (same targets as firecrawl_enrich)
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

# Search URL templates (subset used by this pipeline)
_SITE_SEARCH_URLS: dict[str, str] = {
    "scalemates.com": "https://www.scalemates.com/search.php?q={query}",
    "myfigurecollection.net": "https://myfigurecollection.net/browse.v4.php?keywords={query}",
    "hlj.com": "https://www.hlj.com/search/?q={query}",
    "vgmdb.net": "https://vgmdb.net/search?q={query}",
    "ktown4u.com": "https://www.ktown4u.com/search?goodsTextSearch={query}",
    "mercari.com": "https://www.mercari.com/search/?keyword={query}",
    "bricklink.com": "https://www.bricklink.com/v2/search.page?q={query}",
    "130point.com": "https://130point.com/sales/?search={query}",
    "reddit.com/r/mechmarket": "https://www.google.com/search?q={query}+site%3Areddit.com%2Fr%2Fmechmarket",
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


def _build_search_url(site: str, query: str) -> str:
    """Construct search URL for the given site."""
    encoded = quote_plus(query)
    template = _SITE_SEARCH_URLS.get(site)
    if template:
        return template.replace("{query}", encoded)
    return f"https://www.google.com/search?q={encoded}+site%3A{quote_plus(site)}"


# ---------------------------------------------------------------------------
# Enrichment logic
# ---------------------------------------------------------------------------

async def _enrich_category(
    category: str,
    config: dict[str, Any],
    limit: int,
    stats: IngestStats,
) -> list[CatalogItem]:
    """Run enrichment for a single category using Crawl4AI."""
    from app.lib.crawl4ai_client import scrape_url, configured

    if not configured():
        logger.warning("Crawl4AI not configured — skipping %s", category)
        return []

    items: list[CatalogItem] = []
    seen_keys: set[str] = set()
    site = config["site"]
    brand = config.get("brand", "Various")

    for query in config["search_queries"]:
        if len(items) >= limit:
            break

        search_url = _build_search_url(site, query)
        try:
            result = await scrape_url(search_url)
            if not result or not result.get("markdown"):
                continue
        except Exception as e:
            logger.error("Crawl failed for '%s': %s", search_url, e)
            stats.transform_errors += 1
            continue

        # Split page into listing candidates
        markdown = result["markdown"]
        parts = re.split(r"\n{3,}|^-{3,}$|^#{1,3}\s", markdown, flags=re.MULTILINE)
        candidates = [p.strip() for p in parts if len(p.strip()) > 30]

        for chunk in candidates:
            if len(items) >= limit:
                break

            # Extract title from first valid line
            title = None
            for line in chunk.split("\n"):
                line = line.strip().lstrip("#").strip()
                if 10 <= len(line) <= 300:
                    title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
                    break
            if not title:
                continue

            item_key = slugify(title)
            if not item_key or item_key in seen_keys:
                continue
            seen_keys.add(item_key)

            price, currency = _extract_price_from_text(f"{title} {chunk[:500]}")

            image_url = ""
            img_match = re.search(r"!\[.*?\]\((https?://[^\s)]+)\)", chunk)
            if img_match:
                image_url = img_match.group(1)

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
                        "source": "crawl4ai",
                        "source_url": search_url,
                        "enriched_at": "auto",
                    },
                )
                items.append(item)
            except Exception as e:
                logger.debug("Skipping invalid item '%s': %s", title[:50], e)
                stats.transform_errors += 1
                continue

    log_progress(category, "crawl4ai_enrich", len(items))
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
                            "source": "crawl4ai",
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

    # Clean up Crawl4AI browser
    try:
        from app.lib.crawl4ai_client import close
        await close()
    except Exception:
        pass

    close_http_client()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crawl4ai_enrich",
        description="Enrich CollectAI catalog using Crawl4AI local web crawler.",
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
        "Starting Crawl4AI enrichment: %d categories, limit=%d, dry_run=%s",
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
