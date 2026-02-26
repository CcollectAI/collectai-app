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
        logger.warning(f"Failed to fetch model_registry entry for {category}: {e}")
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


# Cache for loaded model artifacts (keyed by category)
_model_cache: dict[str, dict] = {}
_canary_cache: dict[str, dict] = {}


def _get_cached_model(category: str, is_canary: bool = False) -> dict | None:
    """Get model from in-memory cache."""
    cache = _canary_cache if is_canary else _model_cache
    return cache.get(category)


def _set_cached_model(category: str, artifact: dict, is_canary: bool = False) -> None:
    """Store model in in-memory cache."""
    cache = _canary_cache if is_canary else _model_cache
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
    """Load a model (production or canary) from registry."""
    cached = _get_cached_model(category, is_canary)
    if cached:
        return cached

    entry = await _fetch_model_registry_entry(category, is_canary=is_canary)
    if not entry:
        return None

    artifact: dict | None = None

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

    if artifact is None:
        return None

    # Enrich with registry metadata
    artifact["_registry_id"] = entry.get("id")
    artifact["_category"] = category
    artifact["_is_canary"] = is_canary
    if entry.get("uncertainty_scale") is not None:
        artifact["uncertainty_scale"] = float(entry["uncertainty_scale"])

    _set_cached_model(category, artifact, is_canary)
    label = "canary" if is_canary else "production"
    logger.info(f"Loaded {label} model for {category}: {artifact.get('model_type', 'unknown')}")
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
