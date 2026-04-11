"""
Tests for app/features/photo_upload_router.py — presigned S3 URLs and server-side upload.

Covers:
  - POST /photos/presign-upload      — presign URL generation
  - POST /photos/upload              — server-side optimized upload
  - DELETE /photos/{photo_key:path}  — photo deletion with ownership check
  - GET  /photos/list/{item_id}      — list photos for an item
  - Edge cases: bad content types, empty files, oversized files, path traversal,
    cross-user deletion, S3 unavailable
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

# ---------------------------------------------------------------------------
# Ensure botocore.exceptions is importable even when boto3 is not installed.
# The photo_upload_router does `from botocore.exceptions import ...` inside
# try blocks, so we need stub exception classes available.
# ---------------------------------------------------------------------------
if "botocore" not in sys.modules:
    _botocore = MagicMock()

    class _BotoCoreError(Exception):
        pass

    class _ClientError(Exception):
        def __init__(self, error_response=None, operation_name=""):
            self.response = error_response or {}
            self.operation_name = operation_name
            super().__init__(str(error_response))

    _botocore_exceptions = MagicMock()
    _botocore_exceptions.BotoCoreError = _BotoCoreError
    _botocore_exceptions.ClientError = _ClientError
    _botocore.exceptions = _botocore_exceptions
    sys.modules["botocore"] = _botocore
    sys.modules["botocore.exceptions"] = _botocore_exceptions

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

USER_ID = "dev-user-local"
ITEM_ID = str(uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_s3_client():
    """Return a MagicMock pretending to be a boto3 S3 client."""
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://s3.presigned.example.com/upload"
    s3.put_object.return_value = {}
    s3.delete_object.return_value = {}
    s3.list_objects_v2.return_value = {"Contents": []}
    return s3


# Minimal valid JPEG bytes for imghdr detection
_JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"


def _fake_upload_file(
    content: bytes | None = None,
    content_type: str = "image/jpeg",
    filename: str = "test.jpg",
):
    """Create a dict suitable for TestClient multipart files param.

    If content is not provided, uses a minimal JPEG-valid header.
    """
    if content is None:
        content = _JPEG_HEADER + b"x" * 50
    elif content and content_type == "image/jpeg" and not content.startswith(b"\xff\xd8"):
        # Prepend JPEG magic bytes for tests that pass arbitrary bytes
        content = _JPEG_HEADER + content
    return {"file": (filename, io.BytesIO(content), content_type)}


# ---------------------------------------------------------------------------
# POST /photos/presign-upload
# ---------------------------------------------------------------------------


class TestPresignUpload:
    """Tests for POST /photos/presign-upload endpoint."""

    def test_happy_path(self):
        """Valid presign request returns upload_url, photo_key, cdn_url."""
        s3 = _fake_s3_client()
        with patch("app.features.photo_upload_router._get_s3", return_value=s3):
            resp = client.post(
                "/photos/presign-upload",
                json={"item_id": ITEM_ID, "content_type": "image/jpeg"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "upload_url" in data
        assert "photo_key" in data
        assert "cdn_url" in data
        assert data["upload_url"] == "https://s3.presigned.example.com/upload"
        assert USER_ID in data["photo_key"]
        assert ITEM_ID in data["photo_key"]

    def test_response_schema_types(self):
        """Verify response fields have correct types."""
        s3 = _fake_s3_client()
        with patch("app.features.photo_upload_router._get_s3", return_value=s3):
            resp = client.post(
                "/photos/presign-upload",
                json={"item_id": ITEM_ID, "content_type": "image/png"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["upload_url"], str)
        assert isinstance(data["photo_key"], str)
        assert isinstance(data["cdn_url"], str)
        # photo_key should end with .png since content_type is image/png
        assert data["photo_key"].endswith(".png")

    def test_webp_content_type_accepted(self):
        """WebP content type is allowed."""
        s3 = _fake_s3_client()
        with patch("app.features.photo_upload_router._get_s3", return_value=s3):
            resp = client.post(
                "/photos/presign-upload",
                json={"item_id": ITEM_ID, "content_type": "image/webp"},
            )

        assert resp.status_code == 200
        assert resp.json()["photo_key"].endswith(".webp")

    def test_invalid_content_type_returns_400(self):
        """Unsupported content type (image/gif) returns 400."""
        resp = client.post(
            "/photos/presign-upload",
            json={"item_id": ITEM_ID, "content_type": "image/gif"},
        )
        assert resp.status_code == 400
        detail = resp.json().get("detail", {})
        assert "Unsupported content type" in detail.get("message", "")

    def test_empty_item_id_returns_400(self):
        """Empty item_id returns 400."""
        resp = client.post(
            "/photos/presign-upload",
            json={"item_id": "   ", "content_type": "image/jpeg"},
        )
        assert resp.status_code == 400

    def test_missing_item_id_returns_422(self):
        """Missing item_id field returns 422 validation error."""
        resp = client.post(
            "/photos/presign-upload",
            json={"content_type": "image/jpeg"},
        )
        assert resp.status_code == 422

    def test_missing_content_type_returns_422(self):
        """Missing content_type field returns 422 validation error."""
        resp = client.post(
            "/photos/presign-upload",
            json={"item_id": ITEM_ID},
        )
        assert resp.status_code == 422

    def test_s3_not_configured_returns_503(self):
        """When S3 is not available, returns 503."""
        with patch("app.features.photo_upload_router._get_s3", return_value=None):
            resp = client.post(
                "/photos/presign-upload",
                json={"item_id": ITEM_ID, "content_type": "image/jpeg"},
            )

        assert resp.status_code == 503
        detail = resp.json().get("detail", {})
        assert detail.get("code") == "STORAGE_ERROR"


# ---------------------------------------------------------------------------
# POST /photos/upload
# ---------------------------------------------------------------------------


class TestServerSideUpload:
    """Tests for POST /photos/upload — server-side optimized upload."""

    def test_happy_path(self):
        """Valid upload returns photo_key, cdn_url, blurhash, dimensions."""
        s3 = _fake_s3_client()
        with patch("app.features.photo_upload_router._get_s3", return_value=s3), \
             patch("app.features.photo_upload_router.optimize_image", return_value=(b"optimized", 800, 600)), \
             patch("app.features.photo_upload_router.generate_blurhash", return_value="LKO2?V%2Tw=w]~RB"):
            resp = client.post(
                "/photos/upload",
                files=_fake_upload_file(),
                data={"item_id": ITEM_ID},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "photo_key" in data
        assert "cdn_url" in data
        assert "blurhash" in data
        assert data["width"] == 800
        assert data["height"] == 600
        assert data["original_size"] == len(_JPEG_HEADER) + 50  # default content size
        assert data["optimized_size"] == len(b"optimized")

    def test_response_schema_types(self):
        """Verify all response fields exist with correct types."""
        s3 = _fake_s3_client()
        with patch("app.features.photo_upload_router._get_s3", return_value=s3), \
             patch("app.features.photo_upload_router.optimize_image", return_value=(b"opt", 400, 300)), \
             patch("app.features.photo_upload_router.generate_blurhash", return_value="L00"):
            resp = client.post(
                "/photos/upload",
                files=_fake_upload_file(content=b"x" * 50),
                data={"item_id": ITEM_ID},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["photo_key"], str)
        assert isinstance(data["cdn_url"], str)
        assert isinstance(data["blurhash"], str)
        assert isinstance(data["width"], int)
        assert isinstance(data["height"], int)
        assert isinstance(data["original_size"], int)
        assert isinstance(data["optimized_size"], int)

    def test_empty_item_id_returns_400(self):
        """Empty item_id form field returns 400."""
        resp = client.post(
            "/photos/upload",
            files=_fake_upload_file(),
            data={"item_id": "   "},
        )
        assert resp.status_code == 400

    def test_invalid_content_type_returns_400(self):
        """Unsupported content type returns 400."""
        resp = client.post(
            "/photos/upload",
            files=_fake_upload_file(content_type="image/bmp"),
            data={"item_id": ITEM_ID},
        )
        assert resp.status_code == 400

    def test_empty_file_returns_400(self):
        """Empty file (0 bytes) returns 400."""
        with patch("app.features.photo_upload_router.optimize_image", return_value=(b"opt", 1, 1)), \
             patch("app.features.photo_upload_router.generate_blurhash", return_value="L00"):
            resp = client.post(
                "/photos/upload",
                files=_fake_upload_file(content=b""),
                data={"item_id": ITEM_ID},
            )
        assert resp.status_code == 400

    def test_oversized_file_returns_413(self):
        """File exceeding 10 MB returns 413."""
        big_content = b"x" * (10 * 1024 * 1024 + 1)
        with patch("app.features.photo_upload_router.optimize_image", return_value=(b"opt", 1, 1)), \
             patch("app.features.photo_upload_router.generate_blurhash", return_value="L00"):
            resp = client.post(
                "/photos/upload",
                files=_fake_upload_file(content=big_content),
                data={"item_id": ITEM_ID},
            )
        assert resp.status_code == 413

    def test_s3_not_configured_returns_503(self):
        """When S3 is unavailable, returns 503."""
        with patch("app.features.photo_upload_router._get_s3", return_value=None), \
             patch("app.features.photo_upload_router.optimize_image", return_value=(b"opt", 100, 100)), \
             patch("app.features.photo_upload_router.generate_blurhash", return_value="L00"):
            resp = client.post(
                "/photos/upload",
                files=_fake_upload_file(content=b"x" * 50),
                data={"item_id": ITEM_ID},
            )
        assert resp.status_code == 503

    def test_optimize_image_value_error_returns_400(self):
        """If optimize_image raises ValueError, returns 400."""
        with patch("app.features.photo_upload_router.optimize_image", side_effect=ValueError("Corrupt image")):
            resp = client.post(
                "/photos/upload",
                files=_fake_upload_file(content=b"x" * 50),
                data={"item_id": ITEM_ID},
            )
        assert resp.status_code == 400
        detail = resp.json().get("detail", {})
        assert "Corrupt image" in detail.get("message", "")

    def test_optimize_image_os_error_returns_500(self):
        """If optimize_image raises OSError, returns 500."""
        with patch("app.features.photo_upload_router.optimize_image", side_effect=OSError("disk")):
            resp = client.post(
                "/photos/upload",
                files=_fake_upload_file(content=b"x" * 50),
                data={"item_id": ITEM_ID},
            )
        assert resp.status_code == 500

    def test_blurhash_failure_fallback(self):
        """If blurhash generation fails, a fallback string is used instead of a 500."""
        s3 = _fake_s3_client()
        with patch("app.features.photo_upload_router._get_s3", return_value=s3), \
             patch("app.features.photo_upload_router.optimize_image", return_value=(b"opt", 200, 200)), \
             patch("app.features.photo_upload_router.generate_blurhash", side_effect=RuntimeError("oops")):
            resp = client.post(
                "/photos/upload",
                files=_fake_upload_file(content=b"x" * 50),
                data={"item_id": ITEM_ID},
            )
        assert resp.status_code == 200
        data = resp.json()
        # Fallback blurhash is "C:808080:0:0"
        assert data["blurhash"] == "C:808080:0:0"


# ---------------------------------------------------------------------------
# DELETE /photos/{photo_key:path}
# ---------------------------------------------------------------------------


class TestDeletePhoto:
    """Tests for DELETE /photos/{photo_key:path} endpoint."""

    def test_happy_path(self):
        """Deleting own photo succeeds."""
        s3 = _fake_s3_client()
        photo_key = f"user-uploads/{USER_ID}/{ITEM_ID}/abc123.jpg"

        with patch("app.features.photo_upload_router._get_s3", return_value=s3):
            resp = client.delete(f"/photos/{photo_key}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "Photo deleted successfully"

    def test_response_schema(self):
        """Verify response has success (bool) and message (str)."""
        s3 = _fake_s3_client()
        photo_key = f"user-uploads/{USER_ID}/{ITEM_ID}/xyz.jpg"
        with patch("app.features.photo_upload_router._get_s3", return_value=s3):
            resp = client.delete(f"/photos/{photo_key}")

        data = resp.json()
        assert isinstance(data["success"], bool)
        assert isinstance(data["message"], str)

    def test_path_traversal_blocked(self):
        """Path traversal attempt (with ..) is blocked.

        Note: HTTP clients (httpx/starlette) normalize '../' out of the URL
        path before sending, so the '..' check on the server side is not
        triggered directly via TestClient. Instead, the resolved path fails
        the ownership prefix check (403). Both checks serve the same security
        purpose: preventing cross-user photo deletion.
        """
        photo_key = f"user-uploads/{USER_ID}/../other-user/secret.jpg"
        resp = client.delete(f"/photos/{photo_key}")
        # After path normalization by the client, the key becomes
        # "user-uploads/other-user/secret.jpg" which fails ownership => 403
        assert resp.status_code in (400, 403)

    def test_path_with_literal_dotdot_returns_400(self):
        """A photo key containing literal '..' (not as path traversal) is rejected."""
        # Embed '..' in the filename portion so the HTTP client does not resolve it
        photo_key = f"user-uploads/{USER_ID}/{ITEM_ID}/file..name.jpg"
        s3 = _fake_s3_client()
        with patch("app.features.photo_upload_router._get_s3", return_value=s3):
            resp = client.delete(f"/photos/{photo_key}")
        assert resp.status_code == 400

    def test_cross_user_deletion_returns_403(self):
        """Attempting to delete another user's photo returns 403."""
        other_user = str(uuid4())
        photo_key = f"user-uploads/{other_user}/{ITEM_ID}/img.jpg"
        resp = client.delete(f"/photos/{photo_key}")
        assert resp.status_code == 403
        detail = resp.json().get("detail", {})
        assert detail.get("code") == "AUTH_ERROR"

    def test_s3_not_configured_returns_503(self):
        """When S3 is unavailable, returns 503."""
        photo_key = f"user-uploads/{USER_ID}/{ITEM_ID}/img.jpg"
        with patch("app.features.photo_upload_router._get_s3", return_value=None):
            resp = client.delete(f"/photos/{photo_key}")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /photos/list/{item_id}
