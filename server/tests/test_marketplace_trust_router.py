"""Tests for deal desk reputation & risk-flag endpoints (merged from marketplace_trust_router).

The marketplace_trust_router was merged into deal_desk_router. These tests
cover the enriched /deals/reputation/{user_id} endpoint and the new
/deals/{offer_id}/risk-flags endpoint.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from app.rate_limit import _user_hits  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

VALID_USER_ID = "00000000-0000-0000-0000-000000000099"
VALID_OFFER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    _user_hits.clear()
    yield
    _user_hits.clear()


# ---------------------------------------------------------------------------
# Verify old marketplace_trust_router endpoints are removed
# ---------------------------------------------------------------------------

class TestOldEndpointsRemoved:
    def test_old_trust2_seller_endpoint_gone(self):
        """The old /marketplace/trust2/seller/{user_id} endpoint no longer exists."""
        resp = client.get(f"/marketplace/trust2/seller/{VALID_USER_ID}")
        assert resp.status_code in (404, 405)

    def test_old_trust2_listing_endpoint_gone(self):
        """The old /marketplace/trust2/listing/{id} endpoint no longer exists."""
        resp = client.get("/marketplace/trust2/listing/listing-test-001")
        assert resp.status_code in (404, 405)


# ---------------------------------------------------------------------------
# GET /deals/reputation/{user_id} — enriched reputation
# ---------------------------------------------------------------------------

class TestDealReputation:
    def test_reputation_returns_503_without_db(self):
        """Without DB pool, reputation returns 503."""
        resp = client.get(f"/deals/reputation/{VALID_USER_ID}")
        assert resp.status_code == 503

    def test_reputation_invalid_uuid_returns_error(self):
        """Non-UUID user_id returns 400 (or 503 if DB check runs first)."""
        resp = client.get("/deals/reputation/not-a-uuid")
        assert resp.status_code in (400, 503)


# ---------------------------------------------------------------------------
# GET /deals/{offer_id}/risk-flags — offer risk assessment
# ---------------------------------------------------------------------------

class TestOfferRiskFlags:
    def test_risk_flags_returns_503_without_db(self):
        """Without DB pool, risk-flags returns 503."""
        resp = client.get(f"/deals/{VALID_OFFER_ID}/risk-flags")
        assert resp.status_code == 503

    def test_risk_flags_invalid_uuid_returns_error(self):
        """Non-UUID offer_id returns 400 (or 503 if DB check runs first)."""
        resp = client.get("/deals/not-a-uuid/risk-flags")
        assert resp.status_code in (400, 503)
