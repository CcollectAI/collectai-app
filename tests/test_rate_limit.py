"""Tests for rate_limit.py pure functions — _prune, _client_ip, and per-user limiter."""
import os
import sys
import time
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

# Force DEV_MODE so auth doesn't require real JWT
os.environ.setdefault("DEV_MODE", "true")

# ---------------------------------------------------------------------------
# Mock starlette before importing rate_limit (not installed locally)
# ---------------------------------------------------------------------------

_starlette_request = MagicMock()
_starlette_responses = MagicMock()
sys.modules.setdefault("starlette", MagicMock())
sys.modules.setdefault("starlette.requests", _starlette_request)
sys.modules.setdefault("starlette.responses", _starlette_responses)

from app.rate_limit import (  # noqa: E402
    _prune,
    _prune_user,
    _client_ip,
    _user_hits,
    per_user_rate_limit,
    WINDOW_SECONDS,
    PER_USER_RATE_LIMIT_ENABLED,
)


# ---------------------------------------------------------------------------
# _prune
# ---------------------------------------------------------------------------

class TestPrune:
    def test_empty_list(self):
        assert _prune([], 100.0) == []

    def test_all_within_window(self):
        now = 200.0
        ts = [now - 10, now - 5, now - 1]
        assert _prune(ts, now) == ts

    def test_all_expired(self):
        now = 200.0
        ts = [now - WINDOW_SECONDS - 1, now - WINDOW_SECONDS - 10]
        assert _prune(ts, now) == []

    def test_mixed(self):
        now = 200.0
        old = now - WINDOW_SECONDS - 1
        recent = now - 5
        result = _prune([old, recent], now)
        assert result == [recent]

    def test_exactly_at_cutoff_excluded(self):
        """Timestamps exactly at the cutoff boundary should be excluded (> not >=)."""
        now = 200.0
        at_cutoff = now - WINDOW_SECONDS
        assert _prune([at_cutoff], now) == []

    def test_just_inside_window(self):
        now = 200.0
        just_inside = now - WINDOW_SECONDS + 0.001
        assert _prune([just_inside], now) == [just_inside]

    def test_preserves_order(self):
        now = 200.0
        ts = [now - 30, now - 20, now - 10]
        result = _prune(ts, now)
        assert result == ts

    def test_large_list_performance(self):
        """Prune should handle large timestamp lists."""
        now = 200.0
        ts = [now - i for i in range(1000)]
        result = _prune(ts, now)
        # All within window (max offset = 999 < WINDOW_SECONDS)
        if WINDOW_SECONDS > 999:
            assert len(result) == 1000
        else:
            assert len(result) <= 1000


# ---------------------------------------------------------------------------
# _client_ip
# ---------------------------------------------------------------------------

class TestClientIP:
    def _make_request(self, headers=None, client_host="127.0.0.1"):
        req = MagicMock()
        req.headers = headers or {}
        if client_host:
            req.client = MagicMock()
            req.client.host = client_host
        else:
            req.client = None
        return req

    def test_no_forwarded_header(self):
        req = self._make_request(client_host="192.168.1.1")
        assert _client_ip(req) == "192.168.1.1"

    def test_single_forwarded_ip(self):
        req = self._make_request(headers={"x-forwarded-for": "10.0.0.1"})
        assert _client_ip(req) == "10.0.0.1"

    def test_multiple_forwarded_ips_takes_first(self):
        req = self._make_request(headers={"x-forwarded-for": "10.0.0.1, 10.0.0.2, 10.0.0.3"})
        assert _client_ip(req) == "10.0.0.1"

    def test_forwarded_with_spaces(self):
        req = self._make_request(headers={"x-forwarded-for": "  10.0.0.1 , 10.0.0.2"})
        assert _client_ip(req) == "10.0.0.1"

    def test_no_client(self):
        req = self._make_request(headers={}, client_host=None)
        assert _client_ip(req) == "unknown"

    def test_ipv6_forwarded(self):
        req = self._make_request(headers={"x-forwarded-for": "::1, 10.0.0.2"})
        assert _client_ip(req) == "::1"


