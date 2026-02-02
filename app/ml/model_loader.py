"""
Model loader for CollectAI ML models.

Loads model artifacts from S3 via the model_registry table.
Uses LRU cache for in-memory caching of loaded models.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# Optional: boto3 for S3 access
try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    logger.warning("boto3 not installed; S3 model loading disabled")


def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except Exception as e:
        logger.debug(f"DB pool not available: {e}")
        return None


async def _fetch_model_registry_entry(category: str) -> dict | None:
    """
    Fetch the active model entry from model_registry for a category.
    Returns the row as a dict, or None if not found.
    """
    pool = _get_db_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, category, model_type, s3_key, artifact_json, uncertainty_scale, is_active, created_at
                FROM model_registry
                WHERE category = $1 AND is_active = true
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

    bucket = os.getenv("ML_MODELS_S3_BUCKET", "collectai-ml-models")
    region = os.getenv("AWS_REGION", "eu-west-1")

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


def _get_cached_model(category: str) -> dict | None:
    """Get model from in-memory cache."""
    return _model_cache.get(category)


def _set_cached_model(category: str, artifact: dict) -> None:
    """Store model in in-memory cache."""
    _model_cache[category] = artifact


def clear_model_cache(category: str | None = None) -> None:
    """
    Clear model cache.
    If category is None, clears entire cache.
    """
    if category is None:
        _model_cache.clear()
    elif category in _model_cache:
        del _model_cache[category]


async def get_active_model(category: str) -> dict | None:
    """
    Get the active model artifact for a category.

    1. Check in-memory cache
    2. Query model_registry for active model
    3. If artifact_json is present, use it directly
    4. Otherwise, load from S3 using s3_key
    5. Cache and return

    Returns:
        Model artifact dict with keys like:
        - model_type: str (e.g., "ridge_v1")
        - features: list[str]
        - standardizer: {mean: list, std: list}
        - ridge: {coef: list, intercept: float}
        - uncertainty_scale: float (optional)

        Returns None if no model available.
    """
    # Check cache first
    cached = _get_cached_model(category)
    if cached:
        logger.debug(f"Model cache hit for {category}")
        return cached

    # Fetch from registry
    entry = await _fetch_model_registry_entry(category)
    if not entry:
        logger.info(f"No active model found for category: {category}")
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
        logger.warning(f"Could not load artifact for {category}")
        return None

    # Enrich with registry metadata
    artifact["_registry_id"] = entry.get("id")
    artifact["_category"] = category
    if entry.get("uncertainty_scale") is not None:
        artifact["uncertainty_scale"] = float(entry["uncertainty_scale"])

    # Cache and return
    _set_cached_model(category, artifact)
    logger.info(f"Loaded model for {category}: {artifact.get('model_type', 'unknown')}")

    return artifact


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
