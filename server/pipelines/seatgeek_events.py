"""
SeatGeek Search API → CollectAI events pipeline.

Parallels ticketmaster_events.py. Maps SeatGeek event dicts to
ScrapedEvent, upserts via EventUpserter.

SeatGeek's `venue.country` filter is ISO-2 lowercase (us, gb, de, …).
Rate limit is not formally published but informally ~1 req/sec;
INTER_CALL_SLEEP_SECONDS is set conservatively.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.lib import seatgeek_client
from pipelines.newsletter_scraper import ScrapedEvent, EventUpserter

logger = logging.getLogger("collectai.seatgeek_events")


QUERIES: list[tuple[str, str, str, list[str]]] = [
    # Keyword, category_id, kind_default, countries (ISO-2 lower)
    ("pokemon tcg",          "pokemon",         "convention", ["us", "ca", "gb", "de"]),
    ("magic the gathering",  "mtg",             "convention", ["us", "ca", "gb", "de"]),
    ("yu-gi-oh",             "yugioh",          "convention", ["us", "ca", "gb"]),
    ("comic con",            "comic_books",     "convention", ["us", "ca", "gb", "de"]),
    ("card show",            "sportscards",     "convention", ["us", "ca"]),
    ("sports card",          "sportscards",     "convention", ["us", "ca"]),
    ("anime expo",           "anime_figures",   "convention", ["us", "ca", "gb"]),
    ("anime convention",     "anime_figures",   "convention", ["us", "ca", "gb"]),
    ("funko",                "funko",           "meetup",     ["us", "gb"]),
    ("warhammer",            "warhammer",       "convention", ["us", "gb", "de"]),
    ("bts",                  "kpop_merch",      "convention", ["us", "gb", "de"]),
    ("blackpink",            "kpop_merch",      "convention", ["us", "gb", "de"]),
    ("k-pop",                "kpop_merch",      "convention", ["us", "gb", "de"]),
    ("taylor swift",         "taylor_swift",    "convention", ["us", "gb", "de", "nl"]),
    ("record fair",          "city_pop_vinyl",  "convention", ["us", "gb", "de", "nl"]),
]

INTER_CALL_SLEEP_SECONDS = 0.5


def _event_to_scraped(
    event: dict[str, Any],
    category_id: str,
    kind_default: str,
) -> Optional[ScrapedEvent]:
    """Map SeatGeek event → ScrapedEvent, or None if unmappable."""
    local_date = event.get("datetime_local") or ""
    if not local_date or len(local_date) < 10:
        return None
    date = local_date[:10]
    time_str = local_date[11:16] if len(local_date) >= 16 else None

    venue = event.get("venue") or {}
    city = venue.get("city")
    country = venue.get("country")
    venue_name = venue.get("name")
    location_parts = [p for p in (venue_name, city, country) if p]
    location = ", ".join(location_parts) if location_parts else None

    perfs = event.get("performers") or []
    perf_image = (perfs[0] or {}).get("image") if perfs else None

    return ScrapedEvent(
        title=event.get("title") or event.get("short_title") or "",
        kind=kind_default,
        category_id=category_id,
        date=date,
        time=time_str,
        location=location,
        online_url=None,
        description=event.get("description") or None,
        source_url=event.get("url"),
        image_url=perf_image,
    )


async def run_seatgeek_ingest(
    lookahead_days: int = 180,
    dry_run: bool = False,
) -> list[ScrapedEvent]:
    if not seatgeek_client.configured():
        logger.warning("[SeatGeek] not configured — skipping run")
        return []

    now = datetime.now(timezone.utc)
    gte = now.strftime("%Y-%m-%dT%H:%M:%S")
    lte = (now + timedelta(days=lookahead_days)).strftime("%Y-%m-%dT%H:%M:%S")

    all_events: list[ScrapedEvent] = []
    api_calls = 0

    for keyword, category_id, kind_default, countries in QUERIES:
        for cc in countries:
            api_calls += 1
            raw = await seatgeek_client.search_events(
                query=keyword,
                venue_country=cc,
                datetime_utc_gte=gte,
                datetime_utc_lte=lte,
                per_page=50,
            )
            mapped = [
                ev for ev in (_event_to_scraped(e, category_id, kind_default) for e in raw)
                if ev is not None
            ]
            logger.info(
                "[SeatGeek] %s/%s → %d raw / %d mapped",
                keyword, cc, len(raw), len(mapped),
            )
            all_events.extend(mapped)
            await asyncio.sleep(INTER_CALL_SLEEP_SECONDS)

    seen: set[str] = set()
    unique: list[ScrapedEvent] = []
    for ev in all_events:
        key = ev.source_url or f"{ev.title[:80].lower()}:{ev.date}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(ev)

    logger.info(
        "[SeatGeek] done: %d API calls, %d events (%d unique after dedup)",
        api_calls, len(all_events), len(unique),
    )

    if not dry_run and unique:
        upserter = EventUpserter()
        upserter.upsert(unique, source="seatgeek")
        logger.info(
            "[SeatGeek] upsert: inserted=%d updated=%d skipped=%d",
            upserter.inserted, upserter.updated, upserter.skipped,
        )

    await seatgeek_client.close()
    return unique


async def run_once() -> None:
    await run_seatgeek_ingest()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--lookahead-days", type=int, default=180)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    evs = asyncio.run(run_seatgeek_ingest(
        lookahead_days=args.lookahead_days,
        dry_run=args.dry_run,
    ))
    print(f"Collected {len(evs)} unique events")
    sys.exit(0 if evs else 1)
