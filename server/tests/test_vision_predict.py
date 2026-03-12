"""Tests for the vision-predict router (classify, health, categories)."""

import io
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app():
    import os
    os.environ.setdefault("DEV_MODE", "true")
    os.environ.setdefault("DB_ENABLED", "false")
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["PER_USER_RATE_LIMIT_ENABLED"] = "false"
    from main import app as _app
    return _app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _bypass_auth():
    """Mock get_current_user_id to avoid PyJWT dependency in tests."""
    with patch("app.auth.get_current_user_id", new_callable=AsyncMock, return_value="test-user-123"):
        yield


# ---------------------------------------------------------------------------
# Mock classify result helper
# ---------------------------------------------------------------------------

def _mock_classification_result():
    """Return a mock ClassificationResult dataclass instance."""
    from app.ml.vision_classifier import ClassificationResult
    return ClassificationResult(
        category_id="pokemon",
        category_confidence=0.92,
        condition="near_mint",
        condition_confidence=0.85,
        suggested_name="Charizard Base Set",
        attributes={"set": "Base Set", "card_number": "4/102"},
        embedding_vector=None,
        classification_method="clip",
    )


# ---------------------------------------------------------------------------
# Minimal valid image bytes
# ---------------------------------------------------------------------------

VALID_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
VALID_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
VALID_WEBP = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 100
NON_IMAGE_BYTES = b"this is not an image at all"
EMPTY_FILE = b""


# ---------------------------------------------------------------------------
# Tests — Health check
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_health_returns_ok(client: AsyncClient):
    """GET /vision-predict/health returns ok=True."""
    resp = await client.get("/vision-predict/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["source"] == "vision-predict"
    assert "classification_tier" in data
    assert "max_image_bytes" in data


# ---------------------------------------------------------------------------
# Tests — Categories
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_categories_returns_non_empty_list(client: AsyncClient):
    """GET /vision-predict/categories returns a non-empty category list."""
    resp = await client.get("/vision-predict/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert "total" in data
    assert data["total"] > 0
    assert len(data["categories"]) == data["total"]
    # Each category has the expected fields
    first = data["categories"][0]
    assert "category_id" in first
    assert "description" in first


# ---------------------------------------------------------------------------
# Tests — Classify with valid JPEG
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_classify_valid_jpeg(client: AsyncClient):
    """POST /vision-predict/classify with valid JPEG succeeds."""
    mock_result = _mock_classification_result()
    with patch("app.ml.vision_classifier.classify_image", new_callable=AsyncMock, return_value=mock_result):
        resp = await client.post(
            "/vision-predict/classify",
            files={"file": ("test.jpg", io.BytesIO(VALID_JPEG), "image/jpeg")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["category_id"] == "pokemon"
    assert data["category_confidence"] == 0.92
    assert data["condition"] == "near_mint"
    assert data["condition_confidence"] == 0.85
    assert data["condition_score"] == 0.85  # near_mint -> 0.85
    assert data["classification_method"] == "clip"
    assert data["suggested_name"] == "Charizard Base Set"
    assert data["attributes"] == {"set": "Base Set", "card_number": "4/102"}


# ---------------------------------------------------------------------------
# Tests — Classify with invalid MIME type
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_classify_invalid_mime_type(client: AsyncClient):
    """POST /vision-predict/classify with non-image MIME type returns 400."""
    resp = await client.post(
        "/vision-predict/classify",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests — Classify with empty file
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_classify_empty_file(client: AsyncClient):
    """POST /vision-predict/classify with empty file returns 400."""
    resp = await client.post(
        "/vision-predict/classify",
        files={"file": ("empty.jpg", io.BytesIO(EMPTY_FILE), "image/jpeg")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests — Classify with oversized file
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_classify_oversized_file(client: AsyncClient):
    """POST /vision-predict/classify with file exceeding max size returns 413."""
    from app.config import VISION_MAX_IMAGE_BYTES
    # Create a file just over the limit with valid JPEG header
    oversized = b"\xff\xd8\xff\xe0" + b"\x00" * (VISION_MAX_IMAGE_BYTES + 1)
    resp = await client.post(
        "/vision-predict/classify",
        files={"file": ("big.jpg", io.BytesIO(oversized), "image/jpeg")},
    )
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Tests — Classify with non-image bytes
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_classify_non_image_bytes(client: AsyncClient):
    """POST /vision-predict/classify with non-image bytes returns 400."""
    resp = await client.post(
        "/vision-predict/classify",
        files={"file": ("fake.jpg", io.BytesIO(NON_IMAGE_BYTES), "image/jpeg")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests — Classify with valid PNG
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_classify_valid_png(client: AsyncClient):
    """POST /vision-predict/classify with valid PNG magic bytes succeeds."""
    mock_result = _mock_classification_result()
    with patch("app.ml.vision_classifier.classify_image", new_callable=AsyncMock, return_value=mock_result):
        resp = await client.post(
            "/vision-predict/classify",
            files={"file": ("test.png", io.BytesIO(VALID_PNG), "image/png")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["category_id"] == "pokemon"
    assert data["classification_method"] == "clip"


# ---------------------------------------------------------------------------
# Tests — Classify with valid WebP
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_classify_valid_webp(client: AsyncClient):
    """POST /vision-predict/classify with valid WebP magic bytes succeeds."""
    mock_result = _mock_classification_result()
    with patch("app.ml.vision_classifier.classify_image", new_callable=AsyncMock, return_value=mock_result):
        resp = await client.post(
            "/vision-predict/classify",
            files={"file": ("test.webp", io.BytesIO(VALID_WEBP), "image/webp")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["category_id"] == "pokemon"
    assert data["classification_method"] == "clip"
