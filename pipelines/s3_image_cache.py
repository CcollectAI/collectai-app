"""
S3 Image Cache for catalog import pipelines.

Downloads external thumbnails and uploads to S3 for reliable serving.
Uses deterministic keys: catalog-images/{category}/{item_key}.{ext}

Optional CloudFront CDN distribution for fast global delivery.

Cost at beta scale (~2,000 images × 50KB avg):
  - S3 storage: ~100MB = $0.002/month
  - CloudFront transfer (1GB/month): ~$0.085/month
  - Total: < $0.10/month

Usage:
    cache = S3ImageCache()  # reads config from env
    cdn_url = cache.cache_image("https://external.com/img.jpg", "pokemon", "charizard-base")
    # Returns: https://d1234.cloudfront.net/catalog-images/pokemon/charizard-base.jpg
    # Or falls back to original URL if S3 not configured

Environment variables:
    CATALOG_IMAGES_S3_BUCKET  - S3 bucket name (default: collectai-artifacts)
    CATALOG_IMAGES_CDN_URL    - CloudFront distribution URL (optional)
    AWS_ACCESS_KEY_ID         - AWS credentials
    AWS_SECRET_ACCESS_KEY     - AWS credentials
    AWS_REGION                - AWS region (default: eu-west-1)
"""

from __future__ import annotations

import hashlib
import io
import os
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import logging

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

S3_BUCKET = os.environ.get("CATALOG_IMAGES_S3_BUCKET", os.environ.get("ARTIFACT_BUCKET", ""))
CDN_URL = os.environ.get("CATALOG_IMAGES_CDN_URL", "")  # e.g. https://d1234.cloudfront.net
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")
S3_PREFIX = "catalog-images"

# Local cache dir for downloaded images (avoids re-downloading on retry)
LOCAL_CACHE_DIR = Path(os.environ.get("IMAGE_CACHE_DIR", "/tmp/collectai_image_cache"))

# Limits
MAX_IMAGE_SIZE = 500_000  # 500KB max per image (we only need thumbnails)
DOWNLOAD_TIMEOUT = 10.0   # seconds
MAX_RETRIES = 2


def _ext_from_url(url: str) -> str:
    """Extract file extension from URL, default to .jpg."""
    path = urlparse(url).path.lower()
    for ext in (".png", ".webp", ".gif", ".svg"):
        if path.endswith(ext):
            return ext
    return ".jpg"


def _s3_key(category: str, item_key: str, ext: str) -> str:
    """Generate deterministic S3 key."""
    return f"{S3_PREFIX}/{category}/{item_key}{ext}"


class S3ImageCache:
    """
    Downloads external images and uploads to S3 for reliable serving.

    Falls back gracefully:
    - No S3 configured → returns original URL
    - Download fails → returns original URL
    - Upload fails → returns original URL
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._s3_client = None
        self._http_client = httpx.Client(
            timeout=DOWNLOAD_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "CollectAI-Catalog/1.0"},
        )
        self._stats = {"cached": 0, "skipped": 0, "failed": 0}

        # Ensure local cache dir exists
        LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        if not S3_BUCKET:
            logger.info("No S3 bucket configured — images will use original URLs")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("S3ImageCache enabled — Bucket: %s | CDN: %s", S3_BUCKET, CDN_URL or "none")

    @property
    def s3_client(self):
        """Lazy-init boto3 S3 client."""
        if self._s3_client is None:
            try:
                import boto3
                self._s3_client = boto3.client("s3", region_name=AWS_REGION)
            except ImportError:
                logger.warning("boto3 not installed — falling back to original URLs")
                self.enabled = False
        return self._s3_client

    def cache_image(
        self,
        image_url: str,
        category: str,
        item_key: str,
    ) -> str:
        """
        Cache an external image to S3.

        Args:
            image_url: External URL to download
            category: Category slug (e.g. "pokemon")
            item_key: Item key slug (e.g. "base-set-charizard-holo")

        Returns:
            CDN/S3 URL if cached successfully, or original URL as fallback.
        """
        if not image_url or not self.enabled:
            return image_url

        ext = _ext_from_url(image_url)
        key = _s3_key(category, item_key, ext)
        local_path = LOCAL_CACHE_DIR / category / f"{item_key}{ext}"

        # Check if already uploaded (avoid duplicate work)
        if self._object_exists(key):
            self._stats["skipped"] += 1
            return self._public_url(key)

        if self.dry_run:
            self._stats["cached"] += 1
            return self._public_url(key)

        # Download
        image_data = self._download(image_url)
        if image_data is None:
            self._stats["failed"] += 1
            return image_url  # fallback to original

        # Save local cache
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(image_data)

        # Upload to S3
        if self._upload(key, image_data, ext):
            self._stats["cached"] += 1
            return self._public_url(key)
        else:
            self._stats["failed"] += 1
            return image_url  # fallback to original

    def cache_batch(
        self,
        items: list[tuple[str, str, str]],
        rate_limit: float = 0.1,
    ) -> dict[str, str]:
        """
        Cache a batch of images.

        Args:
            items: List of (image_url, category, item_key) tuples
            rate_limit: Seconds between downloads (be polite to source servers)

        Returns:
            Dict mapping original URL → cached URL
        """
        url_map: dict[str, str] = {}
        for i, (url, category, item_key) in enumerate(items):
            if not url:
                continue
            cached_url = self.cache_image(url, category, item_key)
            url_map[url] = cached_url
            if i > 0 and i % 50 == 0:
                logger.info(
                    "ImageCache progress: %d/%d (cached=%d, skipped=%d, failed=%d)",
                    i, len(items), self._stats['cached'], self._stats['skipped'], self._stats['failed'],
                )
            time.sleep(rate_limit)
        return url_map

    def _download(self, url: str) -> Optional[bytes]:
        """Download image from external URL."""
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._http_client.get(url)
                if resp.status_code != 200:
                    if attempt == MAX_RETRIES - 1:
                        return None
                    time.sleep(0.5)
                    continue

                data = resp.content
                if len(data) > MAX_IMAGE_SIZE:
                    # Image too large — skip (we only want thumbnails)
                    return None
                return data

            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == MAX_RETRIES - 1:
                    return None
                time.sleep(0.5)
        return None

    def _upload(self, key: str, data: bytes, ext: str) -> bool:
        """Upload image bytes to S3."""
        content_types = {
            ".jpg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
        }
        content_type = content_types.get(ext, "image/jpeg")

        try:
            self.s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=data,
                ContentType=content_type,
                CacheControl="public, max-age=31536000",  # 1 year cache
            )
            return True
        except Exception as e:
            logger.warning("S3 upload failed for %s: %s", key, e)
            return False

    def _object_exists(self, key: str) -> bool:
        """Check if object already exists in S3 (avoids re-upload)."""
        if not self.enabled or self.dry_run:
            return False
        try:
            self.s3_client.head_object(Bucket=S3_BUCKET, Key=key)
            return True
        except Exception:
            # boto3 ClientError on 404 is expected; other errors also mean "not cached"
            return False

    def _public_url(self, key: str) -> str:
        """Generate public URL for cached image."""
        if CDN_URL:
            return f"{CDN_URL.rstrip('/')}/{key}"
        # Direct S3 URL (works if bucket has public-read policy on catalog-images/ prefix)
        return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"

    def print_stats(self):
        """Log caching statistics."""
        total = sum(self._stats.values())
        logger.info(
            "ImageCache stats: %d total | %d cached | %d already cached | %d failed",
            total, self._stats['cached'], self._stats['skipped'], self._stats['failed'],
        )

    def close(self):
        """Clean up HTTP client."""
        self._http_client.close()
