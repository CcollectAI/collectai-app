"""Tests for app/agents/purchase_router.py — Smart Deal Agent REST endpoints.

All tests mock DB access via get_conn and db_configured.
DB_ENABLED=false and DEV_MODE=true so auth is bypassed.
"""

import os
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mandate_row(**overrides):
    now = datetime.now(timezone.utc)
    row = {
        "id": uuid.uuid4(),
        "user_id": uuid.UUID("00000000-0000-0000-0000-000000000000"),
        "name": "Test Mandate",
        "status": "active",
        "search_query": "Charizard PSA 10",
        "category": "pokemon",
        "condition_filter": [],
        "min_trust_score": 0.60,
        "max_price": 400.0,
        "max_total_budget": None,
        "spent_total": 0.0,
        "cooldown_hours": 24,
        "allowed_sources": [],
        "region": None,
        "expires_at": None,
        "last_scan_at": None,
        "last_deal_at": None,
        "deals_found": 0,
        "deals_purchased": 0,
        "created_at": now,
        "updated_at": now,
    }
    row.update(overrides)
    return row


def _deal_row(**overrides):
    now = datetime.now(timezone.utc)
    row = {
        "id": uuid.uuid4(),
        "mandate_id": uuid.uuid4(),
        "user_id": uuid.UUID("00000000-0000-0000-0000-000000000000"),
        "status": "discovered",
        "listing_source": "ebay",
        "listing_url": "https://www.ebay.com/itm/123",
        "affiliate_url": "https://www.ebay.com/itm/123?campid=X",
        "listing_title": "Charizard PSA 10",
        "listing_price": 350.0,
        "listing_currency": "EUR",
        "listing_condition": "Near Mint",
        "listing_image_url": None,
        "listing_seller": "seller123",
        "listing_ended": False,
        "provenance_score": 0.85,
        "deal_score": 0.72,
        "price_vs_q50_pct": -12.5,
        "predicted_q50": 400.0,
        "predicted_q10": 300.0,
        "predicted_q90": 500.0,
        "policy_passed": True,
        "policy_reasons": json.dumps(["price OK", "trust OK"]),
        "affiliate_source": "ebay_partner_network",
        "affiliate_click": False,
        "estimated_commission": None,
        "confirmed_price": None,
        "added_item_id": None,
        "discovered_at": now,
        "notified_at": None,
        "clicked_at": None,
        "purchased_at": None,
        "created_at": now,
    }
    row.update(overrides)
    return row


@asynccontextmanager
async def _mock_conn_ctx(conn):
    yield conn


def _patch_db(conn):
    """Return a list of two context-manager patches: db_configured + get_conn."""
    return [
        patch("app.agents.purchase_router.db_configured", return_value=True),
        patch("app.agents.purchase_router.get_conn", return_value=_mock_conn_ctx(conn)),
    ]


# ---------------------------------------------------------------------------
# Mandate CRUD Tests
# ---------------------------------------------------------------------------


class TestCreateMandate:
    def test_create_success(self):
        row = _mandate_row()
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=0)  # count check (under limit)
        conn.fetchrow = AsyncMock(return_value=row)

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post("/purchase/mandates", json={
                "name": "Test Mandate",
                "search_query": "Charizard PSA 10",
                "max_price": 400,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Mandate"
        assert data["status"] == "active"
        # MandateResponse no longer exposes user_id
        assert "user_id" not in data

    def test_create_limit_reached(self):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=5)  # at limit

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post("/purchase/mandates", json={
                "name": "Test",
                "search_query": "Test",
                "max_price": 100,
            })

        assert resp.status_code == 409
        assert "limit" in resp.json()["detail"].lower()

    def test_create_validation_missing_name(self):
        conn = AsyncMock()

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post("/purchase/mandates", json={
                "search_query": "Test",
                "max_price": 100,
            })

        # Pydantic validation rejects the request
        assert resp.status_code == 422


class TestListMandates:
    def test_list_returns_mandates(self):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[_mandate_row()])

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.get("/purchase/mandates")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["mandates"]) == 1
        # No user_id in response
        assert "user_id" not in data["mandates"][0]


