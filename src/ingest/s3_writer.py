"""
S3 Writer for raw observation bundles.

Writes partitioned JSONL files to S3 for bulk raw storage.
Format: s3://{bucket}/ingest/raw/{date}/{run_id}.jsonl.gz

Note: In v1, this is a stub that writes to local filesystem.
For production, implement with boto3 or use Supabase Storage as interim.
"""

import os
import json
import gzip
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .types import RawObservation

# Configurable via environment
S3_BUCKET = os.environ.get('INGEST_S3_BUCKET', '')
USE_S3 = bool(S3_BUCKET)
LOCAL_OUTPUT_DIR = os.environ.get('INGEST_LOCAL_DIR', '/tmp/collectai_ingest')


class S3Writer:
    """
    Writes raw observation bundles to S3 (or local filesystem as fallback).
    """

    def __init__(self, run_id: str, dry_run: bool = False):
        self.run_id = run_id
        self.dry_run = dry_run
        self.date_partition = datetime.now(timezone.utc).strftime('%Y/%m/%d')

    def _get_s3_key(self) -> str:
        """Generate S3 key for this run's bundle."""
        return f"ingest/raw/{self.date_partition}/{self.run_id}.jsonl.gz"

    def _get_local_path(self) -> Path:
        """Generate local path for this run's bundle."""
        base = Path(LOCAL_OUTPUT_DIR) / 'raw' / self.date_partition
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{self.run_id}.jsonl.gz"

    def write_bundle(self, observations: List[RawObservation]) -> Optional[str]:
        """
        Write observations to a JSONL bundle.

        Returns:
            S3 key or local path where bundle was written.
            None if dry_run or empty input.
        """
        if not observations:
            return None

        if self.dry_run:
            print(f"[S3Writer] DRY-RUN: Would write {len(observations)} observations")
            print(f"[S3Writer] DRY-RUN: Key would be: {self._get_s3_key()}")
            return None

        # Convert to JSONL
        jsonl_content = '\n'.join(
            json.dumps(obs.to_dict(), default=str)
            for obs in observations
        )

        if USE_S3:
            return self._write_to_s3(jsonl_content)
        else:
            return self._write_to_local(jsonl_content)

    def _write_to_s3(self, content: str) -> str:
        """Write to S3 bucket (requires boto3)."""
        try:
            import boto3
            s3_client = boto3.client('s3')
            key = self._get_s3_key()

            # Compress and upload
            compressed = gzip.compress(content.encode('utf-8'))
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=compressed,
                ContentType='application/gzip',
                ContentEncoding='gzip',
            )

            print(f"[S3Writer] Wrote {len(content)} bytes to s3://{S3_BUCKET}/{key}")
            return f"s3://{S3_BUCKET}/{key}"

        except ImportError:
            print("[S3Writer] boto3 not available, falling back to local storage")
            return self._write_to_local(content)
        except Exception as e:
            print(f"[S3Writer] S3 upload failed: {e}, falling back to local storage")
            return self._write_to_local(content)

    def _write_to_local(self, content: str) -> str:
        """Write to local filesystem as fallback."""
        path = self._get_local_path()

        with gzip.open(path, 'wt', encoding='utf-8') as f:
            f.write(content)

        print(f"[S3Writer] Wrote {len(content)} bytes to {path}")
        return str(path)


def write_observations_bundle(
    observations: List[RawObservation],
    run_id: str,
    dry_run: bool = False
) -> Optional[str]:
    """
    Convenience function to write a bundle of observations.

    Args:
        observations: List of RawObservation objects
        run_id: Unique run identifier
        dry_run: If True, don't actually write

    Returns:
        Path/key where bundle was written, or None
    """
    writer = S3Writer(run_id=run_id, dry_run=dry_run)
    return writer.write_bundle(observations)
