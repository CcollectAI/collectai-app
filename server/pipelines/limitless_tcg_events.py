"""Limitless TCG tournament scraper.

Public JSON API at play.limitlesstcg.com/api/tournaments — no auth required.
Returns upcoming and recent tournaments for Pokemon TCG, Pokemon Pocket, and
potentially other TCGs.

Filters:
- Only upcoming tournaments (date >= now) — enforced since 2026-08-22;
  before that the rule was "not more than 3 days stale", and every one of the
  1,986 rows it wrote was already in the past at insert time
- Only tournaments with >=8 players (skip tiny local events)
- Maps game codes to our category IDs

Usage:
    from pipelines.limitless_tcg_events import run_limitless_scraper
    events = await run_limitless_scraper()

    # Standalone:
    python -m pipelines.limitless_tcg_events [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from pipelines.import_common import setup_logging

logger = setup_logging("collectai.limitless_tcg")

from pipelines.newsletter_scraper import ScrapedEvent, EventUpserter

API_BASE = "https://play.limitlesstcg.com/api"
USER_AGENT = "CollectAI/1.0 (https://collectai.app; contact@collectai.app)"
MIN_PLAYERS = 16  # Skip tiny local events — filters out noise

# Map Limitless game codes (verified 2026-04-14) to our category IDs
GAME_CATEGORY_MAP = {
    "PTCG": "pokemon",         # Pokemon TCG (main)
    "POCKET": "pokemon",        # Pokemon TCG Pocket (mobile)
    "VGC": "pokemon",           # Pokemon VGC (video game competitive)
    "PTCGL": "pokemon",         # Pokemon TCG Live (digital)
    "OP": "one_piece_tcg",     # One Piece TCG
    "DCG": "digimon",           # Digimon Card Game
    "GUNDAM": "gunpla",         # Gundam Card Game
    "MTG": "mtg",
    "YGO": "yugioh",
    "LOR": "lorcana",
}


async def _fetch_tournaments(client: httpx.AsyncClient, game: str | None = None) -> list[dict[str, Any]]:
    """Fetch tournaments from Limitless API."""
    url = f"{API_BASE}/tournaments"
    params = {"limit": 100}
    if game:
        params["game"] = game

    try:
        resp = await client.get(
            url, params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=15.0,
        )
        if resp.status_code != 200:
            logger.warning("Limitless API returned %d for game=%s", resp.status_code, game)
            return []
        return resp.json()
    except Exception as e:
        logger.warning("Limitless fetch failed for game=%s: %s", game, e)
        return []


def _tournament_to_event(tournament: dict[str, Any]) -> ScrapedEvent | None:
    """Convert a Limitless tournament record to a ScrapedEvent."""
    name = tournament.get("name", "").strip()
    if not name:
        return None

    game = tournament.get("game", "")
    category_id = GAME_CATEGORY_MAP.get(game)
    if not category_id:
        return None  # Unknown game — skip

    # Filter tiny events
    players = tournament.get("players", 0)
    if isinstance(players, int) and players < MIN_PLAYERS:
        return None

    date_raw = tournament.get("date", "")
    if not date_raw:
        return None

    # Limitless returns ISO 8601 — extract YYYY-MM-DD
    try:
        dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Measured 2026-08-22: the API always sends `...T18:30:00.000Z`, so this is
    # aware in practice. A DATE-ONLY string would parse naive, and comparing a
    # naive datetime to an aware `now` raises TypeError — which would kill this
    # row's parse rather than skip it. The previous `(now - dt)` had the same
    # exposure; assume UTC rather than carry it forward.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # UPCOMING ONLY — which is what the module docstring has always claimed and
    # what the code did NOT do.
    #
    # The old rule was `(now - dt) > 3 days -> skip`, i.e. "not more than three
    # days stale". It never required the tournament to be in the FUTURE, so it
    # admitted everything that had already happened within the window.
    #
    # Measured 2026-08-22 on prod: all 1,986 `source='limitless_tcg'` rows were
    # ALREADY PAST at the moment they were inserted — average -12.3 hours, zero
    # of them even a day ahead. That is 70% of the events table, none of it ever
    # eligible for a "what's on" feed. For contrast, ticketmaster averages +62
    # days of lead time, seatgeek +56, newsletter +45.
    #
    # ⚠️ This filter will now admit approximately NOTHING, and that is the
    # honest outcome rather than a regression: the Limitless API is a RESULTS
    # feed, not a schedule. Measured the same day, /api/tournaments returned
    # 60 rows and 0 future ones, and `?upcoming=true`, `?status=upcoming` and
    # `?type=upcoming` all returned 20 rows with 0 future. There is no upcoming
    # endpoint to point at.
    #
    # Left wired rather than deleted so that the day Limitless starts
    # publishing scheduled tournaments this picks them up — but if it is still
    # writing zero rows in a month, delete the pipeline instead of carrying a
    # source that cannot serve the feature.
    now = datetime.now(timezone.utc)
    if dt < now:
        return None

    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M")

    tournament_id = tournament.get("id", "")
    source_url = f"https://play.limitlesstcg.com/tournament/{tournament_id}" if tournament_id else None

    fmt = tournament.get("format") or ""
    description_parts = [f"{players} players"]
    if fmt:
        description_parts.append(f"Format: {fmt}")
    description = " · ".join(description_parts)

    return ScrapedEvent(
        title=f"{name} ({game})"[:200],
        kind="meetup",  # tournaments are scheduled player gatherings
        category_id=category_id,
        date=date_str,
        time=time_str,
        end_date=None,
        location=None,
        online_url=source_url,
        description=description,
        source_url=source_url,
        image_url=None,
    )


async def run_limitless_scraper(dry_run: bool = False) -> list[ScrapedEvent]:
    """Fetch upcoming TCG tournaments from Limitless."""
    all_events: list[ScrapedEvent] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient() as client:
        # Query each game code separately to ensure full coverage
        for game in GAME_CATEGORY_MAP:
            tournaments = await _fetch_tournaments(client, game=game)
            logger.info("Limitless game=%s: %d tournaments", game, len(tournaments))
            for t in tournaments:
                tid = t.get("id")
                if tid in seen_ids:
                    continue
                seen_ids.add(tid)
                event = _tournament_to_event(t)
                if event:
                    all_events.append(event)

    logger.info("Limitless: %d unique events across %d games", len(all_events), len(GAME_CATEGORY_MAP))

    if not dry_run and all_events:
        upserter = EventUpserter()
        try:
            await upserter.upsert_events(all_events, source="limitless_tcg")
            upserter.print_stats()
        except Exception as e:
            logger.warning("Limitless upsert failed: %s", e)
        finally:
            upserter.close()

    return all_events


def main() -> None:
    parser = argparse.ArgumentParser(description="Limitless TCG tournament scraper")
    parser.add_argument("--dry-run", action="store_true", help="Parse without DB writes")
    args = parser.parse_args()

    logger.info("Starting Limitless TCG scraper (dry_run=%s)", args.dry_run)
    events = asyncio.run(run_limitless_scraper(dry_run=args.dry_run))
    logger.info("Done: %d events", len(events))


if __name__ == "__main__":
    main()
