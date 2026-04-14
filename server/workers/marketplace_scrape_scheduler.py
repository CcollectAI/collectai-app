#!/usr/bin/env python3
"""Marketplace scrape scheduler — systematically scrapes catalog items via free adapters.

Iterates through category_items in the catalog and calls MarketplaceAgent.find_sold_comps()
for items that lack recent market_hits. Uses ONLY free adapters (no Firecrawl, Scrape.do,
SerpAPI) to avoid cost during the initial data bake.

Configuration via environment variables:
  MARKETPLACE_SCRAPE_ENABLED   — must be 'true' to start
  MARKETPLACE_SCRAPE_INTERVAL  — seconds between batches (default 300 = 5 min)
  MARKETPLACE_SCRAPE_BATCH     — items per batch (default 10)
  MARKETPLACE_SCRAPE_MAX_DAYS  — auto-shutdown after N days (default 5)
  DB_DSN                       — database connection string (required)

The scheduler auto-disables after MARKETPLACE_SCRAPE_MAX_DAYS days to prevent
ongoing cost from paid adapters post-launch. Set to 0 to disable auto-shutdown.
"""

import asyncio
import datetime
import logging
import os
import signal
import sys
import time

import asyncpg
from app.worker_registry import record_run
from workers.retry import log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [marketplace_scrape] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL = int(os.getenv("MARKETPLACE_SCRAPE_INTERVAL", "300"))  # 5 min
BATCH_SIZE = int(os.getenv("MARKETPLACE_SCRAPE_BATCH", "10"))
MAX_DAYS = int(os.getenv("MARKETPLACE_SCRAPE_MAX_DAYS", "5"))

# Adapters to SKIP (paid per-call)
PAID_ADAPTERS = {"firecrawl", "scrape_do", "serpapi", "google_shopping"}

_shutdown = False
_shutdown_event = asyncio.Event()
_started_at = time.time()


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down", signum)
    _shutdown = True
    _shutdown_event.set()


async def _get_stale_items(conn, batch_size: int):
    """Get catalog items that haven't had market_hits in the last 7 days."""
    return await conn.fetch("""
        SELECT ci.item_key, ci.title, ci.category
        FROM category_items ci
        LEFT JOIN (
            SELECT item_ref, MAX(seen_at) AS last_seen
            FROM market_hits
            GROUP BY item_ref
        ) mh ON mh.item_ref = ci.category || ':' || ci.item_key
        WHERE ci.title IS NOT NULL
          AND (mh.last_seen IS NULL OR mh.last_seen < NOW() - INTERVAL '7 days')
        ORDER BY mh.last_seen ASC NULLS FIRST
        LIMIT $1
    """, batch_size)


async def _scrape_item(agent, item_key: str, title: str, category: str):
    """Search for a single item using free adapters only."""
    try:
        results = await agent.find_sold_comps(
            query=title,
            category=category,
            max_results=20,
        )
        if results:
            logger.info("  %s: %d hits", item_key[:40], len(results))
        return len(results) if results else 0
    except Exception as e:
        logger.warning("  %s: error %s", item_key[:40], e)
        return 0


async def run_once():
    """Execute a single scrape batch."""
    dsn = os.getenv("DB_DSN")
    if not dsn:
        logger.error("DB_DSN not set")
        return 0

    # Auto-shutdown check
    if MAX_DAYS > 0:
        elapsed_days = (time.time() - _started_at) / 86400
        if elapsed_days >= MAX_DAYS:
            logger.info(
                "Auto-shutdown: %d days elapsed (limit=%d). Stopping marketplace scraper.",
                int(elapsed_days), MAX_DAYS,
            )
            global _shutdown
            _shutdown = True
            _shutdown_event.set()
            record_run("marketplace_scrape_worker", "ok")
            return 0

    conn = await asyncpg.connect(dsn)
    try:
        items = await _get_stale_items(conn, BATCH_SIZE)
        if not items:
            logger.info("No stale items to scrape")
            record_run("marketplace_scrape_worker", "ok")
            return 0

        logger.info("Scraping %d stale items", len(items))

        # Lazy import to avoid circular deps at module level
        from app.agents.marketplace_agent import MarketplaceAgent
        agent = MarketplaceAgent()

        # Disable paid adapters
        for adapter_name in PAID_ADAPTERS:
            attr = f"_{adapter_name}_caller"
            if hasattr(agent, attr):
                setattr(agent, attr, None)

        total_hits = 0
        for row in items:
            if _shutdown:
                break
            hits = await _scrape_item(
                agent,
                row["item_key"],
                row["title"],
                row["category"],
            )
            total_hits += hits
            # Small delay to avoid hammering adapters
            await asyncio.sleep(2)

        try:
            await agent.close()
        except Exception:
            pass

        logger.info("Batch complete: %d items, %d total hits", len(items), total_hits)
        record_run("marketplace_scrape_worker", "ok")
        return total_hits

    finally:
        await conn.close()


async def scheduler_loop():
    """Run scrape batches in a loop."""
    logger.info(
        "Marketplace scrape scheduler started (interval=%ds, batch=%d, max_days=%d)",
        INTERVAL, BATCH_SIZE, MAX_DAYS,
    )

    while not _shutdown:
        try:
            await run_once()
        except Exception as e:
            log_dead_letter("marketplace_scrape_scheduler", {}, e)
            logger.exception("Scrape batch failed: %r", e)
            record_run("marketplace_scrape_worker", "error")

        if _shutdown:
            break

        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=INTERVAL)
            break
        except asyncio.TimeoutError:
            pass

    logger.info("Marketplace scrape scheduler stopped")


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not os.getenv("DB_DSN"):
        logger.error("DB_DSN not set — cannot start")
        sys.exit(1)

    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
