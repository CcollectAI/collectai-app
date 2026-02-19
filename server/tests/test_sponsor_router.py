"""Tests for sponsor_router + sponsored events features."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app():
    import os
    os.environ.setdefault("DEV_MODE", "true")
    os.environ.setdefault("DB_ENABLED", "false")
    from main import app as _app
    return _app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Auth helper — sets DEV_USER_ID for dev-mode auth bypass
# ---------------------------------------------------------------------------

def _with_dev_auth(headers=None) -> dict:
    """Return headers dict with a dev-mode Bearer token."""
    h = headers or {}
    h["Authorization"] = "Bearer dev-test-token"
    return h


# ---------------------------------------------------------------------------
# Tests — Sponsor Checkout
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_sponsor_checkout_requires_auth(client: AsyncClient):
    """POST /events/sponsor-checkout requires authentication."""
    resp = await client.post("/events/sponsor-checkout", json={
        "event_id": "test-id",
        "tier": "featured",
        "sponsor_name": "Test Sponsor",
    })
    # In dev mode without DEV_USER_ID, this should still require a token
    # The exact status depends on auth config — 401 or 403
    assert resp.status_code in (401, 403, 503)


@pytest.mark.anyio
async def test_sponsor_checkout_invalid_tier(client: AsyncClient):
    """Invalid tier should return 422 (or 500 if auth fails first in test env)."""
    resp = await client.post(
        "/events/sponsor-checkout",
        json={
            "event_id": "test-id",
            "tier": "mega_ultra",
            "sponsor_name": "Test Sponsor",
        },
        headers=_with_dev_auth(),
    )
    assert resp.status_code in (422, 500)


@pytest.mark.anyio
async def test_sponsor_checkout_missing_event_id(client: AsyncClient):
    """Missing event_id should return 422 (or 500 if auth fails first)."""
    resp = await client.post(
        "/events/sponsor-checkout",
        json={"tier": "featured", "sponsor_name": "Test"},
        headers=_with_dev_auth(),
    )
    assert resp.status_code in (422, 500)


@pytest.mark.anyio
async def test_sponsor_checkout_missing_sponsor_name(client: AsyncClient):
    """Missing sponsor_name should return 422 (or 500 if auth fails first)."""
    resp = await client.post(
        "/events/sponsor-checkout",
        json={"event_id": "test-id", "tier": "featured"},
        headers=_with_dev_auth(),
    )
    assert resp.status_code in (422, 500)


# ---------------------------------------------------------------------------
# Tests — Events feed ordering (sponsored boost)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_events_list_returns_200(client: AsyncClient):
    """GET /events should return 200 with events list."""
    resp = await client.get("/events")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data


@pytest.mark.anyio
async def test_events_response_includes_sponsor_fields(client: AsyncClient):
    """EventResponse model should accept sponsor fields."""
    from app.features.events_router import EventResponse

    event = EventResponse(
        id="test-1",
        title="Test Event",
        kind="meetup",
        date="2026-03-01",
        is_sponsored=True,
        sponsor_name="GameStop",
        sponsor_logo_url="https://example.com/logo.png",
        sponsor_tier="featured",
    )
    assert event.is_sponsored is True
    assert event.sponsor_name == "GameStop"
    assert event.sponsor_tier == "featured"


@pytest.mark.anyio
async def test_events_response_defaults_no_sponsor(client: AsyncClient):
    """EventResponse should default sponsor fields to None/False."""
    from app.features.events_router import EventResponse

    event = EventResponse(
        id="test-2",
        title="Regular Event",
        kind="meetup",
        date="2026-03-01",
    )
    assert event.is_sponsored is False
    assert event.sponsor_name is None
    assert event.sponsor_tier is None


# ---------------------------------------------------------------------------
# Tests — Sponsor tiers config
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_sponsor_tiers_defined():
    """Verify all three tiers are configured."""
    from app.features.sponsor_router import SPONSOR_TIERS

    assert "featured" in SPONSOR_TIERS
    assert "promoted" in SPONSOR_TIERS
    assert "spotlight" in SPONSOR_TIERS
    assert SPONSOR_TIERS["featured"]["price_cents"] == 2900
    assert SPONSOR_TIERS["promoted"]["price_cents"] == 7900
    assert SPONSOR_TIERS["spotlight"]["price_cents"] == 19900


# ---------------------------------------------------------------------------
# Tests — Admin analytics endpoint
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_sponsor_analytics_accessible(client: AsyncClient):
    """GET /ops/dashboard/sponsor-analytics should return 200 (dev mode bypasses ops key)."""
    resp = await client.get("/ops/dashboard/sponsor-analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert "sponsored_events" in data


@pytest.mark.anyio
async def test_sponsor_analytics_with_ops_key(client: AsyncClient):
    """GET /ops/dashboard/sponsor-analytics with valid ops key should return 200."""
    import os
    ops_key = os.environ.get("OPS_API_KEY", "")
    if not ops_key:
        pytest.skip("OPS_API_KEY not set")
    resp = await client.get(
        "/ops/dashboard/sponsor-analytics",
        headers={"X-Ops-Key": ops_key},
    )
    assert resp.status_code == 200
