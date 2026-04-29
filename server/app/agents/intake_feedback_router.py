"""
Intake feedback router — user corrections and active learning.

Endpoints:
  POST /intake/feedback              — submit corrections (name/category/condition)
  GET  /intake/feedback/prompts/{id} — active-learning prompts for uncertain scans
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

_feedback_limit = per_user_rate_limit(30, scope="intake_feedback")

router = APIRouter(
    prefix="/intake/feedback",
    tags=["Intake Feedback"],
    dependencies=[Depends(get_current_user_id), Depends(_feedback_limit)],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    scan_session_id: str = Field(..., min_length=1, max_length=64)
    corrected_name: Optional[str] = Field(None, max_length=500)
    corrected_category: Optional[str] = Field(None, max_length=64)
    corrected_condition: Optional[str] = Field(None, max_length=30)


class FeedbackResponse(BaseModel):
    id: str
    scan_session_id: str
    accepted: bool = True
    retrain_flagged: bool = False


class ActiveLearningPrompt(BaseModel):
    question: str
    options: list[str]
    field: str  # "name" | "category" | "condition"
    scan_session_id: str


class ActiveLearningResponse(BaseModel):
    prompts: list[ActiveLearningPrompt] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    req: FeedbackRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Submit corrections for a scan result.

    Links corrections to the original scan via scan_session_id.
    Weights corrections by user level (gamification) — level >= 10 gets 2x weight.
    Flags category for retraining when corrections reach threshold (50).
    """
    from app.db import db_configured, get_conn

    if not db_configured():
        return FeedbackResponse(
            id=str(uuid4()),
            scan_session_id=req.scan_session_id,
            accepted=True,
        )

    # At least one correction must be provided
    if not any([req.corrected_name, req.corrected_category, req.corrected_condition]):
        raise error_response(400, "At least one correction field is required")

    # Get user weight from gamification level
    user_weight = 1.0
    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                "SELECT level FROM user_gamification WHERE user_id = $1::uuid",
                user_id,
            )
            if row and row["level"] >= 10:
                user_weight = 2.0
    except Exception:
        pass  # Default weight 1.0

    feedback_id = str(uuid4())
    retrain_flagged = False

    try:
        async with get_conn() as conn:
            # Insert correction
            await conn.execute(
                """
                INSERT INTO scan_corrections (
                    id, user_id, scan_session_id,
                    corrected_name, corrected_category, corrected_condition,
                    user_weight
                ) VALUES (
                    $1::uuid, $2::uuid, $3,
                    $4, $5, $6,
                    $7
                )
                ON CONFLICT (user_id, scan_session_id) DO UPDATE SET
                    corrected_name = COALESCE(EXCLUDED.corrected_name, scan_corrections.corrected_name),
                    corrected_category = COALESCE(EXCLUDED.corrected_category, scan_corrections.corrected_category),
                    corrected_condition = COALESCE(EXCLUDED.corrected_condition, scan_corrections.corrected_condition),
                    user_weight = EXCLUDED.user_weight,
                    updated_at = now()
                """,
                feedback_id,
                user_id,
                req.scan_session_id,
                req.corrected_name,
                req.corrected_category,
                req.corrected_condition,
                user_weight,
            )

            # Check if category corrections have reached retrain threshold (50)
            if req.corrected_category:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM scan_corrections
                    WHERE corrected_category = $1
                    """,
                    req.corrected_category,
                )
                if count and count >= 50:
                    retrain_flagged = True
                    logger.info(
                        "Retrain flagged: %d corrections for category %s",
                        count, req.corrected_category,
                    )

    except Exception as e:
        logger.warning("Failed to store scan feedback: %s", e)
        raise error_response(500, "Failed to store feedback")

    return FeedbackResponse(
        id=feedback_id,
        scan_session_id=req.scan_session_id,
        accepted=True,
        retrain_flagged=retrain_flagged,
    )


@router.get("/prompts/{session_id}", response_model=ActiveLearningResponse)
async def get_active_learning_prompts(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get active-learning prompts for uncertain scan results.

    Only generates prompts when confidence was in the 0.5-0.7 range.
    Returns up to 2 prompts for user disambiguation.
    """
    from app.db import db_configured, get_conn

    if not db_configured():
        return ActiveLearningResponse(prompts=[])

    prompts: list[ActiveLearningPrompt] = []

    try:
        async with get_conn() as conn:
            # Look up original scan data to find uncertain fields
            # We check alternatives from the intake result (stored in items or cache)
            # For now, generate prompts based on session pattern
            row = await conn.fetchrow(
                """
                SELECT attrs
                FROM items
                WHERE attrs::text LIKE $1
                LIMIT 1
                """,
                f"%{session_id}%",
            )

            if row and row["attrs"]:
                import json
                attrs = json.loads(row["attrs"]) if isinstance(row["attrs"], str) else row["attrs"]
                name_conf = attrs.get("name_confidence", 1.0)

                if 0.5 <= name_conf <= 0.7:
                    # Low name confidence — suggest alternatives
                    prompts.append(ActiveLearningPrompt(
                        question="Which name best matches your item?",
                        options=[attrs.get("suggested_name", "Unknown"), "Other"],
                        field="name",
                        scan_session_id=session_id,
                    ))

    except Exception as e:
        logger.debug("Active learning prompt generation error: %s", e)

    return ActiveLearningResponse(prompts=prompts)
