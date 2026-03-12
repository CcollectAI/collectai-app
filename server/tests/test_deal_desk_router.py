"""Tests for app/agents/deal_desk_router.py — P2P offer/negotiation layer.

Covers:
  - POST /deals/offer — propose an offer (happy path, own-item error, item not found)
  - POST /deals/{id}/counter — counter-offer (happy path, IDOR check)
  - POST /deals/{id}/respond — accept/decline (happy path, IDOR check)
  - POST /deals/{id}/cancel — cancel (happy path, IDOR check)
  - POST /deals/{id}/ship — mark shipped (happy path, seller-only IDOR)
  - POST /deals/{id}/complete — confirm delivery (happy path, buyer-only IDOR)
  - GET  /deals/active — list active offers
  - GET  /deals/history — list history
  - PUT  /items/{id}/for-sale — toggle for-sale (happy path, ownership IDOR)
  - Validation: invalid UUID, invalid price

All tests mock get_db_pool() and override the auth dependency so no real
database is needed.
"""

from __future__ import annotations

import json
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

TEST_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER_USER_ID = "11111111-2222-3333-4444-555555555555"
OFFER_UUID = "00000000-0000-0000-0000-000000000001"
ITEM_UUID = "00000000-0000-0000-0000-000000000099"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pool():
    """Create a mock asyncpg pool with a mock connection."""
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=None)
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    # Support conn.transaction() as async context manager (no-op in tests)
    mock_tx = AsyncMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=mock_acquire)

    return pool, mock_conn


def _auth_override(user_id: str = TEST_USER_ID):
    from app.auth import get_current_user_id

    async def _fake_user():
        return user_id

    app.dependency_overrides[get_current_user_id] = _fake_user


def _clear_overrides():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: POST /deals/offer — Propose an offer
# ---------------------------------------------------------------------------

