"""
Tests for workers/deal_discovery_worker.py — DealDiscoveryWorker run_once().

Covers:
  1. DSN not set -> returns early without error
  2. scan returns empty list -> no pushes sent
  3. scan returns 2 deals -> push sends > 0, deals marked notified
  4. push raises exception for first deal -> continues to second
  5. scan_all_active raises exception -> agent still closed
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_deal(**overrides):
    """Build a minimal deal dict matching what DealDiscoveryAgent.scan_all_active returns."""
    deal = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "listing_title": "Charizard PSA 10 Base Set",
        "listing_price": 350.00,
        "listing_url": "https://ebay.com/itm/123",
        "affiliate_url": "https://ebay.com/aff/123",
    }
    deal.update(overrides)
    return deal


def _build_pool_and_conn():
    """Create a mock asyncpg pool and connection using an async context manager."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetchval = AsyncMock(return_value=0)

    @asynccontextmanager
    async def _mock_acquire():
        yield mock_conn

    mock_pool = AsyncMock()
    mock_pool.acquire = _mock_acquire
    mock_pool.close = AsyncMock()

    return mock_pool, mock_conn


# ---------------------------------------------------------------------------
# Fixture: disable the retry decorator so run_once can be tested directly
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_retry():
    """Disable with_async_retry so tests exercise run_once without retries/sleep."""
    def noop_retry(**kwargs):
        def decorator(fn):
            return fn
        return decorator

    with patch("workers.retry.with_async_retry", noop_retry):
        import importlib
        import workers.deal_discovery_worker as mod
        importlib.reload(mod)
        yield mod
        importlib.reload(mod)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunOnceNoDsn:
    """When DSN is not set, run_once should return immediately without error."""

    @pytest.mark.asyncio
    async def test_run_once_no_dsn(self, _patch_retry):
        mod = _patch_retry

        with patch.object(mod, "DSN", None):
            # Should not raise, just log and return
            await mod.run_once()


class TestRunOnceNoDeals:
    """When scan_all_active returns an empty list, no pushes should be sent."""

    @pytest.mark.asyncio
    async def test_run_once_no_deals(self, _patch_retry):
        mod = _patch_retry
        mock_pool, mock_conn = _build_pool_and_conn()

        mock_agent = MagicMock()
        mock_agent.scan_all_active = AsyncMock(return_value=[])
        mock_agent.close = AsyncMock()

        mock_send = AsyncMock(return_value=1)

        with patch.object(mod, "DSN", "mock://dsn"):
            with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
                with patch("app.agents.deal_discovery_agent.DealDiscoveryAgent", return_value=mock_agent):
                    with patch("app.push.send_push_to_user", mock_send):
                        await mod.run_once()

        # Agent was created, scanned, and closed
        mock_agent.scan_all_active.assert_awaited_once()
        mock_agent.close.assert_awaited_once()

        # No deals -> send_push_to_user should never be called
        mock_send.assert_not_awaited()

        # Pool should be closed
        mock_pool.close.assert_awaited_once()


class TestRunOnceWithDealsAndPush:
    """When scan returns 2 deals and push succeeds, both should be marked notified."""

    @pytest.mark.asyncio
    async def test_run_once_with_deals_and_push(self, _patch_retry):
        mod = _patch_retry
        mock_pool, mock_conn = _build_pool_and_conn()

        deal_1 = _make_deal()
        deal_2 = _make_deal()
        new_deals = [deal_1, deal_2]

        mock_agent = MagicMock()
        mock_agent.scan_all_active = AsyncMock(return_value=new_deals)
        mock_agent.close = AsyncMock()

        # send_push_to_user returns >0 for both deals
        mock_send = AsyncMock(return_value=1)

        with patch.object(mod, "DSN", "mock://dsn"):
            with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
                with patch("app.agents.deal_discovery_agent.DealDiscoveryAgent", return_value=mock_agent):
                    with patch("app.push.send_push_to_user", mock_send):
                        await mod.run_once()

        # Push should have been called once per deal
        assert mock_send.await_count == 2

        # Each deal should have triggered an UPDATE ... SET status = 'notified'
        assert mock_conn.execute.await_count == 2
        for c in mock_conn.execute.call_args_list:
            sql = c[0][0]
            assert "notified" in sql
            assert "mandate_deals" in sql

        mock_agent.close.assert_awaited_once()
        mock_pool.close.assert_awaited_once()


