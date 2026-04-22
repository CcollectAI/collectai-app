"""Announcement endpoints for events: post, list, mark read, batch read, unread count."""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import BackgroundTasks, Depends, HTTPException

from app.auth import get_current_user_id
from app.errors import error_response
from app.features.pagination import pagination_params
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode

from .events_helpers import (
    AnnouncementRequest,
    AnnouncementResponse,
    BatchReadRequest,
    event_announce_limit,
)

from ._router import router as announcements_router

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DM helper (background task)
# ---------------------------------------------------------------------------

async def _send_announcement_dms(
    pool,
    event_id: str,
    author_user_id: str,
    event_title: str,
    announcement_title: str | None,
    announcement_body: str,
) -> None:
    """Send a DM to every attendee (going/interested) for an event announcement.

    For each attendee, this finds or creates a DM thread between the event host
    (author) and the attendee, then inserts a chat message with the announcement
    content. Runs as a background task so the announcement response is not delayed.

    Errors are logged but never propagated — DM delivery is best-effort.
    """
    try:
        async with pool.acquire() as conn:
            # Fetch all attendees who are going or interested, excluding the author
            attendee_rows = await conn.fetch(
                """
                SELECT user_id
                FROM event_attendees
                WHERE event_id = $1
                  AND status IN ('going', 'interested')
                  AND user_id != $2::uuid
                """,
                event_id,
                author_user_id,
            )

            if not attendee_rows:
                logger.info(
                    "[events/dm] No attendees to notify for event %s announcement",
                    event_id,
                )
                return

            # Build the DM message text
            subject = announcement_title or "Event Announcement"
            dm_text = f"[{event_title}] {subject}\n\n{announcement_body}"
            # Cap at 2000 chars to stay within typical message limits
            if len(dm_text) > 2000:
                dm_text = dm_text[:1997] + "..."

            sent_count = 0
            skip_count = 0

            for att_row in attendee_rows:
                attendee_id = str(att_row["user_id"])
                try:
                    # Check if a DM thread already exists between host and attendee
                    thread_row = await conn.fetchrow(
                        """
                        SELECT id, status
                        FROM dm_threads
                        WHERE (requester_id = $1::uuid AND responder_id = $2::uuid)
                           OR (requester_id = $2::uuid AND responder_id = $1::uuid)
                        LIMIT 1
                        """,
                        author_user_id,
                        attendee_id,
                    )

                    if thread_row is not None:
                        # Skip declined threads — respect the user's choice
                        if thread_row["status"] == "declined":
                            skip_count += 1
                            continue
                        thread_id = str(thread_row["id"])
                    else:
                        # Create a new thread (auto-accepted since it's a host announcement)
                        new_thread = await conn.fetchrow(
                            """
                            INSERT INTO dm_threads (requester_id, responder_id, status)
                            VALUES ($1::uuid, $2::uuid, 'accepted')
                            RETURNING id
                            """,
                            author_user_id,
                            attendee_id,
                        )
                        thread_id = str(new_thread["id"])

                    # Insert the announcement message into chat_messages_v1
                    # (legacy `chat_messages` is room-based with columns
                    # room_id/user_id/text — wrong shape for DMs). 2026-04-22.
                    await conn.execute(
                        """
                        INSERT INTO chat_messages_v1 (thread_id, user_id, body)
                        VALUES ($1::uuid, $2::uuid, $3)
                        """,
                        thread_id,
                        author_user_id,
                        dm_text,
                    )

                    # Update thread timestamp so it surfaces in the inbox
                    await conn.execute(
                        "UPDATE dm_threads SET updated_at = now() WHERE id = $1::uuid",
                        thread_id,
                    )

                    sent_count += 1

                except Exception as per_user_err:
                    logger.warning(
                        "[events/dm] Failed to send announcement DM to user %s for event %s: %s",
                        attendee_id,
                        event_id,
                        per_user_err,
                    )

            logger.info(
                "[events/dm] Announcement DMs for event %s: sent=%d, skipped=%d, total_attendees=%d",
                event_id,
                sent_count,
                skip_count,
                len(attendee_rows),
            )

    except Exception as e:
        logger.error(
            "[events/dm] Failed to send announcement DMs for event %s: %s",
            event_id,
            e,
        )


# ---------------------------------------------------------------------------
# Endpoints — Unread announcement count (MUST be before /{event_id})
# ---------------------------------------------------------------------------