# ---------------------------------------------------------------------------


class TestListPhotos:
    """Tests for GET /photos/list/{item_id} endpoint."""

    def test_happy_path_empty_list(self):
        """Listing photos for an item with no photos returns empty list."""
        s3 = _fake_s3_client()
        s3.list_objects_v2.return_value = {"Contents": []}

        with patch("app.features.photo_upload_router._get_s3", return_value=s3):
            resp = client.get(f"/photos/list/{ITEM_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == ITEM_ID
        assert data["photos"] == []

    def test_happy_path_with_photos(self):
        """Listing returns photo objects with correct fields."""
        s3 = _fake_s3_client()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        s3.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": f"user-uploads/{USER_ID}/{ITEM_ID}/img1.jpg",
                    "Size": 12345,
                    "LastModified": now,
                },
                {
                    "Key": f"user-uploads/{USER_ID}/{ITEM_ID}/img2.jpg",
                    "Size": 67890,
                    "LastModified": now,
                },
            ]
        }

        with patch("app.features.photo_upload_router._get_s3", return_value=s3):
            resp = client.get(f"/photos/list/{ITEM_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["photos"]) == 2
        photo = data["photos"][0]
        assert "photo_key" in photo
        assert "cdn_url" in photo
        assert "size" in photo
        assert "last_modified" in photo
        assert photo["size"] == 12345

    def test_response_schema_types(self):
        """Verify response field types."""
        s3 = _fake_s3_client()
        with patch("app.features.photo_upload_router._get_s3", return_value=s3):
            resp = client.get(f"/photos/list/{ITEM_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["photos"], list)
        assert isinstance(data["item_id"], str)

    def test_empty_item_id_returns_400(self):
        """Empty item_id returns 400."""
        resp = client.get("/photos/list/%20%20")
        assert resp.status_code == 400

    def test_s3_not_configured_returns_503(self):
        """When S3 is unavailable, returns 503."""
        with patch("app.features.photo_upload_router._get_s3", return_value=None):
            resp = client.get(f"/photos/list/{ITEM_ID}")
        assert resp.status_code == 503
