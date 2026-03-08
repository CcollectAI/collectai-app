"""
Condition grading utilities for CollectAI.

Maps defect annotations from vision AI to standardized grading scales
(PSA, CGC, generic condition).
"""

from __future__ import annotations
from typing import Any

# Defect severity weights for grade calculation
SEVERITY_WEIGHTS = {
    "minor": 0.5,
    "moderate": 1.5,
    "major": 3.0,
    "severe": 5.0,
}

# PSA grade thresholds (10-point scale)
PSA_THRESHOLDS = [
    (0.0, 10, "Gem Mint"),
    (0.5, 9, "Mint"),
    (1.5, 8, "Near Mint-Mint"),
    (3.0, 7, "Near Mint"),
    (5.0, 6, "Excellent-Mint"),
    (7.0, 5, "Excellent"),
    (10.0, 4, "Very Good-Excellent"),
    (15.0, 3, "Very Good"),
    (20.0, 2, "Good"),
    (float("inf"), 1, "Poor"),
]

# CGC grade thresholds (10-point scale)
CGC_THRESHOLDS = [
    (0.0, 9.8, "Near Mint/Mint"),
    (0.5, 9.6, "Near Mint+"),
    (1.0, 9.4, "Near Mint"),
    (2.0, 9.2, "Near Mint-"),
    (3.0, 9.0, "Very Fine/Near Mint"),
    (5.0, 8.5, "Very Fine+"),
    (7.0, 8.0, "Very Fine"),
    (10.0, 7.0, "Fine/Very Fine"),
    (15.0, 5.0, "Very Good/Fine"),
    (20.0, 3.0, "Good/Very Good"),
    (float("inf"), 1.0, "Poor"),
]

# Generic condition mapping
GENERIC_THRESHOLDS = [
    (0.0, "mint"),
    (1.0, "near_mint"),
    (3.0, "very_good"),
    (7.0, "good"),
    (15.0, "fair"),
    (float("inf"), "poor"),
]


def _total_defect_score(defects: list[dict[str, Any]]) -> float:
    """Sum weighted severity scores from defect annotations."""
    total = 0.0
    for d in defects:
        severity = d.get("severity", "minor")
        total += SEVERITY_WEIGHTS.get(severity, 1.0)
    return total


def map_defects_to_psa_grade(defects: list[dict[str, Any]]) -> dict[str, Any]:
    """Map defect annotations to a PSA grade estimate."""
    score = _total_defect_score(defects)
    for threshold, grade, label in PSA_THRESHOLDS:
        if score <= threshold:
            return {"scale": "PSA", "grade": grade, "label": label, "defect_score": round(score, 2)}
    return {"scale": "PSA", "grade": 1, "label": "Poor", "defect_score": round(score, 2)}


def map_defects_to_cgc_grade(defects: list[dict[str, Any]]) -> dict[str, Any]:
    """Map defect annotations to a CGC grade estimate."""
    score = _total_defect_score(defects)
    for threshold, grade, label in CGC_THRESHOLDS:
        if score <= threshold:
            return {"scale": "CGC", "grade": grade, "label": label, "defect_score": round(score, 2)}
    return {"scale": "CGC", "grade": 1.0, "label": "Poor", "defect_score": round(score, 2)}


def defects_to_generic_condition(defects: list[dict[str, Any]]) -> dict[str, Any]:
    """Map defect annotations to a generic condition label."""
    score = _total_defect_score(defects)
    for threshold, label in GENERIC_THRESHOLDS:
        if score <= threshold:
            return {"condition": label, "defect_score": round(score, 2)}
    return {"condition": "poor", "defect_score": round(score, 2)}
