"""Tests for app.ml.model_loader — ML model loading, caching, and canary routing."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# We patch config values at import time via the module reference
import app.ml.model_loader as ml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear model caches before and after each test.

    `_REGISTRY_SCHEMA_OK` is reset too: it is a MODULE GLOBAL memoising one
    `information_schema` probe, so the first test whose mock conn cannot
    answer that probe pins it False for the entire session — every later test
    then gets None out of `_fetch_model_registry_entry` regardless of what it
    mocked. Two tests in this file were passing for exactly that reason
    rather than for the reason they claim.
    """
    ml._model_cache.clear()
    ml._canary_cache.clear()
    ml._REGISTRY_SCHEMA_OK = None
    yield
    ml._model_cache.clear()
    ml._canary_cache.clear()
    ml._REGISTRY_SCHEMA_OK = None


def _make_registry_entry(
    category: str = "watches",
    model_type: str = "ridge_v2",
    artifact_json: dict | str | None = None,
    s3_key: str | None = None,
    is_canary: bool = False,
    uncertainty_scale: float | None = 1.2,
) -> dict:
    """Build a fake model_registry row dict."""
    return {
        "id": 42,
        "category": category,
        "model_type": model_type,
        "s3_key": s3_key,
        "artifact_json": artifact_json,
        "uncertainty_scale": uncertainty_scale,
        "is_active": True,
        "is_canary": is_canary,
        "created_at": "2026-03-20T00:00:00Z",
    }


SAMPLE_ARTIFACT = {
    "model_type": "ridge_v2",
    "features": ["condition", "rarity", "age"],
    "standardizer": {"mean": [1.0, 2.0, 3.0], "std": [0.5, 1.0, 1.5]},
    "ridge": {"coef": [0.1, 0.2, 0.3], "intercept": 5.0},
}


# ---------------------------------------------------------------------------
# _get_cached_model / _set_cached_model
# ---------------------------------------------------------------------------

class TestCaching:
    def test_cache_miss_returns_none(self):
        assert ml._get_cached_model("watches") is None

    def test_set_then_get_returns_artifact(self):
        art = {**SAMPLE_ARTIFACT}
        ml._set_cached_model("watches", art)
        cached = ml._get_cached_model("watches")
        assert cached is not None
        assert cached["model_type"] == "ridge_v2"

    def test_canary_cache_separate_from_production(self):
        prod = {**SAMPLE_ARTIFACT, "label": "prod"}
        canary = {**SAMPLE_ARTIFACT, "label": "canary"}
        ml._set_cached_model("watches", prod, is_canary=False)
        ml._set_cached_model("watches", canary, is_canary=True)

        assert ml._get_cached_model("watches", is_canary=False)["label"] == "prod"
        assert ml._get_cached_model("watches", is_canary=True)["label"] == "canary"

    def test_cache_ttl_expiry(self):
        art = {**SAMPLE_ARTIFACT}
        ml._set_cached_model("watches", art)
        # Manually expire
        ml._model_cache["watches"]["_cached_at"] = time.time() - ml.CACHE_TTL - 1
        assert ml._get_cached_model("watches") is None
        # Entry should be evicted
        assert "watches" not in ml._model_cache

    def test_cache_evicts_oldest_when_full(self):
        original_max = ml.MAX_CACHE_SIZE
        ml.MAX_CACHE_SIZE = 3
        try:
            for i in range(3):
                art = {**SAMPLE_ARTIFACT, "idx": i}
                ml._set_cached_model(f"cat_{i}", art)
                # Stagger timestamps so oldest is deterministic
                ml._model_cache[f"cat_{i}"]["_cached_at"] = time.time() - (3 - i)

            # Adding a 4th should evict cat_0 (oldest)
            ml._set_cached_model("cat_new", {**SAMPLE_ARTIFACT, "idx": 99})
            assert "cat_0" not in ml._model_cache
            assert "cat_new" in ml._model_cache
        finally:
            ml.MAX_CACHE_SIZE = original_max


