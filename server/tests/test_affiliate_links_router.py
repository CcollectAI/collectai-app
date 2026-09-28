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
    # With no category we have nothing better to suggest, so eBay leads.
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


# ---------------------------------------------------------------------------
# Ordering, qualification and price ceiling
#
# `app/(tabs)/wishlist.tsx` opens links[0] directly, so ordering is behaviour,
# not cosmetics. Before 2026-08-04 eBay was appended first unconditionally and
# every MTG single routed to eBay US with Cardmarket unused further down.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_category_preference_beats_ebay_first(client: AsyncClient):
    """For a TCG single the first link is Cardmarket, not eBay."""
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "Bayou", "category": "mtg"},
    )
    assert resp.status_code == 200
    assert resp.json()["links"][0]["source"] == "cardmarket"


@pytest.mark.anyio
async def test_lego_prefers_bricklink(client: AsyncClient):
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "10179", "category": "lego"},
    )
    assert resp.status_code == 200
    assert resp.json()["links"][0]["source"] == "bricklink"


@pytest.mark.anyio
async def test_cardmarket_uses_the_right_game_path(client: AsyncClient):
    """Cardmarket namespaces its catalogue per game in the PATH.

    The builder hardcoded /en/Pokemon/ for every category, so MTG, Yu-Gi-Oh and
    Lorcana searches were run against the Pokemon catalogue.
    """
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "Bayou", "category": "mtg"},
    )
    cm = next(x for x in resp.json()["links"] if x["source"] == "cardmarket")
    assert "/en/Magic/" in cm["url"]
    assert "/en/Pokemon/" not in cm["url"]


@pytest.mark.anyio
async def test_ebay_url_is_narrowed(client: AsyncClient):
    """eBay search carries category, Buy-It-Now, and cheapest-first sort."""
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "Bayou", "category": "mtg"},
    )
    ebay = next(x for x in resp.json()["links"] if x["source"] == "ebay")
    assert "_sacat=2536" in ebay["url"]   # Collectible Card Games
    assert "LH_BIN=1" in ebay["url"]      # Buy It Now only
    assert "_sop=15" in ebay["url"]       # price + shipping, lowest first


@pytest.mark.anyio
async def test_query_is_qualified_with_category_suffix(client: AsyncClient):
    """A bare title is not shoppable — "Bayou" alone returns swamp photos."""
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "Bayou", "category": "mtg"},
    )
    ebay = next(x for x in resp.json()["links"] if x["source"] == "ebay")
    assert "Bayou" in ebay["url"]
    assert "MTG" in ebay["url"]


@pytest.mark.anyio
async def test_suffix_not_duplicated_when_already_present(client: AsyncClient):
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "Bayou MTG", "category": "mtg"},
    )
    ebay = next(x for x in resp.json()["links"] if x["source"] == "ebay")
    assert ebay["url"].lower().count("mtg") == 1


@pytest.mark.anyio
async def test_max_price_becomes_an_ebay_ceiling(client: AsyncClient):
    """A target price caps the search rather than only labelling the alert."""
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "Bayou", "category": "mtg", "max_price": 8015, "max_price_currency": "EUR"},
    )
    assert resp.status_code == 200
    ebay = next(x for x in resp.json()["links"] if x["source"] == "ebay")
    assert "_udhi=" in ebay["url"]


@pytest.mark.anyio
async def test_no_max_price_means_no_ceiling(client: AsyncClient):
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "Bayou", "category": "mtg"},
    )
    ebay = next(x for x in resp.json()["links"] if x["source"] == "ebay")
    assert "_udhi=" not in ebay["url"]


@pytest.mark.anyio
async def test_every_profile_names_only_buildable_sources(client: AsyncClient):
    """A source with no search builder silently drops out of the response.

    Guards the gap that made this worth writing: `affiliate.py` tags 16 networks
    but only nine can build a *search* URL. Naming e.g. "chrono24" in a profile
    would look wired while returning nothing.
    """
    from app.routes.affiliate_links_router import _CATEGORY_PROFILES, _SEARCHABLE_SOURCES

    offenders = {
        cat: [s for s in prof.sources if s not in _SEARCHABLE_SOURCES]
        for cat, prof in _CATEGORY_PROFILES.items()
    }
    assert not {k: v for k, v in offenders.items() if v}


@pytest.mark.anyio
async def test_unknown_category_still_returns_links(client: AsyncClient):
    """An unmapped category degrades to the default profile, not an empty list."""
    resp = await client.get(
        "/marketplace/affiliate-links",
        params={"query": "something", "category": "not_a_real_category"},
    )
    assert resp.status_code == 200
    sources = [x["source"] for x in resp.json()["links"]]
    assert sources[0] == "ebay"
    assert len(sources) >= 1


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


def test_chrono24_search_runs_the_search():
    # Without dosearch=true Chrono24 ignores the query and shows an empty form.
    from app.routes.affiliate_links_router import _build_chrono24_search_url

    url = _build_chrono24_search_url("rolex submariner")
    assert "dosearch=true" in url
    assert "query=rolex+submariner" in url


def test_yahoo_auctions_jp_hidden_in_europe():
    # Yahoo! JAPAN blocks the EEA and the UK; the link opens a notice, not a search.
    from app.routes.affiliate_links_router import _eligible_sources

    assert "yahoo_auctions_jp" not in _eligible_sources("anime_figures", "europe")
    assert "yahoo_auctions_jp" in _eligible_sources("anime_figures", "americas")
    assert "yahoo_auctions_jp" in _eligible_sources("pokemon", "japan")


@pytest.mark.anyio
async def test_saved_region_used_when_caller_sends_none(app, client: AsyncClient, monkeypatch):
    # useItemMarketplace and barcode-scan send no region; a European member
    # must still not be offered Yahoo! JAPAN, which blocks the EEA.
    from contextlib import asynccontextmanager
    import app.routes.affiliate_links_router as r
    from app.auth import get_optional_user_id

    class _Conn:
        async def fetchval(self, sql, uid):
            assert "user_settings" in sql and uid == "u-1"
            return "europe"

    @asynccontextmanager
    async def _get_conn():
        yield _Conn()

    monkeypatch.setattr(r, "db_configured", lambda: True)
    monkeypatch.setattr(r, "get_conn", _get_conn)
    app.dependency_overrides[get_optional_user_id] = lambda: "u-1"
    try:
        resp = await client.get("/marketplace/affiliate-links",
                                params={"query": "miku figure", "category": "anime_figures", "limit": 10})
    finally:
        app.dependency_overrides.pop(get_optional_user_id, None)
    sources = [l["source"] for l in resp.json()["links"]]
    assert "yahoo_auctions_jp" not in sources
    assert "amiami" in sources


def test_mercari_hidden_in_europe():
    from app.routes.affiliate_links_router import _eligible_sources

    assert "mercari" not in _eligible_sources("funko", "europe")
    assert "mercari" in _eligible_sources("funko", "americas")
    assert "mercari" in _eligible_sources("funko", "")
