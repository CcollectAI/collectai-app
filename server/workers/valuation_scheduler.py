#!/usr/bin/env python3
"""Scheduler that runs valuation_worker.run_once() on a configurable interval.

The valuation_worker trains Ridge models against market_hits and writes
price_predictions for each category_item. Default: every 6 hours, matching
the worker_registry entry.

Configuration via environment variables:
  VALUATION_INTERVAL_SECS  — seconds between runs (default 21600 = 6h)
  DB_DSN                   — database connection string (required)

Usage:
  python -m workers.valuation_scheduler

Or wire into main.py lifespan via `VALUATION_ENABLED=true` env flag.
"""

import asyncio
import logging
import os
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [valuation_scheduler] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL_SECS = int(os.getenv("VALUATION_INTERVAL_SECS", "21600"))  # 6h

_shutdown = False
_shutdown_event = asyncio.Event()


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down after current cycle", signum)
    _shutdown = True
    _shutdown_event.set()


_running = False


async def scheduler_loop():
    """Run the valuation worker in a loop with a configurable interval."""
    global _running
    from workers.valuation_worker import run_once
    from workers.retry import log_dead_letter

    logger.info(
        "Valuation scheduler started (interval=%ds)", INTERVAL_SECS,
    )

    while not _shutdown:
        if _running:
            logger.warning("Previous valuation cycle still running, skipping this tick")
        else:
            _running = True
            try:
                logger.info("Starting valuation cycle")
                await run_once()
                logger.info("Valuation cycle finished, sleeping %ds", INTERVAL_SECS)
            except Exception as e:
                log_dead_letter("valuation_scheduler", {}, e)
                logger.exception("Valuation cycle failed: %r", e)
            finally:
                _running = False

        # Wait for shutdown signal or interval timeout
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=INTERVAL_SECS)
            break  # shutdown signaled
        except asyncio.TimeoutError:
            pass  # normal timeout, next iteration

    logger.info("Valuation scheduler stopped")


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not os.getenv("DB_DSN"):
        logger.error("DB_DSN not set in environment — cannot start scheduler")
        sys.exit(1)

    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
