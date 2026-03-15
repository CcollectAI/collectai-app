"""
Condition assessment logic for the intake pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .helpers import IntakeResult

logger = logging.getLogger(__name__)


def apply_condition_grading(result: IntakeResult, vision_cat: Optional[str]) -> None:
    """
    Enrich IntakeResult with condition grading from defect annotations.

    Modifies result.suggested_grade in place if defects are present
    but no grade has been assigned yet.
    """
    if not result.defect_annotations or result.suggested_grade:
        return

    try:
        from app.ml.condition_grader import map_defects_to_psa_grade, defects_to_generic_condition
        cat_lower = (vision_cat or "").lower()
        if any(k in cat_lower for k in ("pokemon", "mtg", "yugioh", "lorcana", "sportscards")):
            gr = map_defects_to_psa_grade(result.defect_annotations)
            result.suggested_grade = {
                "scale": "psa",
                "grade_value": str(gr["grade"]),
                "reasoning": f"{len(result.defect_annotations)} defect(s): {gr['label']}",
            }
        else:
            gr = defects_to_generic_condition(result.defect_annotations)
            result.suggested_grade = {
                "scale": "generic",
                "grade_value": gr["condition"].replace("_", " ").title(),
                "reasoning": f"{len(result.defect_annotations)} defect(s) detected",
            }
    except Exception:
        pass  # Best-effort grading
