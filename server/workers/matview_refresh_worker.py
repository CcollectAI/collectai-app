#!/usr/bin/env python3
"""
Materialized view refresh worker.

Periodically refreshes data moat materialized views so that
supply trends and demand heat queries return up-to-date data.

Views refreshed:
- mv_supply_trend  (90-day rolling supply snapshots)
- mv_demand_heat   (7-day demand signal aggregates)

Usage:
    python -m workers.matview_refresh_worker          # single run
    MATVIEW_REFRESH_INTERVAL=3600 python -m workers.matview_refresh_worker --loop
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [matview_refresh] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")
INTERVAL_SECS = int(os.getenv("MATVIEW_REFRESH_INTERVAL", "3600"))

MATVIEWS = [
    "public.mv_supply_trend",
    "public.mv_demand_heat",
]

_shutdown = False


def _handle_signal(sig, _frame):
    global _shutdown
    logger.info("Received signal %s, shutting down...", sig)
    _shutdown = True


@with_async_retry(max_retries=2, base_delay=5.0, max_delay=30.0)
async def run_once():
    """Refresh all data moat materialized views."""
    if not DSN:
        logger.warning("DB_DSN not set, skipping matview refresh")
        return

    import asyncpg

    conn = await asyncpg.connect(DSN)
    try:
        refreshed = 0
        for view_name in MATVIEWS:
            try:
                # CONCURRENTLY allows reads during refresh (requires unique index)
                await conn.execute(
                    f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"
                )
                refreshed += 1
                logger.info("Refreshed %s", view_name)
            except Exception as e:
                # Fall back to non-concurrent if unique index missing
                logger.warning(
                    "CONCURRENTLY failed for %s (%s), trying non-concurrent",
                    view_name, e,
                )
                try:
                    await conn.execute(
                        f"REFRESH MATERIALIZED VIEW {view_name}"
                    )
                    refreshed += 1
                    logger.info("Refreshed %s (non-concurrent)", view_name)
                except Exception as e2:
                    logger.error("Failed to refresh %s: %s", view_name, e2)

        logger.info("Matview refresh complete: %d/%d views", refreshed, len(MATVIEWS))
    finally:
        await conn.close()

    record_run("matview_refresh", "ok")


async def scheduler_loop():
    """Run refresh in a loop with configurable interval."""
    while not _shutdown:
        try:
            await run_once()
        except Exception as e:
            record_run("matview_refresh", "error")
            log_dead_letter("matview_refresh", {}, e)
            logger.exception("matview_refresh crashed: %r", e)

        for _ in range(INTERVAL_SECS):
            if _shutdown:
                break
            await asyncio.sleep(1)


async def main():
    if "--loop" in sys.argv:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
        await scheduler_loop()
    else:
        try:
            await run_once()
        except Exception as e:
            record_run("matview_refresh", "error")
            log_dead_letter("matview_refresh", {}, e)
            logger.exception("matview_refresh crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
