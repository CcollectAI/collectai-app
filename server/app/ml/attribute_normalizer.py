"""
Attribute Normalizer — snap fuzzy vision-extracted attributes to canonical
values from the catalog vocabulary.

When the QuickScan vision pipeline returns attributes like:
    {"set_name": "base", "manufacturer": "rolex", ...}

This module looks up the canonical values from the per-category vocabulary
(built by `pipelines/build_attribute_vocab.py`) and snaps fuzzy matches:
    {"set_name": "Base Set", "manufacturer": "Rolex", ...}

Strategy:
1. Exact match (case-insensitive) → snap immediately
2. Substring match → if vision value is contained in or contains a vocab
   value with high overlap, snap
3. Levenshtein distance ≤ 2 → snap
4. No match → keep the original value (may be a new variant we should learn)

The vocab is loaded once at module import (lazy) and cached.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

VOCAB_PATH = Path(__file__).resolve().parents[2] / "data" / "_vocab" / "attribute_vocab.json"
BRAND_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "_vocab" / "brand_registry.json"

# Fields that map through the brand registry for canonicalization
_BRAND_FIELDS = {
    "brand", "manufacturer", "house", "publisher", "distributor",
    "label", "agency", "release_label",
}


# ---------------------------------------------------------------------------
# Levenshtein distance (small standalone implementation)
# ---------------------------------------------------------------------------

def _levenshtein(a: str, b: str, max_dist: int = 3) -> int:
    """
    Compute Levenshtein distance between two strings, capped at max_dist + 1.
    Returns max_dist + 1 if the distance exceeds max_dist (early bailout).
    """
    if a == b:
        return 0
    if abs(len(a) - len(b)) > max_dist:
        return max_dist + 1
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        min_in_row = curr[0]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
            if curr[j] < min_in_row:
                min_in_row = curr[j]
        if min_in_row > max_dist:
            return max_dist + 1
        prev = curr
    return prev[-1]


# ---------------------------------------------------------------------------
# Vocabulary loading (lazy + cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_vocab() -> dict[str, dict[str, dict[str, int]]]:
    """Load the attribute vocabulary from disk. Returns empty dict on error."""
    try:
        if not VOCAB_PATH.exists():
            logger.warning(f"Attribute vocab not found at {VOCAB_PATH}")
            return {}
        return json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to load attribute vocab: {e}")
        return {}


@lru_cache(maxsize=1)
def _load_brand_registry() -> dict[str, dict[str, str]]:
    """Load brand registry: {category: {variant_lc: canonical}}."""
    try:
        if not BRAND_REGISTRY_PATH.exists():
            return {}
        return json.loads(BRAND_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to load brand registry: {e}")
        return {}


def _canonicalize_brand(category: str, value: str) -> str | None:
    """Look up the canonical form of a brand-like value, or None if not found."""
    registry = _load_brand_registry()
    cat_reg = registry.get(category, {})
    if not cat_reg:
        return None
    return cat_reg.get(value.lower().strip())


def _get_field_values(category: str, field: str) -> dict[str, int]:
    """Return {canonical_value: count} for a category/field, or {} if unknown."""
    vocab = _load_vocab()
    return vocab.get(category, {}).get(field, {})


# ---------------------------------------------------------------------------
# Normalization (single value)
# ---------------------------------------------------------------------------

def normalize_value(
    category: str,
    field: str,
    value: Any,
    *,
    max_lev_distance: int = 2,
) -> tuple[Any, str | None]:
    """
    Snap a single attribute value to its canonical form.

    Returns: (normalized_value, match_type)
        match_type ∈ {"exact", "case", "substring", "fuzzy", None}
    """
    if value is None or value == "":
        return value, None

    # Only normalize string values
    if not isinstance(value, str):
        return value, None

    raw = value.strip()
    if not raw:
        return value, None

    # 0. Brand registry lookup (highest priority for brand-like fields)
    if field in _BRAND_FIELDS:
        canonical = _canonicalize_brand(category, raw)
        if canonical and canonical != raw:
            return canonical, "brand_registry"

    candidates = _get_field_values(category, field)
    if not candidates:
        return value, None

    # 1. Exact match (case-sensitive)
    if raw in candidates:
        return raw, "exact"

    # 2. Case-insensitive match
    lower = raw.lower()
    for canon in candidates:
        if canon.lower() == lower:
            return canon, "case"

    # 3. Substring match (only when one fully contains the other)
    matches: list[tuple[str, int]] = []
    for canon in candidates:
        cl = canon.lower()
        if lower in cl or cl in lower:
            matches.append((canon, candidates[canon]))
    if matches:
        # Pick the canonical with highest support count
        matches.sort(key=lambda x: -x[1])
        return matches[0][0], "substring"

    # 4. Fuzzy match (Levenshtein) — only for short-ish strings
    if len(raw) > 60:
        return value, None
    best: tuple[str, int] | None = None
    for canon in candidates:
        if abs(len(canon) - len(raw)) > max_lev_distance:
            continue
        d = _levenshtein(lower, canon.lower(), max_lev_distance)
        if d <= max_lev_distance:
            if best is None or d < best[1]:
                best = (canon, d)
                if d == 0:
                    break
    if best:
        return best[0], "fuzzy"

    return value, None


# ---------------------------------------------------------------------------
# Normalization (full dict)
# ---------------------------------------------------------------------------

def normalize_attributes(
    category: str,
    attributes: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """
    Normalize an entire attributes dict.

    Returns: (normalized_attrs, match_log)
        normalized_attrs: same shape as input but with snapped values
        match_log: {field: match_type} for fields that were normalized
    """
    if not attributes:
        return attributes, {}

    out: dict[str, Any] = {}
    log: dict[str, str] = {}
    for field, value in attributes.items():
        normalized, match_type = normalize_value(category, field, value)
        out[field] = normalized
        if match_type and match_type != "exact" and normalized != value:
            log[field] = match_type
    return out, log


# ---------------------------------------------------------------------------
# Vocab statistics
# ---------------------------------------------------------------------------

def get_vocab_stats() -> dict[str, Any]:
    """Return summary stats about the loaded vocabulary."""
    vocab = _load_vocab()
    if not vocab:
        return {"loaded": False}
    return {
        "loaded": True,
        "categories": len(vocab),
        "total_fields": sum(len(f) for f in vocab.values()),
        "total_values": sum(
            len(v) for f in vocab.values() for v in f.values()
        ),
    }


def reload_vocab() -> None:
    """Force a reload of the vocabulary from disk (useful after rebuild)."""
    _load_vocab.cache_clear()
    _load_brand_registry.cache_clear()
