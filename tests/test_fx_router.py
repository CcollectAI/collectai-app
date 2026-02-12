"""Tests for app.routes.fx_router — GET /fx/rates endpoint."""

import os

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")

from unittest.mock import AsyncMock, patch
import pytest
from starlette.testclient import TestClient
from main import app

client = TestClient(app)


def test_fx_rates_returns_valid_structure():
    """GET /fx/rates should return base, rates, rates_from_eur."""
    fake_to_eur = {"USD": 0.92, "GBP": 1.16, "JPY": 0.006, "EUR": 1.0}
    fake_from_eur = {"USD": 1.087, "GBP": 0.862, "JPY": 166.67}

    with patch("app.routes.fx_router.get_rates", new_callable=AsyncMock, return_value=fake_to_eur):
        with patch("app.routes.fx_router.get_rates_from_eur", new_callable=AsyncMock, return_value=fake_from_eur):
            r = client.get("/fx/rates")

    assert r.status_code == 200
    data = r.json()
    assert data["base"] == "EUR"
    assert "USD" in data["rates"]
    assert "GBP" in data["rates"]
    assert "JPY" in data["rates"]
    # EUR should be filtered out of the response
    assert "EUR" not in data["rates"]
    assert "USD" in data["rates_from_eur"]


def test_fx_rates_no_auth_required():
    """FX rates endpoint should be public (no auth header needed)."""
    fake_to_eur = {"USD": 0.92, "EUR": 1.0}
    fake_from_eur = {"USD": 1.087}

    with patch("app.routes.fx_router.get_rates", new_callable=AsyncMock, return_value=fake_to_eur):
        with patch("app.routes.fx_router.get_rates_from_eur", new_callable=AsyncMock, return_value=fake_from_eur):
            r = client.get("/fx/rates")

    # Should not get 401/403 even without auth
    assert r.status_code == 200
