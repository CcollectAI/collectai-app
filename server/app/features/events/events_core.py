"""Core event CRUD endpoints: search, list, create, get, update, delete, nearby, duplicate,
ticket checkout, category follows, templates, and drop alerts."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, time as dt_time, timezone
from typing import Any, List, Optional
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, Depends, HTTPException, Query

from app.auth import get_current_user_id, get_optional_user_id
from app.cache import cache_get, cache_set
from app.config import STRIPE_SECRET_KEY
from app.errors import error_response
from app.features.pagination import pagination_params
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode

from .events_helpers import (
    ALLOWED_EVENT_FORMATS,
    ALLOWED_EVENT_KINDS,
    ALLOWED_EVENT_STATUSES,
    CreateEventRequest,
    CreateTemplateRequest,
    DropAlertRequest,
    DropAlertResponse,
    EVENT_COLUMNS,
    EVENTS_CACHE_TTL,
    EventListResponse,
    EventResponse,
    IN_MEMORY_DROP_ALERTS,
    IN_MEMORY_EVENTS,
    IN_MEMORY_FOLLOWS,
    IN_MEMORY_RSVPS,
    MAX_IN_MEMORY_EVENTS,
    MAX_IN_MEMORY_FOLLOWS,
    TEMPLATE_FIELDS,
    TemplateResponse,
    UPDATABLE_EVENT_COLUMNS,
    UpdateEventRequest,
    count_events_basic,
    drop_alert_limit,
    event_rsvp_limit,
    event_search_limit,
    fetch_events_basic,
    haversine,
    increment_sponsor_impression,
    row_to_event,
)

from ._router import router as core_router

try:
    import stripe
except ImportError:
    stripe = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Endpoints — Events
# ---------------------------------------------------------------------------


@core_router.get("/search", response_model=EventListResponse, summary="Search events")
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
                       (SELECT COUNT(*) FROM event_attendees ea WHERE ea.event_id::uuid = e.id AND ea.status = 'going') AS going_count,
                       (SELECT COUNT(*) FROM event_attendees ea WHERE ea.event_id::uuid = e.id AND ea.status = 'interested') AS interested_count
                FROM events e
                WHERE {where}
                ORDER BY date ASC
                LIMIT ${idx} OFFSET ${idx + 1}
            """
            params.extend([limit, offset])

            rows = await conn.fetch(query_str, *params)
            events = [row_to_event(dict(r)) for r in rows] if rows else []

        # Record event-search demand signal (best-effort, after pool released).
        # Pre-fix: events /search captured nothing — event-search text was
        # invisible in the intelligence layer.
        if q.strip():
            try:
                from app.features.data_moat import record_demand_signal
                await record_demand_signal(
                    signal_type="search_query",
                    category=category or "event",
                    query_text=q.strip()[:200],
                    user_id=user_id,
                )
            except Exception as ds_e:
                logger.debug("[events/search] demand_signal record failed: %s", ds_e)

        return EventListResponse(events=events, total=total_count or 0)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise e
        logger.warning("search_events error: %s", e)
        raise error_response(500, "Event search failed", code=ErrorCode.INTERNAL_ERROR)


