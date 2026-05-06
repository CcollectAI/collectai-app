#!/usr/bin/env python3
"""ExecStop hook: pg_cancel_backend bake's in-flight queries before SIGTERM.

Closes the orphan-on-restart category. Without this hook, when bake is
restarted (deploy, systemd auto-restart, manual stop), any worker query
in flight stays alive in PG until its statement_timeout fires — bounded
to 600s/1800s by recent worker changes, but still enough to starve the
new bake's workers if they collide with the orphans on the pool.

Identification: workers tagged via `app.lib.db_helpers.tagged_direct_connect`
set `application_name = 'collectai-bake-{worker_name}'`. This script finds
those backends and issues a graceful pg_cancel_backend (NOT
pg_terminate_backend — graceful only, per
`feedback_dont_terminate_active_queries_in_prod.md`).

Idempotent. Safe to run repeatedly. Best-effort: a connect failure or PG
side error logs and exits 0 so it never blocks the systemd stop sequence.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cancel_bake_queries] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# How long to wait for the cancel sweep itself. Capped low so a degraded
# DB doesn't make us hang past the systemd TimeoutStopSec window.
SWEEP_TIMEOUT_S = 10.0


async def _sweep() -> None:
    import asyncpg

    dsn = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
    if not dsn:
        logger.warning("DB_DSN_DIRECT/DB_DSN not set — nothing to cancel")
        return

    try:
        conn = await asyncio.wait_for(asyncpg.connect(dsn, timeout=5), timeout=6)
    except Exception as e:
        logger.warning("could not connect to DB to cancel orphans: %s", e)
        return

    try:
        await conn.execute("SET statement_timeout = '5s'")
        rows = await conn.fetch(
            """
            SELECT pid, application_name, state,
                   EXTRACT(EPOCH FROM (now() - query_start))::int AS age_s
            FROM pg_stat_activity
            WHERE application_name LIKE 'collectai-bake-%'
              AND state = 'active'
            """
        )
        if not rows:
            logger.info("no active collectai-bake-* backends to cancel")
            return

        for r in rows:
            try:
                cancelled = await conn.fetchval(
                    "SELECT pg_cancel_backend($1)", r["pid"]
                )
                logger.info(
                    "pg_cancel_backend(%s) [%s, age=%ss] -> %s",
                    r["pid"], r["application_name"], r["age_s"], cancelled,
                )
            except Exception as e:
                logger.warning("cancel of pid=%s failed: %s", r["pid"], e)
    finally:
        try:
            await conn.close()
        except Exception:
            pass


async def _main() -> None:
    try:
        await asyncio.wait_for(_sweep(), timeout=SWEEP_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning("cancel sweep exceeded %.0fs — exiting", SWEEP_TIMEOUT_S)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except Exception as e:
        # Never block bake's stop sequence with an unhandled exception.
        logger.warning("cancel sweep crashed: %s", e)
    sys.exit(0)
