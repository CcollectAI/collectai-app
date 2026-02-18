"""
User-scoped database query helpers.

Since asyncpg connections bypass Supabase RLS policies, every user-scoped
query **must** include a ``WHERE user_id = $N`` guard.  The helpers in this
module make that hard to forget.

Usage:
    from app.db_helpers import fetch_for_user, fetchrow_for_user, execute_for_user

    rows = await fetch_for_user(
        conn,
        "SELECT * FROM items WHERE category = $2",
        user_id,
        category,
    )
    # Executes: SELECT * FROM items WHERE user_id = $1 AND (category = $2)

Notes:
    * ``user_id`` is always bound to ``$1``.
    * The caller's query must use placeholders starting from ``$2``.
    * If the query already contains a ``WHERE`` clause, the user_id filter
      is prepended with ``AND``.  If not, a ``WHERE user_id = $1`` clause
      is injected automatically.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Matches "WHERE" (case-insensitive) that is NOT inside quotes.
_WHERE_RE = re.compile(r"\bWHERE\b", re.IGNORECASE)


def _inject_user_filter(query: str, user_id_column: str = "user_id") -> str:
    """Inject ``user_id = $1`` into *query*.

    If the query already has a WHERE clause the filter is added as the first
    condition.  Otherwise a ``WHERE user_id = $1`` is inserted before ORDER BY
    / LIMIT / RETURNING or at the end.
    """
    match = _WHERE_RE.search(query)
    if match:
        # Insert right after WHERE
        pos = match.end()
        return query[:pos] + f" {user_id_column} = $1 AND" + query[pos:]

    # No WHERE — find a suitable injection point
    for kw in ("ORDER BY", "LIMIT", "RETURNING", "GROUP BY", "HAVING"):
        kw_match = re.search(rf"\b{kw}\b", query, re.IGNORECASE)
        if kw_match:
            pos = kw_match.start()
            return query[:pos] + f" WHERE {user_id_column} = $1 " + query[pos:]

    # Append at end
    return query.rstrip().rstrip(";") + f" WHERE {user_id_column} = $1"


async def fetch_for_user(
    conn: asyncpg.Connection,
    query: str,
    user_id: str,
    *args: Any,
    user_id_column: str = "user_id",
) -> list[asyncpg.Record]:
    """``conn.fetch`` with automatic ``user_id = $1`` injection.

    Parameters
    ----------
    conn : asyncpg.Connection
    query : str
        SQL query.  Use ``$2``, ``$3``, … for other parameters.
    user_id : str
        The authenticated user's ID (bound to ``$1``).
    *args :
        Remaining positional parameters (``$2`` onwards).
    user_id_column : str
        Column name for the user-id filter (default ``user_id``).
    """
    safe_query = _inject_user_filter(query, user_id_column)
    return await conn.fetch(safe_query, user_id, *args)


async def fetchrow_for_user(
    conn: asyncpg.Connection,
    query: str,
    user_id: str,
    *args: Any,
    user_id_column: str = "user_id",
) -> asyncpg.Record | None:
    """``conn.fetchrow`` with automatic ``user_id = $1`` injection."""
    safe_query = _inject_user_filter(query, user_id_column)
    return await conn.fetchrow(safe_query, user_id, *args)


async def fetchval_for_user(
    conn: asyncpg.Connection,
    query: str,
    user_id: str,
    *args: Any,
    user_id_column: str = "user_id",
) -> Any:
    """``conn.fetchval`` with automatic ``user_id = $1`` injection."""
    safe_query = _inject_user_filter(query, user_id_column)
    return await conn.fetchval(safe_query, user_id, *args)


async def execute_for_user(
    conn: asyncpg.Connection,
    query: str,
    user_id: str,
    *args: Any,
    user_id_column: str = "user_id",
) -> str:
    """``conn.execute`` with automatic ``user_id = $1`` injection."""
    safe_query = _inject_user_filter(query, user_id_column)
    return await conn.execute(safe_query, user_id, *args)


def verify_user_guard(query: str, user_id_column: str = "user_id") -> bool:
    """Check whether *query* already contains a ``user_id`` filter.

    Useful as a lint / assertion in tests to ensure every user-scoped
    query explicitly guards on the user id.
    """
    pattern = rf"\b{re.escape(user_id_column)}\s*=\s*\$\d+"
    return bool(re.search(pattern, query, re.IGNORECASE))