@core_router.get("", response_model=EventListResponse, summary="List personalized events")
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
                total_count = await count_events_basic(conn, category_id, include_past, user_id=user_id)

                if user_id:
                    # Try the personalized RPC first
                    try:
                        rows = await conn.fetch(
                            "SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, attendee_count, going_count, interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM rpc_list_personalized_events_v1($1, $2, $3) LIMIT $4 OFFSET $5",
                            user_id,
                            category_id,
                            include_past,
                            limit,
                            offset,
                        )
                    except Exception as rpc_err:
                        logger.warning("[events] Personalized RPC failed, falling back: %s", rpc_err)
                        rows = await fetch_events_basic(conn, category_id, include_past, limit, offset)
                else:
                    rows = await fetch_events_basic(conn, category_id, include_past, limit, offset)

                events = []
                for row in rows:
                    ev = row_to_event(dict(row), user_id=user_id)
                    # Hide non-public events unless the user is the creator
                    if not ev.is_public and ev.created_by != user_id:
                        continue
                    events.append(ev)
                result = EventListResponse(events=events, total=total_count)
                cache_set(cache_key, result, ttl=EVENTS_CACHE_TTL)
                return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error listing events: %s", e)
            raise error_response(500, "Failed to list events", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    today_str = date.today().isoformat()
    events = []
    for ev in IN_MEMORY_EVENTS.values():
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
        rsvps = IN_MEMORY_RSVPS.get(ev["id"], {})
        ev_copy = {**ev, "attendee_count": len(rsvps)}
        if user_id:
            ev_copy["user_rsvp_status"] = rsvps.get(user_id)
        events.append(EventResponse(**ev_copy))
    # Sort: sponsored first, then by date
    events.sort(key=lambda e: (not e.is_sponsored, e.date))
    total_count = len(events)
    result = EventListResponse(events=events[offset:offset + limit], total=total_count)
    cache_set(cache_key, result, ttl=EVENTS_CACHE_TTL)
    return result


@core_router.post("", response_model=EventResponse, status_code=201, summary="Create an event")
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
                    # asyncpg requires Python date/time objects for date/time
                    # columns; the request validator keeps these as strings
                    # (YYYY-MM-DD / HH:MM). Parse here. 2026-04-22.
                    date.fromisoformat(request.date),
                    dt_time.fromisoformat(request.time) if request.time else None,
                    date.fromisoformat(request.end_date) if request.end_date else None,
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
                return row_to_event(dict(row), user_id=user_id)

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
    IN_MEMORY_EVENTS[event_id] = event_data
    # Evict oldest entries if over capacity
    while len(IN_MEMORY_EVENTS) > MAX_IN_MEMORY_EVENTS:
        IN_MEMORY_EVENTS.pop(next(iter(IN_MEMORY_EVENTS)))
    logger.info("[events] Created event (in-memory): id=%s, title=%s", event_id, request.title)
    return EventResponse(**event_data)


@core_router.get("/nearby", response_model=EventListResponse, summary="List nearby events")
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
                    SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, 0 AS attendee_count, 0 AS going_count, 0 AS interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at,
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
                events = [row_to_event(dict(r), user_id=user_id) for r in rows]
                result = EventListResponse(events=events, total=total_count or 0)
                cache_set(cache_key, result, ttl=EVENTS_CACHE_TTL)
                return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error listing nearby events: %s", e)
            raise error_response(500, "Failed to list nearby events", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback with Haversine
    today_str = date.today().isoformat()
    events_with_dist = []
    for ev in IN_MEMORY_EVENTS.values():
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
        dist = haversine(lat, lon, ev_lat, ev_lon)
        if dist <= radius_km:
            events_with_dist.append((dist, ev))

    events_with_dist.sort(key=lambda x: x[0])
    total_count = len(events_with_dist)
    events = [
        EventResponse(**{**ev, "attendee_count": len(IN_MEMORY_RSVPS.get(ev["id"], {}))})
        for _, ev in events_with_dist[offset:offset + limit]
    ]
    result = EventListResponse(events=events, total=total_count)
    cache_set(cache_key, result, ttl=EVENTS_CACHE_TTL)
    return result


# ---------------------------------------------------------------------------
# Endpoints — Category follows
# NOTE: These MUST be registered before /{event_id} to avoid route shadowing.
# ---------------------------------------------------------------------------

@core_router.get("/categories/followed", summary="List followed categories")
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
    follows = IN_MEMORY_FOLLOWS.get(user_id, set())
    return {"categories": sorted(follows)}


@core_router.post("/categories/{category_id}/follow", summary="Follow a category")
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
            try:
                from app.features.data_moat import record_demand_signal
                await record_demand_signal(
                    signal_type="event_followed",
                    category=category_id,
                    user_id=user_id,
                )
            except Exception:
                pass
            return {"success": True, "category_id": category_id}

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error following category %s: %s", category_id, e)
            raise error_response(500, "Failed to follow category", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    IN_MEMORY_FOLLOWS.setdefault(user_id, set()).add(category_id)
    # Evict oldest user entries if over capacity
    while len(IN_MEMORY_FOLLOWS) > MAX_IN_MEMORY_FOLLOWS:
        IN_MEMORY_FOLLOWS.pop(next(iter(IN_MEMORY_FOLLOWS)))
    logger.info("[events] Follow category (in-memory): user=%s, category=%s", user_id, category_id)
    return {"success": True, "category_id": category_id}


@core_router.delete("/categories/{category_id}/follow", summary="Unfollow a category")
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
    follows = IN_MEMORY_FOLLOWS.get(user_id, set())
    follows.discard(category_id)
    logger.info("[events] Unfollow category (in-memory): user=%s, category=%s", user_id, category_id)
    return {"success": True, "message": "Category unfollowed"}


@core_router.get("/categories/{category_id}/following", summary="Check category follow status")
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
    follows = IN_MEMORY_FOLLOWS.get(user_id, set())
    return {"following": category_id in follows}


# ---------------------------------------------------------------------------
# Endpoints — Drop Alerts (MUST be registered before /{event_id})
# ---------------------------------------------------------------------------


@core_router.get("/my-alerts", response_model=List[DropAlertResponse], summary="List my drop alerts")
async def list_my_drop_alerts(
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(drop_alert_limit),
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
    alerts = IN_MEMORY_DROP_ALERTS.get(user_id, {})
    return [
        DropAlertResponse(
            user_id=user_id,
            event_id=eid,
            notify_before_hours=data.get("notify_before_hours", 24),
            created_at=data.get("created_at"),
        )
        for eid, data in alerts.items()
    ]


@core_router.post("/{event_id}/alert", response_model=DropAlertResponse, status_code=201, summary="Subscribe to drop alert")
async def subscribe_drop_alert(
    event_id: str,
    request: DropAlertRequest = DropAlertRequest(),
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(drop_alert_limit),
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
    IN_MEMORY_DROP_ALERTS.setdefault(user_id, {})[event_id] = {
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


@core_router.delete("/{event_id}/alert", summary="Unsubscribe from drop alert")
async def unsubscribe_drop_alert(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(drop_alert_limit),
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
    alerts = IN_MEMORY_DROP_ALERTS.get(user_id, {})
    alerts.pop(event_id, None)
    logger.info("[events] Drop alert unsubscribed (in-memory): user=%s, event=%s", user_id, event_id)
    return {"success": True, "message": "Drop alert removed"}


# ---------------------------------------------------------------------------
# Endpoints — Templates (MUST be registered before /{event_id})
# ---------------------------------------------------------------------------


@core_router.get("/templates", response_model=List[TemplateResponse], summary="List event templates")
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


@core_router.post("/templates", response_model=TemplateResponse, status_code=201, summary="Create event template")
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
                    "SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, 0 AS attendee_count, 0 AS going_count, 0 AS interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM events WHERE id = $1 AND created_by = $2",
                    request.from_event_id, user_id,
                )
                if not ev_row:
                    raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)
                ev = dict(ev_row)
                template_data = {k: ev[k] for k in TEMPLATE_FIELDS if ev.get(k) is not None}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error copying event for template: %s", e)
            raise error_response(500, "Failed to create template", code=ErrorCode.INTERNAL_ERROR)

    if pool is not None:
        try:
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


@core_router.delete("/templates/{template_id}", summary="Delete event template")
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
# Endpoints — Single event + update/delete (parameterized routes last)
# ---------------------------------------------------------------------------

@core_router.get("/{event_id}", response_model=EventResponse, summary="Get event detail")
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
                        # `attendees` was non-existent; view exposes
                        # attendee_count / going_count / interested_count.
                        "SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, attendee_count, going_count, interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM v_events_with_attendees_v1 WHERE id = $1",
                        event_id,
                    )
                except Exception as view_err:
                    logger.warning("[events] View query failed, falling back to events table: %s", view_err)
                    row = await conn.fetchrow(
                        "SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, 0 AS attendee_count, 0 AS going_count, 0 AS interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM events WHERE id = $1",
                        event_id,
                    )

                if row is None:
                    raise error_response(404, "Event not found", code=ErrorCode.NOT_FOUND)

                event = row_to_event(dict(row), user_id=user_id)

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
                    background_tasks.add_task(increment_sponsor_impression, conn, event_id)

                # Record demand signal for event view (best-effort).
                # Pre-fix: events_router did not call record_demand_signal at
                # all, so /intelligence/top-events could only show follower
                # counts (event_follows_v1) — never view-count or scan-count.
                if user_id:
                    try:
                        from app.features.data_moat import record_demand_signal
                        await record_demand_signal(
                            signal_type="event_viewed",
                            category=event.category_id or "event",
                            item_key=event_id,
                            user_id=user_id,
                        )
                    except Exception as ds_e:
                        logger.debug("[events] demand_signal record failed: %s", ds_e)

                return event

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error fetching event %s: %s", event_id, e)
            raise error_response(500, "Failed to fetch event", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    ev = IN_MEMORY_EVENTS.get(event_id)
    if ev is None:
        raise error_response(404, "Event not found", code=ErrorCode.NOT_FOUND)

    # Hide non-public events unless the user is the creator
    if not ev.get("is_public", True) and ev.get("created_by") != user_id:
        raise error_response(404, "Event not found", code=ErrorCode.NOT_FOUND)

    rsvps = IN_MEMORY_RSVPS.get(event_id, {})
    ev_copy = {**ev, "attendee_count": len(rsvps)}
    if user_id:
        ev_copy["user_rsvp_status"] = rsvps.get(user_id)
    return EventResponse(**ev_copy)


@core_router.patch("/{event_id}", response_model=EventResponse, summary="Update an event")
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
    bad_keys = set(updates.keys()) - UPDATABLE_EVENT_COLUMNS
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
                    "SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, 0 AS attendee_count, 0 AS going_count, 0 AS interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM events WHERE id = $1 AND created_by = $2",
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
                return row_to_event(dict(updated), user_id=user_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error updating event %s: %s", event_id, e)
            raise error_response(500, "Failed to update event", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    ev = IN_MEMORY_EVENTS.get(event_id)
    if ev is None or ev.get("created_by") != user_id:
        raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)

    ev.update(updates)
    return EventResponse(**ev)


@core_router.delete("/{event_id}", summary="Cancel an event")
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
    ev = IN_MEMORY_EVENTS.get(event_id)
    if ev is None or ev.get("created_by") != user_id:
        raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)
    ev["status"] = "cancelled"
    logger.info("[events] Soft-deleted event (in-memory): id=%s", event_id)
    return {"success": True, "message": "Event cancelled"}


# ---------------------------------------------------------------------------
# Endpoints — Ticket Checkout
# ---------------------------------------------------------------------------

@core_router.post("/{event_id}/ticket-checkout", summary="Create ticket checkout session", description="Creates a Stripe Checkout Session for a paid event ticket with a 5% platform fee.")
async def ticket_checkout(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(event_rsvp_limit),
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
                "SELECT id, title, ticket_price_cents, status, max_attendees, category_id FROM events WHERE id = $1",
                event_id,
            )
            if not row:
                raise error_response(404, "Event not found", code=ErrorCode.NOT_FOUND)
            if row["status"] != "published":
                raise error_response(400, "Event is not published", code=ErrorCode.VALIDATION_ERROR)

            ticket_price = row.get("ticket_price_cents") or 0
            if ticket_price <= 0:
                raise error_response(400, "This event is free — use RSVP instead", code=ErrorCode.VALIDATION_ERROR)

        # Funnel signal — user clicked "buy ticket" (intent, not yet paid;
        # the actual purchase fires via stripe webhook → subscription_purchased
        # path). Lets us measure intent→purchase drop-off.
        try:
            from app.features.data_moat import record_demand_signal
            await record_demand_signal(
                signal_type="ticket_clicked",
                category=row.get("category_id") or "event",
                item_key=event_id,
                user_id=user_id,
            )
        except Exception:
            pass

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
            # Auto-detect payment methods (card, iDEAL, SEPA, etc.) by region
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
# Endpoints — Duplicate
# ---------------------------------------------------------------------------

@core_router.post("/{event_id}/duplicate", response_model=EventResponse, status_code=201, summary="Duplicate an event")
async def duplicate_event(
    event_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(event_search_limit),
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
                    "SELECT id, title, kind, category_id, date, time, end_date, location, online_url, image_url, description, format, status, is_public, latitude, longitude, created_by, source, 0 AS attendee_count, 0 AS going_count, 0 AS interested_count, max_attendees, created_at, is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at FROM events WHERE id = $1 AND created_by = $2",
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
                return row_to_event(dict(new_row), user_id=user_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("[events] Error duplicating event %s: %s", event_id, e)
            raise error_response(500, "Failed to duplicate event", code=ErrorCode.INTERNAL_ERROR)

    # Offline / in-memory fallback
    ev = IN_MEMORY_EVENTS.get(event_id)
    if ev is None or ev.get("created_by") != user_id:
        raise error_response(404, "Event not found or not owned by you", code=ErrorCode.NOT_FOUND)

    new_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    dup = {**ev, "id": new_id, "status": "draft", "date": date.today().isoformat(),
           "attendee_count": 0, "created_at": now}
    IN_MEMORY_EVENTS[new_id] = dup
    return EventResponse(**dup)
