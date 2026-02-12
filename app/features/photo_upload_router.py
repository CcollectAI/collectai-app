"""
User photo upload — presigned S3 URLs *and* server-side optimized upload.

Path pattern: user-uploads/{user_id}/{item_id}/{uuid}.{ext}
Supports: JPEG, PNG, WebP (max 10 MB raw; optimized to JPEG q85, 1200 px max edge)

Server-side upload flow (/photos/upload):
  1. Client POSTs multipart/form-data with the raw image
  2. Server resizes to 1200 px max edge, converts to JPEG q85, strips EXIF
  3. Server generates a blurhash placeholder string
  4. Server uploads the optimized bytes to S3
  5. Returns CDN URL + blurhash + dimensions

Cost at 10K users (~600GB): ~$40/month (S3 $14 + CloudFront $26)
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.config import (
    USER_UPLOADS_S3_BUCKET as S3_BUCKET,
    USER_UPLOADS_CDN_URL as CDN_URL,
    AWS_REGION,
    USER_UPLOADS_MAX_SIZE as MAX_UPLOAD_SIZE,
)
from app.lib.image_optimizer import generate_blurhash, optimize_image

router = APIRouter(prefix="/photos", tags=["photos"])
logger = logging.getLogger(__name__)
PRESIGN_EXPIRY = 300  # 5 minutes

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

# ---------------------------------------------------------------------------
# Lazy S3 client
# ---------------------------------------------------------------------------

_s3_client = None


def _get_s3():
    """Lazy-init boto3 S3 client."""
    global _s3_client
    if _s3_client is None:
        try:
            import boto3
            _s3_client = boto3.client("s3", region_name=AWS_REGION)
            logger.info(f"[photo_upload] S3 client initialized: bucket={S3_BUCKET}, region={AWS_REGION}")
        except ImportError:
            logger.warning("[photo_upload] boto3 not installed — photo upload will not work")
            return None
        except Exception as e:
            logger.error(f"[photo_upload] Failed to init S3 client: {e}")
            return None
    return _s3_client


def _public_url(key: str) -> str:
    """Generate public URL for an uploaded photo."""
    if CDN_URL:
        return f"{CDN_URL.rstrip('/')}/{key}"
    return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class PresignUploadRequest(BaseModel):
    """Request body for generating a presigned upload URL."""
    item_id: str = Field(..., description="UUID of the item to attach the photo to")
    content_type: str = Field(..., description="MIME type of the image (image/jpeg, image/png, image/webp)")
    user_id: str = Field(..., description="UUID of the user uploading the photo")


class PresignUploadResponse(BaseModel):
    """Response with presigned URL and metadata."""
    upload_url: str = Field(..., description="Presigned S3 PUT URL (valid for 5 minutes)")
    photo_key: str = Field(..., description="S3 object key for the uploaded photo")
    cdn_url: str = Field(..., description="Public URL for the photo after upload (CDN or S3)")


class PhotoInfo(BaseModel):
    """Info about a single photo."""
    photo_key: str
    cdn_url: str
    size: Optional[int] = None
    last_modified: Optional[str] = None


class PhotoListResponse(BaseModel):
    """Response for listing photos."""
    photos: list[PhotoInfo]
    item_id: str


class ServerUploadResponse(BaseModel):
    """Response from the server-side optimized upload endpoint."""
    photo_key: str = Field(..., description="S3 object key for the uploaded photo")
    cdn_url: str = Field(..., description="Public URL for the optimized photo")
    blurhash: str = Field(..., description="Blurhash placeholder string for progressive loading")
    width: int = Field(..., description="Width of the optimized image in pixels")
    height: int = Field(..., description="Height of the optimized image in pixels")
    original_size: int = Field(..., description="Original file size in bytes")
    optimized_size: int = Field(..., description="Optimized file size in bytes")


class DeletePhotoResponse(BaseModel):
    """Response for photo deletion."""
    success: bool
    message: str


# Maximum raw upload size: 10 MB (before optimization)
MAX_RAW_UPLOAD = 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/presign-upload", response_model=PresignUploadResponse)
async def presign_upload(request: PresignUploadRequest):
    """
    Generate a presigned S3 PUT URL for direct upload from the mobile app.

    The client should PUT the raw image bytes to the returned `upload_url`
    with the matching Content-Type header. After a successful upload,
    the image is immediately available at `cdn_url`.

    Key format: user-uploads/{user_id}/{item_id}/{uuid}.{ext}
    """
    # Validate content type
    if request.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type: {request.content_type}. "
                   f"Allowed: {', '.join(ALLOWED_CONTENT_TYPES.keys())}",
        )

    # Validate user_id and item_id are non-empty
    if not request.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    if not request.item_id.strip():
        raise HTTPException(status_code=400, detail="item_id is required")

    s3 = _get_s3()
    if s3 is None:
        raise HTTPException(
            status_code=503,
            detail="S3 is not configured — photo upload is unavailable",
        )

    # Generate unique filename
    ext = ALLOWED_CONTENT_TYPES[request.content_type]
    filename = f"{uuid.uuid4().hex}.{ext}"
    photo_key = f"user-uploads/{request.user_id}/{request.item_id}/{filename}"

    try:
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": photo_key,
                "ContentType": request.content_type,
            },
            ExpiresIn=PRESIGN_EXPIRY,
        )
    except Exception as e:
        logger.error("[photo_upload] Failed to generate presigned URL: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")

    cdn_url = _public_url(photo_key)

    logger.info(
        f"[photo_upload] Presigned URL generated: user={request.user_id}, "
        f"item={request.item_id}, key={photo_key}"
    )

    return PresignUploadResponse(
        upload_url=upload_url,
        photo_key=photo_key,
        cdn_url=cdn_url,
    )


@router.post("/upload", response_model=ServerUploadResponse)
async def upload_photo(
    file: UploadFile = File(..., description="Image file (JPEG, PNG, or WebP)"),
    item_id: str = Form(..., description="UUID of the item to attach the photo to"),
    user_id: str = Form(..., description="UUID of the user uploading the photo"),
):
    """
    Server-side optimized photo upload.

    Accepts a raw image, optimizes it (resize to 1200 px max edge, JPEG q85,
    strip EXIF), generates a blurhash placeholder, uploads to S3, and returns
    the CDN URL + blurhash + dimensions.

    The frontend should prefer this endpoint over presign-upload to benefit
    from automatic image optimization and blurhash generation.
    """
    # Validate user_id and item_id
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    if not item_id.strip():
        raise HTTPException(status_code=400, detail="item_id is required")

    # Validate content type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type: {content_type}. "
                   f"Allowed: {', '.join(ALLOWED_CONTENT_TYPES.keys())}",
        )

    # Read file bytes
    raw_bytes = await file.read()
    original_size = len(raw_bytes)

    if original_size > MAX_RAW_UPLOAD:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({original_size} bytes). Maximum: {MAX_RAW_UPLOAD} bytes (10 MB)",
        )

    if original_size == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Optimize image
    try:
        optimized_bytes, width, height = optimize_image(raw_bytes, max_edge=1200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("[photo_upload] Image optimization failed: %s", e)
        raise HTTPException(status_code=500, detail="Image optimization failed")

    # Generate blurhash (non-blocking — runs on the original bytes for accuracy)
    try:
        blurhash = generate_blurhash(raw_bytes, x_components=4, y_components=4)
    except Exception as e:
        logger.warning("[photo_upload] Blurhash generation failed: %s", e)
        blurhash = "C:808080:0:0"

    # Upload optimized image to S3
    s3 = _get_s3()
    if s3 is None:
        raise HTTPException(
            status_code=503,
            detail="S3 is not configured — photo upload is unavailable",
        )

    # Always store as JPEG since we convert during optimization
    filename = f"{uuid.uuid4().hex}.jpg"
    photo_key = f"user-uploads/{user_id}/{item_id}/{filename}"

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=photo_key,
            Body=optimized_bytes,
            ContentType="image/jpeg",
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as e:
        logger.error("[photo_upload] S3 upload failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to upload photo to S3")

    cdn_url = _public_url(photo_key)

    logger.info(
        "[photo_upload] Server-side upload complete: user=%s, item=%s, "
        "key=%s, %d->%d bytes (%dx%d), blurhash=%s",
        user_id, item_id, photo_key,
        original_size, len(optimized_bytes), width, height, blurhash[:12],
    )

    return ServerUploadResponse(
        photo_key=photo_key,
        cdn_url=cdn_url,
        blurhash=blurhash,
        width=width,
        height=height,
        original_size=original_size,
        optimized_size=len(optimized_bytes),
    )


@router.delete("/{photo_key:path}", response_model=DeletePhotoResponse)
async def delete_photo(photo_key: str, user_id: str = Query(..., description="User ID for ownership verification")):
    """
    Delete a user's photo from S3.

    Verifies the photo_key starts with `user-uploads/{user_id}/`
    to prevent cross-user deletion.
    """
    # Security: reject path traversal attempts
    if ".." in photo_key:
        raise HTTPException(status_code=400, detail="Invalid photo key")

    # Security: verify the photo belongs to the requesting user
    expected_prefix = f"user-uploads/{user_id}/"
    if not photo_key.startswith(expected_prefix):
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own photos",
        )

    s3 = _get_s3()
    if s3 is None:
        raise HTTPException(
            status_code=503,
            detail="S3 is not configured — photo deletion is unavailable",
        )

    try:
        s3.delete_object(Bucket=S3_BUCKET, Key=photo_key)
        logger.info("[photo_upload] Deleted photo: key=%s, user=%s", photo_key, user_id)
        return DeletePhotoResponse(success=True, message="Photo deleted successfully")
    except Exception as e:
        logger.error("[photo_upload] Failed to delete photo: key=%s, error=%s", photo_key, e)
        raise HTTPException(status_code=500, detail="Failed to delete photo")


@router.get("/list/{item_id}", response_model=PhotoListResponse)
async def list_photos(item_id: str, user_id: str = Query(..., description="User ID to scope photo listing")):
    """
    List all photos for an item belonging to a specific user.

    Uses S3 list_objects_v2 with prefix `user-uploads/{user_id}/{item_id}/`.
    """
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    if not item_id.strip():
        raise HTTPException(status_code=400, detail="item_id is required")

    s3 = _get_s3()
    if s3 is None:
        raise HTTPException(
            status_code=503,
            detail="S3 is not configured — photo listing is unavailable",
        )

    prefix = f"user-uploads/{user_id}/{item_id}/"

    try:
        response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
        photos: list[PhotoInfo] = []

        for obj in response.get("Contents", []):
            key = obj["Key"]
            photos.append(PhotoInfo(
                photo_key=key,
                cdn_url=_public_url(key),
                size=obj.get("Size"),
                last_modified=obj["LastModified"].isoformat() if obj.get("LastModified") else None,
            ))

        logger.info(f"[photo_upload] Listed {len(photos)} photos: user={user_id}, item={item_id}")

        return PhotoListResponse(photos=photos, item_id=item_id)

    except Exception as e:
        logger.error("[photo_upload] Failed to list photos: user=%s, item=%s, error=%s", user_id, item_id, e)
        raise HTTPException(status_code=500, detail="Failed to list photos")
