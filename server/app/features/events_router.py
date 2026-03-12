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

import asyncio
import logging
import math
import time as _time
from datetime import date, datetime, timezone
from typing import Any, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user_id, get_optional_user_id
from app.cache import cache_get, cache_set
from app.errors import error_response
from app.features.pagination import pagination_params
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode
from app.config import STRIPE_SECRET_KEY
from app.rate_limit import per_user_rate_limit

try:
    import stripe
except ImportError:
    stripe = None  # type: ignore[assignment]

router = APIRouter(prefix="/events", tags=["Events"])
logger = logging.getLogger(__name__)

# Per-user: 30 event search requests per minute (expensive DB queries)
# Applied to auth-required search-like endpoints. For optional-auth listing
# endpoints (search_events, list_nearby_events, list_events), the global
# IP-based middleware rate limit provides protection.
_event_search_limit = per_user_rate_limit(30, window_seconds=60, scope="event_search")
# Per-user: 10 RSVP actions per minute (prevent toggle spam)
_event_rsvp_limit = per_user_rate_limit(10, window_seconds=60, scope="event_rsvp")
# Per-user: 5 announcements per hour (sends DMs to all attendees)
_event_announce_limit = per_user_rate_limit(5, window_seconds=3600, scope="event_announce")

_EVENTS_CACHE_TTL = 300  # 5 minutes

ALLOWED_EVENT_KINDS = {"collection_drop", "meetup", "stream", "convention", "release"}
ALLOWED_EVENT_FORMATS = {"in_person", "online", "hybrid"}
ALLOWED_EVENT_STATUSES = {"draft", "published", "cancelled"}

# Explicit whitelist of columns that can be updated via PATCH /{event_id}
_UPDATABLE_EVENT_COLUMNS = {"title", "status", "description", "location", "online_url", "image_url", "date", "time", "end_date", "format", "is_public", "max_attendees"}


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
    ticket_price_cents: Optional[int] = Field(None, ge=0, description="Ticket price in cents (0 = free)")


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
    ticket_price_cents: int = 0
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
    total: int = 0


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


