"""Tests for app/features/search_router.py — unified search endpoint.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
The search router returns category matches (static) and empty lists for DB-backed
entities when no DB pool is available.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")

from starlette.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# GET /search/unified — unified search
# ---------------------------------------------------------------------------

class TestUnifiedSearch:
    def test_search_returns_200(self):
        """Returns 200 for a valid search query."""
        resp = client.get("/search/unified", params={"q": "pokemon"})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "catalog" in data
        assert "users" in data
        assert "events" in data
        assert "categories" in data

    def test_search_empty_query(self):
        """Empty query returns all empty lists."""
        resp = client.get("/search/unified", params={"q": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["catalog"] == []
        assert data["users"] == []
        assert data["events"] == []
        assert data["categories"] == []

    def test_search_no_query_param(self):
        """Missing query defaults to empty string, returns empty lists."""
        resp = client.get("/search/unified")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["catalog"] == []
        assert data["categories"] == []

    def test_search_category_match(self):
        """Search matches category names from static list."""
        resp = client.get("/search/unified", params={"q": "pokemon"})
        data = resp.json()
        assert len(data["categories"]) > 0
        assert any("pokemon" in c["id"].lower() or "pokemon" in c["name"].lower()
                    for c in data["categories"])

    def test_search_category_match_case_insensitive(self):
        """Category search is case-insensitive."""
        resp = client.get("/search/unified", params={"q": "LEGO"})
        data = resp.json()
        assert len(data["categories"]) > 0
        assert any(c["id"] == "lego" for c in data["categories"])

    def test_search_no_db_returns_empty_items_users_events(self):
        """Without DB pool, items/catalog/users/events are empty, only categories match."""
        resp = client.get("/search/unified", params={"q": "funko"})
        data = resp.json()
        assert data["items"] == []
        assert data["catalog"] == []
        assert data["users"] == []
        assert data["events"] == []
        assert len(data["categories"]) > 0

    def test_search_with_custom_limit(self):
        """Accepts custom limit parameter."""
        resp = client.get("/search/unified", params={"q": "a", "limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["categories"]) <= 2

    def test_search_no_match(self):
        """Query with no matching category returns empty categories list."""
        resp = client.get("/search/unified", params={"q": "zzzzzzzznonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["categories"] == []


class _RecordingConn:
    def __init__(self):
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return []


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self_inner):
                return conn

            async def __aexit__(self_inner, *a):
                return False
        return _Ctx()


def _search(q, monkeypatch):
    from app.features import search_router
    conn = _RecordingConn()
    monkeypatch.setattr(search_router, "get_db_pool", lambda: _Pool(conn))
    resp = client.get("/search/unified", params={"q": q, "limit": 8})
    assert resp.status_code == 200
    return conn.calls


class TestSearchSqlShape:
    """2026-10-15: search_key matching, the event display gate, the "&&" guard."""

    def test_catalogue_and_items_match_on_search_key_with_raw_words(self, monkeypatch):
        calls = _search("1989 taylors version", monkeypatch)
        cat = next(c for c in calls if "FROM category_items" in c[0])
        assert "public.search_key(c.title || ' ' || c.category)" in cat[0]
        assert "LIMIT 200" in cat[0]   # bounded candidates (985 ms -> 15 ms)
        assert cat[1][0] == ["1989", "taylors", "version"]   # raw words; SQL normalises
        assert cat[1][3:] == ("1989", "taylors", "version")   # one indexed LIKE per word
        assert cat[1][2] is True                              # has_text
        items = next(c for c in calls if "FROM items" in c[0])
        assert "public.search_key(name" in items[0]

    def test_a_query_without_letters_or_digits_matches_nothing(self, monkeypatch):
        calls = _search("&&", monkeypatch)
        cat = next(c for c in calls if "FROM category_items" in c[0])
        assert cat[1][2] is False   # LIKE ALL over an empty set would be TRUE

    def test_events_use_the_feed_gate(self, monkeypatch):
        calls = _search("pokemon", monkeypatch)
        ev = next(c for c in calls if "FROM events" in c[0])
        assert "status = 'published'" in ev[0]
        assert "date >= CURRENT_DATE" in ev[0]
        assert "quality_score" in ev[0] and "NOT IN" in ev[0]   # display_gate_sql()
