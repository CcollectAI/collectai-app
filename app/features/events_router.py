"""
Events router for community events, drops, meetups, streams, and conventions.

Endpoints:
- GET    /events                       - List personalized events
- POST   /events                       - Create an event
- GET    /events/{event_id}            - Get single event detail
- POST   /events/{event_id}/rsvp       - RSVP to an event
- DELETE  /events/{event_id}/rsvp      - Un-RSVP from an event
- GET    /events/categories/followed   - List followed categories
- POST   /events/categories/{category_id}/follow   - Follow a category
- DELETE  /events/categories/{category_id}/follow   - Unfollow a category
- GET    /events/categories/{category_id}/following - Check if following
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger(__name__)

ALLOWED_EVENT_KINDS = {"collection_drop", "meetup", "stream", "convention", "release"}
ALLOWED_EVENT_FORMATS = {"in_person", "online", "hybrid"}


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except Exception as e:
        logger.debug("DB pool not available: %s", e)
        return None


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def get_current_user_id() -> str:
    # TODO: replace with real auth
    return "demo-user"


def get_optional_user_id() -> Optional[str]:
    """Return user_id if authenticated, None otherwise."""
    # TODO: replace with real auth — for now always returns the demo user
    return "demo-user"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateEventRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    kind: str = Field(..., max_length=50, pattern=r"^(collection_drop|meetup|stream|convention|release)$")
    category_id: Optional[str] = Field(None, max_length=64)
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
    time: Optional[str] = Field(None, max_length=10)
    end_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    location: Optional[str] = Field(None, max_length=500)
    online_url: Optional[str] = Field(None, max_length=2048)
    description: str = Field(default="", max_length=5000)
    format: str = Field(default="in_person", pattern=r"^(in_person|online|hybrid)$")
    is_public: bool = True
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class RsvpRequest(BaseModel):
    status: str = Field(default="going", pattern=r"^(going|interested|not_going)$")


class FollowCategoryRequest(BaseModel):
    category_id: str = Field(..., min_length=1, max_length=64)


class EventResponse(BaseModel):
    id: str
    title: str
    kind: str
    category_id: Optional[str] = None
    date: str
    time: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    online_url: Optional[str] = None
    description: str = ""
    format: str = "in_person"
    is_public: bool = True
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_by: Optional[str] = None
    source: str = "user"
    attendee_count: int = 0
    user_rsvp_status: Optional[str] = None
    created_at: Optional[str] = None


class EventListResponse(BaseModel):
    events: List[EventResponse]


# ---------------------------------------------------------------------------
# In-memory fallback stores (used when DB is disabled)
# ---------------------------------------------------------------------------

_IN_MEMORY_EVENTS: dict[str, dict[str, Any]] = {}
_IN_MEMORY_RSVPS: dict[str, dict[str, str]] = {}  # event_id -> {user_id: status}
_IN_MEMORY_FOLLOWS: dict[str, set[str]] = {}  # user_id -> set of category_ids


# ---------------------------------------------------------------------------
# Endpoints — Events
# ---------------------------------------------------------------------------

@router.get("", response_model=EventListResponse)
async def list_events(
    category_id: Optional[str] = Query(None, description="Filter by category"),
    include_past: bool = Query(False, description="Include past events"),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """
    List events, optionally filtered by category.

    If the user is authenticated and the DB is available, calls
    rpc_list_personalized_events_v1 for personalized ordering.
    Otherwise returns all future events.
    """
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                if user_id:
                    # Try the personalized RPC first
                    try:
                        rows = await conn.fetch(
                            "SELECT * FROM rpc_list_personalized_events_v1($1, $2, $3)",
                            user_id,
                            category_id,
                            include_past,
                        )
                    except Exception as rpc_err:
                        logger.warning("[events] Personalized RPC failed, falling back: %s", rpc_err)
                        rows = await _fetch_events_basic(conn, category_id, include_past)
                else:
                    rows = await _fetch_events_basic(conn, category_id, include_past)

                events = []
                for row in rows:
                    ev = _row_to_event(dict(row), user_id=user_id)
                    # Hide non-public events unless the user is the creator
                    if not ev.is_public and ev.created_by != user_id:
                        continue
                    events.append(ev)
                return EventListResponse(events=events)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error listing events: %s", e)
            raise HTTPException(status_code=500, detail="Failed to list events")

    # Offline / in-memory fallback
    today_str = date.today().isoformat()
    events = []
    for ev in _IN_MEMORY_EVENTS.values():
        if not include_past and ev.get("date", "") < today_str:
            continue
        if category_id and ev.get("category_id") != category_id:
            continue
        # Hide non-public events unless the user is the creator
        if not ev.get("is_public", True) and ev.get("created_by") != user_id:
            continue
        rsvps = _IN_MEMORY_RSVPS.get(ev["id"], {})
        ev_copy = {**ev, "attendee_count": len(rsvps)}
        if user_id:
            ev_copy["user_rsvp_status"] = rsvps.get(user_id)
        events.append(EventResponse(**ev_copy))
    return EventListResponse(events=events)


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(
    request: CreateEventRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new community event."""
    if request.kind not in ALLOWED_EVENT_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event kind: {request.kind}. "
                   f"Allowed: {', '.join(sorted(ALLOWED_EVENT_KINDS))}",
        )

    if request.format not in ALLOWED_EVENT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event format: {request.format}. "
                   f"Allowed: {', '.join(sorted(ALLOWED_EVENT_FORMATS))}",
        )

    # Validate date format
    try:
        datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    if request.end_date:
        try:
            datetime.strptime(request.end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD.")

    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO events (
                        title, kind, category_id, date, time, end_date,
                        location, online_url, description, created_by, source,
                        format, is_public, latitude, longitude
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'user',
                            $11, $12, $13, $14)
                    RETURNING *
                    """,
                    request.title,
                    request.kind,
                    request.category_id,
                    request.date,
                    request.time,
                    request.end_date,
                    request.location,
                    request.online_url,
                    request.description,
                    user_id,
                    request.format,
                    request.is_public,
                    request.latitude,
                    request.longitude,
                )
                return _row_to_event(dict(row), user_id=user_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error creating event: %s", e)
            raise HTTPException(status_code=500, detail="Failed to create event")

    # Offline / in-memory fallback
    event_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    event_data = {
        "id": event_id,
        "title": request.title,
        "kind": request.kind,
        "category_id": request.category_id,
        "date": request.date,
        "time": request.time,
        "end_date": request.end_date,
        "location": request.location,
        "online_url": request.online_url,
        "description": request.description,
        "format": request.format,
        "is_public": request.is_public,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "created_by": user_id,
        "source": "user",
        "attendee_count": 0,
        "created_at": now,
    }
    _IN_MEMORY_EVENTS[event_id] = event_data
    logger.info("[events] Created event (in-memory): id=%s, title=%s", event_id, request.title)
    return EventResponse(**event_data)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Get a single event by ID, including attendee count and user RSVP status."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Try the view with attendee info first
                try:
                    row = await conn.fetchrow(
                        "SELECT * FROM v_events_with_attendees_v1 WHERE id = $1",
                        event_id,
                    )
                except Exception as view_err:
                    logger.warning("[events] View query failed, falling back to events table: %s", view_err)
                    row = await conn.fetchrow(
                        "SELECT * FROM events WHERE id = $1",
                        event_id,
                    )

                if row is None:
                    raise HTTPException(status_code=404, detail="Event not found")

                event = _row_to_event(dict(row), user_id=user_id)

                # If the view didn't include rsvp status, look it up separately
                if user_id and event.user_rsvp_status is None:
                    try:
                        rsvp_row = await conn.fetchrow(
                            "SELECT status FROM event_attendees WHERE event_id = $1 AND user_id = $2",
                            event_id,
                            user_id,
                        )
                        if rsvp_row:
                            event.user_rsvp_status = rsvp_row["status"]
                    except Exception as e:
                        logger.warning("[events] RSVP lookup failed for user=%s event=%s: %s", user_id, event_id, e)

                return event

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error fetching event %s: %s", event_id, e)
            raise HTTPException(status_code=500, detail="Failed to fetch event")

    # Offline / in-memory fallback
    ev = _IN_MEMORY_EVENTS.get(event_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Event not found")

    rsvps = _IN_MEMORY_RSVPS.get(event_id, {})
    ev_copy = {**ev, "attendee_count": len(rsvps)}
    if user_id:
        ev_copy["user_rsvp_status"] = rsvps.get(user_id)
    return EventResponse(**ev_copy)


# ---------------------------------------------------------------------------
# Endpoints — RSVP
# ---------------------------------------------------------------------------

@router.post("/{event_id}/rsvp")
async def rsvp_event(
    event_id: str,
    request: RsvpRequest,
    user_id: str = Depends(get_current_user_id),
):
    """RSVP to an event (going, interested, not_going)."""
    if request.status not in {"going", "interested", "not_going"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid RSVP status. Must be one of: going, interested, not_going",
        )

    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO event_attendees (event_id, user_id, status)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (event_id, user_id)
                    DO UPDATE SET status = $3, updated_at = now()
                    """,
                    event_id,
                    user_id,
                    request.status,
                )
                logger.info("[events] RSVP: user=%s, event=%s, status=%s", user_id, event_id, request.status)
                return {"success": True, "status": request.status}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error RSVP event %s: %s", event_id, e)
            raise HTTPException(status_code=500, detail="Failed to RSVP")

    # Offline / in-memory fallback
    _IN_MEMORY_RSVPS.setdefault(event_id, {})[user_id] = request.status
    logger.info("[events] RSVP (in-memory): user=%s, event=%s, status=%s", user_id, event_id, request.status)
    return {"success": True, "status": request.status}


