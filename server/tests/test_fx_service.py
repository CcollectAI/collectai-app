"""Tests for app.lib.fx_service — live FX rate service with caching."""

import os

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")

from unittest.mock import AsyncMock, patch, MagicMock
import pytest


@pytest.mark.asyncio
async def test_get_rates_returns_fallback_when_api_fails():
    """When the external API fails, fallback rates from config are returned."""
    from app.cache import cache_delete

    cache_delete("fx:rates")

    with patch("app.lib.fx_service._fetch_live_rates", new_callable=AsyncMock, return_value=None):
        from app.lib.fx_service import get_rates

        rates = await get_rates()

    assert "USD" in rates
    assert "GBP" in rates
    assert "JPY" in rates
    assert "EUR" in rates
    assert rates["EUR"] == 1.0
    assert isinstance(rates["USD"], float)


@pytest.mark.asyncio
async def test_get_rates_uses_cache():
    """Second call should use cached value, not re-fetch."""
    from app.cache import cache_set, cache_delete

    cache_delete("fx:rates")
    fake_rates = {"USD": 0.91, "GBP": 1.17, "JPY": 0.006, "EUR": 1.0}
    cache_set("fx:rates", fake_rates, ttl=3600)

    from app.lib.fx_service import get_rates

    rates = await get_rates()
    assert rates == fake_rates

    # Cleanup
    cache_delete("fx:rates")


@pytest.mark.asyncio
async def test_get_rates_from_eur_inverts():
    """get_rates_from_eur should return inverse of get_rates."""
    from app.cache import cache_set, cache_delete

    cache_delete("fx:rates")
    cache_set("fx:rates", {"USD": 0.92, "GBP": 1.16, "JPY": 0.006, "EUR": 1.0}, ttl=3600)

    from app.lib.fx_service import get_rates_from_eur

    from_eur = await get_rates_from_eur()
    assert "USD" in from_eur
    # 1 / 0.92 ≈ 1.087
    assert from_eur["USD"] == pytest.approx(1.0 / 0.92, abs=0.01)

    cache_delete("fx:rates")


@pytest.mark.asyncio
async def test_convert_to_eur_same_currency():
    """Converting EUR to EUR returns the same amount."""
    from app.lib.fx_service import convert_to_eur

    result = await convert_to_eur(42.50, "EUR")
    assert result == 42.50


@pytest.mark.asyncio
async def test_convert_to_eur_usd():
    """Converting USD to EUR uses the rate."""
    from app.cache import cache_set, cache_delete

    cache_delete("fx:rates")
    cache_set("fx:rates", {"USD": 0.92, "GBP": 1.16, "JPY": 0.006, "EUR": 1.0}, ttl=3600)

    from app.lib.fx_service import convert_to_eur

    result = await convert_to_eur(100.0, "USD")
    assert result == pytest.approx(92.0, abs=0.01)

    cache_delete("fx:rates")


@pytest.mark.asyncio
async def test_convert_to_eur_unknown_currency():
    """Unknown currency returns amount as-is."""
    from app.lib.fx_service import convert_to_eur

    result = await convert_to_eur(50.0, "ZZZ")
    assert result == 50.0


@pytest.mark.asyncio
async def test_fetch_live_rates_happy_path():
    """When API returns valid data, rates are parsed correctly."""
    from app.cache import cache_delete

    cache_delete("fx:rates")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "rates": {"USD": 1.08, "GBP": 0.86, "JPY": 164.0},
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.lib.fx_service.httpx.AsyncClient", return_value=mock_client):
        from app.lib.fx_service import _fetch_live_rates

        rates = await _fetch_live_rates()

    assert rates is not None
    assert "USD" in rates
    assert "GBP" in rates
    assert "JPY" in rates
    # EUR→USD is 1.08, so USD→EUR should be ~0.926
    assert rates["USD"] == pytest.approx(1.0 / 1.08, abs=0.001)
