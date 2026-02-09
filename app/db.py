"""
DB layer for collectors backend.

main.py expects:
    from app.db import connect_pool, close_pool, db_configured

When DB_ENABLED=true (and DB_DSN is set), provides real asyncpg connections.
Otherwise runs in 'DB disabled' mode with no-ops.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg

from fastapi import FastAPI  # only for type hints, not strictly required

logger = logging.getLogger(__name__)

DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() == "true"
DB_DSN = os.getenv("DB_DSN", "")
DB_POOL_MIN = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
DB_COMMAND_TIMEOUT = float(os.getenv("DB_COMMAND_TIMEOUT", "30"))  # seconds
DB_CONNECT_TIMEOUT = float(os.getenv("DB_CONNECT_TIMEOUT", "10"))  # seconds
DB_IDLE_LIFETIME = float(os.getenv("DB_MAX_IDLE_LIFETIME", "300"))  # seconds


class _DummyPool:
    async def close(self) -> None:
        logger.info("DB stub: closing dummy pool")


_pool: Optional[asyncpg.Pool | _DummyPool] = None


def db_configured() -> bool:
    """
    Return True if DB_ENABLED=true and DB_DSN is set.
    """
    return DB_ENABLED and bool(DB_DSN)


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
        # Fallback: create one-off connection if pool not initialized
        conn = await asyncpg.connect(DB_DSN)
        try:
            yield conn
        finally:
            await conn.close()
    else:
        async with _pool.acquire() as conn:
            yield conn
