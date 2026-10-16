"""A negative rating must say what went wrong (2026-10-16, Vinted guidance).

Walked: "Problem" posted a negative grade in one tap with no reason.
"""
import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.features.p2p_offers_router import GradeCreate  # noqa: E402


@pytest.mark.parametrize("note", [None, "", "   ", "bad", "too short"])
def test_negative_without_a_real_reason_is_refused(note):
    with pytest.raises(ValidationError, match="what went wrong"):
        GradeCreate(verdict="negative", note=note)


def test_negative_with_a_reason_is_accepted():
    g = GradeCreate(verdict="negative", note="Card arrived creased on the corner")
    assert g.verdict == "negative"


@pytest.mark.parametrize("note", [None, "", "Smooth trade"])
def test_positive_needs_no_reason(note):
    assert GradeCreate(verdict="positive", note=note).verdict == "positive"
