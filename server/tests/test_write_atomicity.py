"""A read-decide-write is ONE act, and the row is locked while it happens.

Three handlers, one class (`docs/CLASS_SWEEPS.md` class S / K): responding to an
offer, confirming an exchange, and recording a marketplace sale. Each read a
row, decided in Python, and wrote — with no transaction and no row lock.

2026-09-17, class S / class K. `respond_to_offer` read the offer, checked its
status in Python, and then wrote — with no transaction and no row lock:

  * `accept` writes `p2p_offers` and THEN `marketplace_listings`. A failure
    between them left an ACCEPTED offer whose listing was never reserved;
    `withdraw` had the mirror, leaving the listing reserved to a cancelled offer
    — invisible to the seller and unreachable by any other buyer's accept.
  * two responses in flight both read `pending` and both wrote. A `decline`
    racing an `accept` left the listing reserved for a declined offer, and
    `counter_count` could pass `MAX_COUNTERS` because the cap was checked
    against a stale read.

`FOR UPDATE OF o` and not a bare `FOR UPDATE`: the query LEFT JOINs the listing
and the address, and Postgres refuses to lock the nullable side of an outer join
("FOR UPDATE cannot be applied to the nullable side of an outer join" — the
error was reproduced on production before this test was written).

These tests assert ORDER through a recording connection, not source text. The
30 green tests that let the seller-only bug live in this same handler all
inspected source.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.features import p2p_offers_router as p2p  # noqa: E402

OFFER = "00000000-0000-0000-0000-00000000aaaa"
LISTING = "00000000-0000-0000-0000-00000000bbbb"
SELLER = "00000000-0000-0000-0000-00000000cccc"
BUYER = "00000000-0000-0000-0000-00000000dddd"


class _Row(dict):
    pass


def _offer_row(status="pending", counter_count=0):
    return _Row(
        id=OFFER, listing_id=LISTING, seller_id=SELLER, buyer_id=BUYER,
        status=status, counter_count=counter_count, amount=25.0, currency="EUR",
        listing_title="Charizard", delivery_postcode=None, delivery_country=None,
    )


class _Conn:
    """Records the ORDER of everything: statements, and the transaction edges."""

    def __init__(self, row=None, events=None):
        self.row = row if row is not None else _offer_row()
        # Shared with the hook fakes when one is passed in — see
        # `test_the_external_hooks_run_after_the_commit`.
        self.events: list[str] = events if events is not None else []

    # -- transaction ------------------------------------------------------
    def transaction(self):
        conn = self

        class _Tx:
            async def __aenter__(self):
                conn.events.append("BEGIN")
                return None

            async def __aexit__(self, *exc):
                conn.events.append("ROLLBACK" if exc[0] else "COMMIT")
                return False

        return _Tx()

    # -- statements -------------------------------------------------------
    def _log(self, q):
        flat = " ".join(q.split())
        self.events.append(flat)
        return flat

    async def fetchrow(self, q, *a):
        self._log(q)
        return self.row

    async def execute(self, q, *a):
        self._log(q)
        return "UPDATE 1"

    async def fetchval(self, q, *a):
        self._log(q)
        return None

    async def fetch(self, q, *a):
        self._log(q)
        return []


class _Acquire:
    def __init__(self, conn):
        self._c = conn

    async def __aenter__(self):
        return self._c

    async def __aexit__(self, *e):
        return False


class _Pool:
    def __init__(self, conn):
        self._c = conn

    def acquire(self):
        return _Acquire(self._c)


@pytest.fixture
def conn(monkeypatch):
    c = _Conn()
    monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(c))
    # The response mapper and the notification are not what these tests are
    # about, and both need rows/tables a fake connection does not have.
    monkeypatch.setattr(p2p, "_row_to_offer", lambda r, me: {"id": OFFER})

    async def _noop_notify(*a, **k):
        c.events.append("NOTIFY")

    monkeypatch.setattr(p2p, "_notify_trade", _noop_notify)
    return c


async def _respond(action, user_id=SELLER, amount=None):
    return await p2p.respond_to_offer(OFFER, action=action, amount=amount, user_id=user_id)


def _writes(events):
    return [e for e in events if e.startswith("UPDATE")]


class TestAcceptIsAtomic:
    @pytest.mark.asyncio
    async def test_both_writes_are_inside_one_transaction(self, conn):
        await _respond("accept")
        ev = conn.events
        begin, commit = ev.index("BEGIN"), ev.index("COMMIT")
        writes = [i for i, e in enumerate(ev) if e.startswith("UPDATE")]
        assert len(writes) == 2, ev  # the offer, then the soft reserve
        assert all(begin < i < commit for i in writes), ev

    @pytest.mark.asyncio
    async def test_the_offer_row_is_locked_before_the_status_is_trusted(self, conn):
        await _respond("accept")
        ev = conn.events
        select = next(e for e in ev if e.startswith("SELECT o.*"))
        assert "FOR UPDATE OF o" in select
        # A bare FOR UPDATE is a runtime error on this query, not a style choice.
        assert "FOR UPDATE OF o" in select and "o LEFT JOIN" in select
        assert ev.index("BEGIN") < ev.index(select)

    @pytest.mark.asyncio
    async def test_the_listing_reserve_is_the_second_write(self, conn):
        await _respond("accept")
        w = _writes(conn.events)
        assert "public.p2p_offers" in w[0]
        assert "public.marketplace_listings" in w[1]
        assert "reserved_offer_id" in w[1]


class TestWithdrawIsAtomic:
    @pytest.mark.asyncio
    async def test_cancel_and_unreserve_commit_together(self, conn):
        conn.row = _offer_row(status="accepted")
        await _respond("withdraw", user_id=BUYER)
        ev = conn.events
        begin, commit = ev.index("BEGIN"), ev.index("COMMIT")
        writes = [i for i, e in enumerate(ev) if e.startswith("UPDATE")]
        assert len(writes) == 2, ev
        assert all(begin < i < commit for i in writes), ev
        w = _writes(ev)
        assert "withdrawn_by" in w[0]
        assert "reserved_offer_id = NULL" in w[1]


class TestTheLockIsNotHeldOverTheNotification:
    @pytest.mark.asyncio
    async def test_notification_happens_after_commit(self, conn):
        await _respond("accept")
        ev = conn.events
        assert ev.index("COMMIT") < ev.index("NOTIFY"), ev


class TestARejectedResponseWritesNothing:
    @pytest.mark.asyncio
    async def test_a_closed_offer_rolls_back_with_no_writes(self, conn):
        conn.row = _offer_row(status="completed")
        with pytest.raises(Exception):
            await _respond("accept")
        assert _writes(conn.events) == []
        # The guard raises INSIDE the transaction, so it must unwind as one.
        assert conn.events[-1] == "ROLLBACK", conn.events

    @pytest.mark.asyncio
    async def test_the_counter_cap_rolls_back_with_no_writes(self, conn):
        conn.row = _offer_row(counter_count=p2p.MAX_COUNTERS)
        with pytest.raises(Exception):
            await _respond("counter", amount=30.0)
        assert _writes(conn.events) == []
        assert conn.events[-1] == "ROLLBACK", conn.events


# ---------------------------------------------------------------------------
# confirm_exchange — completion must be decided under the lock, exactly once
# ---------------------------------------------------------------------------
#
# Before 2026-09-17 "both sides confirmed" was decided by reading the row back
# after an UNLOCKED write. Two confirms in flight each saw only their own, so
# `both` was false for both callers: completion never fired and the trade sat at
# `accepted` with two confirmation timestamps and no way forward, because
# ALREADY_CONFIRMED blocks the retry that would fix it. The mirror ordering ran
# the completion body TWICE — and `_dac7_accrue` reports consideration for tax.


class _ConfirmConn(_Conn):
    """Answers the two different SELECTs confirm_exchange makes."""

    def __init__(self, offer, fresh, events=None):
        super().__init__(offer, events=events)
        self.fresh = fresh

    async def fetchrow(self, q, *a):
        flat = self._log(q)
        if flat.startswith("SELECT * FROM public.p2p_offers"):
            return self.row
        return self.fresh


def _confirm_rows(seller_at, buyer_at, status="accepted"):
    offer = _Row(
        id=OFFER, listing_id=LISTING, seller_id=SELLER, buyer_id=BUYER,
        status=status, seller_confirmed_at=seller_at, buyer_confirmed_at=buyer_at,
        amount=25.0, currency="EUR",
    )
    fresh = _Row(offer)
    fresh["listing_title"] = "Charizard"
    return offer, fresh


@pytest.fixture
def confirm_env(monkeypatch):
    calls = {"hooks": [], "settle": 0, "events": []}

    import app.features.p2p_listing_router as listing

    async def _stale(*a, **k):
        calls["hooks"].append("stale")
        calls["events"].append("stale")

    async def _sold(*a, **k):
        calls["hooks"].append("sold_comp")
        calls["events"].append("sold_comp")

    async def _gt(*a, **k):
        calls["hooks"].append("ground_truth")
        calls["events"].append("ground_truth")

    async def _dac7(*a, **k):
        calls["hooks"].append("dac7")
        calls["events"].append("dac7")

    async def _settle(conn, *a, **k):
        calls["settle"] += 1
        # Recorded in the connection's own event stream: a count alone cannot
        # tell "inside the transaction" from "after the commit", and a mutation
        # that moved this call past COMMIT kept every test green until it was.
        conn.events.append("SETTLE")

    monkeypatch.setattr(listing, "_stale_supply_hook", _stale)
    monkeypatch.setattr(listing, "_sold_comp_hook", _sold)
    monkeypatch.setattr(listing, "_ground_truth_hook", _gt)
    monkeypatch.setattr(p2p, "_dac7_accrue", _dac7)
    monkeypatch.setattr(p2p, "_settle_completed_trade", _settle)
    monkeypatch.setattr(p2p, "_row_to_offer", lambda r, me: {"id": OFFER})

    async def _noop_notify(*a, **k):
        calls["hooks"].append("notify")

    monkeypatch.setattr(p2p, "_notify_trade", _noop_notify)
    return calls


async def _confirm(conn, monkeypatch, user_id):
    monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
    return await p2p.confirm_exchange(OFFER, user_id=user_id)


class TestConfirmExchange:
    @pytest.mark.asyncio
    async def test_the_offer_row_is_locked(self, monkeypatch, confirm_env):
        offer, fresh = _confirm_rows(None, None)
        conn = _ConfirmConn(offer, fresh, events=confirm_env["events"])
        await _confirm(conn, monkeypatch, SELLER)
        first = next(e for e in conn.events if e.startswith("SELECT * FROM public.p2p_offers"))
        assert "FOR UPDATE" in first, conn.events
        assert conn.events.index("BEGIN") < conn.events.index(first)

    @pytest.mark.asyncio
    async def test_one_sided_confirm_writes_once_and_completes_nothing(self, monkeypatch, confirm_env):
        offer, fresh = _confirm_rows(None, None)
        conn = _ConfirmConn(offer, fresh, events=confirm_env["events"])
        await _confirm(conn, monkeypatch, SELLER)
        writes = _writes(conn.events)
        assert len(writes) == 1 and "seller_confirmed_at" in writes[0], writes
        assert confirm_env["settle"] == 0
        assert "sold_comp" not in confirm_env["hooks"]

    @pytest.mark.asyncio
    async def test_completion_settles_inside_the_transaction(self, monkeypatch, confirm_env):
        # The buyer confirms second: the row read back shows both timestamps.
        offer, fresh = _confirm_rows("2026-09-17T10:00:00Z", None)
        fresh["buyer_confirmed_at"] = "2026-09-17T10:05:00Z"
        conn = _ConfirmConn(offer, fresh, events=confirm_env["events"])
        await _confirm(conn, monkeypatch, BUYER)
        ev = conn.events
        begin, commit = ev.index("BEGIN"), ev.index("COMMIT")
        writes = [i for i, e in enumerate(ev) if e.startswith("UPDATE")]
        assert len(writes) == 3, _writes(ev)  # my confirm, status, listing sold
        assert all(begin < i < commit for i in writes), ev
        assert confirm_env["settle"] == 1
        assert begin < ev.index("SETTLE") < commit, ev

    @pytest.mark.asyncio
    async def test_the_external_hooks_run_after_the_commit(self, monkeypatch, confirm_env):
        offer, fresh = _confirm_rows("2026-09-17T10:00:00Z", None)
        fresh["buyer_confirmed_at"] = "2026-09-17T10:05:00Z"
        conn = _ConfirmConn(offer, fresh, events=confirm_env["events"])
        await _confirm(conn, monkeypatch, BUYER)
        # Each opens its OWN connection; `_sold_comp_hook` SELECTs
        # marketplace_listings and would read the pre-commit status.
        ev = conn.events
        assert confirm_env["hooks"][:4] == ["stale", "sold_comp", "ground_truth", "dac7"]
        commit = ev.index("COMMIT")
        for hook in ("stale", "sold_comp", "ground_truth", "dac7"):
            assert commit < ev.index(hook), (hook, ev)
        # And the settlement, which shares this connection, is on the OTHER side
        # of the commit from them.
        assert ev.index("SETTLE") < commit, ev

    @pytest.mark.asyncio
    async def test_dac7_is_accrued_exactly_once(self, monkeypatch, confirm_env):
        offer, fresh = _confirm_rows("2026-09-17T10:00:00Z", None)
        fresh["buyer_confirmed_at"] = "2026-09-17T10:05:00Z"
        conn = _ConfirmConn(offer, fresh, events=confirm_env["events"])
        await _confirm(conn, monkeypatch, BUYER)
        assert confirm_env["hooks"].count("dac7") == 1

    @pytest.mark.asyncio
    async def test_an_already_completed_trade_accrues_nothing(self, monkeypatch, confirm_env):
        # `completed_now` is False, so the whole completion body — including the
        # tax accrual — must not run a second time.
        offer, fresh = _confirm_rows("2026-09-17T10:00:00Z", None, status="shipped")
        fresh["buyer_confirmed_at"] = "2026-09-17T10:05:00Z"
        fresh["status"] = "completed"
        conn = _ConfirmConn(offer, fresh, events=confirm_env["events"])
        await _confirm(conn, monkeypatch, BUYER)
        assert confirm_env["hooks"].count("dac7") == 0
        assert confirm_env["settle"] == 0


# ---------------------------------------------------------------------------
# marketplace_listing_router.record_sale — money, then a status, in two writes
# ---------------------------------------------------------------------------
#
# Not P2P, but the same class and the same fake: `record_sale` INSERTs a
# `marketplace_sales` row carrying `net_proceeds` and THEN marks the listing
# sold. With no transaction, a failure between them left a banked sale for a
# listing still advertised as available — and the "already recorded" guard reads
# `status = 'sold'`, so the retry did not catch it and wrote a SECOND sale row.
# Two taps did the same thing without any failure at all.

from app.features import marketplace_listing_router as mkt  # noqa: E402

SALE_LISTING = "00000000-0000-0000-0000-0000000eeeee"


class _SaleConn(_Conn):
    def __init__(self, status="active", events=None):
        super().__init__(_Row(id=SALE_LISTING, status=status), events=events)

    async def fetchrow(self, q, *a):
        flat = self._log(q)
        if "INSERT INTO marketplace_sales" in flat:
            return _Row(
                id="sale-1", listing_id=SALE_LISTING, user_id=SELLER,
                sale_price=100.0, net_proceeds=90.0, currency="EUR", status="pending",
            )
        return self.row


def _sale_payload():
    return mkt.SaleRecord(sale_price=100.0, currency="EUR", platform_fee=5.0)


class TestRecordSaleIsAtomic:
    @pytest.mark.asyncio
    async def test_the_insert_and_the_status_commit_together(self, monkeypatch):
        conn = _SaleConn()
        monkeypatch.setattr(mkt, "get_db_pool", lambda: _Pool(conn))
        await mkt.record_sale(SALE_LISTING, _sale_payload(), user_id=SELLER)
        ev = conn.events
        begin, commit = ev.index("BEGIN"), ev.index("COMMIT")
        writes = [i for i, e in enumerate(ev)
                  if e.startswith("INSERT INTO marketplace_sales") or e.startswith("UPDATE marketplace_listings")]
        assert len(writes) == 2, ev
        assert all(begin < i < commit for i in writes), ev

    @pytest.mark.asyncio
    async def test_the_listing_row_is_locked_before_the_guard_is_trusted(self, monkeypatch):
        conn = _SaleConn()
        monkeypatch.setattr(mkt, "get_db_pool", lambda: _Pool(conn))
        await mkt.record_sale(SALE_LISTING, _sale_payload(), user_id=SELLER)
        guard = next(e for e in conn.events if e.startswith("SELECT id, status"))
        assert "FOR UPDATE" in guard, conn.events
        assert conn.events.index("BEGIN") < conn.events.index(guard)

    @pytest.mark.asyncio
    async def test_an_already_sold_listing_banks_nothing(self, monkeypatch):
        conn = _SaleConn(status="sold")
        monkeypatch.setattr(mkt, "get_db_pool", lambda: _Pool(conn))
        with pytest.raises(Exception):
            await mkt.record_sale(SALE_LISTING, _sale_payload(), user_id=SELLER)
        assert not [e for e in conn.events if e.startswith("INSERT INTO marketplace_sales")]
        assert conn.events[-1] == "ROLLBACK", conn.events


# ---------------------------------------------------------------------------
# purchase_router.confirm_deal — the deal and the mandate's spend move together
# ---------------------------------------------------------------------------
#
# The deal's own write is a correct compare-and-set. What was not guarded is the
# MANDATE: `spent_total = spent_total + price` ran as a separate statement
# afterwards, so a failure between them marked the deal purchased while the
# spend never moved — and `max_total_budget` is checked against `spent_total`,
# so the agent could keep spending past the cap the member set. The row count
# was discarded too: a mandate_id that is not the member's matched nothing and
# the spend vanished silently.

from app.agents import purchase_router as purch  # noqa: E402

DEAL = "00000000-0000-0000-0000-00000000dea1"
MANDATE = "00000000-0000-0000-0000-00000000ma01"


class _DealConn(_Conn):
    def __init__(self, counter_status="UPDATE 1", events=None):
        super().__init__(events=events)
        self.counter_status = counter_status

    async def fetchrow(self, q, *a):
        flat = self._log(q)
        if "FROM public.mandate_deals" in flat:
            return _Row(id=DEAL, mandate_id=MANDATE, listing_price=40.0, user_id=SELLER)
        if "max_total_budget" in flat:
            return _Row(max_total_budget=None, spent_total=40.0)
        return None

    async def execute(self, q, *a):
        flat = self._log(q)
        if "UPDATE public.purchase_mandates" in flat and "spent_total" in flat:
            return self.counter_status
        return "UPDATE 1"


class _GetConn:
    def __init__(self, conn):
        self._c = conn

    async def __aenter__(self):
        return self._c

    async def __aexit__(self, *e):
        return False


@pytest.fixture
def deal_env(monkeypatch):
    monkeypatch.setattr(purch, "_require_db", lambda: None)
    monkeypatch.setattr(purch, "_parse_uuid", lambda v, label="id": v)
    monkeypatch.setattr(purch, "_is_uuid", lambda v: False)


async def _confirm_deal(conn, monkeypatch, price=None):
    monkeypatch.setattr(purch, "get_conn", lambda: _GetConn(conn))
    body = purch.DealConfirmBody(confirmed_price=price) if price is not None else purch.DealConfirmBody()
    return await purch.confirm_deal(DEAL, body, user_id=SELLER)


class TestConfirmDealIsAtomic:
    @pytest.mark.asyncio
    async def test_the_deal_and_the_spend_commit_together(self, monkeypatch, deal_env):
        conn = _DealConn()
        out = await _confirm_deal(conn, monkeypatch)
        assert out["status"] == "purchased"
        ev = conn.events
        begin, commit = ev.index("BEGIN"), ev.index("COMMIT")
        writes = [i for i, e in enumerate(ev) if e.startswith("UPDATE public.")]
        assert len(writes) >= 2, ev
        assert all(begin < i < commit for i in writes), ev

    @pytest.mark.asyncio
    async def test_a_spend_that_lands_nowhere_rolls_the_purchase_back(self, monkeypatch, deal_env):
        conn = _DealConn(counter_status="UPDATE 0")
        with pytest.raises(Exception) as e:
            await _confirm_deal(conn, monkeypatch)
        assert getattr(e.value, "status_code", None) == 409, e.value
        assert conn.events[-1] == "ROLLBACK", conn.events


# ---------------------------------------------------------------------------
# A completed trade records the seller's sale
# ---------------------------------------------------------------------------
#
# `marketplace_sales` held 0 rows on production (2026-09-18) against 3 sold
# listings and a completed trade: its only writer is
# POST /marketplace/listings/sales/{id}/record, whose client wrapper has no
# caller, and completion recorded nothing. So GET /portfolio/realised-pl — the
# endpoint docs/COLLECTOR_DEMAND.md §5 asks for — returned nothing for everyone.


class TestCompletionRecordsTheSale:
    @pytest.mark.asyncio
    async def test_the_sale_is_written_inside_the_completion_transaction(self, monkeypatch, confirm_env):
        offer, fresh = _confirm_rows("2026-09-17T10:00:00Z", None)
        fresh["buyer_confirmed_at"] = "2026-09-17T10:05:00Z"
        conn = _ConfirmConn(offer, fresh, events=confirm_env["events"])
        # the real writer, not the patched settlement
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        await p2p.confirm_exchange(OFFER, user_id=BUYER)
        ev = conn.events
        insert = next((e for e in ev if "INSERT INTO public.marketplace_sales" in e), None)
        assert insert, ev
        assert ev.index("BEGIN") < ev.index(insert) < ev.index("COMMIT")

    @pytest.mark.asyncio
    async def test_postage_is_NULL_and_the_fees_are_zero(self, monkeypatch, confirm_env):
        offer, fresh = _confirm_rows("2026-09-17T10:00:00Z", None)
        fresh["buyer_confirmed_at"] = "2026-09-17T10:05:00Z"
        conn = _ConfirmConn(offer, fresh, events=confirm_env["events"])
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        await p2p.confirm_exchange(OFFER, user_id=BUYER)
        insert = next(e for e in conn.events if "INSERT INTO public.marketplace_sales" in e)
        # Sparrow charges nothing on the marketplace and never learns the
        # seller's postage. The NULL is written EXPLICITLY because the column
        # defaults to 0, and 0 would say "postage cost nothing".
        assert "NULL, 0, 0," in insert, insert
        assert "'sparrow'" in insert

    @pytest.mark.asyncio
    async def test_it_cannot_double_a_members_proceeds(self, monkeypatch, confirm_env):
        offer, fresh = _confirm_rows("2026-09-17T10:00:00Z", None)
        fresh["buyer_confirmed_at"] = "2026-09-17T10:05:00Z"
        conn = _ConfirmConn(offer, fresh, events=confirm_env["events"])
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        await p2p.confirm_exchange(OFFER, user_id=BUYER)
        insert = next(e for e in conn.events if "INSERT INTO public.marketplace_sales" in e)
        # There is no unique key on listing_id (checked on prod), so the guard
        # has to be in the statement.
        assert "WHERE NOT EXISTS" in insert, insert

    @pytest.mark.asyncio
    async def test_a_trade_that_does_not_complete_records_no_sale(self, monkeypatch, confirm_env):
        offer, fresh = _confirm_rows(None, None)   # only one side confirms
        conn = _ConfirmConn(offer, fresh, events=confirm_env["events"])
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        await p2p.confirm_exchange(OFFER, user_id=SELLER)
        assert not [e for e in conn.events if "INSERT INTO public.marketplace_sales" in e]


# ---------------------------------------------------------------------------
# set_postage — the one number Sparrow cannot know
# ---------------------------------------------------------------------------
#
# A completed trade records `shipping_cost_actual = NULL`, so realised P/L
# withholds a profit for that sale. This is the seller closing that gap. It must
# not be usable to rewrite the sale price, and it must refuse rather than answer
# `ok` when there is nothing to amend.


class _PostageConn(_Conn):
    def __init__(self, offer, sale_row, events=None):
        super().__init__(offer, events=events)
        self.sale_row = sale_row

    async def fetchrow(self, q, *a):
        flat = self._log(q)
        if flat.startswith("SELECT * FROM public.p2p_offers"):
            return self.row
        if "UPDATE public.marketplace_sales" in flat:
            return self.sale_row
        return None


def _completed_offer(seller=SELLER, status="completed"):
    return _Row(id=OFFER, listing_id=LISTING, seller_id=seller, buyer_id=BUYER, status=status)


def _sale_after(amount):
    return _Row(sale_price=195.0, net_proceeds=195.0 - amount,
                shipping_cost_actual=amount, currency="EUR")


class TestSetPostage:
    @pytest.mark.asyncio
    async def test_the_seller_turns_an_upper_bound_into_a_result(self, monkeypatch):
        conn = _PostageConn(_completed_offer(), _sale_after(7.25))
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        out = await p2p.set_postage(OFFER, p2p.PostageIn(amount=7.25), user_id=SELLER)
        assert out["net_proceeds"] == 187.75
        assert out["shipping_cost_actual"] == 7.25

    @pytest.mark.asyncio
    async def test_zero_postage_is_a_real_answer_not_unknown(self, monkeypatch):
        # Local pickup. 0 and NULL are different, which is the whole reason the
        # column is nullable.
        conn = _PostageConn(_completed_offer(), _sale_after(0))
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        out = await p2p.set_postage(OFFER, p2p.PostageIn(amount=0), user_id=SELLER)
        assert out["net_proceeds"] == 195.0
        assert out["shipping_cost_actual"] == 0

    @pytest.mark.asyncio
    async def test_the_buyer_gets_404_not_403(self, monkeypatch):
        # A 403 would confirm the offer exists to someone who is not party to it.
        conn = _PostageConn(_completed_offer(), _sale_after(5))
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        with pytest.raises(Exception) as e:
            await p2p.set_postage(OFFER, p2p.PostageIn(amount=5), user_id=BUYER)
        assert getattr(e.value, "status_code", None) == 404
        assert not [x for x in conn.events if x.startswith("UPDATE")]

    @pytest.mark.asyncio
    async def test_an_unfinished_trade_is_refused(self, monkeypatch):
        conn = _PostageConn(_completed_offer(status="accepted"), _sale_after(5))
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        with pytest.raises(Exception) as e:
            await p2p.set_postage(OFFER, p2p.PostageIn(amount=5), user_id=SELLER)
        assert getattr(e.value, "status_code", None) == 409
        assert not [x for x in conn.events if x.startswith("UPDATE")]

    @pytest.mark.asyncio
    async def test_no_sale_row_is_404_not_ok(self, monkeypatch):
        # Trades completed before completion recorded sales have no row. Saying
        # `ok` would be the class-S lie on a money path.
        conn = _PostageConn(_completed_offer(), None)
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        with pytest.raises(Exception) as e:
            await p2p.set_postage(OFFER, p2p.PostageIn(amount=5), user_id=SELLER)
        assert getattr(e.value, "status_code", None) == 404
        assert e.value.detail["code"] == "SALE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_the_offer_is_locked_and_the_write_is_in_the_transaction(self, monkeypatch):
        conn = _PostageConn(_completed_offer(), _sale_after(7.25))
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        await p2p.set_postage(OFFER, p2p.PostageIn(amount=7.25), user_id=SELLER)
        ev = conn.events
        select = next(e for e in ev if e.startswith("SELECT * FROM public.p2p_offers"))
        assert "FOR UPDATE" in select
        upd = next(i for i, e in enumerate(ev) if e.startswith("UPDATE public.marketplace_sales"))
        assert ev.index("BEGIN") < upd < ev.index("COMMIT")

    @pytest.mark.asyncio
    async def test_the_net_is_recomputed_from_STORED_numbers(self, monkeypatch):
        conn = _PostageConn(_completed_offer(), _sale_after(7.25))
        monkeypatch.setattr(p2p, "get_db_pool", lambda: _Pool(conn))
        await p2p.set_postage(OFFER, p2p.PostageIn(amount=7.25), user_id=SELLER)
        upd = next(e for e in conn.events if e.startswith("UPDATE public.marketplace_sales"))
        # The sale price comes from the row, never from the request — this
        # endpoint must not be a way to rewrite what the item sold for.
        assert "net_proceeds = sale_price" in upd
        assert "COALESCE(platform_fee, 0)" in upd
