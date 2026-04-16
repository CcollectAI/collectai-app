"""
Tests for workers/aggregate_catalog_attributes.py.

Covers:
  - aggregate_attrs_for_group: mode for strings, median for numerics,
    min_obs threshold, confidence scoring, attributes_raw skip.
  - JSONB merge safety: existing non-market_observed keys must survive
    (tested via _write_aggregate SQL shape).
  - dry-run vs apply mode gating.
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")


# ---------------------------------------------------------------------------
# Pure-function tests: aggregate_attrs_for_group
# ---------------------------------------------------------------------------

class TestAggregateAttrsForGroup:

    @staticmethod
    def _fn():
        from workers.aggregate_catalog_attributes import aggregate_attrs_for_group
        return aggregate_attrs_for_group

    def test_string_mode(self):
        fn = self._fn()
        hits = [
            {"brand": "Nintendo"},
            {"brand": "Nintendo"},
            {"brand": "Sega"},
            {"brand": "Nintendo"},
        ]
        result = fn(hits, min_obs=3)
        assert "brand" in result
        assert result["brand"]["value"] == "Nintendo"
        assert result["brand"]["type"] == "string"
        assert result["brand"]["n"] == 4
        assert result["brand"]["confidence"] == 0.75

    def test_numeric_median(self):
        fn = self._fn()
        hits = [{"year": 2000}, {"year": 2001}, {"year": 2003}, {"year": 2002}]
        result = fn(hits, min_obs=3)
        assert "year" in result
        assert result["year"]["type"] == "numeric"
        assert result["year"]["median"] == 2001.5
        assert result["year"]["n"] == 4

    def test_min_obs_threshold(self):
        fn = self._fn()
        hits = [{"brand": "Nintendo"}, {"brand": "Sega"}]
        result = fn(hits, min_obs=3)
        assert "brand" not in result  # only 2 obs, need 3

    def test_attributes_raw_skipped(self):
        fn = self._fn()
        hits = [
            {"brand": "A", "attributes_raw": {"x": 1}},
            {"brand": "A", "attributes_raw": {"y": 2}},
            {"brand": "A", "attributes_raw": {"z": 3}},
        ]
        result = fn(hits, min_obs=3)
        assert "brand" in result
        assert "attributes_raw" not in result

    def test_empty_hits(self):
        fn = self._fn()
        assert fn([], min_obs=1) == {}

    def test_none_values_skipped(self):
        fn = self._fn()
        hits = [{"brand": None}, {"brand": "A"}, {"brand": "A"}, {"brand": "A"}]
        result = fn(hits, min_obs=3)
        assert result["brand"]["n"] == 3

    def test_mixed_types_treated_as_string(self):
        fn = self._fn()
        hits = [{"grade": "PSA 10"}, {"grade": "PSA 9"}, {"grade": "PSA 10"}]
        result = fn(hits, min_obs=3)
        assert result["grade"]["type"] == "string"

    def test_confidence_range(self):
        fn = self._fn()
        hits = [{"color": "Red"}] * 5 + [{"color": "Blue"}] * 5
        result = fn(hits, min_obs=3)
        assert 0.0 <= result["color"]["confidence"] <= 1.0

    def test_distribution_capped_at_10(self):
        fn = self._fn()
        # Create 15 distinct brands each appearing 3+ times
        hits = []
        for i in range(15):
            for _ in range(3):
                hits.append({"brand": f"Brand{i}"})
        result = fn(hits, min_obs=3)
        assert len(result["brand"]["distribution"]) <= 10

    def test_non_dict_hits_ignored(self):
        fn = self._fn()
        hits = [{"brand": "A"}, "not a dict", None, {"brand": "A"}, {"brand": "A"}]
        result = fn(hits, min_obs=3)
        assert result["brand"]["n"] == 3


# ---------------------------------------------------------------------------
# _is_numeric edge cases
# ---------------------------------------------------------------------------

class TestIsNumeric:

    @staticmethod
    def _fn():
        from workers.aggregate_catalog_attributes import _is_numeric
        return _is_numeric

    def test_bool_not_numeric(self):
        assert not self._fn()(True)

    def test_int_is_numeric(self):
        assert self._fn()(42)

    def test_float_string_is_numeric(self):
        assert self._fn()("3.14")

    def test_word_not_numeric(self):
        assert not self._fn()("hello")


# ---------------------------------------------------------------------------
# Feature-flag gating
# ---------------------------------------------------------------------------

class TestRunOnceGating:

    @pytest.mark.asyncio
    async def test_apply_blocked_without_flag(self):
        """Apply mode must refuse if ATTR_AGGREGATION_ENABLED != 'true'."""
        with patch.dict(os.environ, {"ATTR_AGGREGATION_ENABLED": "false"}):
            from workers.aggregate_catalog_attributes import run_once
            stats = await run_once(dry_run=False)
            assert stats.get("skipped_flag") is True

    @pytest.mark.asyncio
    async def test_dry_run_allowed_without_flag(self):
        """Dry run should NOT be blocked by the feature flag — only writes are."""
        with patch.dict(os.environ, {"ATTR_AGGREGATION_ENABLED": "false"}), \
             patch("app.db.get_conn") as mock_get_conn, \
             patch("app.db.db_configured", return_value=True):
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_get_conn.return_value = mock_ctx
            from workers.aggregate_catalog_attributes import run_once
            stats = await run_once(dry_run=True)
            assert "skipped_flag" not in stats


# ---------------------------------------------------------------------------
# JSONB merge safety — _write_aggregate uses jsonb_set, not ||
# ---------------------------------------------------------------------------

class TestWriteAggregateSafety:

    @pytest.mark.asyncio
    async def test_uses_jsonb_set(self):
        """_write_aggregate SQL must contain jsonb_set, not ||."""
        from workers.aggregate_catalog_attributes import _write_aggregate
        mock_conn = AsyncMock()
        await _write_aggregate(mock_conn, "pokemon", "charizard-base", {"brand": {"value": "WOTC"}})
        call_args = mock_conn.execute.call_args
        sql = call_args[0][0]
        assert "jsonb_set" in sql
        assert "||" not in sql
