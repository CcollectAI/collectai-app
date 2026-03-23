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

                    # Check title similarity
                    sim = _token_overlap(a["title"] or "", b["title"] or "")
                    if sim < similarity_threshold:
                        continue

                    # Found a duplicate pair — keep the richer one
                    def _richness(r):  # noqa: E301
                        score = 0
                        if r["description"]:
                            score += len(r["description"])
                        if r["image_url"]:
                            score += 100
                        if r["location"]:
                            score += 50
                        return score

                    if _richness(a) >= _richness(b):
                        ids_to_delete.append(b["id"])
                        seen_merged.add(b["id"])
                    else:
                        ids_to_delete.append(a["id"])
                        seen_merged.add(a["id"])

        if ids_to_delete and not dry_run:
            # Delete in batches of 50
            for batch_start in range(0, len(ids_to_delete), 50):
                batch = ids_to_delete[batch_start : batch_start + 50]
                await conn.execute(
                    "DELETE FROM public.events WHERE id = ANY($1)",
                    batch,
                )
            removed = len(ids_to_delete)
            logger.info("Dedup: removed %d duplicate events", removed)
        elif ids_to_delete:
            removed = len(ids_to_delete)
            logger.info("Dedup (dry-run): would remove %d duplicates", removed)

    finally:
        await conn.close()

    return removed


async def main():
    removed = await deduplicate_events()
    print(f"Removed {removed} duplicates")


if __name__ == "__main__":
    asyncio.run(main())
