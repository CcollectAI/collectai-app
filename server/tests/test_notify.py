"""Tests for app/lib/notify.py — preference-aware, frequency-capped push delivery.

Covers:
  - should_notify: preference enabled/disabled, missing prefs, frequency caps per tier
  - notify_user: sends push when allowed, skips on disabled pref, skips on cap,
                 urgent bypasses cap, handles exceptions, missing category
  - ALERT_TYPE_TO_PREF mapping sanity

All DB calls and push delivery are mocked — no real database needed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")

from app.lib.notify import (
    should_notify,
    notify_user,
    FREE_DAILY_CAP,
    PRO_DAILY_CAP,
    PREMIUM_DAILY_CAP,
    ALERT_TYPE_TO_PREF,
    _get_user_prefs,
    _get_daily_push_count,
    _get_user_tier,
)

TEST_USER = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_conn(prefs=None, tier="free", daily_count=0):
    """Return an AsyncMock conn that responds to the three DB queries."""
    conn = AsyncMock()

    async def _fetchrow(sql, *args):
        sql_lower = sql.strip().lower()
        if "notification_preferences" in sql_lower and "subscription_tier" not in sql_lower:
            if prefs is None:
                return None
            return {"notification_preferences": prefs}
        if "subscription_tier" in sql_lower:
            return {"subscription_tier": tier}
        if "notification_history" in sql_lower:
            return {"cnt": daily_count}
        return None

    conn.fetchrow = AsyncMock(side_effect=_fetchrow)
    return conn


# ---------------------------------------------------------------------------
# _get_user_prefs
# ---------------------------------------------------------------------------

class TestGetUserPrefs:
    """`_get_user_prefs` reads user_settings.notification_preferences.

    History worth keeping: this class previously asserted the OPPOSITE — that
    the function always returned {} and never touched the DB — because it had
    been stubbed out in the 2026-04-20 sweep on the belief that the column did
    not exist. The column does exist and PUT /notifications/preferences had
    been writing it all along, so the stub silently discarded every user's
    saved preferences on the delivery path: mute a category, still get pushed.

    A test that pins a stub is how a bug becomes permanent. These now assert
    the behaviour users actually expect, and the last one is the regression
    guard: a stored `False` MUST be honoured.
    """

    @pytest.mark.asyncio
    async def test_returns_stored_prefs(self):
        conn = _mock_conn(prefs={"price_alerts": False})
        assert await _get_user_prefs(conn, TEST_USER) == {"price_alerts": False}

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_row(self):
        conn = _mock_conn(prefs=None)
        assert await _get_user_prefs(conn, TEST_USER) == {}

    @pytest.mark.asyncio
    async def test_parses_jsonb_returned_as_text(self):
        # asyncpg hands back jsonb as str unless a codec is registered.
        conn = _mock_conn(prefs='{"deal_alerts": false}')
        assert await _get_user_prefs(conn, TEST_USER) == {"deal_alerts": False}

    @pytest.mark.asyncio
    async def test_never_raises_on_db_error(self):
        # A prefs lookup must never be able to block a notification.
        conn = _mock_conn(prefs={})
        conn.fetchrow.side_effect = RuntimeError("connection reset")
        assert await _get_user_prefs(conn, TEST_USER) == {}

    @pytest.mark.asyncio
    async def test_disabled_category_actually_blocks_the_push(self):
        """The regression that mattered: a stored False must reach the gate."""
        conn = _mock_conn(prefs={"price_alerts": False})
        prefs = await _get_user_prefs(conn, TEST_USER)
        assert prefs.get("price_alerts", True) is False


# ---------------------------------------------------------------------------
# _get_daily_push_count
# ---------------------------------------------------------------------------

class TestGetDailyPushCount:
    @pytest.mark.asyncio
    async def test_returns_count(self):
        conn = _mock_conn(daily_count=7)
        result = await _get_daily_push_count(conn, TEST_USER)
        assert result == 7

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_row(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        result = await _get_daily_push_count(conn, TEST_USER)
        assert result == 0


# ---------------------------------------------------------------------------
# _get_user_tier
# ---------------------------------------------------------------------------

class TestGetUserTier:
    @pytest.mark.asyncio
    async def test_returns_tier(self):
        conn = _mock_conn(tier="pro")
        result = await _get_user_tier(conn, TEST_USER)
        assert result == "pro"

    @pytest.mark.asyncio
    async def test_defaults_to_free(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        result = await _get_user_tier(conn, TEST_USER)
        assert result == "free"

    @pytest.mark.asyncio
    async def test_defaults_when_tier_is_none(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"subscription_tier": None})
        result = await _get_user_tier(conn, TEST_USER)
        assert result == "free"


# ---------------------------------------------------------------------------
# should_notify
# ---------------------------------------------------------------------------

class TestShouldNotify:
    @pytest.mark.asyncio
    async def test_allowed_when_pref_enabled(self):
        conn = _mock_conn(prefs={"price_alerts": True}, tier="free", daily_count=0)
        allowed, reason = await should_notify(conn, TEST_USER, "price_alerts")
        assert allowed is True
        assert reason == "ok"

    @pytest.mark.asyncio
    async def test_allowed_when_prefs_empty_defaults_true(self):
        """Missing preference key defaults to True (all notifications on)."""
        conn = _mock_conn(prefs={}, tier="free", daily_count=0)
        allowed, reason = await should_notify(conn, TEST_USER, "price_alerts")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_allowed_when_no_prefs_row(self):
        """No user_settings row at all — defaults to all True."""
        conn = _mock_conn(prefs=None, tier="free", daily_count=0)
        allowed, reason = await should_notify(conn, TEST_USER, "price_alerts")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_pref_disabled_blocks(self):
        # Restored 2026-07-25. This previously asserted the opposite
        # ("no_longer_blocks") because _get_user_prefs had been stubbed to {}
        # on the belief that the column did not exist — so muting a category
        # did nothing. The column exists and is written by
        # PUT /notifications/preferences.
        conn = _mock_conn(prefs={"price_alerts": False}, tier="free", daily_count=0)
        allowed, reason = await should_notify(conn, TEST_USER, "price_alerts")
        assert allowed is False
        assert "disabled" in reason.lower()

    @pytest.mark.asyncio
    async def test_pref_enabled_or_absent_allows(self):
        for prefs in ({"price_alerts": True}, {}, {"deal_alerts": False}):
            conn = _mock_conn(prefs=prefs, tier="free", daily_count=0)
            allowed, _ = await should_notify(conn, TEST_USER, "price_alerts")
            assert allowed is True, f"prefs={prefs} should not block price_alerts"

    @pytest.mark.asyncio
    async def test_blocked_free_cap_reached(self):
        conn = _mock_conn(prefs={}, tier="free", daily_count=FREE_DAILY_CAP)
        allowed, reason = await should_notify(conn, TEST_USER, "price_alerts")
        assert allowed is False
        assert "cap" in reason.lower()
        assert "free" in reason

    @pytest.mark.asyncio
    async def test_allowed_free_under_cap(self):
        conn = _mock_conn(prefs={}, tier="free", daily_count=FREE_DAILY_CAP - 1)
        allowed, reason = await should_notify(conn, TEST_USER, "price_alerts")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_blocked_pro_cap_reached(self):
        conn = _mock_conn(prefs={}, tier="pro", daily_count=PRO_DAILY_CAP)
        allowed, reason = await should_notify(conn, TEST_USER, "deal_alerts")
        assert allowed is False
        assert "pro" in reason

    @pytest.mark.asyncio
    async def test_allowed_pro_under_cap(self):
        conn = _mock_conn(prefs={}, tier="pro", daily_count=PRO_DAILY_CAP - 1)
        allowed, _ = await should_notify(conn, TEST_USER, "deal_alerts")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_blocked_premium_cap_reached(self):
        conn = _mock_conn(prefs={}, tier="premium", daily_count=PREMIUM_DAILY_CAP)
        allowed, reason = await should_notify(conn, TEST_USER, "value_changes")
        assert allowed is False
        assert "premium" in reason

    @pytest.mark.asyncio
    async def test_allowed_premium_under_cap(self):
        conn = _mock_conn(prefs={}, tier="premium", daily_count=PREMIUM_DAILY_CAP - 1)
        allowed, _ = await should_notify(conn, TEST_USER, "value_changes")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_unknown_tier_defaults_to_free_cap(self):
        conn = _mock_conn(prefs={}, tier="enterprise", daily_count=FREE_DAILY_CAP)
        allowed, reason = await should_notify(conn, TEST_USER, "price_alerts")
        assert allowed is False
        assert "cap" in reason.lower()

    @pytest.mark.asyncio
    async def test_unknown_category_defaults_true(self):
        """A category not in user prefs dict still defaults to True."""
        conn = _mock_conn(prefs={"price_alerts": False}, tier="free", daily_count=0)
        allowed, _ = await should_notify(conn, TEST_USER, "some_new_category")
        assert allowed is True


# ---------------------------------------------------------------------------
# notify_user
# ---------------------------------------------------------------------------

class TestNotifyUser:
    @pytest.mark.asyncio
    async def test_sends_push_when_allowed(self):
        conn = _mock_conn(prefs={}, tier="free", daily_count=0)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock, return_value=1) as mock_push:
            sent = await notify_user(conn, TEST_USER, "Price Alert", "Dropped", category="price_alerts")
        assert sent == 1
        mock_push.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pref_disabled_skips(self):
        # Restored 2026-07-25 — see TestGetUserPrefs. Muting a category must
        # stop the push, not merely deprioritise it.
        conn = _mock_conn(prefs={"price_alerts": False}, tier="free", daily_count=0)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock, return_value=1) as mock_push:
            sent = await notify_user(conn, TEST_USER, "Price Alert", "Dropped", category="price_alerts")
        assert sent == 0
        mock_push.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_when_daily_cap_reached(self):
        conn = _mock_conn(prefs={}, tier="free", daily_count=FREE_DAILY_CAP)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock) as mock_push:
            sent = await notify_user(conn, TEST_USER, "Alert", "Body", category="price_alerts")
        assert sent == 0
        mock_push.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_urgent_bypasses_cap(self):
        conn = _mock_conn(prefs={}, tier="free", daily_count=FREE_DAILY_CAP + 10)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock, return_value=1) as mock_push:
            sent = await notify_user(
                conn, TEST_USER, "URGENT", "Body", category="price_alerts", urgent=True
            )
        assert sent == 1
        mock_push.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_urgent_bypasses_the_cap_but_not_the_preference(self):
        """docs/alerts-and-insights.md: urgent alerts "bypass frequency caps but
        still respect user preferences". notify_user checks the preference
        unconditionally (`# Check preference (always)`) and only the cap is
        skipped for urgent."""
        # Muted category + urgent -> still blocked.
        conn = _mock_conn(prefs={"price_alerts": False}, tier="free", daily_count=0)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock, return_value=1) as mock_push:
            sent = await notify_user(
                conn, TEST_USER, "URGENT", "Body", category="price_alerts", urgent=True
            )
        assert sent == 0
        mock_push.assert_not_awaited()

        # Not muted, but over the daily cap + urgent -> sends anyway.
        conn = _mock_conn(prefs={}, tier="free", daily_count=FREE_DAILY_CAP)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock, return_value=1) as mock_push:
            sent = await notify_user(
                conn, TEST_USER, "URGENT", "Body", category="price_alerts", urgent=True
            )
        assert sent == 1
        mock_push.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_data_and_deep_link(self):
        conn = _mock_conn(prefs={}, tier="pro", daily_count=0)
        data = {"item_id": "123", "type": "price_alert"}
        with patch("app.push.send_push_to_user", new_callable=AsyncMock, return_value=1) as mock_push:
            await notify_user(
                conn, TEST_USER, "Title", "Body",
                category="price_alerts", data=data, deep_link="/items/123",
            )
        call_kwargs = mock_push.call_args
        assert call_kwargs.kwargs.get("data") == data or call_kwargs[1].get("data") == data

    @pytest.mark.asyncio
    async def test_returns_zero_on_exception(self):
        conn = _mock_conn(prefs={}, tier="free", daily_count=0)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            sent = await notify_user(conn, TEST_USER, "Title", "Body", category="price_alerts")
        assert sent == 0

    @pytest.mark.asyncio
    async def test_pro_tier_15_cap(self):
        conn = _mock_conn(prefs={}, tier="pro", daily_count=14)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock, return_value=1) as mock_push:
            sent = await notify_user(conn, TEST_USER, "Title", "Body", category="deal_alerts")
        assert sent == 1
        mock_push.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pro_tier_blocked_at_15(self):
        conn = _mock_conn(prefs={}, tier="pro", daily_count=15)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock) as mock_push:
            sent = await notify_user(conn, TEST_USER, "Title", "Body", category="deal_alerts")
        assert sent == 0
        mock_push.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_premium_tier_30_cap(self):
        conn = _mock_conn(prefs={}, tier="premium", daily_count=29)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock, return_value=1) as mock_push:
            sent = await notify_user(conn, TEST_USER, "Title", "Body")
        assert sent == 1

    @pytest.mark.asyncio
    async def test_premium_tier_blocked_at_30(self):
        conn = _mock_conn(prefs={}, tier="premium", daily_count=30)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock) as mock_push:
            sent = await notify_user(conn, TEST_USER, "Title", "Body")
        assert sent == 0

    @pytest.mark.asyncio
    async def test_default_category_is_price_alerts(self):
        """When no category is specified, 'price_alerts' is the default."""
        conn = _mock_conn(prefs={"price_alerts": False}, tier="free", daily_count=0)
        with patch("app.push.send_push_to_user", new_callable=AsyncMock) as mock_push:
            sent = await notify_user(conn, TEST_USER, "Title", "Body")
        assert sent == 0  # blocked because price_alerts is disabled


# ---------------------------------------------------------------------------
# ALERT_TYPE_TO_PREF mapping
# ---------------------------------------------------------------------------

class TestAlertTypeToPref:
    def test_all_values_are_strings(self):
        for key, val in ALERT_TYPE_TO_PREF.items():
            assert isinstance(key, str)
            assert isinstance(val, str)

    def test_expected_mappings_present(self):
        assert ALERT_TYPE_TO_PREF["price_alert"] == "price_alerts"
        assert ALERT_TYPE_TO_PREF["deal_alert"] == "deal_alerts"
        assert ALERT_TYPE_TO_PREF["chat_message"] == "chat_messages"
        assert ALERT_TYPE_TO_PREF["weekly_digest"] == "weekly_digest"

    def test_cap_constants(self):
        assert FREE_DAILY_CAP == 3
        assert PRO_DAILY_CAP == 15
        assert PREMIUM_DAILY_CAP == 30
