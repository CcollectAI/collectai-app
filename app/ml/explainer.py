"""
Explainer module for generating human-readable price explanations.

Takes model features and coefficients to produce natural language explanations
of why an item is priced at a certain level.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Feature display names and descriptions
FEATURE_LABELS: dict[str, str] = {
    # Condition features
    "condition_score": "Condition",
    "condition": "Condition",
    "grade": "Grade",
    "graded": "Professional grading",
    "psa_grade": "PSA grade",
    "bgs_grade": "BGS grade",
    "cgc_grade": "CGC grade",

    # Rarity features
    "rarity_score": "Rarity",
    "rarity": "Rarity",
    "is_rare": "Rarity",
    "is_holo": "Holographic",
    "is_foil": "Foil",
    "is_first_edition": "First edition",
    "is_shadowless": "Shadowless print",
    "is_reverse_holo": "Reverse holo",
    "is_full_art": "Full art",
    "is_secret_rare": "Secret rare",

    # Edition/set features
    "edition_score": "Edition value",
    "set_age_years": "Set age",
    "set_rarity": "Set rarity",
    "print_run_estimate": "Print run",
    "is_limited": "Limited edition",
    "is_promo": "Promotional",
    "is_exclusive": "Exclusive variant",

    # Market features
    "market_demand": "Market demand",
    "recent_sales_volume": "Recent sales",
    "price_trend_30d": "Recent price trend",
    "population_count": "Population",

    # Category-specific
    "power_level": "Power level",
    "playability": "Playability",
    "chase_score": "Chase factor",
    "nostalgia_factor": "Nostalgia factor",
    "completeness": "Set completeness bonus",
}

# Friendly value descriptors
CONDITION_DESCRIPTORS = {
    (0.0, 0.3): "lower condition",
    (0.3, 0.5): "moderate condition",
    (0.5, 0.7): "good condition",
    (0.7, 0.9): "excellent condition",
    (0.9, 1.1): "near mint/mint condition",
}

RARITY_DESCRIPTORS = {
    (0.0, 0.3): "common",
    (0.3, 0.5): "uncommon",
    (0.5, 0.7): "moderately rare",
    (0.7, 0.9): "rare",
    (0.9, 1.1): "highly sought-after",
}


def _get_descriptor(value: float, descriptors: dict) -> str:
    """Get friendly descriptor for a numeric value."""
    for (low, high), desc in descriptors.items():
        if low <= value < high:
            return desc
    return "notable"


def _get_feature_contribution(
    feature_name: str,
    feature_value: float,
    coefficient: float,
    mean: float,
    std: float,
) -> tuple[float, str]:
    """
    Calculate the contribution of a feature to the prediction
    and generate a description.

    Returns (contribution_magnitude, description).
    """
    if std == 0:
        std = 1.0

    # Standardized value
    z = (feature_value - mean) / std
    # Contribution to prediction
    contribution = coefficient * z

    # Get label
    label = FEATURE_LABELS.get(feature_name, feature_name.replace("_", " ").title())

    return contribution, label


def generate_explanation(features: dict[str, Any], artifact: dict) -> str:
    """
    Generate a human-readable explanation of the price prediction.

    Args:
        features: Dict of feature name -> value used for prediction
        artifact: Model artifact containing coefficients, means, stds

    Returns:
        Human-readable explanation string
    """
    if artifact.get("model_type") != "ridge_v1":
        return "Price estimate based on similar items in the market."

    try:
        cols = artifact.get("features", [])
        mu = artifact.get("standardizer", {}).get("mean", [])
        sd = artifact.get("standardizer", {}).get("std", [])
        coef = artifact.get("ridge", {}).get("coef", [])

        if not cols or len(cols) != len(coef):
            return "Price estimate based on category patterns and recent sales."

        # Calculate contributions for each feature
        contributions: list[tuple[float, str, float]] = []  # (contribution, label, raw_value)

        for i, col in enumerate(cols):
            if i >= len(mu) or i >= len(sd) or i >= len(coef):
                continue

            raw_value = float(features.get(col, 0.0))
            contribution, label = _get_feature_contribution(
                col, raw_value, coef[i], mu[i], sd[i] if sd[i] != 0 else 1.0
            )
            contributions.append((contribution, label, raw_value))

        # Sort by absolute contribution (most impactful first)
        contributions.sort(key=lambda x: abs(x[0]), reverse=True)

        # Build explanation from top 3 contributors
        top_factors = contributions[:3]

        if not top_factors:
            return "Price estimate based on market comparisons."

        # Generate explanation parts
        positive_factors = []
        negative_factors = []

        for contrib, label, raw_value in top_factors:
            if abs(contrib) < 0.05:  # Skip negligible contributions
                continue

            # Generate contextual description
            lower_label = label.lower()

            if "condition" in lower_label or "grade" in lower_label:
                if raw_value > 0.7:
                    positive_factors.append("excellent condition")
                elif raw_value > 0.5:
                    positive_factors.append("good condition")
                elif raw_value < 0.3:
                    negative_factors.append("lower condition")
            elif "rarity" in lower_label or "rare" in lower_label:
                if raw_value > 0.7 or contrib > 0:
                    positive_factors.append("rarity")
                else:
                    negative_factors.append("common availability")
            elif "holo" in lower_label or "foil" in lower_label:
                if raw_value > 0.5 or contrib > 0:
                    positive_factors.append("holographic/foil variant")
            elif "first" in lower_label or "edition" in lower_label:
                if raw_value > 0.5 or contrib > 0:
                    positive_factors.append("desirable edition")
            elif "demand" in lower_label or "trend" in lower_label:
                if contrib > 0:
                    positive_factors.append("strong market demand")
                else:
                    negative_factors.append("current market trends")
            elif "age" in lower_label:
                if contrib > 0:
                    positive_factors.append("vintage appeal")
            else:
                # Generic handling
                if contrib > 0.1:
                    positive_factors.append(label.lower())
                elif contrib < -0.1:
                    negative_factors.append(label.lower())

        # Deduplicate
        positive_factors = list(dict.fromkeys(positive_factors))[:3]
        negative_factors = list(dict.fromkeys(negative_factors))[:2]

        # Build final explanation
        parts = []

        if positive_factors:
            if len(positive_factors) == 1:
                parts.append(f"Priced based on its {positive_factors[0]}")
            else:
                factors_str = ", ".join(positive_factors[:-1]) + f" and {positive_factors[-1]}"
                parts.append(f"Key factors: {factors_str}")

        if negative_factors and not positive_factors:
            factors_str = " and ".join(negative_factors)
            parts.append(f"Price reflects {factors_str}")

        if not parts:
            return "Price estimate based on recent market sales for similar items."

        explanation = ". ".join(parts) + "."
        return explanation

    except Exception as e:
        logger.warning(f"Error generating explanation: {e}")
        return "Price estimate based on market data and item characteristics."


def generate_simple_explanation(
    category: str,
    condition_guess: str | None = None,
    edition_guess: str | None = None,
    rarity_score: float | None = None,
) -> str:
    """
    Generate a simple explanation when no model artifact is available.
    Uses the QuickScan attributes directly.
    """
    parts = []

    # Add condition context
    if condition_guess:
        cond_lower = condition_guess.lower()
        if "mint" in cond_lower or "nm" in cond_lower:
            parts.append("excellent condition")
        elif "good" in cond_lower or "lp" in cond_lower:
            parts.append("good condition")
        elif "played" in cond_lower or "mp" in cond_lower or "hp" in cond_lower:
            parts.append("played condition")

    # Add edition context
    if edition_guess:
        ed_lower = edition_guess.lower()
        if "1st" in ed_lower or "first" in ed_lower:
            parts.append("first edition printing")
        elif "unlimited" in ed_lower:
            parts.append("unlimited edition")
        elif "promo" in ed_lower:
            parts.append("promotional release")
        elif edition_guess and edition_guess != "Unknown edition":
            parts.append(f"{edition_guess} set")

    # Add rarity context
    if rarity_score is not None:
        if rarity_score > 0.8:
            parts.append("high rarity")
        elif rarity_score > 0.6:
            parts.append("above-average rarity")

    if not parts:
        # Category-specific fallbacks
        cat_lower = category.lower()
        if "mtg" in cat_lower or "magic" in cat_lower:
            return "Estimate based on recent Magic: The Gathering market sales."
        elif "pokemon" in cat_lower:
            return "Estimate based on recent Pokémon TCG market sales."
        elif "funko" in cat_lower:
            return "Estimate based on recent Funko Pop market sales."
        else:
            return f"Estimate based on recent {category} market sales."

    if len(parts) == 1:
        return f"Priced based on {parts[0]} and recent market data."
    else:
        factors = ", ".join(parts[:-1]) + f" and {parts[-1]}"
        return f"Key factors: {factors}."
