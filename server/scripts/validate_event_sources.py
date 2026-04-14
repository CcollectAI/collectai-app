#!/usr/bin/env python3
"""Validate all event data sources — checks that each is reachable and
produces at least one valid event.

Runs in 3 modes:
- `--quick`: only verifies HTTP 200 + valid XML/JSON (fast)
- `--full`: actually parses each source and counts events (slower, ~1-2 min)
- `--ci`: like --full but exits non-zero if any source is broken (for GitHub Actions)

Usage:
    python -m scripts.validate_event_sources --quick
    python -m scripts.validate_event_sources --full
    python -m scripts.validate_event_sources --ci  # used by CI
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

sys.path.insert(0, ".")

USER_AGENT = "CollectAI/1.0 (source validator)"
TIMEOUT = 10.0


async def _check_rss_feed(
    client: httpx.AsyncClient, target: dict[str, Any], mode: str
) -> dict[str, Any]:
    """Check a single RSS feed."""
    url = target["feed_url"]
    name = target["description"]
    result = {"url": url, "name": name, "category": target.get("category_id"), "status": "UNKNOWN", "events": 0, "error": None}

    try:
        resp = await client.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml"},
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            result["status"] = f"HTTP_{resp.status_code}"
            result["error"] = f"HTTP {resp.status_code}"
            return result

        text = resp.text
        is_xml = "<rss" in text[:500].lower() or "<feed" in text[:500].lower() or "<?xml" in text[:500].lower()
        if not is_xml:
            result["status"] = "NOT_XML"
            result["error"] = "Response is not RSS/Atom XML"
            return result

        if mode == "quick":
            result["status"] = "OK"
            return result

        # Full mode: actually parse
        from pipelines.rss_events import _parse_feed_xml
        since = datetime.now(timezone.utc) - timedelta(days=30)
        events = _parse_feed_xml(text, target, since)
        result["events"] = len(events)
        result["status"] = "OK" if events else "ZERO_EVENTS"
        return result

    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = str(e)[:80]
        return result


async def _check_musicbrainz(client: httpx.AsyncClient) -> dict[str, Any]:
    """Verify MusicBrainz is reachable and returning data."""
    try:
        from pipelines.musicbrainz_events import run_musicbrainz_scraper
        events = await run_musicbrainz_scraper(days_ahead=30, dry_run=True)
        return {
            "url": "https://musicbrainz.org/ws/2",
            "name": "MusicBrainz vinyl",
            "category": "vinyl_records",
            "status": "OK" if events else "ZERO_EVENTS",
            "events": len(events),
            "error": None,
        }
    except Exception as e:
        return {
            "url": "https://musicbrainz.org/ws/2",
            "name": "MusicBrainz vinyl",
            "category": "vinyl_records",
            "status": "FAIL",
            "events": 0,
            "error": str(e)[:80],
        }


async def _check_limitless(client: httpx.AsyncClient) -> dict[str, Any]:
    """Verify Limitless TCG API is reachable."""
    try:
        from pipelines.limitless_tcg_events import run_limitless_scraper
        events = await run_limitless_scraper(dry_run=True)
        return {
            "url": "https://play.limitlesstcg.com/api",
            "name": "Limitless TCG",
            "category": "pokemon",
            "status": "OK" if events else "ZERO_EVENTS",
            "events": len(events),
            "error": None,
        }
    except Exception as e:
        return {
            "url": "https://play.limitlesstcg.com/api",
            "name": "Limitless TCG",
            "category": "pokemon",
            "status": "FAIL",
            "events": 0,
            "error": str(e)[:80],
        }


async def main(mode: str) -> int:
    """Returns exit code (0 = all healthy, 1 = at least one source broken)."""
    from pipelines.rss_events import RSS_FEED_TARGETS

    print(f"=== Validating event sources (mode={mode}) ===\n")

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        # RSS feeds (parallel, max 5 at a time)
        semaphore = asyncio.Semaphore(5)

        async def check_with_semaphore(target):
            async with semaphore:
                return await _check_rss_feed(client, target, mode)

        rss_tasks = [check_with_semaphore(t) for t in RSS_FEED_TARGETS]
        results.extend(await asyncio.gather(*rss_tasks))

        # Non-RSS sources (only in full mode — these hit real APIs)
        if mode in ("full", "ci"):
            results.append(await _check_musicbrainz(client))
            results.append(await _check_limitless(client))

    # Print report
    ok = [r for r in results if r["status"] == "OK"]
    zero = [r for r in results if r["status"] == "ZERO_EVENTS"]
    broken = [r for r in results if r["status"] not in ("OK", "ZERO_EVENTS")]

    for r in ok:
        events_str = f"({r['events']} events)" if r["events"] else ""
        print(f"  OK       {r['name']:40s} {events_str}")

    if zero:
        print("\n--- Sources returning 0 events (not fatal but suspicious) ---")
        for r in zero:
            print(f"  ZERO     {r['name']:40s} {r['url'][:60]}")

    if broken:
        print("\n--- BROKEN SOURCES ---")
        for r in broken:
            print(f"  {r['status']:10s} {r['name']:40s} {r['error']}")

    print(f"\n=== Summary: {len(ok)} OK, {len(zero)} zero-events, {len(broken)} broken (total {len(results)}) ===")

    # Exit code: fail in CI mode if any broken
    if mode == "ci" and broken:
        print("\n❌ CI check failed: broken sources detected")
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate event data sources")
    parser.add_argument("--quick", action="store_true", help="Only HTTP check")
    parser.add_argument("--full", action="store_true", help="Parse and count events")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 1 on any broken source")
    args = parser.parse_args()

    mode = "ci" if args.ci else ("full" if args.full else "quick")
    sys.exit(asyncio.run(main(mode)))