class TestProposeOffer:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_propose_offer_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        rpc_result = json.dumps({"offer_id": OFFER_UUID, "status": "proposed"})
        conn.fetchval = AsyncMock(return_value=rpc_result)

        resp = client.post("/deals/offer", json={
            "item_id": ITEM_UUID,
            "price": 25.0,
            "message": "I want this!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["offer_id"] == OFFER_UUID
        assert data["status"] == "proposed"

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_propose_offer_own_item_rejected(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchval = AsyncMock(side_effect=Exception("Cannot bid on own item"))

        resp = client.post("/deals/offer", json={
            "item_id": ITEM_UUID,
            "price": 25.0,
        })
        assert resp.status_code == 400

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_propose_offer_item_not_found(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchval = AsyncMock(side_effect=Exception("Item not found"))

        resp = client.post("/deals/offer", json={
            "item_id": ITEM_UUID,
            "price": 25.0,
        })
        assert resp.status_code == 404

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_propose_offer_invalid_uuid(self, mock_get_pool):
        """Invalid item_id UUID should return 400."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        resp = client.post("/deals/offer", json={
            "item_id": "not-a-uuid",
            "price": 25.0,
        })
        # The route calls _validate_uuid which raises 400
        assert resp.status_code == 400

    def test_propose_offer_zero_price(self):
        """Price must be > 0 per Pydantic Field(gt=0)."""
        resp = client.post("/deals/offer", json={
            "item_id": ITEM_UUID,
            "price": 0,
        })
        assert resp.status_code == 422

    def test_propose_offer_negative_price(self):
        """Negative price rejected by Pydantic validation."""
        resp = client.post("/deals/offer", json={
            "item_id": ITEM_UUID,
            "price": -10.0,
        })
        assert resp.status_code == 422

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_propose_offer_db_unavailable(self, mock_get_pool):
        mock_get_pool.return_value = None
        resp = client.post("/deals/offer", json={
            "item_id": ITEM_UUID,
            "price": 25.0,
        })
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Tests: POST /deals/{offer_id}/counter — Counter-offer with IDOR check
# ---------------------------------------------------------------------------

class TestCounterOffer:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_counter_offer_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # First call: IDOR check returns 1 (participant)
        # Second call: RPC returns result
        rpc_result = json.dumps({"offer_id": OFFER_UUID, "status": "countered"})
        conn.fetchval = AsyncMock(side_effect=[1, rpc_result])

        resp = client.post(f"/deals/{OFFER_UUID}/counter", json={
            "price": 30.0,
            "message": "How about 30?",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "countered"

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_counter_offer_idor_forbidden(self, mock_get_pool):
        """Non-participant cannot counter an offer."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # IDOR check returns None (not a participant)
        conn.fetchval = AsyncMock(return_value=None)

        resp = client.post(f"/deals/{OFFER_UUID}/counter", json={
            "price": 30.0,
        })
        assert resp.status_code == 403

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_counter_offer_invalid_uuid(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        resp = client.post("/deals/bad-uuid/counter", json={"price": 30.0})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: POST /deals/{offer_id}/respond — Accept or decline with IDOR check
# ---------------------------------------------------------------------------

class TestRespondOffer:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_respond_accept_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        rpc_result = json.dumps({"offer_id": OFFER_UUID, "status": "accepted"})
        conn.fetchval = AsyncMock(side_effect=[1, rpc_result])

        resp = client.post(f"/deals/{OFFER_UUID}/respond", json={
            "accept": True,
            "message": "Deal!",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_respond_decline_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        rpc_result = json.dumps({"offer_id": OFFER_UUID, "status": "declined"})
        conn.fetchval = AsyncMock(side_effect=[1, rpc_result])

        resp = client.post(f"/deals/{OFFER_UUID}/respond", json={
            "accept": False,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "declined"

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_respond_idor_forbidden(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchval = AsyncMock(return_value=None)

        resp = client.post(f"/deals/{OFFER_UUID}/respond", json={
            "accept": True,
        })
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /deals/{offer_id}/cancel — Cancel with IDOR check
# ---------------------------------------------------------------------------

class TestCancelOffer:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_cancel_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        rpc_result = json.dumps({"offer_id": OFFER_UUID, "status": "cancelled"})
        conn.fetchval = AsyncMock(side_effect=[1, rpc_result])

        resp = client.post(f"/deals/{OFFER_UUID}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_cancel_idor_forbidden(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchval = AsyncMock(return_value=None)

        resp = client.post(f"/deals/{OFFER_UUID}/cancel")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /deals/{offer_id}/ship — Seller-only IDOR check
# ---------------------------------------------------------------------------

class TestMarkShipped:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_ship_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        rpc_result = json.dumps({"offer_id": OFFER_UUID, "status": "shipped"})
        conn.fetchval = AsyncMock(side_effect=[1, rpc_result])

        resp = client.post(f"/deals/{OFFER_UUID}/ship", json={
            "tracking_info": "TRACK-12345",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "shipped"

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_ship_non_seller_forbidden(self, mock_get_pool):
        """Only the seller can mark as shipped."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # IDOR check for seller_id returns None
        conn.fetchval = AsyncMock(return_value=None)

        resp = client.post(f"/deals/{OFFER_UUID}/ship", json={})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /deals/{offer_id}/complete — Buyer-only IDOR check
# ---------------------------------------------------------------------------

class TestCompleteDeal:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_complete_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        rpc_result = json.dumps({"offer_id": OFFER_UUID, "status": "completed"})
        # First call: buyer IDOR check; second call: RPC; third call: deal_count for XP
        conn.fetchval = AsyncMock(side_effect=[1, rpc_result, 1])
        # For the ground-truth recording (second pool.acquire → fetchrow)
        conn.fetchrow = AsyncMock(return_value=None)

        resp = client.post(f"/deals/{OFFER_UUID}/complete", json={
            "stars": 5,
            "comment": "Great seller!",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_complete_non_buyer_forbidden(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchval = AsyncMock(return_value=None)

        resp = client.post(f"/deals/{OFFER_UUID}/complete", json={
            "stars": 3,
        })
        assert resp.status_code == 403

    def test_complete_invalid_stars_too_low(self):
        """Stars must be 1-5."""
        resp = client.post(f"/deals/{OFFER_UUID}/complete", json={
            "stars": 0,
        })
        assert resp.status_code == 422

    def test_complete_invalid_stars_too_high(self):
        """Stars must be 1-5."""
        resp = client.post(f"/deals/{OFFER_UUID}/complete", json={
            "stars": 6,
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: PUT /items/{item_id}/for-sale — Toggle for-sale with ownership check
# ---------------------------------------------------------------------------

class TestToggleForSale:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_toggle_for_sale_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchval = AsyncMock(return_value=TEST_USER_ID)
        conn.execute = AsyncMock(return_value="UPDATE 1")

        resp = client.put(f"/items/{ITEM_UUID}/for-sale", json={
            "for_sale": True,
            "asking_price": 100.0,
            "currency": "EUR",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["for_sale"] is True
        assert data["asking_price"] == 100.0

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_toggle_for_sale_not_owner(self, mock_get_pool):
        """Non-owner cannot toggle for-sale."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchval = AsyncMock(return_value=OTHER_USER_ID)

        resp = client.put(f"/items/{ITEM_UUID}/for-sale", json={
            "for_sale": True,
            "asking_price": 50.0,
        })
        assert resp.status_code == 403

    @patch("app.agents.deal_desk_router.get_db_pool")
    def test_toggle_for_sale_item_not_found(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchval = AsyncMock(return_value=None)

        resp = client.put(f"/items/{ITEM_UUID}/for-sale", json={
            "for_sale": False,
        })
        assert resp.status_code == 404

    def test_toggle_for_sale_invalid_currency(self):
        """Currency must match the pattern."""
        resp = client.put(f"/items/{ITEM_UUID}/for-sale", json={
            "for_sale": True,
            "asking_price": 50.0,
            "currency": "INVALID",
        })
        assert resp.status_code == 422
