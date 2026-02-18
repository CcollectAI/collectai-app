"""
Storage router -- presigned S3 URLs and object pointer management.

Provides endpoints for:
- Generating presigned upload URLs (PUT) for direct client-to-S3 uploads
- Generating presigned download URLs (GET) or CDN URLs for reading objects
- Listing objects by type or related item
- Soft-deleting object pointers

All S3 objects are tracked in the `object_pointers` table for auditing,
deduplication, and cross-referencing with items/categories.
"""

from __future__ import annotations

import logging
import os
import re
import uuid as _uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id

from app.db import db_configured, get_conn
from app.lib.s3_client import (
    DEFAULT_BUCKET,
    DEFAULT_EXPIRES_IN,
    generate_presigned_download,
    generate_presigned_upload,
    get_cdn_url,
    get_public_url,
)

router = APIRouter(prefix="/storage", tags=["storage"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed object types (whitelist)
# ---------------------------------------------------------------------------

ALLOWED_OBJECT_TYPES = frozenset({
    "catalog_image",
    "user_photo",
    "market_dump",
    "embedding",
    "training_data",
})

# Allowed content types for uploads
ALLOWED_CONTENT_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/json",
    "application/jsonl+gzip",
    "application/gzip",
    "application/octet-stream",
})

# Filename sanitisation pattern
_SAFE_FILENAME_RE = re.compile(r"[^\w.\-]")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class PresignUploadRequest(BaseModel):
    """Request body for generating a presigned upload URL."""

    object_type: str = Field(
        ...,
        description="Type of object: catalog_image, user_photo, market_dump, embedding, training_data",
    )
    content_type: str = Field(..., description="MIME type (e.g. image/jpeg)")
    filename: str = Field(..., description="Original filename", max_length=255)
    related_item_id: Optional[str] = Field(None, description="Optional item UUID")
    related_category: Optional[str] = Field(None, description="Optional category slug")


class PresignUploadResponse(BaseModel):
    """Response with presigned PUT URL and tracking metadata."""

    upload_url: str
    s3_key: str
    pointer_id: str
    expires_in: int


class PresignDownloadResponse(BaseModel):
    """Response with presigned GET URL (or CDN URL) and metadata."""

    download_url: str
    content_type: Optional[str]
    size_bytes: Optional[int]


class ObjectPointerOut(BaseModel):
    """Public representation of an object pointer."""

    id: str
    s3_key: str
    bucket: str
    content_hash: Optional[str]
    size_bytes: Optional[int]
    content_type: Optional[str]
    object_type: str
    related_item_id: Optional[str]
    related_category: Optional[str]
    created_by: str
    created_at: str
    metadata: Optional[dict]


class ObjectListResponse(BaseModel):
    """Paginated list of object pointers."""

    objects: List[ObjectPointerOut]
    count: int


class DeleteResponse(BaseModel):
    """Response for soft-delete."""

    success: bool
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_s3_key(
    object_type: str,
    filename: str,
    related_category: Optional[str] = None,
    created_by: str = "system",
) -> str:
    """
    Build a deterministic S3 key.

    Convention: {object_type}/{category_or_user}/{uuid}_{safe_filename}
    """
    safe_name = _SAFE_FILENAME_RE.sub("_", os.path.basename(filename))[:100]
    sub_folder = related_category or created_by
    unique_id = _uuid.uuid4().hex[:12]
    return f"{object_type}/{sub_folder}/{unique_id}_{safe_name}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/presign-upload", response_model=PresignUploadResponse)
