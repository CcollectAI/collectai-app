"""Tests for app/features/marketplace_trust_router.py — marketplace trust endpoints.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
The trust router returns stub/fallback data when no DB pool is available.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")

from starlette.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app)

VALID_USER_ID = "00000000-0000-0000-0000-000000000099"
VALID_LISTING_ID = "listing-test-001"


# ---------------------------------------------------------------------------
# GET /marketplace/trust2/seller/{user_id} — seller reputation
# ---------------------------------------------------------------------------

class TestSellerReputation:
    def test_seller_reputation_returns_200(self):
        """Returns 200 with stub reputation when no DB pool."""
        resp = client.get(f"/marketplace/trust2/seller/{VALID_USER_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        assert "score" in data
        assert "badge" in data
        assert "total_trades" in data
        assert "disputes" in data
        assert "dispute_rate" in data

    def test_seller_reputation_offline_defaults(self):
        """Offline mode returns empty stub (score=0, badge='new')."""
        resp = client.get(f"/marketplace/trust2/seller/{VALID_USER_ID}")
        data = resp.json()
        assert data["user_id"] == VALID_USER_ID
        assert data["score"] == 0.0
        assert data["badge"] == "new"
        assert data["total_trades"] == 0
        assert data["disputes"] == 0
        assert data["dispute_rate"] == 0.0

    def test_seller_reputation_invalid_user_id(self):
        """Rejects non-UUID user_id with 400."""
        resp = client.get("/marketplace/trust2/seller/some-arbitrary-id")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /marketplace/trust2/listing/{listing_id} — listing trust snapshot
# ---------------------------------------------------------------------------

class TestListingTrustSnapshot:
    def test_listing_trust_returns_200(self):
        """Returns 200 with stub trust snapshot when no DB pool."""
        resp = client.get(f"/marketplace/trust2/listing/{VALID_LISTING_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "seller" in data
        assert "listing_flags" in data

    def test_listing_trust_offline_defaults(self):
        """Offline mode returns empty seller stub and no flags."""
        resp = client.get(f"/marketplace/trust2/listing/{VALID_LISTING_ID}")
        data = resp.json()
        assert data["seller"]["user_id"] == "unknown"
        assert data["seller"]["score"] == 0.0
        assert data["seller"]["badge"] == "new"
        assert data["listing_flags"] == []

    def test_listing_trust_arbitrary_listing_id(self):
        """Accepts any string as listing_id."""
        resp = client.get("/marketplace/trust2/listing/any-listing-id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["listing_flags"] == []
