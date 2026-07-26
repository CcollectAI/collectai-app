"""Tests for IntakeResult defaults.

This file used to hold three "fast-path" tests for the F2 optimisation that
skipped the catalog re-prompt when `clip_confidence >= 0.90`. They asserted
nothing about the product: none of them called `process_intake`, they
re-implemented the comparison inline and asserted on their own local
variables. They passed whether or not the fast-path existed — and in fact the
fast-path NEVER executed in production, because `clip_confidence` was only
ever written by the fal.ai CLIP tier, which never ran (FAL_KEY unset). A green
suite therefore actively concealed a dead feature.

The fast-path was deleted with the CLIP tier (2026-07-27); the tests that
pinned it are deleted here rather than rewritten, since there is no behaviour
left to cover.
"""
import pytest

from app.agents.intake_agent import IntakeResult


@pytest.mark.asyncio
async def test_scan_session_id_defaults_to_none():
    """IntakeResult.scan_session_id is unset until process_intake assigns it."""
    result = IntakeResult()
    assert result.scan_session_id is None
