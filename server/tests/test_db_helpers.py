"""Tests for app.db_helpers — user-scoped query helpers."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.db_helpers import (
    _inject_user_filter,
    fetch_for_user,
    fetchrow_for_user,
    fetchval_for_user,
    execute_for_user,
    verify_user_guard,
)


# ---------------------------------------------------------------------------
# _inject_user_filter — query rewriting
# ---------------------------------------------------------------------------

class TestInjectUserFilter:
    def test_no_where_clause_appends(self):
        q = "SELECT * FROM items"
        result = _inject_user_filter(q)
        assert "WHERE user_id = $1" in result

    def test_existing_where_clause_prepends(self):
        q = "SELECT * FROM items WHERE category = $2"
        result = _inject_user_filter(q)
        assert "WHERE user_id = $1 AND" in result
        assert "category = $2" in result

    def test_with_order_by(self):
        q = "SELECT * FROM items ORDER BY created_at DESC"
        result = _inject_user_filter(q)
        assert "WHERE user_id = $1" in result
        assert result.index("WHERE") < result.index("ORDER BY")

    def test_with_limit(self):
        q = "SELECT * FROM items LIMIT 10"
        result = _inject_user_filter(q)
        assert "WHERE user_id = $1" in result
        assert result.index("WHERE") < result.index("LIMIT")

    def test_with_group_by(self):
        q = "SELECT category, COUNT(*) FROM items GROUP BY category"
        result = _inject_user_filter(q)
        assert "WHERE user_id = $1" in result
        assert result.index("WHERE") < result.index("GROUP BY")

    def test_custom_column(self):
        q = "SELECT * FROM events WHERE date > $2"
        result = _inject_user_filter(q, user_id_column="created_by")
        assert "created_by = $1 AND" in result

    def test_where_with_multiple_conditions(self):
        q = "SELECT * FROM items WHERE category = $2 AND price > $3"
        result = _inject_user_filter(q)
        assert "user_id = $1 AND" in result
        assert "category = $2" in result
        assert "price > $3" in result

    def test_with_returning(self):
        q = "INSERT INTO items (title, user_id) VALUES ($2, $1) RETURNING *"
        result = _inject_user_filter(q)
        # Should inject before RETURNING if no WHERE
        assert "WHERE user_id = $1" in result

    def test_preserves_semicolon(self):
        q = "SELECT * FROM items;"
        result = _inject_user_filter(q)
        assert "WHERE user_id = $1" in result


# ---------------------------------------------------------------------------
# verify_user_guard
# ---------------------------------------------------------------------------

class TestVerifyUserGuard:
    def test_returns_true_for_guarded_query(self):
        q = "SELECT * FROM items WHERE user_id = $1 AND category = $2"
        assert verify_user_guard(q) is True

    def test_returns_false_for_unguarded_query(self):
        q = "SELECT * FROM items WHERE category = $1"
        assert verify_user_guard(q) is False

    def test_custom_column(self):
        q = "SELECT * FROM items WHERE created_by = $2"
        assert verify_user_guard(q, user_id_column="created_by") is True

    def test_detects_any_param_position(self):
        q = "SELECT * FROM items WHERE category = $1 AND user_id = $2"
        assert verify_user_guard(q) is True


# ---------------------------------------------------------------------------
# Async wrappers
# ---------------------------------------------------------------------------

class TestFetchForUser:
    @pytest.mark.asyncio
    async def test_injects_user_id_and_calls_fetch(self):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[{"id": "1"}])

        result = await fetch_for_user(
            conn, "SELECT * FROM items WHERE category = $2", "user-abc", "funko"
        )

        conn.fetch.assert_called_once()
        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "user_id = $1" in query
        assert call_args[0][1] == "user-abc"
        assert call_args[0][2] == "funko"
        assert result == [{"id": "1"}]


class TestFetchrowForUser:
    @pytest.mark.asyncio
    async def test_injects_user_id_and_calls_fetchrow(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": "1"})

        result = await fetchrow_for_user(
            conn, "SELECT * FROM items WHERE id = $2", "user-abc", "item-1"
        )

        conn.fetchrow.assert_called_once()
        query = conn.fetchrow.call_args[0][0]
        assert "user_id = $1" in query
        assert result == {"id": "1"}


class TestFetchvalForUser:
    @pytest.mark.asyncio
    async def test_injects_user_id_and_calls_fetchval(self):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=42)

        result = await fetchval_for_user(
            conn, "SELECT COUNT(*) FROM items", "user-abc"
        )

        conn.fetchval.assert_called_once()
        query = conn.fetchval.call_args[0][0]
        assert "user_id = $1" in query
        assert result == 42


class TestExecuteForUser:
    @pytest.mark.asyncio
    async def test_injects_user_id_and_calls_execute(self):
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="UPDATE 1")

        result = await execute_for_user(
            conn,
            "UPDATE items SET title = $2 WHERE id = $3",
            "user-abc",
            "New Title",
            "item-1",
        )

        conn.execute.assert_called_once()
        query = conn.execute.call_args[0][0]
        assert "user_id = $1" in query
        assert result == "UPDATE 1"
