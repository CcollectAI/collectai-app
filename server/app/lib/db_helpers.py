"""Shared database helpers used across routers."""

import logging
import os
from typing import Any

_log = logging.getLogger(__name__)


def get_db_pool() -> Any:
    """Get the database connection pool, or None if unavailable."""
    try:
        from app.db import get_pool
        return get_pool()
    except Exception:
        _log.exception("Failed to get database pool")
        return None


# ── Tagged direct connections ────────────────────────────────────────────
# Workers that open a direct asyncpg connection (DB_DSN_DIRECT, bypassing
# the pooler) should use `tagged_direct_connect(name)` instead of raw
# `asyncpg.connect(dsn)`.
#
# Tagging stamps each backend with `application_name='collectai-bake-{name}'`
# so the ExecStop hook (`scripts/cancel_bake_queries.py`) can identify
# which active queries belong to this bake and `pg_cancel_backend` them
# at restart, instead of leaving multi-hour orphans behind.
#
# The 2026-05-04 incident: a pre-restart auction_alert query (PID
# 2285378) ran for 3h+ as an orphan, holding pool capacity and starving
# every other worker. Tagging + cancel hook eliminates this category.
async def tagged_direct_connect(name: str, *, timeout: float = 30.0):
    """Open a direct asyncpg connection tagged with the worker name.

    `name` should match the worker's manifest entry (e.g. 'valuation_worker'),
    not a free-form string — the cancel script looks for this exact prefix.

    Returns an asyncpg connection. Caller is responsible for closing it.
    """
    import asyncpg
    dsn = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
    if not dsn:
        raise RuntimeError("DB_DSN_DIRECT (or DB_DSN) must be set")
    return await asyncpg.connect(
        dsn,
        timeout=timeout,
        server_settings={"application_name": f"collectai-bake-{name}"},
    )
