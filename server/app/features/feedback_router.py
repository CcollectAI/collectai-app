"""
Feedback router for capturing user feedback on predictions.

Endpoints:
- GET  /feedback/corrections - List training items with corrections (paginated)
- POST /feedback/submit - Save feedback to feedback table
- POST /feedback/correction - Update training_items.corrected_* columns
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.errors import error_response
from app.features.pagination import pagination_params

router = APIRouter(prefix="/feedback", tags=["feedback"])
logger = logging.getLogger(__name__)


def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except (ImportError, RuntimeError, OSError) as e:
        logger.debug(f"DB pool not available: {e}")
        return None


class FeedbackSubmitRequest(BaseModel):
    """Request body for submitting feedback."""
    item_id: str = Field(..., max_length=64, description="UUID of the item")
    feedback_type: str = Field(
        ...,
        max_length=50,
        description="Type of feedback: sale_price, disagree, accurate, or custom"
    )
    value: str | None = Field(
        None,
        max_length=500,
        description="Value for the feedback (e.g., sale price amount)"
    )
    notes: str | None = Field(
        None,
        max_length=2000,
        description="Optional notes about the feedback"
    )


class FeedbackSubmitResponse(BaseModel):
    """Response from feedback submission."""
    success: bool
    feedback_id: str | None = None
    message: str


ALLOWED_CURRENCIES = {"EUR", "USD", "GBP", "JPY"}


class VerifiedSaleRequest(BaseModel):
    """Request body for reporting a verified sale."""
    item_id: str = Field(..., max_length=64, description="UUID of the item sold")
    sale_price: float = Field(..., gt=0, le=1_000_000, description="Actual sale price")
    currency: str = Field("EUR", max_length=3, description="ISO currency code (EUR/USD/GBP/JPY)")
    platform: str | None = Field(None, max_length=100, description="Where the sale happened (eBay, Mercari, etc.)")
    condition: str | None = Field(None, max_length=100, description="Item condition at time of sale")
    sold_at: str | None = Field(None, description="When the sale happened (ISO 8601)")
    notes: str | None = Field(None, max_length=2000, description="Additional details about the sale")


class VerifiedSaleResponse(BaseModel):
    """Response from verified sale submission."""
    success: bool
    sale_id: str | None = None
    message: str


class CorrectionRequest(BaseModel):
    """Request body for submitting a correction to training data."""
    item_id: str = Field(..., max_length=64, description="UUID of the training item")
    corrected_price: float | None = Field(
        None,
        description="Corrected price value"
    )
    corrected_condition: str | None = Field(
        None,
        max_length=100,
        description="Corrected condition (e.g., 'Near Mint', 'Good')"
    )
    corrected_category: str | None = Field(
        None,
        max_length=64,
        description="Corrected category"
    )
    corrected_attributes: dict[str, Any] | None = Field(
        None,
        description="Corrected attributes JSON"
    )
    notes: str | None = Field(
        None,
        max_length=2000,
        description="Notes about the correction"
    )


class CorrectionResponse(BaseModel):
    """Response from correction submission."""
    success: bool
    message: str


async def _log_provenance_event(
    pool, item_id: str, user_id: str, event_type: str,
    note: str | None = None, source: str = "manual", metadata: dict | None = None,
) -> None:
    """
    Insert a provenance event into item_provenance_events.

    Best-effort: logs a warning on failure but does not raise.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.item_provenance_events
                    (item_id, user_id, event_type, note, source, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                item_id,
                user_id,
                event_type,
                note,
                source,
                json.dumps(metadata or {}),
            )
        logger.info(
            "[feedback] Auto-logged provenance event: item=%s, type=%s",
            item_id, event_type,
        )
    except asyncpg.PostgresError as e:
        logger.warning(
            "[feedback] Failed to auto-log provenance event for item=%s: %s",
            item_id, e,
        )


class CorrectionListItem(BaseModel):
    """A single correction entry returned in the list."""
    item_id: str
    corrected_price: float | None = None
    corrected_condition: str | None = None
    corrected_category: str | None = None
    corrected_attributes: dict[str, Any] | None = None
    correction_notes: str | None = None
    corrected_at: str | None = None


class CorrectionListResponse(BaseModel):
    """Response for listing corrections."""
    corrections: list[CorrectionListItem]


