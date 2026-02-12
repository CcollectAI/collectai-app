"""
Tests for app/agents/intake_agent.py — process_intake() orchestrator.

Covers:
  - Barcode-only intake (mocked barcode lookup)
  - Vision-only intake (mocked vision classifier)
  - Barcode + vision supplement (partial barcode match)
  - Manual fallback when nothing provided
  - User hints override logic
  - Taxonomy correction lookup
  - Price estimation pipeline
  - Error resilience (exceptions caught, partial result returned)
  - IntakeResult.to_dict() serialization

Existing tests in test_intake_url_import.py cover helpers
(_detect_url_source, _convert_price_to_eur, _guess_category_from_url)
and process_url_import(). This file focuses on process_intake().
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# IntakeResult unit tests
# ---------------------------------------------------------------------------


class TestIntakeResult:
    """Verify IntakeResult dataclass and serialization."""

    def test_default_values(self):
        from app.agents.intake_agent import IntakeResult

        r = IntakeResult()
        assert r.name is None
        assert r.category_id is None
        assert r.category_confidence == 0.0
        assert r.identification_method == "manual"
        assert r.taxonomy_version == "v1.0"
        assert r.rationale == []

    def test_to_dict_round_trip(self):
        from app.agents.intake_agent import IntakeResult

        r = IntakeResult(
            name="Charizard",
            category_id="pokemon",
            category_confidence=0.856789,
            estimated_price=150.0,
        )
        d = r.to_dict()
        assert d["name"] == "Charizard"
        assert d["category_id"] == "pokemon"
        assert d["category_confidence"] == 0.8568  # rounded to 4dp
        assert d["estimated_price"] == 150.0
        assert d["taxonomy_version"] == "v1.0"

    def test_to_dict_contains_all_fields(self):
        from app.agents.intake_agent import IntakeResult

        d = IntakeResult().to_dict()
        expected_keys = {
            "name", "category_id", "category_confidence", "subtype_id",
            "attributes", "identification_method", "barcode", "barcode_type",
            "taxonomy_version", "taxonomy_confidence", "suggested_corrections",
            "estimated_price", "price_source", "price_band", "image_url",
            "rationale",
        }
        assert set(d.keys()) == expected_keys


# ---------------------------------------------------------------------------
# _price_band_to_dict tests
# ---------------------------------------------------------------------------


class TestPriceBandToDict:
    """Tests for _price_band_to_dict() helper."""

    def test_dict_passthrough(self):
        from app.agents.intake_agent import _price_band_to_dict

        band = {"q10": 5.0, "q50": 10.0, "q90": 15.0}
        assert _price_band_to_dict(band) == band

    def test_pydantic_v2_model(self):
        from app.agents.intake_agent import _price_band_to_dict

        mock_model = MagicMock()
        mock_model.model_dump.return_value = {"q10": 5, "q50": 10, "q90": 15}
        result = _price_band_to_dict(mock_model)
        assert result == {"q10": 5, "q50": 10, "q90": 15}

    def test_pydantic_v1_model(self):
        from app.agents.intake_agent import _price_band_to_dict

        mock_model = MagicMock(spec=[])
        mock_model.model_dump = MagicMock(side_effect=AttributeError)
        mock_model.dict = MagicMock(return_value={"q10": 1, "q50": 2, "q90": 3})
        result = _price_band_to_dict(mock_model)
        assert result == {"q10": 1, "q50": 2, "q90": 3}

    def test_fallback_getattr(self):
        from app.agents.intake_agent import _price_band_to_dict

        class Dummy:
            q10 = 1.0
            q50 = 2.0
            q90 = 3.0
            confidence = 0.5
            currency = "EUR"

        result = _price_band_to_dict(Dummy())
        assert result["q10"] == 1.0
        assert result["q50"] == 2.0
        assert result["currency"] == "EUR"


# ---------------------------------------------------------------------------
# process_intake — barcode path
# ---------------------------------------------------------------------------


class TestProcessIntakeBarcode:
    """Tests for process_intake() barcode lookup path."""

    @pytest.mark.asyncio
    async def test_barcode_found_full_match(self):
        from app.agents.intake_agent import process_intake

        mock_barcode = AsyncMock(return_value={
            "title": "Charizard Base Set Holo",
            "category_id": "pokemon",
            "subtype_id": "holo_rare",
            "attributes": {"set": "Base Set", "source": "local_catalog"},
            "image_url": "https://img.example.com/char.jpg",
            "rationale": ["Matched in local catalog"],
            "price_band": {"q10": 100, "q50": 200, "q90": 350, "confidence": 0.8, "currency": "EUR"},
            "identification_method": "barcode_catalog",
        })

        with patch("app.agents.intake_agent._get_db_pool", return_value=None), \
             patch("app.agents.intake_agent._barcode_lookup_internal", mock_barcode), \
             patch("app.agents.intake_agent._lookup_taxonomy_corrections", AsyncMock(return_value=[])):
            result = await process_intake(barcode="1234567890123", barcode_type="ean13")

        assert result.name == "Charizard Base Set Holo"
        assert result.category_id == "pokemon"
        assert result.identification_method == "barcode_catalog"
        assert result.estimated_price == 200
        assert result.category_confidence == 0.9
        assert result.barcode == "1234567890123"
        assert any("Matched in local catalog" in r for r in result.rationale)

    @pytest.mark.asyncio
    async def test_barcode_not_found_falls_through(self):
        from app.agents.intake_agent import process_intake

        mock_barcode = AsyncMock(return_value=None)

        with patch("app.agents.intake_agent._get_db_pool", return_value=None), \
             patch("app.agents.intake_agent._barcode_lookup_internal", mock_barcode):
            result = await process_intake(barcode="0000000000000")

        assert result.name is None
        assert result.identification_method == "manual"
        assert any("not found" in r for r in result.rationale)


# ---------------------------------------------------------------------------
# process_intake — vision path
# ---------------------------------------------------------------------------


class TestProcessIntakeVision:
    """Tests for process_intake() vision classification path."""

    @pytest.mark.asyncio
    async def test_vision_only(self):
        from app.agents.intake_agent import process_intake

        mock_vision = AsyncMock(return_value={
            "category_id": "funko",
            "category_confidence": 0.85,
            "condition": "Near Mint",
            "condition_confidence": 0.7,
            "suggested_name": "Funko Pop! Spider-Man",
            "attributes": {"series": "Marvel"},
            "identification_method": "vision_clip",
        })

        with patch("app.agents.intake_agent._get_db_pool", return_value=None), \
             patch("app.agents.intake_agent._vision_classify_internal", mock_vision), \
             patch("app.agents.intake_agent._lookup_taxonomy_corrections", AsyncMock(return_value=[])), \
             patch("app.agents.intake_agent._estimate_price", AsyncMock(return_value=(25.0, "market_hits", {"q10": 15, "q50": 25, "q90": 40}))):
            result = await process_intake(image_bytes=b"\x89PNG\r\n\x1a\n")

        assert result.category_id == "funko"
        assert result.category_confidence == 0.85
        assert result.name == "Funko Pop! Spider-Man"
        assert result.attributes.get("condition") == "Near Mint"
        assert result.identification_method == "vision_clip"
        assert result.estimated_price == 25.0

    @pytest.mark.asyncio
    async def test_vision_returns_none(self):
        from app.agents.intake_agent import process_intake

        mock_vision = AsyncMock(return_value=None)

        with patch("app.agents.intake_agent._get_db_pool", return_value=None), \
             patch("app.agents.intake_agent._vision_classify_internal", mock_vision):
            result = await process_intake(image_bytes=b"\x89PNG")

        assert result.category_id is None
        assert any("no result" in r for r in result.rationale)


# ---------------------------------------------------------------------------
# process_intake — barcode partial + vision supplement
# ---------------------------------------------------------------------------


class TestProcessIntakeBarcodePartialVision:
    """Tests for barcode partial match supplemented by vision."""

    @pytest.mark.asyncio
    async def test_partial_barcode_supplemented_by_vision(self):
        from app.agents.intake_agent import process_intake

        mock_barcode = AsyncMock(return_value={
            "title": "Dragon Ball Z Figure",
            "category_id": None,  # No category from barcode
            "subtype_id": None,
            "attributes": {"source": "catalog"},
            "image_url": None,
            "rationale": ["Found name only"],
            "price_band": None,
            "identification_method": "barcode_catalog",
        })

        mock_vision = AsyncMock(return_value={
            "category_id": "anime_figures",
            "category_confidence": 0.75,
            "condition": None,
            "condition_confidence": 0.0,
            "suggested_name": "DBZ Goku Figure",
            "attributes": {},
            "identification_method": "vision_openai",
        })

        with patch("app.agents.intake_agent._get_db_pool", return_value=None), \
             patch("app.agents.intake_agent._barcode_lookup_internal", mock_barcode), \
             patch("app.agents.intake_agent._vision_classify_internal", mock_vision), \
             patch("app.agents.intake_agent._lookup_taxonomy_corrections", AsyncMock(return_value=[])), \
             patch("app.agents.intake_agent._estimate_price", AsyncMock(return_value=(None, None, None))):
            result = await process_intake(
                barcode="9876543210987",
                image_bytes=b"\x89PNG",
            )

        # Name should come from barcode, category from vision
        assert result.name == "Dragon Ball Z Figure"
        assert result.category_id == "anime_figures"
        assert "barcode_catalog" in result.identification_method
        assert "vision_openai" in result.identification_method


# ---------------------------------------------------------------------------
# process_intake — no input
# ---------------------------------------------------------------------------


class TestProcessIntakeManual:
    """Tests for manual fallback when no barcode or image provided."""

    @pytest.mark.asyncio
    async def test_no_barcode_no_image(self):
        from app.agents.intake_agent import process_intake

        with patch("app.agents.intake_agent._get_db_pool", return_value=None):
            result = await process_intake()

        assert result.identification_method == "manual"
        assert any("manual" in r.lower() for r in result.rationale)


# ---------------------------------------------------------------------------
# process_intake — user hints
# ---------------------------------------------------------------------------


class TestProcessIntakeUserHints:
    """Tests for user hint overrides in process_intake()."""

    @pytest.mark.asyncio
    async def test_user_hints_override_category(self):
        from app.agents.intake_agent import process_intake

        mock_vision = AsyncMock(return_value={
            "category_id": "funko",
            "category_confidence": 0.6,
            "condition": None,
            "condition_confidence": 0.0,
            "suggested_name": "Some Pop",
            "attributes": {},
            "identification_method": "vision_heuristic",
        })

        with patch("app.agents.intake_agent._get_db_pool", return_value=None), \
             patch("app.agents.intake_agent._vision_classify_internal", mock_vision), \
             patch("app.agents.intake_agent._lookup_taxonomy_corrections", AsyncMock(return_value=[])), \
             patch("app.agents.intake_agent._estimate_price", AsyncMock(return_value=(None, None, None))):
            result = await process_intake(
                image_bytes=b"\x89PNG",
                user_hints={"category": "designer_toys", "name": "KAWS Figure", "condition": "Mint"},
            )

        assert result.category_id == "designer_toys"
        assert result.category_confidence == 1.0
        assert result.name == "KAWS Figure"
        assert result.attributes["condition"] == "Mint"
        assert any("overrode" in r for r in result.rationale)


# ---------------------------------------------------------------------------
# process_intake — taxonomy corrections
# ---------------------------------------------------------------------------


class TestProcessIntakeTaxonomyCorrections:
    """Tests for taxonomy correction pattern awareness."""

    @pytest.mark.asyncio
    async def test_corrections_appended_to_result(self):
        from app.agents.intake_agent import process_intake

        mock_vision = AsyncMock(return_value={
            "category_id": "pokemon",
            "category_confidence": 0.8,
            "condition": None,
            "condition_confidence": 0.0,
            "suggested_name": "Pikachu V",
            "attributes": {},
            "identification_method": "vision_clip",
        })

        mock_corrections = AsyncMock(return_value=[
            {"from_category": "pokemon", "to_category": "pokemon_jp", "frequency": 10, "user_count": 3},
        ])

        with patch("app.agents.intake_agent._get_db_pool", return_value=None), \
             patch("app.agents.intake_agent._vision_classify_internal", mock_vision), \
             patch("app.agents.intake_agent._lookup_taxonomy_corrections", mock_corrections), \
             patch("app.agents.intake_agent._estimate_price", AsyncMock(return_value=(None, None, None))):
            result = await process_intake(image_bytes=b"\x89PNG")

        assert len(result.suggested_corrections) == 1
        assert result.suggested_corrections[0]["to_category"] == "pokemon_jp"
        assert any("correction" in r.lower() for r in result.rationale)


# ---------------------------------------------------------------------------
# process_intake — error resilience
# ---------------------------------------------------------------------------


class TestProcessIntakeErrorResilience:
    """Tests that process_intake() catches exceptions and returns partial result."""

    @pytest.mark.asyncio
    async def test_barcode_exception_caught(self):
        from app.agents.intake_agent import process_intake

        mock_barcode = AsyncMock(side_effect=RuntimeError("DB gone"))

        with patch("app.agents.intake_agent._get_db_pool", return_value=None), \
             patch("app.agents.intake_agent._barcode_lookup_internal", mock_barcode):
            result = await process_intake(barcode="1234567890123")

        # Should not raise, should return partial result
        assert result is not None
        assert any("error" in r.lower() for r in result.rationale)

    @pytest.mark.asyncio
    async def test_intake_timestamp_always_set(self):
        from app.agents.intake_agent import process_intake

        with patch("app.agents.intake_agent._get_db_pool", return_value=None):
            result = await process_intake()

        assert "intake_timestamp" in result.attributes
