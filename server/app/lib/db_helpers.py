"""Shared database helpers used across routers."""

import logging
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
