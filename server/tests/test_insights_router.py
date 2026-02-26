"""Tests for app/features/insights_router.py — personalized insights endpoints.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
The insights router returns empty/fallback data when no DB pool is available.
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


# ---------------------------------------------------------------------------
# GET /insights/personalized — personalized insights
# ---------------------------------------------------------------------------

class TestPersonalizedInsights:
    def test_personalized_returns_200(self):
        """Returns 200 with empty insights when no DB pool."""
        resp = client.get("/insights/personalized")
        assert resp.status_code == 200
        data = resp.json()
        assert "overexposed_categories" in data
        assert "diversification_suggestions" in data
        assert "rare_set_alerts" in data
        assert "trending_items" in data
        assert data["overexposed_categories"] == []
        assert data["diversification_suggestions"] == []
        assert data["rare_set_alerts"] == []
        assert data["trending_items"] == []

    def test_personalized_with_pagination(self):
        """Accepts pagination query params."""
        resp = client.get("/insights/personalized", params={"limit": 10, "offset": 0})
        assert resp.status_code == 200

    def test_personalized_response_model(self):
        """Response matches PersonalizedInsightsResponse schema."""
        resp = client.get("/insights/personalized")
        data = resp.json()
        assert isinstance(data["overexposed_categories"], list)
        assert isinstance(data["diversification_suggestions"], list)
        assert isinstance(data["rare_set_alerts"], list)
        assert isinstance(data["trending_items"], list)


# ---------------------------------------------------------------------------
# GET /insights/home-widget — home widget snapshot
# ---------------------------------------------------------------------------

class TestHomeWidget:
    def test_home_widget_returns_200(self):
        """Returns 200 with default widget data when no DB pool."""
        resp = client.get("/insights/home-widget")
        assert resp.status_code == 200
        data = resp.json()
        assert "collection_value" in data
        assert "today_change" in data
        assert "biggest_mover_name" in data
        assert "biggest_mover_change" in data
        assert "currency" in data

    def test_home_widget_offline_defaults(self):
        """Offline mode returns zero values and default currency."""
        resp = client.get("/insights/home-widget")
        data = resp.json()
        assert data["collection_value"] == 0.0
        assert data["today_change"] == 0.0
        assert data["biggest_mover_name"] == "--"
        assert data["biggest_mover_change"] == 0.0
        assert data["currency"] == "EUR"

    def test_home_widget_has_quickscan_shortcut(self):
        """Response includes quickscan shortcut path."""
        resp = client.get("/insights/home-widget")
        data = resp.json()
        assert "quickscan_shortcut" in data
        assert data["quickscan_shortcut"] == "/quickscan-advanced/single"
