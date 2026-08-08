"""Tests for production hardening features:
- Data moat REST endpoints and demand signal wiring
- Valuation worker confidence scores and temporal decay
- Trust score computation from real offer data
- Alert rate limiting per user
- Policy engine recency from discovered_at
- Model loader cache TTL
- Calibration worker batch pattern
"""

import inspect
import re
import math
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


# ---------------------------------------------------------------------------
# Package 1: Data Moat Endpoints
# ---------------------------------------------------------------------------

class TestDataMoatEndpoints:
    """Tests for data moat REST API surface."""

    def test_router_exists(self):
        from app.features.data_moat import router
        routes = [r.path for r in router.routes]
        assert any("supply-trends" in r for r in routes)
        assert any("demand-heat" in r for r in routes)
        assert any("health" in r for r in routes)

    def test_data_moat_registered_in_main(self):
        import inspect
        import main
        src = inspect.getsource(main)
        assert "data_moat.router" in src


# ---------------------------------------------------------------------------
# Demand-signal wiring — resolved through the call graph, not by grepping one
# function body.
#
# 2026-07-27: five of these tests were failing because the instrumentation had
# been REFACTORED INTO HELPERS, not removed. `get_category_deep_dive` calls
# `spawn_bg(_record_category_view(...))`; `add_to_watchlist` calls
# `_record_watchlist_demand(...)`; search signals moved to
# `search_router.unified_search`. Verified against prod before touching these:
# demand_signals holds 164 rows across 11 signal types, including
# watchlist_add (25), search_query (22) and category_viewed — so the feature
# was healthy and the assertions were stale.
#
# `inspect.getsource(fn)` + substring is the wrong instrument for "is this
# wired": it fails on a pure refactor and would equally pass on a helper that
# is defined but never called. This walks one level of the module's own call
# graph instead — still fails if the wiring is genuinely deleted, no longer
# fails when it merely moves.
# ---------------------------------------------------------------------------

def _records_demand_signal(module_name: str, func_name: str) -> bool:
    """True if `func_name` records a demand signal, directly or via a helper
    defined in the same module that it actually calls."""
    mod = __import__(module_name, fromlist=[func_name])
    fn = getattr(mod, func_name)
    src = inspect.getsource(fn)
    if "record_demand_signal" in src:
        return True

    module_src = inspect.getsource(mod)
    for helper in re.findall(r"^(?:async )?def (_\w+)", module_src, re.M):
        # The helper must be BOTH referenced by the route and itself record.
        if helper not in src:
            continue
        m = re.search(
            rf"^(?:async )?def {helper}\b.*?(?=^(?:async )?def |\Z)",
            module_src,
            re.M | re.S,
        )
        if m and "record_demand_signal" in m.group(0):
            return True
    return False


class TestDemandSignalWiring:
    """Verify demand signals are wired into search, watchlist, and alerts."""

    def test_search_records_a_search_query_signal(self):
        """Search demand is recorded by search_router.unified_search.

        It is NOT in marketplace_router.marketplace_search, which is what
        this used to assert. Prod carries 22 `search_query` rows, so the
        signal fires — from the unified search route.
        """
        assert _records_demand_signal("app.features.search_router", "unified_search")
        src = inspect.getsource(
            __import__("app.features.search_router", fromlist=["unified_search"]).unified_search
        )
        assert "search_query" in src

    def test_watchlist_add_records_signal(self):
        """Via the _record_watchlist_demand helper (prod: 25 watchlist_add rows)."""
        assert _records_demand_signal("app.features.watchlist_router", "add_to_watchlist")

    def test_unified_search_records_signal(self):
        src = inspect.getsource(
            __import__("app.features.search_router", fromlist=["unified_search"]).unified_search
        )
        assert "record_demand_signal" in src
        assert "search_query" in src

    def test_alert_creation_records_signal(self):
        src = inspect.getsource(
            __import__(
                "app.features.alerts_feature_router",
                fromlist=["create_or_update_alert"],
            ).create_or_update_alert
        )
        assert "record_demand_signal" in src
        assert "price_alert_set" in src


# ---------------------------------------------------------------------------
# Package 2: Valuation Worker — Confidence Score & Temporal Decay
# ---------------------------------------------------------------------------

