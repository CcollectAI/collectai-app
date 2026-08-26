#!/usr/bin/env python3
"""CLI wrapper around `workers.lorcast_worker.run_once`.

The write logic used to live HERE, and was run by hand exactly once
(2026-08-15). It moved to `server/workers/lorcast_worker.py` on 2026-08-26 when
it became a scheduled bake worker — see that module's header for why the direct
DSN is the right path and what the two dated deadlines were.

This file stays because a manual re-run is genuinely useful (backfilling after
an outage, or forcing a refresh without waiting for the daily cycle). It must
never grow a second copy of the SQL: one implementation, two entry points.

Usage:  python3 server/scripts/load_lorcana_direct.py [--batch 200]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=200)
    args = ap.parse_args()

    # basicConfig belongs to the CLI, not to the module. At module scope it
    # reconfigured the ROOT logger for whatever imported it — which, now that
    # the bake imports this code, would have re-pointed logging for the entire
    # server process as a side effect of scheduling one worker.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [load_lorcana] %(levelname)s: %(message)s",
    )

    from workers.lorcast_worker import run_once

    try:
        summary = await run_once(batch=args.batch)
    except Exception as exc:
        logging.getLogger(__name__).error("lorcast load failed: %r", exc)
        return 1
    logging.getLogger(__name__).info("lorcast load: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
