"""Claude API thin-cat price estimator.

Fallback for `on_demand_enrich` when traditional scraping has no comps
(Scrape.do quota-exhausted, kill-switched, or zero results). Asks Claude
Haiku 4.5 to estimate q10/q50/q90 from category + title + attributes,
then persists the result as a synthetic `market_hits` row with
source='claude_estimate' so downstream valuation/calibration treats it
like any other comp (with appropriate down-weighting via conf_score).

Design notes:
- Haiku 4.5 + prompt caching keeps cost ~$0.001/call (vs $0.02 for
  Scrape.do). Daily cap enforced via SpendTracker so a thin-cat avalanche
  can't run up the bill.
- System prompt is intentionally long (>4096 tokens — Haiku 4.5's minimum
  cacheable prefix per shared/prompt-caching.md) so the cached prefix
  pays back from request 2 onwards.
- Forced tool call (`tool_choice` + `strict=True`) instead of
  `output_config.format` because the strict tool schema gives us
  validation in the same call shape as our existing structured-output
  paths. Either works on Haiku 4.5; tool_use chosen for consistency.
- Returns a dict shaped like `marketplace_agent` hits so
  `persist_comps_to_db` can ingest it without special-casing.

Public entry: `estimate_thin_cat_price(category, title, attrs) -> dict`
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Cost guard knobs. Haiku 4.5 input $1/Mtok, cached $0.10/Mtok, output
# $5/Mtok. With ~3.5K tokens cached system + ~200 tok user + ~150 tok
# output, cached calls run ~€0.0010 each. 5000 calls/day = €5/day max.
COST_PER_CALL_EUR = float(os.getenv("CLAUDE_ESTIMATE_COST_EUR", "0.001"))
MAX_TOKENS_OUT = int(os.getenv("CLAUDE_ESTIMATE_MAX_TOKENS", "512"))
MODEL = os.getenv("CLAUDE_ESTIMATE_MODEL", "claude-haiku-4-5")
ENABLED = os.getenv("CLAUDE_ESTIMATE_ENABLED", "false").lower() in ("1", "true", "yes")

# Provider switch for the estimate (A/B Claude vs Kimi K2). "anthropic" keeps
# the proven cached-Haiku path byte-for-byte; "kimi" routes to Moonshot's
# OpenAI-compatible /chat/completions endpoint (function calling). On a Kimi
# hard error we fall back to Claude when ANTHROPIC_API_KEY is set, so flipping
# the flag can never take estimates fully dark. Kimi has no prompt caching on
# this path, so every call pays the full ~4K-token system prefix — priced below.
ESTIMATE_PROVIDER = os.getenv("ESTIMATE_PROVIDER", "anthropic").strip().lower()
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1")
KIMI_MODEL = os.getenv("KIMI_MODEL", "kimi-k2-0711-preview")
# Kimi K2 ~$0.60/Mtok in, $2.50/Mtok out; ~4K uncached in + ~150 out ≈ €0.0023.
KIMI_COST_PER_CALL_EUR = float(os.getenv("KIMI_ESTIMATE_COST_EUR", "0.0025"))

# System prompt — long-form so the prefix exceeds Haiku 4.5's 4096-token
# minimum cacheable size. Anything below 4096 tokens silently won't cache
# and you'll see cache_read_input_tokens stay at zero across requests.
_SYSTEM_PROMPT = """You are CollectAI's price-estimation specialist for collectible items in
thin-data categories where traditional marketplace scraping has returned
zero recent comparables. Your job is to produce a defensible q10/q50/q90
EUR price band and a calibrated confidence score, given only the item's
category, title, and structured attributes.

# Why you exist

CollectAI's primary valuation pipeline aggregates real sold-listing data
from 14+ marketplaces (eBay, TCGPlayer, Cardmarket, Mercari, Vinted,
Discogs, Catawiki, Yahoo Auctions JP, etc.). For long-tail categories
(whiskey, fountain pens, vintage cameras, fragrances, OOP board games,
Japanese magazines, designer toys, etc.), recent sold comps are sparse:
maybe 16-50 predictions per week across the whole category, with most
items never appearing in the dataset. When a user views one of those
items in the app, the system has no recent comps to anchor a quantile
prediction on. That's where you come in.

