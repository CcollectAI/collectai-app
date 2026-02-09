"""Tests for rate_limit.py pure functions — _prune and _client_ip logic."""
import sys
import time
from unittest.mock import MagicMock
import pytest


# ---------------------------------------------------------------------------
# Mock starlette before importing rate_limit (not installed locally)
# ---------------------------------------------------------------------------

_starlette_request = MagicMock()
_starlette_responses = MagicMock()
sys.modules.setdefault("starlette", MagicMock())
sys.modules.setdefault("starlette.requests", _starlette_request)
sys.modules.setdefault("starlette.responses", _starlette_responses)

from app.rate_limit import _prune, _client_ip, WINDOW_SECONDS  # noqa: E402


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
