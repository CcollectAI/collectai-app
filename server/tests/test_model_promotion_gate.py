"""The promotion gate's decision rule.

Measured on the first re-enabled run (2026-08-29):

    holdout_n = 0  -> 53 categories, ALL promoted ("no_holdout — first train
                      or empty ground_truth")
    holdout_n = 3  -> 1 category (lorcana), REVERTED on
                      new_mae=24.23 > old_mae=2.82 * 1.05

That rule is incoherent: zero evidence promotes, three samples reject. It is
strictly more permissive the LESS it knows, and a 5% MAE tolerance applied to
three points is noise amplified into a decision.

The evidence base cannot grow on its own either. `price_ground_truths` holds
**9 rows in total**, and docs/ARCHITECTURE.md:838 records why: it only fills
when a real user marks an item sold, and there are no users yet.

So the gate may only REJECT when it has enough holdout to mean something.
Below that it promotes -- consistent with the n=0 path -- and says so loudly
rather than pretending it decided.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workers.model_retrain_worker import should_revert, MIN_HOLDOUT_FOR_GATE


def test_a_real_regression_on_enough_holdout_is_reverted():
    """KNOWN-BAD: the case the gate exists for."""
    revert, reason = should_revert(old_mae=2.0, new_mae=10.0,
                                   holdout_n=MIN_HOLDOUT_FOR_GATE, tolerance=1.05)
    assert revert is True
    assert "regression" in reason


def test_an_improvement_on_enough_holdout_is_promoted():
    """KNOWN-GOOD: same path, opposite verdict."""
    revert, reason = should_revert(old_mae=10.0, new_mae=2.0,
                                   holdout_n=MIN_HOLDOUT_FOR_GATE, tolerance=1.05)
    assert revert is False


def test_within_tolerance_is_promoted():
    revert, _ = should_revert(old_mae=10.0, new_mae=10.4,
                              holdout_n=MIN_HOLDOUT_FOR_GATE, tolerance=1.05)
    assert revert is False, "a 4% change is inside the 5% tolerance"


def test_the_lorcana_case_is_NOT_reverted_on_three_samples():
    """The exact numbers from the 2026-08-29 run.

    An 8.6x MAE ratio looks damning until you see it was measured on THREE
    points drawn from a nine-row table. The gate must not turn that into a
    revert while it promotes 53 other categories on zero evidence.
    """
    revert, reason = should_revert(old_mae=2.81931273173279,
                                   new_mae=24.228030904952,
                                   holdout_n=3, tolerance=1.05)
    assert revert is False
    assert "insufficient" in reason.lower()
    assert "24.23" in reason and "2.82" in reason, \
        "the numbers must survive into the reason — not acting on a signal is " \
        "not the same as discarding it"


def test_no_holdout_is_promoted_and_says_so():
    revert, reason = should_revert(old_mae=None, new_mae=None,
                                   holdout_n=0, tolerance=1.05)
    assert revert is False
    assert "no_holdout" in reason


def test_the_rule_is_monotonic_in_evidence():
    """The defect in one assertion: more evidence must never be MORE
    permissive. The old rule rejected at n=3 and promoted at n=0."""
    bad = dict(old_mae=2.0, new_mae=100.0, tolerance=1.05)
    below, _ = should_revert(holdout_n=MIN_HOLDOUT_FOR_GATE - 1, **bad)
    at, _ = should_revert(holdout_n=MIN_HOLDOUT_FOR_GATE, **bad)
    none_, _ = should_revert(holdout_n=0, **bad)
    assert none_ is False and below is False and at is True, \
        "reverting must switch ON as evidence grows, never off"
