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
        logger.info("DB: creating asyncpg connection pool")
        _pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=10)
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
