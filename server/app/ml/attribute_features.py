"""
Attribute Featurizer — convert structured attributes_json into numeric
features that Ridge regression models can consume.

Used at both:
1. **Training time** — when generating train.jsonl, attribute-derived
   features enrich the existing condition/rarity/edition core.
2. **Inference time** — when QuickScan runs, the same featurizer
   converts vision-extracted attributes into model inputs.

Strategy: keep features simple, normalized to 0-1 where possible, so
they compose cleanly with the existing core features.

Features generated (when attributes are available):
    - brand_tier:          0-1 frequency rank in vocab (popular brand = high)
    - has_set_info:        0/1
    - has_reference:       0/1
    - has_serial:          0/1
    - is_limited_edition:  0/1 (any value contains "limited"/"LE"/etc.)
    - set_completeness:    0-1 (card_number / set_total)
    - has_year:            0/1
    - set_age_years:       normalized 0-1 (older = higher)
    - manufacturer_tier:   0-1 frequency rank
    - has_grade:           0/1 (graded by PSA/CGC/etc.)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Reference year for set_age computation
_CURRENT_YEAR = datetime.now().year

_LIMITED_KEYWORDS = ("limited", "exclusive", "le ", " le", "chase", "rare")
_GRADE_KEYWORDS = ("psa", "cgc", "bgs", "cbcs", "sgc", "graded")


# ---------------------------------------------------------------------------
# Tier rank lookup (lazy-loaded from vocab)
# ---------------------------------------------------------------------------

_brand_ranks_cache: dict[str, dict[str, float]] | None = None


def _get_field_ranks(category: str, field: str) -> dict[str, float]:
    """
    Compute 0-1 normalized ranks for values of a field, using vocab counts.
    Highest-frequency value → 1.0, rarest → 0.0.
    Cached lazily.
    """
    global _brand_ranks_cache
    if _brand_ranks_cache is None:
        _brand_ranks_cache = {}
        try:
            from app.ml.attribute_normalizer import _load_vocab
            vocab = _load_vocab()
            for cat, fields in vocab.items():
                for fld, values in fields.items():
                    if not values:
                        continue
                    sorted_vals = sorted(values.items(), key=lambda x: -x[1])
                    n = len(sorted_vals)
                    if n == 0:
                        continue
                    # Linear rank: 1.0 for #1, 0.0 for last
                    ranks = {
                        v: round(1.0 - (i / max(n - 1, 1)), 4)
                        for i, (v, _) in enumerate(sorted_vals)
                    }
                    _brand_ranks_cache[f"{cat}:{fld}"] = ranks
        except Exception as e:
            logger.debug(f"Failed to load vocab for ranks: {e}")
            _brand_ranks_cache = {}
    return _brand_ranks_cache.get(f"{category}:{field}", {})


# ---------------------------------------------------------------------------
# Feature extractors
# ---------------------------------------------------------------------------

def _extract_brand_tier(category: str, attrs: dict[str, Any]) -> float:
    brand = attrs.get("brand") or attrs.get("manufacturer") or attrs.get("house")
    if not brand or not isinstance(brand, str):
        return 0.0
    ranks = _get_field_ranks(category, "brand")
    if not ranks:
        ranks = _get_field_ranks(category, "manufacturer")
    if not ranks:
        ranks = _get_field_ranks(category, "house")
    return ranks.get(brand.strip(), 0.5)  # 0.5 = unknown brand


def _extract_set_completeness(attrs: dict[str, Any]) -> float:
    """Returns card_number / set_total if both present, else 0."""
    num = attrs.get("card_number")
    total = attrs.get("set_total")
    if isinstance(num, (int, float)) and isinstance(total, (int, float)) and total > 0:
        return min(1.0, max(0.0, float(num) / float(total)))
    return 0.0


def _extract_set_age_years(attrs: dict[str, Any]) -> float:
    """Years since release, normalized 0-1 (50+ years = 1.0)."""
    year = attrs.get("year") or attrs.get("pressing_year") or attrs.get("year_released")
    if isinstance(year, (int, float)) and 1900 <= year <= _CURRENT_YEAR + 1:
        age = _CURRENT_YEAR - int(year)
        return min(1.0, age / 50.0)
    return 0.0


def _is_limited_edition(attrs: dict[str, Any]) -> float:
    """1.0 if any attribute value contains a limited-edition keyword."""
    for v in attrs.values():
        if isinstance(v, str):
            v_lower = v.lower()
            if any(kw in v_lower for kw in _LIMITED_KEYWORDS):
                return 1.0
    if attrs.get("is_limited_edition"):
        return 1.0
    if attrs.get("limited_edition_size"):
        return 1.0
    return 0.0


def _is_graded(attrs: dict[str, Any]) -> float:
    """1.0 if attributes mention a grading service."""
    if attrs.get("graded") or attrs.get("grade") or attrs.get("grade_value"):
        return 1.0
    for v in attrs.values():
        if isinstance(v, str):
            v_lower = v.lower()
            if any(kw in v_lower for kw in _GRADE_KEYWORDS):
                return 1.0
    return 0.0


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def featurize_attributes(
    category: str,
    attributes: dict[str, Any] | None,
) -> dict[str, float]:
    """
    Convert structured attributes into a feature dict.

    Returns features that should be merged with core features
    (condition_score, rarity_score, edition_score) before training/inference.

    Returns an empty dict if attributes is None or empty.
    """
    if not attributes:
        return {}

    feats: dict[str, float] = {}

    # Brand tier
    feats["brand_tier"] = _extract_brand_tier(category, attributes)

    # Presence flags (binary signals are useful for Ridge)
    feats["has_set_info"] = 1.0 if (attributes.get("set_name") or attributes.get("set_code")) else 0.0
    feats["has_reference"] = 1.0 if attributes.get("reference_number") else 0.0
    feats["has_year"] = 1.0 if (attributes.get("year") or attributes.get("pressing_year")) else 0.0
    feats["has_movement"] = 1.0 if (attributes.get("movement") or attributes.get("movement_caliber")) else 0.0

    # Numerical
    feats["set_completeness"] = _extract_set_completeness(attributes)
    feats["set_age_years_norm"] = _extract_set_age_years(attributes)

    # Special signals
    feats["is_limited_edition"] = _is_limited_edition(attributes)
    feats["is_graded"] = _is_graded(attributes)

    # Piece count (LEGO etc.) — log-normalized
    pc = attributes.get("piece_count")
    if isinstance(pc, (int, float)) and pc > 0:
        # Log-normalize: 50 pieces → 0.4, 1000 → 0.7, 10000 → 1.0
        import math
        feats["piece_count_log"] = min(1.0, math.log10(pc) / 4.0)
    else:
        feats["piece_count_log"] = 0.0

    return feats


def merge_with_core(
    core_features: dict[str, float],
    category: str,
    attributes: dict[str, Any] | None,
) -> dict[str, float]:
    """
    Merge core features (condition_score, rarity_score, edition_score) with
    attribute-derived features. Core features take precedence if there are
    name collisions.
    """
    out = featurize_attributes(category, attributes)
    out.update(core_features)
    return out
