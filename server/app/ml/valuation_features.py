"""Shared feature extraction for the price-valuation model.

ONE source of truth for turning a market observation (condition string +
attrs jsonb) into the model's core feature vector. Imported by BOTH the
trainer (`model_retrain_worker._price_to_features`) and the serving path
(`valuation_worker`), so train-time and serve-time features can never drift
apart again.

History (audit V1/V2): training used to hardcode `rarity_score = edition_score
= 0.5` for every row while serving stuffed the empirical median price into the
condition slot. The model therefore learned nothing and was fed garbage at
inference. This module makes both sides compute the SAME real features from the
same attrs.
"""

from __future__ import annotations

from typing import Any

# Must match train_price.py CORE_FEATURES (order matters — it's the vector order).
CORE_FEATURES = ["condition_score", "rarity_score", "edition_score"]

# Neutral fallbacks when a signal is absent. Chosen to match the trainer's
# historical defaults so existing artifacts behave sensibly.
_DEFAULT_CONDITION = 0.70
_DEFAULT_RARITY = 0.50
_DEFAULT_EDITION = 0.50


def condition_to_score(condition: str | None) -> float:
    """Map a free-text condition to [0,1]. Specific checks before general."""
    cond = (condition or "").lower()
    if any(k in cond for k in ("like new", "near mint", "nm")):
        return 0.85
    if any(k in cond for k in ("new", "sealed", "mint")):
        return 0.95
    if any(k in cond for k in ("good", "very good", "vg", "excellent")):
        return 0.70
    if any(k in cond for k in ("fair", "acceptable", "played")):
        return 0.45
    if any(k in cond for k in ("poor", "damaged", "heavy")):
        return 0.20
    return _DEFAULT_CONDITION


def _as_dict(attrs: Any) -> dict:
    if isinstance(attrs, dict):
        return attrs
    if isinstance(attrs, str):
        import json
        try:
            d = json.loads(attrs)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}
    return {}


# Rarity tier keywords → score. Foils/holos and chase/secret rares sit high;
# commons low. This is intentionally coarse — it just needs to carry ordinal
# signal the Ridge model can weight, not be a perfect taxonomy.
_RARITY_TIERS = [
    (0.98, ("secret rare", "special illustration", "hyper rare", "grail", "1/1", "one of one")),
    (0.90, ("ultra rare", "chase", "alt art", "alternate art", "full art", "rainbow")),
    (0.82, ("foil", "holo", "holographic", "prismatic", "refractor", "shiny")),
    (0.75, ("super rare", "rare holo", "double rare")),
    (0.60, ("rare", "uncommon foil")),
    (0.45, ("uncommon",)),
    (0.30, ("common",)),
]


def rarity_to_score(attrs: dict) -> float:
    """Derive a rarity score from attrs. Looks at rarity/foil/variant fields."""
    blob = " ".join(
        str(attrs.get(k, "")) for k in
        ("rarity", "foil", "holo", "variant", "finish", "subtype", "type")
    ).lower()
    # explicit boolean foil flags
    if attrs.get("is_foil") is True or attrs.get("foil") in (True, "true", "yes", "1"):
        if not blob.strip():
            return 0.82
    if not blob.strip():
        return _DEFAULT_RARITY
    for score, kws in _RARITY_TIERS:
        if any(kw in blob for kw in kws):
            return score
    return _DEFAULT_RARITY


def edition_to_score(attrs: dict) -> float:
    """Derive an edition score from attrs. 1st-edition / limited / exclusive rank high."""
    blob = " ".join(
        str(attrs.get(k, "")) for k in
        ("edition", "first_edition", "printing", "release", "variant", "exclusive")
    ).lower()
    if attrs.get("first_edition") in (True, "true", "yes", "1"):
        return 0.95
    if not blob.strip():
        return _DEFAULT_EDITION
    if any(k in blob for k in ("1st", "first edition", "first print", "1e")):
        return 0.95
    if any(k in blob for k in ("limited", "exclusive", "promo", "special edition", "anniversary")):
        return 0.80
    if any(k in blob for k in ("unlimited", "reprint", "2nd", "second")):
        return 0.35
    return _DEFAULT_EDITION


def extract_core_features(condition: str | None, attrs: Any) -> dict[str, float]:
    """Return the 3 core model features from a single observation.

    Used per-row at train time and per-item (from aggregated comp attrs) at
    serve time, so the two never diverge.
    """
    a = _as_dict(attrs)
    return {
        "condition_score": round(condition_to_score(condition), 4),
        "rarity_score": round(rarity_to_score(a), 4),
        "edition_score": round(edition_to_score(a), 4),
    }


def build_feature_vector(feature_names: list[str], values: dict[str, float]) -> list[float]:
    """Assemble a vector in the model artifact's feature order.

    Missing features default to a neutral 0.5 rather than 0.0 — these are all
    [0,1] scores, so 0.0 would be an extreme, not a neutral, value.
    """
    return [float(values.get(name, 0.5)) for name in feature_names]
