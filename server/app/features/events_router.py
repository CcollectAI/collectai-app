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
import math
from datetime import date, datetime, timezone
from typing import Any, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user_id, get_optional_user_id
from app.errors import error_response
from app.features.pagination import pagination_params

router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger(__name__)

ALLOWED_EVENT_KINDS = {"collection_drop", "meetup", "stream", "convention", "release"}
ALLOWED_EVENT_FORMATS = {"in_person", "online", "hybrid"}
ALLOWED_EVENT_STATUSES = {"draft", "published", "cancelled"}

# Explicit whitelist of columns that can be updated via PATCH /{event_id}
_UPDATABLE_EVENT_COLUMNS = {"title", "status", "description", "location", "online_url", "image_url", "date", "time", "end_date", "format", "is_public", "max_attendees"}


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


# get_optional_user_id imported from app.auth — returns None instead of 401


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
    image_url: Optional[str] = Field(None, max_length=2048)
    description: str = Field(default="", max_length=5000)
    format: str = Field(default="in_person", pattern=r"^(in_person|online|hybrid)$")
    status: str = Field(default="published", pattern=r"^(draft|published|cancelled)$")
    is_public: bool = True
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class UpdateEventRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = Field(None, pattern=r"^(draft|published|cancelled)$")
    description: Optional[str] = Field(None, max_length=5000)
    location: Optional[str] = Field(None, max_length=500)
    online_url: Optional[str] = Field(None, max_length=2048)
    image_url: Optional[str] = Field(None, max_length=2048)
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: Optional[str] = Field(None, max_length=10)
    end_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    format: Optional[str] = Field(None, pattern=r"^(in_person|online|hybrid)$")
    is_public: Optional[bool] = None
    max_attendees: Optional[int] = Field(None, ge=1)


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
    image_url: Optional[str] = None
    description: str = ""
    format: str = "in_person"
    status: str = "published"
    is_public: bool = True
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_by: Optional[str] = None
    source: str = "user"
    attendee_count: int = 0
    going_count: int = 0
    interested_count: int = 0
    max_attendees: Optional[int] = None
    is_full: bool = False
    user_rsvp_status: Optional[str] = None
    created_at: Optional[str] = None
    # Sponsor fields
    is_sponsored: bool = False
    sponsor_name: Optional[str] = None
    sponsor_logo_url: Optional[str] = None
    sponsor_tier: Optional[str] = None
    sponsor_company_id: Optional[str] = None


class CreateTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    from_event_id: Optional[str] = None
    template_data: Optional[dict] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    template_data: dict
    use_count: int = 0
    created_at: Optional[str] = None


class AnnouncementRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    body: str = Field(..., min_length=1, max_length=2000)
    image_url: Optional[str] = Field(None, max_length=2048)


class AnnouncementResponse(BaseModel):
    id: str
    event_id: str
    author_user_id: str
    title: Optional[str] = None
    body: str
    image_url: Optional[str] = None
    is_read: bool = False
    created_at: Optional[str] = None


class EventListResponse(BaseModel):
    events: List[EventResponse]


# ---------------------------------------------------------------------------
# In-memory fallback stores (used when DB is disabled)
# ---------------------------------------------------------------------------

_IN_MEMORY_EVENTS: dict[str, dict[str, Any]] = {}
_IN_MEMORY_RSVPS: dict[str, dict[str, str]] = {}  # event_id -> {user_id: status}
_IN_MEMORY_FOLLOWS: dict[str, set[str]] = {}  # user_id -> set of category_ids
_MAX_IN_MEMORY_EVENTS = 1000  # eviction cap to prevent unbounded memory growth
_MAX_IN_MEMORY_FOLLOWS = 500


# ---------------------------------------------------------------------------
# Endpoints — Events
# ---------------------------------------------------------------------------

