"""
Multi-item detection for CollectAI.

Uses OpenAI Vision API to detect multiple collectible items in a single
photograph (e.g., shelf of items, display case) with bounding box estimates.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.config import OPENAI_API_KEY, OPENAI_VISION_MODEL

logger = logging.getLogger(__name__)

# Max items to detect in a single image
MAX_ITEMS = 10


@dataclass
class BoundingBox:
    """Relative bounding box (0.0 - 1.0 coordinates)."""
    x: float = 0.0
    y: float = 0.0
    w: float = 1.0
    h: float = 1.0


@dataclass
class DetectedItem:
    """A single item detected in a multi-item image."""
    item_index: int = 0
    bounding_box: BoundingBox = field(default_factory=BoundingBox)
    category_hint: Optional[str] = None
    suggested_name: Optional[str] = None
    confidence: float = 0.0


_MULTI_DETECT_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "multi_item_detection",
        "strict": False,
        "schema": {
            "type": "object",
            "properties": {
                "items_detected": {
                    "type": "integer",
                    "description": "Total number of distinct collectible items visible",
                },
                "items": {
                    "type": "array",
                    "description": "List of detected items with bounding boxes",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_index": {
                                "type": "integer",
                                "description": "1-based index of this item",
                            },
                            "bounding_box": {
                                "type": "object",
                                "description": "Relative bounding box (0.0-1.0)",
                                "properties": {
                                    "x": {"type": "number", "description": "Left edge (0.0-1.0)"},
                                    "y": {"type": "number", "description": "Top edge (0.0-1.0)"},
                                    "w": {"type": "number", "description": "Width (0.0-1.0)"},
                                    "h": {"type": "number", "description": "Height (0.0-1.0)"},
                                },
                            },
                            "category_hint": {
                                "type": "string",
                                "description": "Best guess category for this item",
                            },
                            "suggested_name": {
                                "type": "string",
                                "description": "Best guess name/title for this item",
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Detection confidence (0.0-1.0)",
                            },
                        },
                    },
                },
            },
            "required": ["items_detected", "items"],
        },
    },
}

_MULTI_DETECT_PROMPT = """You are analyzing a photograph that may contain MULTIPLE collectible items (shelf, display case, table, collection spread).

Your task:
1. Count the number of distinct collectible items visible
2. For each item, estimate its bounding box in relative coordinates (0.0 to 1.0)
3. Guess each item's category and name

Rules:
- Only detect clearly visible, individual collectible items
- Maximum {max_items} items
- Bounding boxes should tightly frame each item
- If only 1 item is visible, return just that item
- Categories: pokemon,mtg,yugioh,lorcana,funko,designer_toys,anime_figures,hot_toys,action_figures,vintage_toys,marvel_legends,lego,gunpla,scale_models,warhammer,retro_games,manga,comic_books,vinyl_records,sneakers,watches,blind_box,whiskey,vintage_cameras,pens,kpop_merch,disney"""


async def detect_multiple_items(
    image_bytes: bytes,
    max_items: int = MAX_ITEMS,
) -> list[DetectedItem]:
    """
    Detect multiple collectible items in a single image.

    Uses OpenAI Vision API with a specialized multi-item detection prompt.
    Returns a list of DetectedItem with bounding boxes and category hints.

    Args:
        image_bytes: Raw image bytes
        max_items: Maximum number of items to detect (default 10)

    Returns:
        List of DetectedItem, empty list on any error
    """
    if not OPENAI_API_KEY or not image_bytes:
        return []

    from workers.circuit_breaker import openai_circuit, CircuitOpenError

    try:
        openai_circuit.check()
    except CircuitOpenError:
        logger.info("OpenAI circuit open — skipping multi-item detection")
        return []

    try:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        mime = "image/jpeg"
        if image_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"

        system_prompt = _MULTI_DETECT_PROMPT.format(max_items=max_items)

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_VISION_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime};base64,{b64_image}",
                                        "detail": "high",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": "Detect all collectible items in this image.",
                                },
                            ],
                        },
                    ],
                    "response_format": _MULTI_DETECT_SCHEMA,
                    "max_tokens": 1200,
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not content:
            return []

        parsed = json.loads(content.strip())
        openai_circuit.record_success()

        items_raw = parsed.get("items", [])
        detected: list[DetectedItem] = []

        for item in items_raw[:max_items]:
            bb = item.get("bounding_box", {})
            detected.append(DetectedItem(
                item_index=item.get("item_index", len(detected) + 1),
                bounding_box=BoundingBox(
                    x=max(0.0, min(1.0, float(bb.get("x", 0)))),
                    y=max(0.0, min(1.0, float(bb.get("y", 0)))),
                    w=max(0.0, min(1.0, float(bb.get("w", 1)))),
                    h=max(0.0, min(1.0, float(bb.get("h", 1)))),
                ),
                category_hint=item.get("category_hint"),
                suggested_name=item.get("suggested_name"),
                confidence=max(0.0, min(1.0, float(item.get("confidence", 0)))),
            ))

        logger.info("Multi-item detection: found %d items", len(detected))
        return detected

    except json.JSONDecodeError as e:
        logger.warning("Multi-item detection JSON parse error: %s", e)
        openai_circuit.record_failure()
        return []
    except httpx.HTTPStatusError as e:
        logger.warning("Multi-item detection HTTP error: %s", e)
        openai_circuit.record_failure()
        return []
    except Exception as e:
        logger.warning("Multi-item detection failed: %s", e)
        openai_circuit.record_failure()
        return []
