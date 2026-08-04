"""Tests for app/features/catalog_browser_router.py — Catalog browse + progress tracking.

Covers:
  - GET   /catalog/{category_id}/items — browse catalog (happy path, with search, with rarity)
  - PATCH /items/{item_id}/progress   — update progress (happy path, IDOR, no fields, not found)
  - GET   /items/{item_id}/progress   — get progress (happy path, IDOR, not found)
  - DB unavailable (503) checks

All tests mock get_pool() (from app.db) and override the auth dependency so no
real database is needed.
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
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("PER_USER_RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)

TEST_USER_ID = "catalog-test-user-001"
OTHER_USER_ID = "catalog-other-user-999"
ITEM_UUID = "00000000-0000-0000-0000-000000000042"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pool():
    """Create a mock asyncpg pool that supports both direct calls and acquire()."""
    pool = MagicMock()

    # The catalog_browser_router calls pool.fetchval/pool.fetch/pool.execute
    # directly (not via pool.acquire()), so we need to mock those too.
    pool.fetchval = AsyncMock(return_value=0)
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock(return_value="UPDATE 1")

    # Also provide acquire() for any endpoints that use it
    mock_conn = AsyncMock()
    mock_conn.fetchval = pool.fetchval
    mock_conn.fetch = pool.fetch
    mock_conn.fetchrow = pool.fetchrow
    mock_conn.execute = pool.execute

    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=mock_acquire)

    return pool


def _auth_override(user_id: str = TEST_USER_ID):
    from app.auth import get_current_user_id

    async def _fake_user():
        return user_id

    app.dependency_overrides[get_current_user_id] = _fake_user


def _clear_overrides():
    app.dependency_overrides.clear()


def _make_catalog_row(**overrides):
    """Create a mock catalog_items row."""
    base = {
        "id": "cat-item-001",
        "category": "pokemon",
        "item_key": "charizard-base",
        "title": "Charizard Base Set",
        "brand": "Pokemon",
        "rarity": "Rare Holo",
        "notes": None,
        "image_url": "https://example.com/charizard.png",
        "external_id": "4-102",
        "set_code": "base1",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests: GET /catalog/{category_id}/items — Browse catalog
# ---------------------------------------------------------------------------

class TestBrowseCatalog:
    @patch("app.features.catalog_browser_router.get_pool")
    def test_browse_empty_category(self, mock_get_pool):
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchval = AsyncMock(return_value=0)
        pool.fetch = AsyncMock(return_value=[])

        resp = client.get("/catalog/pokemon/items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["category_id"] == "pokemon"
        assert data["limit"] == 50
        assert data["offset"] == 0

    @patch("app.features.catalog_browser_router.get_pool")
    def test_browse_with_results(self, mock_get_pool):
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchval = AsyncMock(return_value=2)
        pool.fetch = AsyncMock(side_effect=[
            [_make_catalog_row(), _make_catalog_row(id="cat-item-002", title="Blastoise")],
            [],  # price_rows (empty)
        ])

        resp = client.get("/catalog/pokemon/items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["title"] == "Charizard Base Set"

    @patch("app.features.catalog_browser_router.get_pool")
    def test_browse_with_search_query(self, mock_get_pool):
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchval = AsyncMock(return_value=1)
        pool.fetch = AsyncMock(side_effect=[
            [_make_catalog_row()],
            [],  # price_rows
        ])

        resp = client.get("/catalog/pokemon/items?q=charizard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @patch("app.features.catalog_browser_router.get_pool")
    def test_browse_with_rarity_filter(self, mock_get_pool):
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchval = AsyncMock(return_value=1)
        pool.fetch = AsyncMock(side_effect=[
            [_make_catalog_row()],
            [],  # price_rows
        ])

        resp = client.get("/catalog/pokemon/items?rarity=Rare+Holo")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @patch("app.features.catalog_browser_router.get_pool")
    def test_browse_with_pagination(self, mock_get_pool):
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchval = AsyncMock(return_value=100)
        pool.fetch = AsyncMock(side_effect=[
            [_make_catalog_row()],
            [],  # price_rows
        ])

        resp = client.get("/catalog/pokemon/items?limit=10&offset=20")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 10
        assert data["offset"] == 20
        assert data["total"] == 100

    @patch("app.features.catalog_browser_router.get_pool")
    def test_browse_db_unavailable(self, mock_get_pool):
        mock_get_pool.return_value = None

        resp = client.get("/catalog/pokemon/items")
        assert resp.status_code == 503

    def test_browse_limit_out_of_range(self):
        """limit > 200 should fail validation."""
        resp = client.get("/catalog/pokemon/items?limit=999")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: PATCH /items/{item_id}/progress — Update progress
# ---------------------------------------------------------------------------

class TestUpdateProgress:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.catalog_browser_router.get_pool")
    def test_update_progress_success(self, mock_get_pool):
        pool = _mock_pool()
        mock_get_pool.return_value = pool

        # fetchval: ownership check returns user_id
        pool.fetchval = AsyncMock(return_value=TEST_USER_ID)
        # execute: UPDATE
        pool.execute = AsyncMock(return_value="UPDATE 1")
        # fetchrow: return updated values
        pool.fetchrow = AsyncMock(return_value={
            "progress_status": "reading",
            "progress_pct": 50,
            "progress_notes": "Halfway through!",
        })

        resp = client.patch(f"/items/{ITEM_UUID}/progress", json={
            "progress_status": "reading",
            "progress_pct": 50,
            "progress_notes": "Halfway through!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == ITEM_UUID
        assert data["progress_status"] == "reading"
        assert data["progress_pct"] == 50

    @patch("app.features.catalog_browser_router.get_pool")
    def test_update_progress_idor_forbidden(self, mock_get_pool):
        """User cannot update progress on another user's item."""
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchval = AsyncMock(return_value=OTHER_USER_ID)

        resp = client.patch(f"/items/{ITEM_UUID}/progress", json={
            "progress_status": "reading",
        })
        assert resp.status_code == 403

    @patch("app.features.catalog_browser_router.get_pool")
    def test_update_progress_item_not_found(self, mock_get_pool):
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchval = AsyncMock(return_value=None)

        resp = client.patch(f"/items/{ITEM_UUID}/progress", json={
            "progress_status": "reading",
        })
        assert resp.status_code == 404

    @patch("app.features.catalog_browser_router.get_pool")
    def test_update_progress_no_fields(self, mock_get_pool):
        """Empty update (all fields None) returns 400."""
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchval = AsyncMock(return_value=TEST_USER_ID)

        resp = client.patch(f"/items/{ITEM_UUID}/progress", json={})
        assert resp.status_code == 400

    @patch("app.features.catalog_browser_router.get_pool")
    def test_update_progress_db_unavailable(self, mock_get_pool):
        mock_get_pool.return_value = None

        resp = client.patch(f"/items/{ITEM_UUID}/progress", json={
            "progress_status": "reading",
        })
        assert resp.status_code == 503

    def test_update_progress_invalid_status(self):
        """progress_status must match the regex pattern."""
        resp = client.patch(f"/items/{ITEM_UUID}/progress", json={
            "progress_status": "invalid_status",
        })
        assert resp.status_code == 422

    def test_update_progress_pct_out_of_range(self):
        """progress_pct must be 0-100."""
        resp = client.patch(f"/items/{ITEM_UUID}/progress", json={
            "progress_pct": 150,
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: GET /items/{item_id}/progress — Get progress
# ---------------------------------------------------------------------------

class TestGetProgress:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.catalog_browser_router.get_pool")
    def test_get_progress_success(self, mock_get_pool):
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchrow = AsyncMock(return_value={
            "user_id": TEST_USER_ID,
            "progress_status": "completed",
            "progress_pct": 100,
            "progress_notes": "Done!",
        })

        resp = client.get(f"/items/{ITEM_UUID}/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == ITEM_UUID
        assert data["progress_status"] == "completed"
        assert data["progress_pct"] == 100

    @patch("app.features.catalog_browser_router.get_pool")
    def test_get_progress_not_found(self, mock_get_pool):
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchrow = AsyncMock(return_value=None)

        resp = client.get(f"/items/{ITEM_UUID}/progress")
        assert resp.status_code == 404

    @patch("app.features.catalog_browser_router.get_pool")
    def test_get_progress_idor_forbidden(self, mock_get_pool):
        """Cannot view another user's progress."""
        pool = _mock_pool()
        mock_get_pool.return_value = pool
        pool.fetchrow = AsyncMock(return_value={
            "user_id": OTHER_USER_ID,
            "progress_status": "reading",
            "progress_pct": 25,
            "progress_notes": None,
        })

        resp = client.get(f"/items/{ITEM_UUID}/progress")
        assert resp.status_code == 403

    @patch("app.features.catalog_browser_router.get_pool")
    def test_get_progress_db_unavailable(self, mock_get_pool):
        mock_get_pool.return_value = None

        resp = client.get(f"/items/{ITEM_UUID}/progress")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Accessory / packaging-filler suppression
#
# The tcgcsv importer ingests TCGPlayer's full product list per game, so the
# lorcana catalog carried 85 "Puzzle Insert" rows — the cardboard spacer inside
# a booster box — plus playmats, sleeves and deck boxes, whose dead CDN art
# rendered as black tiles in the browse grid.
#
# The hard part is NOT matching the product words. TCGPlayer also sells promo
# CARDS named after the accessory they shipped with, and a bare-term filter hid
# 34 of them. Every "should NOT be filtered" case below is a real row from the
# live catalog that an earlier revision wrongly hid.
# ---------------------------------------------------------------------------

def _is_filtered(title: str) -> bool:
    """Replicate the router's two-part predicate in Python.

    Postgres `\\y` (word boundary) == Python `\\b`; everything else is the same
    POSIX syntax.
    """
    import re
    from app.features.catalog_browser_router import (
        _ACCESSORY_TITLE_RE,
        _CARD_CODE_RE,
    )

    looks_like_product = re.search(_ACCESSORY_TITLE_RE.replace(r"\y", r"\b"), title, re.I)
    has_card_code = re.search(_CARD_CODE_RE, title)
    return bool(looks_like_product) and not bool(has_card_code)


class TestAccessoryFilter:
    @pytest.mark.parametrize("title", [
        # Product naming: ':' or '-' straight after the item type.
        "Official Playmat: Boa Hancock",
        "Official Playmat - Elsa Spirit of Winter",
        "Tournament Playmat - Nationals 2024",
        "Championship Playmat: Ace (Marineford)",
        "Official Card Sleeves - Snow White (65 count)",
        "Official DCG Card Sleeves: Royal Knights",
        "Official Deck Box - Rapunzel Sunshine",
        "Official Portfolio Binder - 9 Pocket",
        # Puzzle inserts appear mid-title and carry a NUMERIC set number.
        "Mickey Mouse - Brave Little Tailor Puzzle Insert (Top Right) [1] (Normal)",
        "Azurite Sea Puzzle Insert (Set of 9) [6] (Normal)",
    ])
    def test_filters_accessories_and_filler(self, title):
        assert _is_filtered(title), f"should be filtered: {title}"

    @pytest.mark.parametrize("title", [
        # Plain cards.
        "Elsa - Snow Queen [1] (Normal)",
        "Let It Go [5] (Normal)",
        # Sealed product is a collected format — never filtered.
        "Azurite Sea Booster Pack",
        "Rise of the Floodborn Booster Box",
        "Illumineer's Quest Deck Bundle",
        # Cards whose NAME contains an accessory word. Bare-term matching hid
        # all of these; "Binder" alone was 34 real cards out of 36 matches.
        "Dihada, Binder of Wills",
        "Fiend Binder",
        "Maliss Q White Binder [MP25] (1st Edition)",
        # Promo cards named after the product they shipped with. The parenthesis
        # form has no ':'/'-' separator after the item type...
        "Crocodile (Seven Warlords of the Sea Binder Set) [OP-PR] (Foil)",
        "MetalGarurumon (Omnimon Binder Set) [BT-17] (Foil)",
        "Monkey.D.Luffy (Official Playmat Limited Edition Vol.5) [OP-PR] (Foil)",
        "Calumon (Digimon Card Game Deck Box Set) [EX-02] (Foil)",
        # ...and these two DO have a dash, so only the card-set-code guard
        # keeps them visible. They are why that guard exists.
        "Usopp (Official Playmat -Limited Edition Vol. 3-) [OP-PR] (Foil)",
        "Zeus (Official Playmat -Bandai Card Games Fest 24-25 Edition-) [OP-PR] (Foil)",
    ])
    def test_spares_real_cards(self, title):
        assert not _is_filtered(title), f"should NOT be filtered: {title}"

    def test_filter_is_scoped_to_tcg_card_categories(self):
        """In a merch category the accessory IS the collectible.

        Applied catalogue-wide this would hide "Pokemon Base Set Binder (1999)"
        from retro_pokemon and "Pikachu Leather Deck Box" from nintendo_merch —
        both legitimate items in a category that collects merchandise.
        """
        from app.features.catalog_browser_router import _ACCESSORY_FILTERED_CATEGORIES

        for cat in ("mtg", "pokemon", "yugioh", "lorcana", "digimon", "one_piece_tcg"):
            assert cat in _ACCESSORY_FILTERED_CATEGORIES

        for cat in ("retro_pokemon", "nintendo_merch", "pop_fandom", "disney",
                    "theme_park", "loungefly", "kpop_merch"):
            assert cat not in _ACCESSORY_FILTERED_CATEGORIES
