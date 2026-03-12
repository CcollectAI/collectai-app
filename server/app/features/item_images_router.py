"""
Item images router — multi-photo per item with labels and ordering.

Endpoints:
- GET    /items/{item_id}/images              - List all images for an item
- POST   /items/{item_id}/images              - Add an image (multipart form with label)
- DELETE /items/{item_id}/images/{image_id}   - Remove an image
- PUT    /items/{item_id}/images/reorder      - Reorder images
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode
from app.config import (
    USER_UPLOADS_S3_BUCKET as S3_BUCKET,
    USER_UPLOADS_CDN_URL as CDN_URL,
    AWS_REGION,
)
from app.rate_limit import per_user_rate_limit

router = APIRouter(tags=["Item Images"])
logger = logging.getLogger(__name__)

# Rate limit: 30 uploads per hour per user
_upload_limit = per_user_rate_limit(30, window_seconds=3600, scope="item_image_upload")

VALID_LABELS = {"front", "back", "detail", "box", "certificate", "damage", "other"}

# ---------------------------------------------------------------------------
# In-memory fallback store
# ---------------------------------------------------------------------------

_mem_item_images: list[dict] = []
_mem_counter = 0


def _next_mem_id() -> str:
    global _mem_counter
    _mem_counter += 1
    return f"img-{_mem_counter}"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ItemImageResponse(BaseModel):
    id: str
    item_id: str
    image_url: str
    label: Optional[str] = None
    position: int = 0
    created_at: Optional[str] = None


class ItemImagesListResponse(BaseModel):
    images: list[ItemImageResponse]
    item_id: str
    total: int


class ReorderRequest(BaseModel):
    image_ids: List[str] = Field(..., min_length=1, max_length=50)


class ReorderResponse(BaseModel):
    success: bool
    reordered_count: int


class DeleteImageResponse(BaseModel):
    success: bool
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_uuid_or_none(s: str | None) -> UUID | None:
    if not s:
        return None
    try:
        return UUID(s)
    except (ValueError, AttributeError):
        return None


async def _verify_item_ownership(pool, item_id: UUID, user_id: str) -> bool:
    """Verify the item belongs to the user."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM public.items WHERE id = $1 AND user_id = $2::uuid",
            item_id,
            user_id,
        )
        return row is not None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/items/{item_id}/images", response_model=ItemImagesListResponse)
