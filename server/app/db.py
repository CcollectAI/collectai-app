"""
DB layer for collectors backend.

main.py expects:
    from app.db import connect_pool, close_pool, db_configured

When DB_ENABLED=true (and DB_DSN is set), provides real asyncpg connections.
Otherwise runs in 'DB disabled' mode with no-ops.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg

from fastapi import FastAPI  # only for type hints, not strictly required

from app.config import (
    DB_ENABLED,
    DB_DSN,
    DB_POOL_MIN,
    DB_POOL_MAX,
    DB_COMMAND_TIMEOUT,
    DB_CONNECT_TIMEOUT,
    DB_IDLE_LIFETIME,
)

logger = logging.getLogger(__name__)


class _DummyPool:
    async def close(self) -> None:
        logger.info("DB stub: closing dummy pool")


_pool: Optional[asyncpg.Pool | _DummyPool] = None


def db_configured() -> bool:
    """
    Return True if DB_ENABLED=true and DB_DSN is set.
    """
    return DB_ENABLED and bool(DB_DSN)


async def _init_conn(conn: asyncpg.Connection) -> None:
    """Decode json/jsonb into Python objects instead of raw strings.

    asyncpg returns JSONB as `str` unless a codec is registered, and nothing
    registered one. Every endpoint that hands a JSONB column straight to the
    client therefore serialised a *quoted JSON string*, and the app's property
    access silently read `undefined` off it.

    Measured 2026-08-06: `GET /alerts/trigger-history` returns
    `alert_trigger_history.trigger_value` this way, so `app/alerts.tsx:335`
    (`typeof item.triggerValue?.listing_url === 'string'`) was false for every
    row and the snipe alert's "View on <provider>" button could never render.
    `notification_router.py:430` returns `notification_history.data` the same
    way (no FE consumer today — it reads the `deep_link` text column).

    Fixed here, at the one chokepoint, rather than at each call site: two
    routers had already grown local `isinstance(row[...], str)` guards
    (`alerts_feature_router.py:117`, `provenance_router.py:75`), which is the
    tell that the drift was being patched downstream instead of at the source.
    Those guards keep working — they now take the else branch.
    """
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def connect_pool(app: Optional[FastAPI] = None) -> None:
    """
    Initialize connection pool on startup.
    """
    global _pool
    if db_configured():
        logger.info("DB: creating asyncpg connection pool (max=%d, cmd_timeout=%.0fs)", DB_POOL_MAX, DB_COMMAND_TIMEOUT)
        _pool = await asyncpg.create_pool(
            DB_DSN,
            min_size=DB_POOL_MIN,
            max_size=DB_POOL_MAX,
            command_timeout=DB_COMMAND_TIMEOUT,
            timeout=DB_CONNECT_TIMEOUT,
            max_inactive_connection_lifetime=DB_IDLE_LIFETIME,
            init=_init_conn,
        )
    else:
        logger.info("DB stub: connect_pool() called; no DB connection will be created")
        _pool = _DummyPool()


async def close_pool(app: Optional[FastAPI] = None) -> None:
    """
    Close connection pool on shutdown.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
    _pool = None


def get_pool() -> Optional[asyncpg.Pool]:
    """
    Return the connection pool (or None if not initialized / DB disabled).
    Used by model_loader.py to query model_registry.
    """
    if isinstance(_pool, _DummyPool):
        return None
    return _pool


@asynccontextmanager
async def get_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Context manager for getting a database connection.

    Usage:
        async with get_conn() as conn:
            row = await conn.fetchrow("SELECT ...")

    Raises RuntimeError if DB is not configured.
    """
    if not db_configured():
        raise RuntimeError("Database not configured (DB_ENABLED=false or DB_DSN missing)")

    if _pool is None or isinstance(_pool, _DummyPool):
        # Fallback: create one-off connection if pool not initialized.
        # Must register the same codecs as the pool — otherwise the same
        # request returns dicts or strings depending on whether the pool
        # happened to be up, which is worse than being consistently wrong.
        conn = await asyncpg.connect(DB_DSN)
        await _init_conn(conn)
        try:
            yield conn
        finally:
            await conn.close()
    else:
        async with _pool.acquire() as conn:
            yield conn
