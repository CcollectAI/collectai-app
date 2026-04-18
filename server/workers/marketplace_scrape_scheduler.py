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

# Categories that already have >100% coverage via dedicated bulk feeds
# (tcgcsv + scryfall). Including them in this worker's SELECT just means
# 80K+ TCG card items hog the queue and starve thin cats (disney, funko,
# hot_toys etc. were at <2% attempt rate despite running for days).
#
# Coverage snapshot (2026-04-18): pokemon 311%, yugioh 189%, mtg 728%,
# lorcana 651%, one_piece_tcg 817%, digimon 1233%.
SKIP_CATEGORIES = {
    "pokemon",
    "yugioh",
    "mtg",
    "lorcana",
    "one_piece_tcg",
    "digimon",
}

_shutdown = False
_shutdown_event = asyncio.Event()
_started_at = time.time()


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down", signum)
    _shutdown = True
    _shutdown_event.set()


async def _get_stale_items(conn, batch_size: int):
    """Get catalog items due for a scrape attempt.

    Selection policy:
      1. `last_scrape_attempt_at IS NULL`  (never attempted — bootstrap)
      2. Else, oldest `last_scrape_attempt_at` first (round-robin).

    Filter: skip items that already have market_hits within the last 7d
    (no need to re-scrape).

    The `last_scrape_attempt_at` column is bumped after each attempt
    regardless of hit count. Without this, niche items with
    `mh.last_seen IS NULL` (no adapter can find them) kept winning every
    cycle because the old selector ordered by `last_seen NULLS FIRST` —
    see 2026-04-17 incident where 3 consecutive batches returned 0 hits.
    """
    return await conn.fetch("""
        SELECT ci.id, ci.item_key, ci.title, ci.category
        FROM category_items ci
        LEFT JOIN (
            SELECT item_ref, MAX(seen_at) AS last_seen
            FROM market_hits
            GROUP BY item_ref
        ) mh ON mh.item_ref = ci.category || ':' || ci.item_key
        WHERE ci.title IS NOT NULL
          AND ci.category <> ALL($2::text[])
          AND (mh.last_seen IS NULL OR mh.last_seen < NOW() - INTERVAL '7 days')
        ORDER BY ci.last_scrape_attempt_at ASC NULLS FIRST, RANDOM()
        LIMIT $1
    """, batch_size, sorted(SKIP_CATEGORIES))


async def _mark_attempted(conn, item_ids: list) -> None:
    """Bump last_scrape_attempt_at for every item we tried this cycle.

    Called regardless of whether the attempt produced hits — the whole
    point is that niche items don't lock the queue after a zero-hit run.
    category_items.id is uuid; asyncpg handles the coercion from the
    Python-side values returned by fetch() automatically.
    """
    if not item_ids:
        return
    await conn.execute(
        "UPDATE public.category_items "
        "SET last_scrape_attempt_at = NOW() "
        "WHERE id = ANY($1::uuid[])",
        item_ids,
    )


async def _scrape_item(agent, item_key: str, title: str, category: str):
    """Search for a single item using free adapters only, then persist hits."""
    try:
        result = await agent.find_sold_comps(
            query=title,
            category=category,
            limit=20,
        )
        hits = getattr(result, "hits", []) or []
        if not hits:
            return 0
        normalized_key = f"{category}:{item_key}"
        inserted = await agent.persist_comps_to_db(result, normalized_key=normalized_key, category=category)
        logger.info("  %s: %d hits, %d persisted", item_key[:40], len(hits), inserted)
        return inserted
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
        zero_hit_items = 0
        attempted_ids: list[int] = []
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
            if hits == 0:
                zero_hit_items += 1
            attempted_ids.append(row["id"])
            # Small delay to avoid hammering adapters
            await asyncio.sleep(2)

        try:
            await agent.close()
        except Exception:
            pass

        # Bump last_scrape_attempt_at for every item we tried this cycle
        # — even the ones that produced 0 hits. Keeps niche items from
        # re-winning the selector next cycle.
        try:
            await _mark_attempted(conn, attempted_ids)
        except Exception as e:
            logger.warning("Failed to mark items attempted: %s", e)

        # WARN when the whole batch produced nothing — usually a sign that
        # adapter circuits are clustered-open. Appears in grep for "Batch
        # unproductive" so ops can triage quickly.
        if total_hits == 0 and len(items) > 0:
            logger.warning(
                "Batch unproductive: 0 hits from %d items — check adapter circuit state",
                len(items),
            )
        else:
            logger.info(
                "Batch complete: %d items, %d total hits, %d items with 0 hits",
                len(items), total_hits, zero_hit_items,
            )
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
