#!/usr/bin/env python3
"""Search gap worker — turns 0-result user searches into catalog candidates.

Reads `demand_signals` rows with `signal_type='search_query'` and finds queries
that don't match any existing `category_items` (likely searched-for items we
don't carry yet). Aggregates by normalized query text and writes to
`category_candidates` so admin can see what to add to the catalog next.

Closes the loop:
  user search → demand_signals → search_gap_worker → category_candidates
  → admin promotes → catalog_items → search returns hits

Without this consumer, search queries pile up in `demand_signals` but never
inform what gets added to the catalog. Schema for `category_candidates`
already exists from the catalog_learning workflow; this worker fills the
"discovery" half that catalog_learning_worker doesn't touch (that one
handles user-suggested categories with a name; this one handles the
search-text inference signal).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

import asyncpg

from app.worker_registry import record_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [search_gap] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")

LOOKBACK_DAYS = int(os.getenv("SEARCH_GAP_LOOKBACK_DAYS", "30"))
MIN_USERS = int(os.getenv("SEARCH_GAP_MIN_USERS", "2"))
MIN_SEARCHES = int(os.getenv("SEARCH_GAP_MIN_SEARCHES", "3"))


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9\s_-]", "", name.lower().strip())
    return re.sub(r"[\s-]+", "_", s).strip("_")[:64]


async def run_once() -> dict[str, int]:
    if not DSN:
        logger.warning("DB_DSN not set — skipping")
        record_run("search_gap_worker", "error")
        return {"new": 0, "updated": 0}

    conn = await asyncpg.connect(DSN)
    new_count = 0
    updated_count = 0
    try:
        # Find queries with enough volume + diverse users that DON'T match
        # an existing catalog item or alias.
        rows = await conn.fetch(
            """
            WITH q AS (
                SELECT
                    lower(trim(query_text)) AS query,
                    COUNT(*) AS searches,
                    COUNT(DISTINCT user_id) AS unique_users,
                    MIN(created_at) AS first_seen,
                    MAX(created_at) AS last_seen
                FROM public.demand_signals
                WHERE signal_type = 'search_query'
                  AND query_text IS NOT NULL
                  AND length(trim(query_text)) BETWEEN 3 AND 80
                  AND created_at >= now() - ($1 || ' days')::interval
                GROUP BY 1
                HAVING COUNT(*) >= $2
                   AND COUNT(DISTINCT user_id) >= $3
            )
            SELECT q.query, q.searches, q.unique_users, q.first_seen, q.last_seen
            FROM q
            WHERE NOT EXISTS (
                -- Skip if this query already matches a catalog item
                SELECT 1 FROM public.category_items ci
                WHERE lower(ci.title) = q.query
                   OR lower(ci.item_key) = q.query
                LIMIT 1
            )
            ORDER BY q.searches DESC
            LIMIT 200
            """,
            LOOKBACK_DAYS, MIN_SEARCHES, MIN_USERS,
        )

        if not rows:
            logger.info("No search-gap candidates this cycle")
            record_run("search_gap_worker", "ok")
            return {"new": 0, "updated": 0}

        for r in rows:
            slug = _slugify(r["query"])
            if not slug:
                continue
            # Upsert by proposed_slug — bump signal_count + unique_users +
            # last_seen if already present, else insert pending.
            result = await conn.fetchrow(
                """
                INSERT INTO public.category_candidates
                    (proposed_name, proposed_slug, description,
                     signal_count, unique_users, first_seen, last_seen, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')
                ON CONFLICT (proposed_slug) DO UPDATE
                SET signal_count = GREATEST(public.category_candidates.signal_count, EXCLUDED.signal_count),
                    unique_users = GREATEST(public.category_candidates.unique_users, EXCLUDED.unique_users),
                    last_seen = GREATEST(public.category_candidates.last_seen, EXCLUDED.last_seen)
                RETURNING (xmax = 0) AS inserted
                """,
                r["query"][:200],
                slug,
                f"Search-gap candidate: {r['searches']} searches by {r['unique_users']} users in last {LOOKBACK_DAYS}d",
                r["searches"],
                r["unique_users"],
                r["first_seen"],
                r["last_seen"],
            )
            if result and result["inserted"]:
                new_count += 1
            else:
                updated_count += 1

        logger.info(
            "search_gap cycle complete: new=%d updated=%d (lookback=%dd, min_users=%d, min_searches=%d)",
            new_count, updated_count, LOOKBACK_DAYS, MIN_USERS, MIN_SEARCHES,
        )
        record_run("search_gap_worker", "ok")
        return {"new": new_count, "updated": updated_count}
    finally:
        await conn.close()


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("search_gap_worker", "error")
        logger.exception("search_gap_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