class TestClearModelCache:
    def test_clear_all(self):
        ml._set_cached_model("a", {**SAMPLE_ARTIFACT})
        ml._set_cached_model("b", {**SAMPLE_ARTIFACT})
        ml._set_cached_model("a", {**SAMPLE_ARTIFACT}, is_canary=True)
        ml.clear_model_cache()
        assert len(ml._model_cache) == 0
        assert len(ml._canary_cache) == 0

    def test_clear_specific_category(self):
        ml._set_cached_model("a", {**SAMPLE_ARTIFACT})
        ml._set_cached_model("b", {**SAMPLE_ARTIFACT})
        ml._set_cached_model("a", {**SAMPLE_ARTIFACT}, is_canary=True)
        ml.clear_model_cache("a")
        assert "a" not in ml._model_cache
        assert "a" not in ml._canary_cache
        assert "b" in ml._model_cache


# ---------------------------------------------------------------------------
# _fetch_model_registry_entry
# ---------------------------------------------------------------------------

class TestFetchModelRegistryEntry:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_pool(self):
        with patch.object(ml, "get_db_pool", return_value=None):
            result = await ml._fetch_model_registry_entry("watches")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dict_for_production_model(self):
        row = _make_registry_entry()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=MagicMock(**{k: row[k] for k in row}, __iter__=row.__iter__, __getitem__=row.__getitem__, keys=row.keys))

        # Make the conn context manager work
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        # `_schema_is_compatible` runs BEFORE the SELECT and guards it. The
        # mock conn cannot answer its information_schema probe, so without
        # this patch the function returns None and the test reads as "no row"
        # — which is what it had been doing.
        with patch.object(ml, "get_db_pool", return_value=mock_pool), \
             patch.object(ml, "_schema_is_compatible", new_callable=AsyncMock,
                          return_value=True):
            # Mock fetchrow to return a dict-like object
            mock_conn.fetchrow = AsyncMock(return_value=row)
            result = await ml._fetch_model_registry_entry("watches", is_canary=False)

        assert result is not None
        assert result["category"] == "watches"

    @pytest.mark.asyncio
    async def test_incompatible_schema_skips_the_lookup_entirely(self):
        """The guard's whole purpose: degrade instead of erroring.

        When `model_registry` lacks the columns this loader needs, DB-side
        lookups are skipped and valuation falls back to disk/empirical rather
        than raising. Pinned because the two "returns None" tests below cannot
        tell this path apart from a genuine miss.
        """
        row = _make_registry_entry()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=row)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch.object(ml, "get_db_pool", return_value=mock_pool), \
             patch.object(ml, "_schema_is_compatible", new_callable=AsyncMock,
                          return_value=False):
            result = await ml._fetch_model_registry_entry("watches")

        assert result is None
        mock_conn.fetchrow.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_row(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch.object(ml, "get_db_pool", return_value=mock_pool):
            result = await ml._fetch_model_registry_entry("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_db_exception(self):
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch.object(ml, "get_db_pool", return_value=mock_pool):
            result = await ml._fetch_model_registry_entry("watches")
        assert result is None

    @pytest.mark.asyncio
    async def test_canary_query_path(self):
        """Ensure is_canary=True calls fetchrow with canary SQL."""
        row = _make_registry_entry(is_canary=True)
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=row)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch.object(ml, "get_db_pool", return_value=mock_pool), \
             patch.object(ml, "_schema_is_compatible", new_callable=AsyncMock,
                          return_value=True):
            result = await ml._fetch_model_registry_entry("watches", is_canary=True)

        assert result is not None
        # The SQL passed should contain "is_canary = true"
        call_args = mock_conn.fetchrow.call_args
        assert "is_canary = true" in call_args[0][0]


# ---------------------------------------------------------------------------
# _load_artifact_from_s3
# ---------------------------------------------------------------------------

class TestLoadArtifactFromS3:
    def test_returns_none_when_boto3_unavailable(self):
        with patch.object(ml, "S3_AVAILABLE", False):
            assert ml._load_artifact_from_s3("models/watches.json") is None

    @pytest.mark.skipif(not ml.S3_AVAILABLE, reason="boto3 not installed")
    def test_loads_artifact_successfully(self):
        import boto3
        body_bytes = json.dumps(SAMPLE_ARTIFACT).encode("utf-8")
        mock_body = MagicMock()
        mock_body.read.return_value = body_bytes

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch.object(ml, "S3_AVAILABLE", True), \
             patch.object(boto3, "client", return_value=mock_s3):
            result = ml._load_artifact_from_s3("models/watches.json")

        assert result is not None
        assert result["model_type"] == "ridge_v2"
        assert result["features"] == ["condition", "rarity", "age"]

    @pytest.mark.skipif(not ml.S3_AVAILABLE, reason="boto3 not installed")
    def test_returns_none_on_client_error(self):
        """S3 ClientError should be caught gracefully."""
        import boto3
        from botocore.exceptions import ClientError
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject"
        )

        with patch.object(ml, "S3_AVAILABLE", True), \
             patch.object(boto3, "client", return_value=mock_s3):
            result = ml._load_artifact_from_s3("missing/key.json")

        assert result is None

    @pytest.mark.skipif(not ml.S3_AVAILABLE, reason="boto3 not installed")
    def test_returns_none_on_generic_exception(self):
        import boto3
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = RuntimeError("network failure")

        with patch.object(ml, "S3_AVAILABLE", True), \
             patch.object(boto3, "client", return_value=mock_s3):
            result = ml._load_artifact_from_s3("models/watches.json")

        assert result is None

    def test_loads_artifact_without_boto3(self):
        """When boto3 is not available, S3 loading returns None gracefully."""
        with patch.object(ml, "S3_AVAILABLE", False):
            result = ml._load_artifact_from_s3("models/watches.json")
        assert result is None


