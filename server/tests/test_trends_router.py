"""Tests for app/features/trends_and_deepdive_router.py — analytics endpoints.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
The analytics router returns empty/fallback data when no DB pool is available.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")

from starlette.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app)

VALID_ITEM_ID = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# GET /analytics/collection/trends — collection trend graph
# ---------------------------------------------------------------------------

class TestCollectionTrends:
    def test_collection_trends_returns_200(self):
        """Returns 200 with empty trends when no DB pool."""
        resp = client.get("/analytics/collection/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_history" in data
        assert "per_category_gain_loss" in data
        assert "currency" in data

    def test_collection_trends_offline_defaults(self):
        """Offline mode returns empty history and gain/loss."""
        resp = client.get("/analytics/collection/trends")
        data = resp.json()
        assert data["total_history"] == []
        assert data["per_category_gain_loss"] == {}
        assert data["currency"] == "EUR"

    def test_collection_trends_with_days(self):
        """Accepts days query parameter."""
        resp = client.get("/analytics/collection/trends", params={"days": 90})
        assert resp.status_code == 200

    def test_collection_trends_invalid_days_too_high(self):
        """Rejects days > 365."""
        resp = client.get("/analytics/collection/trends", params={"days": 500})
        assert resp.status_code == 422

    def test_collection_trends_invalid_days_zero(self):
        """Rejects days < 1."""
        resp = client.get("/analytics/collection/trends", params={"days": 0})
        assert resp.status_code == 422

    def test_collection_trends_with_currency(self):
        """Accepts currency query parameter."""
        resp = client.get("/analytics/collection/trends", params={"currency": "USD"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["currency"] == "USD"


# ---------------------------------------------------------------------------
# GET /analytics/items/{item_id}/trends — item-level trends
# ---------------------------------------------------------------------------

class TestItemTrends:
    def test_item_trends_returns_200(self):
        """Returns 200 with empty trends when no DB pool."""
        resp = client.get(f"/analytics/items/{VALID_ITEM_ID}/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert "item_id" in data
        assert "history" in data
        assert "currency" in data

    def test_item_trends_offline_defaults(self):
        """Offline mode returns empty history."""
        resp = client.get(f"/analytics/items/{VALID_ITEM_ID}/trends")
        data = resp.json()
        assert data["item_id"] == VALID_ITEM_ID
        assert data["history"] == []
        assert data["currency"] == "EUR"

    def test_item_trends_with_days(self):
        """Accepts days query parameter."""
        resp = client.get(
            f"/analytics/items/{VALID_ITEM_ID}/trends",
            params={"days": 7},
        )
        assert resp.status_code == 200

    def test_item_trends_invalid_days(self):
        """Rejects days out of bounds."""
        resp = client.get(
            f"/analytics/items/{VALID_ITEM_ID}/trends",
            params={"days": 0},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /analytics/portfolio/category-breakdown — portfolio category breakdown
# ---------------------------------------------------------------------------

class TestPortfolioCategoryBreakdown:
    def test_breakdown_returns_200(self):
        """Returns 200 with empty breakdown when no DB pool."""
        resp = client.get("/analytics/portfolio/category-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert "breakdown" in data
        assert "total_value" in data

    def test_breakdown_offline_defaults(self):
        """Offline mode returns empty breakdown and zero total."""
        resp = client.get("/analytics/portfolio/category-breakdown")
        data = resp.json()
        assert data["breakdown"] == []
        assert data["total_value"] == 0.0


# ---------------------------------------------------------------------------
# GET /analytics/categories/{category}/deep-dive — category deep dive
# ---------------------------------------------------------------------------

class TestCategoryDeepDive:
    def test_deep_dive_returns_200(self):
        """Returns 200 with empty deep dive data when no DB pool."""
        resp = client.get("/analytics/categories/pokemon_tcg/deep-dive")
        assert resp.status_code == 200
        data = resp.json()
        assert "category" in data
        assert "avg_market_price" in data
        assert "value_distribution" in data
        assert "volume_trend" in data
        assert "top_traded_items" in data
        assert "top_movers" in data

    def test_deep_dive_offline_defaults(self):
        """Offline mode returns zeros and empty lists."""
        resp = client.get("/analytics/categories/lego/deep-dive")
        data = resp.json()
        assert data["category"] == "lego"
        assert data["avg_market_price"] == 0.0
        assert data["value_distribution"] == []
        assert data["volume_trend"] == []
        assert data["top_traded_items"] == []
        assert data["top_movers"] == []
        assert data["currency"] == "EUR"

    def test_deep_dive_with_days(self):
        """Accepts days query parameter (min 7)."""
        resp = client.get(
            "/analytics/categories/funko/deep-dive",
            params={"days": 30},
        )
        assert resp.status_code == 200

    def test_deep_dive_invalid_days_too_low(self):
        """Rejects days below minimum (7)."""
        resp = client.get(
            "/analytics/categories/funko/deep-dive",
            params={"days": 3},
        )
        assert resp.status_code == 422

    def test_deep_dive_invalid_days_too_high(self):
        """Rejects days above maximum (365)."""
        resp = client.get(
            "/analytics/categories/funko/deep-dive",
            params={"days": 500},
        )
        assert resp.status_code == 422

    def test_deep_dive_with_currency(self):
        """Accepts currency query parameter."""
        resp = client.get(
            "/analytics/categories/mtg/deep-dive",
            params={"currency": "USD"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["currency"] == "USD"

    def test_deep_dive_arbitrary_category(self):
        """Accepts any category string (no validation on category name)."""
        resp = client.get("/analytics/categories/nonexistent_category/deep-dive")
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "nonexistent_category"