class TestConfidenceScore:
    """Tests for confidence_score formula."""

    def test_high_confidence_many_recent_diverse_sources(self):
        """Many recent hits from diverse sources → confidence near 1.0."""
        # 10 hits, 3 sources, all very recent (weight ≈ 1.0)
        n = 10
        unique_sources = 3
        avg_weight = 0.95

        source_diversity = min(1.0, unique_sources / 3)  # 1.0
        source_count_factor = min(1.0, n / 5)  # 1.0
        recency_factor = min(1.0, avg_weight)  # 0.95

        conf = source_count_factor * source_diversity * recency_factor
        assert conf >= 0.90

    def test_low_confidence_few_old_single_source(self):
        """Few old hits from single source → low confidence."""
        n = 2
        unique_sources = 1
        avg_weight = 0.3

        source_diversity = min(1.0, unique_sources / 3)  # 0.33
        source_count_factor = min(1.0, n / 5)  # 0.4
        recency_factor = min(1.0, avg_weight)  # 0.3

        conf = source_count_factor * source_diversity * recency_factor
        assert conf < 0.10

    def test_confidence_caps_at_1(self):
        """Confidence should never exceed 1.0."""
        n = 100
        unique_sources = 10
        avg_weight = 1.0

        source_diversity = min(1.0, unique_sources / 3)
        source_count_factor = min(1.0, n / 5)
        recency_factor = min(1.0, avg_weight)

        conf = source_count_factor * source_diversity * recency_factor
        assert conf <= 1.0


class TestTemporalDecay:
    """Tests for exponential temporal decay weighting."""

    def test_recent_listing_high_weight(self):
        """A listing from today should have weight ≈ 1.0."""
        days_old = 0
        half_life = 30.0
        weight = math.exp(-days_old / half_life)
        assert weight >= 0.99

    def test_30_day_old_half_weight(self):
        """A listing from 30 days ago should have weight ≈ 0.37 (e^-1)."""
        days_old = 30
        half_life = 30.0
        weight = math.exp(-days_old / half_life)
        assert 0.35 <= weight <= 0.40

    def test_60_day_old_very_low_weight(self):
        """A listing from 60 days ago should have weight ≈ 0.14 (e^-2)."""
        days_old = 60
        half_life = 30.0
        weight = math.exp(-days_old / half_life)
        assert weight < 0.15

    def test_valuation_worker_has_temporal_decay(self):
        """Verify valuation_worker.py uses temporal decay."""
        import workers.valuation_worker as vw
        src = inspect.getsource(vw.run_once)
        assert "math.exp" in src or "_DECAY_HALF_LIFE" in src
        assert "weighted_quantile" in src


class TestValuationModelBlending:
    """Ridge model blending in the valuation worker.

    Repointed 2026-07-27: `_predict_ridge` was renamed `_predict_quantile`
    and its second argument became a feature dict rather than an item_ref
    plus a raw price. These three had been dead with ImportError since.
    """

    def test_predict_quantile_basic(self):
        from workers.valuation_worker import _predict_quantile
        model = {
            "features": ["price"],
            "standardizer": {"mean": [100.0], "std": [50.0]},
            "ridge": {"coef": [1.0], "intercept": 100.0},
        }
        result = _predict_quantile(model, {"price": 150.0}, "ridge")
        assert result is not None
        assert result > 0

    def test_predict_quantile_mismatched_dimensions(self):
        """An older artifact's standardizer vs a newer feature list."""
        from workers.valuation_worker import _predict_quantile
        model = {
            "features": ["price", "condition"],
            "standardizer": {"mean": [100.0], "std": [50.0]},  # wrong dimension
            "ridge": {"coef": [1.0, 0.5], "intercept": 100.0},
        }
        result = _predict_quantile(model, {"price": 150.0, "condition": 0.8}, "ridge")
        assert result is None  # skip the model; empirical wins

    def test_predict_quantile_zero_std(self):
        """A feature constant in training must be ignored, not divide by zero."""
        from workers.valuation_worker import _predict_quantile
        model = {
            "features": ["price"],
            "standardizer": {"mean": [100.0], "std": [0.0]},
            "ridge": {"coef": [1.0], "intercept": 100.0},
        }
        result = _predict_quantile(model, {"price": 150.0}, "ridge")
        assert result is not None
        assert result == 100.0  # intercept only


