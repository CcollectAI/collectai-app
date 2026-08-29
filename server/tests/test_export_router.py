"""
Tests for app/features/export_router.py — insurance valuation report export.

Covers:
  - GET /export/insurance-report?format=json  — no pool fallback, mocked DB happy path, DB error
  - GET /export/insurance-report?format=html  — no pool fallback, mocked DB happy path, HTML rendering
  - Currency validation (valid + invalid currencies)
  - Schema validation for InsuranceReportData and InsuranceItemRow
  - Edge cases: empty collection, items with null estimated values, XSS via fields
  - Invalid format parameter

All tests mock get_db_pool() so no real database is needed.
DEV_MODE=true provides automatic auth as "dev-user-local".
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("PER_USER_RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

MODULE = "app.features.export_router"

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_pool():
    """Create a mock pool with an async context manager for acquire()."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetchval = AsyncMock(return_value=None)

    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=mock_acquire)

    return pool, mock_conn


def _make_user_row(display_name="Test User", email="test@example.com"):
    return {"display_name": display_name, "email": email}


def _make_item_row(
    item_id="00000000-0000-0000-0000-000000000001",
    title="Charizard Holo 1st Edition",
    category="pokemon",
    condition="Near Mint",
    grade="PSA 9",
    image_url="https://example.com/img.webp",
    date_acquired=NOW,
    estimated_value=1500.0,
):
    return {
        "id": item_id,
        "title": title,
        "category": category,
        "condition": condition,
        "grade": grade,
        "image_url": image_url,
        "date_acquired": date_acquired,
        "estimated_value": estimated_value,
    }


# ---------------------------------------------------------------------------
# GET /export/insurance-report?format=json — no pool (DB_ENABLED=false)
# ---------------------------------------------------------------------------


