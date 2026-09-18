"""`/collections/user/progress` answered 500 for every member, always.

Reported by the class-A sweep on 2026-09-16 as "returns 500 for a real member"
and left open. The cause was NOT the query — that runs fine against production.
It was the response model: `UserCollectionProgress.collection_key` was a
required `str`, mapped from `sets.external_id`, which is **NULL on every set on
production** (3 of 3, checked 2026-09-18). Pydantic rejected every row, the
handler's `except Exception` turned the ValidationError into
`500 Failed to get collection progress`, and the log line said "Failed to get
user progress" with no hint that the shape was the problem.

The fix is the type, not the data: a set with no external key still has a real
name and a real size, and `docs/HELP_AND_GUIDES.md` reserves omission for sets
whose SIZE is unknown ("omitted rather than given an invented total").
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.features.collections_router import UserCollectionProgress, UserProgressResponse  # noqa: E402


def test_a_set_with_no_external_id_does_not_blow_up_the_response():
    """The exact shape production returns: external_id NULL, everything else real."""
    row = UserCollectionProgress(
        collection_id="829892b3-fe52-4550-ab4f-833dc95f4397",
        collection_key=None,
        display_name="McDonald's Match Battle 2023",
        category="pokemon",
        total_items=15,
        owned_count=0,
        completion_pct=0.0,
    )
    assert row.collection_key is None
    assert row.display_name == "McDonald's Match Battle 2023"


def test_the_whole_payload_serialises_with_null_keys():
    # This is what 500'd: one bad row poisoned the entire response.
    rows = [
        UserCollectionProgress(collection_id=f"id-{i}", collection_key=None,
                               display_name=f"Set {i}", category="pokemon",
                               total_items=15, owned_count=i, completion_pct=0.0)
        for i in range(3)
    ]
    payload = UserProgressResponse(progress=rows, total_collections=3,
                                   total_owned=3, total_items=45)
    dumped = payload.model_dump()
    assert len(dumped["progress"]) == 3
    assert all(p["collection_key"] is None for p in dumped["progress"])


def test_a_real_external_id_still_comes_through():
    row = UserCollectionProgress(
        collection_id="x", collection_key="base1", display_name="Base Set",
        category="pokemon", total_items=102, owned_count=4, completion_pct=3.9,
    )
    assert row.collection_key == "base1"