class TestRunOncePushFailureContinues:
    """If push raises for the first deal, the worker should continue to the second."""

    @pytest.mark.asyncio
    async def test_run_once_push_failure_continues(self, _patch_retry):
        mod = _patch_retry
        mock_pool, mock_conn = _build_pool_and_conn()

        deal_1 = _make_deal()
        deal_2 = _make_deal()
        new_deals = [deal_1, deal_2]

        mock_agent = MagicMock()
        mock_agent.scan_all_active = AsyncMock(return_value=new_deals)
        mock_agent.close = AsyncMock()

        # First call raises, second call succeeds
        mock_send = AsyncMock(side_effect=[Exception("APNS timeout"), 1])

        with patch.object(mod, "DSN", "mock://dsn"):
            with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
                with patch("app.agents.deal_discovery_agent.DealDiscoveryAgent", return_value=mock_agent):
                    with patch("app.push.send_push_to_user", mock_send):
                        await mod.run_once()

        # Push was attempted for both deals
        assert mock_send.await_count == 2

        # Only the second deal should have been marked notified (first push failed)
        assert mock_conn.execute.await_count == 1
        sql = mock_conn.execute.call_args_list[0][0][0]
        assert "notified" in sql

        # The UUID passed should be deal_2's id
        passed_uuid = mock_conn.execute.call_args_list[0][0][1]
        assert str(passed_uuid) == deal_2["id"]

        mock_agent.close.assert_awaited_once()
        mock_pool.close.assert_awaited_once()


class TestRunOnceAgentError:
    """If scan_all_active raises an exception, agent.close() must still be called."""

    @pytest.mark.asyncio
    async def test_run_once_agent_error(self, _patch_retry):
        mod = _patch_retry
        mock_pool, mock_conn = _build_pool_and_conn()

        mock_agent = MagicMock()
        mock_agent.scan_all_active = AsyncMock(side_effect=RuntimeError("DB connection lost"))
        mock_agent.close = AsyncMock()

        with patch.object(mod, "DSN", "mock://dsn"):
            with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
                with patch("app.agents.deal_discovery_agent.DealDiscoveryAgent", return_value=mock_agent):
                    with pytest.raises(RuntimeError, match="DB connection lost"):
                        await mod.run_once()

        # Even after error, agent.close() must be awaited (finally block)
        mock_agent.close.assert_awaited_once()

        # Pool must also be closed (outer finally block)
        mock_pool.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# Watchlist snipes
#
# Until 2026-08-04 `_check_watchlist_snipes` joined on `mh.category = w.category`
# alone — the docstring claimed a fuzzy title match that was never in the SQL.
# Any listing in the category under the target fired: a €8015 target on an MTG
# dual land alerted on a €0.02 common, with a dead button attached because the
# matched row was a Scryfall price observation with no URL.
#
# These are structural asserts on the query. They cannot prove the join returns
# the right rows (that needs real data — verified separately against prod), but
# they do fail loudly if someone widens the join back to category-only.
# ---------------------------------------------------------------------------

