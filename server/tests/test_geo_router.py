"""Tests for app/routes/geo_router.py — IP-based geolocation detection.

Covers:
  - GET /geo/detect — country mapping, fallback for unknown/local IPs
  - Caching behaviour
  - Response format validation
  - IP masking utility
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("FORCE_DEV_MODE", "true")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["PER_USER_RATE_LIMIT_ENABLED"] = "false"

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_ip_api_response(country_code: str, status: str = "success"):
    """Create a mock httpx response for ip-api.com."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "status": status,
        "countryCode": country_code,
    }
    return mock_resp


def _mock_httpx_client(response):
    """Create a mock httpx.AsyncClient context manager."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# IP masking utility
# ---------------------------------------------------------------------------

class TestIPMasking:
    def test_ipv4_masking(self):
        """IPv4 last octet should be masked."""
        from app.routes.geo_router import _mask_ip
        result = _mask_ip("192.168.1.100")
        assert result == "192.168.1.xxx"

    def test_ipv6_masking(self):
        """IPv6 should be hashed (contains colon)."""
        from app.routes.geo_router import _mask_ip
        result = _mask_ip("::1")
        assert len(result) == 12  # sha256 hex prefix

    def test_ipv4_no_dots(self):
        """Single-segment IP returns as-is."""
        from app.routes.geo_router import _mask_ip
        result = _mask_ip("localhost")
        assert result == "localhost"


# ---------------------------------------------------------------------------
# Country code mapping
# ---------------------------------------------------------------------------

class TestCountryMap:
    def test_us_mapping(self):
        """US should map to americas/USD."""
        from app.routes.geo_router import _COUNTRY_MAP
        region, currency = _COUNTRY_MAP["US"]
        assert region == "americas"
        assert currency == "USD"

    def test_gb_mapping(self):
        """GB should map to europe/GBP."""
        from app.routes.geo_router import _COUNTRY_MAP
        region, currency = _COUNTRY_MAP["GB"]
        assert region == "europe"
        assert currency == "GBP"

    def test_jp_mapping(self):
        """JP should map to japan/JPY."""
        from app.routes.geo_router import _COUNTRY_MAP
        region, currency = _COUNTRY_MAP["JP"]
        assert region == "japan"
        assert currency == "JPY"

    def test_kr_mapping(self):
        """KR should map to korea/KRW."""
        from app.routes.geo_router import _COUNTRY_MAP
        region, currency = _COUNTRY_MAP["KR"]
        assert region == "korea"
        assert currency == "KRW"

    def test_au_mapping(self):
        """AU should map to oceania/AUD."""
        from app.routes.geo_router import _COUNTRY_MAP
        region, currency = _COUNTRY_MAP["AU"]
        assert region == "oceania"
        assert currency == "AUD"

    def test_de_mapping(self):
        """DE should map to europe/EUR."""
        from app.routes.geo_router import _COUNTRY_MAP
        region, currency = _COUNTRY_MAP["DE"]
        assert region == "europe"
        assert currency == "EUR"

    def test_unknown_country_fallback(self):
        """Unknown country code falls back to other/EUR."""
        from app.routes.geo_router import _COUNTRY_MAP
        region, currency = _COUNTRY_MAP.get("ZZ", ("other", "EUR"))
        assert region == "other"
        assert currency == "EUR"


# ---------------------------------------------------------------------------
# GET /geo/detect — localhost/missing IP → fallback
# ---------------------------------------------------------------------------

class TestGeoDetectFallback:
    def test_localhost_returns_fallback(self):
        """Localhost IP should return default fallback immediately (no external call)."""
        # TestClient uses 127.0.0.1 / testclient by default
        with patch("app.routes.geo_router.cache_get", return_value=None), \
             patch("app.routes.geo_router.cache_set"):
            resp = client.get("/geo/detect")
        assert resp.status_code == 200
        body = resp.json()
        assert body["region"] == "other"
        assert body["currency"] == "EUR"
        assert body["country_code"] is None

    def test_loopback_ipv6_returns_fallback(self):
        """::1 should return fallback."""
        with patch("app.routes.geo_router.cache_get", return_value=None), \
             patch("app.routes.geo_router.cache_set"):
            resp = client.get(
                "/geo/detect",
                headers={"x-forwarded-for": "::1"},
            )
        assert resp.status_code == 200
        assert resp.json()["region"] == "other"


# ---------------------------------------------------------------------------
# GET /geo/detect — successful external IP resolution
# ---------------------------------------------------------------------------

class TestGeoDetectSuccess:
    def test_us_ip_detected(self):
        """US IP should return americas/USD."""
        mock_resp = _mock_ip_api_response("US")
        mock_client = _mock_httpx_client(mock_resp)

        with patch("app.routes.geo_router.cache_get", return_value=None), \
             patch("app.routes.geo_router.cache_set") as mock_cache_set, \
             patch("httpx.AsyncClient", return_value=mock_client):
            resp = client.get(
                "/geo/detect",
                headers={"x-forwarded-for": "8.8.8.8"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["region"] == "americas"
        assert body["currency"] == "USD"
        assert body["country_code"] == "US"
        # Should cache the result
        mock_cache_set.assert_called_once()

    def test_jp_ip_detected(self):
        """Japanese IP should return japan/JPY."""
        mock_resp = _mock_ip_api_response("JP")
        mock_client = _mock_httpx_client(mock_resp)

        with patch("app.routes.geo_router.cache_get", return_value=None), \
             patch("app.routes.geo_router.cache_set"), \
             patch("httpx.AsyncClient", return_value=mock_client):
            resp = client.get(
                "/geo/detect",
                headers={"x-forwarded-for": "203.0.113.1"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["region"] == "japan"
        assert body["currency"] == "JPY"
        assert body["country_code"] == "JP"

    def test_unknown_country_returns_other_eur(self):
        """Country not in map should return other/EUR."""
        mock_resp = _mock_ip_api_response("ZZ")
        mock_client = _mock_httpx_client(mock_resp)

        with patch("app.routes.geo_router.cache_get", return_value=None), \
             patch("app.routes.geo_router.cache_set"), \
             patch("httpx.AsyncClient", return_value=mock_client):
            resp = client.get(
                "/geo/detect",
                headers={"x-forwarded-for": "198.51.100.1"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["region"] == "other"
        assert body["currency"] == "EUR"
        assert body["country_code"] == "ZZ"


# ---------------------------------------------------------------------------
# GET /geo/detect — cache hit
# ---------------------------------------------------------------------------

class TestGeoDetectCache:
    def test_cached_result_returned(self):
        """When cached, external API should not be called."""
        cached = {"region": "europe", "currency": "GBP", "country_code": "GB"}
        with patch("app.routes.geo_router.cache_get", return_value=cached):
            resp = client.get(
                "/geo/detect",
                headers={"x-forwarded-for": "8.8.4.4"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["region"] == "europe"
        assert body["currency"] == "GBP"
        assert body["country_code"] == "GB"


# ---------------------------------------------------------------------------
# GET /geo/detect — external API failure
# ---------------------------------------------------------------------------

class TestGeoDetectExternalFailure:
    def test_api_error_returns_fallback(self):
        """If ip-api.com throws, return fallback and cache it."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.routes.geo_router.cache_get", return_value=None), \
             patch("app.routes.geo_router.cache_set") as mock_cache_set, \
             patch("httpx.AsyncClient", return_value=mock_client):
            resp = client.get(
                "/geo/detect",
                headers={"x-forwarded-for": "10.0.0.1"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["region"] == "other"
        assert body["currency"] == "EUR"
        # Should cache fallback to avoid hammering
        mock_cache_set.assert_called_once()

    def test_api_non_success_status(self):
        """ip-api returning status != 'success' should use fallback."""
        mock_resp = _mock_ip_api_response("", status="fail")
        mock_client = _mock_httpx_client(mock_resp)

        with patch("app.routes.geo_router.cache_get", return_value=None), \
             patch("app.routes.geo_router.cache_set"), \
             patch("httpx.AsyncClient", return_value=mock_client):
            resp = client.get(
                "/geo/detect",
                headers={"x-forwarded-for": "192.0.2.1"},
            )

        assert resp.status_code == 200
        assert resp.json()["region"] == "other"


# ---------------------------------------------------------------------------
# Response format validation
# ---------------------------------------------------------------------------

class TestGeoResponseFormat:
    def test_response_has_required_keys(self):
        """Response must contain region, currency, country_code."""
        with patch("app.routes.geo_router.cache_get", return_value=None), \
             patch("app.routes.geo_router.cache_set"):
            resp = client.get("/geo/detect")
        body = resp.json()
        assert "region" in body
        assert "currency" in body
        assert "country_code" in body

    def test_region_is_string(self):
        """Region should always be a string."""
        with patch("app.routes.geo_router.cache_get", return_value=None), \
             patch("app.routes.geo_router.cache_set"):
            resp = client.get("/geo/detect")
        assert isinstance(resp.json()["region"], str)

    def test_currency_is_string(self):
        """Currency should always be a string."""
        with patch("app.routes.geo_router.cache_get", return_value=None), \
             patch("app.routes.geo_router.cache_set"):
            resp = client.get("/geo/detect")
        assert isinstance(resp.json()["currency"], str)
