"""Tests for POST /intake/save endpoint."""

import os
import pytest
from fastapi.testclient import TestClient

# Force DB-disabled mode for tests
os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DB_DSN", "")
os.environ.setdefault("DEV_MODE", "true")

from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


class TestIntakeSave:
    """POST /intake/save."""

    def test_save_returns_created_item(self):
        resp = client.post("/intake/save", json={
            "title": "Charizard Base Set Holo",
            "category": "pokemon",
            "condition": "Near Mint",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Charizard Base Set Holo"
        assert data["category"] == "pokemon"
        assert data["created"] is True
        assert "id" in data
        # UUID should be a valid format
        assert len(data["id"]) == 36

    def test_save_minimal_payload(self):
        resp = client.post("/intake/save", json={
            "title": "Unknown Item",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Unknown Item"
        assert data["created"] is True

    def test_save_with_full_payload(self):
        resp = client.post("/intake/save", json={
            "title": "Yu-Gi-Oh! Blue-Eyes White Dragon",
            "category": "yugioh",
            "condition": "Mint",
            "subtype_id": "LOB-001",
            "taxonomy_version": "v1.0",
            "attributes": {"rarity": "Ultra Rare", "set": "Legend of Blue Eyes"},
            "images": ["https://example.com/bewd.jpg"],
            "barcode": "4012927843123",
            "estimated_price": 150.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Yu-Gi-Oh! Blue-Eyes White Dragon"
        assert data["category"] == "yugioh"

    def test_save_rejects_empty_title(self):
        resp = client.post("/intake/save", json={
            "title": "",
        })
        assert resp.status_code == 422  # Validation error

    def test_save_rejects_missing_title(self):
        resp = client.post("/intake/save", json={
            "category": "pokemon",
        })
        assert resp.status_code == 422
