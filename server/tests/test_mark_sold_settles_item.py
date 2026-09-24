"""Marking a listing sold takes the item out of the seller's collection.

2026-09-24: "Mark as sold" set status='sold' and nothing else — sold_at stayed
NULL and the card stayed in the collection, still counted in portfolio value.
The offer-completion path already retired it (2026-08-09); both now share
retire_sold_item.
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.features import p2p_listing_router as lr  # noqa: E402

USER = "00000000-0000-0000-0000-0000000000a1"
LISTING = "00000000-0000-0000-0000-0000000000f1"
ITEM = "00000000-0000-0000-0000-0000000000c1"


class _Conn:
    def __init__(self):
        self.sql = []

    def transaction(self):
        @asynccontextmanager
        async def tx():
            yield
        return tx()

    async def fetchrow(self, q, *a):
        self.sql.append(q)
        return {"id": LISTING, "item_id": ITEM, "currency": "EUR"}

    async def fetchval(self, q, *a):
        self.sql.append(q)
        return 1

    async def execute(self, q, *a):
        self.sql.append(q)


class _Pool:
    def __init__(self, c):
        self.c = c

    def acquire(self):
        c = self.c

        @asynccontextmanager
        async def a():
            yield c
        return a()


async def _run(monkeypatch, status, sale_price=None, accrued=None):
    conn = _Conn()
    from app.features import p2p_offers_router as orr

    async def _accrue(uid, amount, currency):
        if accrued is not None:
            accrued.append((amount, currency))

    monkeypatch.setattr(orr, "_dac7_accrue", _accrue)
    monkeypatch.setattr(lr, "get_db_pool", lambda: _Pool(conn))

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(lr, "_stale_supply_hook", _noop)
    await lr.delist(LISTING, status=status, sale_price=sale_price, user_id=USER, _rl=None)
    return " ".join(conn.sql)


@pytest.mark.asyncio
async def test_sold_archives_the_item_and_stamps_sold_at(monkeypatch):
    sql = await _run(monkeypatch, "sold")
    assert "sold_at" in sql
    assert "archived = TRUE" in sql


@pytest.mark.asyncio
async def test_delisted_keeps_the_item(monkeypatch):
    sql = await _run(monkeypatch, "delisted")
    assert "archived = TRUE" not in sql


@pytest.mark.asyncio
async def test_sale_price_records_the_sale_and_counts_for_dac7(monkeypatch):
    """Off-platform sales were recorded nowhere: no realised P/L, no DAC7."""
    accrued = []
    sql = await _run(monkeypatch, "sold", sale_price=19.5, accrued=accrued)
    assert "INSERT INTO public.marketplace_sales" in sql
    assert accrued == [(19.5, "EUR")]


@pytest.mark.asyncio
async def test_no_price_records_no_sale(monkeypatch):
    accrued = []
    sql = await _run(monkeypatch, "sold", accrued=accrued)
    assert "marketplace_sales" not in sql and accrued == []