# ---------------------------------------------------------------------------
# Package 3: Worker Hardening
# ---------------------------------------------------------------------------

class TestAlertRateLimiting:
    """Tests for per-user alert caps in price_monitor_worker."""

    def test_max_alerts_per_user_constant_exists(self):
        import workers.price_monitor_worker as pmw
        assert hasattr(pmw, "MAX_ALERTS_PER_USER")
        assert pmw.MAX_ALERTS_PER_USER > 0

    def test_threshold_alerts_has_per_user_tracking(self):
        import workers.price_monitor_worker as pmw
        src = inspect.getsource(pmw.check_threshold_alerts)
        assert "alerts_per_user" in src
        assert "MAX_ALERTS_PER_USER" in src

    def test_anomaly_detection_has_per_user_tracking(self):
        import workers.price_monitor_worker as pmw
        src = inspect.getsource(pmw.detect_anomalies)
        assert "anomaly_alerts_per_user" in src
        assert "MAX_ALERTS_PER_USER" in src


class TestCalibrationBatch:
    """Tests for calibration worker N+1 fix."""

    def test_calibration_uses_batch_query(self):
        """Verify calibration worker uses ANY($1) batch query."""
        import workers.calibration_worker as cw
        src = inspect.getsource(cw.run_once)
        assert "ANY($1)" in src
        assert "actuals_by_key" in src

    def test_calibration_no_per_prediction_query(self):
        """Verify there's no per-prediction inner query loop."""
        import workers.calibration_worker as cw
        src = inspect.getsource(cw.run_once)
        # The old N+1 pattern had a query inside `for pred in predictions:`
        # Now the actuals fetch happens BEFORE the prediction loop
        lines = src.split("\n")
        batch_idx = None
        pred_loop_idx = None
        for i, line in enumerate(lines):
            if "ANY($1)" in line:
                batch_idx = i
            if "for pred in predictions:" in line:
                pred_loop_idx = i
        assert batch_idx is not None
        assert pred_loop_idx is not None
        assert batch_idx < pred_loop_idx  # Batch query before the loop


class TestPolicyEngineRecency:
    """Tests for policy engine recency_score from discovered_at."""

    def test_recent_listing_high_recency(self):
        from app.agents.policy_engine import evaluate
        now = datetime.now(timezone.utc)
        mandate = {"max_price": 100, "min_trust_score": 0}
        hit = {
            "price": 50,
            "provenance_score": 0.9,
            "discovered_at": now.isoformat(),
        }
        prediction = {"q50": 80}
        verdict = evaluate(mandate, hit, prediction)
        # Recency should be near 1.0 for a just-discovered listing
        assert verdict.deal_score > 0

    def test_old_listing_low_recency(self):
        from app.agents.policy_engine import evaluate
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        mandate = {"max_price": 100, "min_trust_score": 0}
        hit = {
            "price": 50,
            "provenance_score": 0.9,
            "discovered_at": old,
        }
        prediction = {"q50": 80}
        verdict = evaluate(mandate, hit, prediction)
        # 60 days old → recency should be 0 (max(0, 1-60/30) = 0)
        assert verdict.passed

    def test_no_discovered_at_fallback(self):
        from app.agents.policy_engine import evaluate
        mandate = {"max_price": 100, "min_trust_score": 0}
        hit = {
            "price": 50,
            "provenance_score": 0.9,
        }
        verdict = evaluate(mandate, hit)
        # Should still work with 0.5 baseline
        assert verdict.passed


# ---------------------------------------------------------------------------
# Package 4: Trust Wiring (was marketplace_trust_router -> deal_desk_router;
# Deal Desk removed 2026-08-09, member trust now lives in p2p_offers_router
# via member_grades)
# ---------------------------------------------------------------------------

# _compute_badge tests removed — marketplace_trust_router was deleted
# after merging trust logic into the offers router. Badge computation
# is tested via the P2P member-grade endpoints.