async def presign_upload(request: PresignUploadRequest, user_id: str = Depends(get_current_user_id)):
    """
    Generate a presigned PUT URL for direct upload to S3.

    Inserts a pointer row into `object_pointers` to track the object.
    The client should PUT raw bytes to the returned `upload_url` with
    the matching Content-Type header.
    """
    # Validate object_type
    if request.object_type not in ALLOWED_OBJECT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid object_type. Allowed: {', '.join(sorted(ALLOWED_OBJECT_TYPES))}",
        )

    # Validate content_type
    if request.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content_type. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    # Validate filename
    if not request.filename or not request.filename.strip():
        raise HTTPException(status_code=400, detail="filename is required")

    created_by = user_id

    s3_key = _build_s3_key(
        object_type=request.object_type,
        filename=request.filename,
        related_category=request.related_category,
        created_by=created_by,
    )

    # Generate presigned upload URL
    upload_url = generate_presigned_upload(
        bucket=DEFAULT_BUCKET,
        key=s3_key,
        content_type=request.content_type,
        expires_in=DEFAULT_EXPIRES_IN,
    )
    if upload_url is None:
        raise HTTPException(
            status_code=503,
            detail="S3 is not configured or unavailable",
        )

    # Insert pointer into DB (if DB is available)
    pointer_id = str(_uuid.uuid4())
    if db_configured():
        try:
            async with get_conn() as conn:
                await conn.execute(
                    """
                    INSERT INTO object_pointers
                        (id, s3_key, bucket, content_type, object_type,
                         related_item_id, related_category, created_by, created_at, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    _uuid.UUID(pointer_id),
                    s3_key,
                    DEFAULT_BUCKET,
                    request.content_type,
                    request.object_type,
                    request.related_item_id,
                    request.related_category,
                    created_by,
                    datetime.now(timezone.utc),
                    "{}",
                )
        except Exception as e:
            logger.warning("Failed to insert object pointer into DB: %s", e)
            # Continue -- the upload URL is still valid; pointer can be reconciled later
    else:
        logger.info("DB not configured; skipping object_pointers insert for %s", s3_key)

    logger.info(
        "Presigned upload URL generated: type=%s, key=%s, pointer=%s",
        request.object_type,
        s3_key,
        pointer_id,
    )

    return PresignUploadResponse(
        upload_url=upload_url,
        s3_key=s3_key,
        pointer_id=pointer_id,
        expires_in=DEFAULT_EXPIRES_IN,
    )


@router.get("/presign-download/{pointer_id}", response_model=PresignDownloadResponse)
async def presign_download(pointer_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Generate a presigned GET URL for downloading an object.

    If a CDN is configured, returns the CDN URL directly (no presigning needed).
    Otherwise generates a presigned S3 GET URL.
    """
    # Validate pointer_id format
    try:
        _uuid.UUID(pointer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pointer ID format")

    if not db_configured():
        raise HTTPException(status_code=503, detail="Database not configured")

    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT s3_key, bucket, content_type, size_bytes
                FROM object_pointers
                WHERE id = $1 AND deleted_at IS NULL AND created_by = $2
                """,
                _uuid.UUID(pointer_id),
                user_id,
            )
    except Exception as e:
        logger.error("Failed to look up object pointer %s: %s", pointer_id, e)
        raise HTTPException(status_code=500, detail="Failed to look up object")

    if row is None:
        raise HTTPException(status_code=404, detail="Object not found")

    s3_key = row["s3_key"]
    bucket = row["bucket"]
    content_type = row["content_type"]
    size_bytes = row["size_bytes"]

    # Prefer CDN URL if configured
    cdn = get_cdn_url(s3_key)
    if cdn:
        return PresignDownloadResponse(
            download_url=cdn,
            content_type=content_type,
            size_bytes=size_bytes,
        )

    # Otherwise generate presigned download URL
    download_url = generate_presigned_download(
        bucket=bucket,
        key=s3_key,
        expires_in=DEFAULT_EXPIRES_IN,
    )
    if download_url is None:
        raise HTTPException(
            status_code=503,
            detail="S3 is not configured or unavailable",
        )

    return PresignDownloadResponse(
        download_url=download_url,
        content_type=content_type,
        size_bytes=size_bytes,
    )


@router.get("/objects", response_model=ObjectListResponse)
async def list_objects(
    object_type: Optional[str] = Query(None, description="Filter by object type"),
    related_item_id: Optional[str] = Query(None, description="Filter by related item ID"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user_id: str = Depends(get_current_user_id),
):
    """
    List object pointers, optionally filtered by type and/or related item.

    Only returns non-deleted pointers, ordered by creation time (newest first).
    """
    if not db_configured():
        raise HTTPException(status_code=503, detail="Database not configured")

    # Validate object_type if provided
    if object_type and object_type not in ALLOWED_OBJECT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid object_type. Allowed: {', '.join(sorted(ALLOWED_OBJECT_TYPES))}",
        )

    # Build query dynamically — always scope to current user
    conditions = ["deleted_at IS NULL"]
    params: list = []
    param_idx = 1
    conditions.append(f"created_by = ${param_idx}")
    params.append(user_id)

    if object_type:
        param_idx += 1
        conditions.append(f"object_type = ${param_idx}")
        params.append(object_type)

    if related_item_id:
        param_idx += 1
        conditions.append(f"related_item_id = ${param_idx}")
        params.append(related_item_id)

    where_clause = " AND ".join(conditions)

    param_idx += 1
    limit_param = param_idx
    params.append(limit)

    param_idx += 1
    offset_param = param_idx
    params.append(offset)

    query = f"""
        SELECT id, s3_key, bucket, content_hash, size_bytes, content_type,
               object_type, related_item_id, related_category, created_by,
               created_at, metadata
        FROM object_pointers
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ${limit_param} OFFSET ${offset_param}
    """

    try:
        async with get_conn() as conn:
            rows = await conn.fetch(query, *params)
    except Exception as e:
        logger.error("Failed to list object pointers: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list objects")

    objects = []
    for row in rows:
        objects.append(
            ObjectPointerOut(
                id=str(row["id"]),
                s3_key=row["s3_key"],
                bucket=row["bucket"],
                content_hash=row["content_hash"],
                size_bytes=row["size_bytes"],
                content_type=row["content_type"],
                object_type=row["object_type"],
                related_item_id=row["related_item_id"],
                related_category=row["related_category"],
                created_by=row["created_by"],
                created_at=row["created_at"].isoformat() if row["created_at"] else "",
                metadata=dict(row["metadata"]) if row["metadata"] else None,
            )
        )

    return ObjectListResponse(objects=objects, count=len(objects))


@router.delete("/objects/{pointer_id}", response_model=DeleteResponse)
async def delete_object(pointer_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Soft-delete an object pointer.

    Sets `deleted_at` timestamp on the pointer row. Does NOT remove the
    actual S3 object -- a separate cleanup job can handle that later.
    """
    # Validate pointer_id format
    try:
        _uuid.UUID(pointer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pointer ID format")

    if not db_configured():
        raise HTTPException(status_code=503, detail="Database not configured")

    try:
        async with get_conn() as conn:
            result = await conn.execute(
                """
                UPDATE object_pointers
                SET deleted_at = $1
                WHERE id = $2 AND deleted_at IS NULL AND created_by = $3
                """,
                datetime.now(timezone.utc),
                _uuid.UUID(pointer_id),
                user_id,
            )
    except Exception as e:
        logger.error("Failed to soft-delete object pointer %s: %s", pointer_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete object")

    # asyncpg returns "UPDATE N" where N is affected row count
    if result and result.endswith("0"):
        raise HTTPException(status_code=404, detail="Object not found or already deleted")

    logger.info("Soft-deleted object pointer: %s", pointer_id)

    return DeleteResponse(success=True, message="Object marked as deleted")
