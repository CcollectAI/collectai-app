"""Tests for the events sub-package split (app.features.events).

Verifies:
  - Backward-compatible shim import from events_router
  - Direct import from app.features.events
  - All public symbols are re-exported
  - Router has exactly 26 routes
  - EVENT_COLUMNS constant exists with expected columns
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("PER_USER_RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Backward-compat shim: from app.features.events_router import ...
# ---------------------------------------------------------------------------

class TestBackwardCompatShim:
    """Importing from events_router.py (the old monolithic module) still works."""

    def test_import_router_from_shim(self):
        from app.features.events_router import router  # noqa: F401
        assert router is not None

    def test_import_event_response_from_shim(self):
        from app.features.events_router import EventResponse  # noqa: F401
        assert EventResponse is not None

    def test_import_in_memory_stores_from_shim(self):
        from app.features.events_router import (  # noqa: F401
            _IN_MEMORY_EVENTS,
            _IN_MEMORY_RSVPS,
            _IN_MEMORY_FOLLOWS,
            _IN_MEMORY_DROP_ALERTS,
        )
        assert isinstance(_IN_MEMORY_EVENTS, dict)
        assert isinstance(_IN_MEMORY_RSVPS, dict)
        assert isinstance(_IN_MEMORY_FOLLOWS, dict)
        assert isinstance(_IN_MEMORY_DROP_ALERTS, dict)

    def test_import_helpers_from_shim(self):
        from app.features.events_router import (  # noqa: F401
            row_to_event,
            build_event_conditions,
            fetch_events_basic,
            count_events_basic,
            haversine,
        )
        assert callable(row_to_event)
        assert callable(build_event_conditions)
        assert callable(fetch_events_basic)
        assert callable(count_events_basic)
        assert callable(haversine)

    def test_import_constants_from_shim(self):
        from app.features.events_router import (  # noqa: F401
            EVENT_COLUMNS,
            EVENTS_CACHE_TTL,
            UPDATABLE_EVENT_COLUMNS,
            TEMPLATE_FIELDS,
            MAX_IN_MEMORY_EVENTS,
            MAX_IN_MEMORY_FOLLOWS,
            ALLOWED_EVENT_KINDS,
            ALLOWED_EVENT_FORMATS,
            ALLOWED_EVENT_STATUSES,
        )
        assert isinstance(EVENT_COLUMNS, str)
        assert isinstance(EVENTS_CACHE_TTL, int)
        assert isinstance(UPDATABLE_EVENT_COLUMNS, set)
        assert isinstance(TEMPLATE_FIELDS, set)
        assert isinstance(ALLOWED_EVENT_KINDS, set)
        assert isinstance(ALLOWED_EVENT_FORMATS, set)
        assert isinstance(ALLOWED_EVENT_STATUSES, set)

    def test_import_request_models_from_shim(self):
        from app.features.events_router import (  # noqa: F401
            CreateEventRequest,
            UpdateEventRequest,
            RsvpRequest,
            FollowCategoryRequest,
            CreateTemplateRequest,
            AnnouncementRequest,
            DropAlertRequest,
            BatchReadRequest,
        )

    def test_import_response_models_from_shim(self):
        from app.features.events_router import (  # noqa: F401
            EventListResponse,
            TemplateResponse,
            AnnouncementResponse,
            DropAlertResponse,
        )


# ---------------------------------------------------------------------------
# Direct import: from app.features.events import ...
# ---------------------------------------------------------------------------

class TestDirectImport:
    """Importing directly from the events sub-package works."""

    def test_import_router_from_package(self):
        from app.features.events import router  # noqa: F401
        assert router is not None

    def test_import_event_response_from_package(self):
        from app.features.events import EventResponse  # noqa: F401
        assert EventResponse is not None

    def test_import_in_memory_stores_from_package(self):
        from app.features.events import (  # noqa: F401
            _IN_MEMORY_EVENTS,
            _IN_MEMORY_RSVPS,
            _IN_MEMORY_FOLLOWS,
            _IN_MEMORY_DROP_ALERTS,
        )
        assert isinstance(_IN_MEMORY_EVENTS, dict)

    def test_import_helpers_from_package(self):
        from app.features.events import (  # noqa: F401
            row_to_event,
            build_event_conditions,
            fetch_events_basic,
            count_events_basic,
            increment_sponsor_impression,
            increment_sponsor_rsvp,
            haversine,
        )

    def test_import_constants_from_package(self):
        from app.features.events import (  # noqa: F401
            EVENT_COLUMNS,
            EVENTS_CACHE_TTL,
            UPDATABLE_EVENT_COLUMNS,
            TEMPLATE_FIELDS,
            MAX_IN_MEMORY_EVENTS,
            MAX_IN_MEMORY_FOLLOWS,
            ALLOWED_EVENT_KINDS,
            ALLOWED_EVENT_FORMATS,
            ALLOWED_EVENT_STATUSES,
        )


# ---------------------------------------------------------------------------
# Router identity: both paths yield the same router object
# ---------------------------------------------------------------------------

class TestRouterIdentity:
    def test_shim_and_package_same_router(self):
        from app.features.events import router as r1
        from app.features.events_router import router as r2
        assert r1 is r2

    def test_router_has_26_routes(self):
        from app.features.events import router
        assert len(router.routes) == 26, (
            f"Expected 26 routes, got {len(router.routes)}: "
            f"{[getattr(r, 'path', '?') for r in router.routes]}"
        )


# ---------------------------------------------------------------------------
# EVENT_COLUMNS constant
# ---------------------------------------------------------------------------

class TestEventColumns:
    def test_event_columns_is_string(self):
        from app.features.events import EVENT_COLUMNS
        assert isinstance(EVENT_COLUMNS, str)

    def test_event_columns_has_expected_fields(self):
        from app.features.events import EVENT_COLUMNS
        expected = [
            "id", "title", "kind", "category_id", "date", "time",
            "end_date", "location", "online_url", "image_url",
            "description", "format", "status", "is_public",
            "latitude", "longitude", "created_by", "source",
            "attendee_count", "going_count", "interested_count",
            "max_attendees", "created_at", "is_sponsored",
            "sponsor_name", "sponsor_logo_url", "sponsor_expires_at",
        ]
        for col in expected:
            assert col in EVENT_COLUMNS, f"Missing column: {col}"