class TestStubRoutersRemoved:
    """Verify stub routers are removed from main.py."""

    def test_no_stub_imports_in_main(self):
        src = inspect.getsource(__import__("main"))
        assert "spool_ui" not in src
        assert "vision_ops" not in src
        assert "vision_ingest" not in src
        assert "spool_ops" not in src
        assert "manifests_router" not in src
        # ops_router is also removed
        assert "from app.routes.ops import" not in src

    def test_stub_files_deleted(self):
        base = Path(__file__).resolve().parent.parent / "app" / "routes"
        assert not (base / "vision_ops.py").exists()
        assert not (base / "spool_ui.py").exists()
        assert not (base / "manifests.py").exists()
        assert not (base / "vision_ingest.py").exists()
        assert not (base / "spool_ops.py").exists()
        assert not (base / "ops.py").exists()


class TestRareSetAlerts:
    """Verify rare-set alerts are wired."""

    def test_rare_set_alerts_are_deliberately_disabled(self):
        """The near-complete-set query was removed ON PURPOSE, 2026-07-24.

        Rewritten 2026-07-27. This used to assert the `set_registry` query
        and its 0.80 threshold were present. They were deleted deliberately:
        the block ran one `items` query per row of set_registry on every
        call — an N+1 — and only ever emits an alert when a user owns
        80-99% of a registered set, so on real data it did all that work to
        return an empty list every time.

        The response FIELD is kept (always []) so no client contract
        changed. Asserting the deleted code back would be pinning a
        performance bug. This pins the decision instead: the field exists
        and the expensive query does not.
        """
        import app.features.insights_router as ir

        src = inspect.getsource(ir.get_personalized_insights)
        assert "rare_set_alerts=" in src, "response field must stay for clients"
        assert "DISABLED 2026-07-24" in src, "the rationale must stay with the code"
        # The alerts are a constant empty list, not the result of a query.
        # (The comment above them still names set_registry — that IS the
        # rationale and must stay, so grepping the source for the table name
        # would assert the wrong thing.)
        assert re.search(r"rare_alerts:\s*List\[RareSetAlert\]\s*=\s*\[\]", src), (
            "rare_set_alerts must be a constant [], not a re-added N+1 query"
        )


# ---------------------------------------------------------------------------
# Package 5: Monitoring & Observability
# ---------------------------------------------------------------------------

class TestModelLoaderCacheTTL:
    """Tests for model cache TTL and max size."""

    def test_cache_ttl_constant(self):
        from app.ml.model_loader import CACHE_TTL, MAX_CACHE_SIZE
        assert CACHE_TTL == 3600
        assert MAX_CACHE_SIZE == 100

    def test_stale_cache_entry_evicted(self):
        from app.ml.model_loader import _get_cached_model, _set_cached_model, _model_cache

        # Set a model with old timestamp
        _model_cache["test_stale"] = {
            "model_type": "test",
            "_cached_at": time.time() - 7200,  # 2 hours ago
        }

        result = _get_cached_model("test_stale")
        assert result is None  # Should be evicted due to TTL
        assert "test_stale" not in _model_cache

    def test_fresh_cache_entry_returned(self):
        from app.ml.model_loader import _get_cached_model, _set_cached_model, _model_cache

        _set_cached_model("test_fresh", {"model_type": "test"})
        result = _get_cached_model("test_fresh")
        assert result is not None
        assert result["model_type"] == "test"

        # Clean up
        _model_cache.pop("test_fresh", None)

    def test_cache_eviction_at_max_size(self):
        from app.ml.model_loader import _set_cached_model, _model_cache, MAX_CACHE_SIZE

        # Clear existing cache
        original = dict(_model_cache)
        _model_cache.clear()

        # Fill cache to max
        for i in range(MAX_CACHE_SIZE):
            _set_cached_model(f"cat_{i}", {"model_type": f"model_{i}"})

        assert len(_model_cache) == MAX_CACHE_SIZE

        # Add one more — should evict oldest
        _set_cached_model("overflow_cat", {"model_type": "overflow"})
        assert len(_model_cache) == MAX_CACHE_SIZE
        assert "overflow_cat" in _model_cache

        # Restore
        _model_cache.clear()
        _model_cache.update(original)


