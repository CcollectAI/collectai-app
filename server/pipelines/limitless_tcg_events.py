"""Limitless TCG tournament scraper.

Public JSON API at play.limitlesstcg.com/api/tournaments — no auth required.
Returns upcoming and recent tournaments for Pokemon TCG, Pokemon Pocket, and
potentially other TCGs.

Filters:
- Only upcoming tournaments (date >= now)
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

    # Skip past tournaments (older than 3 days)
    now = datetime.now(timezone.utc)
    if (now - dt).total_seconds() > 3 * 86400:
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
