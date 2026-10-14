"""Disney Lorcana store events from Ravensburger Play (2026-10-14).

Replaces `limitless_tcg_events`, which is a RESULTS feed: every one of its
2,016 rows was already past when stored, and it had written nothing since
2026-09-28 (0 upcoming) — its own docstring said to delete it if that lasted a
month.

Source: the JSON API behind tcg.ravensburgerplay.com's event finder —
`api.ravensburgerplay.com/api/v2/events/?latitude=&longitude=&num_miles=&
display_statuses=upcoming` — no key. It is NOT a documented public API and no
terms page was found (`/terms-of-service` 404, checked 2026-10-14), so: few
requests per run (HUBS x MAX_PAGES, with a pause), a contact User-Agent, and a
run that fetches nothing is logged as an ERROR rather than read as "no events".

Filter: the feed is ~70% weekly play nights ("Thursday Evening Weekly Play").
Those would bury the Events tab, so only SPECIAL events are kept — a name that
says prerelease / championship / challenge / cup / launch / release, or the
feed's own `is_headlining_event` / `convention` flags. Measured 2026-10-14
within 150 mi of the Netherlands: 244 of 800 upcoming events pass.

Rows go through EventUpserter, whose row builder always emits every key (a
PostgREST batch with mixed key sets is rejected whole — DATA_SCALING_PLAN §10).

Usage:
    from pipelines.ravensburger_play_events import run_ravensburger_scraper
    python -m pipelines.ravensburger_play_events [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx

from pipelines.import_common import setup_logging

logger = setup_logging("collectai.ravensburger_play")

from pipelines.newsletter_scraper import ScrapedEvent, EventUpserter  # noqa: E402

API_URL = "https://api.ravensburgerplay.com/api/v2/events/"
# The finder is a single-page app; this deep link is the best available and is
# also the row's unique source_url (upsert conflict key). Not verified to open
# the event itself (the SPA answers 200 for any id).
EVENT_URL = "https://tcg.ravensburgerplay.com/events?event={id}"
USER_AGENT = "SparrowCollect/1.0 (+https://sparrowcollect.com; support@sparrowcollect.com)"

# (label, latitude, longitude, radius in miles). Benelux + the three biggest
# neighbouring markets; each hub costs at most MAX_PAGES requests per run.
HUBS: list[tuple[str, float, float, int]] = [
    ("benelux", 51.5, 5.5, 150),
    ("london", 51.51, -0.13, 60),
    ("paris", 48.86, 2.35, 60),
    ("berlin", 52.52, 13.40, 60),
]
PAGE_SIZE = 100
MAX_PAGES = 8

# Ravensburger Play `game` ids: 1 = Disney Lorcana, 3 = Riftbound (not a
# category we carry).
GAME_CATEGORY_MAP = {1: "lorcana"}

_SPECIAL = re.compile(
    r"pre-?release|champion|challenge|\bcup\b|launch|release",
    re.IGNORECASE,
)


def is_special(event: dict[str, Any]) -> bool:
    """A special event, not a weekly play night."""
    if event.get("is_headlining_event") or event.get("convention"):
        return True
    return bool(_SPECIAL.search(event.get("name") or ""))


def to_scraped_event(event: dict[str, Any], now: Optional[datetime] = None) -> Optional[ScrapedEvent]:
    """Map one API event to a ScrapedEvent, or None when it should not be stored."""
    category_id = GAME_CATEGORY_MAP.get(event.get("game"))
    if not category_id:
        return None
    if event.get("is_test_event") or event.get("event_is_online"):
        return None
    if (event.get("event_status") or "SCHEDULED") != "SCHEDULED":
        return None
    if not is_special(event):
        return None
    try:
        start = datetime.fromisoformat(str(event["start_datetime"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None
    if start < (now or datetime.now(timezone.utc)):
        return None
    # The date and time the store advertises — its own timezone, not UTC.
    try:
        local = start.astimezone(ZoneInfo(event.get("timezone") or "UTC"))
    except Exception:
        local = start
    store = event.get("store") or {}
    address = event.get("full_address") or store.get("full_address") or ""
    # Some stores type their address over several lines ("59065 HAMM\nGERMANY").
    address = ", ".join(part.strip(" ,") for part in address.splitlines() if part.strip(" ,"))
    location = ", ".join(p for p in (store.get("name"), address) if p)
    details = []
    fmt = event.get("gameplay_format")
    if isinstance(fmt, dict):
        fmt = fmt.get("name")
    if fmt:
        details.append(f"Format: {fmt}")
    cents, currency = event.get("cost_in_cents"), event.get("currency")
    if isinstance(cents, int) and cents > 0 and currency:
        details.append(f"Entry {cents / 100:.2f} {currency}")
    elif cents == 0:
        details.append("Free entry")
    if event.get("capacity"):
        details.append(f"{event['capacity']} seats")
    return ScrapedEvent(
        title=(event.get("name") or "Disney Lorcana event")[:200],
        kind="meetup",  # a scheduled player gathering, as tournaments are elsewhere
        category_id=category_id,
        date=local.strftime("%Y-%m-%d"),
        time=local.strftime("%H:%M"),
        end_date=None,
        location=location or None,
        online_url=None,
        description=" · ".join(details) or None,
        source_url=EVENT_URL.format(id=event.get("id")),
        image_url=event.get("full_header_image_url") or None,
    )


async def _fetch_hub(client: httpx.AsyncClient, lat: float, lon: float, miles: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        resp = await client.get(
            API_URL,
            params={
                "latitude": lat, "longitude": lon, "num_miles": miles,
                "display_statuses": "upcoming", "page_size": PAGE_SIZE, "page": page,
            },
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        events.extend(data.get("results") or [])
        if not data.get("next"):
            break
        await asyncio.sleep(1.0)  # polite: an undocumented API
    return events


async def run_ravensburger_scraper(dry_run: bool = False) -> list[ScrapedEvent]:
    """Fetch upcoming special Lorcana events around each hub and upsert them."""
    seen: set[Any] = set()
    fetched = 0
    out: list[ScrapedEvent] = []
    failures: list[str] = []
    async with httpx.AsyncClient() as client:
        for label, lat, lon, miles in HUBS:
            try:
                raw = await _fetch_hub(client, lat, lon, miles)
            except Exception as e:
                failures.append(f"{label}: {type(e).__name__}")
                logger.error("Ravensburger Play hub=%s failed: %s", label, e)
                continue
            fetched += len(raw)
            for ev in raw:
                if ev.get("id") in seen:
                    continue
                seen.add(ev.get("id"))
                mapped = to_scraped_event(ev)
                if mapped:
                    out.append(mapped)
    logger.info("Ravensburger Play: %d fetched, %d special upcoming kept, %d hub failures",
                fetched, len(out), len(failures))
    if fetched == 0:
        # An empty feed is an outage or a block, never "no events in Europe".
        raise RuntimeError(f"Ravensburger Play returned no events from any hub ({', '.join(failures) or 'empty'})")
    if not dry_run and out:
        upserter = EventUpserter()
        try:
            await upserter.upsert_events(out, source="ravensburger_play")
            upserter.print_stats()
        finally:
            upserter.close()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Ravensburger Play (Disney Lorcana) events")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    events = asyncio.run(run_ravensburger_scraper(dry_run=args.dry_run))
    for e in events[:20]:
        print(f"{e.date} {e.time}  {e.title[:60]}  @ {e.location}")


if __name__ == "__main__":
    main()
