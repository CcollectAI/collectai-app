#!/usr/bin/env python3
"""Scheduler that runs catalog_learning_worker.run_once() on a configurable interval.

Configuration via environment variables:
  CATALOG_LEARNING_INTERVAL_SECS  — seconds between runs (default 1800 = 30 min)
  DB_DSN                          — database connection string (required by the worker)

Usage:
  python -m workers.catalog_learning_scheduler
"""

import asyncio
import logging
import os
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [catalog_learning_scheduler] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL_SECS = int(os.getenv("CATALOG_LEARNING_INTERVAL_SECS", "86400"))  # daily (was 30 min)

# Graceful shutdown flag
_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down after current cycle", signum)
    _shutdown = True


_running = False  # Overlap guard


async def scheduler_loop():
    """Run the catalog learning worker in a loop with a configurable interval."""
    global _running
    from workers.catalog_learning_worker import run_once
    from workers.retry import log_dead_letter

    logger.info(
        "Catalog learning scheduler started (interval=%ds)",
        INTERVAL_SECS,
    )

    while not _shutdown:
        if _running:
            logger.warning("Previous cycle still running, skipping this tick")
        else:
            _running = True
            try:
                logger.info("Starting catalog learning cycle")
                await run_once()
                logger.info("Cycle finished, sleeping %ds", INTERVAL_SECS)
            except Exception as e:
                log_dead_letter("catalog_learning_scheduler", {}, e)
                logger.exception("Catalog learning cycle failed: %r", e)
            finally:
                _running = False

        # Sleep in small increments so we can respond to shutdown quickly
        for _ in range(INTERVAL_SECS):
            if _shutdown:
                break
            await asyncio.sleep(1)

    logger.info("Catalog learning scheduler stopped")


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not os.getenv("DB_DSN"):
        logger.error("DB_DSN not set in environment — cannot start scheduler")
        sys.exit(1)

    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