@router.get("/corrections", response_model=CorrectionListResponse)
async def list_corrections(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """
    List training items that have user corrections applied.

    Returns items where at least one corrected_* column is non-null,
    ordered by most recently corrected first.
    """
    limit, offset = pagination
    pool = _get_db_pool()

    if pool is None:
        return CorrectionListResponse(corrections=[])

    try:
        async with pool.acquire() as conn:
            # Scope corrections to items owned by the current user via
            # taxonomy_corrections join (which records user_id)
            rows = await conn.fetch(
                """
                SELECT t.id, t.corrected_price, t.corrected_condition,
                       t.corrected_category, t.corrected_attributes,
                       t.correction_notes, t.corrected_at
                FROM training_items t
                INNER JOIN public.taxonomy_corrections tc
                    ON tc.item_id = t.id::text AND tc.user_id = $3
                WHERE t.corrected_at IS NOT NULL
                ORDER BY t.corrected_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
                user_id,
            )

        corrections = [
            CorrectionListItem(
                item_id=str(row["id"]),
                corrected_price=float(row["corrected_price"]) if row["corrected_price"] is not None else None,
                corrected_condition=row["corrected_condition"],
                corrected_category=row["corrected_category"],
                corrected_attributes=(
                    json.loads(row["corrected_attributes"])
                    if isinstance(row["corrected_attributes"], str)
                    else row["corrected_attributes"]
                ) if row["corrected_attributes"] is not None else None,
                correction_notes=row["correction_notes"],
                corrected_at=row["corrected_at"].isoformat() if row["corrected_at"] else None,
            )
            for row in rows
        ]
        return CorrectionListResponse(corrections=corrections)

    except asyncpg.PostgresError as e:
        logger.error("[feedback/corrections] Error listing corrections: %s", e)
        return CorrectionListResponse(corrections=[])


@router.post("/submit", response_model=FeedbackSubmitResponse)
async def submit_feedback(request: FeedbackSubmitRequest, user_id: str = Depends(get_current_user_id)):
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
            raise error_response(400, "Invalid item_id format", code="VALIDATION_ERROR")

        async with pool.acquire() as conn:
            # Verify item ownership before recording feedback
            owner_check = await conn.fetchval(
                "SELECT 1 FROM public.items WHERE id = $1::uuid AND user_id = $2::uuid",
                str(item_uuid),
                user_id,
            )
            if owner_check is None:
                raise error_response(404, "Item not found", code="NOT_FOUND")

            # Insert into feedback table (user_id may be NULL if column not yet migrated)
            row = await conn.fetchrow(
                """
                INSERT INTO feedback (item_id, label, notes, observed_at, user_id)
                VALUES ($1, $2, $3, $4, $5::uuid)
                RETURNING id
                """,
                item_uuid,
                label,
                request.notes,
                datetime.now(timezone.utc),
                user_id,
            )

            feedback_id = str(row["id"]) if row else None

            logger.info(f"[feedback/submit] Saved feedback: id={feedback_id}, item={request.item_id}, label={label}")

        # Task 3: Auto-log provenance event for sale_price feedback
        if feedback_type == "sale_price" and request.value:
            sale_note = f"Sale reported at {request.value} EUR"
            if request.notes:
                sale_note += f" - {request.notes}"
            await _log_provenance_event(
                pool,
                item_id=request.item_id,
                user_id=user_id,
                event_type="sale",
                note=sale_note,
                source="manual",
                metadata={"sale_price": request.value, "feedback_id": feedback_id},
            )

        return FeedbackSubmitResponse(
            success=True,
            feedback_id=feedback_id,
            message="Feedback submitted successfully",
        )

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[feedback/submit] Error saving feedback: %s", e)
        raise error_response(500, "Failed to save feedback", code="DB_ERROR")
    except Exception as e:
        logger.error("[feedback/submit] Unexpected error: %s", e)
        raise error_response(500, "Failed to save feedback", code="INTERNAL_ERROR")


@router.post("/verified-sale", response_model=VerifiedSaleResponse)
async def submit_verified_sale(
    request: VerifiedSaleRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Report a verified sale for an item you own.

    Verified sales are high-quality ground-truth data points that receive
    2x weight in ML model training. This builds the data moat by capturing
    real transaction prices that competitors cannot access.
    """
    # Validate currency (before DB check so offline mode also validates)
    if request.currency not in ALLOWED_CURRENCIES:
        raise error_response(
            400,
            f"Invalid currency. Allowed: {', '.join(sorted(ALLOWED_CURRENCIES))}",
            code="VALIDATION_ERROR",
        )

    # Parse and validate sold_at (before DB check)
    sold_at_ts = None
    if request.sold_at:
        try:
            sold_at_ts = datetime.fromisoformat(
                request.sold_at.replace("Z", "+00:00")
            )
        except ValueError:
            raise error_response(400, "Invalid sold_at format", code="VALIDATION_ERROR")
        if sold_at_ts > datetime.now(timezone.utc):
            raise error_response(400, "sold_at cannot be in the future", code="VALIDATION_ERROR")

    pool = _get_db_pool()

    if pool is None:
        logger.info(
            "[feedback/verified-sale] Offline mode: item=%s, price=%s %s",
            request.item_id, request.sale_price, request.currency,
        )
        return VerifiedSaleResponse(
            success=True, sale_id=None,
            message="Verified sale recorded (offline mode)",
        )

    try:

        try:
            item_uuid = UUID(request.item_id)
        except ValueError:
            raise error_response(400, "Invalid item_id format", code="VALIDATION_ERROR")

        async with pool.acquire() as conn:
            # Verify item ownership
            item_row = await conn.fetchrow(
                "SELECT category FROM public.items WHERE id = $1::uuid AND user_id = $2::uuid",
                str(item_uuid), user_id,
            )
            if item_row is None:
                raise error_response(404, "Item not found", code="NOT_FOUND")

            # Rate limit: max 1 verified sale per item per 24h per user
            recent = await conn.fetchval(
                """
                SELECT 1 FROM public.verified_sales
                WHERE item_id = $1 AND user_id = $2::uuid
                  AND created_at > now() - interval '24 hours'
                LIMIT 1
                """,
                item_uuid, user_id,
            )
            if recent:
                raise error_response(
                    429, "Already submitted a sale for this item in the last 24 hours",
                    code="RATE_LIMITED",
                )

            category = item_row["category"] or "unknown"

            row = await conn.fetchrow(
                """
                INSERT INTO public.verified_sales
                    (item_id, user_id, category, sale_price, currency,
                     platform, condition, sold_at, notes)
                VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                item_uuid, user_id, category, request.sale_price,
                request.currency, request.platform, request.condition,
                sold_at_ts, request.notes,
            )
            sale_id = str(row["id"]) if row else None

        # Log provenance event
        sale_note = f"Verified sale at {request.sale_price} {request.currency}"
        if request.platform:
            sale_note += f" on {request.platform}"
        await _log_provenance_event(
            pool, item_id=request.item_id, user_id=user_id,
            event_type="verified_sale", note=sale_note, source="user",
            metadata={
                "sale_price": request.sale_price,
                "currency": request.currency,
                "platform": request.platform,
                "sale_id": sale_id,
            },
        )

        logger.info(
            "[feedback/verified-sale] Recorded: id=%s, item=%s, %s %s",
            sale_id, request.item_id, request.sale_price, request.currency,
        )
        return VerifiedSaleResponse(
            success=True, sale_id=sale_id,
            message="Verified sale recorded successfully",
        )

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[feedback/verified-sale] DB error: %s", e)
        raise error_response(500, "Failed to record sale", code="DB_ERROR")
    except Exception as e:
        logger.error("[feedback/verified-sale] Error: %s", e)
        raise error_response(500, "Failed to record sale", code="INTERNAL_ERROR")


@router.post("/correction", response_model=CorrectionResponse)
async def submit_correction(request: CorrectionRequest, user_id: str = Depends(get_current_user_id)):
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
            raise error_response(400, "Invalid item_id format", code="VALIDATION_ERROR")

        # Verify the training item exists before updating
        # (training_items are system-wide but corrections are user-attributed)

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
            raise error_response(400, "No correction fields provided", code="VALIDATION_ERROR")

        # Always update corrected_at timestamp and corrected_by user for audit trail
        updates.append(f"corrected_at = ${param_idx}")
        params.append(datetime.now(timezone.utc))
        param_idx += 1

        updates.append(f"corrected_by = ${param_idx}")
        params.append(user_id)
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

            if result.endswith(" 0"):
                raise error_response(404, "Training item not found", code="VALIDATION_ERROR")

            logger.info(f"[feedback/correction] Updated training_items: item={request.item_id}")

            # Task 2: Log taxonomy correction if corrected_category is provided
            if request.corrected_category is not None:
                try:
                    # Fetch the original category from training_items
                    row = await conn.fetchrow(
                        "SELECT category FROM training_items WHERE id = $1",
                        item_uuid,
                    )
                    original_category = row["category"] if row and row["category"] else "unknown"

                    await conn.execute(
                        """
                        INSERT INTO public.taxonomy_corrections
                            (user_id, item_id, original_category, corrected_category, source)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        user_id,
                        request.item_id,
                        original_category,
                        request.corrected_category,
                        "feedback",
                    )
                    logger.info(
                        "[feedback/correction] Logged taxonomy correction: item=%s, %s -> %s",
                        request.item_id, original_category, request.corrected_category,
                    )
                except asyncpg.PostgresError as e:
                    logger.warning(
                        "[feedback/correction] Failed to log taxonomy correction for item=%s: %s",
                        request.item_id, e,
                    )

            return CorrectionResponse(
                success=True,
                message="Correction submitted successfully",
            )

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[feedback/correction] Error saving correction: %s", e)
        raise error_response(500, "Failed to save correction", code="DB_ERROR")
    except Exception as e:
        logger.error("[feedback/correction] Unexpected error: %s", e)
        raise error_response(500, "Failed to save correction", code="INTERNAL_ERROR")
