"""Tests for the admin dashboard router."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    os.environ.setdefault("DEV_MODE", "true")
    os.environ.setdefault("DB_ENABLED", "false")
    from main import app
    return TestClient(app, raise_server_exceptions=False)


class TestDashboardPage:
    """GET /ops/dashboard."""

    def test_returns_html(self, client):
        resp = client.get("/ops/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "CollectAI Admin" in resp.text

    def test_contains_stats_grid(self, client):
        resp = client.get("/ops/dashboard")
        assert "stats-grid" in resp.text
        assert "users-table" in resp.text


class TestDashboardStats:
    """GET /ops/dashboard/stats."""

    def test_returns_json(self, client):
        resp = client.get("/ops/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "dev_mode" in data
        assert "db_enabled" in data
        assert "timestamp" in data

    def test_db_disconnected(self, client):
        resp = client.get("/ops/dashboard/stats")
        data = resp.json()
        assert data["db_status"] == "disconnected"


class TestDashboardUsers:
    """GET /ops/dashboard/users."""

    def test_empty_when_no_db(self, client):
        resp = client.get("/ops/dashboard/users")
        assert resp.status_code == 200
        data = resp.json()
        assert data["users"] == []
        assert data["total"] == 0

    def test_pagination_params(self, client):
        resp = client.get("/ops/dashboard/users?page=2&per_page=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
