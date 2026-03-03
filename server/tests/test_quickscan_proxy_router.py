"""Tests for app.features.quickscan_proxy_router — /quickscan endpoints."""

import os

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import io
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from main import app

client = TestClient(app, raise_server_exceptions=False)


# ---- Mock objects for quickscan_advanced_router types ----

class _MockAttrs:
    """Mimics QuickScanAttributes."""
    def __init__(self, category="mtg", edition_guess="Unlimited",
                 condition_guess="Near Mint", rarity_score=0.82):
        self.category = category
        self.edition_guess = edition_guess
        self.condition_guess = condition_guess
        self.rarity_score = rarity_score


class _MockPrediction:
    """Mimics QuickScanPrediction."""
    def __init__(self, name="Demo Black Lotus", estimated_mid=22000.0,
                 confidence=0.91):
        self.name = name
        self.estimated_low = 18000.0
        self.estimated_mid = estimated_mid
        self.estimated_high = 26000.0
        self.currency = "EUR"
        self.confidence = confidence
        self.explanation = "Test explanation"


class _MockResult:
    """Mimics QuickScanResult."""
    def __init__(self, attrs=None, prediction=None):
        self.item_id = None
        self.attributes = attrs or _MockAttrs()
        self.prediction = prediction or _MockPrediction()


class _MockBatchResponse:
    """Mimics BatchQuickScanResponse."""
    def __init__(self, results=None):
        self.results = results if results is not None else [_MockResult()]


class _MockBatchRequest:
    """Mimics BatchQuickScanRequest."""
    def __init__(self, image_ids=None, category=None):
        self.image_ids = image_ids or []
        self.category = category


class _MockSingleRequest:
    """Mimics QuickScanSingleRequest."""
    def __init__(self, category="funko"):
        self.category = category


def _patch_advanced(single_result=None, batch_response=None):
    """Patch the lazy import of quickscan_advanced_router in the proxy."""
    single_result = single_result or _MockResult()
    batch_response = batch_response or _MockBatchResponse()

    mock_single = AsyncMock(return_value=single_result)
    mock_batch = AsyncMock(return_value=batch_response)

    return patch.dict("sys.modules", {
        "app.features.quickscan_advanced_router": type("mod", (), {
            "quickscan_single": mock_single,
            "quickscan_batch": mock_batch,
            "BatchQuickScanRequest": _MockBatchRequest,
            "QuickScanSingleRequest": _MockSingleRequest,
            "QuickScanResult": _MockResult,
            "BatchQuickScanResponse": _MockBatchResponse,
        })(),
    }), mock_single, mock_batch


# ---- POST /quickscan ----


