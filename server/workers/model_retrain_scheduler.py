#!/usr/bin/env python3
"""Scheduler that runs model_retrain_worker.run_once() on a configurable interval.

Default: once per week (604800 seconds).

Configuration via environment variables:
  MODEL_RETRAIN_INTERVAL_SECS  — seconds between runs (default 604800 = weekly)
  DB_DSN                       — database connection string (required)

Usage:
  python -m workers.model_retrain_scheduler
"""

import asyncio
import logging
import os
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [model_retrain_scheduler] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL_SECS = int(os.getenv("MODEL_RETRAIN_INTERVAL_SECS", "604800"))

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down after current cycle", signum)
    _shutdown = True


_running = False


async def scheduler_loop():
    """Run the model retrain worker in a loop with a configurable interval."""
    global _running
    from workers.model_retrain_worker import run_once
    from workers.retry import log_dead_letter

    logger.info(
        "Model retrain scheduler started (interval=%ds = %.1f days)",
        INTERVAL_SECS,
        INTERVAL_SECS / 86400,
    )

    while not _shutdown:
        if _running:
            logger.warning("Previous cycle still running, skipping this tick")
        else:
            _running = True
            try:
                logger.info("Starting model retrain cycle")
                await run_once()
                logger.info("Cycle finished, sleeping %ds", INTERVAL_SECS)
            except Exception as e:
                log_dead_letter("model_retrain_scheduler", {}, e)
                logger.exception("Model retrain cycle failed: %r", e)
            finally:
                _running = False

        # Sleep in small increments for responsive shutdown
        for _ in range(INTERVAL_SECS):
            if _shutdown:
                break
            await asyncio.sleep(1)

    logger.info("Model retrain scheduler stopped")


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not os.getenv("DB_DSN"):
        logger.error("DB_DSN not set in environment — cannot start scheduler")
        sys.exit(1)

    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
