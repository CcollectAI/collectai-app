"""
Ingest pipeline types and schemas.

RawObservation is the canonical schema for all ingested data points.
Designed for taxonomy evolution: taxonomy_version is stored on every record
so we can remap later without losing data.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Any
import hashlib
import json

# Current taxonomy version - increment when taxonomy changes
TAXONOMY_VERSION = "v1.0"


@dataclass
class RawObservation:
    """
    Canonical schema for raw market observations.
    Immutable once written - never delete, only remap.
    """
    observation_id: str  # Unique ID (provider + source_id hash)
    source: str  # 'ebay', 'reddit', 'app_feedback', 'manual_csv'
    source_id: str  # Provider's unique identifier

    # Core data
    title: str
    category_raw: str  # Original category string from source
    condition_raw: Optional[str] = None

    # Pricing
    price: Optional[float] = None
    price_eur: Optional[float] = None
    currency: Optional[str] = None
    is_sold: bool = False

    # Taxonomy mapping (filled by mapper stage)
    category_id: Optional[str] = None
    subtype_id: Optional[str] = None
    taxonomy_version: str = TAXONOMY_VERSION
    mapping_confidence: Optional[float] = None
    mapping_rationale: Optional[str] = None

    # Metadata
    observed_at: Optional[str] = None  # ISO timestamp
    image_url: Optional[str] = None
    url: Optional[str] = None

    # Raw payload for future remapping
    raw_json: Optional[dict] = field(default_factory=dict)

    # Deduplication
    content_hash: Optional[str] = None

    def compute_hash(self) -> str:
        """Compute content hash for deduplication."""
        key_fields = f"{self.source}|{self.source_id}|{self.title}|{self.price_eur}"
        return hashlib.sha256(key_fields.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        d = asdict(self)
        if self.content_hash is None:
            d['content_hash'] = self.compute_hash()
        return d

    @classmethod
    def from_market_observation(cls, row: dict) -> 'RawObservation':
        """Create from existing market_observations table row."""
        obs_id = f"{row['provider']}-{row['source_id']}"
        return cls(
            observation_id=obs_id,
            source=row['provider'],
            source_id=row['source_id'],
            title=row.get('title', ''),
            category_raw=row.get('category', ''),
            condition_raw=row.get('condition'),
            price=float(row['price']) if row.get('price') else None,
            price_eur=float(row['price_eur']) if row.get('price_eur') else None,
            currency=row.get('currency'),
            is_sold=bool(row.get('is_sold', False)),
            observed_at=row.get('observed_at'),
            image_url=row.get('image_url'),
            url=row.get('url'),
            raw_json=row.get('raw', {}),
        )


@dataclass
class TrainingCandidate:
    """
    Normalized training candidate derived from RawObservation.
    Ready for model training with required attributes.
    """
    candidate_id: str
    observation_id: str

    # Taxonomy
    category_id: str
    subtype_id: Optional[str] = None
    taxonomy_version: str = TAXONOMY_VERSION

    # Required attributes for training
    required_attrs: dict = field(default_factory=dict)  # {attr_name: value}

    # Price quantiles (from similar items or model inference)
    price_q10: Optional[float] = None
    price_q50: Optional[float] = None
    price_q90: Optional[float] = None

    # Confidence and state
    confidence: Optional[float] = None
    label_state: str = 'pending'  # 'pending', 'verified', 'rejected'

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IngestRunRecord:
    """
    Record of a single ingest run for tracking and debugging.
    """
    run_id: str
    started_at: str
    finished_at: Optional[str] = None
    status: str = 'running'  # 'running', 'completed', 'failed'

    # Counts
    input_count: int = 0
    processed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0

    # Config
    config_json: dict = field(default_factory=dict)
    errors_json: list = field(default_factory=list)

    # S3 output reference
    s3_bundle_key: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
