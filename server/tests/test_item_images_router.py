"""
Tests for app/features/item_images_router.py — multi-photo per item with labels and ordering.

Covers:
  - GET  /items/{item_id}/images          — in-memory fallback + mocked DB
  - POST /items/{item_id}/images          — in-memory fallback + mocked DB
  - DELETE /items/{item_id}/images/{id}   — in-memory fallback + mocked DB
  - PUT  /items/{item_id}/images/reorder  — in-memory fallback + mocked DB
  - Edge cases: invalid UUIDs, invalid labels, bad content types, oversized files, empty files
"""

from __future__ import annotations

import io
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

VALID_ITEM_ID = str(uuid4())
VALID_IMAGE_ID = str(uuid4())
USER_ID = "dev-user-local"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_conn_ctx():
    """Create a mock async context manager mimicking get_conn() / pool.acquire()."""
    conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return conn, ctx


def _mock_pool_with(conn, ctx):
    """Return a MagicMock pool that yields conn from pool.acquire()."""
    pool = MagicMock()
    pool.acquire.return_value = ctx
    return pool


def _fake_upload_file(content: bytes = b"fake-image-bytes", content_type: str = "image/jpeg", filename: str = "test.jpg"):
    """Create a dict suitable for TestClient multipart files param."""
    return {"file": (filename, io.BytesIO(content), content_type)}


def _clear_mem_store():
    """Clear the in-memory fallback store between tests."""
    import app.features.item_images_router as mod
    mod._mem_item_images.clear()
    mod._mem_counter = 0


# ---------------------------------------------------------------------------
# GET /items/{item_id}/images — in-memory fallback
# ---------------------------------------------------------------------------


