"""
OpenAI Vision API calls and prompt construction for collectible identification.

Uses GPT-4o-mini with chain-of-thought prompting, structured output (response_format),
and category-specific extraction instructions.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from app.config import OPENAI_API_KEY, OPENAI_VISION_MODEL
from app.lib.spend_tracker import spend_tracker, BudgetExceededError
from app.ml.vision_helpers import (
    ALL_CATEGORIES,
    CATEGORY_PROMPTS,
    CONDITION_KEYWORDS,
    DEFAULT_CATEGORY_PROMPT,
    ClassificationResult,
)

logger = logging.getLogger(__name__)

_OPENAI_SYSTEM_PROMPT = """Collectibles ID expert. Observe image details (text, logos, numbers, packaging, damage), classify category, identify specific item (set/number/edition/variant), extract attributes, assess condition (mint/near_mint/very_good/good/fair/poor).

Categories: pokemon,mtg,yugioh,lorcana,funko,designer_toys,anime_figures,hot_toys,action_figures,vintage_toys,marvel_legends,lego,gunpla,scale_models,warhammer,retro_games,manga,bluray_steelbook,anime_bluray,anime_soundtrack,anime_ost_vinyl,kpop_merch,taylor_swift,pop_fandom,kpop_lightsticks,disney,theme_park,ghibli,bandai_premium,jp_magazine,jp_event,nintendo_merch,retro_pokemon,one_piece,vtuber,keycaps,loungefly,diecast,sportscards,retro_handhelds

