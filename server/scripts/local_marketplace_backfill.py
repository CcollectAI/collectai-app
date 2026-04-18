#!/usr/bin/env python3
"""Laptop-side marketplace backfill for zero-coverage categories.

The bake's marketplace_scrape_worker round-robins through the catalog at a
fixed rate; categories like whiskey, anime_figures, ghibli (1000+ items each)
take weeks to cycle through. This script lets you pull comps for a target
category right now from the laptop, writing through the same persistence path
the bake uses (so dedup + item_ref prefix + price_eur normalization all apply).

Usage:
    python -m server.scripts.local_marketplace_backfill \
        --category whiskey --limit 50 --concurrency 2

    # All 15 zero-coverage categories, 25 items each:
    python -m server.scripts.local_marketplace_backfill \
        --zero-coverage --limit 25

Requires DB_DSN in environment (or sourced from ../.env). Uses the same
MarketplaceAgent, adapters, and circuit breakers as the bake.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [backfill] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Categories with Ridge models trained but 0% prediction coverage (2026-04-18).
ZERO_COVERAGE_CATEGORIES = [
    "anime_figures", "whiskey", "ghibli", "vintage_toys", "anime_bluray",
    "keycaps", "sportscards", "sneakers", "marvel_legends", "oop_board_games",
    "action_figures", "comic_books", "pens", "digimon", "vinyl_records",
]


async def _fetch_unscraped_items(
    conn: asyncpg.Connection,
    category: str,
    limit: int,
) -> list[dict]:
    """Return category_items that have no recent market_hits or never scraped."""
    rows = await conn.fetch(
        """
        SELECT ci.category, ci.item_key, ci.title, ci.brand
        FROM public.category_items ci
        WHERE ci.category = $1
          AND (ci.last_scrape_attempt_at IS NULL
               OR ci.last_scrape_attempt_at < now() - interval '7 days')
        ORDER BY ci.last_scrape_attempt_at NULLS FIRST, ci.created_at
        LIMIT $2
        """,
        category, limit,
    )
    return [dict(r) for r in rows]


async def _backfill_one_category(
    agent, conn, category: str, limit: int, sem: asyncio.Semaphore,
) -> tuple[int, int]:
    items = await _fetch_unscraped_items(conn, category, limit)
    if not items:
        logger.info("[%s] no items to scrape (all recently attempted)", category)
        return (0, 0)

    logger.info("[%s] scraping %d items", category, len(items))
    found = 0
    persisted = 0

    for it in items:
        async with sem:
            query = it["title"] or it["item_key"]
            try:
                result = await agent.find_sold_comps(
                    query=query,
                    category=category,
                    max_results=10,
                )
                hit_count = len(result.hits) if result and hasattr(result, "hits") else 0
                found += hit_count

                if hit_count > 0:
                    normalized_key = f"{category}:{it['item_key']}"
                    n_persisted = await agent.persist_comps_to_db(
                        result, normalized_key=normalized_key,
                    )
                    persisted += n_persisted or 0
                    logger.info(
                        "[%s] %s: %d hits, %d persisted",
                        category, it["item_key"][:40], hit_count, n_persisted or 0,
                    )

                # Update last_scrape_attempt_at so round-robin skips this for 7d
                await conn.execute(
                    "UPDATE public.category_items "
                    "SET last_scrape_attempt_at = now() "
                    "WHERE category = $1 AND item_key = $2",
                    category, it["item_key"],
                )
            except Exception as e:
                logger.warning("[%s] %s: scrape failed: %s", category, it["item_key"], e)

    return (found, persisted)


async def run(categories: list[str], limit: int, concurrency: int) -> int:
    dsn = os.getenv("DB_DSN")
    if not dsn:
        logger.error("DB_DSN not set. Source ../.env first.")
        return 1

    from app.agents.marketplace_agent import MarketplaceAgent

    agent = MarketplaceAgent()
    conn = await asyncpg.connect(dsn)
    sem = asyncio.Semaphore(concurrency)

    try:
        total_found = 0
        total_persisted = 0
        for cat in categories:
            found, persisted = await _backfill_one_category(
                agent, conn, cat, limit, sem,
            )
            total_found += found
            total_persisted += persisted

        logger.info(
            "BACKFILL DONE: %d hits found, %d persisted across %d categories",
            total_found, total_persisted, len(categories),
        )
        return 0
    finally:
        await conn.close()
        try:
            await agent.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", help="Single category to backfill")
    parser.add_argument("--zero-coverage", action="store_true",
                        help="Backfill all 15 documented zero-coverage categories")
    parser.add_argument("--limit", type=int, default=25,
                        help="Max items per category (default: 25)")
    parser.add_argument("--concurrency", type=int, default=2,
                        help="Parallel scrapes (default: 2; keep low to stay under adapter rate limits)")
    args = parser.parse_args()

    if args.zero_coverage:
        categories = ZERO_COVERAGE_CATEGORIES
    elif args.category:
        categories = [args.category]
    else:
        parser.error("pass --category <name> or --zero-coverage")

    rc = asyncio.run(run(categories, args.limit, args.concurrency))
    sys.exit(rc)


if __name__ == "__main__":
    main()
