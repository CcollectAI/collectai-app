"""Shared helpers, constants, models, and in-memory stores for the events sub-package."""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limits
# ---------------------------------------------------------------------------

# Per-user: 30 event search requests per minute (expensive DB queries)
# Applied to auth-required search-like endpoints. For optional-auth listing
# endpoints (search_events, list_nearby_events, list_events), the global
# IP-based middleware rate limit provides protection.
event_search_limit = per_user_rate_limit(30, window_seconds=60, scope="event_search")
# Per-user: 10 RSVP actions per minute (prevent toggle spam)
event_rsvp_limit = per_user_rate_limit(10, window_seconds=60, scope="event_rsvp")
# Per-user: 5 announcements per hour (sends DMs to all attendees)
event_announce_limit = per_user_rate_limit(5, window_seconds=3600, scope="event_announce")
# Per-user: 20 drop alert actions per minute
drop_alert_limit = per_user_rate_limit(20, window_seconds=60, scope="drop_alert")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVENTS_CACHE_TTL = 300  # 5 minutes

ALLOWED_EVENT_KINDS = {"collection_drop", "meetup", "stream", "convention", "release"}
ALLOWED_EVENT_FORMATS = {"in_person", "online", "hybrid"}
ALLOWED_EVENT_STATUSES = {"draft", "published", "cancelled"}

# Explicit whitelist of columns that can be updated via PATCH /{event_id}
UPDATABLE_EVENT_COLUMNS = {"title", "status", "description", "location", "online_url", "image_url", "date", "time", "end_date", "format", "is_public", "max_attendees"}

TEMPLATE_FIELDS = {"title", "kind", "category_id", "format", "location", "online_url",
                   "description", "time", "image_url", "is_public", "max_attendees"}

EVENT_COLUMNS = (
    "id, title, kind, category_id, date, time, end_date, location, "
    "online_url, image_url, description, format, status, is_public, "
    "latitude, longitude, created_by, source, attendee_count, "
    "going_count, interested_count, max_attendees, created_at, "
    "is_sponsored, sponsor_name, sponsor_logo_url, sponsor_expires_at"
)


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


class DropAlertRequest(BaseModel):
    notify_before_hours: int = Field(default=24, ge=1, le=168)


class DropAlertResponse(BaseModel):
    user_id: str
    event_id: str
    notify_before_hours: int = 24
    created_at: Optional[str] = None


class BatchReadRequest(BaseModel):
    announcement_ids: list[str] = Field(..., max_length=100)


# ---------------------------------------------------------------------------
# In-memory fallback stores (used when DB is disabled)
# ---------------------------------------------------------------------------

IN_MEMORY_EVENTS: dict[str, dict[str, Any]] = {}
IN_MEMORY_RSVPS: dict[str, dict[str, str]] = {}  # event_id -> {user_id: status}
IN_MEMORY_FOLLOWS: dict[str, set[str]] = {}  # user_id -> set of category_ids
MAX_IN_MEMORY_EVENTS = 1000  # eviction cap to prevent unbounded memory growth
MAX_IN_MEMORY_FOLLOWS = 500

# In-memory fallback for drop alerts
IN_MEMORY_DROP_ALERTS: dict[str, dict[str, dict]] = {}  # user_id -> {event_id: {...}}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def build_event_conditions(
    category_id: Optional[str],
    include_past: bool,
    user_id: Optional[str] = None,
) -> tuple[list[str], list, int]:
    """Build WHERE conditions + params for event queries.

    All column names are hardcoded string literals — no user input enters
    column positions, so this is safe from SQL injection.
    """
    conditions: list[str] = ["status = 'published'"]
    params: list = []
    param_idx = 1

    if not include_past:
        conditions.append(f"date >= ${param_idx}")
        params.append(date.today().isoformat())
        param_idx += 1

    if category_id:
        conditions.append(f"category_id = ${param_idx}")
        params.append(category_id)
        param_idx += 1

    if user_id:
        conditions.append(f"(is_public = true OR created_by = ${param_idx})")
        params.append(user_id)
        param_idx += 1
    else:
        conditions.append("is_public = true")

    return conditions, params, param_idx


async def fetch_events_basic(
    conn: Any, category_id: Optional[str], include_past: bool, limit: int = 50, offset: int = 0,
) -> list[dict]:
    """Fetch events from the events table with optional filters."""
    conditions, params, param_idx = build_event_conditions(category_id, include_past)
    where = f"WHERE {' AND '.join(conditions)}"
    query = (
        f"SELECT {EVENT_COLUMNS} FROM events {where} "
        f"ORDER BY (is_sponsored AND (sponsor_expires_at IS NULL OR sponsor_expires_at > now())) DESC, "
        f"date ASC "
        f"LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    )
    params.append(limit)
    params.append(offset)
    return await conn.fetch(query, *params)


async def count_events_basic(
    conn: Any, category_id: Optional[str], include_past: bool, user_id: Optional[str] = None,
) -> int:
    """Count total events matching filters (without LIMIT/OFFSET)."""
    conditions, params, _ = build_event_conditions(category_id, include_past, user_id)
    where = f"WHERE {' AND '.join(conditions)}"
    result = await conn.fetchval(f"SELECT count(*) FROM events {where}", *params)
    return result or 0


async def increment_sponsor_impression(conn: Any, event_id: str) -> None:
    """Best-effort increment of sponsor impression count."""
    try:
        from app.lib.db_helpers import get_db_pool
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


async def increment_sponsor_rsvp(event_id: str) -> None:
    """Best-effort increment of sponsor RSVP count."""
    try:
        from app.lib.db_helpers import get_db_pool
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


def row_to_event(row: dict[str, Any], user_id: Optional[str] = None) -> EventResponse:
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


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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