class TestGetMandate:
    def test_get_existing(self):
        row = _mandate_row()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=row)

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.get(f"/purchase/mandates/{row['id']}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(row["id"])
        assert "user_id" not in data

    def test_get_not_found(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.get(f"/purchase/mandates/{uuid.uuid4()}")

        assert resp.status_code == 404


class TestUpdateMandate:
    def test_update_success(self):
        row = _mandate_row(name="Updated Mandate")
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=row)

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.patch(f"/purchase/mandates/{row['id']}", json={
                "name": "Updated Mandate",
            })

        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Mandate"
        assert "user_id" not in resp.json()

    def test_update_no_fields(self):
        conn = AsyncMock()

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.patch(f"/purchase/mandates/{uuid.uuid4()}", json={})

        assert resp.status_code == 400
        assert "no fields" in resp.json()["detail"].lower()

    def test_update_whitelist_rejection(self):
        """Non-whitelisted keys in the body are rejected by Pydantic
        (MandateUpdate model ignores extras), so only model-known but
        non-updatable scenarios are relevant. Since MandateUpdate only
        defines whitelisted fields, any truly foreign key is stripped
        by Pydantic.  We verify that sending a valid field works and
        that the whitelisted-columns check is present by checking the
        route internally. Here we test that extra keys are silently
        ignored by Pydantic (no server crash) and the update proceeds."""
        row = _mandate_row(name="Good")
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=row)

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            # Extra field "hacker_field" is not in MandateUpdate and
            # Pydantic strips it; the valid field "name" goes through.
            resp = client.patch(f"/purchase/mandates/{row['id']}", json={
                "name": "Good",
                "hacker_field": "DROP TABLE",
            })

        # Should succeed because Pydantic strips unknown fields
        assert resp.status_code == 200


class TestDeleteMandate:
    def test_delete_pauses_mandate(self):
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="UPDATE 1")

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.delete(f"/purchase/mandates/{uuid.uuid4()}")

        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_delete_not_found(self):
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value="UPDATE 0")

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.delete(f"/purchase/mandates/{uuid.uuid4()}")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Deal Action Tests
# ---------------------------------------------------------------------------


class TestListDeals:
    def test_list_deals_success(self):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[_deal_row()])

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.get("/purchase/deals")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["deals"]) == 1
        # DealResponse no longer exposes user_id
        assert "user_id" not in data["deals"][0]

    def test_list_deals_with_status_filter(self):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[_deal_row(status="clicked")])

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.get("/purchase/deals?status=clicked")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["deals"][0]["status"] == "clicked"

    def test_list_deals_invalid_status_filter(self):
        conn = AsyncMock()

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.get("/purchase/deals?status=INVALID_STATUS")

        assert resp.status_code == 400
        assert "invalid status" in resp.json()["detail"].lower()


class TestClickDeal:
    def test_click_sets_affiliate(self):
        deal = _deal_row(status="discovered")
        conn = AsyncMock()
        # click_deal does a single UPDATE ... RETURNING id, affiliate_url, listing_url
        # with status gate AND status = ANY($3::text[])
        conn.fetchrow = AsyncMock(return_value={
            "id": deal["id"],
            "affiliate_url": deal["affiliate_url"],
            "listing_url": deal["listing_url"],
        })

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post(f"/purchase/deals/{deal['id']}/click")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["url"] == deal["affiliate_url"]

    def test_click_not_found_or_wrong_status(self):
        conn = AsyncMock()
        # UPDATE with status gate returns None when deal doesn't exist
        # or the deal's status is not in ['discovered', 'notified']
        conn.fetchrow = AsyncMock(return_value=None)

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post(f"/purchase/deals/{uuid.uuid4()}/click")

        assert resp.status_code == 404
        assert "not clickable" in resp.json()["detail"].lower() or "not found" in resp.json()["detail"].lower()


