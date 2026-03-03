"""
Tests for app/features/trends_and_deepdive_router.py — analytics endpoints.

Covers:
  - GET /analytics/collection/trends     — no pool fallback, mocked DB happy path, DB error fallback, schema validation
  - GET /analytics/items/{item_id}/trends — no pool fallback, mocked DB happy path, invalid UUID, DB error, schema validation
  - GET /analytics/portfolio/category-breakdown — no pool fallback, mocked DB happy path, cache hit, DB error, schema validation
  - GET /analytics/categories/{category}/deep-dive — no pool fallback, mocked DB happy path, cache hit, DB error, schema validation

All tests mock get_db_pool() so no real database is needed.
DEV_MODE=true provides automatic auth as "dev-user-local".
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("PER_USER_RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

VALID_UUID = "00000000-0000-0000-0000-000000000001"
INVALID_UUID = "not-a-uuid"
MODULE = "app.features.trends_and_deepdive_router"

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_pool():
    """Create a mock pool with an async context manager for acquire()."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetchval = AsyncMock(return_value=None)

    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=mock_acquire)

    return pool, mock_conn


def _clear_cache():
    """Clear in-memory cache to avoid test pollution."""
    try:
        from app.cache import cache_clear
        cache_clear()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# GET /analytics/collection/trends — no pool (DB_ENABLED=false)
# ---------------------------------------------------------------------------


class TestCollectionTrendsNoPool:
    """Tests for collection trends when get_db_pool returns None (no DB)."""

    def test_returns_empty_response_no_pool(self):
        """When pool is None, return empty collection trend response."""
        resp = client.get("/analytics/collection/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_history"] == []
        assert data["per_category_gain_loss"] == {}
        assert data["currency"] == "EUR"

    def test_custom_currency_no_pool(self):
        """Currency parameter is reflected in the response even without a pool."""
        resp = client.get("/analytics/collection/trends?currency=USD")
        assert resp.status_code == 200
        assert resp.json()["currency"] == "USD"

    def test_default_days_param_no_pool(self):
        """Default days=30 is accepted without error."""
        resp = client.get("/analytics/collection/trends?days=30")
        assert resp.status_code == 200

    def test_schema_fields_present(self):
        """Verify all expected response fields exist and have correct types."""
        resp = client.get("/analytics/collection/trends")
        data = resp.json()
        assert "currency" in data
        assert "total_history" in data
        assert "per_category_gain_loss" in data
        assert isinstance(data["total_history"], list)
        assert isinstance(data["per_category_gain_loss"], dict)
        # dca_history can be None
        assert "dca_history" in data


# ---------------------------------------------------------------------------
# GET /analytics/collection/trends — mocked DB
# ---------------------------------------------------------------------------


