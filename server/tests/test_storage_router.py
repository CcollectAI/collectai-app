"""
Tests for app/features/storage_router.py — presigned URL and object pointer management.

Covers RLS (ownership) fixes:
  - POST /storage/presign-upload — valid request, invalid object_type, invalid content_type
  - GET /storage/objects — scoped by user (created_by filter)
  - GET /storage/presign-download/{id} — only own objects (created_by filter in query)
  - DELETE /storage/objects/{id} — only own objects (created_by filter in UPDATE)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

POINTER_ID = str(uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_conn_ctx():
    """Create a mock async context manager for get_conn()."""
    conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return conn, ctx


# ---------------------------------------------------------------------------
# POST /storage/presign-upload — validation
# ---------------------------------------------------------------------------


class TestPresignUpload:
    """Tests for POST /storage/presign-upload."""

    def test_valid_request_returns_upload_url(self):
        """A valid presign-upload request returns the upload_url, s3_key, pointer_id."""
        fake_url = "https://s3.eu-west-1.amazonaws.com/bucket/key?X-Amz-Signature=abc"
        with patch(
            "app.features.storage_router.generate_presigned_upload",
            return_value=fake_url,
        ):
            resp = client.post("/storage/presign-upload", json={
                "object_type": "user_photo",
                "content_type": "image/jpeg",
                "filename": "my_card.jpg",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["upload_url"] == fake_url
        assert "s3_key" in data
        assert "pointer_id" in data
        assert data["expires_in"] == 3600

    def test_valid_request_with_optional_fields(self):
        """Optional fields (related_item_id, related_category) are accepted."""
        item_id = str(uuid4())
        with patch(
            "app.features.storage_router.generate_presigned_upload",
            return_value="https://example.com/upload",
        ):
            resp = client.post("/storage/presign-upload", json={
                "object_type": "catalog_image",
                "content_type": "image/png",
                "filename": "catalog_shot.png",
                "related_item_id": item_id,
                "related_category": "pokemon",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert "pokemon" in data["s3_key"]

    def test_invalid_object_type_returns_400(self):
        """An unrecognised object_type should return 400."""
        resp = client.post("/storage/presign-upload", json={
            "object_type": "hacker_payload",
            "content_type": "image/jpeg",
            "filename": "test.jpg",
        })
        assert resp.status_code == 400
        assert "Invalid object_type" in resp.json()["detail"]["message"]

    def test_invalid_content_type_returns_400(self):
        """An unsupported MIME content_type should return 400."""
        resp = client.post("/storage/presign-upload", json={
            "object_type": "user_photo",
            "content_type": "application/x-executable",
            "filename": "test.bin",
        })
        assert resp.status_code == 400
        assert "Unsupported content_type" in resp.json()["detail"]["message"]

    def test_missing_filename_returns_422(self):
        """Missing filename in the body triggers 422."""
        resp = client.post("/storage/presign-upload", json={
            "object_type": "user_photo",
            "content_type": "image/jpeg",
        })
        assert resp.status_code == 422

    def test_missing_body_returns_422(self):
        """Sending no body returns 422."""
        resp = client.post("/storage/presign-upload")
        assert resp.status_code == 422

    def test_s3_unavailable_returns_503(self):
        """When S3 client is not configured, presigned upload returns 503."""
        with patch(
            "app.features.storage_router.generate_presigned_upload",
            return_value=None,
        ):
            resp = client.post("/storage/presign-upload", json={
                "object_type": "user_photo",
                "content_type": "image/jpeg",
                "filename": "test.jpg",
            })
        assert resp.status_code == 503
        assert "S3" in resp.json()["detail"]["message"]

    def test_all_allowed_object_types_accepted(self):
        """All five allowed object_type values should be accepted."""
        for otype in ("catalog_image", "user_photo", "market_dump", "embedding", "training_data"):
            with patch(
                "app.features.storage_router.generate_presigned_upload",
                return_value="https://example.com/upload",
            ):
                resp = client.post("/storage/presign-upload", json={
                    "object_type": otype,
                    "content_type": "application/octet-stream",
                    "filename": f"test_{otype}.bin",
                })
            assert resp.status_code == 200, f"object_type={otype} should be accepted"


# ---------------------------------------------------------------------------
# GET /storage/objects — scoped by user (created_by filter)
# ---------------------------------------------------------------------------


class TestListObjects:
    """Tests for GET /storage/objects with mocked DB."""

    def test_list_objects_scoped_by_user(self):
        """Objects list query includes created_by = user_id (RLS enforcement)."""
        conn, ctx = _mock_conn_ctx()
        now = datetime.now(timezone.utc)
        row = {
            "id": uuid4(),
            "s3_key": "user_photo/dev-user-local/abc_test.jpg",
            "bucket": "collectai-artifacts",
            "content_hash": None,
            "size_bytes": 12345,
            "content_type": "image/jpeg",
            "object_type": "user_photo",
            "related_item_id": None,
            "related_category": None,
            "created_by": "dev-user-local",
            "created_at": now,
            "metadata": None,
        }
        conn.fetch = AsyncMock(return_value=[row])

        with patch("app.features.storage_router.db_configured", return_value=True), \
             patch("app.features.storage_router.get_conn", return_value=ctx):
            resp = client.get("/storage/objects")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["objects"][0]["created_by"] == "dev-user-local"

        # Verify the query includes the created_by filter
        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "created_by" in query

    def test_list_objects_with_object_type_filter(self):
        """Filtering by object_type appends the filter to the query."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(return_value=[])

        with patch("app.features.storage_router.db_configured", return_value=True), \
             patch("app.features.storage_router.get_conn", return_value=ctx):
            resp = client.get("/storage/objects?object_type=user_photo")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["objects"] == []

        # Verify both created_by and object_type are in the query
        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "created_by" in query
        assert "object_type" in query

    def test_list_objects_invalid_object_type_returns_400(self):
        """An invalid object_type filter returns 400."""
        with patch("app.features.storage_router.db_configured", return_value=True):
            resp = client.get("/storage/objects?object_type=hacker")
        assert resp.status_code == 400

    def test_list_objects_db_not_configured_returns_503(self):
        """When DB is not configured, list objects returns 503."""
        resp = client.get("/storage/objects")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /storage/presign-download/{pointer_id} — only own objects
