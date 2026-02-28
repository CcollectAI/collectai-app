"""Tests for app/agents/dossier_router.py -- dossier, summary, and HTML export endpoints.

All tests mock generate_dossier and db_configured to avoid real DB access.
DB_ENABLED=false and DEV_MODE=true so auth is bypassed and no real DB is needed.
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dossier(**overrides):
    """Create a mock ItemDossier instance."""
    from app.agents.dossier_agent import ItemDossier

    defaults = dict(
        item_id="abc-123-def",
        generated_at="2026-02-10T12:00:00+00:00",
        version="1.0",
        identity={
            "name": "Charizard Base Set Holo",
            "category": "pokemon",
            "condition": "Near Mint",
            "grade": "PSA 9",
            "sealed": False,
            "image_url": "https://example.com/charizard.jpg",
            "attributes": {"rarity": "Holo Rare", "set": "Base Set"},
        },
        valuation={
            "q10": 180.0,
            "q50": 250.0,
            "q90": 350.0,
            "confidence_score": 0.85,
            "explanation": "Based on 15 recent sold comps",
        },
        provenance=[
            {
                "event_type": "purchase",
                "timestamp": "2025-06-15T10:00:00+00:00",
                "source": "ebay",
                "note": "Bought from seller xyz",
            },
            {
                "event_type": "graded",
                "timestamp": "2025-08-01T14:00:00+00:00",
                "source": "PSA",
                "note": "Graded PSA 9",
            },
        ],
        price_history=[
            {
                "recorded_at": "2026-01-15T00:00:00+00:00",
                "price": 240.0,
                "currency": "EUR",
                "source": "market_hits",
            },
        ],
        market_comps=[
            {
                "title": "Charizard Base Set Holo PSA 9",
                "price": 260.0,
                "currency": "EUR",
                "source": "ebay",
                "sold_date": "2026-02-01",
                "condition": "Near Mint",
                "url": "https://ebay.com/itm/99999",
            },
        ],
        photos=["https://example.com/charizard.jpg"],
        collections=["Pokemon Gen 1"],
        authenticity_signals=["owner_verified", "professionally_graded"],
        completeness_score=0.75,
    )
    defaults.update(overrides)
    return ItemDossier(**defaults)


@asynccontextmanager
async def _mock_conn_ctx():
    """Async context manager that yields a MagicMock connection."""
    yield MagicMock()


# ===========================================================================
# GET /dossier/{item_id} -- Full dossier
# ===========================================================================

class TestGetDossier:
    """GET /dossier/{item_id} endpoint."""

    def test_dossier_happy_path(self):
        """Full dossier returns all sections with correct structure."""
        dossier = _make_dossier()
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def")

        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == "abc-123-def"
        assert data["generated_at"] == "2026-02-10T12:00:00+00:00"
        assert data["version"] == "1.0"

        # Identity section
        assert data["identity"]["name"] == "Charizard Base Set Holo"
        assert data["identity"]["category"] == "pokemon"
        assert data["identity"]["condition"] == "Near Mint"
        assert data["identity"]["grade"] == "PSA 9"

        # Valuation section
        assert data["valuation"]["q10"] == 180.0
        assert data["valuation"]["q50"] == 250.0
        assert data["valuation"]["q90"] == 350.0
        assert data["valuation"]["confidence_score"] == 0.85

        # Provenance
        assert len(data["provenance"]) == 2
        assert data["provenance"][0]["event_type"] == "purchase"
        assert data["provenance"][1]["event_type"] == "graded"

        # Price history
        assert len(data["price_history"]) == 1
        assert data["price_history"][0]["price"] == 240.0

        # Market comps
        assert len(data["market_comps"]) == 1
        assert data["market_comps"][0]["title"] == "Charizard Base Set Holo PSA 9"

        # Photos, collections, authenticity
        assert "https://example.com/charizard.jpg" in data["photos"]
        assert "Pokemon Gen 1" in data["collections"]
        assert "owner_verified" in data["authenticity_signals"]
        assert "professionally_graded" in data["authenticity_signals"]
        assert data["completeness_score"] == 0.75

    def test_dossier_item_not_found_404(self):
        """Non-existent item returns 404."""
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            side_effect=ValueError("Item not found"),
        ):
            resp = client.get("/dossier/nonexistent-item-id")

        assert resp.status_code == 404
        detail = resp.json()["detail"]
        msg = detail["message"] if isinstance(detail, dict) else detail
        assert "not found" in msg.lower()

    def test_dossier_db_not_configured_503(self):
        """When database is not configured, return 503."""
        with patch(
            "app.agents.dossier_router.db_configured", return_value=False
        ):
            resp = client.get("/dossier/abc-123-def")

        assert resp.status_code == 503
        detail = resp.json()["detail"]
        msg = detail["message"] if isinstance(detail, dict) else detail
        assert "database" in msg.lower() or "not available" in msg.lower()

    def test_dossier_generate_error_500(self):
        """Unexpected error during dossier generation returns 500."""
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB connection lost"),
        ):
            resp = client.get("/dossier/abc-123-def")

        assert resp.status_code == 500
        detail = resp.json()["detail"]
        msg = detail["message"] if isinstance(detail, dict) else detail
        assert "failed" in msg.lower()

    def test_dossier_minimal_sections(self):
        """Dossier with empty optional sections returns valid response."""
        dossier = _make_dossier(
            provenance=[],
            price_history=[],
            market_comps=[],
            photos=[],
            collections=[],
            authenticity_signals=[],
            completeness_score=0.1,
        )
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def")

        assert resp.status_code == 200
        data = resp.json()
        assert data["provenance"] == []
        assert data["price_history"] == []
        assert data["market_comps"] == []
        assert data["photos"] == []
        assert data["collections"] == []
        assert data["authenticity_signals"] == []
        assert data["completeness_score"] == 0.1

    def test_dossier_passes_user_id(self):
        """generate_dossier is called with the correct user_id."""
        dossier = _make_dossier()
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ) as mock_gen:
            client.get("/dossier/abc-123-def")

        call_args = mock_gen.call_args
        # generate_dossier(item_id, user_id, conn)
        assert call_args.args[0] == "abc-123-def"
        assert call_args.args[1] == "dev-user-local"


# ===========================================================================
# GET /dossier/{item_id}/summary
# ===========================================================================

class TestGetDossierSummary:
    """GET /dossier/{item_id}/summary endpoint."""

    def test_summary_happy_path(self):
        """Summary returns identity + valuation + completeness only."""
        dossier = _make_dossier()
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == "abc-123-def"
        assert data["generated_at"] == "2026-02-10T12:00:00+00:00"

        # Identity section
        assert data["identity"]["name"] == "Charizard Base Set Holo"
        assert data["identity"]["category"] == "pokemon"

        # Valuation section
        assert data["valuation"]["q50"] == 250.0

        # Completeness
        assert data["completeness_score"] == 0.75

        # Summary should NOT include full dossier sections
        assert "provenance" not in data
        assert "price_history" not in data
        assert "market_comps" not in data
        assert "photos" not in data
        assert "collections" not in data
        assert "authenticity_signals" not in data

    def test_summary_item_not_found_404(self):
        """Non-existent item returns 404 for summary."""
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            side_effect=ValueError("Item not found"),
        ):
            resp = client.get("/dossier/nonexistent-item-id/summary")

        assert resp.status_code == 404

    def test_summary_db_not_configured_503(self):
        """When database is not configured, summary returns 503."""
        with patch(
            "app.agents.dossier_router.db_configured", return_value=False
        ):
            resp = client.get("/dossier/abc-123-def/summary")

        assert resp.status_code == 503

    def test_summary_generate_error_500(self):
        """Unexpected error during summary generation returns 500."""
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Unexpected"),
        ):
            resp = client.get("/dossier/abc-123-def/summary")

        assert resp.status_code == 500


# ===========================================================================
# GET /dossier/{item_id}/export -- HTML export
# ===========================================================================

class TestExportDossierHtml:
    """GET /dossier/{item_id}/export endpoint."""

    def test_export_happy_path(self):
        """HTML export returns valid HTML with Content-Disposition header."""
        dossier = _make_dossier()
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def/export")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "content-disposition" in resp.headers
        assert "attachment" in resp.headers["content-disposition"]
        assert "dossier_" in resp.headers["content-disposition"]
        assert ".html" in resp.headers["content-disposition"]

        # Verify HTML content
        body = resp.text
        assert "<!DOCTYPE html>" in body
        assert "Charizard Base Set Holo" in body
        assert "CollectAI" in body

    def test_export_contains_valuation(self):
        """HTML export includes valuation data."""
        dossier = _make_dossier()
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def/export")

        body = resp.text
        assert "Valuation" in body
        # Price values should appear somewhere in the HTML
        assert "250" in body  # q50

    def test_export_contains_provenance(self):
        """HTML export includes provenance timeline."""
        dossier = _make_dossier()
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def/export")

        body = resp.text
        assert "Provenance" in body
        assert "Purchase" in body  # event_type "purchase" -> "Purchase"

    def test_export_contains_market_comps(self):
        """HTML export includes market comparables table."""
        dossier = _make_dossier()
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def/export")

        body = resp.text
        assert "Market Comparables" in body
        assert "Charizard Base Set Holo PSA 9" in body

    def test_export_contains_authenticity_signals(self):
        """HTML export includes authenticity signal badges."""
        dossier = _make_dossier()
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def/export")

        body = resp.text
        assert "Authenticity" in body
        assert "Owner Verified" in body
        assert "Professionally Graded" in body

    def test_export_contains_completeness_bar(self):
        """HTML export includes completeness percentage bar."""
        dossier = _make_dossier(completeness_score=0.75)
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def/export")

        body = resp.text
        assert "Completeness" in body
        assert "75%" in body

    def test_export_item_not_found_404(self):
        """Non-existent item returns 404 for HTML export."""
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            side_effect=ValueError("Item not found"),
        ):
            resp = client.get("/dossier/nonexistent-item-id/export")

        assert resp.status_code == 404

    def test_export_db_not_configured_503(self):
        """When database is not configured, export returns 503."""
        with patch(
            "app.agents.dossier_router.db_configured", return_value=False
        ):
            resp = client.get("/dossier/abc-123-def/export")

        assert resp.status_code == 503

    def test_export_generate_error_500(self):
        """Unexpected error during export returns 500."""
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Disk full"),
        ):
            resp = client.get("/dossier/abc-123-def/export")

        assert resp.status_code == 500

    def test_export_filename_sanitized(self):
        """HTML export filename strips special characters from item name."""
        dossier = _make_dossier(
            identity={
                "name": "Char!zard <Base> Set & Holo",
                "category": "pokemon",
                "condition": "NM",
            },
        )
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def/export")

        assert resp.status_code == 200
        cd = resp.headers["content-disposition"]
        # Filename should not contain < > & !
        assert "<" not in cd
        assert ">" not in cd
        assert "&" not in cd
        assert "!" not in cd

    def test_export_empty_provenance_no_crash(self):
        """Export with no provenance events still renders valid HTML."""
        dossier = _make_dossier(
            provenance=[],
            market_comps=[],
            authenticity_signals=[],
            collections=[],
        )
        with patch(
            "app.agents.dossier_router.db_configured", return_value=True
        ), patch(
            "app.agents.dossier_router.get_conn", side_effect=_mock_conn_ctx
        ), patch(
            "app.agents.dossier_router.generate_dossier",
            new_callable=AsyncMock,
            return_value=dossier,
        ):
            resp = client.get("/dossier/abc-123-def/export")

        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text