class TestQuickScanProxy:

    def test_no_images_falls_back_to_single_demo(self):
        mod_patch, mock_single, mock_batch = _patch_advanced()
        with mod_patch:
            r = client.post("/quickscan", json={})
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Demo Black Lotus"
        assert data["estimated_value"] == 22000.0
        mock_single.assert_awaited_once()
        mock_batch.assert_not_awaited()

    def test_with_image_id_calls_batch(self):
        mod_patch, mock_single, mock_batch = _patch_advanced()
        with mod_patch:
            r = client.post("/quickscan", json={"image_id": "img-001"})
        assert r.status_code == 200
        mock_batch.assert_awaited_once()

    def test_with_image_ids_calls_batch(self):
        mod_patch, mock_single, mock_batch = _patch_advanced()
        with mod_patch:
            r = client.post("/quickscan", json={"image_ids": ["img-001", "img-002"]})
        assert r.status_code == 200
        mock_batch.assert_awaited_once()

    def test_image_ids_deduplicated(self):
        """Duplicate IDs should be collapsed before calling batch."""
        mod_patch, mock_single, mock_batch = _patch_advanced()
        with mod_patch:
            r = client.post("/quickscan", json={
                "image_id": "img-001",
                "image_ids": ["img-001", "img-002", "img-002"],
            })
        assert r.status_code == 200
        # batch_req.image_ids should be ["img-001", "img-002"]
        call_args = mock_batch.call_args
        batch_req = call_args[0][0]
        assert len(batch_req.image_ids) == 2

    def test_empty_image_ids_falls_back_to_single(self):
        mod_patch, mock_single, mock_batch = _patch_advanced()
        with mod_patch:
            r = client.post("/quickscan", json={"image_ids": []})
        assert r.status_code == 200
        mock_single.assert_awaited_once()
        mock_batch.assert_not_awaited()

    def test_batch_empty_results_falls_back_to_single(self):
        """If batch returns 0 results, fall back to single demo."""
        empty_batch = _MockBatchResponse(results=[])
        mod_patch, mock_single, mock_batch = _patch_advanced(batch_response=empty_batch)
        with mod_patch:
            r = client.post("/quickscan", json={"image_id": "img-001"})
        assert r.status_code == 200
        # Should have called batch, then fallen back to single
        mock_batch.assert_awaited_once()
        mock_single.assert_awaited_once()

    def test_category_mapping_known_key(self):
        """Known category code maps to friendly label."""
        result = _MockResult(attrs=_MockAttrs(category="mtg"))
        mod_patch, _, _ = _patch_advanced(single_result=result)
        with mod_patch:
            r = client.post("/quickscan", json={})
        assert r.json()["category"] == "Magic: The Gathering"

    def test_category_mapping_unknown_key(self):
        """Unknown category code passes through as-is."""
        result = _MockResult(attrs=_MockAttrs(category="unknown_cat"))
        mod_patch, _, _ = _patch_advanced(single_result=result)
        with mod_patch:
            r = client.post("/quickscan", json={})
        assert r.json()["category"] == "unknown_cat"

    def test_notes_includes_condition_edition_rarity_confidence(self):
        result = _MockResult(
            attrs=_MockAttrs(
                condition_guess="Near Mint",
                edition_guess="Unlimited",
                rarity_score=0.82,
            ),
            prediction=_MockPrediction(confidence=0.91),
        )
        mod_patch, _, _ = _patch_advanced(single_result=result)
        with mod_patch:
            r = client.post("/quickscan", json={})
        notes = r.json()["notes"]
        assert "QuickScan:" in notes
        assert "Condition guess: Near Mint" in notes
        assert "Edition guess: Unlimited" in notes
        assert "Rarity score: 0.82" in notes
        assert "Model confidence: 0.91" in notes

    def test_notes_omits_missing_attributes(self):
        result = _MockResult(
            attrs=_MockAttrs(condition_guess=None, edition_guess=None, rarity_score=None),
            prediction=_MockPrediction(confidence=0.75),
        )
        mod_patch, _, _ = _patch_advanced(single_result=result)
        with mod_patch:
            r = client.post("/quickscan", json={})
        notes = r.json()["notes"]
        assert "Condition guess" not in notes
        assert "Edition guess" not in notes
        assert "Rarity score" not in notes
        assert "Model confidence: 0.75" in notes

    def test_collection_name_from_edition(self):
        result = _MockResult(attrs=_MockAttrs(edition_guess="Base Set"))
        mod_patch, _, _ = _patch_advanced(single_result=result)
        with mod_patch:
            r = client.post("/quickscan", json={})
        assert r.json()["collection_name"] == "Base Set"

    def test_collection_name_defaults_when_no_edition(self):
        result = _MockResult(attrs=_MockAttrs(edition_guess=None))
        mod_patch, _, _ = _patch_advanced(single_result=result)
        with mod_patch:
            r = client.post("/quickscan", json={})
        assert r.json()["collection_name"] == "Unknown edition"


# ---- POST /quickscan/upload-image ----


class TestQuickScanUpload:

    def test_upload_valid_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"QUICKSCAN_TMP_DIR": tmp}):
                r = client.post(
                    "/quickscan/upload-image",
                    files={"file": ("photo.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["image_id"].startswith("quickscan-")
        assert len(data["image_id"]) > 20  # uuid hex is 32 chars

    def test_upload_too_large_returns_413(self):
        big_content = b"\x00" * (20 * 1024 * 1024 + 1)  # Just over 20 MB
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"QUICKSCAN_TMP_DIR": tmp}):
                r = client.post(
                    "/quickscan/upload-image",
                    files={"file": ("huge.jpg", big_content, "image/jpeg")},
                )
        assert r.status_code == 413

    def test_upload_sanitizes_filename(self):
        """Special characters in filename should be replaced with underscores."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"QUICKSCAN_TMP_DIR": tmp}):
                r = client.post(
                    "/quickscan/upload-image",
                    files={"file": ("my photo (1).jpg", b"\x00" * 10, "image/jpeg")},
                )
        assert r.status_code == 200
        # The file was saved — check the image_id is valid
        assert r.json()["image_id"].startswith("quickscan-")

    def test_upload_truncates_long_filename(self):
        long_name = "a" * 200 + ".jpg"
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"QUICKSCAN_TMP_DIR": tmp}):
                r = client.post(
                    "/quickscan/upload-image",
                    files={"file": (long_name, b"\x00" * 10, "image/jpeg")},
                )
        assert r.status_code == 200

    def test_upload_missing_file_returns_422(self):
        r = client.post("/quickscan/upload-image")
        assert r.status_code == 422

    def test_upload_no_auth_required(self):
        """Upload endpoint is public."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"QUICKSCAN_TMP_DIR": tmp}):
                r = client.post(
                    "/quickscan/upload-image",
                    files={"file": ("test.png", b"\x89PNG" + b"\x00" * 50, "image/png")},
                )
        assert r.status_code == 200
