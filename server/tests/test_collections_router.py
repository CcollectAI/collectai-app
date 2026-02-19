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

    def test_list_with_in_memory_data(self):
        _mem_collections.append({
            "id": "col-1",
            "category": "pokemon",
            "collection_key": "base1",
            "display_name": "Base Set",
            "release_date": "1999-01-09",
            "total_items": 102,
            "image_url": "https://example.com/logo.png",
            "notes": "Base series",
        })
        _mem_collections.append({
            "id": "col-2",
            "category": "mtg",
            "collection_key": "alpha",
            "display_name": "Alpha",
            "release_date": "1993-08-05",
            "total_items": 295,
            "image_url": None,
            "notes": "First MTG set",
        })

        resp = client.get("/collections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["collections"]) == 2

    def test_list_filters_by_category(self):
        _mem_collections.append({
            "id": "col-1",
            "category": "pokemon",
            "collection_key": "base1",
            "display_name": "Base Set",
            "total_items": 102,
        })
        _mem_collections.append({
            "id": "col-2",
            "category": "mtg",
            "collection_key": "alpha",
            "display_name": "Alpha",
            "total_items": 295,
        })

        resp = client.get("/collections?category=pokemon")
        data = resp.json()
        assert data["total"] == 1
        assert data["collections"][0]["collection_key"] == "base1"

    def test_list_pagination(self):
        for i in range(5):
            _mem_collections.append({
                "id": f"col-{i}",
                "category": "pokemon",
                "collection_key": f"set-{i}",
                "display_name": f"Set {i}",
                "total_items": 10,
            })

        resp = client.get("/collections?limit=2&offset=1")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["collections"]) == 2
        assert data["collections"][0]["collection_key"] == "set-1"


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
        resp = client.get("/collections/nonexistent-id")
        assert resp.status_code == 404

    def test_found_in_memory(self):
        _mem_collections.append({
            "id": "col-123",
            "category": "pokemon",
            "collection_key": "base1",
            "display_name": "Base Set",
            "release_date": "1999-01-09",
            "total_items": 102,
            "image_url": "https://example.com/logo.png",
            "notes": "Base series",
        })

        resp = client.get("/collections/col-123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "Base Set"
        assert data["total_items"] == 102
        assert data["items"] == []  # No items in memory fallback


class TestCollectionProgress:
    """GET /collections/{collection_id}/progress endpoint."""

    def test_not_found(self):
        resp = client.get("/collections/nonexistent-id/progress")
        assert resp.status_code == 404
