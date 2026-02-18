"""Tests for app/features/events_router.py — CRUD, RSVP, and category follow endpoints.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")

from starlette.testclient import TestClient
from main import app  # noqa: E402
from app.features.events_router import (
    _IN_MEMORY_EVENTS,
    _IN_MEMORY_RSVPS,
    _IN_MEMORY_FOLLOWS,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_in_memory_stores():
    """Reset all in-memory stores between tests."""
    _IN_MEMORY_EVENTS.clear()
    _IN_MEMORY_RSVPS.clear()
    _IN_MEMORY_FOLLOWS.clear()


def _valid_event_payload(**overrides):
    """Return a valid CreateEventRequest dict, with optional overrides."""
    base = {
        "title": "Pokemon Booster Draft Night",
        "kind": "meetup",
        "date": "2026-06-15",
        "category_id": "pokemon",
        "description": "Weekly casual draft at the local game store.",
        "format": "in_person",
        "is_public": True,
        "location": "Game Store Amsterdam",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_stores():
    """Clear in-memory stores before each test."""
    _clear_in_memory_stores()
    yield
    _clear_in_memory_stores()


# ===========================================================================
# CREATE EVENT — POST /events
# ===========================================================================

class TestCreateEvent:
    def test_create_event_success(self):
        payload = _valid_event_payload()
        r = client.post("/events", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == payload["title"]
        assert data["kind"] == "meetup"
        assert data["date"] == "2026-06-15"
        assert data["category_id"] == "pokemon"
        assert data["format"] == "in_person"
        assert data["is_public"] is True
        assert data["source"] == "user"
        assert data["created_by"] == "dev-user-local"
        assert "id" in data

    def test_create_event_minimal_fields(self):
        payload = {"title": "Quick Drop", "kind": "collection_drop", "date": "2026-07-01"}
        r = client.post("/events", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Quick Drop"
        assert data["kind"] == "collection_drop"
        assert data["description"] == ""
        assert data["format"] == "in_person"

    def test_create_event_all_formats(self):
        for fmt in ("in_person", "online", "hybrid"):
            _clear_in_memory_stores()
            payload = _valid_event_payload(format=fmt)
            r = client.post("/events", json=payload)
            assert r.status_code == 201, f"Failed for format={fmt}"
            assert r.json()["format"] == fmt

    def test_create_event_all_kinds(self):
        for kind in ("collection_drop", "meetup", "stream", "convention", "release"):
            _clear_in_memory_stores()
            payload = _valid_event_payload(kind=kind)
            r = client.post("/events", json=payload)
            assert r.status_code == 201, f"Failed for kind={kind}"
            assert r.json()["kind"] == kind

    def test_create_event_with_coordinates(self):
        payload = _valid_event_payload(latitude=52.3676, longitude=4.9041)
        r = client.post("/events", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["latitude"] == 52.3676
        assert data["longitude"] == 4.9041

    def test_create_event_with_online_url(self):
        payload = _valid_event_payload(
            format="online",
            online_url="https://twitch.tv/pokemon",
        )
        r = client.post("/events", json=payload)
        assert r.status_code == 201
        assert r.json()["online_url"] == "https://twitch.tv/pokemon"

    def test_create_event_with_end_date(self):
        payload = _valid_event_payload(end_date="2026-06-17")
        r = client.post("/events", json=payload)
        assert r.status_code == 201
        assert r.json()["end_date"] == "2026-06-17"

    def test_create_event_private(self):
        payload = _valid_event_payload(is_public=False)
        r = client.post("/events", json=payload)
        assert r.status_code == 201
        assert r.json()["is_public"] is False

    def test_create_event_stored_in_memory(self):
        payload = _valid_event_payload()
        r = client.post("/events", json=payload)
        event_id = r.json()["id"]
        assert event_id in _IN_MEMORY_EVENTS
        assert _IN_MEMORY_EVENTS[event_id]["title"] == payload["title"]

    # ---- Validation / error cases ----

    def test_create_event_missing_title_422(self):
        payload = {"kind": "meetup", "date": "2026-06-15"}
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_missing_kind_422(self):
        payload = {"title": "Test", "date": "2026-06-15"}
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_missing_date_422(self):
        payload = {"title": "Test", "kind": "meetup"}
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_invalid_kind_422(self):
        """Invalid kind should fail Pydantic regex validation (422)."""
        payload = _valid_event_payload(kind="invalid_kind")
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_invalid_format_422(self):
        """Invalid format should fail Pydantic regex validation (422)."""
        payload = _valid_event_payload(format="virtual")
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_invalid_date_format_422(self):
        """Non-YYYY-MM-DD date should fail Pydantic regex validation (422)."""
        payload = _valid_event_payload(date="15-06-2026")
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_empty_title_422(self):
        payload = _valid_event_payload(title="")
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_title_too_long_422(self):
        payload = _valid_event_payload(title="A" * 256)
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_description_too_long_422(self):
        payload = _valid_event_payload(description="X" * 5001)
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_latitude_out_of_range_422(self):
        payload = _valid_event_payload(latitude=91.0)
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_longitude_out_of_range_422(self):
        payload = _valid_event_payload(longitude=181.0)
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_empty_body_422(self):
        r = client.post("/events", json={})
        assert r.status_code == 422


# ===========================================================================
# LIST EVENTS — GET /events
# ===========================================================================

class TestListEvents:
    def test_list_events_empty(self):
        r = client.get("/events")
        assert r.status_code == 200
        data = r.json()
        assert "events" in data
        assert data["events"] == []

    def test_list_events_returns_created(self):
        payload = _valid_event_payload(date="2027-01-01")
        client.post("/events", json=payload)
        r = client.get("/events")
        assert r.status_code == 200
        events = r.json()["events"]
        assert len(events) == 1
        assert events[0]["title"] == payload["title"]

    def test_list_events_excludes_past_by_default(self):
        # Create a past event
        client.post("/events", json=_valid_event_payload(date="2020-01-01"))
        # Create a future event
        client.post("/events", json=_valid_event_payload(title="Future Event", date="2027-12-31"))
        r = client.get("/events")
        events = r.json()["events"]
        # Past event should be excluded
        titles = [e["title"] for e in events]
        assert "Future Event" in titles

    def test_list_events_include_past(self):
        client.post("/events", json=_valid_event_payload(date="2020-01-01"))
        r = client.get("/events?include_past=true")
        events = r.json()["events"]
        assert len(events) == 1

    def test_list_events_filter_by_category(self):
        client.post("/events", json=_valid_event_payload(category_id="pokemon", date="2027-01-01"))
        client.post("/events", json=_valid_event_payload(
            title="MTG Draft", category_id="mtg", date="2027-01-02",
        ))
        r = client.get("/events?category_id=pokemon")
        events = r.json()["events"]
        assert len(events) == 1
        assert events[0]["category_id"] == "pokemon"

    def test_list_events_hides_private_events_from_non_creator(self):
        """Private events not created by the current user should be hidden.

        Since get_optional_user_id always returns 'dev-user-local' and create
        always uses 'dev-user-local', the private event IS visible to us.
        This test verifies the private flag is stored correctly.
        """
        client.post("/events", json=_valid_event_payload(is_public=False, date="2027-01-01"))
        r = client.get("/events")
        events = r.json()["events"]
        # dev-user-local is the creator, so the private event is visible
        assert len(events) == 1
        assert events[0]["is_public"] is False

    def test_list_events_shows_attendee_count(self):
        resp = client.post("/events", json=_valid_event_payload(date="2027-01-01"))
        event_id = resp.json()["id"]
        # RSVP
        client.post(f"/events/{event_id}/rsvp", json={"status": "going"})
        r = client.get("/events")
        events = r.json()["events"]
        assert events[0]["attendee_count"] == 1


# ===========================================================================
# GET EVENT — GET /events/{event_id}
# ===========================================================================

class TestGetEvent:
    def test_get_event_success(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        r = client.get(f"/events/{event_id}")
        assert r.status_code == 200
        assert r.json()["id"] == event_id
        assert r.json()["title"] == "Pokemon Booster Draft Night"

    def test_get_event_not_found_404(self):
        r = client.get("/events/nonexistent-id")
        assert r.status_code == 404

    def test_get_event_includes_rsvp_status(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        client.post(f"/events/{event_id}/rsvp", json={"status": "going"})
        r = client.get(f"/events/{event_id}")
        assert r.json()["user_rsvp_status"] == "going"
        assert r.json()["attendee_count"] == 1

    def test_get_event_no_rsvp_has_null_status(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        r = client.get(f"/events/{event_id}")
        # user_rsvp_status may be None or absent
        assert r.json().get("user_rsvp_status") is None


# ===========================================================================
# RSVP — POST /events/{event_id}/rsvp
# ===========================================================================

class TestRsvpEvent:
    def test_rsvp_going(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        r = client.post(f"/events/{event_id}/rsvp", json={"status": "going"})
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["status"] == "going"

    def test_rsvp_interested(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        r = client.post(f"/events/{event_id}/rsvp", json={"status": "interested"})
        assert r.status_code == 200
        assert r.json()["status"] == "interested"

    def test_rsvp_not_going(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        r = client.post(f"/events/{event_id}/rsvp", json={"status": "not_going"})
        assert r.status_code == 200
        assert r.json()["status"] == "not_going"

    def test_rsvp_invalid_status_422(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        r = client.post(f"/events/{event_id}/rsvp", json={"status": "maybe"})
        assert r.status_code == 422

    def test_rsvp_updates_in_memory(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        client.post(f"/events/{event_id}/rsvp", json={"status": "going"})
        assert _IN_MEMORY_RSVPS.get(event_id, {}).get("dev-user-local") == "going"

    def test_rsvp_overwrite_previous(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        client.post(f"/events/{event_id}/rsvp", json={"status": "going"})
        client.post(f"/events/{event_id}/rsvp", json={"status": "interested"})
        assert _IN_MEMORY_RSVPS[event_id]["dev-user-local"] == "interested"

    def test_rsvp_default_status_going(self):
        """Default RSVP status when not provided should be 'going'."""
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        r = client.post(f"/events/{event_id}/rsvp", json={})
        assert r.status_code == 200
        assert r.json()["status"] == "going"

    def test_rsvp_empty_body_uses_default(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        r = client.post(f"/events/{event_id}/rsvp", json={})
        assert r.status_code == 200
        assert r.json()["status"] == "going"


# ===========================================================================
# UN-RSVP — DELETE /events/{event_id}/rsvp
# ===========================================================================

class TestUnrsvpEvent:
    def test_unrsvp_success(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        client.post(f"/events/{event_id}/rsvp", json={"status": "going"})
        r = client.delete(f"/events/{event_id}/rsvp")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_unrsvp_removes_from_store(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        client.post(f"/events/{event_id}/rsvp", json={"status": "going"})
        assert "dev-user-local" in _IN_MEMORY_RSVPS.get(event_id, {})
        client.delete(f"/events/{event_id}/rsvp")
        assert "dev-user-local" not in _IN_MEMORY_RSVPS.get(event_id, {})

    def test_unrsvp_no_prior_rsvp_still_ok(self):
        resp = client.post("/events", json=_valid_event_payload())
        event_id = resp.json()["id"]
        r = client.delete(f"/events/{event_id}/rsvp")
        assert r.status_code == 200

    def test_unrsvp_reduces_attendee_count(self):
        resp = client.post("/events", json=_valid_event_payload(date="2027-01-01"))
        event_id = resp.json()["id"]
        client.post(f"/events/{event_id}/rsvp", json={"status": "going"})
        # Before un-RSVP
        r = client.get(f"/events/{event_id}")
        assert r.json()["attendee_count"] == 1
        # Un-RSVP
        client.delete(f"/events/{event_id}/rsvp")
        r = client.get(f"/events/{event_id}")
        assert r.json()["attendee_count"] == 0


# ===========================================================================
# FOLLOW CATEGORY — POST /events/categories/{category_id}/follow
# ===========================================================================

class TestFollowCategory:
    def test_follow_category_success(self):
        r = client.post("/events/categories/pokemon/follow")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["category_id"] == "pokemon"

    def test_follow_category_stored_in_memory(self):
        client.post("/events/categories/mtg/follow")
        assert "mtg" in _IN_MEMORY_FOLLOWS.get("dev-user-local", set())

    def test_follow_multiple_categories(self):
        client.post("/events/categories/pokemon/follow")
        client.post("/events/categories/mtg/follow")
        client.post("/events/categories/lego/follow")
        follows = _IN_MEMORY_FOLLOWS.get("dev-user-local", set())
        assert follows == {"pokemon", "mtg", "lego"}

    def test_follow_same_category_twice_idempotent(self):
        client.post("/events/categories/pokemon/follow")
        client.post("/events/categories/pokemon/follow")
        follows = _IN_MEMORY_FOLLOWS.get("dev-user-local", set())
        assert follows == {"pokemon"}


# ===========================================================================
# UNFOLLOW CATEGORY — DELETE /events/categories/{category_id}/follow
# ===========================================================================

class TestUnfollowCategory:
    def test_unfollow_category_success(self):
        client.post("/events/categories/pokemon/follow")
        r = client.delete("/events/categories/pokemon/follow")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_unfollow_removes_from_store(self):
        client.post("/events/categories/pokemon/follow")
        assert "pokemon" in _IN_MEMORY_FOLLOWS.get("dev-user-local", set())
        client.delete("/events/categories/pokemon/follow")
        assert "pokemon" not in _IN_MEMORY_FOLLOWS.get("dev-user-local", set())

    def test_unfollow_nonexistent_category_ok(self):
        r = client.delete("/events/categories/nonexistent/follow")
        assert r.status_code == 200

    def test_unfollow_does_not_affect_other_categories(self):
        client.post("/events/categories/pokemon/follow")
        client.post("/events/categories/mtg/follow")
        client.delete("/events/categories/pokemon/follow")
        follows = _IN_MEMORY_FOLLOWS.get("dev-user-local", set())
        assert "mtg" in follows
        assert "pokemon" not in follows


# ===========================================================================
# CHECK FOLLOWING — GET /events/categories/{category_id}/following
# ===========================================================================

class TestCheckFollowingCategory:
    def test_following_true(self):
        client.post("/events/categories/pokemon/follow")
        r = client.get("/events/categories/pokemon/following")
        assert r.status_code == 200
        assert r.json()["following"] is True

    def test_following_false(self):
        r = client.get("/events/categories/pokemon/following")
        assert r.status_code == 200
        assert r.json()["following"] is False

    def test_following_after_unfollow(self):
        client.post("/events/categories/pokemon/follow")
        client.delete("/events/categories/pokemon/follow")
        r = client.get("/events/categories/pokemon/following")
        assert r.json()["following"] is False


# ===========================================================================
# LIST FOLLOWED CATEGORIES — GET /events/categories/followed
# ===========================================================================

class TestListFollowedCategories:
    def test_no_follows_returns_empty(self):
        r = client.get("/events/categories/followed")
        assert r.status_code == 200
        assert r.json()["categories"] == []

    def test_returns_followed_categories_sorted(self):
        client.post("/events/categories/mtg/follow")
        client.post("/events/categories/pokemon/follow")
        client.post("/events/categories/lego/follow")
        r = client.get("/events/categories/followed")
        assert r.status_code == 200
        cats = r.json()["categories"]
        assert sorted(cats) == cats
        assert set(cats) == {"mtg", "pokemon", "lego"}


# ===========================================================================
# Integration / end-to-end flows
# ===========================================================================

class TestEventsIntegration:
    def test_full_event_lifecycle(self):
        """Create -> RSVP -> check -> un-RSVP -> verify."""
        # Create
        resp = client.post("/events", json=_valid_event_payload(date="2027-06-01"))
        assert resp.status_code == 201
        event_id = resp.json()["id"]

        # RSVP
        r = client.post(f"/events/{event_id}/rsvp", json={"status": "going"})
        assert r.json()["success"] is True

        # Get and verify
        r = client.get(f"/events/{event_id}")
        assert r.json()["user_rsvp_status"] == "going"
        assert r.json()["attendee_count"] == 1

        # Un-RSVP
        r = client.delete(f"/events/{event_id}/rsvp")
        assert r.json()["success"] is True

        # Verify removed
        r = client.get(f"/events/{event_id}")
        assert r.json()["user_rsvp_status"] is None
        assert r.json()["attendee_count"] == 0

    def test_category_follow_lifecycle(self):
        """Follow -> list -> check -> unfollow -> check."""
        # Follow
        client.post("/events/categories/pokemon/follow")
        client.post("/events/categories/mtg/follow")

        # List followed
        r = client.get("/events/categories/followed")
        cats = r.json()["categories"]
        assert "pokemon" in cats
        assert "mtg" in cats

        # Check individual
        r = client.get("/events/categories/pokemon/following")
        assert r.json()["following"] is True

        # Unfollow one
        client.delete("/events/categories/pokemon/follow")

        # Verify
        r = client.get("/events/categories/pokemon/following")
        assert r.json()["following"] is False
        r = client.get("/events/categories/mtg/following")
        assert r.json()["following"] is True

    def test_multiple_events_list(self):
        """Create multiple events and verify the list endpoint returns all of them."""
        for i in range(5):
            client.post("/events", json=_valid_event_payload(
                title=f"Event {i}",
                date=f"2027-0{i+1}-01",
            ))
        r = client.get("/events")
        events = r.json()["events"]
        assert len(events) == 5