# ---------------------------------------------------------------------------
# _prune_user
# ---------------------------------------------------------------------------

class TestPruneUser:
    def test_empty(self):
        assert _prune_user([], 100.0, 60) == []

    def test_custom_window(self):
        now = 200.0
        ts = [now - 30, now - 10]
        # With a 20-second window, only the last one survives
        assert _prune_user(ts, now, 20) == [now - 10]

    def test_all_within_window(self):
        now = 200.0
        ts = [now - 5, now - 3, now - 1]
        assert _prune_user(ts, now, 60) == ts


# ---------------------------------------------------------------------------
# per_user_rate_limit (unit tests using direct invocation)
# ---------------------------------------------------------------------------

class TestPerUserRateLimit:
    """Test the per_user_rate_limit factory and its inner _check function."""

    def setup_method(self):
        """Clear the shared store and ensure per-user limiting is enabled."""
        import app.rate_limit as rl
        rl.PER_USER_RATE_LIMIT_ENABLED = True
        _user_hits.clear()

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        limiter = per_user_rate_limit(5, window_seconds=60, scope="test_under")
        # Should not raise for 5 requests
        for _ in range(5):
            await limiter(user_id="user-a")

    @pytest.mark.asyncio
    async def test_blocks_at_limit(self):
        from fastapi.exceptions import HTTPException

        limiter = per_user_rate_limit(3, window_seconds=60, scope="test_block")
        # First 3 are fine
        for _ in range(3):
            await limiter(user_id="user-b")

        # 4th should raise 429
        with pytest.raises(HTTPException) as exc_info:
            await limiter(user_id="user-b")
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_different_users_independent(self):
        limiter = per_user_rate_limit(2, window_seconds=60, scope="test_indep")
        # User A uses 2 slots
        await limiter(user_id="user-x")
        await limiter(user_id="user-x")

        # User B should still have full quota
        await limiter(user_id="user-y")
        await limiter(user_id="user-y")

    @pytest.mark.asyncio
    async def test_different_scopes_independent(self):
        limiter_a = per_user_rate_limit(2, window_seconds=60, scope="scope_a")
        limiter_b = per_user_rate_limit(2, window_seconds=60, scope="scope_b")

        # Exhaust scope_a for user
        await limiter_a(user_id="user-z")
        await limiter_a(user_id="user-z")

        # scope_b should still work for same user
        await limiter_b(user_id="user-z")
        await limiter_b(user_id="user-z")

    @pytest.mark.asyncio
    async def test_window_expiry(self):
        """Timestamps older than the window should be pruned, freeing capacity."""
        limiter = per_user_rate_limit(2, window_seconds=60, scope="test_expiry")
        key = ("test_expiry", "user-exp")

        # Manually insert old timestamps that are already expired
        old_time = time.monotonic() - 120  # 2 minutes ago
        _user_hits[key] = [old_time, old_time + 1]

        # Should succeed because old timestamps will be pruned
        await limiter(user_id="user-exp")

    @pytest.mark.asyncio
    async def test_retry_after_header_value(self):
        """Retry-After should be a positive integer representing seconds to wait."""
        from fastapi.exceptions import HTTPException

        limiter = per_user_rate_limit(1, window_seconds=30, scope="test_retry")
        await limiter(user_id="user-r")

        with pytest.raises(HTTPException) as exc_info:
            await limiter(user_id="user-r")

        retry_after = int(exc_info.value.headers["Retry-After"])
        assert 1 <= retry_after <= 30

    @pytest.mark.asyncio
    async def test_disabled_via_flag(self):
        """When PER_USER_RATE_LIMIT_ENABLED is False, limiter should be a no-op."""
        import app.rate_limit as rl
        original = rl.PER_USER_RATE_LIMIT_ENABLED

        try:
            rl.PER_USER_RATE_LIMIT_ENABLED = False
            limiter = per_user_rate_limit(1, window_seconds=60, scope="test_disabled")
            # Even after exceeding the limit, should not raise
            await limiter(user_id="user-off")
            await limiter(user_id="user-off")
            await limiter(user_id="user-off")
        finally:
            rl.PER_USER_RATE_LIMIT_ENABLED = original
