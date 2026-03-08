"""Tests for social proof aggregation."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.intake_social_proof import get_social_proof


class AsyncContextMock:
    """Helper for async context manager mocking."""
    def __init__(self, conn):
        self.conn = conn
    async def __aenter__(self):
        return self.conn
    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_returns_defaults_without_pool():
    result = await get_social_proof("pokemon", "charizard", None)
    assert result["collector_count"] == 0
    assert result["is_trending"] is False
    assert result["recent_sold"] == []


@pytest.mark.asyncio
async def test_returns_defaults_without_category():
    pool = MagicMock()
    result = await get_social_proof(None, "charizard", pool)
    assert result["collector_count"] == 0


@pytest.mark.asyncio
async def test_collector_count_query():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=42)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextMock(conn))

    result = await get_social_proof("pokemon", "charizard", pool)
    assert result["collector_count"] == 42


@pytest.mark.asyncio
async def test_trending_detected():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=5)
    conn.fetchrow = AsyncMock(side_effect=[
        {"rank": 3, "heat_score": 0.8},  # trending
        None,  # scarcity
    ])
    conn.fetch = AsyncMock(return_value=[])

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextMock(conn))

    result = await get_social_proof("pokemon", "charizard", pool)
    assert result["is_trending"] is True
    assert result["trend_rank"] == 3


@pytest.mark.asyncio
async def test_recent_sold_returns_items():
    from datetime import datetime
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[
        {"title": "Charizard 1st Ed", "price": 500.0, "currency": "USD", "ended_at": datetime(2025, 1, 1), "source": "ebay"},
    ])

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextMock(conn))

    result = await get_social_proof("pokemon", "charizard", pool)
    assert len(result["recent_sold"]) == 1
    assert result["recent_sold"][0]["price"] == 500.0


@pytest.mark.asyncio
async def test_scarcity_data():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(side_effect=[
        None,  # trending
        {"listing_count": 15, "supply_trend": "decreasing", "scarcity_score": 0.8},  # scarcity
    ])
    conn.fetch = AsyncMock(return_value=[])

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextMock(conn))

    result = await get_social_proof("pokemon", "charizard", pool)
    assert result["scarcity"]["listing_count"] == 15
    assert result["scarcity"]["supply_trend"] == "decreasing"


@pytest.mark.asyncio
async def test_graceful_degradation_on_error():
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=Exception("DB down"))

    result = await get_social_proof("pokemon", "charizard", pool)
    assert result["collector_count"] == 0
    assert result["recent_sold"] == []
