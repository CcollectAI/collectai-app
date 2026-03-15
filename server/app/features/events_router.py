"""Backward-compatible shim — delegates to app.features.events sub-package.

All imports that previously worked against this module continue to work:
    from app.features.events_router import router
    from app.features.events_router import _IN_MEMORY_EVENTS, EventResponse, ...
"""

from app.features.events import (  # noqa: F401
    router,
    _IN_MEMORY_EVENTS,
    _IN_MEMORY_RSVPS,
    _IN_MEMORY_FOLLOWS,
    _IN_MEMORY_DROP_ALERTS,
    EventResponse,
    EventListResponse,
    CreateEventRequest,
    UpdateEventRequest,
    RsvpRequest,
    FollowCategoryRequest,
    CreateTemplateRequest,
    TemplateResponse,
    AnnouncementRequest,
    AnnouncementResponse,
    DropAlertRequest,
    DropAlertResponse,
    BatchReadRequest,
    ALLOWED_EVENT_KINDS,
    ALLOWED_EVENT_FORMATS,
    ALLOWED_EVENT_STATUSES,
    row_to_event,
    build_event_conditions,
    fetch_events_basic,
    count_events_basic,
    increment_sponsor_impression,
    increment_sponsor_rsvp,
    haversine,
    EVENT_COLUMNS,
    EVENTS_CACHE_TTL,
    UPDATABLE_EVENT_COLUMNS,
    TEMPLATE_FIELDS,
    MAX_IN_MEMORY_EVENTS,
    MAX_IN_MEMORY_FOLLOWS,
)