@router.delete("/{event_id}/rsvp")
async def unrsvp_event(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Remove RSVP from an event."""
    pool = _get_db_pool()

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
            raise HTTPException(status_code=500, detail="Failed to remove RSVP")

    # Offline / in-memory fallback
    rsvps = _IN_MEMORY_RSVPS.get(event_id, {})
    rsvps.pop(user_id, None)
    logger.info("[events] Un-RSVP (in-memory): user=%s, event=%s", user_id, event_id)
    return {"success": True, "message": "RSVP removed"}


# ---------------------------------------------------------------------------
# Endpoints — Category follows
# ---------------------------------------------------------------------------

@router.get("/categories/followed")
async def list_followed_categories(
    user_id: str = Depends(get_current_user_id),
):
    """List all category IDs the current user follows."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT category_id FROM user_category_follows WHERE user_id = $1",
                    user_id,
                )
                return {"categories": [row["category_id"] for row in rows]}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error listing followed categories: %s", e)
            raise HTTPException(status_code=500, detail="Failed to list followed categories")

    # Offline / in-memory fallback
    follows = _IN_MEMORY_FOLLOWS.get(user_id, set())
    return {"categories": sorted(follows)}


@router.post("/categories/{category_id}/follow")
async def follow_category(
    category_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Follow a category for event notifications."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO user_category_follows (user_id, category_id)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id, category_id) DO NOTHING
                    """,
                    user_id,
                    category_id,
                )
                logger.info("[events] Follow category: user=%s, category=%s", user_id, category_id)
                return {"success": True, "category_id": category_id}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error following category %s: %s", category_id, e)
            raise HTTPException(status_code=500, detail="Failed to follow category")

    # Offline / in-memory fallback
    _IN_MEMORY_FOLLOWS.setdefault(user_id, set()).add(category_id)
    logger.info("[events] Follow category (in-memory): user=%s, category=%s", user_id, category_id)
    return {"success": True, "category_id": category_id}


@router.delete("/categories/{category_id}/follow")
async def unfollow_category(
    category_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Unfollow a category."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM user_category_follows WHERE user_id = $1 AND category_id = $2",
                    user_id,
                    category_id,
                )
                logger.info("[events] Unfollow category: user=%s, category=%s", user_id, category_id)
                return {"success": True, "message": "Category unfollowed"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error unfollowing category %s: %s", category_id, e)
            raise HTTPException(status_code=500, detail="Failed to unfollow category")

    # Offline / in-memory fallback
    follows = _IN_MEMORY_FOLLOWS.get(user_id, set())
    follows.discard(category_id)
    logger.info("[events] Unfollow category (in-memory): user=%s, category=%s", user_id, category_id)
    return {"success": True, "message": "Category unfollowed"}


@router.get("/categories/{category_id}/following")
async def check_following_category(
    category_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Check whether the current user follows a given category."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT 1 FROM user_category_follows WHERE user_id = $1 AND category_id = $2",
                    user_id,
                    category_id,
                )
                return {"following": row is not None}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error checking follow status: %s", e)
            raise HTTPException(status_code=500, detail="Failed to check follow status")

    # Offline / in-memory fallback
    follows = _IN_MEMORY_FOLLOWS.get(user_id, set())
    return {"following": category_id in follows}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch_events_basic(conn, category_id: Optional[str], include_past: bool):
    """Fetch events from the events table with optional filters."""
    conditions = []
    params = []
    param_idx = 1

    if not include_past:
        conditions.append(f"date >= ${param_idx}")
        params.append(date.today().isoformat())
        param_idx += 1

    if category_id:
        conditions.append(f"category_id = ${param_idx}")
        params.append(category_id)
        param_idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM events {where} ORDER BY date ASC"
    return await conn.fetch(query, *params)


def _row_to_event(row: dict[str, Any], user_id: Optional[str] = None) -> EventResponse:
    """Convert a database row dict to an EventResponse model."""
    return EventResponse(
        id=str(row.get("id", "")),
        title=row.get("title", ""),
        kind=row.get("kind", ""),
        category_id=row.get("category_id"),
        date=str(row.get("date", "")),
        time=row.get("time"),
        end_date=str(row["end_date"]) if row.get("end_date") else None,
        location=row.get("location"),
        online_url=row.get("online_url"),
        description=row.get("description", ""),
        format=row.get("format", "in_person"),
        is_public=row.get("is_public", True),
        latitude=row.get("latitude"),
        longitude=row.get("longitude"),
        created_by=row.get("created_by"),
        source=row.get("source", "user"),
        attendee_count=row.get("attendee_count", 0),
        user_rsvp_status=row.get("user_rsvp_status"),
        created_at=str(row["created_at"]) if row.get("created_at") else None,
    )
