"""
Shared S3 client module for CollectAI backend.

Provides:
- Lazy-initialized boto3 S3 client (configured from env vars)
- Presigned URL generation for uploads and downloads
- CDN URL resolution (CloudFront)

Environment variables:
    AWS_ACCESS_KEY_ID       - AWS credentials (read by boto3 automatically)
    AWS_SECRET_ACCESS_KEY   - AWS credentials (read by boto3 automatically)
    AWS_REGION              - AWS region (default: eu-west-1)
    CATALOG_IMAGES_S3_BUCKET - Default S3 bucket (default: collectai-artifacts)
    CATALOG_IMAGES_CDN_URL  - Optional CloudFront distribution URL
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import (
    AWS_REGION,
    CATALOG_IMAGES_S3_BUCKET as DEFAULT_BUCKET,
    CATALOG_IMAGES_CDN_URL as CDN_URL,
)

logger = logging.getLogger(__name__)

# Default presigned URL expiry
DEFAULT_EXPIRES_IN = 3600  # 1 hour

# ---------------------------------------------------------------------------
# Lazy S3 client
# ---------------------------------------------------------------------------

_s3_client = None
_s3_init_attempted = False


def get_s3_client():
    """
    Returns a configured boto3 S3 client.

    Uses env vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION.
    Returns None if boto3 is not installed or credentials are missing.
    The result is cached for subsequent calls.
    """
    global _s3_client, _s3_init_attempted

    if _s3_init_attempted:
        return _s3_client

    _s3_init_attempted = True

    try:
        import boto3
        from botocore.config import Config

        config = Config(
            region_name=AWS_REGION,
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        )
        _s3_client = boto3.client("s3", config=config)
        logger.info("S3 client initialized: region=%s, bucket=%s", AWS_REGION, DEFAULT_BUCKET)
        return _s3_client

    except ImportError:
        logger.warning("boto3 is not installed -- S3 operations will be unavailable")
        return None
    except Exception as e:
        logger.warning("Failed to initialize S3 client: %s", e)
        return None


def reset_client() -> None:
    """Reset the cached client (useful for testing)."""
    global _s3_client, _s3_init_attempted
    _s3_client = None
    _s3_init_attempted = False


# ---------------------------------------------------------------------------
# Presigned URL generation
# ---------------------------------------------------------------------------


def generate_presigned_upload(
    bucket: str,
    key: str,
    content_type: str,
    expires_in: int = DEFAULT_EXPIRES_IN,
) -> Optional[str]:
    """
    Generate a presigned PUT URL for uploading an object to S3.

    Args:
        bucket: S3 bucket name.
        key: S3 object key.
        content_type: MIME type of the object (e.g. 'image/jpeg').
        expires_in: URL expiry in seconds (default 3600).

    Returns:
        Presigned URL string, or None if S3 is not available.
    """
    client = get_s3_client()
    if client is None:
        logger.warning("Cannot generate presigned upload URL -- S3 client unavailable")
        return None

    try:
        url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        return url
    except Exception as e:
        logger.error("Failed to generate presigned upload URL for %s/%s: %s", bucket, key, e)
        return None


def generate_presigned_download(
    bucket: str,
    key: str,
    expires_in: int = DEFAULT_EXPIRES_IN,
) -> Optional[str]:
    """
    Generate a presigned GET URL for downloading an object from S3.

    Args:
        bucket: S3 bucket name.
        key: S3 object key.
        expires_in: URL expiry in seconds (default 3600).

    Returns:
        Presigned URL string, or None if S3 is not available.
    """
    client = get_s3_client()
    if client is None:
        logger.warning("Cannot generate presigned download URL -- S3 client unavailable")
        return None

    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )
        return url
    except Exception as e:
        logger.error("Failed to generate presigned download URL for %s/%s: %s", bucket, key, e)
        return None


def get_cdn_url(key: str) -> Optional[str]:
    """
    If CATALOG_IMAGES_CDN_URL is set, return a CDN URL for the given key.
    Otherwise returns None.

    Args:
        key: S3 object key.

    Returns:
        CDN URL string, or None if CDN is not configured.
    """
    if CDN_URL:
        return f"{CDN_URL.rstrip('/')}/{key}"
    return None


def generate_upload_url(
    key: str,
    content_type: str = "application/octet-stream",
    expires_in: int = DEFAULT_EXPIRES_IN,
    bucket: Optional[str] = None,
) -> str:
    """Convenience wrapper: generate a presigned upload URL or raise.

    Unlike ``generate_presigned_upload`` (which returns None on failure),
    this function raises ``RuntimeError`` when S3 is not configured — making
    it suitable for endpoints that *require* S3.

    Args:
        key: S3 object key.
        content_type: MIME type (default ``application/octet-stream``).
        expires_in: URL expiry in seconds (default 3600).
        bucket: Override bucket (defaults to CATALOG_IMAGES_S3_BUCKET).
    """
    url = generate_presigned_upload(bucket or DEFAULT_BUCKET, key, content_type, expires_in)
    if url is None:
        raise RuntimeError(
            "S3 is not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
            "environment variables, and ensure boto3 is installed."
        )
    return url


def generate_download_url(
    key: str,
    expires_in: int = DEFAULT_EXPIRES_IN,
    bucket: Optional[str] = None,
) -> str:
    """Convenience wrapper: generate a presigned download URL or raise.

    Unlike ``generate_presigned_download`` (which returns None on failure),
    this function raises ``RuntimeError`` when S3 is not configured.

    Args:
        key: S3 object key.
        expires_in: URL expiry in seconds (default 3600).
        bucket: Override bucket (defaults to CATALOG_IMAGES_S3_BUCKET).
    """
    url = generate_presigned_download(bucket or DEFAULT_BUCKET, key, expires_in)
    if url is None:
        raise RuntimeError(
            "S3 is not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
            "environment variables, and ensure boto3 is installed."
        )
    return url


def get_public_url(key: str, bucket: Optional[str] = None) -> str:
    """
    Return the best available public URL for an S3 object.

    Prefers CDN URL if configured, otherwise returns direct S3 URL.

    Args:
        key: S3 object key.
        bucket: S3 bucket name (defaults to DEFAULT_BUCKET).

    Returns:
        Public URL string.
    """
    cdn = get_cdn_url(key)
    if cdn:
        return cdn
    b = bucket or DEFAULT_BUCKET
    return f"https://{b}.s3.{AWS_REGION}.amazonaws.com/{key}"
