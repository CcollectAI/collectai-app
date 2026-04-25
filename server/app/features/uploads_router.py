"""Presigned-URL upload endpoint.

POST /uploads/presign — returns a presigned S3 PUT URL the client uses
to upload a single image directly to S3, bypassing the backend.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.lib.s3_storage import (
    ALLOWED_CONTENT_TYPES,
    KIND_PREFIXES,
    presign_get,
    presign_put,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/uploads", tags=["Uploads"])


class PresignRequest(BaseModel):
    kind: str = Field(..., description="Logical bucket: " + ", ".join(sorted(KIND_PREFIXES)))
    filename: str = Field(..., min_length=1, max_length=200,
                          description="Filename (no path components)")
    content_type: str = Field(..., description="image/jpeg, image/png, image/webp, etc.")


class PresignResponse(BaseModel):
    upload_url: str
    object_key: str
    public_url: str
    max_bytes: int
    expires_in: int


@router.post("/presign", response_model=PresignResponse,
             summary="Get a presigned S3 PUT URL for direct image upload")
async def presign(payload: PresignRequest, user_id: str = Depends(get_current_user_id)) -> PresignResponse:
    if payload.kind not in KIND_PREFIXES:
        raise HTTPException(400, f"unknown kind: {payload.kind}")
    if payload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, f"content_type not allowed: {payload.content_type}")
    try:
        result = presign_put(
            kind=payload.kind,
            user_id=user_id,
            filename=payload.filename,
            content_type=payload.content_type,
        )
        return PresignResponse(**result)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("presign failed: %s", e)
        raise HTTPException(502, f"Presign failed: {e!s}")


class SignedGetRequest(BaseModel):
    object_key: str = Field(..., min_length=3, max_length=400)
    expires_in: Optional[int] = Field(None, ge=60, le=3600)


@router.post("/signed-get", response_model=dict,
             summary="Get a short-lived signed GET URL for a private object")
async def signed_get(payload: SignedGetRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    # Authorization: caller must own the object. Object keys are
    # namespaced as `<kind>/<user_id>/<filename>`; require user_id to
    # appear as the second path component.
    parts = payload.object_key.split("/", 2)
    if len(parts) < 3 or parts[1] != user_id:
        raise HTTPException(403, "Not your object")
    try:
        url = presign_get(object_key=payload.object_key, expires_in=payload.expires_in)
        return {"url": url, "expires_in": payload.expires_in or 600}
    except Exception as e:
        logger.exception("signed_get failed: %s", e)
        raise HTTPException(502, f"Signed-get failed: {e!s}")
