"""
Intake Agent sub-package.

Re-exports all public symbols so that existing imports like
``from app.agents.intake_agent import process_intake`` continue to work
via the shim at ``app/agents/intake_agent.py``.
"""

from .helpers import (
    IntakeResult,
    TAXONOMY_VERSION,
    CORRECTION_THRESHOLD,
    _price_band_to_dict,
    _normalize_for_search,
    _text_similarity,
    _lookup_taxonomy_corrections,
    _fire_catalog_miss,
    _log_catalog_miss,
)
from .field_extraction import (
    _barcode_lookup_internal,
    _vision_classify_internal,
)
from .catalog_matching import (
    _match_catalog_items,
    _validate_with_reprompt,
    _REPROMPT_SCHEMA,
)
from .enrichment import (
    _estimate_price,
    COLLECTIBLE_EXTRACT_SCHEMA,
    _SUPPORTED_URL_PATTERNS,
    _FX_TO_EUR,
    _detect_url_source,
    _convert_price_to_eur,
    _guess_category_from_url,
    process_url_import,
)
from .condition_grading import apply_condition_grading
from .orchestrator import process_intake

__all__ = [
    # Main entry points
    "process_intake",
    "process_url_import",
    # Types
    "IntakeResult",
    # Constants
    "TAXONOMY_VERSION",
    "CORRECTION_THRESHOLD",
    "COLLECTIBLE_EXTRACT_SCHEMA",
    "_SUPPORTED_URL_PATTERNS",
    "_FX_TO_EUR",
    "_REPROMPT_SCHEMA",
    # Helpers (used by tests)
    "_price_band_to_dict",
    "_normalize_for_search",
    "_text_similarity",
    "_lookup_taxonomy_corrections",
    "_fire_catalog_miss",
    "_log_catalog_miss",
    "_barcode_lookup_internal",
    "_vision_classify_internal",
    "_match_catalog_items",
    "_validate_with_reprompt",
    "_estimate_price",
    "_detect_url_source",
    "_convert_price_to_eur",
    "_guess_category_from_url",
    "apply_condition_grading",
]
