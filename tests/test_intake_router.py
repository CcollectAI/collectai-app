"""Tests for app/agents/intake_router.py -- intake process, barcode-only, URL import, and save.

All tests mock the IntakeAgent functions (process_intake, process_url_import)
to avoid real barcode lookups, vision classification, or URL scraping.
DB_ENABLED=false and DEV_MODE=true so auth is bypassed and no real DB is needed.
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

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

def _make_intake_result(**overrides):
    """Create a mock IntakeResult dataclass instance."""
    from app.agents.intake_agent import IntakeResult

    defaults = dict(
        name="Charizard Base Set Holo",
        category_id="pokemon",
        category_confidence=0.92,
        subtype_id="base-set-holo",
        attributes={"rarity": "Holo Rare", "set": "Base Set"},
        identification_method="barcode",
        barcode="4012927843123",
        barcode_type="EAN-13",
        taxonomy_version="v1.0",
        taxonomy_confidence=0.88,
        suggested_corrections=[],
        estimated_price=250.0,
        price_source="market_hits",
        price_band={
            "q10": 180.0,
            "q50": 250.0,
            "q90": 350.0,
            "confidence": 0.85,
            "currency": "EUR",
        },
        image_url="https://example.com/charizard.jpg",
        rationale=["Barcode matched in catalog", "Taxonomy resolved via registry"],
    )
    defaults.update(overrides)
    return IntakeResult(**defaults)


def _png_magic_bytes():
    """Return minimal bytes that pass the PNG magic-byte check."""
    # PNG header (8 bytes) + enough padding to pass the 4-byte minimum
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _jpeg_magic_bytes():
    """Return minimal bytes that pass the JPEG magic-byte check."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


# ===========================================================================
# POST /intake/barcode-only
# ===========================================================================