@announcements_router.get("/my-announcements/unread-count", summary="Get unread announcement count")
async def get_unread_announcement_count(
    user_id: str = Depends(get_current_user_id),
):
    """Get total unread announcement count across all events the user attends."""
    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM event_announcements ea
                    JOIN event_attendees att ON att.event_id = ea.event_id
                        AND att.user_id = $1 AND att.status IN ('going', 'interested')
                    LEFT JOIN event_announcement_reads ear
                        ON ear.announcement_id = ea.id AND ear.user_id = $1
                    WHERE ear.user_id IS NULL
                    """,
                    user_id,
                )
                return {"unread_count": row["cnt"] if row else 0}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error fetching unread count: %s", e)
            raise error_response(500, "Failed to get unread count", code=ErrorCode.INTERNAL_ERROR)

    return {"unread_count": 0}


# ---------------------------------------------------------------------------
# Endpoints — Announcements (parameterized)
# ---------------------------------------------------------------------------

@announcements_router.post("/{event_id}/announcements", response_model=AnnouncementResponse, status_code=201, summary="Post event announcement")
async def post_announcement(
    event_id: str,
    request: AnnouncementRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(event_announce_limit),
):
    """Post an announcement to event attendees (host or sponsor admin only).

    After creating the announcement record, a background task sends a DM to
    every attendee (going/interested) so the announcement also appears in their
    chat inbox.
    """
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Verify caller is event creator or sponsor company admin
                auth_row = await conn.fetchrow(
                    """
                    SELECT e.title AS event_title
                    FROM events e WHERE e.id = $1 AND e.created_by = $2
                    UNION ALL
                    SELECT e.title AS event_title
                    FROM events e
                    JOIN sponsor_companies sc ON sc.id = e.sponsor_company_id
                    WHERE e.id = $1 AND sc.admin_user_id = $2
                    """,
                    event_id, user_id,
                )
                if not auth_row:
                    raise error_response(403, "Only event host or sponsor admin can post announcements", code=ErrorCode.FORBIDDEN)

                event_title = auth_row.get("event_title", "Event")

                row = await conn.fetchrow(
                    """
                    INSERT INTO event_announcements (event_id, author_user_id, title, body, image_url)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING *
                    """,
                    event_id, user_id, request.title, request.body, request.image_url,
                )

                # Schedule DM delivery to all attendees as a background task
                background_tasks.add_task(
                    _send_announcement_dms,
                    pool,
                    event_id,
                    user_id,
                    event_title,
                    request.title,
                    request.body,
                )

                return AnnouncementResponse(
                    id=str(row["id"]),
                    event_id=str(row["event_id"]),
                    author_user_id=str(row["author_user_id"]),
                    title=row.get("title"),
                    body=row["body"],
                    image_url=row.get("image_url"),
                    created_at=str(row["created_at"]) if row.get("created_at") else None,
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error posting announcement for event %s: %s", event_id, e)
            raise error_response(500, "Failed to post announcement", code=ErrorCode.INTERNAL_ERROR)

    raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)


@announcements_router.get("/{event_id}/announcements", response_model=List[AnnouncementResponse], summary="List event announcements")
async def list_announcements(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """List announcements for an event (attendees only). Includes is_read status."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    limit, offset = pagination
    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Verify caller is attendee or host
                access_row = await conn.fetchrow(
                    """
                    SELECT 1 FROM event_attendees WHERE event_id = $1 AND user_id = $2
                        AND status IN ('going', 'interested')
                    UNION ALL
                    SELECT 1 FROM events WHERE id = $1 AND created_by = $2
                    """,
                    event_id, user_id,
                )
                if not access_row:
                    raise error_response(403, "Only attendees can view announcements", code=ErrorCode.FORBIDDEN)

                rows = await conn.fetch(
                    """
                    SELECT ea.*,
                           (ear.user_id IS NOT NULL) AS is_read
                    FROM event_announcements ea
                    LEFT JOIN event_announcement_reads ear
                        ON ear.announcement_id = ea.id AND ear.user_id = $2
                    WHERE ea.event_id = $1
                    ORDER BY ea.created_at DESC
                    LIMIT $3 OFFSET $4
                    """,
                    event_id, user_id, limit, offset,
                )
                return [
                    AnnouncementResponse(
                        id=str(r["id"]),
                        event_id=str(r["event_id"]),
                        author_user_id=str(r["author_user_id"]),
                        title=r.get("title"),
                        body=r["body"],
                        image_url=r.get("image_url"),
                        is_read=r.get("is_read", False),
                        created_at=str(r["created_at"]) if r.get("created_at") else None,
                    )
                    for r in rows
                ]

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error listing announcements for event %s: %s", event_id, e)
            raise error_response(500, "Failed to list announcements", code=ErrorCode.INTERNAL_ERROR)

    return []


@announcements_router.post("/{event_id}/announcements/{announcement_id}/read", summary="Mark announcement as read")
async def mark_announcement_read(
    event_id: str,
    announcement_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Mark a single announcement as read."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)
    try:
        UUID(announcement_id)
    except ValueError:
        raise error_response(400, "Invalid announcement_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO event_announcement_reads (announcement_id, user_id)
                    VALUES ($1, $2)
                    ON CONFLICT (announcement_id, user_id) DO NOTHING
                    """,
                    announcement_id, user_id,
                )
                return {"success": True}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error marking announcement read: %s", e)
            raise error_response(500, "Failed to mark announcement read", code=ErrorCode.INTERNAL_ERROR)

    return {"success": True}


@announcements_router.post("/{event_id}/announcements/batch-read", summary="Batch mark announcements read")
async def batch_mark_announcements_read(
    event_id: str,
    body: BatchReadRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Mark multiple announcements as read in a single call."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    valid_ids = []
    for aid in body.announcement_ids:
        try:
            UUID(aid)
            valid_ids.append(aid)
        except ValueError:
            continue

    if not valid_ids:
        return {"success": True, "marked": 0}

    pool = get_db_pool()
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO event_announcement_reads (announcement_id, user_id)
                    VALUES ($1, $2)
                    ON CONFLICT (announcement_id, user_id) DO NOTHING
                    """,
                    [(aid, user_id) for aid in valid_ids],
                )
                return {"success": True, "marked": len(valid_ids)}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error batch marking announcements read: %s", e)
            raise error_response(500, "Failed to batch mark announcements read", code=ErrorCode.INTERNAL_ERROR)

    return {"success": True, "marked": len(valid_ids)}