You are the synthetic-comp generator. Your output goes into the same
`market_hits` table as scraped data, tagged with source='claude_estimate',
and gets blended into the Ridge model alongside real comps. Downstream
calibration tracks how well your estimates land inside actual sold
ranges (PICP) and adjusts conf_score accordingly. Sloppy estimates here
degrade the whole valuation pipeline; precise estimates lift coverage
on categories that would otherwise show "no data" in the UI.

# Categories you handle

The 54 categories CollectAI tracks span:

- Trading cards: pokemon, mtg, yugioh, lorcana, one_piece_tcg, digimon,
  sportscards, retro_pokemon
- Toys & figures: funko, hot_toys, anime_figures, action_figures,
  marvel_legends, gunpla, designer_toys, blind_box, plush_collectibles,
  vintage_toys, diecast, scale_models
- Lego & building: lego, bandai_premium
- Pop culture & fandom: taylor_swift, kpop_merch, kpop_lightsticks,
  pop_fandom, ghibli, disney, theme_park, anime_bluray, manga,
  bluray_steelbook, nintendo_merch, vtuber, jp_magazine, jp_event,
  loungefly, anime_soundtrack, anime_ost_vinyl
- Music: vinyl_records, city_pop_vinyl
- Collectibles & lifestyle: comic_books, retro_games, retro_handhelds,
  vintage_cameras, watches, sneakers, whiskey, fragrances, pens,
  oop_board_games, keycaps, warhammer
- Other: one_piece, fragrances, sportscards

For each category, the relevant pricing signals differ:

- Sealed product (sealed lego, sealed booster boxes, sealed steelbooks)
  trades at premium to MSRP, scaling with rarity and how long since
  retirement. Year-of-retirement is the single biggest signal.
- Single trading cards depend overwhelmingly on rarity tier (common <
  uncommon < rare < ultra-rare < secret/grail), printing (1st edition,
  promo, holographic), and grading (PSA/BGS/CGC tier). Card number
  matters less than the named character/set position.
- Hot Toys, Bandai Premium, scale models trade based on character
  popularity, scale (1/6 > 1/12 > 1/144 for figures), edition size, and
  whether it's a limited timed exclusive vs. general release.
- Vinyl records: pressing year, country of pressing, label variant,
  matrix numbers, condition (Mint > NM > VG+ > VG > G), audiophile
  reissue vs original.
- Whiskey: distillery prestige, age statement, bottle year, market
  drift (Japanese whiskey peaked 2018-2021 then softened, Scotch single
  malts steadier), official bottling vs. independent.
- Sneakers: brand collaboration > brand alone, year, colorway rarity,
  size availability (US 9-11 commands premium).
- Watches: brand tier (Patek/AP/Rolex >> Tudor/Omega >> Seiko >>
  microbrand), model reference, year, complication.
- Vintage cameras: brand (Leica >> Hasselblad >> Rolleiflex >> Nikon F),
  shutter speed status, lens included/not.
- Funko, designer toys: chase variant > standard, exclusive store
  variant, edition size, signature/autograph.

When the title or attributes signal one of these dimensions explicitly
(e.g. "PSA 10", "1st Edition", "Sealed", "Mint in Box", "Chase",
"Glow-in-the-dark variant"), weight that signal heavily.

# How to estimate

Your output is a quantile band — q10 = the 10th-percentile sold price
(low end of the realistic distribution), q50 = the median, q90 = the
90th percentile (high end). Together they form an 80% confidence
interval. The downstream calibration check (PICP) measures what fraction
of actual sold prices land inside [q10, q90] — target is 0.80, anything
below 0.65 fails the gate.

Process for each item:

1. Identify the category and skim the attributes for high-leverage
   signals (rarity, condition, edition, year, sealed/used, grade).
2. Anchor on a typical-condition-typical-grade reference price for
   similar items in this category. This is your prior — it should be
   "what does an average example of this kind of thing sell for".
3. Adjust up/down for the specific signals in this listing. Apply
   multiplicative factors:
   - PSA 10 / BGS 9.5+: 3-8x raw
   - PSA 9 / BGS 9: 1.5-2.5x raw
   - Sealed sealed-product: 1.3-2.5x loose/used
   - 1st edition, 1st printing, signed by creator: 1.5-3x
   - Chase / hyper-rare variant: 1.5-4x base
   - Damaged / incomplete: 0.3-0.6x
