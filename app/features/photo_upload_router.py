"""
User photo upload — generates presigned S3 URLs for direct upload from mobile app.

Path pattern: user-uploads/{user_id}/{item_id}/{uuid}.{ext}
Supports: JPEG, PNG, WebP (max 2MB, resized to 1200px max dimension)

Cost at 10K users (~600GB): ~$40/month (S3 $14 + CloudFront $26)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/photos", tags=["photos"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

S3_BUCKET = os.environ.get("USER_UPLOADS_S3_BUCKET", "collectai-artifacts")
CDN_URL = os.environ.get("USER_UPLOADS_CDN_URL", "")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")
MAX_UPLOAD_SIZE = int(os.environ.get("USER_UPLOADS_MAX_SIZE", "2097152"))  # 2MB
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


class DeletePhotoResponse(BaseModel):
    """Response for photo deletion."""
    success: bool
    message: str


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
        logger.error(f"[photo_upload] Failed to generate presigned URL: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {e}")

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


@router.delete("/{photo_key:path}", response_model=DeletePhotoResponse)
async def delete_photo(photo_key: str, user_id: str = Query(..., description="User ID for ownership verification")):
    """
    Delete a user's photo from S3.

    Verifies the photo_key starts with `user-uploads/{user_id}/`
    to prevent cross-user deletion.
    """
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
        logger.info(f"[photo_upload] Deleted photo: key={photo_key}, user={user_id}")
        return DeletePhotoResponse(success=True, message="Photo deleted successfully")
    except Exception as e:
        logger.error(f"[photo_upload] Failed to delete photo: key={photo_key}, error={e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete photo: {e}")


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
        logger.error(f"[photo_upload] Failed to list photos: user={user_id}, item={item_id}, error={e}")
        raise HTTPException(status_code=500, detail=f"Failed to list photos: {e}")
