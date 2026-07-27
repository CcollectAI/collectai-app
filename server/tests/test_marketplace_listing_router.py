"""Tests for app/features/marketplace_listing_router.py — Multi-marketplace selling.

Covers:
  Accounts:
  - GET    /marketplace/listings/accounts — list accounts
  - POST   /marketplace/listings/accounts — connect account (happy, invalid, duplicate)
  - DELETE /marketplace/listings/accounts/{id} — disconnect account (happy, not found)

  Listings:
  - POST   /marketplace/listings — create listing (happy path, validation errors)
  - GET    /marketplace/listings/{id} — get listing (happy, not found)
  - DELETE /marketplace/listings/{id} — delist (happy, not found)

  Fees:
  - POST   /marketplace/listings/fees/calculate — fee calculator (happy, invalid marketplace)

  Validation:
  - Invalid marketplace_id, format, UUID, missing fields

All tests mock get_db_pool() and override the auth dependency so no real
database is needed.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
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

TEST_USER_ID = "mktplace-test-user-001"
LISTING_UUID = "00000000-0000-0000-0000-000000000010"
ITEM_UUID = "00000000-0000-0000-0000-000000000020"
ACCOUNT_UUID = "00000000-0000-0000-0000-000000000030"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pool():
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetchval = AsyncMock(return_value=None)

    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=mock_acquire)

    return pool, mock_conn


def _auth_override():
    from app.auth import get_current_user_id, require_seller_age_verified

    async def _fake_user():
        return TEST_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_user

    # The mutating routes (connect account, create/publish listing) depend on
    # `require_seller_age_verified`, NOT plain get_current_user_id. That
    # dependency runs BEFORE the route body and does its own get_db_pool()
    # (auth.py:103), returning 503 when there is no pool — so patching
    # `marketplace_listing_router.get_db_pool` never got a chance and 8 tests
    # failed with 503 on assertions about 201/400/409/422.
    #
    # Overriding it here is right rather than a workaround: the age gate has
    # its own coverage, and these tests are about the listing router's own
    # logic. Without the override they could only ever assert the gate.
    app.dependency_overrides[require_seller_age_verified] = _fake_user


def _clear_overrides():
    app.dependency_overrides.clear()


def _make_listing_row(**overrides):
    """Create a mock DB row that satisfies _row_to_listing()."""
    now = datetime.now(timezone.utc)
    base = {
        "id": LISTING_UUID,
        "user_id": TEST_USER_ID,
        "item_id": ITEM_UUID,
        "account_id": None,
        "marketplace_id": "ebay",
        "external_listing_id": None,
        "listing_url": None,
        "listing_title": "Test Listing",
        "listing_description": "A test listing",
        "price": 49.99,
        "currency": "EUR",
        "original_price": None,
        "format": "fixed_price",
        "auction_duration_days": None,
        "auction_start_price": None,
        "buy_it_now_price": None,
        "quantity": 1,
        "condition_label": "Like New",
        "condition_notes": None,
        "shipping_method": "standard",
        "shipping_cost": 5.0,
        "ships_international": False,
        "returns_accepted": True,
        "returns_days": 14,
        "status": "draft",
        "status_message": None,
        "views_count": 0,
        "watchers_count": 0,
        "offers_count": 0,
        "estimated_fees": None,
        "estimated_net": None,
        "fee_percentage": None,
        "listed_at": None,
        "expires_at": None,
        "sold_at": None,
        "synced_at": None,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return base


def _make_account_row(**overrides):
    now = datetime.now(timezone.utc)
    base = {
        "id": ACCOUNT_UUID,
        "user_id": TEST_USER_ID,
        "marketplace_id": "ebay",
        "seller_name": "test_seller",
        "seller_id": "seller123",
        "scopes": ["read", "write"],
        "is_active": True,
        "connected_at": now,
        "last_sync_at": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests: Accounts — GET /marketplace/listings/accounts
# ---------------------------------------------------------------------------

class TestListAccounts:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_list_accounts_empty(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(return_value=[])

        resp = client.get("/marketplace/listings/accounts")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_list_accounts_with_data(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(return_value=[_make_account_row()])

        resp = client.get("/marketplace/listings/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["marketplace_id"] == "ebay"
        assert data[0]["seller_name"] == "test_seller"

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_list_accounts_db_unavailable(self, mock_get_pool):
        mock_get_pool.return_value = None
        resp = client.get("/marketplace/listings/accounts")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Tests: Accounts — POST /marketplace/listings/accounts
# ---------------------------------------------------------------------------

class TestConnectAccount:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_connect_account_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        # No existing account
        conn.fetchrow = AsyncMock(side_effect=[None, _make_account_row()])

        resp = client.post("/marketplace/listings/accounts", json={
            "marketplace_id": "ebay",
            "seller_name": "test_seller",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["marketplace_id"] == "ebay"

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_connect_account_duplicate(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        # Existing account found
        conn.fetchrow = AsyncMock(return_value={"id": ACCOUNT_UUID})

        resp = client.post("/marketplace/listings/accounts", json={
            "marketplace_id": "ebay",
        })
        assert resp.status_code == 409

    def test_connect_account_invalid_marketplace(self):
        """Invalid marketplace_id should be rejected."""
        resp = client.post("/marketplace/listings/accounts", json={
            "marketplace_id": "invalid_marketplace",
        })
        # Will be 400 (if pool available) or 503 (no pool). The validation happens
        # before pool check, so it should be 400.
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Accounts — DELETE /marketplace/listings/accounts/{id}
# ---------------------------------------------------------------------------

class TestDisconnectAccount:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_disconnect_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.execute = AsyncMock(return_value="DELETE 1")

        resp = client.delete(f"/marketplace/listings/accounts/{ACCOUNT_UUID}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_disconnect_not_found(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.execute = AsyncMock(return_value="DELETE 0")

        resp = client.delete(f"/marketplace/listings/accounts/{ACCOUNT_UUID}")
        assert resp.status_code == 404

    def test_disconnect_invalid_uuid(self):
        resp = client.delete("/marketplace/listings/accounts/not-a-uuid")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Listings — POST /marketplace/listings (create)
# ---------------------------------------------------------------------------

class TestCreateListing:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_create_listing_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        # fetchrow: item ownership check, then RETURNING row
        conn.fetchrow = AsyncMock(side_effect=[
            {"id": ITEM_UUID},  # item exists
            _make_listing_row(),  # RETURNING *
        ])

        resp = client.post("/marketplace/listings", json={
            "item_id": ITEM_UUID,
            "marketplace_id": "ebay",
            "listing_title": "Rare Charizard PSA 10",
            "price": 500.0,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["listing_title"] == "Test Listing"
        assert data["marketplace_id"] == "ebay"

    def test_create_listing_invalid_marketplace(self):
        """Invalid marketplace_id returns 400."""
        resp = client.post("/marketplace/listings", json={
            "item_id": ITEM_UUID,
            "marketplace_id": "amazon",
            "listing_title": "Test",
            "price": 10.0,
        })
        # marketplace_id validation happens before DB check
        assert resp.status_code == 400

    def test_create_listing_invalid_format(self):
        """Invalid listing format returns 400."""
        resp = client.post("/marketplace/listings", json={
            "item_id": ITEM_UUID,
            "marketplace_id": "ebay",
            "listing_title": "Test",
            "price": 10.0,
            "format": "swap",
        })
        assert resp.status_code == 400

    def test_create_listing_zero_price(self):
        """Price must be > 0."""
        resp = client.post("/marketplace/listings", json={
            "item_id": ITEM_UUID,
            "marketplace_id": "ebay",
            "listing_title": "Free item",
            "price": 0,
        })
        assert resp.status_code == 422

    def test_create_listing_missing_title(self):
        resp = client.post("/marketplace/listings", json={
            "item_id": ITEM_UUID,
            "marketplace_id": "ebay",
            "price": 10.0,
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Listings — GET /marketplace/listings/{listing_id}
# ---------------------------------------------------------------------------

class TestGetListing:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_get_listing_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_listing_row())

        resp = client.get(f"/marketplace/listings/{LISTING_UUID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == LISTING_UUID
        assert data["listing_title"] == "Test Listing"

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_get_listing_not_found(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=None)

        resp = client.get(f"/marketplace/listings/{LISTING_UUID}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Listings — DELETE /marketplace/listings/{listing_id} (delist)
# ---------------------------------------------------------------------------

class TestDeleteListing:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_delist_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.execute = AsyncMock(return_value="UPDATE 1")

        resp = client.delete(f"/marketplace/listings/{LISTING_UUID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["status"] == "delisted"

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_delist_not_found(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchrow = AsyncMock(return_value=None)

        resp = client.delete(f"/marketplace/listings/{LISTING_UUID}")
        assert resp.status_code == 404

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_delist_already_sold_conflict(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchrow = AsyncMock(return_value={"id": LISTING_UUID, "status": "sold"})

        resp = client.delete(f"/marketplace/listings/{LISTING_UUID}")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Tests: Fees — POST /marketplace/listings/fees/calculate
# ---------------------------------------------------------------------------

class TestCalculateFees:
    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_calculate_fees_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value={
            "base_fee_pct": 10.0,
            "payment_processing_pct": 2.9,
            "fixed_fee": 0.30,
            "min_fee": 0,
            "max_fee": None,
        })

        resp = client.post("/marketplace/listings/fees/calculate", json={
            "marketplace_id": "ebay",
            "price": 100.0,
            "shipping_cost": 5.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["marketplace_id"] == "ebay"
        assert data["price"] == 100.0
        assert data["base_fee"] == 10.0
        assert data["payment_processing_fee"] == 2.9
        assert data["fixed_fee"] == 0.30
        assert data["total_fees"] == pytest.approx(13.2, abs=0.01)
        assert data["estimated_net"] == pytest.approx(100.0 - 13.2 - 5.0, abs=0.01)

    def test_calculate_fees_invalid_marketplace(self):
        """Invalid marketplace_id returns 400."""
        resp = client.post("/marketplace/listings/fees/calculate", json={
            "marketplace_id": "amazon",
            "price": 100.0,
        })
        assert resp.status_code == 400

    @patch("app.features.marketplace_listing_router.get_db_pool")
    def test_calculate_fees_no_schedule_found(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=None)

        resp = client.post("/marketplace/listings/fees/calculate", json={
            "marketplace_id": "ebay",
            "price": 100.0,
        })
        assert resp.status_code == 404

    def test_calculate_fees_zero_price(self):
        """Price must be > 0."""
        resp = client.post("/marketplace/listings/fees/calculate", json={
            "marketplace_id": "ebay",
            "price": 0,
        })
        assert resp.status_code == 422
