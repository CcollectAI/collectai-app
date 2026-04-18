"""Tests for R50l hardening code: spend tracker DB wiring, JSONB repair
logic, and the valuation clamp.

These cover the three new code paths that would have caught today's audit
findings if they'd been tested up-front."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")


# ---------------------------------------------------------------------------
# repair_attributes_json_types — _repair_value covers the 3 corruption shapes
# ---------------------------------------------------------------------------

class TestRepairValue:
    def test_dict_is_passed_through(self):
        from scripts.repair_attributes_json_types import _repair_value
        d = {"set": "Modern Horizons", "rarity": "mythic"}
        assert _repair_value(d) == d

    def test_json_string_decoded_to_dict(self):
        from scripts.repair_attributes_json_types import _repair_value
        raw = json.dumps({"theme": "Star Wars", "year": 2024})
        assert _repair_value(raw) == {"theme": "Star Wars", "year": 2024}

    def test_double_stringified_json(self):
        """R50d notes_parser wrote json.dumps(json.dumps(dict)) in many rows."""
        from scripts.repair_attributes_json_types import _repair_value
        inner = json.dumps({"brand": "Nike"})
        raw = json.dumps(inner)  # becomes a JSONB string literal
        assert _repair_value(raw) == {"brand": "Nike"}

    def test_raw_jsonb_array_of_string(self):
        """asyncpg returns jsonb arrays-of-strings as a raw JSON text."""
        from scripts.repair_attributes_json_types import _repair_value
        # Shape we saw in prod: a JSONB array whose single element is a JSON string of a dict
        raw = json.dumps([json.dumps({"set_number": "40716-1", "theme": "Other", "year": "2024"})])
        result = _repair_value(raw)
        assert result == {"set_number": "40716-1", "theme": "Other", "year": "2024"}

    def test_array_with_multiple_dicts_shallow_merged(self):
        from scripts.repair_attributes_json_types import _repair_value
        raw = json.dumps([
            json.dumps({"a": 1, "b": 2}),
            json.dumps({"b": 99, "c": 3}),
        ])
        result = _repair_value(raw)
        # last writer wins on key conflicts
        assert result == {"a": 1, "b": 99, "c": 3}

    def test_none_returns_none(self):
        from scripts.repair_attributes_json_types import _repair_value
        assert _repair_value(None) is None

    def test_garbage_returns_none(self):
        from scripts.repair_attributes_json_types import _repair_value
        assert _repair_value("not json at all") is None
        assert _repair_value("{broken") is None

    def test_empty_dict_passes_through(self):
        from scripts.repair_attributes_json_types import _repair_value
        assert _repair_value({}) == {}

    def test_empty_array_returns_none(self):
        from scripts.repair_attributes_json_types import _repair_value
        assert _repair_value(json.dumps([])) is None


# ---------------------------------------------------------------------------
# valuation_worker._predict_ridge — clamp rejects absurd outputs
# ---------------------------------------------------------------------------

class TestRidgeClamp:
    def test_normal_prediction_returns_float(self):
        from workers.valuation_worker import _predict_ridge
        model = {
            "features": ["price"],
            "standardizer": {"mean": [100.0], "std": [50.0]},
            "ridge": {"coef": [1.0], "intercept": 100.0},
        }
        assert _predict_ridge(model, "pokemon:charizard", 150.0) == pytest.approx(101.0)

    def test_absurd_prediction_returns_none(self):
        """Lego-class blow-up: intercept drives prediction to €1.5B."""
        from workers.valuation_worker import _predict_ridge, _MAX_SANE_PRICE_EUR
        assert _MAX_SANE_PRICE_EUR == 20_000_000.0
        model = {
            "features": ["price"],
            "standardizer": {"mean": [100.0], "std": [50.0]},
            "ridge": {"coef": [0.0], "intercept": 1_500_000_000.0},
        }
        # Intercept alone is €1.5B → should be clamped
        assert _predict_ridge(model, "lego:foo", 150.0) is None

    def test_log_scale_expm1_blowup_is_clamped(self):
        """Log-space intercept of 21 expm1s to ~1.3B — must clamp."""
        from workers.valuation_worker import _predict_ridge
        model = {
            "log_scale": True,
            "features": ["price"],
            "standardizer": {"mean": [100.0], "std": [50.0]},
            "ridge": {"coef": [0.0], "intercept": 21.0},
        }
        assert _predict_ridge(model, "lego:foo", 100.0) is None

    def test_log_scale_reasonable_returns_float(self):
        """log1p(50) ~= 3.93 — normal log-scale model output decodes to ~€50."""
        import math
        from workers.valuation_worker import _predict_ridge
        model = {
            "log_scale": True,
            "features": ["price"],
            "standardizer": {"mean": [math.log1p(100.0)], "std": [1.0]},
            "ridge": {"coef": [0.0], "intercept": math.log1p(50.0)},
        }
        result = _predict_ridge(model, "retro:foo", 100.0)
        assert result is not None
        assert 40 < result < 60

    def test_negative_prediction_returns_none(self):
        from workers.valuation_worker import _predict_ridge
        model = {
            "features": ["price"],
            "standardizer": {"mean": [100.0], "std": [50.0]},
            "ridge": {"coef": [-10.0], "intercept": -1000.0},
        }
        assert _predict_ridge(model, "x:y", 50.0) is None

    def test_nan_prediction_returns_none(self):
        """Feature NaN + intercept NaN → NaN prediction → None."""
        from workers.valuation_worker import _predict_ridge
        model = {
            "features": ["price"],
            "standardizer": {"mean": [float("nan")], "std": [50.0]},
            "ridge": {"coef": [1.0], "intercept": float("nan")},
        }
        assert _predict_ridge(model, "x:y", 100.0) is None


# ---------------------------------------------------------------------------
# spend_tracker — hydrate_from_db + _persist_event path
# ---------------------------------------------------------------------------

class TestSpendTrackerDbWiring:
    def test_record_accumulates_in_memory(self):
        from app.lib.spend_tracker import SpendTracker
        t = SpendTracker(monthly_budget_eur=10.0)
        t.reset()
        t.record("openai", cost_eur=0.01)
        t.record("openai", cost_eur=0.02)
        t.record("firecrawl", cost_eur=0.005)
        assert t.total_spent == pytest.approx(0.035)
        assert t._provider_calls == {"openai": 2, "firecrawl": 1}

    def test_budget_breach_raises(self):
        from app.lib.spend_tracker import SpendTracker, BudgetExceededError
        t = SpendTracker(monthly_budget_eur=0.01)
        t.reset()
        t.record("openai", cost_eur=0.02)
        with pytest.raises(BudgetExceededError):
            t.check("openai")

    @pytest.mark.asyncio
    async def test_hydrate_noop_when_no_pool(self, monkeypatch):
        from app.lib.spend_tracker import SpendTracker
        from app.lib import db_helpers
        monkeypatch.setattr(db_helpers, "get_db_pool", lambda: None)
        t = SpendTracker(monthly_budget_eur=10.0)
        t.reset()
        await t.hydrate_from_db()  # should not raise
        assert t.total_spent == 0.0

    @pytest.mark.asyncio
    async def test_hydrate_populates_from_rows(self, monkeypatch):
        from app.lib.spend_tracker import SpendTracker
        from app.lib import db_helpers

        fake_rows = [
            {"provider": "openai", "spent": 0.42, "n": 3},
            {"provider": "firecrawl", "spent": 0.12, "n": 1},
        ]
        fake_conn = AsyncMock()
        fake_conn.fetch = AsyncMock(return_value=fake_rows)
        fake_pool = MagicMock()
        fake_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=fake_conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        monkeypatch.setattr(db_helpers, "get_db_pool", lambda: fake_pool)

        t = SpendTracker(monthly_budget_eur=10.0)
        t.reset()
        await t.hydrate_from_db()
        assert t.total_spent == pytest.approx(0.54)
        assert t._provider_calls["openai"] == 3
        assert t._provider_calls["firecrawl"] == 1

    def test_persist_event_silent_on_no_pool(self, monkeypatch):
        """_persist_event must never raise — caller should not see DB errors."""
        from app.lib.spend_tracker import SpendTracker
        from app.lib import db_helpers
        monkeypatch.setattr(db_helpers, "get_db_pool", lambda: None)
        t = SpendTracker(monthly_budget_eur=10.0)
        t.reset()
        # record() calls _persist_event internally; must not raise
        t.record("openai", cost_eur=0.005)
        assert t.total_spent == 0.005
