"""
Feedback router for capturing user feedback on predictions.

Endpoints:
- POST /feedback/submit - Save feedback to feedback table
- POST /feedback/correction - Update training_items.corrected_* columns
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/feedback", tags=["feedback"])
logger = logging.getLogger(__name__)


def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except Exception as e:
        logger.debug(f"DB pool not available: {e}")
        return None


class FeedbackSubmitRequest(BaseModel):
    """Request body for submitting feedback."""
    item_id: str = Field(..., description="UUID of the item")
    feedback_type: str = Field(
        ...,
        description="Type of feedback: sale_price, disagree, accurate, or custom"
    )
    value: str | None = Field(
        None,
        description="Value for the feedback (e.g., sale price amount)"
    )
    notes: str | None = Field(
        None,
        description="Optional notes about the feedback"
    )


class FeedbackSubmitResponse(BaseModel):
    """Response from feedback submission."""
    success: bool
    feedback_id: str | None = None
    message: str


class CorrectionRequest(BaseModel):
    """Request body for submitting a correction to training data."""
    item_id: str = Field(..., description="UUID of the training item")
    corrected_price: float | None = Field(
        None,
        description="Corrected price value"
    )
    corrected_condition: str | None = Field(
        None,
        description="Corrected condition (e.g., 'Near Mint', 'Good')"
    )
    corrected_category: str | None = Field(
        None,
        description="Corrected category"
    )
    corrected_attributes: dict[str, Any] | None = Field(
        None,
        description="Corrected attributes JSON"
    )
    notes: str | None = Field(
        None,
        description="Notes about the correction"
    )


class CorrectionResponse(BaseModel):
    """Response from correction submission."""
    success: bool
    message: str


@router.post("/submit", response_model=FeedbackSubmitResponse)
async def submit_feedback(request: FeedbackSubmitRequest):
    """
    Submit feedback on an item's prediction.

    Feedback types:
    - sale_price: User reports actual sale price (value = price string like "123.45")
    - disagree: User disagrees with the prediction
    - accurate: User confirms prediction was accurate
    - custom: Custom feedback with notes

    The feedback is stored in the `feedback` table with label format:
    - For sale_price: "sale_price:123.45"
    - For disagree: "disagree:inaccurate"
    - For accurate: "accurate:confirmed"
    - For custom: "custom:{notes}"
    """
    pool = _get_db_pool()

    # Build label based on feedback type
    feedback_type = request.feedback_type.lower()
    if feedback_type == "sale_price" and request.value:
        label = f"sale_price:{request.value}"
    elif feedback_type == "disagree":
        label = f"disagree:{request.value or 'inaccurate'}"
    elif feedback_type == "accurate":
        label = f"accurate:{request.value or 'confirmed'}"
    else:
        label = f"{feedback_type}:{request.value or request.notes or 'unspecified'}"

    if pool is None:
        # Offline mode - log and return success
        logger.info(f"[feedback/submit] Offline mode - feedback logged: item={request.item_id}, label={label}")
        return FeedbackSubmitResponse(
            success=True,
            feedback_id=None,
            message="Feedback recorded (offline mode)",
        )

    try:
        # Validate item_id is valid UUID
        try:
            item_uuid = UUID(request.item_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid item_id format")

        async with pool.acquire() as conn:
            # Insert into feedback table
            row = await conn.fetchrow(
                """
                INSERT INTO feedback (item_id, label, notes, observed_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                item_uuid,
                label,
                request.notes,
                datetime.utcnow(),
            )

            feedback_id = str(row["id"]) if row else None

            logger.info(f"[feedback/submit] Saved feedback: id={feedback_id}, item={request.item_id}, label={label}")

            return FeedbackSubmitResponse(
                success=True,
                feedback_id=feedback_id,
                message="Feedback submitted successfully",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[feedback/submit] Error saving feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {str(e)}")


@router.post("/correction", response_model=CorrectionResponse)
async def submit_correction(request: CorrectionRequest):
    """
    Submit a correction to training item data.

    Updates the training_items table's corrected_* columns:
    - corrected_price
    - corrected_condition
    - corrected_category
    - corrected_attributes
    - correction_notes
    - corrected_at (timestamp)
    """
    pool = _get_db_pool()

    if pool is None:
        # Offline mode
        logger.info(f"[feedback/correction] Offline mode - correction logged for item={request.item_id}")
        return CorrectionResponse(
            success=True,
            message="Correction recorded (offline mode)",
        )

    try:
        # Validate item_id is valid UUID
        try:
            item_uuid = UUID(request.item_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid item_id format")

        # Build update query dynamically based on provided fields
        updates = []
        params = []
        param_idx = 1

        if request.corrected_price is not None:
            updates.append(f"corrected_price = ${param_idx}")
            params.append(request.corrected_price)
            param_idx += 1

        if request.corrected_condition is not None:
            updates.append(f"corrected_condition = ${param_idx}")
            params.append(request.corrected_condition)
            param_idx += 1

        if request.corrected_category is not None:
            updates.append(f"corrected_category = ${param_idx}")
            params.append(request.corrected_category)
            param_idx += 1

        if request.corrected_attributes is not None:
            updates.append(f"corrected_attributes = ${param_idx}")
            params.append(request.corrected_attributes)
            param_idx += 1

        if request.notes is not None:
            updates.append(f"correction_notes = ${param_idx}")
            params.append(request.notes)
            param_idx += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No correction fields provided")

        # Always update corrected_at timestamp
        updates.append(f"corrected_at = ${param_idx}")
        params.append(datetime.utcnow())
        param_idx += 1

        # Add item_id as final parameter
        params.append(item_uuid)

        query = f"""
            UPDATE training_items
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
        """

        async with pool.acquire() as conn:
            result = await conn.execute(query, *params)

            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Training item not found")

            logger.info(f"[feedback/correction] Updated training_items: item={request.item_id}")

            return CorrectionResponse(
                success=True,
                message="Correction submitted successfully",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[feedback/correction] Error saving correction: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save correction: {str(e)}")
