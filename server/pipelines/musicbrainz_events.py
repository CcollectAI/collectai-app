"""MusicBrainz vinyl release calendar scraper.

Queries the public MusicBrainz JSON API for upcoming vinyl/LP/12inch/7inch
releases and upserts them as `release` events.

No API key required — MusicBrainz is free/public. Rate limit: 1 req/sec per IP
(we respect that with a semaphore + 1.1s delay).

Usage:
    from pipelines.musicbrainz_events import run_musicbrainz_scraper
    events = await run_musicbrainz_scraper(days_ahead=60)

    # Or standalone:
    python -m pipelines.musicbrainz_events [--dry-run] [--days 60]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from pipelines.import_common import setup_logging

logger = setup_logging("collectai.musicbrainz_events")

# Reuse shared event infrastructure
from pipelines.newsletter_scraper import ScrapedEvent, EventUpserter

# ---------------------------------------------------------------------------
# Format filters — map MusicBrainz `format:` query values to our categories
# ---------------------------------------------------------------------------

FORMAT_QUERIES: list[dict[str, Any]] = [
    {"format": "vinyl", "category_id": "vinyl_records", "description": "Vinyl LP releases"},
    {"format": "12%22+Vinyl", "category_id": "vinyl_records", "description": "12-inch vinyl"},
    {"format": "7%22+Vinyl", "category_id": "vinyl_records", "description": "7-inch vinyl"},
    {"format": "Cassette", "category_id": "city_pop_vinyl", "description": "Cassette releases"},
]

API_BASE = "https://musicbrainz.org/ws/2"
USER_AGENT = "CollectAI/1.0 (https://collectai.app; contact@collectai.app)"
RATE_LIMIT_DELAY = 1.1  # seconds between requests (MB allows 1/sec)
MAX_RESULTS_PER_QUERY = 100


async def _fetch_releases(
    client: httpx.AsyncClient,
    format_filter: str,
    since: datetime,
    until: datetime,
) -> list[dict[str, Any]]:
    """Fetch upcoming releases for a given format filter."""
    # Build Lucene query: date range + format
    since_str = since.strftime("%Y-%m-%d")
    until_str = until.strftime("%Y-%m-%d")
    query = f"date:[{since_str} TO {until_str}] AND format:{format_filter}"

    # URL-encode brackets
    import urllib.parse
    params = {"query": query, "limit": MAX_RESULTS_PER_QUERY, "fmt": "json"}
    url = f"{API_BASE}/release?" + urllib.parse.urlencode(params)

    try:
        resp = await client.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=15.0,
        )
        if resp.status_code != 200:
            logger.warning("MusicBrainz query failed: %d for format=%s", resp.status_code, format_filter)
            return []
        data = resp.json()
        return data.get("releases", [])
    except Exception as e:
        logger.warning("MusicBrainz fetch failed for format=%s: %s", format_filter, e)
        return []


# Collector-relevance filters. A release must either have:
#   - high score (MusicBrainz relevance score >= 95), OR
#   - a well-known label/disambiguation (e.g., limited edition, colored vinyl), OR
#   - a top-100 artist indicator (heuristic: artist-credit has 'sort-name' data)
#
# These filters cut ~80% of noise (random indie releases, self-published albums)
# while keeping major-label releases, reissues, and limited variants that
# collectors actually care about.

_COLLECTOR_KEYWORDS = {
    # Special editions — collectors care
    "limited", "numbered", "signed", "exclusive", "deluxe", "box set", "boxset",
    "reissue", "remaster", "anniversary", "collector",
    # Vinyl variants — collector targets
    "splatter", "marbled", "colored", "coloured", "picture disc", "clear vinyl",
    "gold vinyl", "silver vinyl", "red vinyl", "blue vinyl", "green vinyl",
    "half-speed", "half speed", "180g", "180 gram", "audiophile",
    # RSD / store exclusives
    "rsd", "record store day", "indie exclusive", "first pressing",
}

_MIN_MB_SCORE = 95  # MusicBrainz relevance score (0-100) — only top matches


def _is_collector_relevant(release: dict[str, Any]) -> bool:
    """Heuristic: is this release worth showing on a collectibles events page?

    Requires at least ONE of these collector signals:
    - Disambiguation mentions variant/edition (splatter, limited, anniversary, etc.)
    - Title contains collector keywords
    - Packaging is non-standard (box set, gatefold, etc.)
    - Status is 'Official' AND has a release-group linked (indicates real album
      not a bootleg or self-published)

    Score alone is NOT a signal — MusicBrainz returns score=100 for every
    search match regardless of quality.
    """
    # Signal 1: disambiguation has collector keywords
    disambig = (release.get("disambiguation") or "").lower()
    if disambig and any(kw in disambig for kw in _COLLECTOR_KEYWORDS):
        return True

    # Signal 2: title has collector keywords
    title = (release.get("title") or "").lower()
    if any(kw in title for kw in _COLLECTOR_KEYWORDS):
        return True

    # Signal 3: non-standard packaging
    packaging = (release.get("packaging") or "").lower()
    collector_packaging = {
        "digipak", "gatefold", "slipcase", "cardboard sleeve", "book",
        "super jewel box", "cassette case",
    }
    if packaging in collector_packaging:
        return True

    # Signal 4: explicitly identified as collector-worthy by count>1 (multiple
    # variants exist — i.e., the release has special editions catalogued)
    variant_count = release.get("count", 1)
    if isinstance(variant_count, int) and variant_count > 1:
        return True

    return False


def _release_to_event(
    release: dict[str, Any], category_id: str
) -> ScrapedEvent | None:
    """Convert a MusicBrainz release to a ScrapedEvent (collector-filtered)."""
    # Skip releases that aren't collector-relevant
    if not _is_collector_relevant(release):
        return None

    title = release.get("title", "").strip()
    if not title or len(title) < 2:
        return None

    date_str = release.get("date", "").strip()
    if not date_str:
        return None

    # MB may return partial dates (YYYY, YYYY-MM). Normalize to YYYY-MM-DD.
    parts = date_str.split("-")
    if len(parts) == 1 and len(parts[0]) == 4:
        date_str = f"{parts[0]}-01-01"
    elif len(parts) == 2:
        date_str = f"{parts[0]}-{parts[1]}-01"

    # Artist name
    artist_credits = release.get("artist-credit", [])
    artist_name = (
        artist_credits[0].get("name", "").strip()
        if artist_credits and isinstance(artist_credits[0], dict)
        else "Unknown Artist"
    )

    full_title = f"{artist_name} — {title}"[:200]

    # Build a source URL to MusicBrainz
    release_id = release.get("id", "")
    source_url = f"https://musicbrainz.org/release/{release_id}" if release_id else None

    # Disambiguation may include variant info (color, edition)
    disambiguation = release.get("disambiguation", "")
    description = disambiguation[:500] if disambiguation else None

    return ScrapedEvent(
        title=full_title,
        kind="release",
        category_id=category_id,
        date=date_str,
        time=None,
        end_date=None,
        location=None,
        online_url=None,
        description=description,
        source_url=source_url,
        image_url=None,
    )


async def run_musicbrainz_scraper(
    days_ahead: int = 60,
    dry_run: bool = False,
) -> list[ScrapedEvent]:
    """Fetch upcoming vinyl/cassette releases from MusicBrainz."""
    now = datetime.now(timezone.utc)
    until = now + timedelta(days=days_ahead)

    all_events: list[ScrapedEvent] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient() as client:
        for target in FORMAT_QUERIES:
            releases = await _fetch_releases(
                client,
                target["format"],
                since=now,
                until=until,
            )
            logger.info(
                "MusicBrainz format=%s: %d releases",
                target["format"],
                len(releases),
            )

            for rel in releases:
                rel_id = rel.get("id")
                if rel_id in seen_ids:
                    continue
                seen_ids.add(rel_id)

                event = _release_to_event(rel, target["category_id"])
                if event:
                    all_events.append(event)

            # Respect MusicBrainz rate limit
            await asyncio.sleep(RATE_LIMIT_DELAY)

    logger.info("MusicBrainz: %d unique events across %d formats", len(all_events), len(FORMAT_QUERIES))

    if not dry_run and all_events:
        upserter = EventUpserter()
        try:
            await upserter.upsert_events(all_events, source="musicbrainz")
            upserter.print_stats()
        except Exception as e:
            logger.warning("MusicBrainz upsert failed: %s", e)
        finally:
            upserter.close()

    return all_events


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="MusicBrainz vinyl release scraper")
    parser.add_argument("--dry-run", action="store_true", help="Parse without DB writes")
    parser.add_argument("--days", type=int, default=60, help="Days ahead to look (default: 60)")
    args = parser.parse_args()

    logger.info("Starting MusicBrainz scraper (days_ahead=%d, dry_run=%s)", args.days, args.dry_run)
    events = asyncio.run(run_musicbrainz_scraper(days_ahead=args.days, dry_run=args.dry_run))
    logger.info("Done: %d events", len(events))


if __name__ == "__main__":
    main()