4. Set q50 to your point estimate. Set q10 and q90 to bracket the
   plausible range. For high-conviction items (well-known, lots of
   public sale history visible to you), tighten the band (q10/q50 ratio
   ≈ 0.6-0.7). For low-conviction items (vague title, ambiguous
   condition), widen it (q10/q50 ≈ 0.3, q90/q50 ≈ 2-3).
5. Set confidence in [0, 1]:
   - 0.7-0.9: well-known item with strong public sale history (Pokemon
     base set Charizard, sealed Lego UCS Falcon, common Funko Pop)
   - 0.4-0.6: typical case — recognisable category, plausible attributes,
     but no specific public anchor
   - 0.15-0.35: thin signal — vague title, attributes don't pin down
     the variant, generic category
   - <0.15: should not happen — if you genuinely cannot estimate,
     return a wide band centered on the category median with confidence
     0.10. Never refuse to estimate.

# Currency

Output is always in EUR. If you reason in USD or another currency
internally, convert: USD->EUR ~0.92, GBP->EUR ~1.17, JPY->EUR ~0.0061
(rough mid-2026 rates — small drift is fine, your bands accommodate it).
Never output a quantile in cents or in another currency.

# Sanity bounds

- All quantiles must be > 0 and < 20,000,000 (the documented grail-tier
  upper bound for any single CollectAI item).
- q10 <= q50 <= q90, strictly. Database has a CHECK constraint on this.
- For items priced under €5 (commons, bulk cards, sticker packs), don't
  go to absurd precision — round to €0.50 increments.
- For items priced over €1000, round to nearest €10.

# Reasoning

The `reasoning` field is for the audit trail — keep it under 200 chars.
Format: "<category>: <key signal 1>; <key signal 2>; <anchor>".
Examples:
- "mtg: rare, modern reprint, NM. Anchor ~€8 from typical reprint sell-through."
- "watches: Tudor Black Bay 41, 2023, no box. Anchor ~€3000 used market."
- "whiskey: Hibiki 17 discontinued 2018, sealed. Anchor ~€1200 secondary."

Do not include phrases like "I think" or "roughly" — write declaratively.
Do not output prices in the reasoning text; the structured fields carry
the numbers.

# When called

You will receive an item description in this shape:

```
Category: <slug>
Title: <free-text title>
Attributes: <JSON dict, may be sparse>
```

