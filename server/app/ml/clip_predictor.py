"""
CLIP embedding and pre-filtering logic via fal.ai.

Generates image embeddings and compares them against cached text embeddings
of all category descriptions for zero-shot category matching.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import tempfile
from typing import Any

import httpx

from app.config import FAL_KEY, FAL_CLIP_URL

# Both entry points below no-op when FAL_KEY is unset — silently, until now.
# The result was a tier that looked configured, produced nothing and said
# nothing: category_hint was permanently None, which also left the B3.2b
# confusion hint unreachable (it only fires on a truthy hint). Announce it
# once per process so a dead pre-filter is visible instead of inferred from
# an absence of log lines.
_FAL_KEY_WARNED = False


def _warn_clip_disabled(where: str) -> None:
    global _FAL_KEY_WARNED
    if not _FAL_KEY_WARNED:
        _FAL_KEY_WARNED = True
        logger.warning(
            "CLIP pre-filter DISABLED: FAL_KEY is unset (%s). Tier 1 is skipped, "
            "category_hint stays None, and the confusion-hint path is unreachable. "
            "Set FAL_KEY or remove the CLIP tier.", where,
        )
from app.ml.vision_helpers import (
    ALL_CATEGORIES,
    CATEGORY_DESCRIPTIONS,
    ClassificationResult,
    cosine_similarity,
    softmax,
)

logger = logging.getLogger(__name__)

# Cached text embeddings for category descriptions.  Populated once (ideally at
# startup, out of the request path — see warm_clip_text_embeddings), then reused
# for all subsequent calls.  Without this every scan would make 40+ fal.ai
# calls. S3: also persisted to disk, keyed by a hash of the descriptions, so a
# bake restart reloads instantly instead of re-paying the 40-call warm-up on
# the first user's scan.
_clip_text_embeddings: dict[str, list[float]] = {}
_clip_text_embeddings_loaded: bool = False

# Disk cache. /tmp survives process restarts (the case we care about); the hash
# in the filename invalidates the cache automatically if CATEGORY_DESCRIPTIONS
# changes, so stale embeddings can't silently persist across a deploy.
_DESC_HASH = hashlib.sha1(
    json.dumps(
        {c: CATEGORY_DESCRIPTIONS.get(c, c) for c in sorted(ALL_CATEGORIES)},
        sort_keys=True,
    ).encode()
).hexdigest()[:12]
_CLIP_CACHE_PATH = os.getenv(
    "CLIP_EMB_CACHE_PATH",
    os.path.join(tempfile.gettempdir(), f"clip_text_embeddings_{_DESC_HASH}.json"),
)


def _load_clip_cache_from_disk() -> bool:
    """Populate the in-process cache from the disk cache. Returns True on hit."""
    global _clip_text_embeddings, _clip_text_embeddings_loaded
    try:
        if not os.path.exists(_CLIP_CACHE_PATH):
            return False
        with open(_CLIP_CACHE_PATH) as f:
            data = json.load(f)
        if isinstance(data, dict) and data:
            _clip_text_embeddings = {k: v for k, v in data.items() if v}
            _clip_text_embeddings_loaded = True
            logger.info(
                "CLIP: loaded %d text embeddings from disk cache",
                len(_clip_text_embeddings),
            )
            return True
    except Exception as e:
        logger.warning("CLIP: disk cache load failed: %s", e)
    return False


def _save_clip_cache_to_disk() -> None:
    try:
        tmp = f"{_CLIP_CACHE_PATH}.tmp"
        with open(tmp, "w") as f:
            json.dump(_clip_text_embeddings, f)
        os.replace(tmp, _CLIP_CACHE_PATH)  # atomic
    except Exception as e:
        logger.warning("CLIP: disk cache save failed: %s", e)


async def _ensure_clip_text_embeddings(client: httpx.AsyncClient) -> dict[str, list[float]]:
    """Return cached text embeddings, loading from disk or fetching once.

    Order: in-process cache → disk cache → fetch-and-persist. The fetch path
    is the slow ~40-call warm-up; in steady state it runs once at startup
    (warm_clip_text_embeddings) or once after a deploy that changed the
    descriptions, never on a normal user scan.
    """
    global _clip_text_embeddings_loaded

    if _clip_text_embeddings_loaded and _clip_text_embeddings:
        return _clip_text_embeddings
    if _load_clip_cache_from_disk():
        return _clip_text_embeddings

    logger.info("CLIP: warming up text embeddings for %d categories", len(ALL_CATEGORIES))
    for cat_id in ALL_CATEGORIES:
        if cat_id in _clip_text_embeddings:
            continue
        desc = CATEGORY_DESCRIPTIONS.get(cat_id, cat_id)
        try:
            text_resp = await client.post(
                FAL_CLIP_URL,
                headers={
                    "Authorization": f"Key {FAL_KEY}",
                    "Content-Type": "application/json",
                },
                json={"text": desc},
            )
            text_resp.raise_for_status()
            text_data = text_resp.json()
            emb: list[float] = text_data.get("embedding", [])
            if emb:
                _clip_text_embeddings[cat_id] = emb
        except Exception as e:
            logger.warning("CLIP: failed to get text embedding for %s: %s", cat_id, e)

    _clip_text_embeddings_loaded = True
    logger.info("CLIP: cached %d/%d text embeddings", len(_clip_text_embeddings), len(ALL_CATEGORIES))
    if _clip_text_embeddings:
        _save_clip_cache_to_disk()
    return _clip_text_embeddings


async def warm_clip_text_embeddings() -> int:
    """Pre-warm the CLIP text-embedding cache OUT of the request path.

    Call once at app startup (fire-and-forget). Uses its own generous-timeout
    client because the warm-up makes ~40 sequential fal.ai calls — that cost
    belongs at boot, not on the first user's scan. No-op if FAL_KEY is unset or
    the cache is already warm (in-process or on disk).
    """
    if not FAL_KEY:
        _warn_clip_disabled("warmup")
        return 0
    if (_clip_text_embeddings_loaded and _clip_text_embeddings) or _load_clip_cache_from_disk():
        return len(_clip_text_embeddings)
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            await _ensure_clip_text_embeddings(client)
    except Exception as e:
        logger.warning("CLIP: startup warm-up failed (will lazy-warm on first scan): %s", e)
    return len(_clip_text_embeddings)


async def classify_clip(image_bytes: bytes, filename: str) -> ClassificationResult | None:
    """
    Use fal.ai CLIP endpoint to generate image embeddings, then compute
    cosine similarity against cached text embeddings of all category descriptions.
    """
    if not FAL_KEY:
        _warn_clip_disabled("predict")
        return None

    logger.info("vision_classifier: attempting CLIP classification via fal.ai")

    try:
        # Encode image as base64 data URI
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        # Detect MIME type from magic bytes
        mime = "image/jpeg"
        if image_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"
        data_uri = f"data:{mime};base64,{b64_image}"

        # 1) Get image embedding
        async with httpx.AsyncClient(timeout=30.0) as client:
            img_resp = await client.post(
                FAL_CLIP_URL,
                headers={
                    "Authorization": f"Key {FAL_KEY}",
                    "Content-Type": "application/json",
                },
                json={"image_url": data_uri},
            )
            img_resp.raise_for_status()
            img_data = img_resp.json()
            image_embedding: list[float] = img_data.get("embedding", [])

            if not image_embedding:
                logger.warning("CLIP returned empty image embedding")
                return None

            # 2) Compare against cached text embeddings
            text_embs = await _ensure_clip_text_embeddings(client)
            similarities: list[tuple[str, float]] = []
            for cat_id, text_embedding in text_embs.items():
                sim = cosine_similarity(image_embedding, text_embedding)
                similarities.append((cat_id, sim))

            if not similarities:
                logger.warning("CLIP: no text embeddings generated")
                return None

            # Sort by similarity descending
            similarities.sort(key=lambda x: x[1], reverse=True)
            best_cat, best_sim = similarities[0]

            # Convert raw cosine similarity to a confidence via softmax
            raw_scores = [s for _, s in similarities]
            probs = softmax([s * 10.0 for s in raw_scores])  # scale for sharper softmax
            confidence = probs[0]

            logger.info(
                "CLIP classification: category=%s sim=%.4f confidence=%.4f",
                best_cat, best_sim, confidence,
            )

            return ClassificationResult(
                category_id=best_cat,
                category_confidence=min(confidence, 1.0),
                suggested_name=None,
                attributes={"top_3": [
                    {"category": similarities[i][0], "score": round(similarities[i][1], 4)}
                    for i in range(min(3, len(similarities)))
                ]},
                embedding_vector=image_embedding,
                classification_method="clip",
                model_version=f"clip:fal-ai/clip@{FAL_CLIP_URL}",
            )

    except httpx.HTTPStatusError as e:
        logger.warning("CLIP API HTTP error: %s (status %d)", e, e.response.status_code)
        return None
    except Exception as e:
        logger.warning("CLIP classification failed: %s", e)
        return None
