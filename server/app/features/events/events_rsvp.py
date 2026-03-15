"""RSVP endpoints for events."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import Depends, HTTPException

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode

from .events_helpers import (
    IN_MEMORY_RSVPS,
    RsvpRequest,
    event_rsvp_limit,
    increment_sponsor_rsvp,
)

from ._router import router as rsvp_router

logger = logging.getLogger(__name__)


@rsvp_router.post("/{event_id}/rsvp", summary="RSVP to an event")
async def rsvp_event(
    event_id: str,
    request: RsvpRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(event_rsvp_limit),
):
    """RSVP to an event (going, interested, not_going). Auto-waitlists if event is full."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    if request.status not in {"going", "interested", "not_going"}:
        raise error_response(
            400,
            "Invalid RSVP status. Must be one of: going, interested, not_going",
            code=ErrorCode.VALIDATION_ERROR,
        )

    pool = get_db_pool()
    actual_status = request.status
    waitlisted = False

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Block free RSVP for paid events
                    if request.status == "going":
                        ticket_row = await conn.fetchrow(
                            "SELECT ticket_price_cents FROM events WHERE id = $1", event_id,
                        )
                        if ticket_row and ticket_row["ticket_price_cents"] and ticket_row["ticket_price_cents"] > 0:
                            raise error_response(402, "This event requires a ticket purchase", code=ErrorCode.PAYMENT_REQUIRED)

                    # Check capacity if trying to go — lock event row to prevent race
                    if request.status == "going":
                        cap_row = await conn.fetchrow(
                            "SELECT max_attendees FROM events WHERE id = $1 FOR UPDATE",
                            event_id,
                        )
                        if cap_row and cap_row["max_attendees"] is not None:
                            going_count = await conn.fetchval(
                                "SELECT COUNT(*) FROM event_attendees WHERE event_id = $1 AND status = 'going' AND user_id != $2",
                                event_id, user_id,
                            )
                            if going_count >= cap_row["max_attendees"]:
                                actual_status = "interested"
                                waitlisted = True

                    await conn.execute(
                        """
                        INSERT INTO event_attendees (event_id, user_id, status)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (event_id, user_id)
                        DO UPDATE SET status = $3
                        """,
                        event_id,
                        user_id,
                        actual_status,
                    )
                logger.info("[events] RSVP: user=%s, event=%s, status=%s, waitlisted=%s", user_id, event_id, actual_status, waitlisted)

                # Increment sponsor RSVP count if sponsored (best-effort)
                if actual_status == "going":
                    is_spons = await conn.fetchval(
                        "SELECT is_sponsored FROM events WHERE id = $1", event_id
                    )
                    if is_spons:
                        asyncio.ensure_future(increment_sponsor_rsvp(event_id))

                return {"success": True, "status": actual_status, "waitlisted": waitlisted}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error RSVP event %s: %s", event_id, e)
            raise error_response(500, "Failed to RSVP", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    IN_MEMORY_RSVPS.setdefault(event_id, {})[user_id] = actual_status
    logger.info("[events] RSVP (in-memory): user=%s, event=%s, status=%s", user_id, event_id, actual_status)
    return {"success": True, "status": actual_status, "waitlisted": waitlisted}


@rsvp_router.delete("/{event_id}/rsvp", summary="Remove RSVP from event")
async def unrsvp_event(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(event_rsvp_limit),
):
    """Remove RSVP from an event."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM event_attendees WHERE event_id = $1 AND user_id = $2",
                    event_id,
                    user_id,
                )
                logger.info("[events] Un-RSVP: user=%s, event=%s", user_id, event_id)
                return {"success": True, "message": "RSVP removed"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error un-RSVP event %s: %s", event_id, e)
            raise error_response(500, "Failed to remove RSVP", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    rsvps = IN_MEMORY_RSVPS.get(event_id, {})
    rsvps.pop(user_id, None)
    logger.info("[events] Un-RSVP (in-memory): user=%s, event=%s", user_id, event_id)
    return {"success": True, "message": "RSVP removed"}
