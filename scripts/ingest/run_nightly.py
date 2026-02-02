#!/usr/bin/env python3
"""
CollectAI Nightly Ingest Pipeline

Appends datapoints (raw observations) and produces normalized training candidates.

Usage:
    python scripts/ingest/run_nightly.py --dry-run
    python scripts/ingest/run_nightly.py --max-items=100
    python scripts/ingest/run_nightly.py --source=app_feedback

Safety guards:
    --dry-run     : No writes, just print expected counts
    --max-items   : Cap rows per run (default: 1000)
    --skip-dedupe : Skip hash-based deduplication (for testing)

Environment:
    SUPABASE_URL              : Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY : Service role key
    INGEST_S3_BUCKET          : S3 bucket for raw bundles (optional)
    INGEST_LOCAL_DIR          : Local dir for bundles if no S3 (default: /tmp/collectai_ingest)
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingest.types import (
    RawObservation,
    TrainingCandidate,
    IngestRunRecord,
    TAXONOMY_VERSION,
)
from src.ingest.taxonomy_mapper import batch_apply_taxonomy
from src.ingest.s3_writer import write_observations_bundle
from src.ingest.supabase_writer import SupabaseWriter, write_ingest_results

# Default limits
DEFAULT_MAX_ITEMS = 1000
BATCH_SIZE = 100


def generate_run_id() -> str:
    """Generate unique run ID."""
    now = datetime.now(timezone.utc)
    return f"ingest-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def fetch_app_signals(max_items: int) -> List[dict]:
    """
    Fetch app-generated signals (user scans, feedback).
    Reads from market_observations table where source indicates app origin.
    """
    import requests

    supabase_url = os.environ.get('SUPABASE_URL', '')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

    if not supabase_url or not service_key:
        print("[Gather] No Supabase credentials, returning empty signals")
        return []

    try:
        # Fetch recent observations that haven't been processed
        resp = requests.get(
            f"{supabase_url}/rest/v1/market_observations",
            headers={
                'apikey': service_key,
                'Authorization': f'Bearer {service_key}',
            },
            params={
                'select': '*',
                'order': 'created_at.desc',
                'limit': str(max_items),
            },
            timeout=60,
        )

        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"[Gather] Fetch failed: {resp.status_code}")
            return []

    except Exception as e:
        print(f"[Gather] Error fetching signals: {e}")
        return []


def fetch_csv_imports(max_items: int) -> List[dict]:
    """
    Fetch manual CSV/seed imports.
    For v1, this returns empty - implement when CSV import is needed.
    """
    # TODO: Implement CSV import source
    return []


def normalize_to_observations(raw_rows: List[dict]) -> List[RawObservation]:
    """Convert raw input rows to RawObservation objects."""
    observations = []

    for row in raw_rows:
        try:
            obs = RawObservation.from_market_observation(row)
            obs.content_hash = obs.compute_hash()
            observations.append(obs)
        except Exception as e:
            print(f"[Normalize] Error: {e} - row: {row.get('id', 'unknown')}")

    return observations


def dedupe_observations(
    observations: List[RawObservation],
    skip_dedupe: bool = False,
    dry_run: bool = False,
) -> List[RawObservation]:
    """
    Remove duplicates based on content hash.
    Checks both in-batch and against existing Supabase records.
    """
    if skip_dedupe:
        print(f"[Dedupe] Skipping (--skip-dedupe)")
        return observations

    # In-batch dedupe
    seen_hashes = set()
    unique = []

    for obs in observations:
        h = obs.content_hash or obs.compute_hash()
        if h not in seen_hashes:
            seen_hashes.add(h)
            unique.append(obs)

    in_batch_dupes = len(observations) - len(unique)
    if in_batch_dupes > 0:
        print(f"[Dedupe] Removed {in_batch_dupes} in-batch duplicates")

    # Check against existing hashes in Supabase
    if not dry_run:
        writer = SupabaseWriter(dry_run=False)
        existing_hashes = writer.check_existing_hashes(
            [obs.content_hash for obs in unique]
        )

        if existing_hashes:
            before = len(unique)
            unique = [obs for obs in unique if obs.content_hash not in existing_hashes]
            print(f"[Dedupe] Removed {before - len(unique)} existing duplicates")

    return unique


def create_training_candidates(observations: List[RawObservation]) -> List[TrainingCandidate]:
    """
    Create training candidates from mapped observations.
    Only creates candidates for observations with successful taxonomy mapping.
    """
    candidates = []

    for obs in observations:
        if not obs.category_id:
            continue  # Skip unmapped observations

        candidate = TrainingCandidate(
            candidate_id=f"cand-{obs.observation_id}",
            observation_id=obs.observation_id,
            category_id=obs.category_id,
            subtype_id=obs.subtype_id,
            taxonomy_version=obs.taxonomy_version,
            required_attrs={
                'title': obs.title,
                'condition': obs.condition_raw,
            },
            price_q50=obs.price_eur,  # Use actual price as median estimate
            confidence=obs.mapping_confidence,
            label_state='pending',
        )
        candidates.append(candidate)

    return candidates


def run_pipeline(
    dry_run: bool = False,
    max_items: int = DEFAULT_MAX_ITEMS,
    sources: Optional[List[str]] = None,
    skip_dedupe: bool = False,
) -> IngestRunRecord:
    """
    Run the full ingest pipeline.

    Stages:
        0. Lock + idempotency (run_id)
        1. Gather inputs from sources
        2. Normalize to RawObservation
        3. Taxonomy mapping
        4. Write raw bundle to S3
        5. Write pointers + candidates to Supabase
        6. Update summaries (if needed)
    """
    run_id = generate_run_id()
    started_at = datetime.now(timezone.utc).isoformat()

    print(f"\n{'='*60}")
    print(f"CollectAI Nightly Ingest Pipeline")
    print(f"{'='*60}")
    print(f"Run ID      : {run_id}")
    print(f"Started     : {started_at}")
    print(f"Dry-run     : {dry_run}")
    print(f"Max items   : {max_items}")
    print(f"Taxonomy    : {TAXONOMY_VERSION}")
    print(f"{'='*60}\n")

    # Initialize run record
    run_record = IngestRunRecord(
        run_id=run_id,
        started_at=started_at,
        config_json={
            'dry_run': dry_run,
            'max_items': max_items,
            'sources': sources or ['app_signals'],
            'taxonomy_version': TAXONOMY_VERSION,
        },
    )

    errors = []

    try:
        # Stage 1: Gather inputs
        print("[Stage 1] Gathering inputs...")
        sources = sources or ['app_signals']
        raw_rows = []

        for source in sources:
            if source == 'app_signals':
                rows = fetch_app_signals(max_items)
                print(f"  - app_signals: {len(rows)} rows")
                raw_rows.extend(rows)
            elif source == 'csv':
                rows = fetch_csv_imports(max_items)
                print(f"  - csv: {len(rows)} rows")
                raw_rows.extend(rows)

        run_record.input_count = len(raw_rows)
        print(f"  Total input: {len(raw_rows)} rows\n")

        if not raw_rows:
            print("[Pipeline] No input data, exiting early")
            run_record.status = 'completed'
            run_record.finished_at = datetime.now(timezone.utc).isoformat()
            return run_record

        # Apply max_items cap
        if len(raw_rows) > max_items:
            print(f"[Safety] Capping at {max_items} items (had {len(raw_rows)})")
            raw_rows = raw_rows[:max_items]

        # Stage 2: Normalize
        print("[Stage 2] Normalizing to RawObservation schema...")
        observations = normalize_to_observations(raw_rows)
        print(f"  Normalized: {len(observations)} observations\n")

        # Dedupe
        print("[Stage 3] Deduplicating...")
        observations = dedupe_observations(observations, skip_dedupe, dry_run)
        run_record.skipped_count = run_record.input_count - len(observations)
        print(f"  After dedupe: {len(observations)} observations\n")

        # Stage 3: Taxonomy mapping
        print("[Stage 4] Applying taxonomy mapping...")
        observations = batch_apply_taxonomy(observations)

        mapped_count = sum(1 for obs in observations if obs.category_id)
        unmapped_count = len(observations) - mapped_count
        print(f"  Mapped: {mapped_count}, Unmapped: {unmapped_count}\n")

        # Stage 4: Write raw bundle to S3
        print("[Stage 5] Writing raw bundle to S3/local...")
        s3_key = write_observations_bundle(observations, run_id, dry_run)
        run_record.s3_bundle_key = s3_key
        if s3_key:
            print(f"  Bundle: {s3_key}\n")
        else:
            print("  (dry-run or no data)\n")

        # Stage 5: Create training candidates
        print("[Stage 6] Creating training candidates...")
        candidates = create_training_candidates(observations)
        print(f"  Candidates: {len(candidates)}\n")

        # Stage 6: Write to Supabase
        print("[Stage 7] Writing to Supabase...")
        run_record.processed_count = len(observations)

        if dry_run:
            print("  DRY-RUN: Would write:")
            print(f"    - 1 ingest_runs_v1 record")
            print(f"    - {len(observations)} raw_observation_pointers_v1 rows")
            print(f"    - {len(candidates)} training_candidates_v1 rows")
        else:
            success = write_ingest_results(
                run_record=run_record,
                observations=observations,
                candidates=candidates,
                s3_key=s3_key,
                dry_run=False,
            )
            if not success:
                errors.append("Supabase write failed")

        run_record.status = 'completed'

    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        errors.append(str(e))
        run_record.status = 'failed'
        run_record.error_count = 1

    finally:
        run_record.finished_at = datetime.now(timezone.utc).isoformat()
        run_record.errors_json = errors

    # Summary
    print(f"\n{'='*60}")
    print("Pipeline Summary")
    print(f"{'='*60}")
    print(f"Status      : {run_record.status}")
    print(f"Input       : {run_record.input_count}")
    print(f"Processed   : {run_record.processed_count}")
    print(f"Skipped     : {run_record.skipped_count}")
    print(f"Errors      : {run_record.error_count}")
    print(f"S3 Bundle   : {run_record.s3_bundle_key or 'N/A'}")
    print(f"Finished    : {run_record.finished_at}")
    print(f"{'='*60}\n")

    return run_record


def main():
    parser = argparse.ArgumentParser(
        description='CollectAI Nightly Ingest Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='No writes, just print expected counts',
    )
    parser.add_argument(
        '--max-items',
        type=int,
        default=DEFAULT_MAX_ITEMS,
        help=f'Cap rows per run (default: {DEFAULT_MAX_ITEMS})',
    )
    parser.add_argument(
        '--source',
        action='append',
        choices=['app_signals', 'csv'],
        help='Data sources to ingest (can specify multiple)',
    )
    parser.add_argument(
        '--skip-dedupe',
        action='store_true',
        help='Skip hash-based deduplication (for testing)',
    )

    args = parser.parse_args()

    result = run_pipeline(
        dry_run=args.dry_run,
        max_items=args.max_items,
        sources=args.source,
        skip_dedupe=args.skip_dedupe,
    )

    # Exit with error code if pipeline failed
    sys.exit(0 if result.status == 'completed' else 1)


if __name__ == '__main__':
    main()
