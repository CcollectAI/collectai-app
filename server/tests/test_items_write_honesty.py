"""`{"ok": true}` must mean a row was written.

2026-09-17, sweeping the server for "success without a write". Two member-facing
writes in `items_router` claimed a save that had not happened:

  * `if pool is None: return {"ok": True, "item_id": item_id}` — no database, no
    write, and the app closes edit mode on `ok`. 68 other handlers raise 503.
  * the attributes UPDATE discarded asyncpg's status string, so an item id that
    is not the caller's matched no row and still answered `ok`. (The purchase
    handler next door already used RETURNING + a `row is None` check; this is
    the same contract, spelled with the row count.)

These tests drive the handlers with a fake pool, so they fail if either
behaviour comes back — a source grep would not have caught the first fix's own
bug, that the new 404 was raised INSIDE a `try/except Exception` and came back
out as 500 DB_ERROR.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.routes import items_router as ir  # noqa: E402

ITEM = "11111111-1111-1111-1111-111111111111"
USER = "22222222-2222-2222-2222-222222222222"


class _Conn:
    def __init__(self, status="UPDATE 1", row=None):
        self._status, self._row = status, row
        self.calls = 0

    async def execute(self, *args, **kwargs):
        self.calls += 1
        return self._status

    async def fetchrow(self, *args, **kwargs):
        self.calls += 1
        return self._row


class _Acquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


def _patch_pool(monkeypatch, pool):
    monkeypatch.setattr(ir, "get_db_pool", lambda: pool)


def _attrs_payload():
    return ir.UpdateItemAttributesRequest(attributes={"set_code": "SV1"})


class TestAttributes:
    @pytest.mark.asyncio
    async def test_no_pool_is_503_not_ok(self, monkeypatch):
        _patch_pool(monkeypatch, None)
        with pytest.raises(HTTPException) as e:
            await ir.update_item_attributes(ITEM, _attrs_payload(), user_id=USER)
        assert e.value.status_code == 503
        assert e.value.detail["code"] == "DB_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_zero_rows_is_404_not_ok(self, monkeypatch):
        conn = _Conn(status="UPDATE 0")
        _patch_pool(monkeypatch, _Pool(conn))
        with pytest.raises(HTTPException) as e:
            await ir.update_item_attributes(ITEM, _attrs_payload(), user_id=USER)
        # NOT 500: the 404 is raised inside the handler's own try block, and
        # `except Exception` used to swallow it into DB_ERROR.
        assert e.value.status_code == 404, e.value.detail
        assert e.value.detail["code"] == "NOT_FOUND"
        assert conn.calls == 1

    @pytest.mark.asyncio
    async def test_one_row_is_ok(self, monkeypatch):
        _patch_pool(monkeypatch, _Pool(_Conn(status="UPDATE 1")))
        out = await ir.update_item_attributes(ITEM, _attrs_payload(), user_id=USER)
        assert out == {"ok": True, "item_id": ITEM}

    @pytest.mark.asyncio
    async def test_empty_patch_writes_nothing_and_says_ok(self, monkeypatch):
        # Honest: there is nothing to write, so nothing is claimed. The UPDATE
        # must not run at all.
        conn = _Conn(status="UPDATE 0")
        _patch_pool(monkeypatch, _Pool(conn))
        out = await ir.update_item_attributes(
            ITEM, ir.UpdateItemAttributesRequest(attributes={}), user_id=USER
        )
        assert out == {"ok": True, "item_id": ITEM}
        assert conn.calls == 0

    @pytest.mark.asyncio
    async def test_a_real_db_error_is_still_500(self, monkeypatch):
        class _Boom(_Conn):
            async def execute(self, *a, **k):
                raise RuntimeError("connection reset")

        _patch_pool(monkeypatch, _Pool(_Boom()))
        with pytest.raises(HTTPException) as e:
            await ir.update_item_attributes(ITEM, _attrs_payload(), user_id=USER)
        assert e.value.status_code == 500
        assert e.value.detail["code"] == "DB_ERROR"


class TestPurchase:
    @pytest.mark.asyncio
    async def test_no_pool_is_503_not_ok(self, monkeypatch):
        _patch_pool(monkeypatch, None)
        with pytest.raises(HTTPException) as e:
            await ir.update_item_purchase(
                ITEM, ir.UpdateItemPurchaseRequest(purchase_price=12.5, purchase_currency="EUR"), user_id=USER
            )
        assert e.value.status_code == 503
        assert e.value.detail["code"] == "DB_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_no_row_is_404(self, monkeypatch):
        _patch_pool(monkeypatch, _Pool(_Conn(row=None)))
        monkeypatch.setattr(ir, "convert_to_eur", _eur)
        with pytest.raises(HTTPException) as e:
            await ir.update_item_purchase(
                ITEM, ir.UpdateItemPurchaseRequest(purchase_price=12.5, purchase_currency="EUR"), user_id=USER
            )
        assert e.value.status_code == 404
        assert e.value.detail["code"] == "NOT_FOUND"


async def _eur(amount, currency):  # noqa: E302
    return amount
