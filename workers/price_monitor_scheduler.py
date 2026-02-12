#!/usr/bin/env python3
"""Scheduler that runs price_monitor_worker.run_once() on a configurable interval.

Configuration via environment variables:
  MONITOR_INTERVAL_SECS  — seconds between runs (default 3600 = 1 hour)
  DB_DSN                 — database connection string (required by the worker)

Usage:
  python -m workers.price_monitor_scheduler
"""

import asyncio
import logging
import os
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [price_monitor_scheduler] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL_SECS = int(os.getenv("MONITOR_INTERVAL_SECS", "3600"))

# Graceful shutdown flag
_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down after current cycle", signum)
    _shutdown = True


async def scheduler_loop():
    """Run the price monitor worker in a loop with a configurable interval."""
    # Import here to avoid circular imports and ensure DSN is read at call time
    from workers.price_monitor_worker import run_once
    from workers.retry import log_dead_letter

    logger.info(
        "Price monitor scheduler started (interval=%ds)",
        INTERVAL_SECS,
    )

    while not _shutdown:
        try:
            logger.info("Starting price monitor cycle")
            await run_once()
            logger.info("Cycle finished, sleeping %ds", INTERVAL_SECS)
        except Exception as e:
            log_dead_letter("price_monitor_scheduler", {}, e)
            logger.exception("Price monitor cycle failed: %r", e)

        # Sleep in small increments so we can respond to shutdown quickly
        for _ in range(INTERVAL_SECS):
            if _shutdown:
                break
            await asyncio.sleep(1)

    logger.info("Price monitor scheduler stopped")


def main():
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not os.getenv("DB_DSN"):
        logger.error("DB_DSN not set in environment — cannot start scheduler")
        sys.exit(1)

    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