class TestCollectionTrendsMockedDB:
    """Tests for collection trends with mocked database."""

    def setup_method(self):
        _clear_cache()

    @patch(f"{MODULE}.get_db_pool")
    def test_happy_path_with_data(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # Total history query
        ts_rows = [
            {"day": NOW, "total_value": 1500.0},
            {"day": datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc), "total_value": 1600.0},
        ]
        # Per-category gain/loss query
        cat_rows = [
            {"category": "pokemon", "sum_first": 500.0, "sum_last": 600.0},
            {"category": "lego", "sum_first": 1000.0, "sum_last": 1000.0},
        ]
        # DCA history query
        dca_rows = [
            {"day": NOW, "cumulative_cost": 800.0},
        ]

        conn.fetch = AsyncMock(side_effect=[ts_rows, cat_rows, dca_rows])

        resp = client.get("/analytics/collection/trends?days=30&currency=EUR")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["total_history"]) == 2
        assert data["total_history"][0]["value"] == 1500.0
        assert "pokemon" in data["per_category_gain_loss"]
        assert data["per_category_gain_loss"]["pokemon"]["gain_pct"] == 0.2
        assert data["per_category_gain_loss"]["lego"]["gain_pct"] == 0.0
        assert data["dca_history"] is not None
        assert len(data["dca_history"]) == 1

    @patch(f"{MODULE}.get_db_pool")
    def test_empty_db_results(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(side_effect=[[], [], []])

        resp = client.get("/analytics/collection/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_history"] == []
        assert data["per_category_gain_loss"] == {}
        assert data["dca_history"] is None

    @patch(f"{MODULE}.get_db_pool")
    def test_db_error_returns_empty(self, mock_get_pool):
        """When the DB query raises an exception, endpoint returns empty data."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(side_effect=Exception("DB connection lost"))

        resp = client.get("/analytics/collection/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_history"] == []
        assert data["per_category_gain_loss"] == {}

    @patch(f"{MODULE}.get_db_pool")
    def test_dca_query_failure_graceful(self, mock_get_pool):
        """When the DCA query fails, dca_history is None but rest is fine."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        ts_rows = [{"day": NOW, "total_value": 100.0}]
        cat_rows = []
        conn.fetch = AsyncMock(side_effect=[ts_rows, cat_rows, Exception("DCA column missing")])

        resp = client.get("/analytics/collection/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["total_history"]) == 1
        assert data["dca_history"] is None

    def test_days_validation_too_low(self):
        """days=0 should be rejected by FastAPI validation (ge=1)."""
        resp = client.get("/analytics/collection/trends?days=0")
        assert resp.status_code == 422

    def test_days_validation_too_high(self):
        """days=999 should be rejected by FastAPI validation (le=365)."""
        resp = client.get("/analytics/collection/trends?days=999")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /analytics/items/{item_id}/trends — no pool
# ---------------------------------------------------------------------------


class TestItemTrendsNoPool:
    """Tests for item trends when get_db_pool returns None."""

    def test_returns_empty_for_valid_uuid(self):
        resp = client.get(f"/analytics/items/{VALID_UUID}/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == VALID_UUID
        assert data["history"] == []
        assert data["currency"] == "EUR"

    def test_invalid_uuid_returns_400(self):
        resp = client.get(f"/analytics/items/{INVALID_UUID}/trends")
        assert resp.status_code == 400

    def test_custom_currency_reflected(self):
        resp = client.get(f"/analytics/items/{VALID_UUID}/trends?currency=GBP")
        assert resp.status_code == 200
        assert resp.json()["currency"] == "GBP"

    def test_schema_fields(self):
        resp = client.get(f"/analytics/items/{VALID_UUID}/trends")
        data = resp.json()
        assert "item_id" in data
        assert "currency" in data
        assert "history" in data
        assert isinstance(data["history"], list)


# ---------------------------------------------------------------------------
# GET /analytics/items/{item_id}/trends — mocked DB
# ---------------------------------------------------------------------------


class TestItemTrendsMockedDB:
    """Tests for item trends with mocked database."""

    @patch(f"{MODULE}.get_db_pool")
    def test_happy_path(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        rows = [
            {"asof": NOW, "q50": 120.0, "conf_score": 0.85},
            {"asof": datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc), "q50": 130.0, "conf_score": 0.90},
        ]
        conn.fetch = AsyncMock(return_value=rows)

        resp = client.get(f"/analytics/items/{VALID_UUID}/trends?days=60")
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == VALID_UUID
        assert len(data["history"]) == 2
        assert data["history"][0]["value"] == 120.0
        assert data["model_confidence"] is not None
        assert len(data["model_confidence"]) == 2

    @patch(f"{MODULE}.get_db_pool")
    def test_no_confidence_scores(self, mock_get_pool):
        """When all conf_score are None, model_confidence should be None."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        rows = [
            {"asof": NOW, "q50": 50.0, "conf_score": None},
        ]
        conn.fetch = AsyncMock(return_value=rows)

        resp = client.get(f"/analytics/items/{VALID_UUID}/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_confidence"] is None

    @patch(f"{MODULE}.get_db_pool")
    def test_empty_results(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(return_value=[])

        resp = client.get(f"/analytics/items/{VALID_UUID}/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["history"] == []
        assert data["model_confidence"] is None

    @patch(f"{MODULE}.get_db_pool")
    def test_db_error_returns_empty(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(side_effect=Exception("timeout"))

        resp = client.get(f"/analytics/items/{VALID_UUID}/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["history"] == []
        assert data["model_confidence"] is None

    def test_days_validation_too_low(self):
        resp = client.get(f"/analytics/items/{VALID_UUID}/trends?days=0")
        assert resp.status_code == 422

    def test_days_validation_too_high(self):
        resp = client.get(f"/analytics/items/{VALID_UUID}/trends?days=400")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /analytics/portfolio/category-breakdown — no pool
# ---------------------------------------------------------------------------


class TestCategoryBreakdownNoPool:
    """Tests for portfolio category breakdown when no DB pool is available."""

    def test_returns_empty_breakdown(self):
        resp = client.get("/analytics/portfolio/category-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["breakdown"] == []
        assert data["total_value"] == 0.0

    def test_schema_fields(self):
        resp = client.get("/analytics/portfolio/category-breakdown")
        data = resp.json()
        assert "breakdown" in data
        assert "total_value" in data
        assert isinstance(data["breakdown"], list)
        assert isinstance(data["total_value"], (int, float))


# ---------------------------------------------------------------------------
# GET /analytics/portfolio/category-breakdown — mocked DB
# ---------------------------------------------------------------------------


class TestCategoryBreakdownMockedDB:
    """Tests for portfolio category breakdown with mocked database."""

    def setup_method(self):
        _clear_cache()

    @patch(f"{MODULE}.get_db_pool")
    def test_happy_path(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        rows = [
            {"category": "pokemon", "item_count": 10, "total_value": 500.0, "first_total": 400.0},
            {"category": "lego", "item_count": 5, "total_value": 300.0, "first_total": 300.0},
        ]
        conn.fetch = AsyncMock(return_value=rows)

        resp = client.get("/analytics/portfolio/category-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_value"] == 800.0
        assert len(data["breakdown"]) == 2

        pokemon = data["breakdown"][0]
        assert pokemon["category"] == "pokemon"
        assert pokemon["item_count"] == 10
        assert pokemon["total_value"] == 500.0
        assert pokemon["pct_of_portfolio"] == 0.625
        assert pokemon["gain_pct"] == 0.25

        lego = data["breakdown"][1]
        assert lego["gain_pct"] == 0.0

    @patch(f"{MODULE}.get_db_pool")
    def test_empty_portfolio(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(return_value=[])

        resp = client.get("/analytics/portfolio/category-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["breakdown"] == []
        assert data["total_value"] == 0.0

    @patch(f"{MODULE}.get_db_pool")
    def test_zero_first_total_no_division_error(self, mock_get_pool):
        """When first_total is 0, gain_pct should be 0 (no ZeroDivisionError)."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        rows = [
            {"category": "watches", "item_count": 1, "total_value": 200.0, "first_total": 0},
        ]
        conn.fetch = AsyncMock(return_value=rows)

        resp = client.get("/analytics/portfolio/category-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["breakdown"][0]["gain_pct"] == 0.0

    @patch(f"{MODULE}.get_db_pool")
    def test_db_error_returns_empty(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(side_effect=Exception("DB failure"))

        resp = client.get("/analytics/portfolio/category-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["breakdown"] == []
        assert data["total_value"] == 0.0

    @patch(f"{MODULE}.cache_get")
    def test_cache_hit_returns_cached(self, mock_cache_get):
        """When cache has a hit, the cached data is returned directly."""
        cached_data = {
            "breakdown": [
                {"category": "lego", "item_count": 3, "total_value": 150.0, "pct_of_portfolio": 1.0, "gain_pct": 0.1}
            ],
            "total_value": 150.0,
        }
        mock_cache_get.return_value = cached_data

        resp = client.get("/analytics/portfolio/category-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_value"] == 150.0
        assert len(data["breakdown"]) == 1

    @patch(f"{MODULE}.get_db_pool")
    def test_breakdown_item_schema(self, mock_get_pool):
        """Each breakdown item should have all required fields with correct types."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        rows = [
            {"category": "mtg", "item_count": 7, "total_value": 350.0, "first_total": 280.0},
        ]
        conn.fetch = AsyncMock(return_value=rows)

        resp = client.get("/analytics/portfolio/category-breakdown")
        data = resp.json()
        item = data["breakdown"][0]
        assert isinstance(item["category"], str)
        assert isinstance(item["item_count"], int)
        assert isinstance(item["total_value"], (int, float))
        assert isinstance(item["pct_of_portfolio"], (int, float))
        assert isinstance(item["gain_pct"], (int, float))


# ---------------------------------------------------------------------------
# GET /analytics/categories/{category}/deep-dive — no pool
# ---------------------------------------------------------------------------


class TestCategoryDeepDiveNoPool:
    """Tests for category deep dive when no DB pool is available."""

    def setup_method(self):
        _clear_cache()

    def test_returns_empty_deepdive(self):
        resp = client.get("/analytics/categories/pokemon/deep-dive")
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "pokemon"
        assert data["currency"] == "EUR"
        assert data["avg_market_price"] == 0.0
        assert data["value_distribution"] == []
        assert data["volume_trend"] == []
        assert data["top_traded_items"] == []
        assert data["top_movers"] == []

    def test_custom_currency(self):
        resp = client.get("/analytics/categories/lego/deep-dive?currency=USD")
        assert resp.status_code == 200
        assert resp.json()["currency"] == "USD"

    def test_days_min_7(self):
        """days must be >= 7 for deep-dive."""
        resp = client.get("/analytics/categories/pokemon/deep-dive?days=3")
        assert resp.status_code == 422

    def test_days_max_365(self):
        resp = client.get("/analytics/categories/pokemon/deep-dive?days=500")
        assert resp.status_code == 422

    def test_schema_fields(self):
        resp = client.get("/analytics/categories/pokemon/deep-dive")
        data = resp.json()
        assert "category" in data
        assert "currency" in data
        assert "avg_market_price" in data
        assert "value_distribution" in data
        assert "volume_trend" in data
        assert "top_traded_items" in data
        assert "top_movers" in data


# ---------------------------------------------------------------------------
# GET /analytics/categories/{category}/deep-dive — mocked DB
# ---------------------------------------------------------------------------


class TestCategoryDeepDiveMockedDB:
    """Tests for category deep dive with mocked database."""

    def setup_method(self):
        _clear_cache()

    @patch(f"{MODULE}.get_db_pool")
    def test_happy_path(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        daily_rows = [
            {"day": NOW, "avg_price": 25.50, "cnt": 100, "grand_count": 200, "overall_avg": 28.0},
            {"day": datetime(2026, 3, 2, tzinfo=timezone.utc), "avg_price": 30.0, "cnt": 100, "grand_count": 200, "overall_avg": 28.0},
        ]
        combo_rows = [
            {
                "normalized_key": "pokemon:charizard",
                "name": "Charizard Holo",
                "trades": 50,
                "first_price": 20.0,
                "last_price": 30.0,
                "price_cnt": 5,
                "change_pct": 0.5,
                "trade_rank": 1,
                "mover_rank": 1,
            },
        ]
        conn.fetch = AsyncMock(side_effect=[daily_rows, combo_rows])

        resp = client.get("/analytics/categories/pokemon/deep-dive?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "pokemon"
        assert data["avg_market_price"] == 28.0
        assert len(data["value_distribution"]) == 2
        assert len(data["volume_trend"]) == 2
        assert len(data["top_traded_items"]) == 1
        assert data["top_traded_items"][0]["name"] == "Charizard Holo"
        assert data["top_traded_items"][0]["trades"] == 50
        assert len(data["top_movers"]) == 1
        assert data["top_movers"][0]["change_pct"] == 0.5

    @patch(f"{MODULE}.get_db_pool")
    def test_empty_market_data(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(side_effect=[[], []])

        resp = client.get("/analytics/categories/lego/deep-dive")
        assert resp.status_code == 200
        data = resp.json()
        assert data["avg_market_price"] == 0.0
        assert data["top_traded_items"] == []
        assert data["top_movers"] == []

    @patch(f"{MODULE}.get_db_pool")
    def test_db_error_returns_empty(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(side_effect=Exception("Connection refused"))

        resp = client.get("/analytics/categories/mtg/deep-dive")
        assert resp.status_code == 200
        data = resp.json()
        assert data["avg_market_price"] == 0.0
        assert data["value_distribution"] == []

    @patch(f"{MODULE}.cache_get")
    def test_cache_hit(self, mock_cache_get):
        """When the deep-dive result is cached, it is returned without DB access."""
        cached = {
            "category": "lego",
            "currency": "EUR",
            "avg_market_price": 55.0,
            "value_distribution": [],
            "volume_trend": [],
            "top_traded_items": [{"item_id": "lego:42100", "name": "Liebherr", "trades": 10}],
            "top_movers": [],
        }
        mock_cache_get.return_value = cached

        resp = client.get("/analytics/categories/lego/deep-dive")
        assert resp.status_code == 200
        data = resp.json()
        assert data["avg_market_price"] == 55.0
        assert len(data["top_traded_items"]) == 1

    @patch(f"{MODULE}.get_db_pool")
    def test_timeseries_point_schema(self, mock_get_pool):
        """Each timeseries point should have ts and value fields."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        daily_rows = [
            {"day": NOW, "avg_price": 10.0, "cnt": 5, "grand_count": 5, "overall_avg": 10.0},
        ]
        conn.fetch = AsyncMock(side_effect=[daily_rows, []])

        resp = client.get("/analytics/categories/watches/deep-dive")
        data = resp.json()
        assert len(data["value_distribution"]) == 1
        point = data["value_distribution"][0]
        assert "ts" in point
        assert "value" in point
        assert isinstance(point["value"], (int, float))

    @patch(f"{MODULE}.get_db_pool")
    def test_top_traded_sorted_by_trades(self, mock_get_pool):
        """top_traded_items should be sorted by trades descending."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        daily_rows = [
            {"day": NOW, "avg_price": 10.0, "cnt": 50, "grand_count": 50, "overall_avg": 10.0},
        ]
        combo_rows = [
            {"normalized_key": "k1", "name": "Item A", "trades": 20, "first_price": 10.0, "last_price": 15.0, "price_cnt": 3, "change_pct": 0.5, "trade_rank": 2, "mover_rank": 5},
            {"normalized_key": "k2", "name": "Item B", "trades": 50, "first_price": 10.0, "last_price": 12.0, "price_cnt": 3, "change_pct": 0.2, "trade_rank": 1, "mover_rank": 8},
        ]
        conn.fetch = AsyncMock(side_effect=[daily_rows, combo_rows])

        resp = client.get("/analytics/categories/pokemon/deep-dive?days=30")
        data = resp.json()
        assert data["top_traded_items"][0]["trades"] == 50
        assert data["top_traded_items"][1]["trades"] == 20

    @patch(f"{MODULE}.get_db_pool")
    def test_top_movers_sorted_by_abs_change(self, mock_get_pool):
        """top_movers should be sorted by absolute change_pct descending."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        daily_rows = [
            {"day": NOW, "avg_price": 10.0, "cnt": 50, "grand_count": 50, "overall_avg": 10.0},
        ]
        combo_rows = [
            {"normalized_key": "k1", "name": "Gainer", "trades": 5, "first_price": 10.0, "last_price": 15.0, "price_cnt": 3, "change_pct": 0.5, "trade_rank": 15, "mover_rank": 2},
            {"normalized_key": "k2", "name": "Big Loser", "trades": 3, "first_price": 10.0, "last_price": 2.0, "price_cnt": 3, "change_pct": -0.8, "trade_rank": 20, "mover_rank": 1},
        ]
        conn.fetch = AsyncMock(side_effect=[daily_rows, combo_rows])

        resp = client.get("/analytics/categories/mtg/deep-dive?days=30")
        data = resp.json()
        # Sorted by abs(change_pct): 0.8 > 0.5
        assert abs(data["top_movers"][0]["change_pct"]) >= abs(data["top_movers"][1]["change_pct"])
