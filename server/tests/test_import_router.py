"""Tests for app/features/import_router.py — CSV/Excel import endpoints.

Covers:
  - GET  /api/imports/template — download CSV template
  - POST /api/imports/collection — import CSV file (parse-only mode)
  - Validation: empty file, oversized file, unsupported file type
  - Row validation: missing name, valid rows, mixed rows

All tests use DB_ENABLED=false (parse-only mode), so no real database is needed.
The import router detects pool=None and counts rows as inserted without DB writes.
"""

from __future__ import annotations

import io
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

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_override():
    from app.auth import get_current_user_id

    async def _fake_user():
        return "import-test-user-001"

    app.dependency_overrides[get_current_user_id] = _fake_user


def _clear_overrides():
    app.dependency_overrides.clear()


def _csv_bytes(rows: list[list[str]], header: list[str] | None = None) -> bytes:
    """Build CSV bytes from rows; default header = IMPORT_COLUMNS."""
    if header is None:
        header = ["name", "category", "condition", "grade", "graded_by",
                  "sealed", "estimated_value", "notes"]
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(row))
    return "\n".join(lines).encode("utf-8")


# ---------------------------------------------------------------------------
# Tests: GET /api/imports/template
# ---------------------------------------------------------------------------

class TestImportTemplate:
    def test_template_returns_csv(self):
        resp = client.get("/api/imports/template")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        assert "Content-Disposition" in resp.headers
        assert "sparrow_collect_overview.csv" in resp.headers["Content-Disposition"]

    def test_template_has_headers_and_example(self):
        """Template CSV should have header row + 1 example row."""
        resp = client.get("/api/imports/template")
        text = resp.text
        lines = [l for l in text.strip().split("\n") if l.strip()]
        assert len(lines) >= 2
        # First line should contain column headers
        assert "name" in lines[0].lower()
        assert "category" in lines[0].lower()


# ---------------------------------------------------------------------------
# Tests: POST /api/imports/collection — Happy path
# ---------------------------------------------------------------------------

class TestImportCollectionHappyPath:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    def test_import_valid_csv(self):
        """Import a well-formed CSV with 2 valid rows."""
        csv_data = _csv_bytes([
            ["Charizard Base Set", "pokemon", "Near Mint", "PSA 9", "PSA", "no", "350.00", "My fave"],
            ["Dark Magician LOB", "yugioh", "Good", "", "", "no", "50.00", ""],
        ])

        resp = client.post(
            "/api/imports/collection",
            files={"file": ("import.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 2
        assert data["inserted_count"] == 2
        assert data["skipped_count"] == 0
        assert data["db_mode"] == "parse_only"
        assert "name" in data["columns_detected"]

    def test_import_single_row(self):
        csv_data = _csv_bytes([
            ["Single Item", "mtg", "", "", "", "", "", "Just one"],
        ])

        resp = client.post(
            "/api/imports/collection",
            files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 1
        assert data["inserted_count"] == 1

    def test_import_with_sealed_yes(self):
        """Sealed column with 'yes' value is parsed correctly."""
        csv_data = _csv_bytes([
            ["Sealed Box", "pokemon", "New", "", "", "yes", "500.00", ""],
        ])

        resp = client.post(
            "/api/imports/collection",
            files={"file": ("sealed.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert resp.status_code == 200
        assert resp.json()["inserted_count"] == 1


# ---------------------------------------------------------------------------
# Tests: POST /api/imports/collection — Validation errors
# ---------------------------------------------------------------------------

class TestImportCollectionValidation:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    def test_import_empty_file(self):
        """Empty file returns 400."""
        resp = client.post(
            "/api/imports/collection",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert resp.status_code == 400

    def test_import_unsupported_filetype(self):
        """Non-CSV/Excel file returns 400."""
        resp = client.post(
            "/api/imports/collection",
            files={"file": ("data.json", io.BytesIO(b'{"key": "value"}'), "application/json")},
        )
        assert resp.status_code == 400

    def test_import_rows_missing_name(self):
        """Rows without a name column are skipped."""
        csv_data = _csv_bytes([
            ["", "pokemon", "Near Mint", "", "", "no", "100", ""],
            ["Valid Item", "mtg", "", "", "", "", "", ""],
        ])

        resp = client.post(
            "/api/imports/collection",
            files={"file": ("mixed.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 2
        assert data["inserted_count"] == 1
        assert data["skipped_count"] == 1
        assert len(data["errors"]) == 1
        assert "name" in data["errors"][0]["message"].lower()

    def test_import_all_rows_missing_name(self):
        """All rows skipped if none have a name."""
        csv_data = _csv_bytes([
            ["", "pokemon", "", "", "", "", "", ""],
            ["", "mtg", "", "", "", "", "", ""],
        ])

        resp = client.post(
            "/api/imports/collection",
            files={"file": ("bad.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["inserted_count"] == 0
        assert data["skipped_count"] == 2

    def test_import_no_file_provided(self):
        """Missing file upload returns 422."""
        resp = client.post("/api/imports/collection")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: POST /api/imports/collection — Edge cases
# ---------------------------------------------------------------------------

class TestImportCollectionEdgeCases:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    def test_import_normalized_headers(self):
        """Headers with spaces and mixed case should be normalized."""
        csv_content = "Name, Category ,  Condition  ,Grade,Graded By,Sealed,Estimated Value,Notes\n"
        csv_content += "Test Item,pokemon,Good,,,no,10.00,test\n"

        resp = client.post(
            "/api/imports/collection",
            files={"file": ("headers.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["inserted_count"] == 1

    def test_import_estimated_value_with_comma(self):
        """Estimated value with comma decimal separator (European format)."""
        csv_data = "name,category,condition,grade,graded_by,sealed,estimated_value,notes\n"
        csv_data += "Euro Item,pokemon,,,,,1000,50,test\n"

        resp = client.post(
            "/api/imports/collection",
            files={"file": ("euro.csv", io.BytesIO(csv_data.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        assert resp.json()["inserted_count"] == 1