class TestWorkerRegistryPersistence:
    """Tests for worker registry DB persistence."""

    def test_record_run_calls_persist(self):
        from app.worker_registry import record_run, _registry

        # Clear registry to test
        _registry.pop("test_persist", None)
        record_run("test_persist", "ok")

        assert "test_persist" in _registry
        assert _registry["test_persist"]["runs"] == 1
        assert _registry["test_persist"]["last_status"] == "ok"

        # Clean up
        _registry.pop("test_persist", None)

    def test_persist_function_exists(self):
        from app.worker_registry import _persist_run_to_db
        assert callable(_persist_run_to_db)


class TestAdapterHealthEndpoint:
    """Tests for the combined adapter health endpoint."""

    def test_adapter_health_endpoint_registered(self):
        from app.agents.marketplace_router import router
        routes = [r.path for r in router.routes]
        assert any("adapter-health" in r for r in routes)


class TestCanaryStatus:
    """Tests for canary deployment status endpoint."""

    def test_ops_canary_status_registered(self):
        import inspect
        import main
        src = inspect.getsource(main)
        assert "canary-status" in src or "canary_status" in src

    @pytest.mark.asyncio
    async def test_get_canary_status_no_db(self):
        from app.ml.model_loader import get_canary_status
        result = await get_canary_status()
        assert "canary_traffic_pct" in result
        assert "production_models" in result
        assert "canary_models" in result
        assert "calibration" in result


# ---------------------------------------------------------------------------
# Data Moat Strengthening: Split Refresh & Extended Signals
# ---------------------------------------------------------------------------

class TestSplitRefreshIntervals:
    """Tests for independent matview refresh intervals."""

    def test_demand_interval_default_10min(self):
        import workers.matview_refresh_worker as mw
        # Default should be 600s (10 min) unless legacy env var overrides
        assert hasattr(mw, "DEMAND_INTERVAL")
        assert mw.DEMAND_INTERVAL <= 600 or os.getenv("MATVIEW_REFRESH_INTERVAL")

    def test_supply_interval_default_60min(self):
        import workers.matview_refresh_worker as mw
        assert hasattr(mw, "SUPPLY_INTERVAL")
        assert mw.SUPPLY_INTERVAL <= 3600 or os.getenv("MATVIEW_REFRESH_INTERVAL")

    def test_independent_loops_exist(self):
        import workers.matview_refresh_worker as mw
        assert hasattr(mw, "_demand_loop")
        assert hasattr(mw, "_supply_loop")
        assert callable(mw._demand_loop)
        assert callable(mw._supply_loop)

    def test_scheduler_loop_uses_gather(self):
        import workers.matview_refresh_worker as mw
        src = inspect.getsource(mw.scheduler_loop)
        assert "gather" in src
        assert "_demand_loop" in src
        assert "_supply_loop" in src

    def test_worker_registry_has_split_schedules(self):
        from app.worker_registry import SCHEDULES
        assert "matview_demand" in SCHEDULES
        assert "matview_supply" in SCHEDULES
        assert SCHEDULES["matview_demand"] == 600
        assert SCHEDULES["matview_supply"] == 1800


class TestExtendedSignalTypes:
    """Tests for expanded demand signal type whitelist."""

    def test_new_signal_types_in_whitelist(self):
        src = inspect.getsource(
            __import__("app.features.data_moat", fromlist=["record_demand_signal"]).record_demand_signal
        )
        for sig_type in ("item_scanned", "item_added", "catalog_browsed",
                         "category_viewed", "collection_viewed"):
            assert sig_type in src, f"Missing signal type: {sig_type}"


