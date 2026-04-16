"""Tests for app/features/sell_timing_router.py — seasonal sell timing analysis.

Covers:
  1. Insufficient data returns "Not enough data yet"
  2. Sufficient data returns peak month and recommendation
  3. Database unavailable returns 503
  4. Monthly data included in response

DEV_MODE=true + DB_ENABLED=false → require_plan("premium") passes automatically.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from fastapi.testclient import TestClient


def _build_app():
    """Build a minimal FastAPI app with the sell_timing_router mounted."""
    from fastapi import FastAPI
    from app.features.sell_timing_router import router
    from app.auth import get_current_user_id

    app = FastAPI()
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    app.include_router(router)
    return app


def _mock_pool_with_rows(rows):
    """Create a mock pool that returns given rows from fetch."""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=rows)

    @asynccontextmanager
    async def _acquire():
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.acquire = _acquire
    return mock_pool


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_insufficient_data():
    """< 50 observations returns not-enough-data response."""
    rows = [
        {"month_num": 1, "avg_price": 100.0, "cnt": 10},
        {"month_num": 2, "avg_price": 110.0, "cnt": 5},
    ]
    pool = _mock_pool_with_rows(rows)

    app = _build_app()
    with patch("app.features.sell_timing_router.get_db_pool", return_value=pool), \
         patch("app.subscription.get_user_plan", return_value="premium"):
        client = TestClient(app)
        resp = client.get("/sell-timing/items/pokemon-charizard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendation"] == "Not enough data yet"
        assert data["confidence"] == 0.0


def test_sufficient_data_returns_peak():
    """With enough data, returns peak month and recommendation."""
    rows = [
        {"month_num": 1, "avg_price": 100.0, "cnt": 30},
        {"month_num": 6, "avg_price": 120.0, "cnt": 20},
        {"month_num": 11, "avg_price": 180.0, "cnt": 25},
        {"month_num": 12, "avg_price": 150.0, "cnt": 15},
    ]
    pool = _mock_pool_with_rows(rows)

    app = _build_app()
    with patch("app.features.sell_timing_router.get_db_pool", return_value=pool), \
         patch("app.subscription.get_user_plan", return_value="premium"):
        client = TestClient(app)
        resp = client.get("/sell-timing/items/pokemon-charizard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["peak_month"] == "November"
        assert data["peak_avg_price"] == 180.0
        assert data["observation_count"] == 90
        assert data["confidence"] > 0


def test_no_pool_returns_503():
    """Database unavailable returns 503."""
    app = _build_app()
    with patch("app.features.sell_timing_router.get_db_pool", return_value=None), \
         patch("app.subscription.get_user_plan", return_value="premium"):
        client = TestClient(app)
        resp = client.get("/sell-timing/items/pokemon-charizard")
        assert resp.status_code == 503


def test_monthly_data_included():
    """Response includes per-month breakdown."""
    rows = [
        {"month_num": m, "avg_price": 100.0 + m * 5, "cnt": 10}
        for m in range(1, 7)
    ]
    pool = _mock_pool_with_rows(rows)

    app = _build_app()
    with patch("app.features.sell_timing_router.get_db_pool", return_value=pool), \
         patch("app.subscription.get_user_plan", return_value="premium"):
        client = TestClient(app)
        resp = client.get("/sell-timing/items/test-item")
        assert resp.status_code == 200
        data = resp.json()
        assert data["monthly_data"] is not None
        assert len(data["monthly_data"]) == 6
