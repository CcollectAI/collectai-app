"""
Event enrichment — franchise tagging and geocoding.

Runs after event ingestion to:
  1. Tag events with franchise_id based on title/description content matching
  2. Geocode event locations to lat/lon using Nominatim (OpenStreetMap, free)

Usage:
    from pipelines.event_enrich import enrich_events
    await enrich_events()
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import asyncpg
import httpx

logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# ---------------------------------------------------------------------------
# Franchise detection patterns
# ---------------------------------------------------------------------------

# Maps franchise_id -> list of keywords/patterns to match in title/description
FRANCHISE_PATTERNS: dict[str, list[str]] = {
    "star_wars": [
        "star wars", "darth vader", "mandalorian", "lightsaber", "jedi",
        "sith", "boba fett", "grogu", "baby yoda", "ahsoka", "clone wars",
        "galactic", "stormtrooper", "skywalker", "rebel", "empire strikes",
    ],
    "marvel": [
        "marvel", "avengers", "spider-man", "spiderman", "x-men", "xmen",
        "iron man", "captain america", "thor", "hulk", "deadpool",
        "wolverine", "black panther", "guardians of the galaxy", "mcu",
    ],
    "dc": [
        "dc comics", "batman", "superman", "wonder woman", "justice league",
        "joker", "aquaman", "flash", "harley quinn", "gotham",
    ],
    "harry_potter": [
        "harry potter", "wizarding world", "hogwarts", "dumbledore",
        "voldemort", "fantastic beasts", "quidditch", "hermione",
    ],
    "pokemon_franchise": [
        "pokemon", "pokémon", "pikachu", "charizard", "nintendo pokemon",
        "pokemon center", "pokemon tcg",
    ],
    "dragon_ball": [
        "dragon ball", "dragonball", "goku", "vegeta", "saiyan", "dbz",
    ],
    "one_piece_franchise": [
        "one piece", "luffy", "straw hat", "pirate king",
    ],
    "ghibli_franchise": [
        "studio ghibli", "ghibli", "miyazaki", "totoro", "spirited away",
        "howl's moving castle", "princess mononoke",
    ],
    "gundam_franchise": [
        "gundam", "gunpla", "mobile suit", "bandai gundam",
    ],
    "lotr": [
        "lord of the rings", "lotr", "tolkien", "middle-earth", "middle earth",
        "hobbit", "gandalf", "frodo", "mordor", "rings of power",
    ],
    "star_trek": [
        "star trek", "starfleet", "enterprise ncc", "picard", "spock",
        "kirk", "federation", "klingon",
    ],
    "disney_franchise": [
        "disney", "disneyland", "disney world", "disney parks", "pixar",
        "walt disney", "mickey mouse",
    ],
    "taylor_swift_franchise": [
        "taylor swift", "eras tour", "swiftie", "tortured poets",
        "midnights", "folklore", "1989",
    ],
}


def _detect_franchise(title: str, description: str | None) -> str | None:
    """Detect franchise from event title and description."""
    text = (title + " " + (description or "")).lower()
    best_match: str | None = None
    best_count = 0

    for franchise_id, patterns in FRANCHISE_PATTERNS.items():
        count = sum(1 for p in patterns if p in text)
        if count > best_count:
            best_count = count
            best_match = franchise_id

    return best_match if best_count >= 1 else None


# ---------------------------------------------------------------------------
# Geocoding (Nominatim / OpenStreetMap — free, 1 req/sec)
# ---------------------------------------------------------------------------

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GEOCODE_USER_AGENT = "CollectAI/1.0 (collectai.app)"
_geocode_cache: dict[str, Optional[tuple[float, float]]] = {}


async def _geocode_location(location: str) -> Optional[tuple[float, float]]:
    """
    Convert a location string to (lat, lon) using Nominatim.
    Caches results to avoid duplicate requests. Respects 1 req/sec rate limit.
    """
    if not location or len(location) < 3:
        return None

    # Normalize for cache
    cache_key = location.strip().lower()
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                NOMINATIM_URL,
                params={
                    "q": location,
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 0,
                },
                headers={"User-Agent": GEOCODE_USER_AGENT},
            )

            if resp.status_code == 200:
                results = resp.json()
                if results:
                    lat = float(results[0]["lat"])
                    lon = float(results[0]["lon"])
                    _geocode_cache[cache_key] = (lat, lon)
                    return (lat, lon)

        _geocode_cache[cache_key] = None
        return None

    except Exception as e:
        logger.debug("Geocode failed for '%s': %s", location[:50], e)
        _geocode_cache[cache_key] = None
        return None


# ---------------------------------------------------------------------------
# Main enrichment
# ---------------------------------------------------------------------------


async def enrich_events(
    limit: int = 200,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Enrich events with franchise tags and geocoded coordinates.

    Processes events that are missing franchise_id or lat/lon.
    Returns dict with counts: {"franchise_tagged": N, "geocoded": N}
    """
    if not DSN:
        logger.warning("DB_DSN not set, skipping enrichment")
        return {"franchise_tagged": 0, "geocoded": 0}

    conn = await asyncpg.connect(DSN)
    stats = {"franchise_tagged": 0, "geocoded": 0}

    try:
        # 1. Franchise tagging — find events without franchise_id
        rows = await conn.fetch(
            """
            SELECT id, title, description
            FROM public.events
            WHERE franchise_id IS NULL
              AND date >= now() - interval '90 days'
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )

        for row in rows:
            franchise = _detect_franchise(row["title"] or "", row["description"])
            if franchise and not dry_run:
                await conn.execute(
                    "UPDATE public.events SET franchise_id = $1 WHERE id = $2",
                    franchise,
                    row["id"],
                )
                stats["franchise_tagged"] += 1

        logger.info("Franchise tagging: %d events tagged", stats["franchise_tagged"])

        # 2. Geocoding — find events with location but no lat/lon
        geo_rows = await conn.fetch(
            """
            SELECT id, location
            FROM public.events
            WHERE location IS NOT NULL
              AND location != ''
              AND latitude IS NULL
              AND date >= now() - interval '90 days'
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )

        for row in geo_rows:
            coords = await _geocode_location(row["location"])
            if coords and not dry_run:
                lat, lon = coords
                await conn.execute(
                    "UPDATE public.events SET latitude = $1, longitude = $2 WHERE id = $3",
                    lat, lon, row["id"],
                )
                stats["geocoded"] += 1

            # Rate limit: 1 request per second for Nominatim
            await asyncio.sleep(1.1)

        logger.info("Geocoding: %d events geocoded", stats["geocoded"])

    finally:
        await conn.close()

    return stats


async def main():
    stats = await enrich_events()
    print(f"Enrichment: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