class TestIntakeBarcodeOnly:
    """POST /intake/barcode-only endpoint."""

    def test_barcode_only_happy_path(self):
        """Barcode-only intake returns structured result."""
        mock_result = _make_intake_result()
        with patch(
            "app.agents.intake_router.process_intake",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post("/intake/barcode-only", json={
                "barcode": "4012927843123",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Charizard Base Set Holo"
        assert data["category_id"] == "pokemon"
        assert data["barcode"] == "4012927843123"
        assert data["barcode_type"] == "EAN-13"
        assert data["identification_method"] == "barcode"
        assert data["taxonomy_version"] == "v1.0"
        assert isinstance(data["category_confidence"], float)
        assert isinstance(data["taxonomy_confidence"], float)

    def test_barcode_only_with_hints(self):
        """Barcode-only with category/name/condition hints."""
        mock_result = _make_intake_result(
            category_id="yugioh",
            name="Blue-Eyes White Dragon",
        )
        with patch(
            "app.agents.intake_router.process_intake",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_fn:
            resp = client.post("/intake/barcode-only", json={
                "barcode": "4012927843999",
                "barcode_type": "EAN-13",
                "category": "yugioh",
                "name": "Blue-Eyes White Dragon",
                "condition": "Mint",
            })

        assert resp.status_code == 200
        # Verify user_hints were passed
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["barcode"] == "4012927843999"
        assert call_kwargs["barcode_type"] == "EAN-13"
        hints = call_kwargs.get("user_hints", {})
        assert hints["category"] == "yugioh"
        assert hints["name"] == "Blue-Eyes White Dragon"
        assert hints["condition"] == "Mint"

    def test_barcode_only_with_price_band(self):
        """Barcode-only returns price band when available."""
        mock_result = _make_intake_result()
        with patch(
            "app.agents.intake_router.process_intake",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post("/intake/barcode-only", json={
                "barcode": "4012927843123",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["price_band"] is not None
        assert data["price_band"]["q10"] == 180.0
        assert data["price_band"]["q50"] == 250.0
        assert data["price_band"]["q90"] == 350.0
        assert data["price_band"]["confidence"] == 0.85
        assert data["price_band"]["currency"] == "EUR"
        assert data["estimated_price"] == 250.0
        assert data["price_source"] == "market_hits"

    def test_barcode_only_missing_barcode_422(self):
        """Missing barcode should be rejected."""
        resp = client.post("/intake/barcode-only", json={})
        assert resp.status_code == 422

    def test_barcode_only_empty_barcode_422(self):
        """Empty barcode should be rejected by min_length=1."""
        resp = client.post("/intake/barcode-only", json={
            "barcode": "",
        })
        assert resp.status_code == 422

    def test_barcode_only_barcode_too_long_422(self):
        """Barcode longer than 50 chars should be rejected."""
        resp = client.post("/intake/barcode-only", json={
            "barcode": "A" * 51,
        })
        assert resp.status_code == 422

    def test_barcode_only_no_price_band(self):
        """Result without price band has null price_band field."""
        mock_result = _make_intake_result(
            price_band=None,
            estimated_price=None,
            price_source=None,
        )
        with patch(
            "app.agents.intake_router.process_intake",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post("/intake/barcode-only", json={
                "barcode": "9999999999999",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["price_band"] is None
        assert data["estimated_price"] is None

    def test_barcode_only_rationale_returned(self):
        """Rationale trail is included in the response."""
        mock_result = _make_intake_result(
            rationale=["Barcode matched in catalog", "Price from market_hits"],
        )
        with patch(
            "app.agents.intake_router.process_intake",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post("/intake/barcode-only", json={
                "barcode": "4012927843123",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rationale"]) == 2
        assert "Barcode matched in catalog" in data["rationale"]

    def test_barcode_only_suggested_corrections(self):
        """Suggested corrections are included in the response."""
        mock_result = _make_intake_result(
            suggested_corrections=[
                {
                    "from_category": "pokemon",
                    "to_category": "yugioh",
                    "frequency": 12,
                    "user_count": 5,
                },
            ],
        )
        with patch(
            "app.agents.intake_router.process_intake",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post("/intake/barcode-only", json={
                "barcode": "4012927843123",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["suggested_corrections"]) == 1
        assert data["suggested_corrections"][0]["from_category"] == "pokemon"
        assert data["suggested_corrections"][0]["to_category"] == "yugioh"


# ===========================================================================
# POST /intake/url
# ===========================================================================

class TestIntakeUrl:
    """POST /intake/url endpoint."""

    def test_url_import_happy_path(self):
        """URL import returns structured result for a valid eBay URL."""
        mock_result = _make_intake_result(
            identification_method="url_import",
            barcode=None,
            barcode_type=None,
        )
        with patch(
            "app.agents.intake_router.process_url_import",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "app.agents.intake_router.validate_url",
            return_value="https://www.ebay.com/itm/12345",
        ):
            resp = client.post("/intake/url", json={
                "url": "https://www.ebay.com/itm/12345",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Charizard Base Set Holo"
        assert data["identification_method"] == "url_import"

    def test_url_import_with_hints(self):
        """URL import with user hints passes them to the agent."""
        mock_result = _make_intake_result(identification_method="url_import")
        with patch(
            "app.agents.intake_router.process_url_import",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_fn, patch(
            "app.agents.intake_router.validate_url",
            return_value="https://www.ebay.com/itm/12345",
        ):
            resp = client.post("/intake/url", json={
                "url": "https://www.ebay.com/itm/12345",
                "category": "pokemon",
                "name": "Charizard",
                "condition": "Near Mint",
            })

        assert resp.status_code == 200
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["url"] == "https://www.ebay.com/itm/12345"
        hints = call_kwargs.get("user_hints", {})
        assert hints["category"] == "pokemon"

    def test_url_import_missing_url_422(self):
        """Missing URL should be rejected."""
        resp = client.post("/intake/url", json={})
        assert resp.status_code == 422

    def test_url_import_empty_url_422(self):
        """Empty URL string should be rejected by min_length=1."""
        resp = client.post("/intake/url", json={
            "url": "",
        })
        assert resp.status_code == 422

    def test_url_import_no_scheme_rejected(self):
        """URL without http(s):// prefix should be rejected (400)."""
        resp = client.post("/intake/url", json={
            "url": "www.ebay.com/itm/12345",
        })
        assert resp.status_code == 400
        assert "http" in resp.json()["detail"].lower()

    def test_url_import_ssrf_blocked(self):
        """Internal IP URLs should be blocked by SSRF protection."""
        with patch(
            "app.agents.intake_router.validate_url",
            side_effect=ValueError("URL points to a private/internal IP address"),
        ):
            resp = client.post("/intake/url", json={
                "url": "http://169.254.169.254/latest/meta-data/",
            })

        assert resp.status_code == 400
        assert "private" in resp.json()["detail"].lower() or "internal" in resp.json()["detail"].lower()

    def test_url_import_url_too_long_422(self):
        """URL exceeding 2048 chars should be rejected."""
        resp = client.post("/intake/url", json={
            "url": "https://example.com/" + "A" * 2100,
        })
        assert resp.status_code == 422


# ===========================================================================
# POST /intake/save
# ===========================================================================

class TestIntakeSave:
    """POST /intake/save endpoint (DB_ENABLED=false fallback)."""

    def test_save_happy_path(self):
        """Save returns a mock item with UUID."""
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
        assert len(data["id"]) == 36  # UUID format

    def test_save_minimal(self):
        """Save with only required title field."""
        resp = client.post("/intake/save", json={
            "title": "Unknown Item",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Unknown Item"
        assert data["created"] is True

    def test_save_full_payload(self):
        """Save with all optional fields."""
        resp = client.post("/intake/save", json={
            "title": "Blue-Eyes White Dragon",
            "category": "yugioh",
            "condition": "Mint",
            "subtype_id": "LOB-001",
            "taxonomy_version": "v1.0",
            "attributes": {"rarity": "Ultra Rare"},
            "images": ["https://example.com/bewd.jpg"],
            "barcode": "4012927843123",
            "estimated_price": 150.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Blue-Eyes White Dragon"
        assert data["category"] == "yugioh"

    def test_save_missing_title_422(self):
        """Missing title should be rejected."""
        resp = client.post("/intake/save", json={
            "category": "pokemon",
        })
        assert resp.status_code == 422

    def test_save_empty_title_422(self):
        """Empty title should be rejected by min_length=1."""
        resp = client.post("/intake/save", json={
            "title": "",
        })
        assert resp.status_code == 422

    def test_save_title_too_long_422(self):
        """Title exceeding 500 chars should be rejected."""
        resp = client.post("/intake/save", json={
            "title": "A" * 501,
        })
        assert resp.status_code == 422


# ===========================================================================
# POST /intake/process (multipart form)
# ===========================================================================

class TestIntakeProcess:
    """POST /intake/process endpoint (multipart form with optional image + barcode)."""

    def test_process_with_barcode_only(self):
        """Process endpoint with barcode but no image."""
        mock_result = _make_intake_result()
        with patch(
            "app.agents.intake_router.process_intake",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post(
                "/intake/process",
                data={"barcode": "4012927843123"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Charizard Base Set Holo"
        assert data["barcode"] == "4012927843123"

    def test_process_no_barcode_no_image_400(self):
        """Process without barcode or image should return 400."""
        resp = client.post("/intake/process", data={})
        assert resp.status_code == 400
        assert "barcode" in resp.json()["detail"].lower() or "image" in resp.json()["detail"].lower()

    def test_process_with_image(self):
        """Process endpoint with a valid PNG image."""
        mock_result = _make_intake_result(identification_method="vision")
        with patch(
            "app.agents.intake_router.process_intake",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post(
                "/intake/process",
                files={"file": ("test.png", _png_magic_bytes(), "image/png")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["identification_method"] == "vision"

    def test_process_invalid_content_type_400(self):
        """Uploading a non-image file should return 400."""
        resp = client.post(
            "/intake/process",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
        )
        assert resp.status_code == 400
        assert "Unsupported image type" in resp.json()["detail"]

    def test_process_invalid_magic_bytes_400(self):
        """File with wrong magic bytes should return 400."""
        resp = client.post(
            "/intake/process",
            files={"file": ("test.png", b"not a real image at all", "image/png")},
        )
        assert resp.status_code == 400
        assert "valid image" in resp.json()["detail"].lower()


# ===========================================================================
# POST /intake/image-only
# ===========================================================================

class TestIntakeImageOnly:
    """POST /intake/image-only endpoint."""

    def test_image_only_happy_path(self):
        """Image-only intake with a valid JPEG."""
        mock_result = _make_intake_result(identification_method="vision")
        with patch(
            "app.agents.intake_router.process_intake",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post(
                "/intake/image-only",
                files={"file": ("test.jpg", _jpeg_magic_bytes(), "image/jpeg")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["identification_method"] == "vision"

    def test_image_only_with_hints(self):
        """Image-only with category and condition hints."""
        mock_result = _make_intake_result(identification_method="vision")
        with patch(
            "app.agents.intake_router.process_intake",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_fn:
            resp = client.post(
                "/intake/image-only",
                files={"file": ("test.jpg", _jpeg_magic_bytes(), "image/jpeg")},
                data={"category": "pokemon", "condition": "Near Mint"},
            )

        assert resp.status_code == 200
        call_kwargs = mock_fn.call_args.kwargs
        hints = call_kwargs.get("user_hints", {})
        assert hints["category"] == "pokemon"
        assert hints["condition"] == "Near Mint"

    def test_image_only_invalid_content_type_400(self):
        """Image-only with unsupported content type returns 400."""
        resp = client.post(
            "/intake/image-only",
            files={"file": ("test.bmp", b"\x42\x4d" + b"\x00" * 100, "image/bmp")},
        )
        assert resp.status_code == 400

    def test_image_only_invalid_magic_bytes_400(self):
        """Image-only with fake image data returns 400."""
        resp = client.post(
            "/intake/image-only",
            files={"file": ("test.png", b"not an image", "image/png")},
        )
        assert resp.status_code == 400
