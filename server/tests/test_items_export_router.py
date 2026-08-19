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
        """Response contains csv_inline, headed by the round-trip schema.

        The old literal here — `id,title,category,…` — has not been the
        header since at least 2026-04-29. `/overview` is the ROUND-TRIP
        export: 12 columns keyed on `name`, with no `id` and no `title`,
        because it exists to be edited in Excel and re-imported. Asserting the
        constant rather than a copy of it is the point; a hand-typed header in
        a test is a second source of truth that goes stale silently.
        """
        from app.features.items_export_router import EXPORT_COLUMNS

        resp = client.get("/items-export/overview")
        data = resp.json()
        assert "csv_inline" in data
        assert data["csv_inline"].startswith(",".join(EXPORT_COLUMNS))

    def test_export_download_url_is_none(self):
        """Download URL is None in offline mode (no S3)."""
        resp = client.get("/items-export/overview")
        data = resp.json()
        assert data["download_url"] is None

    def test_overview_header_is_exactly_the_import_schema(self):
        """The invariant the export exists for: export → edit → re-import.

        `EXPORT_COLUMNS` and `IMPORT_COLUMNS` are two lists in two files kept
        in step by a COMMENT ("must match IMPORT_COLUMNS in import_router.py").
        Nothing enforced it, so a column added to one side would silently make
        every exported file un-importable — the drift is invisible until a
        user's re-import drops their data.

        Order matters as well as membership: a CSV is positional, and import
        reads by header, so a reordering that keeps the same names is still a
        contract change worth seeing.
        """
        from app.features.import_router import IMPORT_COLUMNS
        from app.features.items_export_router import EXPORT_COLUMNS

        assert EXPORT_COLUMNS == IMPORT_COLUMNS

        resp = client.get("/items-export/overview")
        header_line = resp.json()["csv_inline"].strip().split("\n")[0]
        assert header_line.split(",") == IMPORT_COLUMNS

    def test_export_response_model(self):
        """Response matches ItemsExportResponse schema."""
        resp = client.get("/items-export/overview")
        data = resp.json()
        assert "csv_inline" in data
        assert "download_url" in data
        assert isinstance(data["csv_inline"], str)
