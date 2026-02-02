"""
CollectAI Ingest Pipeline

Nightly job that appends datapoints (raw observations) and produces
normalized training candidates with taxonomy mapping.

Design principles:
- Raw data is append-only and immutable
- Every record includes taxonomy_version for safe remapping
- Hash-based deduplication to prevent duplicates
- Dry-run mode for safe testing
"""

from .types import (
    RawObservation,
    TrainingCandidate,
    IngestRunRecord,
    TAXONOMY_VERSION,
)
from .taxonomy_mapper import (
    apply_taxonomy_mapping,
    batch_apply_taxonomy,
    map_category,
    map_subtype,
)
from .s3_writer import write_observations_bundle, S3Writer
from .supabase_writer import write_ingest_results, SupabaseWriter

__all__ = [
    'RawObservation',
    'TrainingCandidate',
    'IngestRunRecord',
    'TAXONOMY_VERSION',
    'apply_taxonomy_mapping',
    'batch_apply_taxonomy',
    'map_category',
    'map_subtype',
    'write_observations_bundle',
    'S3Writer',
    'write_ingest_results',
    'SupabaseWriter',
]
