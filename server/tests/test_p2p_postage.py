"""Postage is part of the deal (2026-10-16, Vinted's model).

Walked as a buyer: EUR 20 + EUR 2,50 postage listing; the agreed offer, the
buyer's new item and the seller's sale all carried the ITEM amount only.
"""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.features import p2p_offers_router as r  # noqa: E402


class RecordingConn:
    def __init__(self, listing):
        self.listing = listing
        self.executed: list[tuple[str, tuple]] = []

    async def fetchrow(self, sql, *args):
        return self.listing

    async def fetchval(self, sql, *args):
        return None  # the buyer has no item from this trade yet

    async def fetch(self, sql, *args):
        self.executed.append((" ".join(sql.split()), args))
        return []

    async def execute(self, sql, *args):
        self.executed.append((" ".join(sql.split()), args))


LISTING = {
    "item_id": None, "canonical_key": None, "category": "pokemon",
    "condition_label": "Near Mint", "listing_description": None,
    "listing_title": "Pikachu", "photo_catalogue_consent": False,
    "image_url": None, "quantity": 1,
}


def _insert_args(conn):
    return next(a for s, a in conn.executed if s.startswith("INSERT INTO public.items"))


@pytest.mark.asyncio
async def test_buyer_cost_basis_is_item_plus_postage():
    conn = RecordingConn(LISTING)
    with patch("app.lib.fx_service.convert_to_eur", AsyncMock(side_effect=lambda v, c: v)):
        await r._settle_completed_trade(conn, "o1", "l1", "buyer", "seller", 19.0, "EUR", 2.5)
    args = _insert_args(conn)
    assert 21.5 in args  # purchase_price = what the buyer paid
    assert 19.0 not in args


@pytest.mark.asyncio
async def test_no_stated_postage_leaves_the_item_amount():
    conn = RecordingConn(LISTING)
    with patch("app.lib.fx_service.convert_to_eur", AsyncMock(side_effect=lambda v, c: v)):
        await r._settle_completed_trade(conn, "o1", "l1", "buyer", "seller", 19.0, "EUR", None)
    assert 19.0 in _insert_args(conn)


@pytest.mark.asyncio
async def test_sale_records_the_postage_the_buyer_paid():
    conn = RecordingConn(None)
    await r._record_p2p_sale(conn, "l1", "seller", 22.5, "EUR", 2.5)
    sql, args = conn.executed[0]
    assert "shipping_charged" in sql
    assert "round($3::numeric + COALESCE($5::numeric, 0), 2)" in sql  # net = item + postage
    assert args[-1] == 2.5


def test_offer_out_carries_postage_and_tolerates_its_absence():
    base = {
        "id": "o1", "listing_id": "l1", "buyer_id": "b", "seller_id": "s", "amount": 19,
        "currency": "EUR", "status": "pending", "message": None, "counter_count": 0,
        "created_at": "2026-10-16T00:00:00Z", "seller_confirmed_at": None,
        "buyer_confirmed_at": None, "tracking_carrier": None, "tracking_code": None,
        "tracking_set_at": None,
    }
    assert r._row_to_offer({**base, "shipping_cost": 2.5}, "b").shipping_cost == 2.5
    assert r._row_to_offer(base, "b").shipping_cost is None


def test_create_offer_snapshots_the_listing_postage():
    src = Path(r.__file__).read_text()
    assert "status, delisted_at, shipping_cost" in src
    assert 'listing["shipping_cost"],' in src
    assert "RETURNING id, listing_id, buyer_id, seller_id, amount, currency, shipping_cost," in src


def test_postage_record_adds_back_what_the_buyer_paid():
    src = Path(r.__file__).read_text()
    assert "+ COALESCE(shipping_charged, 0)" in src


def test_prefilled_payment_link_carries_item_plus_postage(monkeypatch):
    """'Total to pay EUR 21,50' must not open PayPal prefilled with 19."""
    import asyncio as _a

    class Pool:
        async def fetchrow(self, sql, *a):
            if "p2p_offers" in sql:
                return {"seller_id": "s", "buyer_id": "b", "amount": 19, "currency": "EUR",
                        "status": "accepted", "shipping_cost": 2.5}
            return None  # no stored region

        async def fetch(self, sql, *a):
            return [{"rail_key": "paypal", "handle": "sellerhandle"}]

    monkeypatch.setattr(r, "get_db_pool", lambda: Pool())
    out = _a.run(r.list_payment_rails(region="europe", offer_id="o1", user_id="b"))
    paypal = next(x for x in out.rails if x.key == "paypal")
    assert paypal.pay_url and "21.5" in paypal.pay_url
    assert "/19" not in paypal.pay_url
