"""Announcement endpoints for events: post, list, mark read, batch read, unread count."""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import BackgroundTasks, Depends, HTTPException

from app.auth import get_current_user_id
from app.errors import error_response
from app.features.pagination import pagination_params
from app.lib.blocks import is_blocked
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
                  -- Only accounts that still exist. `chat_threads_v1.dm_user_a/b`
                  -- REFERENCE auth.users, and `event_attendees` has no such FK:
                  -- 3 of production's distinct attendee ids belong to deleted
                  -- accounts (checked 2026-09-17). Without this they each raise
                  -- a foreign-key violation and count as a FAILED send, which
                  -- would keep this task's summary line at warning forever.
                  AND EXISTS (SELECT 1 FROM auth.users u WHERE u.id = event_attendees.user_id)
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
            fail_count = 0

            for att_row in attendee_rows:
                attendee_id = str(att_row["user_id"])
                try:
                    # Blocking is symmetric and one chokepoint decides it
                    # (app/lib/blocks.py). An announcement is still a DM.
                    if await is_blocked(conn, author_user_id, attendee_id):
                        skip_count += 1
                        continue

                    # The attendee turned this host down before. The old code
                    # read `dm_threads.status = 'declined'` for the same reason;
                    # a decision lives in chat_dm_requests_v1 as 'denied' now
                    # (rpc_decide_dm_request_v1).
                    denied = await conn.fetchval(
                        """
                        SELECT 1 FROM public.chat_dm_requests_v1
                         WHERE status = 'denied'
                           AND ((requester_id = $1::uuid AND target_user_id = $2::uuid)
                             OR (requester_id = $2::uuid AND target_user_id = $1::uuid))
                         LIMIT 1
                        """,
                        author_user_id,
                        attendee_id,
                    )
                    if denied:
                        skip_count += 1
                        continue

                    # THE LIVE THREAD TABLE (2026-09-17). This used to find or
                    # create a row in `dm_threads` and then insert the message
                    # into `chat_messages_v1` — whose thread_id FK was repointed
                    # to `chat_threads_v1` on 2026-04-30 ("every sendMessage and
                    # markThreadRead 409'd with FK violation"). Read back on
                    # production: dm_threads holds 0 rows, so every announcement
                    # created a fresh legacy row and every message insert then
                    # violated that FK. The per-user `except` below logged a
                    # warning and moved on, so the host was told nothing and the
                    # summary line said "sent=0" — for five months.
                    #
                    # The pair is canonicalised least/greatest to match
                    # `ux_chat_threads_v1_dm_pair`, exactly as
                    # rpc_decide_dm_request_v1 does it.
                    user_a, user_b = sorted((author_user_id, attendee_id))
                    thread_id = await conn.fetchval(
                        """
                        INSERT INTO public.chat_threads_v1 (kind, created_by, dm_user_a, dm_user_b)
                        VALUES ('dm', $1::uuid, $2::uuid, $3::uuid)
                        ON CONFLICT (kind, dm_user_a, dm_user_b)
                          DO UPDATE SET updated_at = now()
                        RETURNING id
                        """,
                        author_user_id,
                        user_a,
                        user_b,
                    )

                    # Both members, or the thread is invisible to whoever is
                    # missing — chat_thread_members_v1 is what the inbox reads.
                    for member_id in (author_user_id, attendee_id):
                        await conn.execute(
                            """
                            INSERT INTO public.chat_thread_members_v1 (thread_id, user_id, role)
                            VALUES ($1::uuid, $2::uuid, 'member')
                            ON CONFLICT (thread_id, user_id) DO NOTHING
                            """,
                            thread_id,
                            member_id,
                        )

                    # The same RPC chat_router.send_message uses — one writer for
                    # a DM message, so a schema change cannot fix chat and leave
                    # announcements behind, which is this bug's whole shape.
                    row = await conn.fetchrow(
                        "SELECT id FROM rpc_send_message_v1($1::uuid, $2::uuid, $3::text)",
                        thread_id,
                        author_user_id,
                        dm_text,
                    )
                    if row is None:
                        raise RuntimeError("rpc_send_message_v1 returned no row")

                    # Nothing on chat_messages_v1 bumps the thread (read back on
                    # production: no triggers) and the inbox orders by updated_at.
                    await conn.execute(
                        "UPDATE public.chat_threads_v1 SET updated_at = now() WHERE id = $1::uuid",
                        thread_id,
                    )

                    sent_count += 1

                except Exception as per_user_err:
                    fail_count += 1
                    logger.warning(
                        "[events/dm] Failed to send announcement DM to user %s for event %s: %s",
                        attendee_id,
                        event_id,
                        per_user_err,
                    )

            log = logger.info
            if fail_count and sent_count == 0:
                # Every one failed — the shape this function was in for five
                # months while reporting it at INFO. A total failure is an error,
                # not a statistic.
                log = logger.error
            elif fail_count:
                log = logger.warning
            log(
                "[events/dm] Announcement DMs for event %s: sent=%d, skipped=%d, failed=%d, total_attendees=%d",
                event_id,
                sent_count,
                skip_count,
                fail_count,
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
                    JOIN event_attendees att
                      ON att.event_id::uuid = ea.event_id
                     AND att.user_id = $1::uuid
                     AND att.status IN ('going', 'interested')
                    LEFT JOIN event_announcement_reads ear
                      ON ear.announcement_id = ea.id AND ear.user_id = $1::uuid
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
                # Verify caller is attendee or host. event_attendees.event_id
                # is TEXT (legacy schema mismatch — the rest of the system
                # uses uuid), while events.id is UUID. Cast both sides on the
                # event_attendees branch so it doesn't fail with
                # "operator does not exist: text = uuid". Other handlers in
                # this file only query `events`, so they don't hit this.
                access_row = await conn.fetchrow(
                    """
                    SELECT 1 FROM event_attendees
                        WHERE event_id::uuid = $1::uuid AND user_id = $2::uuid
                            AND status IN ('going', 'interested')
                    UNION ALL
                    SELECT 1 FROM events
                        WHERE id = $1::uuid AND created_by = $2::uuid
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
                        ON ear.announcement_id = ea.id AND ear.user_id = $2::uuid
                    WHERE ea.event_id = $1::uuid
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
            try:
                from app.features.data_moat import record_demand_signal
                await record_demand_signal(
                    signal_type="event_announcement_read",
                    item_key=event_id,
                    user_id=user_id,
                )
            except Exception:
                pass
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
