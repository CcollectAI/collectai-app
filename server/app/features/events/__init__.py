"""Events sub-package — splits the monolithic events_router into focused modules.

Re-exports ``router`` so that existing imports continue to work::

    from app.features.events import router
    # or via the shim:
    from app.features.events_router import router
"""

from __future__ import annotations

# Import the shared router instance
from ._router import router  # noqa: F401

# Import sub-modules which register their routes on `router` at import time.
# Order matters: modules with fixed paths (e.g. /my-announcements/unread-count)
# must be imported before modules with parameterized paths (/{event_id}) to
# avoid route shadowing.
from . import events_announcements as _announcements  # noqa: F401, E402
from . import events_core as _core  # noqa: F401, E402
from . import events_rsvp as _rsvp  # noqa: F401, E402

# Re-export helpers & models so test files can keep doing:
#   from app.features.events_router import _IN_MEMORY_EVENTS, EventResponse, ...
from .events_helpers import (  # noqa: F401, E402
    IN_MEMORY_EVENTS as _IN_MEMORY_EVENTS,
    IN_MEMORY_RSVPS as _IN_MEMORY_RSVPS,
    IN_MEMORY_FOLLOWS as _IN_MEMORY_FOLLOWS,
    IN_MEMORY_DROP_ALERTS as _IN_MEMORY_DROP_ALERTS,
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
