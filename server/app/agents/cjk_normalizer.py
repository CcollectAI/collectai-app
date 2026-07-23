"""CJK listing-title enrichment via Kimi K2 (Moonshot).

Many of our sold comps come from Japanese/Asian marketplaces (Yahoo Auctions JP,
Suruga-ya, Mercari, Mandarake) whose listing titles are Japanese. Our canonical
attribute_normalizer works on already-structured `attributes` dicts; it does not
read a free-text Japanese *title*. Kimi K2 is notably stronger at CJK than the
gpt-4o-mini / Haiku models we run elsewhere, so this module asks Kimi to parse a
Japanese title into structured attrs (character, series, edition, condition, plus
English/romaji renderings) that get merged into `market_hits.attrs` and flow into
the data flywheel (category_items.attributes_json.market_observed).

This is a NEW use, not a swap — it fills a gap the existing pipeline can't cover.
It is:
  * opt-in            — CJK_NORMALIZE_ENABLED (default off), so prod is unchanged
  * CJK-gated         — only fires on titles that actually contain CJK characters
  * spend-capped      — goes through SpendTracker under the 'kimi_cjk' key, so the
                        global monthly circuit breaker bounds cost
  * fail-open         — any error returns {} and the write proceeds unchanged

Kimi is NOT Anthropic-compatible; this deliberately uses a raw OpenAI-shaped HTTP
call (Moonshot exposes an OpenAI-compatible endpoint), the same pattern as
ml/openai_vision.py.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# --- config (opt-in; shares the Kimi credentials with claude_estimator) --------
ENABLED = os.getenv("CJK_NORMALIZE_ENABLED", "false").strip().lower() in ("1", "true", "yes")
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1")
KIMI_MODEL = os.getenv("KIMI_MODEL", "kimi-k2-0711-preview")
MAX_TOKENS_OUT = int(os.getenv("CJK_NORMALIZE_MAX_TOKENS", "300"))
# Kimi K2 ~$0.60/Mtok in, $2.50/Mtok out; short prompt + short output ≈ €0.0012.
COST_PER_CALL_EUR = float(os.getenv("CJK_NORMALIZE_COST_EUR", "0.0012"))

# JP/Asian marketplaces whose titles are commonly CJK. The real gate is CJK
# character presence (below); this set is an optional extra filter callers can
# consult, but enrichment does not depend on it — a CJK title from any source is
# worth structuring.
JP_SOURCES = frozenset({
    "yahoo_auctions", "yahoo_auctions_sold", "suruga_ya", "surugaya",
    "mandarake", "mercari", "mercari_jp", "rakuma", "rakuten",
})

# Codepoint ranges that indicate Japanese/Chinese/Korean text. Covers CJK
# symbols/punctuation, hiragana, katakana, CJK unified ideographs (kanji/hanzi),
# and fullwidth forms.
_CJK_RANGES = (
    (0x3000, 0x303F),   # CJK symbols & punctuation
    (0x3040, 0x309F),   # hiragana
    (0x30A0, 0x30FF),   # katakana
    (0x3400, 0x4DBF),   # CJK ext A
    (0x4E00, 0x9FFF),   # CJK unified ideographs
    (0xAC00, 0xD7A3),   # hangul syllables
    (0xF900, 0xFAFF),   # CJK compatibility ideographs
    (0xFF00, 0xFFEF),   # fullwidth / halfwidth forms
)


def has_cjk(text: str) -> bool:
    """True if *text* contains at least one CJK/Japanese/Korean character."""
    for ch in text:
        cp = ord(ch)
        for lo, hi in _CJK_RANGES:
            if lo <= cp <= hi:
                return True
    return False


_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_listing_attributes",
        "description": (
            "Extract structured collectible attributes from a Japanese (or other "
            "CJK) marketplace listing title. Return only fields you can identify "
            "with confidence; omit anything uncertain. Values must be in English "
            "(translate/transliterate as needed)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "character": {"type": "string", "description": "Main character/subject, English (e.g. 'Pikachu', 'Nezuko')."},
                "series": {"type": "string", "description": "Franchise/series, English (e.g. 'Pokemon', 'Demon Slayer')."},
                "edition": {"type": "string", "description": "Edition/version if stated (e.g. '1st Edition', 'Limited', 'Prize')."},
                "variant": {"type": "string", "description": "Colour/variant/pose if stated."},
                "condition": {"type": "string", "description": "Condition, normalized: one of new, like_new, used, damaged, unknown."},
                "title_en": {"type": "string", "description": "Concise English rendering of the full title."},
                "title_romaji": {"type": "string", "description": "Romaji transliteration of the Japanese title, if applicable."},
            },
            "additionalProperties": False,
        },
    },
}

_SYSTEM = (
    "You are a cataloguing assistant for a collectibles marketplace. You read a "
    "single Japanese/CJK listing title and call extract_listing_attributes exactly "
    "once with the structured fields you can confidently identify. Do not guess; "
    "omit fields you are unsure about."
)

_ALLOWED_KEYS = {"character", "series", "edition", "variant", "condition", "title_en", "title_romaji"}


async def enrich_cjk_attrs(
    title: str,
    category: Optional[str] = None,
    existing_attrs: Optional[dict] = None,
) -> dict:
    """Return a dict of Kimi-extracted attributes for a CJK *title*, or {}.

    Never raises. Returns {} when disabled, when the title has no CJK content,
    when the Kimi key is missing, when the spend budget is exhausted, or on any
    API/parse error — callers merge the result as gap-fill and proceed regardless.
    """
    if not ENABLED or not KIMI_API_KEY:
        return {}
    title = (title or "").strip()
    if not title or not has_cjk(title):
        return {}

    # Spend gate — same circuit breaker as the rest of the paid pipeline.
    try:
        from app.lib.spend_tracker import SpendTracker
        tracker = SpendTracker.instance() if hasattr(SpendTracker, "instance") else SpendTracker()
        tracker.check("kimi_cjk")
    except Exception as e:  # noqa: BLE001 — BudgetExceededError + import failures
        logger.warning("[cjk_normalizer] budget gate blocked: %s", e)
        return {}

    import json as _json
    try:
        import httpx
    except ImportError:
        logger.error("[cjk_normalizer] httpx not installed; cannot call Kimi")
        return {}

    user = f"Category: {category or 'unknown'}\nTitle: {title}"
    payload = {
        "model": KIMI_MODEL,
        "max_tokens": MAX_TOKENS_OUT,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        "tools": [_TOOL],
        "tool_choice": {"type": "function", "function": {"name": "extract_listing_attributes"}},
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{KIMI_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {KIMI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("[cjk_normalizer] Kimi call failed (%s): %s", title[:40], e)
        return {}

    try:
        tracker.record("kimi_cjk", cost_eur=COST_PER_CALL_EUR)
    except Exception:
        pass

    try:
        tool_calls = data["choices"][0]["message"].get("tool_calls") or []
        extracted = _json.loads(tool_calls[0]["function"]["arguments"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        logger.warning("[cjk_normalizer] parse failed (%s): %s", title[:40], e)
        return {}

    if not isinstance(extracted, dict):
        return {}
    # Keep only known, non-empty string fields.
    out = {
        k: str(v).strip()
        for k, v in extracted.items()
        if k in _ALLOWED_KEYS and isinstance(v, (str, int, float)) and str(v).strip()
    }
    return out