class TestListImagesInMemory:
    """Tests for GET /items/{item_id}/images when DB is disabled (in-memory)."""

    def test_empty_list_for_new_item(self):
        """New item has no images — returns empty list."""
        _clear_mem_store()
        item_id = str(uuid4())
        resp = client.get(f"/items/{item_id}/images")
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == item_id
        assert data["images"] == []
        assert data["total"] == 0

    def test_response_schema_fields(self):
        """Verify all expected top-level fields exist in response."""
        resp = client.get(f"/items/{str(uuid4())}/images")
        assert resp.status_code == 200
        data = resp.json()
        assert "images" in data
        assert "item_id" in data
        assert "total" in data
        assert isinstance(data["images"], list)
        assert isinstance(data["total"], int)

    def test_invalid_uuid_returns_400(self):
        """Non-UUID item_id returns 400 INVALID_UUID."""
        resp = client.get("/items/not-a-uuid/images")
        assert resp.status_code == 400
        detail = resp.json().get("detail", {})
        assert detail.get("code") == "INVALID_UUID"

    def test_list_after_add_returns_images(self):
        """After adding an image in-memory, listing returns it."""
        _clear_mem_store()
        item_id = str(uuid4())

        with patch("app.features.item_images_router._upload_image_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "https://cdn.example.com/test.jpg"
            resp = client.post(
                f"/items/{item_id}/images",
                files=_fake_upload_file(),
                data={"label": "front"},
            )
            assert resp.status_code == 200

        resp = client.get(f"/items/{item_id}/images")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["images"][0]["label"] == "front"
        assert data["images"][0]["image_url"] == "https://cdn.example.com/test.jpg"


# ---------------------------------------------------------------------------
# GET /items/{item_id}/images — mocked DB
# ---------------------------------------------------------------------------


class TestListImagesMockedDB:
    """Tests for GET /items/{item_id}/images with mocked database."""

    def test_happy_path_returns_images(self):
        """When item belongs to user and has images, return full list."""
        conn, ctx = _mock_conn_ctx()
        pool = _mock_pool_with(conn, ctx)

        now = datetime.now(timezone.utc).isoformat()
        img1_id = str(uuid4())
        item_id = str(uuid4())
        row1 = {
            "id": img1_id,
            "item_id": item_id,
            "image_url": "https://cdn.example.com/img1.jpg",
            "label": "front",
            "position": 0,
            "created_at": now,
        }

        # Ownership check succeeds
        conn.fetchrow = AsyncMock(side_effect=[
            {"id": item_id},  # _verify_item_ownership
            None,  # sentinel — will not be called but just in case
        ])
        conn.fetch = AsyncMock(return_value=[row1])

        with patch("app.features.item_images_router.get_db_pool", return_value=pool):
            resp = client.get(f"/items/{item_id}/images")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["images"][0]["id"] == img1_id
        assert data["images"][0]["label"] == "front"

    def test_item_not_owned_returns_404(self):
        """Ownership check fails — returns 404."""
        conn, ctx = _mock_conn_ctx()
        pool = _mock_pool_with(conn, ctx)

        # Ownership check returns None (no matching row)
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.features.item_images_router.get_db_pool", return_value=pool):
            resp = client.get(f"/items/{str(uuid4())}/images")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /items/{item_id}/images — in-memory fallback
# ---------------------------------------------------------------------------


class TestAddImageInMemory:
    """Tests for POST /items/{item_id}/images when DB is disabled."""

    def test_add_image_happy_path(self):
        """Adding an image with valid label succeeds."""
        _clear_mem_store()
        item_id = str(uuid4())

        with patch("app.features.item_images_router._upload_image_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "https://cdn.example.com/test.jpg"
            resp = client.post(
                f"/items/{item_id}/images",
                files=_fake_upload_file(),
                data={"label": "front"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == item_id
        assert data["image_url"] == "https://cdn.example.com/test.jpg"
        assert data["label"] == "front"
        assert data["position"] == 0
        assert "id" in data
        assert "created_at" in data

    def test_add_image_no_label(self):
        """Adding an image without a label succeeds (label is optional)."""
        _clear_mem_store()
        item_id = str(uuid4())

        with patch("app.features.item_images_router._upload_image_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "https://cdn.example.com/no-label.jpg"
            resp = client.post(
                f"/items/{item_id}/images",
                files=_fake_upload_file(),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] is None

    def test_add_image_increments_position(self):
        """Second image gets position=1."""
        _clear_mem_store()
        item_id = str(uuid4())

        with patch("app.features.item_images_router._upload_image_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "https://cdn.example.com/img.jpg"
            resp1 = client.post(f"/items/{item_id}/images", files=_fake_upload_file())
            resp2 = client.post(f"/items/{item_id}/images", files=_fake_upload_file())

        assert resp1.json()["position"] == 0
        assert resp2.json()["position"] == 1

    def test_invalid_label_returns_400(self):
        """Invalid label value returns 400 VALIDATION_ERROR."""
        resp = client.post(
            f"/items/{str(uuid4())}/images",
            files=_fake_upload_file(),
            data={"label": "INVALID_LABEL"},
        )
        assert resp.status_code == 400
        detail = resp.json().get("detail", {})
        assert detail.get("code") == "VALIDATION_ERROR"

    def test_invalid_content_type_returns_400(self):
        """Unsupported content type (e.g. image/gif) returns 400."""
        resp = client.post(
            f"/items/{str(uuid4())}/images",
            files=_fake_upload_file(content_type="image/gif"),
        )
        assert resp.status_code == 400
        detail = resp.json().get("detail", {})
        assert "Unsupported content type" in detail.get("message", "")

    def test_invalid_item_id_returns_400(self):
        """Non-UUID item_id returns 400."""
        resp = client.post(
            "/items/bad-uuid/images",
            files=_fake_upload_file(),
        )
        assert resp.status_code == 400

    def test_all_valid_labels_accepted(self):
        """Each valid label is accepted without error."""
        _clear_mem_store()
        valid_labels = ["front", "back", "detail", "box", "certificate", "damage", "other"]
        for label in valid_labels:
            item_id = str(uuid4())
            with patch("app.features.item_images_router._upload_image_file", new_callable=AsyncMock) as mock_upload:
                mock_upload.return_value = "https://cdn.example.com/test.jpg"
                resp = client.post(
                    f"/items/{item_id}/images",
                    files=_fake_upload_file(),
                    data={"label": label},
                )
            assert resp.status_code == 200, f"Label '{label}' should be accepted"

    def test_all_valid_content_types_accepted(self):
        """JPEG, PNG, and WebP content types are all accepted."""
        _clear_mem_store()
        for ct in ["image/jpeg", "image/png", "image/webp"]:
            item_id = str(uuid4())
            with patch("app.features.item_images_router._upload_image_file", new_callable=AsyncMock) as mock_upload:
                mock_upload.return_value = "https://cdn.example.com/test.jpg"
                resp = client.post(
                    f"/items/{item_id}/images",
                    files=_fake_upload_file(content_type=ct),
                )
            assert resp.status_code == 200, f"Content type '{ct}' should be accepted"


# ---------------------------------------------------------------------------
# DELETE /items/{item_id}/images/{image_id} — in-memory fallback
# ---------------------------------------------------------------------------


class TestDeleteImageInMemory:
    """Tests for DELETE /items/{item_id}/images/{image_id} when DB is disabled."""

    def test_delete_existing_image_via_mocked_db(self):
        """Deleting an existing image succeeds via mocked DB path.

        Note: in-memory image IDs use 'img-N' format which is not UUID-valid,
        so the DELETE endpoint (which validates UUID) is tested via mocked DB.
        """
        conn, ctx = _mock_conn_ctx()
        pool = _mock_pool_with(conn, ctx)

        item_id = str(uuid4())
        image_id = str(uuid4())

        conn.fetchrow = AsyncMock(side_effect=[
            {"id": item_id},  # _verify_item_ownership
            {"image_url": "https://cdn.example.com/test.jpg"},  # image row
        ])
        conn.execute = AsyncMock(return_value="DELETE 1")

        with patch("app.features.item_images_router.get_db_pool", return_value=pool), \
             patch("app.features.item_images_router._try_delete_s3"):
            resp = client.delete(f"/items/{item_id}/images/{image_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "Image deleted successfully"

    def test_delete_nonexistent_image_returns_404(self):
        """Deleting a non-existent image_id returns 404."""
        _clear_mem_store()
        item_id = str(uuid4())
        resp = client.delete(f"/items/{item_id}/images/{str(uuid4())}")
        assert resp.status_code == 404

    def test_delete_invalid_item_id_returns_400(self):
        """Non-UUID item_id in delete returns 400."""
        resp = client.delete(f"/items/not-uuid/images/{str(uuid4())}")
        assert resp.status_code == 400

    def test_delete_invalid_image_id_returns_400(self):
        """Non-UUID image_id in delete returns 400."""
        resp = client.delete(f"/items/{str(uuid4())}/images/bad-id")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /items/{item_id}/images/{image_id} — mocked DB
# ---------------------------------------------------------------------------


class TestDeleteImageMockedDB:
    """Tests for DELETE /items/{item_id}/images/{image_id} with mocked database."""

    def test_happy_path_deletes_image(self):
        """When ownership check passes and image exists, delete succeeds."""
        conn, ctx = _mock_conn_ctx()
        pool = _mock_pool_with(conn, ctx)

        item_id = str(uuid4())
        image_id = str(uuid4())

        # fetchrow calls: 1) ownership check, 2) get image for S3 cleanup
        conn.fetchrow = AsyncMock(side_effect=[
            {"id": item_id},  # _verify_item_ownership
            {"image_url": "https://cdn.example.com/test.jpg"},  # image row
        ])
        conn.execute = AsyncMock(return_value="DELETE 1")

        with patch("app.features.item_images_router.get_db_pool", return_value=pool), \
             patch("app.features.item_images_router._try_delete_s3"):
            resp = client.delete(f"/items/{item_id}/images/{image_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_image_not_found_returns_404(self):
        """When image does not exist for this item, returns 404."""
        conn, ctx = _mock_conn_ctx()
        pool = _mock_pool_with(conn, ctx)

        item_id = str(uuid4())
        image_id = str(uuid4())

        # Ownership succeeds, but image lookup returns None
        conn.fetchrow = AsyncMock(side_effect=[
            {"id": item_id},  # _verify_item_ownership
            None,  # image not found
        ])

        with patch("app.features.item_images_router.get_db_pool", return_value=pool):
            resp = client.delete(f"/items/{item_id}/images/{image_id}")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /items/{item_id}/images/reorder — in-memory fallback
# ---------------------------------------------------------------------------


class TestReorderImagesInMemory:
    """Tests for PUT /items/{item_id}/images/reorder when DB is disabled."""

    def test_reorder_happy_path(self):
        """Reordering in-memory images succeeds."""
        _clear_mem_store()
        item_id = str(uuid4())

        with patch("app.features.item_images_router._upload_image_file", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "https://cdn.example.com/img.jpg"
            r1 = client.post(f"/items/{item_id}/images", files=_fake_upload_file())
            r2 = client.post(f"/items/{item_id}/images", files=_fake_upload_file())

        id1 = r1.json()["id"]
        id2 = r2.json()["id"]

        # Reorder: put second image first
        resp = client.put(
            f"/items/{item_id}/images/reorder",
            json={"image_ids": [id2, id1]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["reordered_count"] == 2

    def test_reorder_invalid_item_id_returns_400(self):
        """Non-UUID item_id returns 400."""
        resp = client.put(
            "/items/bad-uuid/images/reorder",
            json={"image_ids": [str(uuid4())]},
        )
        assert resp.status_code == 400

    def test_reorder_empty_image_ids_returns_422(self):
        """Empty image_ids list is rejected by Pydantic validation (min_length=1)."""
        resp = client.put(
            f"/items/{str(uuid4())}/images/reorder",
            json={"image_ids": []},
        )
        assert resp.status_code == 422

    def test_reorder_missing_body_returns_422(self):
        """Missing request body returns 422."""
        resp = client.put(f"/items/{str(uuid4())}/images/reorder")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT /items/{item_id}/images/reorder — mocked DB
# ---------------------------------------------------------------------------


class TestReorderImagesMockedDB:
    """Tests for PUT /items/{item_id}/images/reorder with mocked database."""

    def test_happy_path_reorders(self):
        """When ownership passes and images exist, reorder succeeds."""
        conn, ctx = _mock_conn_ctx()
        pool = _mock_pool_with(conn, ctx)

        item_id = str(uuid4())
        img1 = str(uuid4())
        img2 = str(uuid4())

        # _verify_item_ownership
        conn.fetchrow = AsyncMock(return_value={"id": item_id})

        # Existing images for this item
        from uuid import UUID
        conn.fetch = AsyncMock(return_value=[
            {"id": UUID(img1)},
            {"id": UUID(img2)},
        ])
        conn.execute = AsyncMock(return_value="UPDATE 1")

        # Mock transaction context manager
        tx = MagicMock()
        tx.__aenter__ = AsyncMock(return_value=None)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)

        with patch("app.features.item_images_router.get_db_pool", return_value=pool):
            resp = client.put(
                f"/items/{item_id}/images/reorder",
                json={"image_ids": [img2, img1]},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["reordered_count"] == 2

    def test_image_not_belonging_returns_400(self):
        """An image_id not belonging to the item returns 400 VALIDATION_ERROR."""
        conn, ctx = _mock_conn_ctx()
        pool = _mock_pool_with(conn, ctx)

        item_id = str(uuid4())
        img_owned = str(uuid4())
        img_foreign = str(uuid4())

        conn.fetchrow = AsyncMock(return_value={"id": item_id})
        from uuid import UUID
        # Only img_owned belongs to this item
        conn.fetch = AsyncMock(return_value=[
            {"id": UUID(img_owned)},
        ])

        with patch("app.features.item_images_router.get_db_pool", return_value=pool):
            resp = client.put(
                f"/items/{item_id}/images/reorder",
                json={"image_ids": [img_owned, img_foreign]},
            )

        assert resp.status_code == 400
        detail = resp.json().get("detail", {})
        assert detail.get("code") == "VALIDATION_ERROR"

    def test_reorder_invalid_image_uuid_returns_400(self):
        """Non-UUID image_id in the list returns 400 INVALID_UUID."""
        conn, ctx = _mock_conn_ctx()
        pool = _mock_pool_with(conn, ctx)

        item_id = str(uuid4())
        conn.fetchrow = AsyncMock(return_value={"id": item_id})

        with patch("app.features.item_images_router.get_db_pool", return_value=pool):
            resp = client.put(
                f"/items/{item_id}/images/reorder",
                json={"image_ids": ["not-a-uuid"]},
            )

        assert resp.status_code == 400
        detail = resp.json().get("detail", {})
        assert detail.get("code") == "INVALID_UUID"
