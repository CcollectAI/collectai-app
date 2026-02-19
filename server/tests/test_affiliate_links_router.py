"""Tests for affiliate_links_router — marketplace affiliate link generation."""

import pytest
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
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_basic_query_returns_links(client: AsyncClient):
    """Basic query should return at least one link (eBay)."""
    resp = await client.get("/marketplace/affiliate-links", params={"query": "charizard"})
    assert resp.status_code == 200
    data = resp.json()
    assert "links" in data
    assert len(data["links"]) >= 1
    # eBay should always be first
    assert data["links"][0]["source"] == "ebay"
    assert "charizard" in data["links"][0]["url"]


@pytest.mark.anyio
async def test_tcg_category_includes_tcgplayer(client: AsyncClient):
    """TCG categories should include TCGPlayer and Cardmarket links."""
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "pikachu", "category": "pokemon"},
    )
    assert resp.status_code == 200
    sources = [link["source"] for link in resp.json()["links"]]
    assert "ebay" in sources
    assert "tcgplayer" in sources
    assert "cardmarket" in sources


@pytest.mark.anyio
async def test_non_tcg_excludes_tcgplayer(client: AsyncClient):
    """Non-TCG categories should not include TCGPlayer or Cardmarket."""
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "batman comic", "category": "comics"},
    )
    assert resp.status_code == 200
    sources = [link["source"] for link in resp.json()["links"]]
    assert "ebay" in sources
    assert "tcgplayer" not in sources
    assert "cardmarket" not in sources


@pytest.mark.anyio
async def test_limit_param(client: AsyncClient):
    """Limit parameter should cap the number of links returned."""
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "pikachu", "category": "pokemon", "limit": 1},
    )
    assert resp.status_code == 200
    assert len(resp.json()["links"]) == 1


@pytest.mark.anyio
async def test_no_auth_required(client: AsyncClient):
    """Endpoint should work without any auth header."""
    resp = await client.get("/marketplace/affiliate-links", params={"query": "test"})
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_empty_query_validation(client: AsyncClient):
    """Empty query should return 422 validation error."""
    resp = await client.get("/marketplace/affiliate-links", params={"query": ""})
    assert resp.status_code == 422
