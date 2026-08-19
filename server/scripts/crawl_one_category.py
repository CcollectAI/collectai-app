#!/usr/bin/env python3
"""Crawl ONE category's catalogue items on demand.

WHY THIS EXISTS
---------------
`catalog_crawler_worker` is deliberately disabled in the bake ("post-launch
features (no users yet)"), and its selection is round-robin across every
category — so a freshly seeded category gets ~3 items per cycle from a worker
that is not running. Seeding a catalogue with nothing to price it produces a
category full of blanks, which is worse than an empty one.

This runs the SAME `_crawl_single_item` the worker uses — not a second
implementation of it — against one category, so a new seed can be priced the
day it lands.

Usage:
    python3 server/scripts/crawl_one_category.py dnd [limit]

Reads DB_DSN from the environment. Rate-limited by the worker's own
CATALOG_CRAWLER_DELAY.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [crawl_one_category] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    category = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    dsn = os.getenv("DB_DSN")
    if not dsn:
        logger.error("DB_DSN not set")
        return 2

    from app.agents.marketplace_agent import MarketplaceAgent
    from workers.catalog_crawler_worker import _crawl_single_item

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT category, item_key, title
            FROM public.category_items
            WHERE category = $1
            ORDER BY last_crawled_at ASC NULLS FIRST, item_key
            LIMIT $2
            """,
            category,
            limit,
        )
        if not rows:
            logger.warning("No catalogue rows for category %s", category)
            return 1

        logger.info("Crawling %d item(s) in %s", len(rows), category)
        agent = MarketplaceAgent()
        # Serial on purpose: this is a manual backfill sharing prod adapters
        # and rate limits with whatever the bake is doing.
        semaphore = asyncio.Semaphore(1)

        ok = 0
        for row in rows:
            try:
                result = await _crawl_single_item(agent, conn, dict(row), semaphore)
                inserted = (result or {}).get("inserted", 0)
                ok += 1
                logger.info("  %-52s hits=%s", row["item_key"][:52], inserted)
            except Exception:
                logger.exception("  %s FAILED", row["item_key"])

        logger.info("Done: %d/%d crawled", ok, len(rows))
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
