#!/usr/bin/env python3
"""Scheduler that runs catalog_crawler_worker.run_once() on a configurable interval.

Default: once per day (86400 seconds). In pre-launch seeding mode, can be set
to run every 4 hours to fill the database faster.

Configuration via environment variables:
  CATALOG_CRAWLER_INTERVAL_SECS  — seconds between runs (default 86400 = daily)
  DB_DSN                         — database connection string (required)

Usage:
  python -m workers.catalog_crawler_scheduler
"""

import asyncio
import logging
import os
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [catalog_crawler_scheduler] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL_SECS = int(os.getenv("CATALOG_CRAWLER_INTERVAL_SECS", "86400"))

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down after current cycle", signum)
    _shutdown = True


_running = False


async def scheduler_loop():
    """Run the catalog crawler worker in a loop with a configurable interval."""
    global _running
    from workers.catalog_crawler_worker import run_once
    from workers.retry import log_dead_letter

    logger.info(
        "Catalog crawler scheduler started (interval=%ds)", INTERVAL_SECS,
    )

    while not _shutdown:
        if _running:
            logger.warning("Previous cycle still running, skipping this tick")
        else:
            _running = True
            try:
                logger.info("Starting catalog crawler cycle")
                await run_once()
                logger.info("Cycle finished, sleeping %ds", INTERVAL_SECS)
            except Exception as e:
                log_dead_letter("catalog_crawler_scheduler", {}, e)
                logger.exception("Catalog crawler cycle failed: %r", e)
            finally:
                _running = False

        # Sleep in small increments for responsive shutdown
        for _ in range(INTERVAL_SECS):
            if _shutdown:
                break
            await asyncio.sleep(1)

    logger.info("Catalog crawler scheduler stopped")


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not os.getenv("DB_DSN"):
        logger.error("DB_DSN not set in environment — cannot start scheduler")
        sys.exit(1)

    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
