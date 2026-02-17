"""
Crawl4AI Event Page Crawler for CollectAI.

Supplements the email newsletter scraper by directly crawling event/news pages
from collectible publishers using Crawl4AI (local Playwright crawler).
Extracts event data and upserts to the events table.

Functionally equivalent to firecrawl_events.py but uses Crawl4AI instead of
Firecrawl. Adds wait_for support for JS-rendered event pages.

Targets:
  - pokemon.com/events
  - magic.wizards.com/news
  - warhammer-community.com
  - lego.com/news
  - bts-official.us / weverse (BTS / K-pop events)
  - taylorswift.com (Taylor Swift events / Eras Tour dates)
  - Eventbrite collectible event searches

Usage:
    python -m pipelines.crawl4ai_events [options]

Options:
    --dry-run      Parse and display without DB writes
    --since DAYS   Only include events from last N days (default: 30)
    --verbose      Extra logging
    --output FILE  Write events to JSON file
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pipelines.import_common import setup_logging

logger = setup_logging("collectai.crawl4ai_events")

# ---------------------------------------------------------------------------
# Reuse ScrapedEvent and EventUpserter from newsletter_scraper
# ---------------------------------------------------------------------------

from pipelines.newsletter_scraper import (
    ScrapedEvent,
    EventUpserter,
    _extract_dates,
    _classify_event_kind,
    _category_from_content,
)


# ---------------------------------------------------------------------------
# Target pages (same as firecrawl_events, with wait_for for JS-heavy sites)
# ---------------------------------------------------------------------------

EVENT_PAGE_TARGETS: list[dict[str, Any]] = [
    {
        "url": "https://www.pokemon.com/us/pokemon-news",
        "category_id": "pokemon",
        "kind_default": "release",
        "description": "Pokemon news & events",
    },
    {
        "url": "https://magic.wizards.com/en/news",
        "category_id": "mtg",
        "kind_default": "release",
        "description": "Magic: The Gathering news",
    },
    {
        "url": "https://www.warhammer-community.com/latest-news/",
        "category_id": "warhammer",
        "kind_default": "release",
        "description": "Warhammer Community news",
    },
    {
        "url": "https://www.lego.com/en-us/categories/new-sets-and-products",
        "category_id": "lego",
        "kind_default": "collection_drop",
        "description": "LEGO new sets",
    },
    {
        "url": "https://www.funko.com/blog",
        "category_id": "funko",
        "kind_default": "collection_drop",
        "description": "Funko blog / announcements",
    },
    {
        "url": "https://goodsmile-global.com/news/",
        "category_id": "anime_figures",
        "kind_default": "release",
        "description": "Good Smile Company news",
    },
    # BTS / K-pop events
    {
        "url": "https://weverse.io/bts/feed",
        "category_id": "kpop_merch",
        "kind_default": "collection_drop",
        "description": "BTS Weverse announcements",
        "wait_for": "[class*='feed']",
    },
    {
        "url": "https://www.eventbrite.com/d/online/kpop-event/",
        "category_id": "kpop_merch",
        "kind_default": "meetup",
        "description": "K-pop events on Eventbrite",
        "wait_for": "[data-testid='search-results']",
    },
    # Taylor Swift events
    {
        "url": "https://www.taylorswift.com/events/",
        "category_id": "taylor_swift",
        "kind_default": "convention",
        "description": "Taylor Swift official events",
    },
    {
        "url": "https://www.eventbrite.com/d/online/taylor-swift-fan-event/",
        "category_id": "taylor_swift",
        "kind_default": "meetup",
        "description": "Taylor Swift fan events on Eventbrite",
        "wait_for": "[data-testid='search-results']",
    },
    # General collectible events
    {
        "url": "https://www.eventbrite.com/d/online/collectibles-show/",
        "category_id": None,
        "kind_default": "convention",
        "description": "Collectible shows on Eventbrite",
        "wait_for": "[data-testid='search-results']",
    },
    {
        "url": "https://www.eventbrite.com/d/online/comic-con/",
        "category_id": None,
        "kind_default": "convention",
        "description": "Comic Con events on Eventbrite",
        "wait_for": "[data-testid='search-results']",
    },
]


# ---------------------------------------------------------------------------
# Event extraction from markdown
# ---------------------------------------------------------------------------

_EVENT_TITLE_RE = re.compile(
    r"^#{1,3}\s+(.{10,120})$",
    re.MULTILINE,
)

_DATE_RANGE_RE = re.compile(
    r"(\w+\s+\d{1,2})\s*[-–]\s*(\d{1,2}),?\s*(\d{4})",
)

_LOCATION_RE = re.compile(
    r"(?:at|venue|location|held at)\s*:?\s*([A-Z][^.\n]{5,80})",
    re.IGNORECASE,
)


def _extract_events_from_markdown(
    markdown: str,
    page_url: str,
    category_id: Optional[str],
    kind_default: str,
) -> list[ScrapedEvent]:
    """Parse markdown content to extract events."""
    events: list[ScrapedEvent] = []
    seen_titles: set[str] = set()

    all_dates = _extract_dates(markdown)
    if not all_dates:
        return events

    titles = _EVENT_TITLE_RE.findall(markdown)

    if not titles:
        lines = markdown.split("\n")
        for line in lines:
            line = line.strip()
            if len(line) > 15 and len(line) < 200 and not line.startswith("http"):
                titles.append(line)
            if len(titles) >= 10:
                break

    for idx, title in enumerate(titles):
        title_clean = title.strip().strip("#").strip()
        if not title_clean or len(title_clean) < 5:
            continue

        title_norm = title_clean.lower()[:60]
        if title_norm in seen_titles:
            continue
        seen_titles.add(title_norm)

        event_date = all_dates[min(idx, len(all_dates) - 1)]

        kind = _classify_event_kind(title_clean)
        if kind == "release":
            kind = kind_default

        location = None
        loc_match = _LOCATION_RE.search(markdown)
        if loc_match:
            location = loc_match.group(1).strip()

        cat = category_id
        if cat is None:
            cat = _category_from_content(title_clean)

        events.append(ScrapedEvent(
            title=title_clean[:200],
            kind=kind,
            category_id=cat,
            date=event_date,
            location=location,
            online_url=page_url,
            source_url=page_url,
            description=title_clean[:500],
        ))

        if len(events) >= 20:
            break

    return events


# ---------------------------------------------------------------------------
# Crawler
# ---------------------------------------------------------------------------

async def _crawl_event_pages(
    targets: list[dict[str, Any]],
    since_days: int,
) -> list[ScrapedEvent]:
    """Crawl all target pages and extract events."""
    from app.lib.crawl4ai_client import scrape_url, configured

    if not configured():
        logger.error("Crawl4AI not configured (CRAWL4AI_ENABLED is false) — cannot crawl event pages")
        return []

    all_events: list[ScrapedEvent] = []
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")

    for target in targets:
        url = target["url"]
        category_id = target.get("category_id")
        kind_default = target.get("kind_default", "release")
        description = target.get("description", url)
        wait_for = target.get("wait_for")

        logger.info("Crawling: %s (%s)", description, url)

        try:
            result = await scrape_url(url, wait_for=wait_for)
            if not result or not result.get("markdown"):
                logger.warning("  No markdown returned for %s", url)
                continue

            markdown = result["markdown"]
            events = _extract_events_from_markdown(
                markdown, url, category_id, kind_default,
            )

            fresh_events = [
                e for e in events
                if e.date >= cutoff_date
            ]

            logger.info("  Extracted %d events (%d after date filter)", len(events), len(fresh_events))
            all_events.extend(fresh_events)

        except Exception:
            logger.error("  Failed to crawl %s", url, exc_info=True)
            continue

    # Dedup by title + date
    seen: set[str] = set()
    unique: list[ScrapedEvent] = []
    for ev in all_events:
        key = f"{ev.title[:60].lower()}:{ev.date}"
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    logger.info("Total unique events: %d (deduped from %d)", len(unique), len(all_events))
    return unique


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def run_event_crawler(
    since_days: int = 30,
    dry_run: bool = False,
    output_file: Optional[str] = None,
) -> list[ScrapedEvent]:
    """End-to-end: crawl pages, extract events, upsert to DB."""

    events = await _crawl_event_pages(EVENT_PAGE_TARGETS, since_days)

    # Output JSON
    if output_file:
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [e.to_dict() for e in events]
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info("Wrote %d events to %s", len(events), out_path)

    if dry_run:
        if not events:
            logger.info("No events found.")
        else:
            logger.info("\n%s", "=" * 72)
            logger.info("  Crawled Events (%d total)", len(events))
            logger.info("%s\n", "=" * 72)
            for i, ev in enumerate(events, 1):
                logger.info("  [%d] %s", i, ev.title)
                logger.info("      Kind:     %s", ev.kind)
                logger.info("      Category: %s", ev.category_id or "(unknown)")
                logger.info("      Date:     %s", ev.date)
                if ev.location:
                    logger.info("      Location: %s", ev.location)
                if ev.source_url:
                    logger.info("      Source:   %s", ev.source_url)
                logger.info("")
    else:
        upserter = EventUpserter()
        try:
            upserter.upsert(events)
            upserter.print_stats()
        finally:
            upserter.close()

    # Clean up Crawl4AI browser
    try:
        from app.lib.crawl4ai_client import close
        await close()
    except Exception:
        pass

    return events


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crawl4ai_events",
        description="Crawl collectible publisher pages for event data using Crawl4AI.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Display without DB writes")
    parser.add_argument("--since", type=int, default=30, metavar="DAYS", help="Event date cutoff (default: 30)")
    parser.add_argument("--verbose", action="store_true", help="DEBUG-level logging")
    parser.add_argument("--output", type=str, default=None, metavar="FILE", help="Write events to JSON file")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting Crawl4AI event crawler (since=%d days)", args.since)

    try:
        events = asyncio.run(run_event_crawler(
            since_days=args.since,
            dry_run=args.dry_run,
            output_file=args.output,
        ))
        logger.info("Done. %d events crawled.", len(events))
    except Exception:
        logger.exception("Event crawler failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
