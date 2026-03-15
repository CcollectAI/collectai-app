"""
Catalog RAG matching and re-prompt validation for the intake pipeline.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

from app.config import OPENAI_API_KEY, OPENAI_VISION_MODEL

from .helpers import _normalize_for_search, _text_similarity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Catalog matching helpers (RAG step)
# ---------------------------------------------------------------------------

async def _match_catalog_items(
    category_id: Optional[str],
    suggested_name: Optional[str],
    search_keywords: list[str],
    brand: Optional[str],
    set_code: Optional[str],
    pool,
) -> list[dict[str, Any]]:
    """
    Multi-strategy catalog search against category_items table.

    Returns top 5 matches ranked by match_score (descending).
    """
    if not pool or not category_id:
        return []

    seen_ids: set[str] = set()
    matches: list[dict[str, Any]] = []

    try:
        async with pool.acquire() as conn:
            # Strategy 1: Exact item_key match (highest confidence)
            if suggested_name:
                normalized = _normalize_for_search(suggested_name)
                if normalized:
                    rows = await conn.fetch(
                        """
                        SELECT id, category, item_key, title, brand, rarity,
                               set_code, image_url, notes
                        FROM category_items
                        WHERE category = $1
                          AND lower(item_key) ILIKE $2
                        LIMIT 3
                        """,
                        category_id,
                        f"%{normalized[:60]}%",
                    )
                    for row in rows:
                        rid = str(row["id"])
                        if rid not in seen_ids:
                            seen_ids.add(rid)
                            matches.append({
                                "catalog_item_id": rid,
                                "item_key": row["item_key"],
                                "title": row["title"],
                                "category": row["category"],
                                "brand": row["brand"],
                                "rarity": row["rarity"],
                                "set_code": row["set_code"],
                                "image_url": row["image_url"],
                                "match_score": 0.9,
                                "match_reason": "item_key_match",
                            })

            # Strategy 2: Title match (first 4 significant words)
            if suggested_name:
                words = _normalize_for_search(suggested_name).split()[:4]
                title_query = " ".join(words)
                if title_query:
                    rows = await conn.fetch(
                        """
                        SELECT id, category, item_key, title, brand, rarity,
                               set_code, image_url, notes
                        FROM category_items
                        WHERE category = $1
                          AND title ILIKE $2
                        LIMIT 5
                        """,
                        category_id,
                        f"%{title_query}%",
                    )
                    for row in rows:
                        rid = str(row["id"])
                        if rid not in seen_ids:
                            seen_ids.add(rid)
                            sim = _text_similarity(suggested_name, row["title"] or "")
                            matches.append({
                                "catalog_item_id": rid,
                                "item_key": row["item_key"],
                                "title": row["title"],
                                "category": row["category"],
                                "brand": row["brand"],
                                "rarity": row["rarity"],
                                "set_code": row["set_code"],
                                "image_url": row["image_url"],
                                "match_score": round(sim, 4),
                                "match_reason": "title_match",
                            })

            # Strategy 3: Keyword search from vision
            for kw in search_keywords[:5]:
                kw_clean = _normalize_for_search(kw)
                if not kw_clean or len(kw_clean) < 2:
                    continue
                rows = await conn.fetch(
                    """
                    SELECT id, category, item_key, title, brand, rarity,
                           set_code, image_url, notes
                    FROM category_items
                    WHERE category = $1
                      AND (title ILIKE $2 OR item_key ILIKE $2 OR brand ILIKE $2)
                    LIMIT 3
                    """,
                    category_id,
                    f"%{kw_clean}%",
                )
                for row in rows:
                    rid = str(row["id"])
                    if rid not in seen_ids:
                        seen_ids.add(rid)
                        sim = _text_similarity(
                            suggested_name or kw, row["title"] or ""
                        )
                        matches.append({
                            "catalog_item_id": rid,
                            "item_key": row["item_key"],
                            "title": row["title"],
                            "category": row["category"],
                            "brand": row["brand"],
                            "rarity": row["rarity"],
                            "set_code": row["set_code"],
                            "image_url": row["image_url"],
                            "match_score": round(max(0.3, sim), 4),
                            "match_reason": f"keyword:{kw_clean}",
                        })

            # Strategy 4: Brand + set_code combined filter
            if brand and set_code:
                rows = await conn.fetch(
                    """
                    SELECT id, category, item_key, title, brand, rarity,
                           set_code, image_url, notes
                    FROM category_items
                    WHERE category = $1
                      AND brand ILIKE $2
                      AND set_code ILIKE $3
                    LIMIT 5
                    """,
                    category_id,
                    f"%{_normalize_for_search(brand)}%",
                    f"%{_normalize_for_search(set_code)}%",
                )
                for row in rows:
                    rid = str(row["id"])
                    if rid not in seen_ids:
                        seen_ids.add(rid)
                        sim = _text_similarity(
                            suggested_name or "", row["title"] or ""
                        )
                        matches.append({
                            "catalog_item_id": rid,
                            "item_key": row["item_key"],
                            "title": row["title"],
                            "category": row["category"],
                            "brand": row["brand"],
                            "rarity": row["rarity"],
                            "set_code": row["set_code"],
                            "image_url": row["image_url"],
                            "match_score": round(max(0.5, sim), 4),
                            "match_reason": "brand_set_match",
                        })

    except Exception as e:
        logger.debug("Catalog matching error: %s", e)
        return []

    # Sort by match_score descending, return top 5
    matches.sort(key=lambda m: m["match_score"], reverse=True)
    return matches[:5]


# ---------------------------------------------------------------------------
# Re-prompt validation — Step 2.6
# ---------------------------------------------------------------------------

_REPROMPT_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "reprompt_validation",
        "strict": False,
        "schema": {
            "type": "object",
            "properties": {
                "selected_index": {
                    "type": "integer",
                    "description": (
                        "0 = none match (original is better), "
                        "1-N = catalog candidate number"
                    ),
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence in this selection (0.0-1.0)",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of why this candidate was chosen",
                },
            },
            "required": ["selected_index", "confidence", "reasoning"],
        },
    },
}


async def _validate_with_reprompt(
    image_bytes: bytes,
    initial_name: str,
    initial_category: str,
    catalog_candidates: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """
    Send the image + top catalog candidates back to OpenAI Vision for a
    focused validation pass.  Returns {"selected_index", "confidence",
    "reasoning"} or None on any error (graceful degradation).
    """
    import httpx

    if not OPENAI_API_KEY:
        return None

    from workers.circuit_breaker import openai_circuit, CircuitOpenError

    try:
        openai_circuit.check()
    except CircuitOpenError:
        logger.info("OpenAI circuit open — skipping reprompt validation")
        return None

    try:
        # Build numbered candidates text
        lines: list[str] = []
        for i, c in enumerate(catalog_candidates, 1):
            parts = [f"{i}. {c.get('title', '?')}"]
            if c.get("brand"):
                parts.append(f"brand={c['brand']}")
            if c.get("rarity"):
                parts.append(f"rarity={c['rarity']}")
            if c.get("set_code"):
                parts.append(f"set={c['set_code']}")
            if c.get("item_key"):
                parts.append(f"key={c['item_key']}")
            lines.append(" | ".join(parts))
        candidates_text = "\n".join(lines)

        system_prompt = (
            "You are verifying a collectible item identification. "
            f'You previously identified this item as:\n'
            f'"{initial_name}" (category: {initial_category})\n\n'
            f"Compare the image against these catalog candidates:\n"
            f"{candidates_text}\n\n"
            "Rules:\n"
            "- Select the number (1-N) of the catalog item that BEST matches the image\n"
            "- Select 0 if NONE of the catalog items match — your original identification is better\n"
            "- Focus on visual details: art, text, packaging, colors, logos\n"
            "- Be decisive — pick the single best match"
        )

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        mime = "image/jpeg"
        if image_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"

        async with httpx.AsyncClient(timeout=30.0) as client:
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
                                        "detail": "auto",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": "Which catalog candidate best matches this image?",
                                },
                            ],
                        },
                    ],
                    "response_format": _REPROMPT_SCHEMA,
                    "max_tokens": 300,
                    "temperature": 0.1,
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
            return None

        parsed = json.loads(content.strip())
        idx = int(parsed.get("selected_index", -1))
        conf = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
        reasoning = str(parsed.get("reasoning", ""))

        if idx < 0 or idx > len(catalog_candidates):
            logger.warning("Reprompt returned out-of-range index %d", idx)
            return None

        openai_circuit.record_success()
        return {
            "selected_index": idx,
            "confidence": conf,
            "reasoning": reasoning,
        }

    except Exception as e:
        openai_circuit.record_failure()
        logger.warning("Reprompt validation failed (graceful skip): %s", e)
        return None