class TestNewSignalWiring:
    """Tests for demand signal wiring in newly instrumented endpoints."""

    def test_dossier_records_item_viewed(self):
        src = inspect.getsource(
            __import__("app.agents.dossier_router", fromlist=["get_dossier"]).get_dossier
        )
        assert "record_demand_signal" in src
        assert "item_viewed" in src

    def test_intake_process_records_item_scanned(self):
        src = inspect.getsource(
            __import__("app.agents.intake_router", fromlist=["intake_process"]).intake_process
        )
        assert "record_demand_signal" in src
        assert "item_scanned" in src

    def test_intake_barcode_records_item_scanned(self):
        src = inspect.getsource(
            __import__("app.agents.intake_router", fromlist=["intake_barcode_only"]).intake_barcode_only
        )
        assert "record_demand_signal" in src
        assert "item_scanned" in src

    def test_intake_image_records_item_scanned(self):
        src = inspect.getsource(
            __import__("app.agents.intake_router", fromlist=["intake_image_only"]).intake_image_only
        )
        assert "record_demand_signal" in src
        assert "item_scanned" in src

    def test_intake_save_records_item_added(self):
        src = inspect.getsource(
            __import__("app.agents.intake_router", fromlist=["intake_save"]).intake_save
        )
        assert "record_demand_signal" in src
        assert "item_added" in src

    def test_catalog_browse_records_catalog_browsed(self):
        src = inspect.getsource(
            __import__("app.features.catalog_browser_router", fromlist=["browse_catalog_items"]).browse_catalog_items
        )
        assert "record_demand_signal" in src
        assert "catalog_browsed" in src

    def test_collection_viewed_is_declared_but_deliberately_unwired(self):
        """`collection_viewed` has no writer, and that is correct today.

        Rewritten 2026-07-27. This used to assert that
        `get_collection_detail` records the signal. It does not, and it
        must not: that route is a STUB which raises 404 on every call
        ("Catalog-of-sets aggregation not built"), as does
        get_collection_progress. Instrumenting an endpoint that never
        succeeds would only produce a signal that can never fire.

        The type IS declared in data_moat's allowlist and documented, so
        this pins the gap rather than hiding it — when the catalog-of-sets
        feature ships, this test should flip to asserting the wiring.
        """
        from app.features import data_moat

        allow_src = inspect.getsource(data_moat)
        assert "collection_viewed" in allow_src, "signal type should stay declared"

        src = inspect.getsource(
            __import__("app.features.collections_router", fromlist=["get_collection_detail"]).get_collection_detail
        )
        assert "Collection not found" in src, "route is still a stub"
        assert "record_demand_signal" not in src

    def test_category_deepdive_records_category_viewed(self):
        """Via the _record_category_view helper, spawned with spawn_bg.

        Prod carries `category_viewed` rows, so the signal fires; the old
        assertion just grepped the route body, which no longer contains
        the literal call after the helper extraction.
        """
        assert _records_demand_signal(
            "app.features.trends_and_deepdive_router", "get_category_deep_dive"
        )

    def test_price_evidence_records_item_viewed(self):
        src = inspect.getsource(
            __import__("app.features.predict_router", fromlist=["get_price_evidence"]).get_price_evidence
        )
        assert "record_demand_signal" in src
        assert "item_viewed" in src


# ---------------------------------------------------------------------------
# Feature 2: Price Accuracy Feedback Loop
# ---------------------------------------------------------------------------

class TestPriceFeedbackLoop:
    """Tests for ground truth recording from completed deals."""

    def test_record_price_ground_truth_function_exists(self):
        from app.features.data_moat import record_price_ground_truth
        assert callable(record_price_ground_truth)

    @pytest.mark.asyncio
    async def test_record_ground_truth_no_db(self):
        from app.features.data_moat import record_price_ground_truth
        result = await record_price_ground_truth(
            item_id="00000000-0000-0000-0000-000000000001",
            actual_price=42.50,
            currency="EUR",
        )
        assert result is False  # No DB pool in test

    def test_complete_deal_wires_ground_truth(self):
        """A completed trade must feed its agreed price back as a sold comp.

        Repointed 2026-08-09 from `app.agents.deal_completion.execute_complete`
        to the P2P confirmation path. Deal Desk was removed (0 rows, never
        shipped — `SELLING_ENABLED=false`), but the GUARANTEE it was asserting
        is not Deal Desk's, it is the marketplace's: a two-sided confirmed price
        is the only sold-comp source we have for the ~62k catalogue items eBay
        cannot price, so losing this wiring would silently starve
        valuation_worker.

        The mechanism changed name — `record_price_ground_truth(actual_price)`
        became `_sold_comp_hook(listing_id, amount, currency)` — so the test
        asserts the new one. It must keep failing if the hook is dropped.
        """
        src = inspect.getsource(
            __import__(
                "app.features.p2p_offers_router", fromlist=["confirm_exchange"]
            ).confirm_exchange
        )
        assert "_sold_comp_hook" in src, "completion no longer records a sold comp"
        # The AGREED figure, not the asking price. Passing the listing price
        # here would poison every comp with the pre-negotiation number.
        assert 'fresh["amount"]' in src, "sold comp is not fed the agreed amount"

    def test_prediction_accuracy_endpoint_exists(self):
        from app.features.data_moat import router
        routes = [r.path for r in router.routes]
        assert any("prediction-accuracy" in r for r in routes)


