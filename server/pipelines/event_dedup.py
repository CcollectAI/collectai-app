"""
Cross-source event deduplication.

After multiple scrapers ingest events, this module finds duplicates
(same event from different sources) and merges them by keeping the
richest record and deleting duplicates.

Matching criteria:
  1. Exact date match (same day)
  2. Title similarity > 70% (token overlap / Jaccard)
  3. Same or null category_id

Usage:
    from pipelines.event_dedup import deduplicate_events
    removed = await deduplicate_events()
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone

import asyncpg

logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")


def _normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, strip punctuation, collapse whitespace."""
    t = title.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _token_overlap(a: str, b: str) -> float:
    """Compute Jaccard similarity of word tokens between two strings."""
    tokens_a = set(_normalize_title(a).split())
    tokens_b = set(_normalize_title(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _token_containment(a: str, b: str) -> float:
    """Overlap coefficient: |A∩B| / min(|A|,|B|).

    Jaccard cannot see a title that is a DEGRADED version of another,
    because it divides by the union and so punishes the shorter string.
    Measured on the real pair that survived dedup for months:

        "BTS"  vs  "BTS WORLD TOUR 'ARIRANG' IN EAST RUTHERFORD"
        jaccard     = 1/7 = 0.14   -> under the 0.70 threshold, missed
        containment = 1/1 = 1.00   -> caught

    SeatGeek routinely writes the bare artist name where Ticketmaster
    writes the full billing, so every such concert was stored twice.
    """
    tokens_a = set(_normalize_title(a).split())
    tokens_b = set(_normalize_title(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))


# Vendor precedence for cross-source duplicates, best first. Ticketmaster
# outranks SeatGeek because its titles are consistently the fuller billing
# ("BTS WORLD TOUR 'ARIRANG' IN EAST RUTHERFORD" vs a bare "BTS") and it
# carries images and venue strings more reliably — measured across the 459
# rows that have a location, 2026-07-27. Sources absent from this list fall
# back to the richness heuristic.
_SOURCE_RANK: dict[str, int] = {
    "ticketmaster": 0,
    "seatgeek": 1,
}


def _city_of(location: str | None) -> str:
    """Middle component of "Venue, City, Country", normalised.

    Used to require that two same-day, similarly-titled events are in the
    same place before calling them duplicates — a national tour plays the
    same show in many cities on different dates, but two vendors listing
    one date must agree on the city.
    """
    if not location:
        return ""
    parts = [p.strip() for p in location.split(",")]
    return _normalize_title(parts[1]) if len(parts) >= 2 else ""


async def deduplicate_events(
    similarity_threshold: float = 0.70,
    dry_run: bool = False,
) -> int:
    """
    Find and remove duplicate events across sources.

    Groups events by date, then within each date group finds pairs with
    high title similarity. Keeps the record with the most data (longest
    description, has image, has location) and deletes the other.

    Returns count of removed duplicates.
    """
    if not DSN:
        logger.warning("DB_DSN not set, skipping dedup")
        return 0

    conn = await asyncpg.connect(DSN)
    removed = 0

    try:
        # Fetch recent events (last 60 days) grouped by date
        rows = await conn.fetch(
            """
            SELECT id, title, date, category_id, source, description, image_url, location
            FROM public.events
            WHERE date >= now() - interval '60 days'
              AND status = 'published'
            ORDER BY date, created_at
            """
        )

        if not rows:
            return 0

        # Group by date
        by_date: dict[str, list] = {}
        for row in rows:
            date_key = str(row["date"])[:10] if row["date"] else "unknown"
            by_date.setdefault(date_key, []).append(row)

        ids_to_delete: list = []

        for date_key, group in by_date.items():
            if len(group) < 2:
                continue

            # Compare all pairs within the same date
            seen_merged: set = set()
            for i in range(len(group)):
                if group[i]["id"] in seen_merged:
                    continue
                for j in range(i + 1, len(group)):
                    if group[j]["id"] in seen_merged:
                        continue

                    a = group[i]
                    b = group[j]

                    # Category must match (or one is null)
                    if (
                        a["category_id"]
                        and b["category_id"]
                        and a["category_id"] != b["category_id"]
                    ):
                        continue

                    # Check title similarity.
                    #
                    # Jaccard alone missed every cross-vendor duplicate,
                    # because SeatGeek writes the bare artist name where
                    # Ticketmaster writes the full billing. Containment
                    # catches that, but only apply it ACROSS sources and
                    # in the same city — within one source a short title
                    # that is a subset of a longer one is usually a
                    # genuinely different event (a festival's "Day 1" vs
                    # its "2-DAY VIP" ticket).
                    sim = _token_overlap(a["title"] or "", b["title"] or "")
                    cross_source = (a["source"] or "") != (b["source"] or "")
                    same_city = _city_of(a["location"]) == _city_of(b["location"])
                    if sim < similarity_threshold:
                        if not (cross_source and same_city and _city_of(a["location"])):
                            continue
                        if _token_containment(a["title"] or "", b["title"] or "") < 0.99:
                            continue

                    # Found a duplicate pair. Across vendors the winner is
                    # decided by source precedence, not richness: SeatGeek
                    # rows can carry a longer description and still have a
                    # strictly worse title, and the title is what the user
                    # reads in the feed.
                    def _richness(r):  # noqa: E301
                        score = 0
                        if r["description"]:
                            score += len(r["description"])
                        if r["image_url"]:
                            score += 100
                        if r["location"]:
                            score += 50
                        return score

                    rank_a = _SOURCE_RANK.get((a["source"] or "").lower())
                    rank_b = _SOURCE_RANK.get((b["source"] or "").lower())
                    if rank_a is not None and rank_b is not None and rank_a != rank_b:
                        loser = b if rank_a < rank_b else a
                    elif _richness(a) >= _richness(b):
                        loser = b
                    else:
                        loser = a

                    ids_to_delete.append(loser["id"])
                    seen_merged.add(loser["id"])

        if ids_to_delete and not dry_run:
            # Quarantine rather than DELETE (changed 2026-07-27).
            #
            # Every read path filters status='published', so flipping the
            # status hides the duplicate just as effectively while leaving
            # the row inspectable and restorable. A dedup heuristic that
            # destroys rows is unrecoverable when it is wrong, and this one
            # was demonstrably wrong for months in the other direction —
            # its Jaccard threshold silently matched nothing across vendors.
            # ON DELETE CASCADE on event_attendees also meant a false match
            # took real RSVPs with it.
            for batch_start in range(0, len(ids_to_delete), 50):
                batch = ids_to_delete[batch_start : batch_start + 50]
                await conn.execute(
                    "UPDATE public.events SET status = 'rejected' WHERE id = ANY($1)",
                    batch,
                )
            removed = len(ids_to_delete)
            logger.info("Dedup: quarantined %d duplicate events", removed)
        elif ids_to_delete:
            removed = len(ids_to_delete)
            logger.info("Dedup (dry-run): would quarantine %d duplicates", removed)

    finally:
        await conn.close()

    return removed


async def main():
    removed = await deduplicate_events()
    print(f"Removed {removed} duplicates")


if __name__ == "__main__":
    asyncio.run(main())
