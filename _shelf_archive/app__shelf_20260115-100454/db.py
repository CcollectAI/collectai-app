"""
Stub DB layer for collectors backend.

main.py expects:
    from app.db import connect_pool, close_pool, db_configured

For now we run in 'DB disabled' mode:
- db_configured() always returns False
- connect_pool() / close_pool() are async no-ops

This matches the DB-optional setup described in the progress docs.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI  # only for type hints, not strictly required

logger = logging.getLogger(__name__)


class _DummyPool:
    async def close(self) -> None:
        logger.info("DB stub: closing dummy pool")


_pool: Optional[_DummyPool] = None


def db_configured() -> bool:
    """
    Return False to indicate 'no real DB configured'.

    main.py can then skip DB-dependent features, but the app still boots.
    """
    return False


async def connect_pool(app: Optional[FastAPI] = None) -> None:
    """
    Async no-op for startup hooks.
    """
    global _pool
    logger.info("DB stub: connect_pool() called; no DB connection will be created")
    _pool = _DummyPool()


async def close_pool(app: Optional[FastAPI] = None) -> None:
    """
    Async no-op for shutdown hooks.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
    _pool = None
