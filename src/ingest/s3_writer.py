"""
S3 Writer for raw observation bundles.

Writes partitioned JSONL files to S3 for bulk raw storage.
Format: s3://{bucket}/ingest/raw/{date}/{run_id}.jsonl.gz

Uses the shared s3_client module from app.lib for S3 operations.
After successful S3 writes, inserts a pointer row into the
object_pointers table (if a DB connection is available).
"""

import hashlib
import json
import gzip
import logging
import os
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .types import RawObservation

logger = logging.getLogger(__name__)

# Configurable via environment
S3_BUCKET = os.environ.get('INGEST_S3_BUCKET', os.environ.get('CATALOG_IMAGES_S3_BUCKET', ''))
USE_S3 = bool(S3_BUCKET)
LOCAL_OUTPUT_DIR = os.environ.get('INGEST_LOCAL_DIR', '/tmp/collectai_ingest')


def _get_shared_s3_client():
    """Try to get the shared S3 client from app.lib.s3_client."""
    try:
        from app.lib.s3_client import get_s3_client
        return get_s3_client()
    except ImportError:
        return None


def _insert_object_pointer(
    s3_key: str,
    bucket: str,
    content_hash: str,
    size_bytes: int,
    content_type: str,
    object_type: str,
    created_by: str = "pipeline",
    related_category: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """
    Insert a pointer row into the object_pointers table.

    Uses a synchronous connection attempt. Logs and continues on failure
    (the S3 object is already written; the pointer can be reconciled later).
    """
    try:
        import asyncpg
        import asyncio

        db_dsn = os.environ.get("DB_DSN", "")
        if not db_dsn:
            logger.debug("DB_DSN not set; skipping object_pointers insert for %s", s3_key)
            return

        async def _insert():
            conn = await asyncpg.connect(db_dsn, timeout=5)
            try:
                await conn.execute(
                    """
                    INSERT INTO object_pointers
                        (id, s3_key, bucket, content_hash, size_bytes, content_type,
                         object_type, created_by, related_category, created_at, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (s3_key) DO UPDATE SET
                        content_hash = EXCLUDED.content_hash,
                        size_bytes = EXCLUDED.size_bytes
                    """,
                    _uuid.uuid4(),
                    s3_key,
                    bucket,
                    content_hash,
                    size_bytes,
                    content_type,
                    object_type,
                    created_by,
                    related_category,
                    datetime.now(timezone.utc),
                    json.dumps(metadata or {}),
                )
            finally:
                await conn.close()

        # Run in existing event loop if available, otherwise create one
        try:
            loop = asyncio.get_running_loop()
            # We are inside an async context -- schedule as a task
            loop.create_task(_insert())
        except RuntimeError:
            # No running event loop -- create one synchronously
            asyncio.run(_insert())

    except ImportError:
        logger.debug("asyncpg not available; skipping object_pointers insert")
    except Exception as e:
        logger.warning("Failed to insert object pointer for %s: %s", s3_key, e)


class S3Writer:
    """
    Writes raw observation bundles to S3 (or local filesystem as fallback).
    """

    def __init__(
        self,
        run_id: str,
        dry_run: bool = False,
        object_type: str = "market_dump",
    ):
        self.run_id = run_id
        self.dry_run = dry_run
        self.object_type = object_type
        self.date_partition = datetime.now(timezone.utc).strftime('%Y/%m/%d')

    def _get_s3_key(self) -> str:
        """Generate S3 key for this run's bundle."""
        return f"ingest/raw/{self.date_partition}/{self.run_id}.jsonl.gz"

    def _get_local_path(self) -> Path:
        """Generate local path for this run's bundle."""
        base = Path(LOCAL_OUTPUT_DIR) / 'raw' / self.date_partition
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{self.run_id}.jsonl.gz"

    def write_bundle(
        self,
        observations: List[RawObservation],
        related_category: Optional[str] = None,
    ) -> Optional[str]:
        """
        Write observations to a JSONL bundle.

        Args:
            observations: List of RawObservation objects.
            related_category: Optional category slug for object pointer.

        Returns:
            S3 key or local path where bundle was written.
            None if dry_run or empty input.
        """
        if not observations:
            return None

        if self.dry_run:
            logger.info("[S3Writer] DRY-RUN: Would write %d observations", len(observations))
            logger.info("[S3Writer] DRY-RUN: Key would be: %s", self._get_s3_key())
            return None

        # Convert to JSONL
        jsonl_content = '\n'.join(
            json.dumps(obs.to_dict(), default=str)
            for obs in observations
        )

        if USE_S3:
            return self._write_to_s3(jsonl_content, related_category=related_category)
        else:
            return self._write_to_local(jsonl_content)

    def _write_to_s3(
        self,
        content: str,
        related_category: Optional[str] = None,
    ) -> str:
        """Write to S3 bucket. Uses shared client if available, falls back to direct boto3."""
        key = self._get_s3_key()
        compressed = gzip.compress(content.encode('utf-8'))
        content_hash = hashlib.sha256(compressed).hexdigest()

        # Try shared client first
        s3_client = _get_shared_s3_client()

        if s3_client is None:
            # Fall back to direct boto3
            try:
                import boto3
                s3_client = boto3.client('s3')
            except ImportError:
                logger.warning("[S3Writer] boto3 not available, falling back to local storage")
                return self._write_to_local(content)

        try:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=compressed,
                ContentType='application/gzip',
                ContentEncoding='gzip',
            )

            logger.info("[S3Writer] Wrote %d bytes to s3://%s/%s", len(content), S3_BUCKET, key)

            # Insert object pointer (best-effort)
            _insert_object_pointer(
                s3_key=key,
                bucket=S3_BUCKET,
                content_hash=content_hash,
                size_bytes=len(compressed),
                content_type="application/jsonl+gzip",
                object_type=self.object_type,
                created_by="pipeline",
                related_category=related_category,
                metadata={"run_id": self.run_id, "observation_count": len(content.split('\n'))},
            )

            return f"s3://{S3_BUCKET}/{key}"

        except Exception as e:
            logger.warning("[S3Writer] S3 upload failed: %s, falling back to local storage", e)
            return self._write_to_local(content)

    def _write_to_local(self, content: str) -> str:
        """Write to local filesystem as fallback."""
        path = self._get_local_path()

        with gzip.open(path, 'wt', encoding='utf-8') as f:
            f.write(content)

        logger.info("[S3Writer] Wrote %d bytes to %s", len(content), path)
        return str(path)


def write_observations_bundle(
    observations: List[RawObservation],
    run_id: str,
    dry_run: bool = False,
    object_type: str = "market_dump",
    related_category: Optional[str] = None,
) -> Optional[str]:
    """
    Convenience function to write a bundle of observations.

    Args:
        observations: List of RawObservation objects
        run_id: Unique run identifier
        dry_run: If True, don't actually write
        object_type: Type for the object pointer (default: market_dump)
        related_category: Optional category slug

    Returns:
        Path/key where bundle was written, or None
    """
    writer = S3Writer(run_id=run_id, dry_run=dry_run, object_type=object_type)
    return writer.write_bundle(observations, related_category=related_category)
