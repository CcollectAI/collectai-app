"""
Catalog RAG matching and re-prompt validation for the intake pipeline.
"""

from __future__ import annotations

import base64
import json
import re
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


_AMBIGUOUS_SCORE_CAP = 0.5


def _norm_number(value: Optional[str]) -> Optional[str]:
    """'4/102' -> '4', '#161' -> '161', '007' -> '7', 'LOB-001' -> 'lob-1'."""
    if not value:
        return None
    v = value.strip().lower().lstrip("#").split("/")[0].strip()
    if not v:
        return None
    head, sep, tail = v.rpartition("-")
    tail = tail.lstrip("0") or "0"
    return f"{head}{sep}{tail}" if sep else tail


def _key_number(item_key: Optional[str]) -> Optional[str]:
    """The number a catalog key ends with: 'svp-svp-161' -> '161'."""
    if not item_key:
        return None
    last = item_key.lower().rsplit("-", 1)[-1]
    return (last.lstrip("0") or "0") if last else None


# A title match whose catalogue NUMBER contradicts the number read off the
# item is not an identity. Capped below the orchestrator's adopt threshold
# (0.75) and the writers' (0.6 add-manual) so it can only be an alternative.
_NUMBER_CONFLICT_CAP = 0.55
# Printed number + all title words (Strategy 0b): the floor is above the
# orchestrator's adopt threshold (0.75); an exact title reaches 1.0.
_PRINTED_NUMBER_TITLE_FLOOR = 0.8


def norm_printed(value: Optional[str]) -> str:
    """'006/165' -> '6/165', 'TG03/30' -> 'tg3/30'. Leading zeros dropped on each
    side of the slash: vision reads the card's zero-padded print, the catalogue
    stores '6/165' (2026-09-26: an exact compare capped the right row).
    Mirrored in SQL by _PRINTED_SQL — keep the two identical."""
    return re.sub(r"(^|/|[a-z])0+(\d)", r"\1\2", (value or "").strip().lower())


# SQL twin of norm_printed, applied to the catalogue's `number`.
_PRINTED_SQL = "regexp_replace(lower(attributes_json ->> 'number'), '(^|/|[a-z])0+([0-9])', '\\1\\2', 'g')"


def number_agrees(read: Optional[str], printed: Optional[str], card_no: Optional[str]) -> Optional[bool]:
    """Does a catalogue row's number agree with the number read off the item?

    None = cannot tell (nothing read, or the row stores no number).
    The PRINTED form ("4/102", catalogue key `number`) is compared whole when
    both sides have it: it is what separates Base Set Charizard 4/102 from the
    Celebrations reprint 4/25 — the same "4" in `card_number`. Otherwise the
    heads are compared through _norm_number ('4/102' -> '4', 'BT5-087' -> 'bt5-87').
    """
    raw = (read or "").strip()
    if not raw:
        return None
    if "/" in raw and printed and "/" in printed:
        return norm_printed(printed) == norm_printed(raw)
    want = _norm_number(raw)
    for v in (card_no, printed):
        if v and str(v).strip():
            return _norm_number(str(v)) == want
    return None


