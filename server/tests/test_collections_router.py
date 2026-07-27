"""Tests for app/features/collections_router.py — Set completion tracking (Item 20)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from starlette.testclient import TestClient

from main import app
from app.features.collections_router import _mem_collections

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_stores():
    _mem_collections.clear()
    yield
    _mem_collections.clear()


class TestListCollections:
    """GET /collections endpoint."""

    def test_list_returns_empty(self):
        resp = client.get("/collections")
        assert resp.status_code == 200
        data = resp.json()
        assert "collections" in data
        assert "total" in data
        assert data["total"] == 0
        assert data["collections"] == []

    def test_list_with_category_filter(self):
        resp = client.get("/collections?category=pokemon")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # ------------------------------------------------------------------
    # The three tests that used to live here (in-memory listing, category
    # filtering, pagination) asserted a feature that was REMOVED, not one
    # that broke.
    #
    # list_collections now returns CollectionListResponse(collections=[],
    # total=0) unconditionally. Its docstring says why: the catalog-of-sets
    # aggregation it was designed for never landed, and the body previously
    # held ~70 lines of unreachable SQL against a `collections` table shape
    # that does not exist — removed so audit_router_sql_drift stopped
    # flagging 7 phantom columns. The in-memory fallback went with it.
    #
    # Populating _mem_collections and expecting total==2 therefore pins a
    # path that no longer exists. Rewritten 2026-07-27 to pin the stub
    # contract instead, so that when the aggregation ships these fail and
    # get restored deliberately rather than silently passing on an empty
    # list forever.
    # ------------------------------------------------------------------

    def test_list_returns_empty_even_with_in_memory_rows(self):
        """The in-memory path is gone; rows there must NOT leak into the API."""
        _mem_collections.append({
            "id": "col-1",
            "category": "pokemon",
            "collection_key": "base1",
            "display_name": "Base Set",
            "total_items": 102,
        })

        resp = client.get("/collections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["collections"] == []

    def test_list_is_stubbed_not_erroring(self):
        """A stub must answer 200 with an empty set, never 5xx.

        Clients render "no collections yet"; a 500 would show an error
        state for a feature that simply is not built.
        """
        for params in ("", "?category=pokemon", "?limit=2&offset=1"):
            resp = client.get(f"/collections{params}")
            assert resp.status_code == 200, params
            assert resp.json()["total"] == 0, params

    def test_list_still_validates_its_query_params(self):
        """Validation must survive the stub — limit is bounded 1..200."""
        assert client.get("/collections?limit=0").status_code == 422
        assert client.get("/collections?limit=201").status_code == 422
        assert client.get("/collections?offset=-1").status_code == 422


class TestUserProgress:
    """GET /collections/user/progress endpoint (in-memory fallback returns empty)."""

    def test_progress_returns_empty(self):
        # DEV_MODE: no auth header → dev-user-local
        resp = client.get("/collections/user/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert "progress" in data
        assert data["total_collections"] == 0
        assert data["total_owned"] == 0

    def test_progress_with_category(self):
        resp = client.get("/collections/user/progress?category=pokemon")
        assert resp.status_code == 200


class TestCollectionDetail:
    """GET /collections/{collection_id} endpoint."""

    def test_not_found(self):
        resp = client.get("/collections/00000000-0000-0000-0000-000000000099")
        assert resp.status_code == 404

    def test_detail_is_stubbed_even_for_a_known_id(self):
        """404 for every id, including one present in memory.

        Was `test_found_in_memory`, expecting the row back. get_collection_detail
        is a stub — "Get a specific collection — stub. Catalog-of-sets
        aggregation not built." — and raises 404 unconditionally after a UUID
        format check.

        Kept rather than deleted because this is the route that
        `collection_viewed` demand-signal instrumentation belongs on once the
        feature exists (see test_production_hardening
        ::test_collection_viewed_is_declared_but_deliberately_unwired). When
        this starts returning 200, both tests should be revisited together.
        """
        _mem_collections.append({
            "id": "00000000-0000-0000-0000-000000000001",
            "category": "pokemon",
            "collection_key": "base1",
            "display_name": "Base Set",
            "total_items": 102,
        })

        resp = client.get("/collections/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 404

    def test_detail_still_validates_uuid_format(self):
        """The format guard runs BEFORE the stub 404, and must keep doing so."""
        assert client.get("/collections/not-a-uuid").status_code == 400


class TestCollectionProgress:
    """GET /collections/{collection_id}/progress endpoint."""

    def test_not_found(self):
        resp = client.get("/collections/00000000-0000-0000-0000-000000000099/progress")
        assert resp.status_code == 404