# ---------------------------------------------------------------------------
# Feature 3: Scarcity Detection
# ---------------------------------------------------------------------------

class TestScarcityDetection:
    """Tests for supply-down + demand-up scarcity detection."""

    def test_detect_scarcity_function_exists(self):
        from app.features.data_moat import detect_scarcity
        assert callable(detect_scarcity)

    @pytest.mark.asyncio
    async def test_detect_scarcity_no_db(self):
        from app.features.data_moat import detect_scarcity
        result = await detect_scarcity()
        assert result == []  # No DB pool in test

    def test_scarcity_endpoint_exists(self):
        from app.features.data_moat import router
        routes = [r.path for r in router.routes]
        assert any("scarcity" in r for r in routes)

    def test_scarcity_score_formula(self):
        """Scarcity score = demand_growth * supply_decline (both > 0)."""
        demand_growth = 1.5  # 150% more searches
        supply_decline = 0.4  # 40% fewer listings
        score = max(0, demand_growth) * max(0, supply_decline)
        assert score == pytest.approx(0.6, abs=0.01)

    def test_scarcity_score_zero_when_no_decline(self):
        """No scarcity if supply is stable or growing."""
        demand_growth = 2.0
        supply_decline = -0.1  # Supply grew 10%
        score = max(0, demand_growth) * max(0, supply_decline)
        assert score == 0.0


# ---------------------------------------------------------------------------
# Feature 4: Geographic Demand Segmentation
# ---------------------------------------------------------------------------

class TestGeoDemandSegmentation:
    """Tests for geographic demand signal enrichment."""

    def test_record_demand_signal_accepts_geo_params(self):
        src = inspect.getsource(
            __import__("app.features.data_moat", fromlist=["record_demand_signal"]).record_demand_signal
        )
        assert "region" in src
        assert "country_code" in src

    def test_get_user_geo_function_exists(self):
        from app.features.data_moat import get_user_geo
        assert callable(get_user_geo)

    @pytest.mark.asyncio
    async def test_get_user_geo_no_db(self):
        from app.features.data_moat import get_user_geo
        region, country = await get_user_geo("some-user-id")
        assert region is None
        assert country is None

    @pytest.mark.asyncio
    async def test_get_user_geo_none_user(self):
        from app.features.data_moat import get_user_geo
        region, country = await get_user_geo(None)
        assert region is None
        assert country is None

    def test_demand_heat_by_region_endpoint_exists(self):
        from app.features.data_moat import router
        routes = [r.path for r in router.routes]
        assert any("by-region" in r for r in routes)

    def test_search_enriches_demand_signals_with_geo(self):
        """Geo enrichment lives with the search signal, in search_router.

        Repointed 2026-07-27: this asserted `marketplace_router.
        marketplace_search`, which records no demand signal at all — so
        there is nothing there to enrich. `unified_search` is the route
        that writes `search_query`, and it is where get_user_geo is
        called. Verified against prod: demand_signals rows carry region /
        country_code.
        """
        src = inspect.getsource(
            __import__("app.features.search_router", fromlist=["unified_search"]).unified_search
        )
        # Assert the CALL, not the mention. `"get_user_geo" in src` also
        # matches the import line, so it survived a mutation that replaced
        # the call with `region, country = (None, None)` — caught by
        # mutation-testing this file rather than by it passing.
        assert re.search(r"await\s+get_user_geo\s*\(", src), "geo lookup must actually run"
        assert re.search(r"region\s*=\s*region|region=region", src), "region must reach the signal"

    def test_migration_adds_geo_columns(self):
        """Verify the migration file exists and adds region/country_code."""
        migration = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations" / "20260228_data_moat_v2.sql"
        assert migration.exists()
        content = migration.read_text()
        assert "region" in content
        assert "country_code" in content
        assert "price_ground_truths" in content