def resolve_title_ties(matches: list[dict], set_code: Optional[str], number: Optional[str]) -> tuple[list[dict], bool]:
    """Resolve a tie at the top between DIFFERENT catalog rows.

    The pipeline scores an exact title 1.0, so "Charizard ex" in `pokemon`
    returned FIVE rows at 1.0 and `best` was simply the first — a confident,
    arbitrary identity (measured 2026-09-24: sv4pt5-234 for a member holding
    the SVP #161 promo, even with set_code "svp" sent). That key decides the
    item's price and which Target Hit watchers are alerted, and a wrong key is
    worse than none (items_router `_resolve_canonical_key`).

    When the tie cannot be resolved, EVERY tied row's score is capped at
    _AMBIGUOUS_SCORE_CAP (below every caller's write threshold: 0.6 add-manual,
    0.75 items_router) and marked `ambiguous`, so no caller can auto-assign a
    guessed identity. Returns (matches, ambiguous?).
    """
    if not matches:
        return matches, False
    top = float(matches[0].get("match_score", 0.0))
    tied = [m for m in matches if float(m.get("match_score", 0.0)) >= top - 1e-9]
    if len({m.get("item_key") for m in tied}) < 2:
        return matches, False
    pool = tied
    agreeing = [m for m in pool if m.get("number_agrees") is True]
    if agreeing:
        pool = agreeing
    want_num = _norm_number(number)
    if want_num:
        by_num = [m for m in pool if _key_number(m.get("item_key")) == want_num.rsplit("-", 1)[-1]]
        if by_num:
            pool = by_num
    if set_code:
        sc = set_code.strip().lower()
        by_set = [m for m in pool if (m.get("set_code") or "").lower() == sc]
        if by_set:
            pool = by_set
    if len({m.get("item_key") for m in pool}) == 1:
        chosen = pool[0]
        rest = [m for m in matches if m is not chosen]
        return [chosen, *rest], False
    capped = []
    for m in matches:
        if m in tied:
            m = {**m, "match_score": min(float(m.get("match_score", 0.0)), _AMBIGUOUS_SCORE_CAP), "ambiguous": True}
        capped.append(m)
    return capped, True


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

    _attrs = extracted_attributes or {}
    read_number = str(_attrs.get("card_number") or _attrs.get("number") or "").strip()

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
            # Strategy 0b: the PRINTED number read off the item ("4/102") plus
            # every word of the catalogue title present in the name that was
            # read (2026-09-26). Vision often decorates the name — "Charizard
            # 1st Edition" — which no title strategy matches, so Base Set 4/102
            # never became a candidate. The printed number alone is not an
            # identity (4/102 is also HGSS Drapion), the title words alone are
            # 28 Charizards; together they are one card.
            if suggested_name and "/" in read_number:
                name_tokens = set(_normalize_for_search(suggested_name).split())
                rows = await conn.fetch(
                    """
                    SELECT id, category, item_key, title, brand, rarity,
                           set_code, image_url, notes
                    FROM category_items
                    WHERE category = $1
                      AND """ + _PRINTED_SQL + """ = $2
                    LIMIT 20
                    """,
                    category_id,
                    norm_printed(read_number),
                )
                for row in rows:
                    rid = str(row["id"])
                    title_tokens = set(_normalize_for_search(row["title"] or "").split())
                    if rid in seen_ids or not title_tokens or not title_tokens <= name_tokens:
                        continue
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
                        # Scaled by how much of the name the title covers: two
                        # rows can share a printed number AND fit inside the
                        # name — 151 "Charizard ex" 6/165 and Expedition
                        # "Charizard" 6/165 — and the fuller title is the card.
                        "match_score": round(
                            _PRINTED_NUMBER_TITLE_FLOOR
                            + (1.0 - _PRINTED_NUMBER_TITLE_FLOOR)
                            * _text_similarity(suggested_name, row["title"] or ""),
                            4,
                        ),
                        "match_reason": "printed_number+title",
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
                    # Ranked by the number read off the item BEFORE the LIMIT
                    # (2026-09-26). It was an unordered LIMIT 5: "Charizard" has
                    # 28 exact-title rows in pokemon, the five returned were
                    # arbitrary, and a QuickScan of Base Set 4/102 adopted the
                    # Celebrations reprint 4/25 at score 1.00 and priced it at
                    # EUR 154 against the card's EUR 1,159 — base1-4 was never
                    # even a candidate.
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
                        ORDER BY (""" + _PRINTED_SQL + """ = $3) DESC NULLS LAST,
                                 (lower(attributes_json ->> 'card_number') = lower($4)) DESC NULLS LAST
                        LIMIT 5
                        """,
                        category_id,
                        f"%{title_query}%",
                        norm_printed(read_number),
                        read_number.split("/")[0].strip(),
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

    # Number agreement, for EVERY candidate whatever strategy found it: one
    # lookup of the catalogue's own numbers. A contradicting row keeps its place
    # as an alternative but can no longer be adopted (_NUMBER_CONFLICT_CAP).
    if read_number and matches:
        try:
            num_rows = await pool.fetch(
                """
                SELECT id::text AS id,
                       attributes_json ->> 'number' AS printed,
                       attributes_json ->> 'card_number' AS card_no
                FROM category_items
                WHERE id = ANY($1::uuid[])
                """,
                [m["catalog_item_id"] for m in matches],
            )
            nums = {r["id"]: (r["printed"], r["card_no"]) for r in num_rows}
            for m in matches:
                printed, card_no = nums.get(m["catalog_item_id"], (None, None))
                agrees = number_agrees(read_number, printed, card_no)
                m["number_agrees"] = agrees
                if agrees is False:
                    m["match_score"] = min(float(m["match_score"]), _NUMBER_CONFLICT_CAP)
        except Exception as e:
            logger.warning("[catalog_match] number check failed: %s", e)

    # Sort by match_score descending, return top 5
    matches.sort(key=lambda m: m["match_score"], reverse=True)
    attrs = extracted_attributes or {}
    matches, _ = resolve_title_ties(
        matches, set_code, attrs.get("card_number") or attrs.get("number"),
    )
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
