"""Tests for app/features/items_export_router.py — items export endpoint.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
The export router returns a header-only CSV when no DB pool is available.
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
# GET /items-export/overview — export items as CSV
# ---------------------------------------------------------------------------

class TestItemsExportOverview:
    def test_export_returns_200(self):
        """Returns 200 in offline mode."""
        resp = client.get("/items-export/overview")
        assert resp.status_code == 200

    def test_export_returns_csv_inline(self):
        """Response contains csv_inline field with header row."""
        resp = client.get("/items-export/overview")
        data = resp.json()
        assert "csv_inline" in data
        assert "id,title,category,condition,grade,estimated_value,currency" in data["csv_inline"]

    def test_export_download_url_is_none(self):
        """Download URL is None in offline mode (no S3)."""
        resp = client.get("/items-export/overview")
        data = resp.json()
        assert data["download_url"] is None

    def test_export_csv_has_header_columns(self):
        """CSV header contains all expected columns."""
        resp = client.get("/items-export/overview")
        data = resp.json()
        header_line = data["csv_inline"].strip().split("\n")[0]
        expected_cols = ["id", "title", "category", "condition", "grade", "estimated_value", "currency"]
        for col in expected_cols:
            assert col in header_line

    def test_export_response_model(self):
        """Response matches ItemsExportResponse schema."""
        resp = client.get("/items-export/overview")
        data = resp.json()
        assert "csv_inline" in data
        assert "download_url" in data
        assert isinstance(data["csv_inline"], str)