class TestConfirmDeal:
    def test_confirm_purchase(self):
        deal = _deal_row(status="clicked")
        conn = AsyncMock()
        # Query sequence for confirm_deal:
        # 1. fetchrow: SELECT deal with status gate (_CONFIRMABLE_STATUSES)
        # 2. execute:  UPDATE deal SET status='purchased' -> "UPDATE 1"
        # 3. execute:  UPDATE mandate counters (deals_purchased, spent_total)
        # 4. fetchrow: SELECT mandate budget (max_total_budget, spent_total)
        conn.fetchrow = AsyncMock(side_effect=[
            deal,                                                # 1st fetchrow: deal
            {"max_total_budget": None, "spent_total": 350.0},   # 2nd fetchrow: mandate budget
        ])
        conn.execute = AsyncMock(side_effect=[
            "UPDATE 1",  # 1st execute: deal status update
            None,        # 2nd execute: mandate counter update
        ])

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post(f"/purchase/deals/{deal['id']}/confirm", json={
                "confirmed_price": 340,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "purchased"
        assert data["confirmed_price"] == 340

    def test_confirm_not_found_or_wrong_status(self):
        conn = AsyncMock()
        # First fetchrow returns None -> deal not in confirmable state
        conn.fetchrow = AsyncMock(return_value=None)

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post(f"/purchase/deals/{uuid.uuid4()}/confirm", json={
                "confirmed_price": 300,
            })

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower() or "already" in resp.json()["detail"].lower()

    def test_confirm_already_purchased_returns_404(self):
        """A deal with status 'purchased' is not in _CONFIRMABLE_STATUSES,
        so the first SELECT returns None and we get 404."""
        conn = AsyncMock()
        # status='purchased' is not in {'discovered', 'notified', 'clicked'}
        conn.fetchrow = AsyncMock(return_value=None)

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post(f"/purchase/deals/{uuid.uuid4()}/confirm", json={
                "confirmed_price": 300,
            })

        assert resp.status_code == 404

    def test_confirm_budget_exhaustion(self):
        """When confirmed_price pushes spent_total >= max_total_budget,
        the mandate is set to 'exhausted'."""
        deal = _deal_row(status="discovered")
        conn = AsyncMock()
        # After the purchase, spent_total (950) >= max_total_budget (1000)
        # triggers the exhaustion branch
        conn.fetchrow = AsyncMock(side_effect=[
            deal,                                                      # 1st fetchrow: deal
            {"max_total_budget": 1000.0, "spent_total": 1050.0},       # 2nd fetchrow: budget check
        ])
        conn.execute = AsyncMock(side_effect=[
            "UPDATE 1",  # 1st execute: deal status -> purchased
            None,        # 2nd execute: mandate counter update
            None,        # 3rd execute: mandate -> exhausted
        ])

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post(f"/purchase/deals/{deal['id']}/confirm", json={
                "confirmed_price": 350,
            })

        assert resp.status_code == 200
        assert resp.json()["status"] == "purchased"
        # Verify the exhaustion execute was called (3 total execute calls)
        assert conn.execute.call_count == 3
        # The 3rd execute call should contain 'exhausted'
        third_call_sql = conn.execute.call_args_list[2][0][0]
        assert "exhausted" in third_call_sql


class TestDeclineDeal:
    def test_decline_deal_success(self):
        conn = AsyncMock()
        # decline_deal does UPDATE ... AND status = ANY($3::text[]) and returns "UPDATE 1"
        conn.execute = AsyncMock(return_value="UPDATE 1")

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post(f"/purchase/deals/{uuid.uuid4()}/decline")

        assert resp.status_code == 200
        assert resp.json()["status"] == "declined"

    def test_decline_not_found_or_wrong_status(self):
        conn = AsyncMock()
        # UPDATE returns "UPDATE 0" when deal not found or status not declinable
        conn.execute = AsyncMock(return_value="UPDATE 0")

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.post(f"/purchase/deals/{uuid.uuid4()}/decline")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower() or "not declinable" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Stats Tests
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_returns_counts(self):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=2)  # active mandates
        conn.fetchrow = AsyncMock(return_value={
            "total_found": 15,
            "total_clicked": 5,
            "total_purchased": 3,
            "saved_vs_q50": 150.50,
        })

        with _patch_db(conn)[0], _patch_db(conn)[1]:
            resp = client.get("/purchase/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["active_mandates"] == 2
        assert data["total_deals_found"] == 15
        assert data["total_deals_clicked"] == 5
        assert data["total_deals_purchased"] == 3
        assert data["total_saved_vs_q50"] == 150.50
