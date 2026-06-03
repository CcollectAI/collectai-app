"""
Model loader for CollectAI ML models.

Loads model artifacts from S3 via the model_registry table.
Uses LRU cache for in-memory caching of loaded models.
Supports canary deployments: routes configurable % of traffic to canary model.
"""

from __future__ import annotations

import json
import logging
import hashlib
import random
from functools import lru_cache
from typing import Any

from app.config import MODEL_CANARY_TRAFFIC_PCT as CANARY_TRAFFIC_PCT, ML_MODELS_S3_BUCKET, AWS_REGION
from app.lib.db_helpers import get_db_pool

logger = logging.getLogger(__name__)

# Optional: boto3 for S3 access
try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    logger.warning("boto3 not installed; S3 model loading disabled")


# Schema probe: the live model_registry table has a different column set
# from what this loader was written for (columns are id, name, version, params,
# created_at, uri, is_canary — no `category`, `model_type`, `s3_key`,
# `artifact_json`, `uncertainty_scale`, `is_active`). Querying the old columns
# logs a warning on every valuation row, spamming the log. Probe once and
# short-circuit if the schema doesn't match — the valuation_worker gracefully
# falls back to the empirical model on None. (Schema drift uncovered during
# the 2026-04-19 silent-sleeper audit.)
_REGISTRY_SCHEMA_OK: bool | None = None


async def _schema_is_compatible(conn) -> bool:
    global _REGISTRY_SCHEMA_OK
    if _REGISTRY_SCHEMA_OK is not None:
        return _REGISTRY_SCHEMA_OK
    try:
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='model_registry'"
        )
        names = {r["column_name"] for r in cols}
        _REGISTRY_SCHEMA_OK = {"category", "model_type", "is_active"}.issubset(names)
        if not _REGISTRY_SCHEMA_OK:
            logger.info(
                "[model_loader] model_registry schema incompatible "
                "(missing %s) — skipping DB-side lookups; valuation_worker "
                "will use empirical fallback until a loader rewrite lands.",
                {"category", "model_type", "is_active"} - names,
            )
    except Exception:
        _REGISTRY_SCHEMA_OK = False
    return _REGISTRY_SCHEMA_OK