class TestWatchlistSnipeQuery:
    """The snipe query must require identity, buyability, and a price ceiling."""

    @pytest.mark.asyncio
    async def test_query_requires_item_identity(self, _patch_retry):
        mod = _patch_retry
        _, conn = _build_pool_and_conn()

        await mod._check_watchlist_snipes(conn)

        sql = conn.fetch.await_args.args[0]
        # Exact catalog identity: item_id is bare, item_ref namespaced.
        assert "mh.item_ref = w.category || ':' || w.item_id" in sql
        # Title fallback exists for free-text rows, and is bounded.
        assert "similarity(mh.title, w.title)" in sql
        # The old behaviour: category alone must NOT be the whole join condition.
        assert "ON mh.category = w.category" not in sql

    @pytest.mark.asyncio
    async def test_query_requires_a_buyable_listing(self, _patch_retry):
        mod = _patch_retry
        _, conn = _build_pool_and_conn()

        await mod._check_watchlist_snipes(conn)

        sql = conn.fetch.await_args.args[0]
        assert "mh.url IS NOT NULL" in sql
        assert "mh.is_listing IS TRUE" in sql

    @pytest.mark.asyncio
    async def test_query_excludes_identity_free_titles(self, _patch_retry):
        """`(unnamed)` legacy rows must not match everything in their category."""
        mod = _patch_retry
        _, conn = _build_pool_and_conn()

        await mod._check_watchlist_snipes(conn)

        args = conn.fetch.await_args.args
        assert args[1] == mod._TITLE_MATCH_THRESHOLD
        assert "(unnamed)" in args[2]

    @pytest.mark.asyncio
    async def test_no_rows_sends_nothing(self, _patch_retry):
        mod = _patch_retry
        _, conn = _build_pool_and_conn()

        assert await mod._check_watchlist_snipes(conn) == 0
        conn.execute.assert_not_awaited()


class TestWatchlistSnipePayload:
    """The alert must carry what the Alerts screen needs to render a live link."""

    @staticmethod
    def _row(**overrides):
        row = {
            "watchlist_id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "title": "Bayou",
            "category": "mtg",
            "target_price": 8015.00,
            "currency": "EUR",
            # EUR-converted target, computed in SQL by joining the member's
            # currency against the shared fx arrays. Equal to target_price only
            # because this fixture is a EUR row.
            "target_price_eur": 8015.00,
            "listing_title": "Bayou Revised NM",
            "listing_price": 6200.00,
            "listing_url": "https://www.ebay.com/itm/123",
            "provider": "ebay",
        }
        row.update(overrides)
        return row

    async def _run(self, mod, row):
        _, conn = _build_pool_and_conn()
        conn.fetch = AsyncMock(return_value=[row])
        # tier lookup -> free; today's count -> 0
        conn.fetchrow = AsyncMock(side_effect=[{"cnt": 0}, {"plan": "pro"}])
        with patch("app.lib.notify.notify_user", AsyncMock()):
            sent = await mod._check_watchlist_snipes(conn)
        return sent, conn

    @pytest.mark.asyncio
    async def test_trigger_value_carries_listing_source(self, _patch_retry):
        """app/alerts.tsx reads `listing_source` for the button label.

        Only `provider` was ever written, so every snipe rendered
        "View on Marketplace" instead of naming the marketplace.
        """
        import json

        mod = _patch_retry
        sent, conn = await self._run(mod, self._row())
        assert sent == 1

        insert = conn.execute.await_args.args
        payload = json.loads(insert[3])
        assert payload["listing_source"] == "ebay"
        assert payload["listing_url"] == "https://www.ebay.com/itm/123"

    @pytest.mark.asyncio
    async def test_message_names_the_marketplace(self, _patch_retry):
        mod = _patch_retry
        sent, conn = await self._run(mod, self._row())
        assert sent == 1

        message = conn.execute.await_args.args[4]
        assert "on ebay" in message
        assert "Bayou Revised NM" in message

    @pytest.mark.asyncio
    async def test_item_id_is_the_dedupe_handle(self, _patch_retry):
        """item_id stays `watchlist_snipe:<uuid>`; app/alerts.tsx must not route on it."""
        mod = _patch_retry
        row = self._row()
        sent, conn = await self._run(mod, row)
        assert sent == 1

        item_id = conn.execute.await_args.args[2]
        assert item_id == f"watchlist_snipe:{row['watchlist_id']}"


