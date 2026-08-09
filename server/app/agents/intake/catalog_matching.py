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
# Catalog-match scoring constants (S4)
# Previously these were magic numbers scattered inline. Each strategy's score
# is now derived from text similarity where possible, clamped to a documented
# floor/ceiling reflecting how much signal that strategy actually carries.
# ---------------------------------------------------------------------------
_KEY_MATCH_FLOOR = 0.70   # item_key ILIKE: strong but partial — scale UP with title sim
_KEY_MATCH_CEIL = 0.95
_KEYWORD_FLOOR = 0.30     # keyword ILIKE: weak signal
_BRAND_SET_FLOOR = 0.50   # brand+set_code ILIKE: medium signal

# S8 (index policy, DATA_SCALING_PLAN §6): the strategy queries below all use
# leading-wildcard `ILIKE '%...%'`, which a btree index CANNOT serve — adding
# one would be dead weight. A real speedup needs a `pg_trgm` GIN index, which
# is a schema change that per index policy requires EXPLAIN ANALYZE evidence +
# a write-path benchmark first. Deferred deliberately, not forgotten: at 140k
# category_items the sequential ILIKE is acceptable; revisit when the catalog
# grows or scan latency regresses. Do NOT add a btree index here.


# ---------------------------------------------------------------------------
# Catalog matching helpers (RAG step)
# ---------------------------------------------------------------------------

async def _match_by_attributes(
    conn,
    category_id: str,
    attributes: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Match catalog items by JSONB attribute values.

    Tries the most-discriminating fields first (card_number, reference_number,
    set_code) and falls back to less-discriminating ones (set_name, brand).
    Score reflects how many fields matched and how unique they are.
    """
    if not attributes:
        return []

    results: list[dict[str, Any]] = []

    # High-discrimination fields (often unique within a category)
    high_disc = {
        "reference_number": ("reference_number", 0.95),
        "card_number": ("card_number", 0.85),
        "set_code": ("set_code", 0.85),
        "sku": ("sku", 0.95),
        "barcode": ("barcode", 0.99),
    }

    for attr_key, (json_key, score) in high_disc.items():
        val = attributes.get(attr_key)
        if val is None or val == "":
            continue
        try:
            rows = await conn.fetch(
                """
                SELECT id, category, item_key, title, brand, rarity,
                       set_code, image_url, notes, attributes_json
                FROM category_items
                WHERE category = $1
                  AND attributes_json ->> $2 = $3
                LIMIT 5
                """,
                category_id,
                json_key,
                str(val),
            )
            for row in rows:
                results.append({
                    **dict(row),
                    "_score": score,
                    "_reason": f"attr:{attr_key}",
                })
        except Exception as e:
            logger.debug(f"Attribute match query failed for {attr_key}: {e}")

    # Medium-discrimination: set_name + brand combo (high if both match)
    set_name = attributes.get("set_name")
    brand = attributes.get("brand") or attributes.get("manufacturer")
    if set_name and brand:
        try:
            rows = await conn.fetch(
                """
                SELECT id, category, item_key, title, brand, rarity,
                       set_code, image_url, notes, attributes_json
                FROM category_items
                WHERE category = $1
                  AND attributes_json ->> 'set_name' ILIKE $2
                  AND brand ILIKE $3
                LIMIT 5
                """,
                category_id,
                f"%{set_name}%",
                f"%{brand}%",
            )
            for row in rows:
                results.append({
                    **dict(row),
                    "_score": 0.80,
                    "_reason": "attr:set_name+brand",
                })
        except Exception as e:
            logger.debug(f"set+brand match failed: {e}")

    return results


async def _match_catalog_items(
    category_id: Optional[str],
    suggested_name: Optional[str],
    search_keywords: list[str],
    brand: Optional[str],
    set_code: Optional[str],
    pool,
    extracted_attributes: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """
    Multi-strategy catalog search against category_items table.

    Strategies (in order of confidence):
      0. Attribute-based JSONB match (highest — exact set_name + card_number, etc.)
      1. Exact item_key match
      2. Title match
      3. Keyword search
      4. Brand + set_code match

    Returns top 5 matches ranked by match_score (descending).
    """
    if not pool or not category_id:
        return []

    seen_ids: set[str] = set()
    matches: list[dict[str, Any]] = []

    try:
        async with pool.acquire() as conn:
            # Strategy 0: Attribute-based JSONB match (highest confidence).
            # Joins on structured fields extracted by vision (set_name, card_number,
            # reference_number, etc.) — much more reliable than fuzzy text match.
            if extracted_attributes:
                attr_matches = await _match_by_attributes(
                    conn, category_id, extracted_attributes
                )
                for row in attr_matches:
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
                            "match_score": row["_score"],
                            "match_reason": row["_reason"],
                        })
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
                            # S4: don't hardcode 0.9. An item_key ILIKE is a
                            # strong but partial signal — scale it by how well
                            # the suggested name actually matches the row's
                            # title/key, so a weak prefix hit can't outscore a
                            # near-perfect title match.
                            sim = _text_similarity(
                                suggested_name,
                                row["title"] or row["item_key"] or "",
                            )
                            score = min(_KEY_MATCH_CEIL,
                                        _KEY_MATCH_FLOOR + (1.0 - _KEY_MATCH_FLOOR) * sim)
                            matches.append({
                                "catalog_item_id": rid,
                                "item_key": row["item_key"],
                                "title": row["title"],
                                "category": row["category"],
                                "brand": row["brand"],
                                "rarity": row["rarity"],
                                "set_code": row["set_code"],
                                "image_url": row["image_url"],
                                "match_score": round(score, 4),
                                "match_reason": "item_key_match",
                            })

            # Strategy 2: Title match (first 4 significant words)
            #
            # BOTH sides must be normalised the same way. This used to normalise
            # only the query and compare it to the RAW column, which made the
            # strategy structurally incapable of matching any title containing
            # punctuation:
            #
            #   stored   "Naveen's Ukulele [6] (Cold Foil)"
            #   query    "naveens ukulele 6 cold"   (apostrophe/brackets stripped)
            #   ILIKE '%naveens ukulele 6 cold%'  ->  never matches
            #
            # Seed titles ("Goblin Offensive") are unaffected, which is why mtg
            # and lego scored 5/5 while every tcgcsv-derived category — lorcana,
            # digimon, one_piece_tcg, whose titles all carry [set] and (finish)
            # decorations — scored 0, even when fed their own title verbatim.
            # Measured by probe_canonical_key_resolution.py, 2026-07-25.
            #
            # The SQL below mirrors _normalize_for_search exactly: lowercase,
            # drop everything outside [a-z0-9 ], collapse whitespace. Keep the
            # two in sync — divergence silently reintroduces the same dead
            # strategy. No index: it is filtered by category first
            # (~10-25k rows) and docs/DATA_SCALING_PLAN.md rule 1 is
            # "default = refuse to add".
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
                          AND regexp_replace(
                                regexp_replace(lower(title), '[^a-z0-9[:space:]]', '', 'g'),
                                '\\s+', ' ', 'g'
                              ) LIKE $2
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
                            "match_score": round(max(_KEYWORD_FLOOR, sim), 4),
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
                            "match_score": round(max(_BRAND_SET_FLOOR, sim), 4),
                            "match_reason": "brand_set_match",
                        })

    except Exception as e:
        # S1: this used to swallow at debug — a schema drift on category_items
        # or a DB blip silently returned zero catalog matches for every scan
        # with no operator signal. Make it loud and counted.
        from app.ml.openai_vision import record_scan_degradation
        record_scan_degradation("catalog_match", "match_query_error", detail=str(e))
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
