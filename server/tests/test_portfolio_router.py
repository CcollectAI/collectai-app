"""Tests for app.routes.portfolio_router — portfolio summary & proxy endpoints."""

import os

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from starlette.testclient import TestClient

from main import app

client = TestClient(app, raise_server_exceptions=False)


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


# ---- GET /portfolio/summary (no auth) ----


class TestPortfolioSummary:

    def test_summary_with_demo_items(self):
        items = [_demo_item(id="d1", estimated_value=100.0),
                 _demo_item(id="d2", estimated_value=50.5, category=None)]
        with patch(
            "app.routes.portfolio_router.get_demo_items",
            return_value=items,
            create=True,
        ), patch(
            "app.routes.items_router.get_demo_items",
            return_value=items,
        ):
            r = client.get("/portfolio/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total_value"] == pytest.approx(150.5)
        assert len(data["items"]) == 2
        assert data["items"][1]["category"] == "Uncategorized"
        assert data["watchlist"] == []
        assert data["avg_change_pct"] == 0.0

    def test_summary_empty_items(self):
        with patch(
            "app.routes.items_router.get_demo_items",
            return_value=[],
        ):
            r = client.get("/portfolio/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total_value"] == 0.0
        assert data["items"] == []

    def test_summary_non_numeric_value_treated_as_zero(self):
        items = [_demo_item(estimated_value="not-a-number")]
        with patch(
            "app.routes.items_router.get_demo_items",
            return_value=items,
        ):
            r = client.get("/portfolio/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["items"][0]["value"] == 0.0

    def test_summary_none_value_treated_as_zero(self):
        items = [_demo_item(estimated_value=None)]
        with patch(
            "app.routes.items_router.get_demo_items",
            return_value=items,
        ):
            r = client.get("/portfolio/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["items"][0]["value"] == 0.0

    def test_summary_get_demo_items_raises(self):
        with patch(
            "app.routes.items_router.get_demo_items",
            side_effect=RuntimeError("kaboom"),
        ):
            r = client.get("/portfolio/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["total_value"] == 0.0
        assert data["items"] == []

    def test_summary_no_auth_required(self):
        """Public endpoint — no Authorization or API key needed."""
        r = client.get("/portfolio/summary")
        assert r.status_code == 200


# ---- Proxy endpoints (require API key) ----


_VALID_SECRET = "test-shared-secret-123"


class TestPortfolioProxy:

    def _patch_secret(self):
        return patch("app.auth.API_SHARED_SECRET", _VALID_SECRET)

    # -- Auth guard --

    def test_overview_missing_api_key(self):
        with self._patch_secret():
            r = client.get("/portfolio/overview")
        assert r.status_code == 422  # Header required by FastAPI

    def test_overview_wrong_api_key(self):
        with self._patch_secret():
            r = client.get(
                "/portfolio/overview",
                headers={"X-API-Key": "wrong-key"},
            )
        assert r.status_code == 401

    def test_overview_api_key_not_configured(self):
        with patch("app.auth.API_SHARED_SECRET", ""):
            r = client.get(
                "/portfolio/overview",
                headers={"X-API-Key": "anything"},
            )
        assert r.status_code == 500

    # -- Successful proxy --

    def test_overview_proxies_to_signals(self):
        mock_response = httpx.Response(
            200, json={"total_value": 999}, request=httpx.Request("GET", "http://test")
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with self._patch_secret(), \
             patch("app.routes.portfolio_router._get_http_client", return_value=mock_client):
            r = client.get(
                "/portfolio/overview",
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert r.status_code == 200
        assert r.json() == {"total_value": 999}

    def test_items_proxies_to_signals(self):
        mock_response = httpx.Response(
            200, json={"items": []}, request=httpx.Request("GET", "http://test")
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with self._patch_secret(), \
             patch("app.routes.portfolio_router._get_http_client", return_value=mock_client):
            r = client.get(
                "/portfolio/items",
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert r.status_code == 200

    def test_timeseries_proxies_to_signals(self):
        mock_response = httpx.Response(
            200, json={"data": []}, request=httpx.Request("GET", "http://test")
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with self._patch_secret(), \
             patch("app.routes.portfolio_router._get_http_client", return_value=mock_client):
            r = client.get(
                "/portfolio/timeseries",
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert r.status_code == 200

    # -- Upstream errors --

    def test_upstream_http_error_returns_502(self):
        mock_response = httpx.Response(
            500,
            json={"detail": "internal error"},
            request=httpx.Request("GET", "http://test"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with self._patch_secret(), \
             patch("app.routes.portfolio_router._get_http_client", return_value=mock_client):
            r = client.get(
                "/portfolio/overview",
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert r.status_code == 502
        assert "Upstream service error" in r.json()["detail"]

    def test_upstream_unreachable_returns_503(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.is_closed = False

        with self._patch_secret(), \
             patch("app.routes.portfolio_router._get_http_client", return_value=mock_client):
            r = client.get(
                "/portfolio/overview",
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert r.status_code == 503
        assert "Upstream service unavailable" in r.json()["detail"]

    def test_upstream_timeout_returns_503(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ReadTimeout("Read timed out")
        )
        mock_client.is_closed = False

        with self._patch_secret(), \
             patch("app.routes.portfolio_router._get_http_client", return_value=mock_client):
            r = client.get(
                "/portfolio/overview",
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert r.status_code == 503
