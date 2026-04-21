"""
Ticketmaster Discovery API → CollectAI events pipeline.

Runs a small fixed list of keyword+country queries each cycle, maps
raw API events to ScrapedEvent, and upserts via EventUpserter.

Unlike firecrawl_events / crawl4ai_events, this path uses a first-
party API so we get clean structured data (no selector drift, no
Crawl4AI timeouts). Rate limit is 5 calls/sec / 5,000/day; with ~30
queries per cycle and a 0.3s sleep, a cycle uses <10 seconds and
~30 of the daily quota.

Usage:
    python -m pipelines.ticketmaster_events [--dry-run]

Env vars:
    TICKETMASTER_API_KEY, TICKETMASTER_ENABLED  (see app.lib.ticketmaster_client)
    SUPABASE_URL, SUPABASE_SERVICE_KEY          (for EventUpserter)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.lib import ticketmaster_client
from pipelines.newsletter_scraper import ScrapedEvent, EventUpserter

logger = logging.getLogger("collectai.ticketmaster_events")


# ---------------------------------------------------------------------------
# Query matrix: which collectible-relevant queries to run each cycle.
#
# Shape: (keyword, category_id, kind_default, countries).
# Keep this list short — each entry is one API call per country. 5
# calls/sec rate limit; we sleep 0.3s between calls to stay safe.
# ---------------------------------------------------------------------------

QUERIES: list[tuple[str, str, str, list[str]]] = [
    # TCGs / card games
    ("pokemon tcg",          "pokemon",         "convention", ["US", "CA", "GB", "DE"]),
    ("magic the gathering",  "mtg",             "convention", ["US", "CA", "GB", "DE"]),
    ("yu-gi-oh",             "yugioh",          "convention", ["US", "CA", "GB"]),
    ("lorcana",              "lorcana",         "convention", ["US", "CA", "GB"]),
    # Comics / collectibles shows
    ("comic con",            "comic_books",     "convention", ["US", "CA", "GB", "DE", "NL"]),
    ("card show",            "sportscards",     "convention", ["US", "CA"]),
    ("sports card",          "sportscards",     "convention", ["US", "CA"]),
    # Anime / J-culture
    ("anime expo",           "anime_figures",   "convention", ["US", "CA", "GB"]),
    ("anime convention",     "anime_figures",   "convention", ["US", "CA", "GB", "DE", "NL"]),
    # Brands
    ("funko",                "funko",           "meetup",     ["US", "GB"]),
    ("lego",                 "lego",            "convention", ["US", "GB", "DE"]),
    ("warhammer",            "warhammer",       "convention", ["US", "GB", "DE"]),
    # K-pop / fandom (concerts drive merch drops)
    ("bts",                  "kpop_merch",      "convention", ["US", "GB", "DE"]),
    ("blackpink",            "kpop_merch",      "convention", ["US", "GB", "DE"]),
    ("k-pop",                "kpop_merch",      "convention", ["US", "GB", "DE"]),
    ("taylor swift",         "taylor_swift",    "convention", ["US", "GB", "DE", "NL"]),
    # Vinyl / music collectibles
    ("record fair",          "city_pop_vinyl",  "convention", ["US", "GB", "DE", "NL"]),
]

# Sleep between API calls to stay under 5 req/s.
INTER_CALL_SLEEP_SECONDS = 0.3


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

def _event_to_scraped(
    event: dict[str, Any],
    category_id: str,
    kind_default: str,
) -> Optional[ScrapedEvent]:
    """Map a raw Ticketmaster event dict to our ScrapedEvent dataclass.

    Returns None if the event lacks a start date (our DB requires date).
    """
    start = event.get("dates", {}).get("start", {})
    date = start.get("localDate")
    if not date:
        return None

    time_str = start.get("localTime")

    venues = event.get("_embedded", {}).get("venues", []) or []
    venue = venues[0] if venues else {}
    city = (venue.get("city") or {}).get("name")
    country = (venue.get("country") or {}).get("name")
    venue_name = venue.get("name")
    location_parts = [p for p in (venue_name, city, country) if p]
    location = ", ".join(location_parts) if location_parts else None

    images = event.get("images") or []
    image_url: Optional[str] = None
    if images:
        # Prefer images with width >= 640 for display quality.
        hq = [img for img in images if (img.get("width") or 0) >= 640]
        image_url = (hq[0] if hq else images[0]).get("url")

    return ScrapedEvent(
        title=event.get("name") or "",
        kind=kind_default,
        category_id=category_id,
        date=date,
        time=time_str,
        location=location,
        online_url=None,
        description=(event.get("info") or event.get("pleaseNote") or None),
        source_url=event.get("url"),
        image_url=image_url,
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def run_ticketmaster_ingest(
    since_days: int = 0,
    lookahead_days: int = 180,
    dry_run: bool = False,
) -> list[ScrapedEvent]:
    """Execute the query matrix and upsert results. Returns collected events."""

    if not ticketmaster_client.configured():
        logger.warning("[Ticketmaster] not configured — skipping run")
        return []

    now = datetime.now(timezone.utc)
    start_dt = (now - timedelta(days=since_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_dt = (now + timedelta(days=lookahead_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    all_events: list[ScrapedEvent] = []
    api_calls = 0

    for keyword, category_id, kind_default, countries in QUERIES:
        for country_code in countries:
            api_calls += 1
            raw = await ticketmaster_client.search_events(
                keyword=keyword,
                country_code=country_code,
                start_date_time=start_dt,
                end_date_time=end_dt,
                size=50,
            )
            mapped = [
                ev for ev in (_event_to_scraped(e, category_id, kind_default) for e in raw)
                if ev is not None
            ]
            logger.info(
                "[Ticketmaster] %s/%s → %d raw / %d mapped",
                keyword, country_code, len(raw), len(mapped),
            )
            all_events.extend(mapped)
            await asyncio.sleep(INTER_CALL_SLEEP_SECONDS)

    # Dedup by (source_url) or (title,date).
    seen: set[str] = set()
    unique: list[ScrapedEvent] = []
    for ev in all_events:
        key = ev.source_url or f"{ev.title[:80].lower()}:{ev.date}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(ev)

    logger.info(
        "[Ticketmaster] done: %d API calls, %d events (%d unique after dedup)",
        api_calls, len(all_events), len(unique),
    )

    if not dry_run and unique:
        upserter = EventUpserter()
        upserter.upsert(unique, source="ticketmaster")
        logger.info(
            "[Ticketmaster] upsert: inserted=%d updated=%d skipped=%d",
            upserter.inserted, upserter.updated, upserter.skipped,
        )

    await ticketmaster_client.close()
    return unique


async def run_once() -> None:
    """Entry point for the bake orchestrator."""
    await run_ticketmaster_ingest()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ticketmaster → events ingest")
    p.add_argument("--dry-run", action="store_true", help="Skip DB writes")
    p.add_argument("--lookahead-days", type=int, default=180)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    events = asyncio.run(run_ticketmaster_ingest(
        lookahead_days=args.lookahead_days,
        dry_run=args.dry_run,
    ))
    print(f"Collected {len(events)} unique events")
    sys.exit(0 if events else 1)