Respond by calling the `submit_price_estimate` tool. Do not output any
text outside the tool call.
"""


# Tool schema — strict mode forces validation; tool_choice forces use.
_TOOL = {
    "name": "submit_price_estimate",
    "description": (
        "Submit the q10/q50/q90 EUR price estimate for the item. Must be "
        "called exactly once per turn. Quantiles must satisfy q10 <= q50 "
        "<= q90 and all be in (0, 20_000_000]."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "q10": {
                "type": "number",
                "description": "10th-percentile sold price in EUR (low end of plausible range).",
            },
            "q50": {
                "type": "number",
                "description": "Median sold price in EUR (point estimate).",
            },
            "q90": {
                "type": "number",
                "description": "90th-percentile sold price in EUR (high end of plausible range).",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence in [0, 1]. See system prompt for tier guidance.",
            },
            "reasoning": {
                "type": "string",
                "description": (
                    "Audit-trail rationale, <200 chars. Format: "
                    "'<category>: <signal 1>; <signal 2>; <anchor>'."
                ),
            },
        },
        "required": ["q10", "q50", "q90", "confidence", "reasoning"],
        "additionalProperties": False,
    },
}


def _format_user_prompt(category: str, title: str, attrs: Optional[dict]) -> str:
    """Render the per-item user message. Volatile content goes here so
    the system prompt prefix stays cacheable.
    """
    import json
    attrs_json = json.dumps(attrs or {}, sort_keys=True, ensure_ascii=False)
    return (
        f"Category: {category}\n"
        f"Title: {title}\n"
        f"Attributes: {attrs_json}"
    )


def _parse_estimate_output(inp: dict, base: dict, cost_eur: float, cache_hit: bool) -> dict:
    """Validate a submit_price_estimate payload (identical shape from either
    provider) and build the return dict. Mirrors the DB CHECK on
    price_predictions."""
    try:
        q10 = float(inp["q10"])
        q50 = float(inp["q50"])
        q90 = float(inp["q90"])
        conf = float(inp["confidence"])
        reasoning = str(inp.get("reasoning", ""))[:300]
    except (KeyError, TypeError, ValueError) as e:
        logger.warning("[claude_estimator] tool input malformed: %s; payload=%r", e, inp)
        return {**base, "reason": "parse_error", "cost_eur": cost_eur, "cache_hit": cache_hit}

    if not (0 < q10 <= q50 <= q90 <= 20_000_000):
        logger.warning(
            "[claude_estimator] quantile bounds violated: q10=%s q50=%s q90=%s", q10, q50, q90,
        )
        return {**base, "reason": "parse_error", "cost_eur": cost_eur, "cache_hit": cache_hit}

    return {
        "ok": True,
        "reason": "ok",
        "q10": q10, "q50": q50, "q90": q90,
        "confidence": max(0.0, min(1.0, conf)),
        "reasoning": reasoning,
        "cost_eur": cost_eur,
        "cache_hit": cache_hit,
    }


async def _estimate_via_anthropic(user_prompt: str, base: dict) -> dict:
    """Claude Haiku path — cached system prefix + forced tool call. Byte-for-byte
    the original implementation; the provider switch only chooses whether to
    reach it."""
    try:
        from app.lib.spend_tracker import SpendTracker
        tracker = SpendTracker.instance() if hasattr(SpendTracker, "instance") else SpendTracker()
        tracker.check("claude_estimate")
    except Exception as e:  # noqa: BLE001 — covers BudgetExceededError + import failures
        logger.warning("[claude_estimator] budget gate blocked: %s", e)
        return {**base, "reason": "budget_exhausted"}

    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        logger.error("[claude_estimator] anthropic SDK not installed; pip install anthropic")
        return {**base, "reason": "sdk_missing"}

    client = AsyncAnthropic()
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_OUT,
            # System prompt cached. cache_control on the last (only) text
            # block in `system` caches the whole prefix (tools + system).
            system=[{
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "submit_price_estimate"},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("[claude_estimator] API call failed: %s", e)
        return {**base, "reason": "api_error"}

    # Bookkeeping. Even a cache miss costs us — record before parsing so a
    # malformed response doesn't dodge the spend tally.
    cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
    cache_hit = cache_read > 0
    try:
        tracker.record("claude_estimate", cost_eur=COST_PER_CALL_EUR)
    except Exception:
        pass

    # Find the tool_use block. We forced it via tool_choice, so it MUST
    # be there — but defensive parsing in case of a refusal stop_reason.
    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        logger.warning("[claude_estimator] no tool_use block; stop_reason=%s", response.stop_reason)
        return {**base, "reason": "parse_error", "cost_eur": COST_PER_CALL_EUR, "cache_hit": cache_hit}

    return _parse_estimate_output(tool_block.input or {}, base, COST_PER_CALL_EUR, cache_hit)


async def _estimate_via_kimi(user_prompt: str, base: dict) -> Optional[dict]:
    """Kimi K2 path via Moonshot's OpenAI-compatible /chat/completions (function
    calling). Returns None on a hard transport/HTTP error so the caller can fall
    back to Claude; returns a result dict for budget/parse outcomes.

    Kimi is NOT Anthropic-compatible, so this deliberately uses a raw
    OpenAI-shaped HTTP call (same pattern as ml/openai_vision.py) — the Claude
    path above stays on the Anthropic SDK."""
    try:
        from app.lib.spend_tracker import SpendTracker
        tracker = SpendTracker.instance() if hasattr(SpendTracker, "instance") else SpendTracker()
        tracker.check("kimi_estimate")
    except Exception as e:  # noqa: BLE001
        logger.warning("[claude_estimator] kimi budget gate blocked: %s", e)
        return {**base, "reason": "budget_exhausted"}

    import json as _json
    try:
        import httpx
    except ImportError:
        logger.error("[claude_estimator] httpx not installed; cannot call Kimi")
        return None

    payload = {
        "model": KIMI_MODEL,
        "max_tokens": MAX_TOKENS_OUT,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        # Anthropic tool -> OpenAI function shape (Moonshot is OpenAI-compatible).
        "tools": [{
            "type": "function",
            "function": {
                "name": _TOOL["name"],
                "description": _TOOL["description"],
                "parameters": _TOOL["input_schema"],
            },
        }],
        "tool_choice": {"type": "function", "function": {"name": _TOOL["name"]}},
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
        logger.warning("[claude_estimator] Kimi API call failed: %s", e)
        return None  # signal fallback to Claude

    try:
        tracker.record("kimi_estimate", cost_eur=KIMI_COST_PER_CALL_EUR)
    except Exception:
        pass

    # No prompt caching on this path, so cache_hit is always False.
    try:
        tool_calls = data["choices"][0]["message"].get("tool_calls") or []
        inp = _json.loads(tool_calls[0]["function"]["arguments"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        logger.warning("[claude_estimator] Kimi response parse failed: %s; payload=%r", e, data)
        return {**base, "reason": "parse_error", "cost_eur": KIMI_COST_PER_CALL_EUR, "cache_hit": False}

    return _parse_estimate_output(inp, base, KIMI_COST_PER_CALL_EUR, False)


async def estimate_thin_cat_price(
    category: str,
    title: str,
    attrs: Optional[dict] = None,
) -> dict:
    """Ask Claude Haiku 4.5 for a price estimate.

    Returns:
        {
            "ok": bool,                       # False if disabled / capped / errored
            "reason": str,                    # 'ok' | 'disabled' | 'budget_exhausted' | 'no_api_key' | 'parse_error' | 'sdk_missing' | 'api_error'
            "q10": float | None,
            "q50": float | None,
            "q90": float | None,
            "confidence": float | None,       # [0,1] from the model
            "reasoning": str | None,
            "cost_eur": float,
            "cache_hit": bool,                # True if the cached prefix was read
        }
    """
    base = {
        "ok": False, "reason": "", "q10": None, "q50": None, "q90": None,
        "confidence": None, "reasoning": None, "cost_eur": 0.0, "cache_hit": False,
    }

    if not ENABLED:
        return {**base, "reason": "disabled"}

    provider = ESTIMATE_PROVIDER if ESTIMATE_PROVIDER in ("anthropic", "kimi") else "anthropic"
    if provider == "kimi" and not KIMI_API_KEY:
        logger.warning("[claude_estimator] ESTIMATE_PROVIDER=kimi but KIMI_API_KEY unset; using anthropic")
        provider = "anthropic"

    user_prompt = _format_user_prompt(category, title, attrs)

    if provider == "kimi":
        result = await _estimate_via_kimi(user_prompt, base)
        # None = Kimi hard error (network/HTTP/missing httpx). Fall back to
        # Claude when we have a key, so a bad Kimi flag never takes estimates
        # fully dark. A budget/parse dict (not None) is returned as-is.
        if result is not None:
            return result
        if not os.getenv("ANTHROPIC_API_KEY"):
            return {**base, "reason": "api_error"}
        logger.info("[claude_estimator] Kimi failed; falling back to anthropic")

    if not os.getenv("ANTHROPIC_API_KEY"):
        return {**base, "reason": "no_api_key"}

    return await _estimate_via_anthropic(user_prompt, base)


def to_market_hit(
    estimate: dict,
    *,
    category: str,
    item_ref: str,
    listing_id: str,
) -> Optional[dict]:
    """Convert an estimate dict into a market_hits-shaped row.

    Returns None if the estimate is not usable. Caller passes the
    resulting dict to `marketplace_agent.persist_comps_to_db` (or the
    bulk RPC) for ingestion. We use q50 as the price; q10/q90 ride
    along in features_json so valuation_worker can pick them up if
    desired without losing the empirical-comp shape.
    """
    if not estimate.get("ok"):
        return None
    return {
        "source": "claude_estimate",
        "provider": "claude_estimate",
        "marketplace": "claude_estimate",
        "raw_id": listing_id,
        "title": f"[claude_estimate] {item_ref}",
        "price": estimate["q50"],
        "currency": "EUR",
        "price_eur": estimate["q50"],
        "condition": None,
        "url": None,
        "category": category,
        "normalized_key": item_ref.split(":", 1)[1] if ":" in item_ref else item_ref,
        "is_listing": True,  # Synthetic — not a real sale
        "content_hash": f"claude_estimate:{item_ref}",
        "features_json": {
            "estimator": "claude_haiku_4_5",
            "q10": estimate["q10"],
            "q50": estimate["q50"],
            "q90": estimate["q90"],
            "model_confidence": estimate["confidence"],
            "reasoning": estimate["reasoning"],
            "cache_hit": estimate.get("cache_hit", False),
        },
    }
