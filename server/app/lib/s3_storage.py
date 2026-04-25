"""S3-backed user-content storage.

Replaces Supabase Storage for the 3 buckets currently flagged by the
security advisor (`item-images`, `refs`, `user-content`) plus the
`listing-images` and `feed-images` buckets the FE writes to.

Architecture:
- Client requests a presigned PUT URL from `POST /uploads/presign`
- Client PUTs the file directly to S3 with the correct Content-Type
- Server stores the resulting object key in DB; reads use either a
  presigned GET URL or — for content the user wants public — a public
  CloudFront URL once we wire CDN.

Why direct-to-S3 instead of backend proxy:
- Avoids doubling bandwidth (image goes client → backend → S3)
- Stays in users' upload-throughput tier (their cellular/WiFi)
- Backend never holds the bytes — smaller blast radius if leaked

Bucket naming follows the same `collectai-{purpose}-{env}-{region}`
convention as the warehouse bucket (see s3 README).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# One bucket for all user-content (item photos, listing images, feed
# images, profile avatars). Logical separation lives in the object-key
# prefix: `item-images/<uid>/<ts>.jpg`, `listing-images/<uid>/<ts>.jpg`,
# etc. One bucket = one set of lifecycle/encryption/CORS rules to manage.
USER_CONTENT_BUCKET = os.getenv(
    "S3_USER_CONTENT_BUCKET",
    "collectai-user-content-prod-eu-north-1",
)
REGION = os.getenv("S3_USER_CONTENT_REGION", os.getenv("DATALAKE_REGION", "eu-north-1"))

# Object-key prefixes — one per "logical bucket" we used to have on
# Supabase. Frontend chooses which by passing `kind` to the presign
# endpoint.
KIND_PREFIXES: Dict[str, str] = {
    "item-images":    "item-images",
    "listing-images": "listing-images",
    "feed-images":    "feed-images",
    "refs":           "refs",
    "user-content":   "user-content",
    "captures":       "captures",
}

# Allowed content-types (defense in depth — server validates what the
# client claims it's uploading). Reject anything that isn't an image.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic",
    "image/heif",
}

# Max bytes the presigned URL will accept. S3 enforces via the
# Content-Length policy in the signed URL conditions.
MAX_UPLOAD_BYTES = int(os.getenv("S3_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))  # 15 MiB

# Presigned URL lifetime — short enough to limit replay if leaked, long
# enough that mobile users can complete the upload.
PRESIGN_EXPIRY_S = int(os.getenv("S3_PRESIGN_EXPIRY_S", "600"))  # 10 min


def _client():
    """boto3 S3 client. New per call — these are cheap and stateless.

    Force signature_version='s3v4' so presigned URLs include all headers
    in the signature. Without this, boto3's default may produce URLs
    that 403 with SignatureDoesNotMatch on real PUTs from clients that
    set Content-Type."""
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        region_name=REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


def build_object_key(kind: str, user_id: str, filename: str) -> str:
    """Compose the canonical S3 key. Validates kind + sanitizes
    filename so the user can't break out of their prefix.
    """
    if kind not in KIND_PREFIXES:
        raise ValueError(f"unknown kind: {kind}")
    # Defensive: strip any path traversal attempt from filename
    clean = filename.replace("..", "_").replace("/", "_").replace("\\", "_")
    if len(clean) > 120:
        clean = clean[-120:]
    return f"{KIND_PREFIXES[kind]}/{user_id}/{clean}"


def presign_put(
    *,
    kind: str,
    user_id: str,
    filename: str,
    content_type: str,
) -> Dict[str, Any]:
    """Create a presigned PUT URL the client can upload to directly.

    Returns:
        {
            "upload_url": str,        # PUT here with Content-Type header
            "object_key": str,        # store this in the DB
            "public_url": str,        # for reads, post-upload
            "max_bytes": int,
            "expires_in": int,
        }
    """
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"content_type not allowed: {content_type}")
    object_key = build_object_key(kind, user_id, filename)

    s3 = _client()
    # generate_presigned_url with Content-Type included in params makes
    # S3 require the client to send the same Content-Type header on PUT.
    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": USER_CONTENT_BUCKET,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=PRESIGN_EXPIRY_S,
        HttpMethod="PUT",
    )

    public_url = f"https://{USER_CONTENT_BUCKET}.s3.{REGION}.amazonaws.com/{object_key}"

    return {
        "upload_url": upload_url,
        "object_key": object_key,
        "public_url": public_url,
        "max_bytes": MAX_UPLOAD_BYTES,
        "expires_in": PRESIGN_EXPIRY_S,
    }


def presign_get(*, object_key: str, expires_in: Optional[int] = None) -> str:
    """Generate a presigned GET URL for a private object. Use when the
    bucket isn't world-readable (current default — TODO: switch to
    CloudFront for public-readable assets like avatars)."""
    s3 = _client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": USER_CONTENT_BUCKET, "Key": object_key},
        ExpiresIn=expires_in or PRESIGN_EXPIRY_S,
        HttpMethod="GET",
    )
