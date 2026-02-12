"""Tests for app/features/watchlist_router.py — watchlist CRUD endpoints.

All tests use the in-memory store (no DB needed).
"""
import os
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")

from starlette.testclient import TestClient
from main import app  # noqa: E402
from app.features.watchlist_router import _WATCHLIST

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_watchlist():
    """Clear the in-memory watchlist store before each test."""
    _WATCHLIST.clear()
    yield
    _WATCHLIST.clear()


def _add_item(**overrides):
    """Helper to add an item to the watchlist and return the response data."""
    payload = {
        "name": "Charizard Base Set Holo",
        "category": "pokemon",
        "item_id": "item-123",
        "predicted_value": 350.00,
        "currency": "EUR",
    }
    payload.update(overrides)
    r = client.post("/watchlist/mine", json=payload)
    return r


# ===========================================================================
# GET /watchlist/mine — List watchlist
# ===========================================================================

class TestGetWatchlist:
    def test_empty_watchlist(self):
        r = client.get("/watchlist/mine")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert data["items"] == []

    def test_watchlist_returns_added_items(self):
        _add_item()
        r = client.get("/watchlist/mine")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Charizard Base Set Holo"
        assert items[0]["category"] == "pokemon"

    def test_watchlist_returns_multiple_items(self):
        _add_item(name="Item 1")
        _add_item(name="Item 2")
        _add_item(name="Item 3")
        r = client.get("/watchlist/mine")
        items = r.json()["items"]
        assert len(items) == 3
        names = {it["name"] for it in items}
        assert names == {"Item 1", "Item 2", "Item 3"}

    def test_watchlist_item_has_expected_fields(self):
        _add_item()
        r = client.get("/watchlist/mine")
        item = r.json()["items"][0]
        assert "id" in item
        assert "user_id" in item
        assert item["user_id"] == "dev-user-local"
        assert "item_id" in item
        assert "name" in item
        assert "category" in item
        assert "created_at" in item
        assert "predicted_value" in item
        assert "currency" in item


# ===========================================================================
# POST /watchlist/mine — Add to watchlist
# ===========================================================================

class TestAddToWatchlist:
    def test_add_item_success(self):
        r = _add_item()
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Charizard Base Set Holo"
        assert data["category"] == "pokemon"
        assert data["user_id"] == "dev-user-local"
        assert data["item_id"] == "item-123"
        assert data["predicted_value"] == 350.00
        assert data["currency"] == "EUR"
        assert "id" in data

    def test_add_item_with_minimal_fields(self):
        r = client.post("/watchlist/mine", json={})
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == "dev-user-local"
        assert data["currency"] == "EUR"
        assert data["name"] is None
        assert data["category"] is None
        assert data["item_id"] is None
        assert data["predicted_value"] is None

    def test_add_item_custom_currency(self):
        r = _add_item(currency="USD")
        assert r.status_code == 200
        assert r.json()["currency"] == "USD"

    def test_add_item_generates_unique_id(self):
        r1 = _add_item(name="Item 1")
        r2 = _add_item(name="Item 2")
        assert r1.json()["id"] != r2.json()["id"]

    def test_add_item_stores_in_memory(self):
        _add_item()
        assert "dev-user-local" in _WATCHLIST
        assert len(_WATCHLIST["dev-user-local"]) == 1

    def test_add_item_with_zero_value(self):
        r = _add_item(predicted_value=0.0)
        assert r.status_code == 200
        assert r.json()["predicted_value"] == 0.0

    def test_add_item_with_large_value(self):
        r = _add_item(predicted_value=999999.99)
        assert r.status_code == 200
        assert r.json()["predicted_value"] == 999999.99

    def test_add_item_with_negative_value(self):
        """Negative predicted_value is technically allowed (no validation)."""
        r = _add_item(predicted_value=-10.0)
        assert r.status_code == 200
        assert r.json()["predicted_value"] == -10.0

    def test_add_multiple_items_same_category(self):
        _add_item(name="Card 1", category="pokemon")
        _add_item(name="Card 2", category="pokemon")
        r = client.get("/watchlist/mine")
        items = r.json()["items"]
        assert len(items) == 2
        assert all(it["category"] == "pokemon" for it in items)

    # ---- Validation / error cases ----

    def test_add_item_name_too_long_422(self):
        r = _add_item(name="A" * 256)
        assert r.status_code == 422

    def test_add_item_category_too_long_422(self):
        r = _add_item(category="x" * 65)
        assert r.status_code == 422

    def test_add_item_item_id_too_long_422(self):
        r = _add_item(item_id="x" * 65)
        assert r.status_code == 422

    def test_add_item_invalid_currency_format_422(self):
        r = _add_item(currency="euro")
        assert r.status_code == 422

    def test_add_item_currency_lowercase_422(self):
        r = _add_item(currency="eur")
        assert r.status_code == 422

    def test_add_item_currency_too_long_422(self):
        r = _add_item(currency="EURO")
        assert r.status_code == 422