# ---------------------------------------------------------------------------
# _load_model_entry
# ---------------------------------------------------------------------------

class TestLoadModelEntry:
    @pytest.mark.asyncio
    async def test_returns_cached_model_if_available(self):
        art = {**SAMPLE_ARTIFACT}
        ml._set_cached_model("watches", art)

        # Should return cached without hitting DB
        with patch.object(ml, "_fetch_model_registry_entry", new_callable=AsyncMock) as mock_fetch:
            result = await ml._load_model_entry("watches")

        mock_fetch.assert_not_called()
        assert result is not None
        assert result["model_type"] == "ridge_v2"

    @pytest.mark.asyncio
    async def test_loads_from_inline_artifact_json_dict(self):
        entry = _make_registry_entry(artifact_json=SAMPLE_ARTIFACT)
        with patch.object(ml, "_fetch_model_registry_entry", new_callable=AsyncMock, return_value=entry):
            result = await ml._load_model_entry("watches")

        assert result is not None
        assert result["_registry_id"] == 42
        assert result["_category"] == "watches"
        assert result["_is_canary"] is False
        assert result["uncertainty_scale"] == 1.2

    @pytest.mark.asyncio
    async def test_loads_from_inline_artifact_json_string(self):
        entry = _make_registry_entry(artifact_json=json.dumps(SAMPLE_ARTIFACT))
        with patch.object(ml, "_fetch_model_registry_entry", new_callable=AsyncMock, return_value=entry):
            result = await ml._load_model_entry("watches")

        assert result is not None
        assert result["model_type"] == "ridge_v2"

    @pytest.mark.asyncio
    async def test_falls_back_to_s3_when_no_inline_artifact(self):
        entry = _make_registry_entry(artifact_json=None, s3_key="models/watches.json")
        with patch.object(ml, "_fetch_model_registry_entry", new_callable=AsyncMock, return_value=entry), \
             patch.object(ml, "_load_artifact_from_s3", return_value={**SAMPLE_ARTIFACT}):
            result = await ml._load_model_entry("watches")

        assert result is not None
        assert result["model_type"] == "ridge_v2"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_registry_entry(self):
        with patch.object(ml, "_fetch_model_registry_entry", new_callable=AsyncMock, return_value=None):
            result = await ml._load_model_entry("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_inline_s3_and_disk_all_fail(self):
        """THREE sources, not two — disk was added after this test was written.

        `_load_model_entry` falls back to `artifacts/{category}/{slot}/model.json`
        when the registry yields nothing usable, which is the path that keeps
        valuation alive while the registry schema is incompatible. The test
        left it unpatched and got a real on-disk model back.
        """
        entry = _make_registry_entry(artifact_json="{{invalid json", s3_key="bad/key")
        with patch.object(ml, "_fetch_model_registry_entry", new_callable=AsyncMock, return_value=entry), \
             patch.object(ml, "_load_artifact_from_s3", return_value=None), \
             patch.object(ml, "_load_artifact_from_disk", return_value=None):
            result = await ml._load_model_entry("watches")
        assert result is None

    @pytest.mark.asyncio
    async def test_disk_fallback_is_used_and_labelled(self):
        """The fallback that actually runs in production today.

        `_loaded_from` is how a caller tells a registry-backed model from a
        disk one; without it a silently-stale on-disk artifact is
        indistinguishable from the live model.
        """
        entry = _make_registry_entry(artifact_json="{{invalid json", s3_key="bad/key")
        with patch.object(ml, "_fetch_model_registry_entry", new_callable=AsyncMock, return_value=entry), \
             patch.object(ml, "_load_artifact_from_s3", return_value=None), \
             patch.object(ml, "_load_artifact_from_disk", return_value={**SAMPLE_ARTIFACT}):
            result = await ml._load_model_entry("watches")

        assert result is not None
        assert result["_loaded_from"] == "disk:active"

    @pytest.mark.asyncio
    async def test_caches_after_load(self):
        entry = _make_registry_entry(artifact_json=SAMPLE_ARTIFACT)
        with patch.object(ml, "_fetch_model_registry_entry", new_callable=AsyncMock, return_value=entry):
            await ml._load_model_entry("watches")

        # Should now be in cache
        cached = ml._get_cached_model("watches")
        assert cached is not None
        assert cached["_registry_id"] == 42

    @pytest.mark.asyncio
    async def test_no_uncertainty_scale_enrichment_when_none(self):
        """When registry entry has uncertainty_scale=None, artifact keeps its original value only."""
        # Use an artifact WITHOUT uncertainty_scale already in it
        minimal_artifact = {"model_type": "ridge_v2", "features": ["condition"]}
        entry = _make_registry_entry(artifact_json=minimal_artifact, uncertainty_scale=None)
        with patch.object(ml, "_fetch_model_registry_entry", new_callable=AsyncMock, return_value=entry):
            result = await ml._load_model_entry("watches")

        # The enrichment step should NOT add uncertainty_scale when registry value is None
        assert "uncertainty_scale" not in result


# ---------------------------------------------------------------------------
# get_active_model — canary routing
# ---------------------------------------------------------------------------

class TestGetActiveModel:
    @pytest.mark.asyncio
    async def test_returns_production_model(self):
        prod = {**SAMPLE_ARTIFACT, "_is_canary": False}

        async def side_effect(cat, is_canary=False):
            if is_canary:
                return None
            return prod

        with patch.object(ml, "_load_model_entry", new_callable=AsyncMock, side_effect=side_effect):
            with patch.object(ml, "CANARY_TRAFFIC_PCT", 0):
                result = await ml.get_active_model("watches")

        assert result is not None
        assert result["_is_canary"] is False

    @pytest.mark.asyncio
    async def test_returns_canary_when_traffic_routes(self):
        canary = {**SAMPLE_ARTIFACT, "_is_canary": True}
        with patch.object(ml, "_load_model_entry", new_callable=AsyncMock, return_value=canary):
            with patch.object(ml, "CANARY_TRAFFIC_PCT", 100):
                result = await ml.get_active_model("watches", routing_key="user_123")

        assert result is not None
        assert result["_is_canary"] is True

    @pytest.mark.asyncio
    async def test_falls_back_to_production_when_no_canary(self):
        prod = {**SAMPLE_ARTIFACT, "_is_canary": False}

        async def side_effect(cat, is_canary=False):
            if is_canary:
                return None  # No canary available
            return prod

        with patch.object(ml, "_load_model_entry", new_callable=AsyncMock, side_effect=side_effect):
            with patch.object(ml, "CANARY_TRAFFIC_PCT", 100):
                result = await ml.get_active_model("watches", routing_key="user_123")

        assert result is not None
        assert result["_is_canary"] is False

    @pytest.mark.asyncio
    async def test_returns_none_when_no_models(self):
        with patch.object(ml, "_load_model_entry", new_callable=AsyncMock, return_value=None):
            with patch.object(ml, "CANARY_TRAFFIC_PCT", 0):
                result = await ml.get_active_model("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_deterministic_routing_key(self):
        """Same routing_key always gets same canary decision."""
        results = []
        canary = {**SAMPLE_ARTIFACT, "_is_canary": True}
        prod = {**SAMPLE_ARTIFACT, "_is_canary": False}

        async def side_effect(cat, is_canary=False):
            return canary if is_canary else prod

        with patch.object(ml, "_load_model_entry", new_callable=AsyncMock, side_effect=side_effect):
            with patch.object(ml, "CANARY_TRAFFIC_PCT", 50):
                for _ in range(10):
                    r = await ml.get_active_model("watches", routing_key="fixed_key")
                    results.append(r["_is_canary"])

        # All results should be identical (deterministic)
        assert len(set(results)) == 1

    @pytest.mark.asyncio
    async def test_random_routing_without_key(self):
        """Without routing_key, uses random — just verify it doesn't crash."""
        prod = {**SAMPLE_ARTIFACT, "_is_canary": False}

        async def side_effect(cat, is_canary=False):
            if is_canary:
                return None
            return prod

        with patch.object(ml, "_load_model_entry", new_callable=AsyncMock, side_effect=side_effect):
            with patch.object(ml, "CANARY_TRAFFIC_PCT", 5):
                result = await ml.get_active_model("watches")
        # Should get something (production fallback)
        assert result is not None


# ---------------------------------------------------------------------------
# get_canary_status
# ---------------------------------------------------------------------------

class TestGetCanaryStatus:
    @pytest.mark.asyncio
    async def test_returns_default_when_no_pool(self):
        with patch.object(ml, "get_db_pool", return_value=None):
            result = await ml.get_canary_status()
        assert "canary_traffic_pct" in result
        assert result["production_models"] == {}
        assert result["canary_models"] == {}
        assert result["calibration"] == {}

    @pytest.mark.asyncio
    async def test_returns_populated_status(self):
        from datetime import datetime
        now = datetime(2026, 3, 20)

        prod_rows = [{"category": "watches", "model_type": "ridge_v2", "created_at": now}]
        canary_rows = [{"category": "watches", "model_type": "ridge_v3", "created_at": now}]
        cal_rows = [{"category": "watches", "picp": 0.85, "ace": 0.02, "mae": 5.0, "gate_pass": True, "created_at": now}]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[prod_rows, canary_rows, cal_rows])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch.object(ml, "get_db_pool", return_value=mock_pool):
            result = await ml.get_canary_status()

        assert "watches" in result["production_models"]
        assert result["production_models"]["watches"]["model_type"] == "ridge_v2"
        assert "watches" in result["canary_models"]
        assert result["calibration"]["watches"]["picp"] == 0.85
        assert result["calibration"]["watches"]["gate_pass"] is True

    @pytest.mark.asyncio
    async def test_handles_db_exception_gracefully(self):
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch.object(ml, "get_db_pool", return_value=mock_pool):
            result = await ml.get_canary_status()

        # Should still return the default structure
        assert "canary_traffic_pct" in result


# ---------------------------------------------------------------------------
# get_active_model_sync
# ---------------------------------------------------------------------------

class TestGetActiveModelSync:
    def test_returns_cached_model_in_running_loop(self):
        """When an event loop is already running, falls back to cache."""
        art = {**SAMPLE_ARTIFACT}
        ml._set_cached_model("watches", art)

        # Simulate being inside a running loop
        with patch("asyncio.get_event_loop") as mock_gel:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_gel.return_value = mock_loop
            result = ml.get_active_model_sync("watches")

        assert result is not None
        assert result["model_type"] == "ridge_v2"

    def test_returns_none_when_no_cache_in_running_loop(self):
        with patch("asyncio.get_event_loop") as mock_gel:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_gel.return_value = mock_loop
            result = ml.get_active_model_sync("nonexistent")

        assert result is None


# ---------------------------------------------------------------------------
# Thread safety — concurrent cache access
# ---------------------------------------------------------------------------

class TestConcurrentAccess:
    def test_concurrent_cache_writes(self):
        """Multiple threads writing to cache should not crash."""
        import threading

        errors = []

        def writer(cat_id: int):
            try:
                for _ in range(50):
                    ml._set_cached_model(f"cat_{cat_id}", {**SAMPLE_ARTIFACT, "idx": cat_id})
                    ml._get_cached_model(f"cat_{cat_id}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No exceptions expected (dict ops are GIL-protected in CPython)
        assert len(errors) == 0