async def list_item_images(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """List all images for an item, ordered by position."""
    iid = _to_uuid_or_none(item_id)
    if iid is None:
        raise error_response(400, "Invalid item_id", code=ErrorCode.INVALID_UUID)

    pool = get_db_pool()

    if pool is not None:
        try:
            if not await _verify_item_ownership(pool, iid, user_id):
                raise error_response(404, "Item not found", code=ErrorCode.NOT_FOUND)

            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, item_id, image_url, label, position,
                           created_at::text
                    FROM public.item_images
                    WHERE item_id = $1
                    ORDER BY position ASC, created_at ASC
                    """,
                    iid,
                )
                images = [
                    ItemImageResponse(
                        id=str(r["id"]),
                        item_id=str(r["item_id"]),
                        image_url=r["image_url"],
                        label=r["label"],
                        position=r["position"],
                        created_at=r["created_at"],
                    )
                    for r in rows
                ]
                return ItemImagesListResponse(
                    images=images,
                    item_id=item_id,
                    total=len(images),
                )
        except Exception as exc:
            if hasattr(exc, "status_code"):
                raise
            logger.error("Failed to list item images: %s", exc)
            raise error_response(500, "Failed to list item images", code=ErrorCode.DB_ERROR)

    # In-memory fallback
    images = [
        ItemImageResponse(**img)
        for img in _mem_item_images
        if img["item_id"] == item_id
    ]
    images.sort(key=lambda x: x.position)
    return ItemImagesListResponse(images=images, item_id=item_id, total=len(images))


@router.post("/items/{item_id}/images", response_model=ItemImageResponse)
async def add_item_image(
    item_id: str,
    file: UploadFile = File(..., description="Image file (JPEG, PNG, or WebP)"),
    label: Optional[str] = Form(None, description="Image label (front, back, detail, box, certificate, damage, other)"),
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_upload_limit),
):
    """
    Add an image to an item.

    Accepts a multipart form with the image file and an optional label.
    The image is uploaded to S3 via the photo upload service, then the
    image URL is stored in the item_images table.
    """
    iid = _to_uuid_or_none(item_id)
    if iid is None:
        raise error_response(400, "Invalid item_id", code=ErrorCode.INVALID_UUID)

    # Validate label
    if label and label not in VALID_LABELS:
        raise error_response(
            400,
            f"Invalid label: {label}. Must be one of: {', '.join(sorted(VALID_LABELS))}",
            code=ErrorCode.VALIDATION_ERROR,
        )

    # Validate content type
    content_type = file.content_type or ""
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if content_type not in allowed_types:
        raise error_response(
            400,
            f"Unsupported content type: {content_type}. Allowed: {', '.join(sorted(allowed_types))}",
            code=ErrorCode.VALIDATION_ERROR,
        )

    pool = get_db_pool()

    if pool is not None:
        try:
            if not await _verify_item_ownership(pool, iid, user_id):
                raise error_response(404, "Item not found", code=ErrorCode.NOT_FOUND)

            # Upload image via photo upload service
            image_url = await _upload_image_file(file, item_id, user_id)

            # Get next position
            async with pool.acquire() as conn:
                max_pos_row = await conn.fetchrow(
                    "SELECT COALESCE(MAX(position), -1) AS max_pos FROM public.item_images WHERE item_id = $1",
                    iid,
                )
                next_position = (max_pos_row["max_pos"] + 1) if max_pos_row else 0

                row = await conn.fetchrow(
                    """
                    INSERT INTO public.item_images (item_id, image_url, label, position)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, item_id, image_url, label, position, created_at::text
                    """,
                    iid,
                    image_url,
                    label,
                    next_position,
                )

                logger.info(
                    "[item_images] Added image: item=%s, label=%s, position=%d, user=%s",
                    item_id,
                    label,
                    next_position,
                    user_id,
                )

                return ItemImageResponse(
                    id=str(row["id"]),
                    item_id=str(row["item_id"]),
                    image_url=row["image_url"],
                    label=row["label"],
                    position=row["position"],
                    created_at=row["created_at"],
                )
        except Exception as exc:
            if hasattr(exc, "status_code"):
                raise
            logger.error("Failed to add item image: %s", exc)
            raise error_response(500, "Failed to add item image", code=ErrorCode.DB_ERROR)

    # In-memory fallback
    image_url = await _upload_image_file(file, item_id, user_id)
    existing = [img for img in _mem_item_images if img["item_id"] == item_id]
    next_position = max((img["position"] for img in existing), default=-1) + 1
    img_id = _next_mem_id()
    img_data = {
        "id": img_id,
        "item_id": item_id,
        "image_url": image_url,
        "label": label,
        "position": next_position,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _mem_item_images.append(img_data)
    return ItemImageResponse(**img_data)


@router.delete("/items/{item_id}/images/{image_id}", response_model=DeleteImageResponse)
async def delete_item_image(
    item_id: str,
    image_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete an image from an item."""
    iid = _to_uuid_or_none(item_id)
    img_id = _to_uuid_or_none(image_id)

    if iid is None:
        raise error_response(400, "Invalid item_id", code=ErrorCode.INVALID_UUID)
    if img_id is None:
        raise error_response(400, "Invalid image_id", code=ErrorCode.INVALID_UUID)

    pool = get_db_pool()

    if pool is not None:
        try:
            if not await _verify_item_ownership(pool, iid, user_id):
                raise error_response(404, "Item not found", code=ErrorCode.NOT_FOUND)

            async with pool.acquire() as conn:
                # Get image URL before deletion (for optional S3 cleanup)
                img_row = await conn.fetchrow(
                    "SELECT image_url FROM public.item_images WHERE id = $1 AND item_id = $2",
                    img_id,
                    iid,
                )
                if not img_row:
                    raise error_response(404, "Image not found", code=ErrorCode.NOT_FOUND)

                await conn.execute(
                    "DELETE FROM public.item_images WHERE id = $1 AND item_id = $2",
                    img_id,
                    iid,
                )

                logger.info(
                    "[item_images] Deleted image: id=%s, item=%s, user=%s",
                    image_id,
                    item_id,
                    user_id,
                )

                # Optionally clean up S3 — best effort, don't fail the request
                _try_delete_s3(img_row["image_url"], user_id)

                return DeleteImageResponse(success=True, message="Image deleted successfully")
        except Exception as exc:
            if hasattr(exc, "status_code"):
                raise
            logger.error("Failed to delete item image: %s", exc)
            raise error_response(500, "Failed to delete item image", code=ErrorCode.DB_ERROR)

    # In-memory fallback
    before = len(_mem_item_images)
    remaining = [
        img
        for img in _mem_item_images
        if not (img["id"] == image_id and img["item_id"] == item_id)
    ]
    if len(remaining) == before:
        raise error_response(404, "Image not found", code=ErrorCode.NOT_FOUND)
    _mem_item_images.clear()
    _mem_item_images.extend(remaining)
    return DeleteImageResponse(success=True, message="Image deleted successfully")


@router.put("/items/{item_id}/images/reorder", response_model=ReorderResponse)
async def reorder_item_images(
    item_id: str,
    request: ReorderRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Reorder images for an item.

    The body should contain an array of image_ids in the desired order.
    Position 0 = first image (hero/cover), position 1 = second, etc.
    """
    iid = _to_uuid_or_none(item_id)
    if iid is None:
        raise error_response(400, "Invalid item_id", code=ErrorCode.INVALID_UUID)

    pool = get_db_pool()

    if pool is not None:
        try:
            if not await _verify_item_ownership(pool, iid, user_id):
                raise error_response(404, "Item not found", code=ErrorCode.NOT_FOUND)

            # Validate all image_ids are valid UUIDs
            image_uuids = []
            for img_id_str in request.image_ids:
                uid = _to_uuid_or_none(img_id_str)
                if uid is None:
                    raise error_response(
                        400,
                        f"Invalid image_id: {img_id_str}",
                        code=ErrorCode.INVALID_UUID,
                    )
                image_uuids.append(uid)

            async with pool.acquire() as conn:
                # Verify all images belong to this item
                existing = await conn.fetch(
                    "SELECT id FROM public.item_images WHERE item_id = $1",
                    iid,
                )
                existing_ids = {r["id"] for r in existing}
                for uid in image_uuids:
                    if uid not in existing_ids:
                        raise error_response(
                            400,
                            f"Image {uid} does not belong to item {item_id}",
                            code=ErrorCode.VALIDATION_ERROR,
                        )

                # Update positions in a transaction
                async with conn.transaction():
                    for idx, uid in enumerate(image_uuids):
                        await conn.execute(
                            "UPDATE public.item_images SET position = $1 WHERE id = $2 AND item_id = $3",
                            idx,
                            uid,
                            iid,
                        )

                logger.info(
                    "[item_images] Reordered %d images for item=%s, user=%s",
                    len(image_uuids),
                    item_id,
                    user_id,
                )

                return ReorderResponse(success=True, reordered_count=len(image_uuids))
        except Exception as exc:
            if hasattr(exc, "status_code"):
                raise
            logger.error("Failed to reorder item images: %s", exc)
            raise error_response(500, "Failed to reorder images", code=ErrorCode.DB_ERROR)

    # In-memory fallback
    count = 0
    for idx, img_id_str in enumerate(request.image_ids):
        for img in _mem_item_images:
            if img["id"] == img_id_str and img["item_id"] == item_id:
                img["position"] = idx
                count += 1
                break
    return ReorderResponse(success=True, reordered_count=count)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _upload_image_file(file: UploadFile, item_id: str, user_id: str) -> str:
    """
    Upload an image file using the existing photo upload infrastructure.

    Returns the CDN URL of the uploaded image.
    """
    import uuid as _uuid

    try:
        from app.lib.image_optimizer import optimize_image

        raw_bytes = await file.read()
        if len(raw_bytes) == 0:
            raise error_response(400, "Empty file", code=ErrorCode.VALIDATION_ERROR)

        max_raw = 10 * 1024 * 1024
        if len(raw_bytes) > max_raw:
            raise error_response(
                413,
                f"File too large ({len(raw_bytes)} bytes). Maximum: {max_raw} bytes (10 MB)",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Optimize image
        try:
            optimized_bytes, width, height = optimize_image(raw_bytes, max_edge=1200)
        except ValueError as e:
            raise error_response(400, str(e), code=ErrorCode.VALIDATION_ERROR)

        # Upload to S3
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError

            s3 = boto3.client("s3", region_name=AWS_REGION)
            filename = f"{_uuid.uuid4().hex}.jpg"
            photo_key = f"user-uploads/{user_id}/{item_id}/{filename}"

            s3.put_object(
                Bucket=S3_BUCKET,
                Key=photo_key,
                Body=optimized_bytes,
                ContentType="image/jpeg",
                CacheControl="public, max-age=31536000, immutable",
            )

            if CDN_URL:
                return f"{CDN_URL.rstrip('/')}/{photo_key}"
            return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{photo_key}"

        except ImportError:
            logger.warning("[item_images] boto3 not installed — using placeholder URL")
            return f"https://placeholder.collectai.app/{item_id}/{_uuid.uuid4().hex}.jpg"
        except (BotoCoreError, ClientError) as e:
            logger.error("[item_images] S3 upload failed: %s", e)
            raise error_response(500, "Failed to upload image", code="STORAGE_ERROR")

    except ImportError:
        # image_optimizer not available — store raw (dev mode)
        logger.warning("[item_images] image_optimizer not available — using placeholder URL")
        return f"https://placeholder.collectai.app/{item_id}/{_uuid.uuid4().hex}.jpg"


def _try_delete_s3(image_url: str, user_id: str) -> None:
    """Best-effort S3 cleanup of a deleted image."""
    try:
        # Extract the photo key from the URL
        if CDN_URL and image_url.startswith(CDN_URL):
            photo_key = image_url[len(CDN_URL.rstrip("/")) + 1 :]
        elif ".s3." in image_url and ".amazonaws.com/" in image_url:
            photo_key = image_url.split(".amazonaws.com/", 1)[1]
        else:
            return  # Can't determine key

        # Verify ownership prefix
        expected_prefix = f"user-uploads/{user_id}/"
        if not photo_key.startswith(expected_prefix):
            logger.warning("[item_images] S3 cleanup skipped — key doesn't match user: %s", photo_key)
            return

        import boto3

        s3 = boto3.client("s3", region_name=AWS_REGION)
        s3.delete_object(Bucket=S3_BUCKET, Key=photo_key)
        logger.info("[item_images] S3 cleanup: deleted %s", photo_key)
    except Exception as e:
        logger.warning("[item_images] S3 cleanup failed (non-critical): %s", e)