@router.get("/search", response_model=EventListResponse, summary="Search events")
async def search_events(
    q: str = "",
    category: Optional[str] = None,
    event_type: Optional[str] = None,
    location: Optional[str] = None,
    upcoming_only: bool = True,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Search events by name, category, type, or location."""
    pool = get_db_pool()
    if not pool:
        return EventListResponse(events=[], total=0)

    try:
        async with pool.acquire() as conn:
            conditions = []
            params: list[Any] = []
            idx = 1

            if q.strip():
                conditions.append(f"(title ILIKE ${idx} OR description ILIKE ${idx})")
                params.append(f"%{q.strip()}%")
                idx += 1

            if category:
                conditions.append(f"category_id = ${idx}")
                params.append(category)
                idx += 1

            if event_type:
                conditions.append(f"kind = ${idx}")
                params.append(event_type)
                idx += 1

            if location:
                conditions.append(f"location ILIKE ${idx}")
                params.append(f"%{location}%")
                idx += 1

            if upcoming_only:
                conditions.append("status != 'cancelled'")
                conditions.append(f"date >= ${idx}")
                params.append(date.today())
                idx += 1

            where = " AND ".join(conditions) if conditions else "TRUE"

            # Count total matching rows (without LIMIT/OFFSET)
            count_query = f"SELECT count(*) FROM events WHERE {where}"
            total_count = await conn.fetchval(count_query, *params)

            query_str = f"""
                SELECT id, title, description, kind, category_id,
                       date, time, end_date, location, online_url, image_url,
                       created_by, status, format, is_public, max_attendees,
                       created_at,
                       (SELECT COUNT(*) FROM event_attendees ea WHERE ea.event_id = e.id AND ea.status = 'going') AS going_count,
                       (SELECT COUNT(*) FROM event_attendees ea WHERE ea.event_id = e.id AND ea.status = 'interested') AS interested_count
                FROM events e
                WHERE {where}
                ORDER BY date ASC
                LIMIT ${idx} OFFSET ${idx + 1}
            """
            params.extend([limit, offset])

            rows = await conn.fetch(query_str, *params)
            events = [_row_to_event(dict(r)) for r in rows] if rows else []
            return EventListResponse(events=events, total=total_count or 0)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise e
        logger.warning("search_events error: %s", e)
        raise error_response(500, "Event search failed", code=ErrorCode.INTERNAL_ERROR)


@router.get("", response_model=EventListResponse, summary="List personalized events")
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

    # Check cache
    uid = user_id or "anon"
    cache_key = f"events:list:{uid}:{category_id}:{include_past}:{limit}:{offset}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Get total count for pagination
                total_count = await _count_events_basic(conn, category_id, include_past, user_id=user_id)

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
                result = EventListResponse(events=events, total=total_count)
                cache_set(cache_key, result, ttl=_EVENTS_CACHE_TTL)
                return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error listing events: %s", e)
            raise error_response(500, "Failed to list events", code=ErrorCode.INTERNAL_ERROR)

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
    total_count = len(events)
    result = EventListResponse(events=events[offset:offset + limit], total=total_count)
    cache_set(cache_key, result, ttl=_EVENTS_CACHE_TTL)
    return result


@router.post("", response_model=EventResponse, status_code=201, summary="Create an event")
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
            code=ErrorCode.VALIDATION_ERROR,
        )

    if request.format not in ALLOWED_EVENT_FORMATS:
        raise error_response(
            400,
            f"Invalid event format: {request.format}. "
            f"Allowed: {', '.join(sorted(ALLOWED_EVENT_FORMATS))}",
            code=ErrorCode.VALIDATION_ERROR,
        )

    # Validate date format
    try:
        datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        raise error_response(400, "Invalid date format. Use YYYY-MM-DD.", code=ErrorCode.VALIDATION_ERROR)

    if request.end_date:
        try:
            datetime.strptime(request.end_date, "%Y-%m-%d")
        except ValueError:
            raise error_response(400, "Invalid end_date format. Use YYYY-MM-DD.", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO events (
                        title, kind, category_id, date, time, end_date,
                        location, online_url, image_url, description, created_by, source,
                        format, status, is_public, latitude, longitude, ticket_price_cents
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'user',
                            $12, $13, $14, $15, $16, $17)
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
                    request.ticket_price_cents or 0,
                )
                return _row_to_event(dict(row), user_id=user_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error creating event: %s", e)
            raise error_response(500, "Failed to create event", code=ErrorCode.INTERNAL_ERROR)

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
        "ticket_price_cents": request.ticket_price_cents or 0,
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


@router.get("/nearby", response_model=EventListResponse, summary="List nearby events")
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

    # Check cache (round lat/lon to 2 decimals to improve cache hit rate)
    lat_r = round(lat, 2)
    lon_r = round(lon, 2)
    uid = user_id or "anon"
    cache_key = f"events:nearby:{uid}:{lat_r}:{lon_r}:{radius_km}:{limit}:{offset}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Count total matching rows (without LIMIT/OFFSET)
                total_count = await conn.fetchval(
                    """
                    SELECT count(*)
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
                    """,
                    lat, lon, radius_km,
                )

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
                result = EventListResponse(events=events, total=total_count or 0)
                cache_set(cache_key, result, ttl=_EVENTS_CACHE_TTL)
                return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error listing nearby events: %s", e)
            raise error_response(500, "Failed to list nearby events", code=ErrorCode.INTERNAL_ERROR)

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
    total_count = len(events_with_dist)
    events = [
        EventResponse(**{**ev, "attendee_count": len(_IN_MEMORY_RSVPS.get(ev["id"], {}))})
        for _, ev in events_with_dist[offset:offset + limit]
    ]
    result = EventListResponse(events=events, total=total_count)
    cache_set(cache_key, result, ttl=_EVENTS_CACHE_TTL)
    return result


# ---------------------------------------------------------------------------
# Endpoints — Category follows
# NOTE: These MUST be registered before /{event_id} to avoid route shadowing.
# ---------------------------------------------------------------------------

@router.get("/categories/followed", summary="List followed categories")
async def list_followed_categories(
    user_id: str = Depends(get_current_user_id),
):
    """List all category IDs the current user follows."""
    pool = get_db_pool()

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
            raise error_response(500, "Failed to list followed categories", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    follows = _IN_MEMORY_FOLLOWS.get(user_id, set())
    return {"categories": sorted(follows)}


@router.post("/categories/{category_id}/follow", summary="Follow a category")
async def follow_category(
    category_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Follow a category for event notifications."""
    pool = get_db_pool()

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
            raise error_response(500, "Failed to follow category", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    _IN_MEMORY_FOLLOWS.setdefault(user_id, set()).add(category_id)
    # Evict oldest user entries if over capacity
    while len(_IN_MEMORY_FOLLOWS) > _MAX_IN_MEMORY_FOLLOWS:
        _IN_MEMORY_FOLLOWS.pop(next(iter(_IN_MEMORY_FOLLOWS)))
    logger.info("[events] Follow category (in-memory): user=%s, category=%s", user_id, category_id)
    return {"success": True, "category_id": category_id}


@router.delete("/categories/{category_id}/follow", summary="Unfollow a category")
async def unfollow_category(
    category_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Unfollow a category."""
    pool = get_db_pool()

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
            raise error_response(500, "Failed to unfollow category", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    follows = _IN_MEMORY_FOLLOWS.get(user_id, set())
    follows.discard(category_id)
    logger.info("[events] Unfollow category (in-memory): user=%s, category=%s", user_id, category_id)
    return {"success": True, "message": "Category unfollowed"}


@router.get("/categories/{category_id}/following", summary="Check category follow status")
async def check_following_category(
    category_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Check whether the current user follows a given category."""
    pool = get_db_pool()

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
            raise error_response(500, "Failed to check follow status", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    follows = _IN_MEMORY_FOLLOWS.get(user_id, set())
    return {"following": category_id in follows}


# ---------------------------------------------------------------------------
# Endpoints — Drop Alerts (MUST be registered before /{event_id})
# ---------------------------------------------------------------------------

# Per-user: 20 drop alert actions per minute
_drop_alert_limit = per_user_rate_limit(20, window_seconds=60, scope="drop_alert")


class DropAlertRequest(BaseModel):
    notify_before_hours: int = Field(default=24, ge=1, le=168)


class DropAlertResponse(BaseModel):
    user_id: str
    event_id: str
    notify_before_hours: int = 24
    created_at: Optional[str] = None


# In-memory fallback for drop alerts
_IN_MEMORY_DROP_ALERTS: dict[str, dict[str, dict]] = {}  # user_id -> {event_id: {...}}


@router.get("/my-alerts", response_model=List[DropAlertResponse], summary="List my drop alerts")
async def list_my_drop_alerts(
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_drop_alert_limit),
):
    """List all drop alert subscriptions for the current user."""
    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT user_id, event_id, notify_before_hours, created_at
                    FROM user_drop_alerts
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    """,
                    user_id,
                )
                return [
                    DropAlertResponse(
                        user_id=str(r["user_id"]),
                        event_id=str(r["event_id"]),
                        notify_before_hours=r["notify_before_hours"],
                        created_at=str(r["created_at"]) if r.get("created_at") else None,
                    )
                    for r in rows
                ]

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error listing drop alerts: %s", e)
            raise error_response(500, "Failed to list drop alerts", code=ErrorCode.INTERNAL_ERROR)

    # In-memory fallback
    alerts = _IN_MEMORY_DROP_ALERTS.get(user_id, {})
    return [
        DropAlertResponse(
            user_id=user_id,
            event_id=eid,
            notify_before_hours=data.get("notify_before_hours", 24),
            created_at=data.get("created_at"),
        )
        for eid, data in alerts.items()
    ]


@router.post("/{event_id}/alert", response_model=DropAlertResponse, status_code=201, summary="Subscribe to drop alert")
async def subscribe_drop_alert(
    event_id: str,
    request: DropAlertRequest = DropAlertRequest(),
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_drop_alert_limit),
):
    """Subscribe to a drop alert for an event."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Verify event exists
                ev_row = await conn.fetchrow("SELECT id FROM events WHERE id = $1", event_id)
                if not ev_row:
                    raise error_response(404, "Event not found", code=ErrorCode.NOT_FOUND)

                row = await conn.fetchrow(
                    """
                    INSERT INTO user_drop_alerts (user_id, event_id, notify_before_hours)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, event_id)
                    DO UPDATE SET notify_before_hours = $3
                    RETURNING user_id, event_id, notify_before_hours, created_at
                    """,
                    user_id,
                    event_id,
                    request.notify_before_hours,
                )
                logger.info("[events] Drop alert subscribed: user=%s, event=%s", user_id, event_id)
                return DropAlertResponse(
                    user_id=str(row["user_id"]),
                    event_id=str(row["event_id"]),
                    notify_before_hours=row["notify_before_hours"],
                    created_at=str(row["created_at"]) if row.get("created_at") else None,
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error subscribing drop alert: %s", e)
            raise error_response(500, "Failed to subscribe to drop alert", code=ErrorCode.INTERNAL_ERROR)

    # In-memory fallback
    now = datetime.now(timezone.utc).isoformat()
    _IN_MEMORY_DROP_ALERTS.setdefault(user_id, {})[event_id] = {
        "notify_before_hours": request.notify_before_hours,
        "created_at": now,
    }
    logger.info("[events] Drop alert subscribed (in-memory): user=%s, event=%s", user_id, event_id)
    return DropAlertResponse(
        user_id=user_id,
        event_id=event_id,
        notify_before_hours=request.notify_before_hours,
        created_at=now,
    )


@router.delete("/{event_id}/alert", summary="Unsubscribe from drop alert")
async def unsubscribe_drop_alert(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_drop_alert_limit),
):
    """Unsubscribe from a drop alert for an event."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM user_drop_alerts WHERE user_id = $1 AND event_id = $2",
                    user_id,
                    event_id,
                )
                logger.info("[events] Drop alert unsubscribed: user=%s, event=%s", user_id, event_id)
                return {"success": True, "message": "Drop alert removed"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error unsubscribing drop alert: %s", e)
            raise error_response(500, "Failed to unsubscribe from drop alert", code=ErrorCode.INTERNAL_ERROR)

    # In-memory fallback
    alerts = _IN_MEMORY_DROP_ALERTS.get(user_id, {})
    alerts.pop(event_id, None)
    logger.info("[events] Drop alert unsubscribed (in-memory): user=%s, event=%s", user_id, event_id)
    return {"success": True, "message": "Drop alert removed"}


# ---------------------------------------------------------------------------
# Endpoints — Templates (MUST be registered before /{event_id})
# ---------------------------------------------------------------------------

_TEMPLATE_FIELDS = {"title", "kind", "category_id", "format", "location", "online_url",
                    "description", "time", "image_url", "is_public", "max_attendees"}


@router.get("/templates", response_model=List[TemplateResponse], summary="List event templates")
async def list_templates(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List the current user's event templates, ordered by use_count DESC."""
    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, name, template_data, use_count, created_at FROM event_templates WHERE user_id = $1 ORDER BY use_count DESC, created_at DESC LIMIT $2 OFFSET $3",
                    user_id,
                    limit,
                    offset,
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
            raise error_response(500, "Failed to list templates", code=ErrorCode.INTERNAL_ERROR)

    return []


@router.post("/templates", response_model=TemplateResponse, status_code=201, summary="Create event template")
async def create_template(
    request: CreateTemplateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create an event template from explicit data or by copying from an existing event."""
    pool = get_db_pool()

    template_data = request.template_data or {}

    if request.from_event_id and pool is not None:
        try:
            async with pool.acquire() as conn:
                ev_row = await conn.fetchrow(
                    "SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, attendee_count, going_count, interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM events WHERE id = $1 AND created_by = $2",
                    request.from_event_id, user_id,
                )
                if not ev_row:
                    raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)
                ev = dict(ev_row)
                template_data = {k: ev[k] for k in _TEMPLATE_FIELDS if ev.get(k) is not None}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error copying event for template: %s", e)
            raise error_response(500, "Failed to create template", code=ErrorCode.INTERNAL_ERROR)

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
            raise error_response(500, "Failed to create template", code=ErrorCode.INTERNAL_ERROR)

    raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)


@router.delete("/templates/{template_id}", summary="Delete event template")
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete an event template (owner only)."""
    try:
        UUID(template_id)
    except ValueError:
        raise error_response(400, "Invalid template_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM event_templates WHERE id = $1 AND user_id = $2",
                    template_id, user_id,
                )
                if result.endswith(" 0"):
                    raise error_response(404, "Template not found", code=ErrorCode.NOT_FOUND)
                return {"success": True, "message": "Template deleted"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error deleting template: %s", e)
            raise error_response(500, "Failed to delete template", code=ErrorCode.INTERNAL_ERROR)

    raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)


# ---------------------------------------------------------------------------
# Endpoints — Unread announcement count (MUST be before /{event_id})
# ---------------------------------------------------------------------------

@router.get("/my-announcements/unread-count", summary="Get unread announcement count")
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
# Endpoints — Single event + RSVP (parameterized routes last)
# ---------------------------------------------------------------------------

@router.get("/{event_id}", response_model=EventResponse, summary="Get event detail")
async def get_event(
    event_id: str,
    background_tasks: BackgroundTasks = None,
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Get a single event by ID, including attendee count and user RSVP status."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

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
                        "SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, attendee_count, going_count, interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM events WHERE id = $1",
                        event_id,
                    )

                if row is None:
                    raise error_response(404, "Event not found", code=ErrorCode.NOT_FOUND)

                event = _row_to_event(dict(row), user_id=user_id)

                # Hide non-public events unless the user is the creator
                if not event.is_public and event.created_by != user_id:
                    raise error_response(404, "Event not found", code=ErrorCode.NOT_FOUND)

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

                # Increment sponsor impression (best-effort, non-blocking)
                if event.is_sponsored and background_tasks:
                    background_tasks.add_task(_increment_sponsor_impression, conn, event_id)

                return event

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error fetching event %s: %s", event_id, e)
            raise error_response(500, "Failed to fetch event", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    ev = _IN_MEMORY_EVENTS.get(event_id)
    if ev is None:
        raise error_response(404, "Event not found", code=ErrorCode.NOT_FOUND)

    # Hide non-public events unless the user is the creator
    if not ev.get("is_public", True) and ev.get("created_by") != user_id:
        raise error_response(404, "Event not found", code=ErrorCode.NOT_FOUND)

    rsvps = _IN_MEMORY_RSVPS.get(event_id, {})
    ev_copy = {**ev, "attendee_count": len(rsvps)}
    if user_id:
        ev_copy["user_rsvp_status"] = rsvps.get(user_id)
    return EventResponse(**ev_copy)


@router.patch("/{event_id}", response_model=EventResponse, summary="Update an event")
async def update_event(
    event_id: str,
    request: UpdateEventRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Update an event (title, status, description, location, online_url). Creator only."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise error_response(400, "No fields to update", code=ErrorCode.VALIDATION_ERROR)

    # Validate against column whitelist to prevent injection via future model changes
    bad_keys = set(updates.keys()) - _UPDATABLE_EVENT_COLUMNS
    if bad_keys:
        raise error_response(400, f"Cannot update fields: {', '.join(sorted(bad_keys))}", code=ErrorCode.VALIDATION_ERROR)

    if request.status and request.status not in ALLOWED_EVENT_STATUSES:
        raise error_response(400, f"Invalid status: {request.status}", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Verify ownership
                row = await conn.fetchrow(
                    "SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, attendee_count, going_count, interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM events WHERE id = $1 AND created_by = $2",
                    event_id, user_id,
                )
                if not row:
                    raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)

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
                    raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)
                return _row_to_event(dict(updated), user_id=user_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error updating event %s: %s", event_id, e)
            raise error_response(500, "Failed to update event", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    ev = _IN_MEMORY_EVENTS.get(event_id)
    if ev is None or ev.get("created_by") != user_id:
        raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)

    ev.update(updates)
    return EventResponse(**ev)


@router.delete("/{event_id}", summary="Cancel an event")
async def delete_event(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Soft-delete an event by setting status to 'cancelled'. Creator only."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

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
                    raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)
                logger.info("[events] Soft-deleted event: id=%s, user=%s", event_id, user_id)
                return {"success": True, "message": "Event cancelled"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error deleting event %s: %s", event_id, e)
            raise error_response(500, "Failed to delete event", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    ev = _IN_MEMORY_EVENTS.get(event_id)
    if ev is None or ev.get("created_by") != user_id:
        raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)
    ev["status"] = "cancelled"
    logger.info("[events] Soft-deleted event (in-memory): id=%s", event_id)
    return {"success": True, "message": "Event cancelled"}


# ---------------------------------------------------------------------------
# Endpoints — Ticket Checkout
# ---------------------------------------------------------------------------

@router.post("/{event_id}/ticket-checkout", summary="Create ticket checkout session", description="Creates a Stripe Checkout Session for a paid event ticket with a 5% platform fee.")
async def ticket_checkout(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_event_rsvp_limit),
):
    """Create a Stripe Checkout Session for a paid event ticket (5% platform fee)."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, title, ticket_price_cents, status, max_attendees FROM events WHERE id = $1",
                event_id,
            )
            if not row:
                raise error_response(404, "Event not found", code=ErrorCode.NOT_FOUND)
            if row["status"] != "published":
                raise error_response(400, "Event is not published", code=ErrorCode.VALIDATION_ERROR)

            ticket_price = row.get("ticket_price_cents") or 0
            if ticket_price <= 0:
                raise error_response(400, "This event is free — use RSVP instead", code=ErrorCode.VALIDATION_ERROR)

            # Check user hasn't already RSVPd as going
            existing = await conn.fetchrow(
                "SELECT status FROM event_attendees WHERE event_id = $1 AND user_id = $2",
                event_id, user_id,
            )
            if existing and existing["status"] == "going":
                raise error_response(409, "You are already going to this event", code=ErrorCode.ALREADY_EXISTS)

            # Check capacity
            if row["max_attendees"] is not None:
                going_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM event_attendees WHERE event_id = $1 AND status = 'going'",
                    event_id,
                )
                if going_count >= row["max_attendees"]:
                    raise error_response(409, "Event is full", code=ErrorCode.CONFLICT)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[events] Error checking event for ticket checkout: %s", e)
        raise error_response(500, "Failed to check event", code=ErrorCode.INTERNAL_ERROR)

    if not STRIPE_SECRET_KEY:
        raise error_response(503, "Billing not configured")

    stripe.api_key = STRIPE_SECRET_KEY
    event_title = row["title"] or "Event Ticket"
    fee_amount = int(ticket_price * 0.05)  # 5% platform fee

    try:
        session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": f"Ticket: {event_title}"},
                    "unit_amount": ticket_price,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"collectai://events/{event_id}?checkout=success",
            cancel_url=f"collectai://events/{event_id}?checkout=cancel",
            metadata={
                "type": "event_ticket",
                "event_id": event_id,
                "user_id": user_id,
            },
        )
        return {"url": session.url, "session_id": session.id}

    except Exception as e:
        logger.error("[events] Stripe ticket checkout creation failed: %s", e)
        raise error_response(500, "Failed to create checkout session", code=ErrorCode.EXTERNAL_SERVICE_ERROR)


# ---------------------------------------------------------------------------
# Endpoints — RSVP
# ---------------------------------------------------------------------------

@router.post("/{event_id}/rsvp", summary="RSVP to an event")
async def rsvp_event(
    event_id: str,
    request: RsvpRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_event_rsvp_limit),
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
                        asyncio.ensure_future(_increment_sponsor_rsvp(event_id))

                return {"success": True, "status": actual_status, "waitlisted": waitlisted}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error RSVP event %s: %s", event_id, e)
            raise error_response(500, "Failed to RSVP", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    _IN_MEMORY_RSVPS.setdefault(event_id, {})[user_id] = actual_status
    logger.info("[events] RSVP (in-memory): user=%s, event=%s, status=%s", user_id, event_id, actual_status)
    return {"success": True, "status": actual_status, "waitlisted": waitlisted}


@router.delete("/{event_id}/rsvp", summary="Remove RSVP from event")
async def unrsvp_event(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_event_rsvp_limit),
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
    rsvps = _IN_MEMORY_RSVPS.get(event_id, {})
    rsvps.pop(user_id, None)
    logger.info("[events] Un-RSVP (in-memory): user=%s, event=%s", user_id, event_id)
    return {"success": True, "message": "RSVP removed"}


# ---------------------------------------------------------------------------
# Endpoints — Duplicate
# ---------------------------------------------------------------------------

@router.post("/{event_id}/duplicate", response_model=EventResponse, status_code=201, summary="Duplicate an event")
async def duplicate_event(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_event_search_limit),
):
    """Duplicate an event (creator only). Copies all fields except date, attendees, status."""
    try:
        UUID(event_id)
    except ValueError:
        raise error_response(400, "Invalid event_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, attendee_count, going_count, interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM events WHERE id = $1 AND created_by = $2",
                    event_id, user_id,
                )
                if not row:
                    raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)

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
            raise error_response(500, "Failed to duplicate event", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    ev = _IN_MEMORY_EVENTS.get(event_id)
    if ev is None or ev.get("created_by") != user_id:
        raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)

    new_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    dup = {**ev, "id": new_id, "status": "draft", "date": date.today().isoformat(),
           "attendee_count": 0, "created_at": now}
    _IN_MEMORY_EVENTS[new_id] = dup
    return EventResponse(**dup)


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

                    # Insert the announcement message
                    await conn.execute(
                        """
                        INSERT INTO chat_messages (thread_id, author_user_id, text)
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


@router.post("/{event_id}/announcements", response_model=AnnouncementResponse, status_code=201, summary="Post event announcement")
async def post_announcement(
    event_id: str,
    request: AnnouncementRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_event_announce_limit),
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


@router.get("/{event_id}/announcements", response_model=List[AnnouncementResponse], summary="List event announcements")
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


@router.post("/{event_id}/announcements/{announcement_id}/read", summary="Mark announcement as read")
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


class BatchReadRequest(BaseModel):
    announcement_ids: list[str] = Field(..., max_length=100)


@router.post("/{event_id}/announcements/batch-read", summary="Batch mark announcements read")
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch_events_basic(conn, category_id: Optional[str], include_past: bool, limit: int = 50, offset: int = 0) -> list:
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
        f"SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, attendee_count, going_count, interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM events {where} "
        f"ORDER BY (is_sponsored AND (sponsor_expires_at IS NULL OR sponsor_expires_at > now())) DESC, "
        f"date ASC "
        f"LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    )
    params.append(limit)
    params.append(offset)
    return await conn.fetch(query, *params)


async def _count_events_basic(conn, category_id: Optional[str], include_past: bool, user_id: Optional[str] = None) -> int:
    """Count total events matching filters (without LIMIT/OFFSET)."""
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

    # Exclude private events unless user is the creator
    if user_id:
        conditions.append(f"(is_public = true OR created_by = ${param_idx})")
        params.append(user_id)
        param_idx += 1
    else:
        conditions.append("is_public = true")

    where = f"WHERE {' AND '.join(conditions)}"
    result = await conn.fetchval(f"SELECT count(*) FROM events {where}", *params)
    return result or 0


async def _increment_sponsor_impression(conn: Any, event_id: str) -> None:
    """Best-effort increment of sponsor impression count."""
    try:
        pool = get_db_pool()
        if pool:
            async with pool.acquire() as c:
                await c.execute(
                    """
                    UPDATE event_sponsor_analytics
                    SET impressions = impressions + 1
                    WHERE event_id = $1
                    """,
                    event_id,
                )
    except Exception as e:
        logger.debug("[events] sponsor impression increment failed: %s", e)


async def _increment_sponsor_rsvp(event_id: str) -> None:
    """Best-effort increment of sponsor RSVP count."""
    try:
        pool = get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE event_sponsor_analytics
                    SET rsvps = rsvps + 1
                    WHERE event_id = $1
                    """,
                    event_id,
                )
    except Exception as e:
        logger.debug("[events] sponsor rsvp increment failed: %s", e)


def _row_to_event(row: dict[str, Any], user_id: Optional[str] = None) -> EventResponse:
    """Convert a database row dict to an EventResponse model."""
    # Filter out expired sponsors
    is_sponsored = bool(row.get("is_sponsored", False))
    sponsor_expires = row.get("sponsor_expires_at")
    if is_sponsored and sponsor_expires is not None:
        try:
            exp = sponsor_expires if isinstance(sponsor_expires, datetime) else datetime.fromisoformat(str(sponsor_expires))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
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
        ticket_price_cents=row.get("ticket_price_cents", 0) or 0,
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