@router.get("", response_model=EventListResponse)
async def list_events(
    category_id: Optional[str] = Query(None, description="Filter by category"),
    include_past: bool = Query(False, description="Include past events"),
    user_id: Optional[str] = Depends(get_optional_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """
    List events, optionally filtered by category.

    If the user is authenticated and the DB is available, calls
    rpc_list_personalized_events_v1 for personalized ordering.
    Otherwise returns all future events.
    """
    limit, offset = pagination
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                if user_id:
                    # Try the personalized RPC first
                    try:
                        rows = await conn.fetch(
                            "SELECT * FROM rpc_list_personalized_events_v1($1, $2, $3) LIMIT $4 OFFSET $5",
                            user_id,
                            category_id,
                            include_past,
                            limit,
                            offset,
                        )
                    except Exception as rpc_err:
                        logger.warning("[events] Personalized RPC failed, falling back: %s", rpc_err)
                        rows = await _fetch_events_basic(conn, category_id, include_past, limit, offset)
                else:
                    rows = await _fetch_events_basic(conn, category_id, include_past, limit, offset)

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
            raise error_response(500, "Failed to list events", code="EVENT_LIST_ERROR")

    # Offline / in-memory fallback
    today_str = date.today().isoformat()
    events = []
    for ev in _IN_MEMORY_EVENTS.values():
        if not include_past and ev.get("date", "") < today_str:
            continue
        if category_id and ev.get("category_id") != category_id:
            continue
        # Only show published events (unless creator sees their own drafts)
        ev_status = ev.get("status", "published")
        if ev_status != "published" and ev.get("created_by") != user_id:
            continue
        # Hide non-public events unless the user is the creator
        if not ev.get("is_public", True) and ev.get("created_by") != user_id:
            continue
        rsvps = _IN_MEMORY_RSVPS.get(ev["id"], {})
        ev_copy = {**ev, "attendee_count": len(rsvps)}
        if user_id:
            ev_copy["user_rsvp_status"] = rsvps.get(user_id)
        events.append(EventResponse(**ev_copy))
    # Sort: sponsored first, then by date
    events.sort(key=lambda e: (not e.is_sponsored, e.date))
    return EventListResponse(events=events[offset:offset + limit])


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(
    request: CreateEventRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new community event."""
    if request.kind not in ALLOWED_EVENT_KINDS:
        raise error_response(
            400,
            f"Invalid event kind: {request.kind}. "
            f"Allowed: {', '.join(sorted(ALLOWED_EVENT_KINDS))}",
            code="INVALID_EVENT_KIND",
        )

    if request.format not in ALLOWED_EVENT_FORMATS:
        raise error_response(
            400,
            f"Invalid event format: {request.format}. "
            f"Allowed: {', '.join(sorted(ALLOWED_EVENT_FORMATS))}",
            code="INVALID_EVENT_FORMAT",
        )

    # Validate date format
    try:
        datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        raise error_response(400, "Invalid date format. Use YYYY-MM-DD.", code="INVALID_DATE")

    if request.end_date:
        try:
            datetime.strptime(request.end_date, "%Y-%m-%d")
        except ValueError:
            raise error_response(400, "Invalid end_date format. Use YYYY-MM-DD.", code="INVALID_DATE")

    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO events (
                        title, kind, category_id, date, time, end_date,
                        location, online_url, image_url, description, created_by, source,
                        format, status, is_public, latitude, longitude
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'user',
                            $12, $13, $14, $15, $16)
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
                    request.image_url,
                    request.description,
                    user_id,
                    request.format,
                    request.status,
                    request.is_public,
                    request.latitude,
                    request.longitude,
                )
                return _row_to_event(dict(row), user_id=user_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error creating event: %s", e)
            raise error_response(500, "Failed to create event", code="EVENT_CREATE_ERROR")

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
        "image_url": request.image_url,
        "description": request.description,
        "format": request.format,
        "status": request.status,
        "is_public": request.is_public,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "created_by": user_id,
        "source": "user",
        "attendee_count": 0,
        "created_at": now,
    }
    _IN_MEMORY_EVENTS[event_id] = event_data
    # Evict oldest entries if over capacity
    while len(_IN_MEMORY_EVENTS) > _MAX_IN_MEMORY_EVENTS:
        _IN_MEMORY_EVENTS.pop(next(iter(_IN_MEMORY_EVENTS)))
    logger.info("[events] Created event (in-memory): id=%s, title=%s", event_id, request.title)
    return EventResponse(**event_data)


@router.get("/nearby", response_model=EventListResponse)
async def list_nearby_events(
    lat: float = Query(..., ge=-90, le=90, description="User latitude"),
    lon: float = Query(..., ge=-180, le=180, description="User longitude"),
    radius_km: float = Query(default=50, ge=1, le=500, description="Search radius in km"),
    user_id: Optional[str] = Depends(get_optional_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """List upcoming published events within a radius of the given coordinates.

    Uses the Haversine formula for distance calculation.
    """
    limit, offset = pagination
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT *,
                        (6371 * acos(LEAST(1.0, GREATEST(-1.0,
                            cos(radians($1)) * cos(radians(latitude))
                            * cos(radians(longitude) - radians($2))
                            + sin(radians($1)) * sin(radians(latitude))
                        )))) AS distance_km
                    FROM events
                    WHERE latitude IS NOT NULL
                      AND longitude IS NOT NULL
                      AND status = 'published'
                      AND is_public = true
                      AND date >= CURRENT_DATE
                      AND (6371 * acos(LEAST(1.0, GREATEST(-1.0,
                            cos(radians($1)) * cos(radians(latitude))
                            * cos(radians(longitude) - radians($2))
                            + sin(radians($1)) * sin(radians(latitude))
                        )))) <= $3
                    ORDER BY distance_km ASC
                    LIMIT $4 OFFSET $5
                    """,
                    lat, lon, radius_km, limit, offset,
                )
                events = [_row_to_event(dict(r), user_id=user_id) for r in rows]
                return EventListResponse(events=events)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error listing nearby events: %s", e)
            raise error_response(500, "Failed to list nearby events", code="EVENT_NEARBY_ERROR")

    # Offline / in-memory fallback with Haversine
    today_str = date.today().isoformat()
    events_with_dist = []
    for ev in _IN_MEMORY_EVENTS.values():
        ev_lat = ev.get("latitude")
        ev_lon = ev.get("longitude")
        if ev_lat is None or ev_lon is None:
            continue
        if ev.get("date", "") < today_str:
            continue
        if ev.get("status", "published") != "published":
            continue
        if not ev.get("is_public", True):
            continue
        dist = _haversine(lat, lon, ev_lat, ev_lon)
        if dist <= radius_km:
            events_with_dist.append((dist, ev))

    events_with_dist.sort(key=lambda x: x[0])
    events = [
        EventResponse(**{**ev, "attendee_count": len(_IN_MEMORY_RSVPS.get(ev["id"], {}))})
        for _, ev in events_with_dist[offset:offset + limit]
    ]
    return EventListResponse(events=events)


# ---------------------------------------------------------------------------
# Endpoints — Category follows
# NOTE: These MUST be registered before /{event_id} to avoid route shadowing.
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
            raise error_response(500, "Failed to list followed categories", code="FOLLOW_LIST_ERROR")

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
            raise error_response(500, "Failed to follow category", code="FOLLOW_ERROR")

    # Offline / in-memory fallback
    _IN_MEMORY_FOLLOWS.setdefault(user_id, set()).add(category_id)
    # Evict oldest user entries if over capacity
    while len(_IN_MEMORY_FOLLOWS) > _MAX_IN_MEMORY_FOLLOWS:
        _IN_MEMORY_FOLLOWS.pop(next(iter(_IN_MEMORY_FOLLOWS)))
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
            raise error_response(500, "Failed to unfollow category", code="FOLLOW_ERROR")

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
            raise error_response(500, "Failed to check follow status", code="FOLLOW_CHECK_ERROR")

    # Offline / in-memory fallback
    follows = _IN_MEMORY_FOLLOWS.get(user_id, set())
    return {"following": category_id in follows}


# ---------------------------------------------------------------------------
# Endpoints — Templates (MUST be registered before /{event_id})
# ---------------------------------------------------------------------------

_TEMPLATE_FIELDS = {"title", "kind", "category_id", "format", "location", "online_url",
                    "description", "time", "image_url", "is_public", "max_attendees"}


@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(
    user_id: str = Depends(get_current_user_id),
):
    """List the current user's event templates, ordered by use_count DESC."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM event_templates WHERE user_id = $1 ORDER BY use_count DESC, created_at DESC",
                    user_id,
                )
                return [
                    TemplateResponse(
                        id=str(r["id"]),
                        name=r["name"],
                        template_data=r["template_data"] if isinstance(r["template_data"], dict) else {},
                        use_count=r.get("use_count", 0),
                        created_at=str(r["created_at"]) if r.get("created_at") else None,
                    )
                    for r in rows
                ]

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error listing templates: %s", e)
            raise error_response(500, "Failed to list templates", code="TEMPLATE_LIST_ERROR")

    return []


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    request: CreateTemplateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create an event template from explicit data or by copying from an existing event."""
    pool = _get_db_pool()

    template_data = request.template_data or {}

    if request.from_event_id and pool is not None:
        try:
            async with pool.acquire() as conn:
                ev_row = await conn.fetchrow(
                    "SELECT * FROM events WHERE id = $1 AND created_by = $2",
                    request.from_event_id, user_id,
                )
                if not ev_row:
                    raise error_response(404, "Event not found or not owned by you", code="EVENT_NOT_FOUND")
                ev = dict(ev_row)
                template_data = {k: ev[k] for k in _TEMPLATE_FIELDS if ev.get(k) is not None}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error copying event for template: %s", e)
            raise error_response(500, "Failed to create template", code="TEMPLATE_CREATE_ERROR")

    if pool is not None:
        try:
            import json
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO event_templates (user_id, name, template_data)
                    VALUES ($1, $2, $3::jsonb)
                    RETURNING *
                    """,
                    user_id,
                    request.name,
                    json.dumps(template_data),
                )
                return TemplateResponse(
                    id=str(row["id"]),
                    name=row["name"],
                    template_data=row["template_data"] if isinstance(row["template_data"], dict) else {},
                    use_count=row.get("use_count", 0),
                    created_at=str(row["created_at"]) if row.get("created_at") else None,
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error creating template: %s", e)
            raise error_response(500, "Failed to create template", code="TEMPLATE_CREATE_ERROR")

    raise error_response(503, "Database not available", code="DB_UNAVAILABLE")


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete an event template (owner only)."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM event_templates WHERE id = $1 AND user_id = $2",
                    template_id, user_id,
                )
                if result.endswith(" 0"):
                    raise error_response(404, "Template not found", code="TEMPLATE_NOT_FOUND")
                return {"success": True, "message": "Template deleted"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error deleting template: %s", e)
            raise error_response(500, "Failed to delete template", code="TEMPLATE_DELETE_ERROR")

    raise error_response(503, "Database not available", code="DB_UNAVAILABLE")


# ---------------------------------------------------------------------------
# Endpoints — Unread announcement count (MUST be before /{event_id})
# ---------------------------------------------------------------------------

@router.get("/my-announcements/unread-count")
async def get_unread_announcement_count(
    user_id: str = Depends(get_current_user_id),
):
    """Get total unread announcement count across all events the user attends."""
    pool = _get_db_pool()

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
            raise error_response(500, "Failed to get unread count", code="ANNOUNCEMENT_COUNT_ERROR")

    return {"unread_count": 0}


# ---------------------------------------------------------------------------
# Endpoints — Single event + RSVP (parameterized routes last)
# ---------------------------------------------------------------------------

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
                    raise error_response(404, "Event not found", code="EVENT_NOT_FOUND")

                event = _row_to_event(dict(row), user_id=user_id)

                # Hide non-public events unless the user is the creator
                if not event.is_public and event.created_by != user_id:
                    raise error_response(404, "Event not found", code="EVENT_NOT_FOUND")

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
            raise error_response(500, "Failed to fetch event", code="EVENT_FETCH_ERROR")

    # Offline / in-memory fallback
    ev = _IN_MEMORY_EVENTS.get(event_id)
    if ev is None:
        raise error_response(404, "Event not found", code="EVENT_NOT_FOUND")

    # Hide non-public events unless the user is the creator
    if not ev.get("is_public", True) and ev.get("created_by") != user_id:
        raise error_response(404, "Event not found", code="EVENT_NOT_FOUND")

    rsvps = _IN_MEMORY_RSVPS.get(event_id, {})
    ev_copy = {**ev, "attendee_count": len(rsvps)}
    if user_id:
        ev_copy["user_rsvp_status"] = rsvps.get(user_id)
    return EventResponse(**ev_copy)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    request: UpdateEventRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Update an event (title, status, description, location, online_url). Creator only."""
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise error_response(400, "No fields to update", code="NO_FIELDS")

    # Validate against column whitelist to prevent injection via future model changes
    bad_keys = set(updates.keys()) - _UPDATABLE_EVENT_COLUMNS
    if bad_keys:
        raise error_response(400, f"Cannot update fields: {', '.join(sorted(bad_keys))}", code="INVALID_FIELDS")

    if request.status and request.status not in ALLOWED_EVENT_STATUSES:
        raise error_response(400, f"Invalid status: {request.status}", code="INVALID_STATUS")

    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Verify ownership
                row = await conn.fetchrow(
                    "SELECT * FROM events WHERE id = $1 AND created_by = $2",
                    event_id, user_id,
                )
                if not row:
                    raise error_response(404, "Event not found or not owned by you", code="EVENT_NOT_FOUND")

                set_parts = []
                params = [event_id, user_id]
                idx = 3
                for key, val in updates.items():
                    set_parts.append(f"{key} = ${idx}")
                    params.append(val)
                    idx += 1
                set_parts.append(f"updated_at = ${idx}")
                params.append(datetime.now(timezone.utc))

                query = f"""
                    UPDATE events SET {', '.join(set_parts)}
                    WHERE id = $1 AND created_by = $2
                    RETURNING *
                """
                updated = await conn.fetchrow(query, *params)
                if not updated:
                    raise error_response(404, "Event not found or not owned by you", code="EVENT_NOT_FOUND")
                return _row_to_event(dict(updated), user_id=user_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error updating event %s: %s", event_id, e)
            raise error_response(500, "Failed to update event", code="EVENT_UPDATE_ERROR")

    # Offline / in-memory fallback
    ev = _IN_MEMORY_EVENTS.get(event_id)
    if ev is None or ev.get("created_by") != user_id:
        raise error_response(404, "Event not found or not owned by you", code="EVENT_NOT_FOUND")

    ev.update(updates)
    return EventResponse(**ev)


@router.delete("/{event_id}")
async def delete_event(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Soft-delete an event by setting status to 'cancelled'. Creator only."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE events SET status = 'cancelled', updated_at = $3
                    WHERE id = $1 AND created_by = $2
                    """,
                    event_id, user_id, datetime.now(timezone.utc),
                )
                if result.endswith(" 0"):
                    raise error_response(404, "Event not found or not owned by you", code="EVENT_NOT_FOUND")
                logger.info("[events] Soft-deleted event: id=%s, user=%s", event_id, user_id)
                return {"success": True, "message": "Event cancelled"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error deleting event %s: %s", event_id, e)
            raise error_response(500, "Failed to delete event", code="EVENT_DELETE_ERROR")

    # Offline / in-memory fallback
    ev = _IN_MEMORY_EVENTS.get(event_id)
    if ev is None or ev.get("created_by") != user_id:
        raise error_response(404, "Event not found or not owned by you", code="EVENT_NOT_FOUND")
    ev["status"] = "cancelled"
    logger.info("[events] Soft-deleted event (in-memory): id=%s", event_id)
    return {"success": True, "message": "Event cancelled"}


# ---------------------------------------------------------------------------
# Endpoints — RSVP
# ---------------------------------------------------------------------------

@router.post("/{event_id}/rsvp")
async def rsvp_event(
    event_id: str,
    request: RsvpRequest,
    user_id: str = Depends(get_current_user_id),
):
    """RSVP to an event (going, interested, not_going). Auto-waitlists if event is full."""
    if request.status not in {"going", "interested", "not_going"}:
        raise error_response(
            400,
            "Invalid RSVP status. Must be one of: going, interested, not_going",
            code="INVALID_RSVP_STATUS",
        )

    pool = _get_db_pool()
    actual_status = request.status
    waitlisted = False

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Check capacity if trying to go
                if request.status == "going":
                    cap_row = await conn.fetchrow(
                        """
                        SELECT e.max_attendees,
                               COUNT(*) FILTER (WHERE ea.status = 'going') AS going_count
                        FROM events e
                        LEFT JOIN event_attendees ea ON ea.event_id = e.id
                            AND ea.user_id != $2
                        WHERE e.id = $1
                        GROUP BY e.max_attendees
                        """,
                        event_id, user_id,
                    )
                    if cap_row and cap_row["max_attendees"] is not None:
                        if cap_row["going_count"] >= cap_row["max_attendees"]:
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
                return {"success": True, "status": actual_status, "waitlisted": waitlisted}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error RSVP event %s: %s", event_id, e)
            raise error_response(500, "Failed to RSVP", code="RSVP_ERROR")

    # Offline / in-memory fallback
    _IN_MEMORY_RSVPS.setdefault(event_id, {})[user_id] = actual_status
    logger.info("[events] RSVP (in-memory): user=%s, event=%s, status=%s", user_id, event_id, actual_status)
    return {"success": True, "status": actual_status, "waitlisted": waitlisted}


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
            raise error_response(500, "Failed to remove RSVP", code="RSVP_ERROR")

    # Offline / in-memory fallback
    rsvps = _IN_MEMORY_RSVPS.get(event_id, {})
    rsvps.pop(user_id, None)
    logger.info("[events] Un-RSVP (in-memory): user=%s, event=%s", user_id, event_id)
    return {"success": True, "message": "RSVP removed"}


# ---------------------------------------------------------------------------
# Endpoints — Duplicate
# ---------------------------------------------------------------------------

@router.post("/{event_id}/duplicate", response_model=EventResponse, status_code=201)
async def duplicate_event(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Duplicate an event (creator only). Copies all fields except date, attendees, status."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM events WHERE id = $1 AND created_by = $2",
                    event_id, user_id,
                )
                if not row:
                    raise error_response(404, "Event not found or not owned by you", code="EVENT_NOT_FOUND")

                new_row = await conn.fetchrow(
                    """
                    INSERT INTO events (
                        title, kind, category_id, location, online_url, description,
                        image_url, format, status, is_public, latitude, longitude,
                        date, source, created_by, max_attendees
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, 'draft', $9, $10, $11,
                        CURRENT_DATE, 'user', $12, $13
                    )
                    RETURNING *
                    """,
                    row["title"],
                    row["kind"],
                    row["category_id"],
                    row["location"],
                    row["online_url"],
                    row["description"],
                    row["image_url"],
                    row["format"],
                    row.get("is_public", True),
                    row.get("latitude"),
                    row.get("longitude"),
                    user_id,
                    row.get("max_attendees"),
                )
                return _row_to_event(dict(new_row), user_id=user_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error duplicating event %s: %s", event_id, e)
            raise error_response(500, "Failed to duplicate event", code="EVENT_DUPLICATE_ERROR")

    # Offline / in-memory fallback
    ev = _IN_MEMORY_EVENTS.get(event_id)
    if ev is None or ev.get("created_by") != user_id:
        raise error_response(404, "Event not found or not owned by you", code="EVENT_NOT_FOUND")

    new_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    dup = {**ev, "id": new_id, "status": "draft", "date": date.today().isoformat(),
           "attendee_count": 0, "created_at": now}
    _IN_MEMORY_EVENTS[new_id] = dup
    return EventResponse(**dup)


@router.post("/{event_id}/announcements", response_model=AnnouncementResponse, status_code=201)
async def post_announcement(
    event_id: str,
    request: AnnouncementRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Post an announcement to event attendees (host or sponsor admin only)."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Verify caller is event creator or sponsor company admin
                auth_row = await conn.fetchrow(
                    """
                    SELECT 1 FROM events e WHERE e.id = $1 AND e.created_by = $2
                    UNION ALL
                    SELECT 1 FROM events e
                    JOIN sponsor_companies sc ON sc.id = e.sponsor_company_id
                    WHERE e.id = $1 AND sc.admin_user_id = $2
                    """,
                    event_id, user_id,
                )
                if not auth_row:
                    raise error_response(403, "Only event host or sponsor admin can post announcements", code="FORBIDDEN")

                row = await conn.fetchrow(
                    """
                    INSERT INTO event_announcements (event_id, author_user_id, title, body, image_url)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING *
                    """,
                    event_id, user_id, request.title, request.body, request.image_url,
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
            raise error_response(500, "Failed to post announcement", code="ANNOUNCEMENT_ERROR")

    raise error_response(503, "Database not available", code="DB_UNAVAILABLE")


@router.get("/{event_id}/announcements", response_model=List[AnnouncementResponse])
async def list_announcements(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """List announcements for an event (attendees only). Includes is_read status."""
    limit, offset = pagination
    pool = _get_db_pool()

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
                    raise error_response(403, "Only attendees can view announcements", code="FORBIDDEN")

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
            raise error_response(500, "Failed to list announcements", code="ANNOUNCEMENT_ERROR")

    return []


@router.post("/{event_id}/announcements/{announcement_id}/read")
async def mark_announcement_read(
    event_id: str,
    announcement_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Mark a single announcement as read."""
    pool = _get_db_pool()

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
            raise error_response(500, "Failed to mark announcement read", code="ANNOUNCEMENT_READ_ERROR")

    return {"success": True}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch_events_basic(conn, category_id: Optional[str], include_past: bool, limit: int = 50, offset: int = 0):
    """Fetch events from the events table with optional filters."""
    conditions = ["status = 'published'"]
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

    where = f"WHERE {' AND '.join(conditions)}"
    query = (
        f"SELECT * FROM events {where} "
        f"ORDER BY (is_sponsored AND (sponsor_expires_at IS NULL OR sponsor_expires_at > now())) DESC, "
        f"date ASC "
        f"LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    )
    params.append(limit)
    params.append(offset)
    return await conn.fetch(query, *params)


def _row_to_event(row: dict[str, Any], user_id: Optional[str] = None) -> EventResponse:
    """Convert a database row dict to an EventResponse model."""
    # Filter out expired sponsors
    is_sponsored = bool(row.get("is_sponsored", False))
    sponsor_expires = row.get("sponsor_expires_at")
    if is_sponsored and sponsor_expires is not None:
        from datetime import datetime as _dt, timezone as _tz
        try:
            exp = sponsor_expires if isinstance(sponsor_expires, _dt) else _dt.fromisoformat(str(sponsor_expires))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=_tz.utc)
            if exp < _dt.now(_tz.utc):
                is_sponsored = False
        except (ValueError, TypeError):
            pass

    going_count = row.get("going_count", 0) or 0
    interested_count = row.get("interested_count", 0) or 0
    max_attendees = row.get("max_attendees")
    is_full = bool(max_attendees and going_count >= max_attendees)

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
        image_url=row.get("image_url"),
        description=row.get("description", ""),
        format=row.get("format", "in_person"),
        status=row.get("status", "published"),
        is_public=row.get("is_public", True),
        latitude=row.get("latitude"),
        longitude=row.get("longitude"),
        created_by=row.get("created_by"),
        source=row.get("source", "user"),
        attendee_count=row.get("attendee_count", 0),
        going_count=going_count,
        interested_count=interested_count,
        max_attendees=max_attendees,
        is_full=is_full,
        user_rsvp_status=row.get("user_rsvp_status"),
        created_at=str(row["created_at"]) if row.get("created_at") else None,
        is_sponsored=is_sponsored,
        sponsor_name=row.get("sponsor_name") if is_sponsored else None,
        sponsor_logo_url=row.get("sponsor_logo_url") if is_sponsored else None,
        sponsor_tier=row.get("sponsor_tier") if is_sponsored else None,
        sponsor_company_id=str(row["sponsor_company_id"]) if row.get("sponsor_company_id") else None,
    )


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points on Earth in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
