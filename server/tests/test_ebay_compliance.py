"""eBay API compliance (2026-10-05): daily quota, eBay-issued affiliate URLs,
and the marketplace-account-deletion endpoint."""

import asyncio
import hashlib
import os
import sys
from pathlib import Path

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app.lib import ebay_quota  # noqa: E402


# ── quota ───────────────────────────────────────────────────────────────────

def _reset_quota():
    ebay_quota._state.update(remaining=None, fetched_at=0.0, since_fetch=0,
                             window_start=0.0, window_calls=0, blocked_logged_at=0.0)


def _run(coro):
    return asyncio.run(coro)


def test_quota_allows_until_the_reserve(monkeypatch):
    _reset_quota()

    async def fake_fetch(client, token):
        return ebay_quota._RESERVE + 3      # 3 calls left above the reserve
    monkeypatch.setattr(ebay_quota, "fetch_remaining", fake_fetch)

    allowed = 0
    for _ in range(10):
        if _run(ebay_quota.allow_call(None, "t")):
            ebay_quota.record_call()
            allowed += 1
    assert allowed == 3


def test_quota_blind_is_bounded_not_open(monkeypatch):
    _reset_quota()

    async def blind(client, token):
        return None
    monkeypatch.setattr(ebay_quota, "fetch_remaining", blind)

    allowed = 0
    for _ in range(ebay_quota._BLIND_WINDOW_CAP + 25):
        if _run(ebay_quota.allow_call(None, "t")):
            ebay_quota.record_call()
            allowed += 1
    assert allowed == ebay_quota._BLIND_WINDOW_CAP
    # 96 fifteen-minute windows a day must stay under eBay's 5,000.
    assert (86400 // ebay_quota._REFRESH_S) * ebay_quota._BLIND_WINDOW_CAP < 5000


def test_quota_reads_ebays_own_count(monkeypatch):
    """The meter must parse eBay's rate_limit shape (captured 2026-10-05)."""
    payload = {"rateLimits": [{"apiContext": "buy", "apiName": "Browse", "resources": [
        {"name": "buy.browse", "rates": [{"count": 880, "limit": 5000, "remaining": 4120}]},
        {"name": "buy.browse.item.bulk", "rates": [{"remaining": 5000}]}]}]}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    class Client:
        async def get(self, *a, **k):
            return Resp()

    assert _run(ebay_quota.fetch_remaining(Client(), "t")) == 4120


# ── affiliate: eBay-issued URLs keep eBay's params ──────────────────────────

def test_ebay_issued_link_keeps_ebays_params(monkeypatch):
    from app.lib import affiliate
    monkeypatch.setattr(affiliate, "EBAY_AFFILIATE_CAMPAIGN_ID", "5339218687", raising=False)
    issued = ("https://www.ebay.com/itm/398448741287?mkevt=1&mkcid=1&mkrid=711-53200-19255-0"
              "&campid=5339218687&customid=sparrow&toolid=10049")
    tagged = affiliate._tag_epn(issued, "5339218687", "deal-42")
    assert "toolid=10049" in tagged          # eBay's own tool id survives
    assert "toolid=10001" not in tagged
    assert "customid=deal-42" in tagged      # our per-click sub-id is set


def test_plain_ebay_link_is_still_tagged():
    from app.lib import affiliate
    tagged = affiliate._tag_epn("https://www.ebay.com/itm/123", "5339218687", "sparrow")
    assert "campid=5339218687" in tagged and "toolid=10001" in tagged


def test_browse_normaliser_keeps_the_affiliate_url():
    from app.agents.adapters.ebay_caller import _normalize_browse_item
    item = {"itemId": "v1|1|0", "title": "x", "price": {"value": "1.00", "currency": "EUR"},
            "itemWebUrl": "https://www.ebay.com/itm/1",
            "itemAffiliateWebUrl": "https://www.ebay.com/itm/1?campid=5339218687&toolid=10049"}
    hit = _normalize_browse_item(item, {"EUR": 1.0})
    assert hit["url"] == "https://www.ebay.com/itm/1"          # clean, for dedup
    assert hit["affiliate_url"].endswith("toolid=10049")


# ── account-deletion endpoint ───────────────────────────────────────────────

ENDPOINT = "https://api.sparrowcollect.com/ebay/marketplace-account-deletion"
TOKEN = "t" * 40


@pytest.fixture
def client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routes import ebay_notifications_router as r
    monkeypatch.setattr(r, "EBAY_NOTIFICATION_ENDPOINT", ENDPOINT)
    monkeypatch.setattr(r, "EBAY_NOTIFICATION_VERIFICATION_TOKEN", TOKEN)
    app = FastAPI()
    app.include_router(r.router)
    return TestClient(app), r


def test_challenge_hash_is_ebays_order(client):
    c, _ = client
    resp = c.get("/ebay/marketplace-account-deletion", params={"challenge_code": "abc123"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    expected = hashlib.sha256(("abc123" + TOKEN + ENDPOINT).encode()).hexdigest()
    assert resp.json() == {"challengeResponse": expected}
    # Order is part of the spec: any other order must give a different hash.
    assert expected != hashlib.sha256((TOKEN + "abc123" + ENDPOINT).encode()).hexdigest()


def test_unconfigured_challenge_says_so(client, monkeypatch):
    c, r = client
    monkeypatch.setattr(r, "EBAY_NOTIFICATION_VERIFICATION_TOKEN", "")
    resp = c.get("/ebay/marketplace-account-deletion", params={"challenge_code": "x"})
    assert resp.status_code == 503


def test_notification_is_acknowledged(client):
    c, _ = client
    body = {"metadata": {"topic": "MARKETPLACE_ACCOUNT_DELETION"},
            "notification": {"notificationId": "n-1", "data": {"username": "u", "userId": "i"}}}
    assert c.post("/ebay/marketplace-account-deletion", json=body).status_code == 204
    assert c.post("/ebay/marketplace-account-deletion", content=b"not json").status_code == 204