class TestWatchlistSnipeDeepLink:
    """The notification must land somewhere.

    MEASURED against prod 2026-08-04: all 11 rows in notification_history had
    deep_link NULL, and app/notifications.tsx::handleTap navigates only when
    it is set — so every notification in the app was tap-to-nothing.
    """

    @pytest.mark.asyncio
    async def test_notification_carries_a_deep_link(self, _patch_retry):
        mod = _patch_retry
        _, conn = _build_pool_and_conn()
        conn.fetch = AsyncMock(return_value=[TestWatchlistSnipePayload._row()])
        conn.fetchrow = AsyncMock(side_effect=[{"cnt": 0}, {"plan": "pro"}])

        notify = AsyncMock()
        with patch("app.lib.notify.notify_user", notify):
            assert await mod._check_watchlist_snipes(conn) == 1

        kwargs = notify.await_args.kwargs
        assert kwargs["deep_link"], "snipe notification has no deep_link — tapping it does nothing"
        assert kwargs["deep_link"].startswith("https://")

    @pytest.mark.asyncio
    async def test_no_listing_url_means_no_deep_link(self, _patch_retry):
        """Never fabricate a destination. No URL → no link, rather than a dead one."""
        mod = _patch_retry
        _, conn = _build_pool_and_conn()
        conn.fetch = AsyncMock(return_value=[TestWatchlistSnipePayload._row(listing_url=None)])
        conn.fetchrow = AsyncMock(side_effect=[{"cnt": 0}, {"plan": "pro"}])

        notify = AsyncMock()
        with patch("app.lib.notify.notify_user", notify):
            await mod._check_watchlist_snipes(conn)

        assert notify.await_args.kwargs["deep_link"] is None


class TestWatchlistSnipeCurrency:
    """`target_price` is stored in the MEMBER's currency; the comparison is EUR.

    Watching a JPY 8000 listing wrote `target_price = 8000, currency = 'EUR'`
    and Target Hit then read 8000 as euros — ~164x too generous, firing on
    listings the member could not afford. The query now converts, and the worker
    must consume the CONVERTED column, not the raw one.
    """

    @pytest.mark.asyncio
    async def test_worker_reads_the_converted_target(self, _patch_retry):
        """The message and the discount are EUR, so they must use the EUR half.

        Pinning this because both columns are on the row and picking the wrong
        one is silent: `target_price` alone still produces a plausible-looking
        alert, just one whose percentage and euro figure are nonsense.
        """
        mod = _patch_retry
        row = TestWatchlistSnipePayload._row(
            target_price=8000.00,      # what the member typed, in JPY
            currency="JPY",
            target_price_eur=48.80,    # what it is worth
            listing_price=40.00,       # EUR — under the real target
        )
        _, conn = _build_pool_and_conn()
        conn.fetch = AsyncMock(return_value=[row])
        conn.fetchrow = AsyncMock(side_effect=[{"cnt": 0}, {"plan": "pro"}])
        with patch("app.lib.notify.notify_user", AsyncMock()):
            assert await mod._check_watchlist_snipes(conn) == 1

        payload = json.loads(conn.execute.await_args.args[3])
        # 40 against a real target of 48.80 is ~18% below; against the raw 8000
        # it would read as 99% below, which is the tell that the wrong column
        # was used.
        assert 15 <= payload["discount_pct"] <= 20, payload["discount_pct"]

    @pytest.mark.asyncio
    async def test_query_converts_with_the_members_currency(self, _patch_retry):
        """The SQL must join fx on the WATCHLIST currency, not the listing's."""
        mod = _patch_retry
        _, conn = _build_pool_and_conn()
        conn.fetch = AsyncMock(return_value=[])
        await mod._check_watchlist_snipes(conn)
        sql = conn.fetch.await_args.args[0]
        assert "fxw.code = w.currency" in sql
        assert "mh.price_eur <= w.target_price * COALESCE(fxw.rate, 1)" in sql
        # Never jsonb: app/db.py's codec double-encodes it and every rate
        # silently becomes NULL (see fx_service.fx_arrays).
        assert "::jsonb" not in sql
