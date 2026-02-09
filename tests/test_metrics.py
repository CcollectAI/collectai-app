"""Tests for metrics.py pure functions — ID detection, label generation, rendering."""
import sys
from unittest.mock import MagicMock
import pytest

# ---------------------------------------------------------------------------
# Mock fastapi/starlette before importing metrics (not installed locally)
# ---------------------------------------------------------------------------

sys.modules.setdefault("fastapi", MagicMock())
sys.modules.setdefault("starlette", MagicMock())
sys.modules.setdefault("starlette.requests", MagicMock())
sys.modules.setdefault("starlette.responses", MagicMock())

from app.metrics import (  # noqa: E402
    _looks_like_id,
    _label,
    _render_metrics,
    _request_count,
    _request_duration_sum,
)


# ---------------------------------------------------------------------------
# _looks_like_id
# ---------------------------------------------------------------------------

class TestLooksLikeId:
    def test_uuid_format(self):
        assert _looks_like_id("550e8400-e29b-41d4-a716-446655440000") is True

    def test_long_hex_string(self):
        assert _looks_like_id("a" * 20) is True

    def test_short_segment(self):
        assert _looks_like_id("items") is False

    def test_empty_string(self):
        assert _looks_like_id("") is False

    def test_numeric_id_short(self):
        assert _looks_like_id("123") is False

    def test_19_chars_not_id(self):
        assert _looks_like_id("a" * 19) is False

    def test_20_chars_is_id(self):
        assert _looks_like_id("a" * 20) is True

    def test_uuid_no_dashes(self):
        """32 hex chars without dashes — caught by length >= 20."""
        s = "550e8400e29b41d4a716446655440000"
        assert _looks_like_id(s) is True

    def test_path_segment(self):
        assert _looks_like_id("predict") is False


# ---------------------------------------------------------------------------
# _label
# ---------------------------------------------------------------------------

class TestLabel:
    def test_basic_path(self):
        result = _label("GET", "/api/items", 200)
        assert result == "GET|/api/items|200"

    def test_id_replacement(self):
        result = _label("GET", "/api/items/550e8400-e29b-41d4-a716-446655440000", 200)
        assert "{id}" in result
        assert "550e8400" not in result

    def test_trailing_slash_stripped(self):
        r1 = _label("GET", "/api/items/", 200)
        r2 = _label("GET", "/api/items", 200)
        assert r1 == r2

    def test_preserves_method_and_status(self):
        result = _label("POST", "/api/predict", 201)
        assert result.startswith("POST|")
        assert result.endswith("|201")

    def test_root_path(self):
        result = _label("GET", "/", 200)
        assert result == "GET||200"

    def test_multiple_segments_with_id(self):
        result = _label("DELETE", "/api/users/550e8400-e29b-41d4-a716-446655440000/items", 204)
        parts = result.split("|")
        assert parts[0] == "DELETE"
        assert "{id}" in parts[1]
        assert "items" in parts[1]
        assert parts[2] == "204"


# ---------------------------------------------------------------------------
# _render_metrics
# ---------------------------------------------------------------------------

class TestRenderMetrics:
    def test_empty_metrics(self):
        saved_count = dict(_request_count)
        saved_duration = dict(_request_duration_sum)
        _request_count.clear()
        _request_duration_sum.clear()

        try:
            output = _render_metrics()
            assert "# HELP http_requests_total" in output
            assert "# TYPE http_requests_total counter" in output
            assert "# HELP http_request_duration_seconds_sum" in output
        finally:
            _request_count.update(saved_count)
            _request_duration_sum.update(saved_duration)

    def test_renders_count_and_duration(self):
        saved_count = dict(_request_count)
        saved_duration = dict(_request_duration_sum)
        _request_count.clear()
        _request_duration_sum.clear()

        try:
            _request_count["GET|/api/test|200"] = 5
            _request_duration_sum["GET|/api/test|200"] = 1.2345

            output = _render_metrics()
            assert 'http_requests_total{method="GET",path="/api/test",status="200"} 5' in output
            assert 'http_request_duration_seconds_sum{method="GET",path="/api/test",status="200"} 1.2345' in output
        finally:
            _request_count.clear()
            _request_duration_sum.clear()
            _request_count.update(saved_count)
            _request_duration_sum.update(saved_duration)

    def test_ends_with_newline(self):
        output = _render_metrics()
        assert output.endswith("\n")

    def test_multiple_labels_sorted(self):
        saved_count = dict(_request_count)
        saved_duration = dict(_request_duration_sum)
        _request_count.clear()
        _request_duration_sum.clear()

        try:
            _request_count["POST|/b|201"] = 2
            _request_count["GET|/a|200"] = 3
            output = _render_metrics()
            # GET /a should appear before POST /b (sorted)
            pos_a = output.index("GET")
            pos_b = output.index("POST")
            assert pos_a < pos_b
        finally:
            _request_count.clear()
            _request_duration_sum.clear()
            _request_count.update(saved_count)
            _request_duration_sum.update(saved_duration)
