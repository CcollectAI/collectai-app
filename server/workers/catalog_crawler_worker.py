#!/usr/bin/env python3
"""Catalog crawler worker — proactive nightly price ingestion for ALL catalog items.

Iterates category_items rows (stalest first), calls MarketplaceAgent.aggregate_search()
for each, and persists results to market_hits. This feeds the valuation_worker →
price_predictions pipeline so that price data exists BEFORE users search for items.

Configuration via environment variables:
  CATALOG_CRAWLER_BATCH    — items per cycle (default 200)
  CATALOG_CRAWLER_DELAY    — seconds between items to respect rate limits (default 2.0)
  CATALOG_CRAWLER_SOLD     — include sold comps, "1" or "0" (default "1")
  DB_DSN                   — database connection string
"""

import asyncio
import json
import logging
import os
import statistics
from datetime import datetime, timezone

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [catalog_crawler] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# Items to crawl per cycle — balance throughput vs. API load
BATCH_SIZE = int(os.getenv("CATALOG_CRAWLER_BATCH", "200"))

# Delay between items (seconds) to avoid overwhelming adapters
INTER_ITEM_DELAY = float(os.getenv("CATALOG_CRAWLER_DELAY", "2.0"))

# Whether to include sold comps (highest quality price data)
INCLUDE_SOLD = os.getenv("CATALOG_CRAWLER_SOLD", "1") == "1"

# Concurrency: how many items to crawl in parallel (small to respect rate limits)
CONCURRENCY = int(os.getenv("CATALOG_CRAWLER_CONCURRENCY", "3"))


async def _ensure_last_crawled_column(conn) -> bool:
    """Ensure category_items has a last_crawled_at column (idempotent)."""
    try:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'category_items'
                  AND column_name = 'last_crawled_at'
            )
        """)
        if not exists:
            await conn.execute("""
                ALTER TABLE public.category_items
                ADD COLUMN last_crawled_at timestamptz DEFAULT NULL
            """)
            logger.info("Added last_crawled_at column to category_items")
        return True
    except Exception as e:
        logger.warning("Could not ensure last_crawled_at column: %s", e)
        return False


async def _crawl_single_item(
    agent, conn, row: dict, semaphore: asyncio.Semaphore
) -> dict:
    """Crawl a single catalog item and persist results."""
    from app.features.data_moat import record_supply_snapshot

    item_key = row["item_key"]
    category = row["category"]
    title = row["title"] or item_key

    async with semaphore:
        try:
            # Throttle to avoid overwhelming adapters
            await asyncio.sleep(INTER_ITEM_DELAY)

            search_query = title
            result = await agent.aggregate_search(
                query=search_query,
                category=category,
                limit=20,
                include_sold=INCLUDE_SOLD,
            )

            # Persist hits to market_hits (valuation_worker picks these up)
            normalized_key = f"{category}:{item_key}"
            inserted = await agent.persist_comps_to_db(
                result, normalized_key=normalized_key,
            )

            # Extract price stats for supply snapshot
            prices = [
                float(h.hit.get("price", 0))
                for h in result.hits
                if h.hit.get("price") is not None and float(h.hit.get("price", 0)) > 0
            ]

            hit_count = len(result.hits)

            # Record supply snapshot (data moat)
            if prices and category:
                try:
                    await record_supply_snapshot(
                        category=category,
                        item_key=normalized_key,
                        listing_count=hit_count,
                        avg_price_eur=statistics.mean(prices),
                        min_price_eur=min(prices),
                        max_price_eur=max(prices),
                        source="catalog_crawler",
                    )
                except Exception as e:
                    logger.debug("Supply snapshot failed for %s: %s", item_key, e)

            # Update last_crawled_at
            try:
                await conn.execute(
                    """
                    UPDATE public.category_items
                    SET last_crawled_at = $1
                    WHERE category = $2 AND item_key = $3
                    """,
                    datetime.now(timezone.utc),
                    category,
                    item_key,
                )
            except Exception:
                pass  # Column may not exist yet in some environments

            return {
                "item_key": item_key,
                "category": category,
                "hits": hit_count,
                "inserted": inserted,
                "median_price": statistics.median(prices) if prices else None,
                "status": "ok",
            }

        except Exception as e:
            logger.warning(
                "Failed to crawl %s/%s: %s", category, item_key, e,
                exc_info=True,
            )
            return {
                "item_key": item_key,
                "category": category,
                "hits": 0,
                "inserted": 0,
                "median_price": None,
                "status": "error",
                "error": str(e)[:200],
            }


@with_async_retry(max_retries=2, base_delay=5.0, max_delay=120.0)
async def run_once():
    """Execute a single catalog crawling cycle."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        record_run("catalog_crawler_worker", "error")
        return

    from app.agents.marketplace_agent import MarketplaceAgent

    conn = await asyncpg.connect(DSN)
    logger.info("Connected to DB — starting catalog crawler cycle")

    agent = MarketplaceAgent()
    semaphore = asyncio.Semaphore(CONCURRENCY)

    try:
        # Ensure tracking column exists
        await _ensure_last_crawled_column(conn)

        # Fetch catalog items, prioritizing:
        # 1. Never-crawled items (NULL last_crawled_at)
        # 2. Oldest-crawled items
        rows = await conn.fetch(
            """
            SELECT category, item_key, title
            FROM public.category_items
            ORDER BY last_crawled_at ASC NULLS FIRST
            LIMIT $1
            """,
            BATCH_SIZE,
        )

        if not rows:
            logger.info("No catalog items to crawl")
            record_run("catalog_crawler_worker", "ok")
            return

        logger.info(
            "Crawling %d catalog items (batch=%d, delay=%.1fs, concurrency=%d, sold=%s)",
            len(rows), BATCH_SIZE, INTER_ITEM_DELAY, CONCURRENCY, INCLUDE_SOLD,
        )

        # Process items with bounded concurrency
        tasks = [
            _crawl_single_item(agent, conn, dict(row), semaphore)
            for row in rows
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Summarize
        ok_count = 0
        error_count = 0
        total_hits = 0
        total_inserted = 0

        for r in results:
            if isinstance(r, Exception):
                error_count += 1
                logger.warning("Unexpected crawl error: %s", r)
            elif isinstance(r, dict):
                if r["status"] == "ok":
                    ok_count += 1
                    total_hits += r["hits"]
                    total_inserted += r["inserted"]
                else:
                    error_count += 1

        logger.info(
            "Catalog crawler cycle complete: ok=%d errors=%d hits=%d inserted=%d",
            ok_count, error_count, total_hits, total_inserted,
        )

        record_run("catalog_crawler_worker", "ok" if error_count < ok_count else "error")

    finally:
        await agent.close()
        await conn.close()


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("catalog_crawler_worker", "error")
        log_dead_letter("catalog_crawler_worker", {}, e)
        logger.exception("catalog_crawler_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