async def _fetch_model_registry_entry(
    category: str,
    is_canary: bool = False,
) -> dict | None:
    """
    Fetch the active model entry from model_registry for a category.
    If is_canary=True, fetches the canary model instead.
    Returns the row as a dict, or None if not found.
    """
    pool = get_db_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            if not await _schema_is_compatible(conn):
                return None

            if is_canary:
                row = await conn.fetchrow(
                    """
                    SELECT id, category, model_type, s3_key, artifact_json,
                           uncertainty_scale, is_active, is_canary, created_at
                    FROM model_registry
                    WHERE category = $1 AND is_canary = true
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    category,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT id, category, model_type, s3_key, artifact_json,
                           uncertainty_scale, is_active, is_canary, created_at
                    FROM model_registry
                    WHERE category = $1 AND is_active = true AND (is_canary IS NULL OR is_canary = false)
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    category,
                )
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.debug("model_registry lookup for %s failed: %s", category, e)
        return None


def _load_artifact_from_s3(s3_key: str) -> dict | None:
    """
    Load model artifact JSON from S3.
    Returns parsed dict or None on failure.
    """
    if not S3_AVAILABLE:
        return None

    bucket = ML_MODELS_S3_BUCKET
    region = AWS_REGION

    try:
        s3 = boto3.client("s3", region_name=region)
        response = s3.get_object(Bucket=bucket, Key=s3_key)
        body = response["Body"].read().decode("utf-8")
        return json.loads(body)
    except ClientError as e:
        logger.warning(f"S3 error loading {s3_key}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to load artifact from S3 {s3_key}: {e}")
        return None


# ---------------------------------------------------------------------------
# Disk fallback — reads `artifacts/{category}/{slot}/model.json` from disk.
# Required because the live `model_registry` table has an incompatible
# schema (4 rows, columns: name/version/params/uri/is_canary — no category /
# model_type / s3_key / artifact_json / is_active). _schema_is_compatible
# correctly returns False; without this fallback every get_active_model
# returned None and **valuation_worker silently used empirical quantiles
# only** despite Ridge models retraining weekly to disk.
# Discovered 2026-04-25 while planning B2 model A/B work.
# ---------------------------------------------------------------------------

_ARTIFACTS_ROOT = None


def _resolve_artifacts_root():
    """Find the artifacts/ directory regardless of CWD.

    On EC2: /opt/collectors/server/artifacts.
    Locally: server/artifacts (CWD-relative).
    """
    global _ARTIFACTS_ROOT
    if _ARTIFACTS_ROOT is not None:
        return _ARTIFACTS_ROOT
    import pathlib
    candidates = [
        pathlib.Path.cwd() / "artifacts",
        pathlib.Path("/opt/collectors/server/artifacts"),
        pathlib.Path(__file__).resolve().parents[2] / "artifacts",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            _ARTIFACTS_ROOT = c
            logger.info("[model_loader] Using disk artifacts root: %s", c)
            return c
    return None


def stale_model_categories(max_age_days: float = 21.0) -> list[tuple[str, float]]:
    """Return [(category, age_days)] for active models older than max_age_days.

    V4: serve-time staleness detection. The retrain worker runs weekly; if it
    silently fails (or a category's training errors repeatedly), the old
    artifact keeps serving forever with no signal. This reads each category's
    `active` model age from its version-stamped directory name (YYYYMMDD_HHMMSS),
    falling back to the model.json mtime, and surfaces anything older than the
    threshold. Default 21d = 3x the weekly retrain interval, so a single missed
    cycle doesn't false-alarm.
    """
    import datetime as _dt
    import os as _os
    root = _resolve_artifacts_root()
    if root is None:
        return []
    now = _dt.datetime.now(_dt.timezone.utc)
    stale: list[tuple[str, float]] = []
    try:
        for cat_dir in root.iterdir():
            try:
                if not cat_dir.is_dir():
                    continue
                active = cat_dir / "active"
                if not active.exists():
                    continue
                ts: _dt.datetime | None = None
                if active.is_symlink():
                    ver = _os.path.basename(_os.readlink(str(active)))
                    try:
                        ts = _dt.datetime.strptime(ver[:15], "%Y%m%d_%H%M%S").replace(
                            tzinfo=_dt.timezone.utc)
                    except Exception:
                        ts = None
                if ts is None:
                    mj = active / "model.json"
                    if mj.exists():
                        ts = _dt.datetime.fromtimestamp(mj.stat().st_mtime, _dt.timezone.utc)
                if ts is None:
                    continue
                age = (now - ts).total_seconds() / 86400.0
                if age > max_age_days:
                    stale.append((cat_dir.name, round(age, 1)))
            except Exception:
                continue
    except Exception:
        return []
    return sorted(stale, key=lambda x: -x[1])


def _load_artifact_from_disk(category: str, slot: str = "active") -> dict | None:
    """Load `artifacts/{category}/{slot}/model.json` from disk.

    `slot` is the symlink name: 'active' for production, 'canary' for A/B.
    Returns parsed artifact dict or None.
    """
    root = _resolve_artifacts_root()
    if root is None:
        return None
    path = root / category / slot / "model.json"
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("[model_loader] Disk read failed for %s/%s: %s", category, slot, e)
        return None


# Cache for loaded model artifacts (keyed by category)
# Each entry: {"artifact": dict, "loaded_at": float}
_model_cache: dict[str, dict] = {}
_canary_cache: dict[str, dict] = {}

# Cache configuration
CACHE_TTL = 3600  # 1 hour
MAX_CACHE_SIZE = 100


def _get_cached_model(category: str, is_canary: bool = False) -> dict | None:
    """Get model from in-memory cache, respecting TTL."""
    import time
    cache = _canary_cache if is_canary else _model_cache
    entry = cache.get(category)
    if entry is None:
        return None
    # Check TTL
    if time.time() - entry.get("_cached_at", 0) > CACHE_TTL:
        cache.pop(category, None)
        return None
    return entry


def _set_cached_model(category: str, artifact: dict, is_canary: bool = False) -> None:
    """Store model in in-memory cache with timestamp. Evicts oldest if over limit."""
    import time
    cache = _canary_cache if is_canary else _model_cache
    # Evict oldest entries if at capacity
    if len(cache) >= MAX_CACHE_SIZE and category not in cache:
        oldest_key = min(cache, key=lambda k: cache[k].get("_cached_at", 0))
        cache.pop(oldest_key, None)
    artifact["_cached_at"] = time.time()
    cache[category] = artifact


def clear_model_cache(category: str | None = None) -> None:
    """
    Clear model cache.
    If category is None, clears entire cache.
    """
    if category is None:
        _model_cache.clear()
        _canary_cache.clear()
    else:
        _model_cache.pop(category, None)
        _canary_cache.pop(category, None)


async def _load_model_entry(category: str, is_canary: bool = False) -> dict | None:
    """Load a model (production or canary) from registry, with disk fallback."""
    cached = _get_cached_model(category, is_canary)
    if cached:
        return cached

    entry = await _fetch_model_registry_entry(category, is_canary=is_canary)
    artifact: dict | None = None

    if entry:
        # Try artifact_json first (inline storage)
        if entry.get("artifact_json"):
            try:
                if isinstance(entry["artifact_json"], str):
                    artifact = json.loads(entry["artifact_json"])
                else:
                    artifact = entry["artifact_json"]
            except Exception as e:
                logger.warning(f"Failed to parse artifact_json for {category}: {e}")

        # Fall back to S3 if no inline artifact
        if artifact is None and entry.get("s3_key"):
            artifact = _load_artifact_from_s3(entry["s3_key"])

    # FINAL fallback: read directly from disk via the symlink the train
    # pipeline actually uses (`artifacts/{category}/{active|canary}`).
    # This is the production path today because the live model_registry
    # schema is incompatible with this loader (see _schema_is_compatible).
    if artifact is None:
        slot = "canary" if is_canary else "active"
        artifact = _load_artifact_from_disk(category, slot=slot)
        if artifact is not None:
            artifact["_loaded_from"] = f"disk:{slot}"

    if artifact is None:
        return None

    # Enrich with registry metadata
    if entry:
        artifact["_registry_id"] = entry.get("id")
        if entry.get("uncertainty_scale") is not None:
            artifact["uncertainty_scale"] = float(entry["uncertainty_scale"])
    artifact["_category"] = category
    artifact["_is_canary"] = is_canary

    _set_cached_model(category, artifact, is_canary)
    label = "canary" if is_canary else "production"
    src = artifact.get("_loaded_from", "registry")
    logger.info(f"Loaded {label} model for {category} from {src}: {artifact.get('model_type', 'unknown')}")
    return artifact


async def get_active_model(category: str, routing_key: str | None = None) -> dict | None:
    """
    Get the active model artifact for a category.

    Supports canary deployment (#13): routes CANARY_TRAFFIC_PCT % of requests
    to the canary model if one exists.

    Args:
        category: Category slug (e.g., "pokemon")
        routing_key: Optional key for deterministic canary routing (e.g., user_id or item_id).
                     If provided, same key always gets the same model (sticky routing).
                     If None, falls back to random routing.

    Returns:
        Model artifact dict with keys like:
        - model_type: str (e.g., "ridge_v2")
        - features: list[str]
        - standardizer: {mean: list, std: list}
        - ridge: {coef: list, intercept: float}
        - uncertainty_scale: float (optional)
        - _is_canary: bool (whether this is the canary model)

        Returns None if no model available.
    """
    # Canary routing (#13) — deterministic if routing_key provided
    if routing_key:
        bucket = int(hashlib.md5(routing_key.encode()).hexdigest(), 16) % 100
        use_canary = bucket < CANARY_TRAFFIC_PCT
    else:
        use_canary = random.random() * 100 < CANARY_TRAFFIC_PCT
    if use_canary:
        canary = await _load_model_entry(category, is_canary=True)
        if canary:
            logger.debug(f"Routing to canary model for {category}")
            return canary
        # No canary available, fall through to production

    # Production model
    production = await _load_model_entry(category, is_canary=False)
    if production:
        return production

    logger.info(f"No active model found for category: {category}")
    return None


async def get_canary_status() -> dict:
    """Return canary deployment metrics: traffic split, per-model accuracy, active models."""
    pool = get_db_pool()
    result: dict = {
        "canary_traffic_pct": CANARY_TRAFFIC_PCT,
        "production_models": {},
        "canary_models": {},
        "calibration": {},
    }

    if not pool:
        return result

    try:
        async with pool.acquire() as conn:
            # Active models per category
            prod_rows = await conn.fetch(
                """
                SELECT DISTINCT ON (category) category, model_type, created_at
                FROM model_registry
                WHERE is_active = true AND (is_canary IS NULL OR is_canary = false)
                ORDER BY category, created_at DESC
                """
            )
            for r in prod_rows:
                result["production_models"][r["category"]] = {
                    "model_type": r["model_type"],
                    "deployed_at": r["created_at"].isoformat() if r["created_at"] else None,
                }

            canary_rows = await conn.fetch(
                """
                SELECT DISTINCT ON (category) category, model_type, created_at
                FROM model_registry
                WHERE is_canary = true
                ORDER BY category, created_at DESC
                """
            )
            for r in canary_rows:
                result["canary_models"][r["category"]] = {
                    "model_type": r["model_type"],
                    "deployed_at": r["created_at"].isoformat() if r["created_at"] else None,
                }

            # Latest calibration per category
            cal_rows = await conn.fetch(
                """
                SELECT DISTINCT ON (category) category, picp, ace, mae, gate_pass, created_at
                FROM calibration_snapshots
                ORDER BY category, created_at DESC
                """
            )
            for r in cal_rows:
                result["calibration"][r["category"]] = {
                    "picp": float(r["picp"]) if r["picp"] is not None else None,
                    "ace": float(r["ace"]) if r["ace"] is not None else None,
                    "mae": float(r["mae"]) if r["mae"] is not None else None,
                    "gate_pass": r["gate_pass"],
                    "measured_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
    except Exception as e:
        logger.warning("Failed to fetch canary status: %s", e)

    return result


def get_active_model_sync(category: str) -> dict | None:
    """
    Synchronous wrapper for get_active_model.
    Uses asyncio.run() - only use from sync contexts.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context, can't use run()
            # Return cached or None
            return _get_cached_model(category)
        return loop.run_until_complete(get_active_model(category))
    except RuntimeError:
        # No event loop
        return asyncio.run(get_active_model(category))
