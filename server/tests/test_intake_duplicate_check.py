"""Tests for duplicate/variant detection."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.intake_duplicate_check import check_user_duplicates


class AsyncContextMock:
    def __init__(self, conn):
        self.conn = conn
    async def __aenter__(self):
        return self.conn
    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_returns_defaults_without_pool():
    result = await check_user_duplicates("user1", "pokemon", "charizard", None, None)
    assert result["owned_count"] == 0
    assert result["is_variant"] is False


@pytest.mark.asyncio
async def test_returns_defaults_without_user():
    pool = MagicMock()
    result = await check_user_duplicates(None, "pokemon", "charizard", None, pool)
    assert result["owned_count"] == 0


@pytest.mark.asyncio
async def test_exact_match_found():
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[
        [{"id": "item-1", "title": "Charizard Base Set", "normalized_key": "charizard base set"}],  # exact
    ])
    conn.fetchval = AsyncMock(side_effect=[1, 500])  # owned, total

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextMock(conn))

    result = await check_user_duplicates("user1", "pokemon", "charizard base set", None, pool)
    assert result["owned_count"] == 1
    assert "item-1" in result["owned_item_ids"]


@pytest.mark.asyncio
async def test_variant_detected():
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[
        [],  # exact match
        [{"id": "item-2", "title": "Charizard VMAX Alt Art", "normalized_key": "charizard vmax alt art"}],  # variant
    ])
    conn.fetchval = AsyncMock(side_effect=[5, 500])

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextMock(conn))

    result = await check_user_duplicates("user1", "pokemon", "charizard vmax", "charizard vmax", pool)
    assert result["is_variant"] is True
    assert result["variant_of"] == "Charizard VMAX Alt Art"


@pytest.mark.asyncio
async def test_set_completion():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(side_effect=[25, 100])  # owned, total

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextMock(conn))

    result = await check_user_duplicates("user1", "pokemon", "test key", None, pool)
    assert result["set_completion"]["owned"] == 25
    assert result["set_completion"]["total"] == 100
    assert result["set_completion"]["pct"] == 25.0


@pytest.mark.asyncio
async def test_no_duplicates():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(side_effect=[0, 500])

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextMock(conn))

    result = await check_user_duplicates("user1", "pokemon", "something unique", None, pool)
    assert result["owned_count"] == 0
    assert result["is_variant"] is False


@pytest.mark.asyncio
async def test_graceful_error_handling():
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=Exception("DB error"))

    result = await check_user_duplicates("user1", "pokemon", "test", None, pool)
    assert result["owned_count"] == 0


@pytest.mark.asyncio
async def test_returns_defaults_without_search_key():
    pool = MagicMock()
    result = await check_user_duplicates("user1", "pokemon", None, None, pool)
    assert result["owned_count"] == 0