# ===========================================================================
# DELETE /watchlist/mine/{watch_id} — Remove from watchlist
# ===========================================================================

class TestRemoveFromWatchlist:
    def test_remove_item_success(self):
        r = _add_item()
        watch_id = r.json()["id"]
        r = client.delete(f"/watchlist/mine/{watch_id}")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert len(data["items"]) == 0

    def test_remove_item_not_found_404(self):
        r = client.delete("/watchlist/mine/nonexistent-id")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_remove_item_from_multiple(self):
        r1 = _add_item(name="Item 1")
        r2 = _add_item(name="Item 2")
        r3 = _add_item(name="Item 3")
        watch_id = r2.json()["id"]

        r = client.delete(f"/watchlist/mine/{watch_id}")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 2
        remaining_names = {it["name"] for it in items}
        assert "Item 2" not in remaining_names
        assert "Item 1" in remaining_names
        assert "Item 3" in remaining_names

    def test_remove_same_item_twice_404(self):
        r = _add_item()
        watch_id = r.json()["id"]
        # First delete
        r = client.delete(f"/watchlist/mine/{watch_id}")
        assert r.status_code == 200
        # Second delete
        r = client.delete(f"/watchlist/mine/{watch_id}")
        assert r.status_code == 404

    def test_remove_item_updates_in_memory(self):
        r = _add_item()
        watch_id = r.json()["id"]
        assert len(_WATCHLIST["dev-user-local"]) == 1
        client.delete(f"/watchlist/mine/{watch_id}")
        assert len(_WATCHLIST["dev-user-local"]) == 0

    def test_remove_returns_remaining_items(self):
        """Delete response should include all remaining watchlist items."""
        _add_item(name="Keep Me")
        r2 = _add_item(name="Delete Me")
        watch_id = r2.json()["id"]
        r = client.delete(f"/watchlist/mine/{watch_id}")
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Keep Me"


# ===========================================================================
# Integration / end-to-end flows
# ===========================================================================

class TestWatchlistIntegration:
    def test_full_lifecycle(self):
        """Add -> list -> delete -> list -> verify empty."""
        # Add
        r = _add_item(name="Test Item")
        assert r.status_code == 200
        watch_id = r.json()["id"]

        # List
        r = client.get("/watchlist/mine")
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Test Item"

        # Delete
        r = client.delete(f"/watchlist/mine/{watch_id}")
        assert r.status_code == 200

        # List again
        r = client.get("/watchlist/mine")
        assert r.json()["items"] == []

    def test_add_many_delete_specific(self):
        """Add 5 items, delete the 3rd, verify the remaining 4."""
        ids = []
        for i in range(5):
            r = _add_item(name=f"Item {i}")
            ids.append(r.json()["id"])

        # Delete item at index 2
        r = client.delete(f"/watchlist/mine/{ids[2]}")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 4
        remaining_ids = {it["id"] for it in items}
        assert ids[2] not in remaining_ids
        for i in [0, 1, 3, 4]:
            assert ids[i] in remaining_ids

    def test_watchlist_preserves_all_fields(self):
        """Ensure all fields survive the add -> list round trip."""
        payload = {
            "name": "Pikachu VMAX",
            "category": "pokemon",
            "item_id": "pika-vmax-001",
            "predicted_value": 42.50,
            "currency": "EUR",
        }
        client.post("/watchlist/mine", json=payload)
        r = client.get("/watchlist/mine")
        item = r.json()["items"][0]
        assert item["name"] == "Pikachu VMAX"
        assert item["category"] == "pokemon"
        assert item["item_id"] == "pika-vmax-001"
        assert item["predicted_value"] == 42.50
        assert item["currency"] == "EUR"
        assert item["user_id"] == "dev-user-local"
