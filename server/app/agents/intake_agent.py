"""
Intake Agent for CollectAI — backward-compatible shim.

All logic has been moved to the ``app.agents.intake`` sub-package.
This module re-exports every public symbol so that existing imports
(``from app.agents.intake_agent import …``) continue to work unchanged.
"""

from app.agents.intake import (  # noqa: F401 — re-exports
    # Main entry points
    process_intake,
    process_url_import,
    # Types
    IntakeResult,
    # Constants
    TAXONOMY_VERSION,
    CORRECTION_THRESHOLD,
    COLLECTIBLE_EXTRACT_SCHEMA,
    _SUPPORTED_URL_PATTERNS,
    _FX_TO_EUR,
    _REPROMPT_SCHEMA,
    # Helpers (used by tests)
    _price_band_to_dict,
    _normalize_for_search,
    _text_similarity,
    _lookup_taxonomy_corrections,
    _fire_catalog_miss,
    _log_catalog_miss,
    _barcode_lookup_internal,
    _vision_classify_internal,
    _match_catalog_items,
    _validate_with_reprompt,
    _estimate_price,
    _detect_url_source,
    _convert_price_to_eur,
    _guess_category_from_url,
    apply_condition_grading,
)

# Also expose get_db_pool import path that was present in the original module
from app.lib.db_helpers import get_db_pool as get_db_pool  # noqa: F401
