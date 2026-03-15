"""
CLIP embedding and pre-filtering logic via fal.ai.

Generates image embeddings and compares them against cached text embeddings
of all category descriptions for zero-shot category matching.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.config import FAL_KEY, FAL_CLIP_URL
from app.ml.vision_helpers import (
    ALL_CATEGORIES,
    CATEGORY_DESCRIPTIONS,
    ClassificationResult,
    cosine_similarity,
    softmax,
)

logger = logging.getLogger(__name__)

# Cached text embeddings for category descriptions.  Populated once on first
# CLIP classification call, then reused for all subsequent calls.  This avoids
# 37+ fal.ai API calls per scan — only 1 (image) is needed after warm-up.
_clip_text_embeddings: dict[str, list[float]] = {}
_clip_text_embeddings_loaded: bool = False


async def _ensure_clip_text_embeddings(client: httpx.AsyncClient) -> dict[str, list[float]]:
    """Fetch and cache text embeddings for all category descriptions (once)."""
    global _clip_text_embeddings_loaded

    if _clip_text_embeddings_loaded and _clip_text_embeddings:
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
    return _clip_text_embeddings


async def classify_clip(image_bytes: bytes, filename: str) -> ClassificationResult | None:
    """
    Use fal.ai CLIP endpoint to generate image embeddings, then compute
    cosine similarity against cached text embeddings of all category descriptions.
    """
    if not FAL_KEY:
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