{category_detail}
Also note any visible defects (scratches, dents, wear, stains, creases) with severity and location. Suggest a PSA/CGC grade for cards/comics."""

# Structured output JSON schema for response_format
_IDENTIFICATION_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "collectible_identification",
        "strict": False,
        "schema": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Chain-of-thought trace: what you see, how you identify it",
                },
                "category_id": {
                    "type": "string",
                    "description": "Category ID from the allowed list",
                },
                "category_confidence": {
                    "type": "number",
                    "description": "Confidence in category (0.0-1.0)",
                },
                "suggested_name": {
                    "type": "string",
                    "description": "Specific item name with set/number/edition/variant",
                },
                "name_confidence": {
                    "type": "number",
                    "description": "Confidence in the item name (0.0-1.0)",
                },
                "condition": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "description": "Condition: mint, near_mint, very_good, good, fair, poor, or null",
                },
                "condition_confidence": {
                    "type": "number",
                    "description": "Confidence in condition assessment (0.0-1.0)",
                },
                "attributes": {
                    "type": "object",
                    "description": "Category-specific extracted attributes",
                    "additionalProperties": True,
                },
                "search_keywords": {
                    "type": "array",
                    "description": "3-5 keywords for catalog search",
                    "items": {"type": "string"},
                },
                "defect_annotations": {
                    "type": "array",
                    "description": "Defects detected in the item (scratches, dents, wear, creases, etc.)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "description": "Defect type (scratch, dent, crease, stain, tear, foxing, wear, fading, discoloration, chip, crack)"},
                            "severity": {"type": "string", "description": "minor, moderate, major, or severe"},
                            "location": {"type": "string", "description": "Where on the item (front, back, corner, edge, surface)"},
                            "description": {"type": "string", "description": "Brief description of the defect"}
                        }
                    },
                },
                "suggested_grade": {
                    "anyOf": [{"type": "object", "properties": {
                        "scale": {"type": "string", "description": "psa, cgc, or generic"},
                        "grade_value": {"type": "string", "description": "Suggested grade value"},
                        "reasoning": {"type": "string", "description": "Why this grade was chosen"}
                    }}, {"type": "null"}],
                    "description": "Suggested grading if applicable (cards, comics)"
                },
            },
            "required": [
                "reasoning", "category_id", "category_confidence",
                "suggested_name", "name_confidence",
                "condition", "condition_confidence",
                "attributes", "search_keywords",
            ],
            "additionalProperties": False,
        },
    },
}


def build_system_prompt(category_hint: str | None = None) -> str:
    """Build the system prompt, optionally injecting category-specific extraction instructions."""
    if category_hint:
        detail = CATEGORY_PROMPTS.get(category_hint, DEFAULT_CATEGORY_PROMPT)
        detail_block = f"Category hint: {category_hint}\n{detail}"
    else:
        detail_block = (
            "No category hint available. Identify the category first, "
            "then extract relevant attributes."
        )
    return _OPENAI_SYSTEM_PROMPT.format(category_detail=detail_block)


async def classify_openai_vision(
    image_bytes: bytes,
    filename: str,
    category_hint: str | None = None,
) -> ClassificationResult | None:
    """
    Use OpenAI Vision API with chain-of-thought prompting and structured output
    to identify a specific collectible item from an image.
    """
    if not OPENAI_API_KEY:
        return None

    try:
        spend_tracker.check("openai")
    except BudgetExceededError:
        logger.warning("OpenAI Vision call blocked by spend budget")
        return None

    logger.info(
        "vision_classifier: attempting OpenAI Vision classification (hint=%s)",
        category_hint,
    )

    try:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        mime = "image/jpeg"
        if image_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"

        system_prompt = build_system_prompt(category_hint)

        async with httpx.AsyncClient(timeout=60.0) as client:
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
                                    "text": f"Identify this collectible item. Filename: {filename}",
                                },
                            ],
                        },
                    ],
                    "response_format": _IDENTIFICATION_SCHEMA,
                    "max_tokens": 800,
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        # Record spend (estimate cost from token usage if available)
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 500)
        output_tokens = usage.get("completion_tokens", 200)
        # gpt-4o-mini: $0.15/1M input, $0.60/1M output (USD→EUR via config)
        from app.config import USD_TO_EUR
        cost_usd = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000
        spend_tracker.record("openai", cost_eur=cost_usd * USD_TO_EUR)

        # Parse the structured response
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            logger.warning("OpenAI Vision returned empty content")
            return None

        # With response_format, content is guaranteed valid JSON (no markdown stripping needed)
        # But keep a safety fallback for edge cases
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            content = "\n".join(lines).strip()

        parsed = json.loads(content)

        category_id = parsed.get("category_id", "")
        if category_id not in ALL_CATEGORIES:
            logger.warning("OpenAI Vision returned unknown category: %s", category_id)
            cat_lower = category_id.lower().replace(" ", "_").replace("-", "_")
            if cat_lower in ALL_CATEGORIES:
                category_id = cat_lower
            else:
                return None

        confidence = max(0.0, min(1.0, float(parsed.get("category_confidence", 0.7))))
        name_confidence = max(0.0, min(1.0, float(parsed.get("name_confidence", 0.5))))

        condition = parsed.get("condition")
        if condition and condition not in CONDITION_KEYWORDS:
            condition = condition.lower().replace(" ", "_").replace("-", "_")
            if condition not in CONDITION_KEYWORDS:
                condition = None

        cond_conf = max(0.0, min(1.0, float(parsed.get("condition_confidence", 0.0))))

        # Merge extracted attributes with per-field confidences and search keywords
        attributes = parsed.get("attributes", {})
        attributes["search_keywords"] = parsed.get("search_keywords", [])
        attributes["chain_of_thought"] = parsed.get("reasoning", "")
        attributes["name_confidence"] = name_confidence
        attributes["defect_annotations"] = parsed.get("defect_annotations", [])
        attributes["suggested_grade"] = parsed.get("suggested_grade")

        logger.info(
            "OpenAI Vision identification: category=%s conf=%.2f name='%s' name_conf=%.2f",
            category_id, confidence,
            parsed.get("suggested_name", "")[:60], name_confidence,
        )

        return ClassificationResult(
            category_id=category_id,
            category_confidence=confidence,
            condition=condition,
            condition_confidence=cond_conf,
            suggested_name=parsed.get("suggested_name"),
            attributes=attributes,
            embedding_vector=None,
            classification_method="openai_vision",
            model_version=f"openai:{OPENAI_VISION_MODEL}",
        )

    except json.JSONDecodeError as e:
        logger.warning("OpenAI Vision response was not valid JSON: %s", e)
        return None
    except httpx.HTTPStatusError as e:
        logger.warning("OpenAI Vision API HTTP error: %s (status %d)", e, e.response.status_code)
        return None
    except Exception as e:
        logger.warning("OpenAI Vision classification failed: %s", e)
        return None
