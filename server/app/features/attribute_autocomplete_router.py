"""
Attribute Autocomplete API — typeahead suggestions for manual-add forms.

Powered by the catalog vocabulary built by `pipelines/build_attribute_vocab.py`.
Returns the most-frequent values for a given category/field, optionally
filtered by a query prefix.

Endpoint:
    GET /attributes/autocomplete?category=watches&field=brand&q=rol&limit=10
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.errors import error_response
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attributes", tags=["Attributes"])

_autocomplete_limit = per_user_rate_limit(60, window_seconds=60, scope="attr_autocomplete")


class AutocompleteSuggestion(BaseModel):
    value: str
    count: int = Field(..., description="Frequency in catalog (higher = more common)")


class AutocompleteResponse(BaseModel):
    category: str
    field: str
    suggestions: List[AutocompleteSuggestion]
    total: int


@router.get(
    "/autocomplete",
    response_model=AutocompleteResponse,
    summary="Get attribute value suggestions for typeahead",
)
async def autocomplete(
    category: str = Query(..., description="Category slug, e.g. 'watches'"),
    field: str = Query(..., description="Attribute field name, e.g. 'brand'"),
    q: str = Query("", description="Optional prefix filter"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    _rl: None = Depends(_autocomplete_limit),
):
    """
    Returns top N values for a given attribute field, optionally filtered by
    a prefix query. Powered by the catalog vocabulary.
    """
    try:
        from app.ml.attribute_normalizer import _load_vocab
    except ImportError as e:
        raise error_response(500, f"Vocab unavailable: {e}", code="VOCAB_UNAVAILABLE")

    vocab = _load_vocab()
    if not vocab:
        return AutocompleteResponse(
            category=category, field=field, suggestions=[], total=0
        )

    cat_vocab = vocab.get(category, {})
    field_values = cat_vocab.get(field, {})

    if not field_values:
        return AutocompleteResponse(
            category=category, field=field, suggestions=[], total=0
        )

    # Filter by prefix
    q_lower = q.lower().strip()
    if q_lower:
        filtered = {
            v: c for v, c in field_values.items()
            if q_lower in v.lower()
        }
    else:
        filtered = field_values

    # Sort by count desc
    sorted_vals = sorted(filtered.items(), key=lambda x: -x[1])[:limit]

    suggestions = [
        AutocompleteSuggestion(value=v, count=c)
        for v, c in sorted_vals
    ]

    return AutocompleteResponse(
        category=category,
        field=field,
        suggestions=suggestions,
        total=len(filtered),
    )