class TestInsuranceReportJsonNoPool:
    """Tests for JSON format insurance report when get_db_pool returns None."""

    def test_returns_empty_report(self):
        resp = client.get("/export/insurance-report?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 0
        assert data["total_estimated_value"] == 0.0
        assert data["currency"] == "EUR"
        assert data["items"] == []
        assert "generated_at" in data

    def test_custom_currency_reflected(self):
        resp = client.get("/export/insurance-report?format=json&currency=USD")
        assert resp.status_code == 200
        assert resp.json()["currency"] == "USD"

    def test_methodology_placeholder(self):
        resp = client.get("/export/insurance-report?format=json")
        data = resp.json()
        assert "No database connection" in data["methodology"]

    def test_schema_fields_present(self):
        resp = client.get("/export/insurance-report?format=json")
        data = resp.json()
        for field in ["generated_at", "total_items", "total_estimated_value", "currency", "methodology", "items"]:
            assert field in data, f"Missing field: {field}"
        assert isinstance(data["items"], list)
        assert isinstance(data["total_items"], int)
        assert isinstance(data["total_estimated_value"], (int, float))


# ---------------------------------------------------------------------------
# GET /export/insurance-report?format=html — no pool
# ---------------------------------------------------------------------------


class TestInsuranceReportHtmlNoPool:
    """Tests for HTML format insurance report when no DB pool is available."""

    def test_returns_html(self):
        resp = client.get("/export/insurance-report?format=html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_html_contains_sparrow_branding(self):
        # Renamed from CollectAI on 2026-05-04. This asserted the OLD name and
        # had therefore been red ever since -- pinning a brand the rename
        # deliberately removed. The export does carry branding
        # (export_router.py:255 logo, :312 footer, :452 methodology); only the
        # name this test looked for had changed.
        resp = client.get("/export/insurance-report")
        assert resp.status_code == 200
        assert "Sparrow Collect" in resp.text
        assert "CollectAI" not in resp.text, "the pre-rename name must not resurface"

    def test_html_default_format(self):
        """Default format (no param) should be html."""
        resp = client.get("/export/insurance-report")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# Currency validation
# ---------------------------------------------------------------------------


class TestCurrencyValidation:
    """Tests for currency allowlist validation."""

    @pytest.mark.parametrize("currency", ["EUR", "USD", "GBP", "JPY", "KRW", "AUD", "CAD"])
    def test_valid_currencies_accepted(self, currency):
        resp = client.get(f"/export/insurance-report?format=json&currency={currency}")
        assert resp.status_code == 200
        assert resp.json()["currency"] == currency

    def test_invalid_currency_rejected(self):
        resp = client.get("/export/insurance-report?format=json&currency=BTC")
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data

    def test_invalid_currency_xss_attempt(self):
        """XSS attempt via currency param should be rejected by allowlist."""
        resp = client.get("/export/insurance-report?format=json&currency=<script>alert(1)</script>")
        assert resp.status_code == 400

    def test_empty_currency_rejected(self):
        """Empty string currency is not in the allowlist."""
        resp = client.get("/export/insurance-report?format=json&currency=")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Format validation
# ---------------------------------------------------------------------------


class TestFormatValidation:
    """Tests for the format query parameter."""

    def test_invalid_format_rejected(self):
        """Format must be 'html' or 'json'; anything else returns 422."""
        resp = client.get("/export/insurance-report?format=pdf")
        assert resp.status_code == 422

    def test_format_csv_rejected(self):
        resp = client.get("/export/insurance-report?format=csv")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /export/insurance-report?format=json — mocked DB
# ---------------------------------------------------------------------------


class TestInsuranceReportJsonMockedDB:
    """Tests for JSON format with mocked database."""

    @patch(f"{MODULE}.get_db_pool")
    def test_happy_path_with_items(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[
            _make_item_row(),
            _make_item_row(
                item_id="00000000-0000-0000-0000-000000000002",
                title="LEGO Millennium Falcon",
                category="lego",
                condition="New",
                grade="N/A",
                estimated_value=800.0,
                date_acquired=datetime(2025, 6, 15, tzinfo=timezone.utc),
            ),
        ])

        resp = client.get("/export/insurance-report?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 2
        assert data["total_estimated_value"] == 2300.0
        assert data["user_name"] == "Test User"
        assert data["user_email"] == "test@example.com"
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == "Charizard Holo 1st Edition"
        assert data["items"][1]["name"] == "LEGO Millennium Falcon"
        assert "ridge regression" in data["methodology"].lower() or "pricing algorithm" in data["methodology"].lower()

    @patch(f"{MODULE}.get_db_pool")
    def test_item_with_null_value(self, mock_get_pool):
        """Items with None estimated_value should still appear; total should exclude them."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[
            _make_item_row(estimated_value=100.0),
            _make_item_row(
                item_id="00000000-0000-0000-0000-000000000099",
                title="Mystery Item",
                estimated_value=None,
            ),
        ])

        resp = client.get("/export/insurance-report?format=json")
        data = resp.json()
        assert data["total_items"] == 2
        assert data["total_estimated_value"] == 100.0
        assert data["items"][1]["estimated_value"] is None

    @patch(f"{MODULE}.get_db_pool")
    def test_empty_collection(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[])

        resp = client.get("/export/insurance-report?format=json")
        data = resp.json()
        assert data["total_items"] == 0
        assert data["total_estimated_value"] == 0.0
        assert data["items"] == []

    @patch(f"{MODULE}.get_db_pool")
    def test_user_not_found(self, mock_get_pool):
        """When user row is not found, user_email and user_name should be None."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetch = AsyncMock(return_value=[
            _make_item_row(),
        ])

        resp = client.get("/export/insurance-report?format=json")
        data = resp.json()
        assert data["user_email"] is None
        assert data["user_name"] is None
        assert data["total_items"] == 1

    @patch(f"{MODULE}.get_db_pool")
    def test_db_error_returns_500(self, mock_get_pool):
        """When DB query fails, endpoint returns 500."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(side_effect=Exception("Connection lost"))

        resp = client.get("/export/insurance-report?format=json")
        assert resp.status_code == 500

    @patch(f"{MODULE}.get_db_pool")
    def test_item_row_schema(self, mock_get_pool):
        """Each item in the response should have all InsuranceItemRow fields."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[_make_item_row()])

        resp = client.get("/export/insurance-report?format=json")
        item = resp.json()["items"][0]
        for field in ["id", "name", "category", "condition", "grade", "estimated_value", "currency"]:
            assert field in item, f"Missing field: {field}"
        assert isinstance(item["estimated_value"], (int, float))
        assert isinstance(item["name"], str)

    @patch(f"{MODULE}.get_db_pool")
    def test_item_date_formatted(self, mock_get_pool):
        """date_acquired should be formatted as YYYY-MM-DD string."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[_make_item_row(date_acquired=NOW)])

        resp = client.get("/export/insurance-report?format=json")
        item = resp.json()["items"][0]
        assert item["date_acquired"] == "2026-03-01"

    @patch(f"{MODULE}.get_db_pool")
    def test_item_no_date_acquired(self, mock_get_pool):
        """When date_acquired is None, it should appear as None in the response."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[_make_item_row(date_acquired=None)])

        resp = client.get("/export/insurance-report?format=json")
        item = resp.json()["items"][0]
        assert item["date_acquired"] is None

    @patch(f"{MODULE}.get_db_pool")
    def test_custom_currency_in_items(self, mock_get_pool):
        """Currency parameter should be reflected in each item row."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[_make_item_row()])

        resp = client.get("/export/insurance-report?format=json&currency=GBP")
        data = resp.json()
        assert data["currency"] == "GBP"
        assert data["items"][0]["currency"] == "GBP"


# ---------------------------------------------------------------------------
# GET /export/insurance-report?format=html — mocked DB
# ---------------------------------------------------------------------------


class TestInsuranceReportHtmlMockedDB:
    """Tests for HTML format with mocked database."""

    @patch(f"{MODULE}.get_db_pool")
    def test_html_contains_item_names(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[
            _make_item_row(title="Charizard Holo"),
        ])

        resp = client.get("/export/insurance-report?format=html")
        assert resp.status_code == 200
        assert "Charizard Holo" in resp.text

    @patch(f"{MODULE}.get_db_pool")
    def test_html_contains_total_value(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[
            _make_item_row(estimated_value=1500.0),
        ])

        resp = client.get("/export/insurance-report?format=html&currency=EUR")
        assert resp.status_code == 200
        assert "1,500.00" in resp.text

    @patch(f"{MODULE}.get_db_pool")
    def test_html_escapes_special_chars(self, mock_get_pool):
        """HTML output should escape special characters to prevent XSS."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row(display_name="<script>alert(1)</script>"))
        conn.fetch = AsyncMock(return_value=[
            _make_item_row(title='Item "with" <tags>'),
        ])

        resp = client.get("/export/insurance-report?format=html")
        assert resp.status_code == 200
        assert "<script>" not in resp.text
        assert "&lt;script&gt;" in resp.text
        assert "&lt;tags&gt;" in resp.text

    @patch(f"{MODULE}.get_db_pool")
    def test_html_contains_user_name(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row(display_name="Alice Collector"))
        conn.fetch = AsyncMock(return_value=[])

        resp = client.get("/export/insurance-report?format=html")
        assert resp.status_code == 200
        assert "Alice Collector" in resp.text

    @patch(f"{MODULE}.get_db_pool")
    def test_html_has_print_button(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[])

        resp = client.get("/export/insurance-report?format=html")
        assert "window.print()" in resp.text

    @patch(f"{MODULE}.get_db_pool")
    def test_html_methodology_section(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[_make_item_row()])

        resp = client.get("/export/insurance-report?format=html")
        assert "Methodology" in resp.text
        assert "ridge regression" in resp.text.lower() or "pricing algorithm" in resp.text.lower()

    @patch(f"{MODULE}.get_db_pool")
    def test_html_image_url_rendered(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[
            _make_item_row(image_url="https://example.com/pic.webp"),
        ])

        resp = client.get("/export/insurance-report?format=html")
        assert "https://example.com/pic.webp" in resp.text

    @patch(f"{MODULE}.get_db_pool")
    def test_html_no_image_shows_placeholder(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetchrow = AsyncMock(return_value=_make_user_row())
        conn.fetch = AsyncMock(return_value=[
            _make_item_row(image_url=None),
        ])

        resp = client.get("/export/insurance-report?format=html")
        assert "N/A" in resp.text
