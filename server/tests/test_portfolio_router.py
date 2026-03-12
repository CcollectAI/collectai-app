"""Tests for app.routes.portfolio_router — portfolio endpoints."""

import os

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from starlette.testclient import TestClient

from app.auth import get_current_user_id
from main import app

_TEST_USER = "user-portfolio-test"
_AUTH_HEADERS = {}  # No real auth header needed with override

# Override auth dependency globally for tests
app.dependency_overrides[get_current_user_id] = lambda: _TEST_USER

client = TestClient(app, raise_server_exceptions=False)


def _override_no_pool():
    """Mock get_db_pool to return None (no DB available)."""
    return patch("app.routes.portfolio_router.get_db_pool", return_value=None)


# ---- Helpers ----

def _demo_item(**overrides):
    """Create a fake demo item (SimpleNamespace that quacks like ItemResponse)."""
    defaults = {
        "id": "demo-1",
        "name": "Test Card",
        "category": "pokemon",
        "estimated_value": 45.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---- Auth guard ----
# Note: auth is overridden globally for tests via dependency_overrides.
# In production, get_current_user_id validates JWT tokens.


# ---- Timeseries endpoint ----

class TestPortfolioTimeseries:

    def test_timeseries_no_db_no_signals_returns_empty(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.is_closed = False

        with _override_no_pool(), \
             patch("app.routes.portfolio_router._get_http_client", return_value=mock_client):
            r = client.get("/portfolio/timeseries?range=30d", headers=_AUTH_HEADERS)
        assert r.status_code == 200
        assert r.json() == {"points": []}

    def test_timeseries_no_db_falls_back_to_proxy(self):
        mock_response = httpx.Response(
            200, json={"points": [{"t": "2025-01-01", "v": 100}]},
            request=httpx.Request("GET", "http://test"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with _override_no_pool(), \
             patch("app.routes.portfolio_router._get_http_client", return_value=mock_client):
            r = client.get("/portfolio/timeseries?range=7d", headers=_AUTH_HEADERS)
        assert r.status_code == 200
        assert len(r.json()["points"]) == 1

    def test_timeseries_invalid_range_rejected(self):
        r = client.get("/portfolio/timeseries?range=invalid", headers=_AUTH_HEADERS)
        assert r.status_code == 422

    def test_timeseries_with_db(self):
        import datetime
        mock_rows = [
            {"day": datetime.date(2025, 1, 1), "total_value": 100.50},
            {"day": datetime.date(2025, 1, 2), "total_value": 105.00},
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.routes.portfolio_router.get_db_pool", return_value=mock_pool):
            r = client.get("/portfolio/timeseries?range=7d", headers=_AUTH_HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert len(data["points"]) == 2
        assert data["points"][0]["v"] == 100.5
        assert data["points"][1]["v"] == 105.0


# ---- Overview endpoint ----

class TestPortfolioOverview:

    def test_overview_no_db_falls_back(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.is_closed = False

        with _override_no_pool(), \
             patch("app.routes.portfolio_router._get_http_client", return_value=mock_client):
            r = client.get("/portfolio/overview", headers=_AUTH_HEADERS)
        assert r.status_code == 200
        assert r.json() == {"total_value": 0, "item_count": 0, "items": []}

    def test_overview_with_db(self):
        mock_rows = [
            {"id": "item-1", "name": "Card A", "category": "pokemon", "current_value": 200, "prev_value": 180},
            {"id": "item-2", "name": "Card B", "category": "mtg", "current_value": 50, "prev_value": 50},
        ]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.routes.portfolio_router.get_db_pool", return_value=mock_pool):
            r = client.get("/portfolio/overview", headers=_AUTH_HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["total_value"] == 250.0
        assert data["item_count"] == 2
        assert data["items"][0]["current_value"] == 200.0


# ---- Items endpoint ----

class TestPortfolioItems:

    def test_items_no_db(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.is_closed = False

        with _override_no_pool(), \
             patch("app.routes.portfolio_router._get_http_client", return_value=mock_client):
            r = client.get("/portfolio/items", headers=_AUTH_HEADERS)
        assert r.status_code == 200
        assert r.json() == {"items": []}


# ---- Summary endpoint ----

class TestPortfolioSummary:

    def test_summary_with_demo_items(self):
        items = [_demo_item(id="d1", estimated_value=100.0),
                 _demo_item(id="d2", estimated_value=50.5, category=None)]
        with _override_no_pool(), \
             patch(
                "app.routes.items_router.get_demo_items",
                return_value=items,
             ):
            r = client.get("/portfolio/summary", headers=_AUTH_HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["total_value"] == pytest.approx(150.5)

    def test_summary_empty_items(self):
        with _override_no_pool(), \
             patch(
                "app.routes.items_router.get_demo_items",
                return_value=[],
             ):
            r = client.get("/portfolio/summary", headers=_AUTH_HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["total_value"] == 0.0

    def test_summary_get_demo_items_raises(self):
        with _override_no_pool(), \
             patch(
                "app.routes.items_router.get_demo_items",
                side_effect=RuntimeError("kaboom"),
             ):
            r = client.get("/portfolio/summary", headers=_AUTH_HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["total_value"] == 0.0
