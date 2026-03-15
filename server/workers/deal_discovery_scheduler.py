#!/usr/bin/env python3
"""Scheduler that runs deal_discovery_worker.run_once() on a configurable interval.

Configuration via environment variables:
  DEAL_SCAN_INTERVAL_SECS  — seconds between runs (default 1800 = 30 min)
  DB_DSN                   — database connection string (required by the worker)

Usage:
  python -m workers.deal_discovery_scheduler
"""

import asyncio
import logging
import os
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [deal_discovery_scheduler] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL_SECS = int(os.getenv("DEAL_SCAN_INTERVAL_SECS", "3600"))

# Graceful shutdown
_shutdown = False
_shutdown_event = asyncio.Event()


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down after current cycle", signum)
    _shutdown = True
    _shutdown_event.set()


_running = False  # Overlap guard


async def scheduler_loop():
    """Run the deal discovery worker in a loop with a configurable interval."""
    global _running
    from workers.deal_discovery_worker import run_once
    from workers.retry import log_dead_letter

    logger.info(
        "Deal discovery scheduler started (interval=%ds)",
        INTERVAL_SECS,
    )

    while not _shutdown:
        if _running:
            logger.warning("Previous cycle still running, skipping this tick")
        else:
            _running = True
            try:
                logger.info("Starting deal discovery cycle")
                await run_once()
                logger.info("Cycle finished, sleeping %ds", INTERVAL_SECS)
            except Exception as e:
                log_dead_letter("deal_discovery_scheduler", {}, e)
                logger.exception("Deal discovery cycle failed: %r", e)
            finally:
                _running = False

        # Wait for shutdown signal or interval timeout
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=INTERVAL_SECS)
            break  # shutdown was signaled
        except asyncio.TimeoutError:
            pass  # normal timeout, continue to next iteration

    logger.info("Deal discovery scheduler stopped")


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not os.getenv("DB_DSN"):
        logger.error("DB_DSN not set in environment — cannot start scheduler")
        sys.exit(1)

    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