# ---------------------------------------------------------------------------


class TestPresignDownload:
    """Tests for GET /storage/presign-download/{pointer_id} with mocked DB."""

    def test_download_own_object_success(self):
        """When the object belongs to the user, return a download URL."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value={
            "s3_key": "user_photo/dev-user-local/abc_test.jpg",
            "bucket": "collectai-artifacts",
            "content_type": "image/jpeg",
            "size_bytes": 54321,
        })

        with patch("app.features.storage_router.db_configured", return_value=True), \
             patch("app.features.storage_router.get_conn", return_value=ctx), \
             patch("app.features.storage_router.get_cdn_url", return_value=None), \
             patch(
                 "app.features.storage_router.generate_presigned_download",
                 return_value="https://s3.example.com/download?sig=xyz",
             ):
            resp = client.get(f"/storage/presign-download/{POINTER_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["download_url"] == "https://s3.example.com/download?sig=xyz"
        assert data["content_type"] == "image/jpeg"
        assert data["size_bytes"] == 54321

        # Verify the query includes created_by (ownership filter)
        call_args = conn.fetchrow.call_args
        query = call_args[0][0]
        assert "created_by" in query

    def test_download_not_owned_returns_404(self):
        """When the object doesn't belong to the user (fetchrow returns None), return 404."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.features.storage_router.db_configured", return_value=True), \
             patch("app.features.storage_router.get_conn", return_value=ctx):
            resp = client.get(f"/storage/presign-download/{POINTER_ID}")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]["message"].lower()

    def test_download_cdn_url_preferred(self):
        """When CDN is configured, return CDN URL instead of presigned URL."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value={
            "s3_key": "user_photo/dev-user-local/abc_test.jpg",
            "bucket": "collectai-artifacts",
            "content_type": "image/png",
            "size_bytes": 999,
        })

        with patch("app.features.storage_router.db_configured", return_value=True), \
             patch("app.features.storage_router.get_conn", return_value=ctx), \
             patch(
                 "app.features.storage_router.get_cdn_url",
                 return_value="https://cdn.example.com/user_photo/dev-user-local/abc_test.jpg",
             ):
            resp = client.get(f"/storage/presign-download/{POINTER_ID}")

        assert resp.status_code == 200
        assert "cdn.example.com" in resp.json()["download_url"]

    def test_download_invalid_pointer_id_returns_400(self):
        """A non-UUID pointer_id returns 400."""
        with patch("app.features.storage_router.db_configured", return_value=True):
            resp = client.get("/storage/presign-download/not-a-uuid")
        assert resp.status_code == 400
        assert "Invalid pointer ID" in resp.json()["detail"]["message"]

    def test_download_db_not_configured_returns_503(self):
        """When DB is not configured, presign-download returns 503."""
        resp = client.get(f"/storage/presign-download/{POINTER_ID}")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# DELETE /storage/objects/{pointer_id} — only own objects
# ---------------------------------------------------------------------------


class TestDeleteObject:
    """Tests for DELETE /storage/objects/{pointer_id} with mocked DB."""

    def test_delete_own_object_success(self):
        """When the object belongs to the user, soft-delete succeeds."""
        conn, ctx = _mock_conn_ctx()
        conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("app.features.storage_router.db_configured", return_value=True), \
             patch("app.features.storage_router.get_conn", return_value=ctx):
            resp = client.delete(f"/storage/objects/{POINTER_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()

        # Verify the UPDATE includes created_by (ownership filter)
        call_args = conn.execute.call_args
        query = call_args[0][0]
        assert "created_by" in query

    def test_delete_not_owned_returns_404(self):
        """When the object doesn't belong to the user (UPDATE 0), return 404."""
        conn, ctx = _mock_conn_ctx()
        conn.execute = AsyncMock(return_value="UPDATE 0")

        with patch("app.features.storage_router.db_configured", return_value=True), \
             patch("app.features.storage_router.get_conn", return_value=ctx):
            resp = client.delete(f"/storage/objects/{POINTER_ID}")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]["message"].lower()

    def test_delete_invalid_pointer_id_returns_400(self):
        """A non-UUID pointer_id returns 400."""
        with patch("app.features.storage_router.db_configured", return_value=True):
            resp = client.delete("/storage/objects/not-a-uuid")
        assert resp.status_code == 400
        assert "Invalid pointer ID" in resp.json()["detail"]["message"]

    def test_delete_db_not_configured_returns_503(self):
        """When DB is not configured, delete returns 503."""
        resp = client.delete(f"/storage/objects/{POINTER_ID}")
        assert resp.status_code == 503
