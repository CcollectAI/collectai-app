"""
Supabase Writer for ingest pipeline.

Writes:
- ingest_runs_v1: Run tracking records
- raw_observation_pointers_v1: Pointers to S3 raw data
- training_candidates_v1: Normalized training candidates
"""

import os
import json
from datetime import datetime
from typing import List, Optional
import requests

from .types import RawObservation, TrainingCandidate, IngestRunRecord

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')


class SupabaseWriter:
    """
    Writes ingest data to Supabase tables.
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.base_url = SUPABASE_URL
        self.headers = {
            'apikey': SERVICE_KEY,
            'Authorization': f'Bearer {SERVICE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates',
        }

    def _post(self, table: str, rows: List[dict]) -> bool:
        """POST rows to Supabase table."""
        if not rows:
            return True

        if self.dry_run:
            print(f"[SupabaseWriter] DRY-RUN: Would write {len(rows)} rows to {table}")
            return True

        if not SUPABASE_URL or not SERVICE_KEY:
            print(f"[SupabaseWriter] SKIP: No Supabase credentials")
            return False

        try:
            resp = requests.post(
                f"{self.base_url}/rest/v1/{table}",
                headers=self.headers,
                data=json.dumps(rows, default=str),
                timeout=60,
            )

            if resp.status_code >= 300:
                print(f"[SupabaseWriter] ERROR: {table} - {resp.status_code}: {resp.text}")
                return False

            print(f"[SupabaseWriter] Wrote {len(rows)} rows to {table}")
            return True

        except Exception as e:
            print(f"[SupabaseWriter] ERROR: {table} - {e}")
            return False

    def write_ingest_run(self, record: IngestRunRecord) -> bool:
        """Write or update ingest run record."""
        row = {
            'run_id': record.run_id,
            'started_at': record.started_at,
            'finished_at': record.finished_at,
            'status': record.status,
            'input_count': record.input_count,
            'processed_count': record.processed_count,
            'skipped_count': record.skipped_count,
            'error_count': record.error_count,
            'config_json': record.config_json,
            'errors_json': record.errors_json,
            's3_bundle_key': record.s3_bundle_key,
        }
        return self._post('ingest_runs_v1', [row])

    def write_observation_pointers(
        self,
        observations: List[RawObservation],
        s3_key: Optional[str] = None,
    ) -> bool:
        """
        Write pointer rows for observations.
        Pointers reference the S3 raw bundle + include taxonomy mapping.
        """
        rows = []
        for obs in observations:
            rows.append({
                'observation_id': obs.observation_id,
                's3_key': s3_key,
                'source': obs.source,
                'observed_at': obs.observed_at,
                'taxonomy_version': obs.taxonomy_version,
                'category_id': obs.category_id,
                'subtype_id': obs.subtype_id,
                'confidence': obs.mapping_confidence,
                'content_hash': obs.content_hash or obs.compute_hash(),
            })

        return self._post('raw_observation_pointers_v1', rows)

    def write_training_candidates(self, candidates: List[TrainingCandidate]) -> bool:
        """Write training candidate rows."""
        rows = []
        for c in candidates:
            rows.append({
                'candidate_id': c.candidate_id,
                'observation_id': c.observation_id,
                'category_id': c.category_id,
                'subtype_id': c.subtype_id,
                'taxonomy_version': c.taxonomy_version,
                'required_attrs_json': c.required_attrs,
                'price_q10': c.price_q10,
                'price_q50': c.price_q50,
                'price_q90': c.price_q90,
                'confidence': c.confidence,
                'label_state': c.label_state,
            })

        return self._post('training_candidates_v1', rows)

    def check_existing_hashes(self, hashes: List[str]) -> set:
        """
        Check which hashes already exist (for deduplication).
        Returns set of existing hashes.
        """
        if self.dry_run or not hashes:
            return set()

        if not SUPABASE_URL or not SERVICE_KEY:
            return set()

        try:
            # Query for existing hashes
            hash_list = ','.join(f'"{h}"' for h in hashes[:500])  # Limit query size
            resp = requests.get(
                f"{self.base_url}/rest/v1/raw_observation_pointers_v1",
                headers={
                    'apikey': SERVICE_KEY,
                    'Authorization': f'Bearer {SERVICE_KEY}',
                },
                params={
                    'select': 'content_hash',
                    'content_hash': f'in.({hash_list})',
                },
                timeout=30,
            )

            if resp.status_code == 200:
                return {r['content_hash'] for r in resp.json()}

            return set()

        except Exception as e:
            print(f"[SupabaseWriter] Hash check failed: {e}")
            return set()


def write_ingest_results(
    run_record: IngestRunRecord,
    observations: List[RawObservation],
    candidates: List[TrainingCandidate],
    s3_key: Optional[str],
    dry_run: bool = False,
) -> bool:
    """
    Convenience function to write all ingest results to Supabase.

    Args:
        run_record: The ingest run record
        observations: List of raw observations
        candidates: List of training candidates
        s3_key: S3 key where raw bundle was written
        dry_run: If True, don't actually write

    Returns:
        True if all writes succeeded
    """
    writer = SupabaseWriter(dry_run=dry_run)

    success = True
    success = writer.write_ingest_run(run_record) and success
    success = writer.write_observation_pointers(observations, s3_key) and success
    success = writer.write_training_candidates(candidates) and success

    return success
