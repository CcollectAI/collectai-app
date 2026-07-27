"""`_predict_quantile` — the V3 quantile-head contract.

Written 2026-07-27. `_predict_quantile` produces the euro figure a user
reads on an item, and the only tests that ever touched it were written for
`_predict_ridge` — a function renamed long ago, so they had been dead with
ImportError and the money path had NO live coverage.

Those nine are repointed in test_r50l_hardening.py and
test_production_hardening.py. This file covers what NOTHING ever covered:
the `coef_key` argument that selects which trained head runs. That argument
is the whole of V3 — before it, q10/q90 artifacts were trained and then
ignored (see the docstring on _predict_quantile), so a bug here silently
reverts the price band to the empirical one without any error.

Contract, from workers/valuation_worker.py and app/ml/valuation_features.py:

  _predict_quantile(model, feature_values: dict, coef_key="ridge") -> float|None

  * `coef_key` in {"ridge" (q50), "ridge_q10", "ridge_q90"}
  * feature vector is assembled by build_feature_vector in the ARTIFACT's
    feature order; a feature the caller omits defaults to 0.5, deliberately
    neutral rather than 0.0, because these are all [0,1] scores
  * returns None — never raises, never a sentinel number — on a missing
    head, a dimension mismatch, or a non-finite / non-positive / absurd
    result, so the caller falls back to empirical
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

_server_dir = str(Path(__file__).resolve().parent.parent)
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

os.environ.setdefault("DB_ENABLED", "false")

from workers.valuation_worker import (  # noqa: E402
    _MAX_SANE_PRICE_EUR,
    _MODEL_BLEND_ALPHA,
    _MODEL_SANITY_BAND,
    _predict_quantile,
)


def three_head_model(*, q10: float, q50: float, q90: float) -> dict:
    """An artifact with all three heads, distinguishable by intercept only.

    coef is zeroed so each head's output IS its intercept — that makes
    "did coef_key select the right head?" unambiguous.
    """
    return {
        "features": ["price", "condition"],
        "standardizer": {"mean": [100.0, 0.5], "std": [50.0, 0.25]},
        "ridge": {"coef": [0.0, 0.0], "intercept": q50},
        "ridge_q10": {"coef": [0.0, 0.0], "intercept": q10},
        "ridge_q90": {"coef": [0.0, 0.0], "intercept": q90},
    }


FV = {"price": 150.0, "condition": 0.75}


class TestHeadSelection:
    """The V3 feature that had zero coverage."""

    def test_each_key_runs_its_own_head(self):
        model = three_head_model(q10=10.0, q50=50.0, q90=90.0)
        assert _predict_quantile(model, FV, "ridge_q10") == pytest.approx(10.0)
        assert _predict_quantile(model, FV, "ridge") == pytest.approx(50.0)
        assert _predict_quantile(model, FV, "ridge_q90") == pytest.approx(90.0)

    def test_default_key_is_the_median_head(self):
        model = three_head_model(q10=10.0, q50=50.0, q90=90.0)
        assert _predict_quantile(model, FV) == _predict_quantile(model, FV, "ridge")

    def test_missing_head_returns_none_so_caller_falls_back(self):
        """A q50-only artifact must not silently answer for q10/q90.

        valuation_worker treats None as "use the empirical quantile for this
        head" — returning the q50 value instead would collapse the band.
        """
        model = {
            "features": ["price"],
            "standardizer": {"mean": [100.0], "std": [50.0]},
            "ridge": {"coef": [0.0], "intercept": 50.0},
        }
        assert _predict_quantile(model, {"price": 150.0}, "ridge") == pytest.approx(50.0)
        assert _predict_quantile(model, {"price": 150.0}, "ridge_q10") is None
        assert _predict_quantile(model, {"price": 150.0}, "ridge_q90") is None

    def test_head_present_but_malformed_returns_none(self):
        model = {
            "features": ["price"],
            "standardizer": {"mean": [100.0], "std": [50.0]},
            "ridge": {"intercept": 50.0},  # no "coef"
        }
        assert _predict_quantile(model, {"price": 150.0}, "ridge") is None

    def test_unknown_key_returns_none(self):
        model = three_head_model(q10=10.0, q50=50.0, q90=90.0)
        assert _predict_quantile(model, FV, "ridge_q99") is None


class TestFeatureVectorAssembly:
    def test_missing_feature_defaults_to_neutral_half_not_zero(self):
        """0.0 would be an EXTREME on a [0,1] score, not a neutral one.

        Pinned because the difference is invisible until it moves a price:
        with mean 0.5 / std 0.25, a missing feature at 0.5 standardizes to
        0.0 and contributes nothing, whereas 0.0 would standardize to -2.0
        and drag the prediction by -2*coef.
        """
        model = {
            "features": ["price", "condition"],
            "standardizer": {"mean": [100.0, 0.5], "std": [50.0, 0.25]},
            "ridge": {"coef": [0.0, 10.0], "intercept": 100.0},
        }
        # `condition` omitted -> 0.5 -> standardized 0.0 -> contributes 0
        assert _predict_quantile(model, {"price": 150.0}, "ridge") == pytest.approx(100.0)
        # explicit 0.0 -> standardized -2.0 -> contributes -20
        assert _predict_quantile(
            model, {"price": 150.0, "condition": 0.0}, "ridge"
        ) == pytest.approx(80.0)

    def test_vector_follows_artifact_feature_order_not_dict_order(self):
        model = {
            "features": ["b", "a"],
            "standardizer": {"mean": [0.0, 0.0], "std": [1.0, 1.0]},
            "ridge": {"coef": [1.0, 100.0], "intercept": 0.0},
        }
        # a=1 lands on coef 100, b=2 on coef 1 -> 102, regardless of dict order
        assert _predict_quantile(model, {"a": 1.0, "b": 2.0}, "ridge") == pytest.approx(102.0)
        assert _predict_quantile(model, {"b": 2.0, "a": 1.0}, "ridge") == pytest.approx(102.0)

    def test_empty_feature_values_still_predicts_from_defaults(self):
        model = {
            "features": ["price"],
            "standardizer": {"mean": [0.5], "std": [1.0]},
            "ridge": {"coef": [0.0], "intercept": 42.0},
        }
        assert _predict_quantile(model, {}, "ridge") == pytest.approx(42.0)


class TestClampsApplyPerHead:
    """The guards are per-call, so a single rogue head cannot poison a band."""

    def test_absurd_q90_is_dropped_while_q10_and_q50_survive(self):
        model = three_head_model(q10=10.0, q50=50.0, q90=1_500_000_000.0)
        assert _predict_quantile(model, FV, "ridge_q10") == pytest.approx(10.0)
        assert _predict_quantile(model, FV, "ridge") == pytest.approx(50.0)
        assert _predict_quantile(model, FV, "ridge_q90") is None

    def test_boundary_of_max_sane_price(self):
        just_over = three_head_model(q10=1.0, q50=1.0, q90=_MAX_SANE_PRICE_EUR + 1.0)
        assert _predict_quantile(just_over, FV, "ridge_q90") is None
        exactly = three_head_model(q10=1.0, q50=1.0, q90=_MAX_SANE_PRICE_EUR)
        assert _predict_quantile(exactly, FV, "ridge_q90") == pytest.approx(_MAX_SANE_PRICE_EUR)

    def test_zero_and_negative_are_rejected(self):
        """A price of exactly 0 is not a valid valuation either."""
        assert _predict_quantile(three_head_model(q10=0.0, q50=1.0, q90=2.0), FV, "ridge_q10") is None
        assert _predict_quantile(three_head_model(q10=-5.0, q50=1.0, q90=2.0), FV, "ridge_q10") is None

    def test_non_finite_is_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            model = three_head_model(q10=bad, q50=1.0, q90=2.0)
            assert _predict_quantile(model, FV, "ridge_q10") is None

    def test_never_raises_on_a_malformed_artifact(self):
        """Returning None is the contract; an exception would abort the cycle."""
        for broken in (
            {},
            {"features": ["price"]},
            {"features": ["price"], "standardizer": {}, "ridge": {"coef": [1.0], "intercept": 0.0}},
            {"features": None, "standardizer": {"mean": [1.0], "std": [1.0]},
             "ridge": {"coef": [1.0], "intercept": 0.0}},
        ):
            assert _predict_quantile(broken, FV, "ridge") is None


class TestLogScaleHeads:
    def test_log_scale_applies_to_every_head(self):
        model = {
            "log_scale": True,
            "features": ["price"],
            "standardizer": {"mean": [0.0], "std": [1.0]},
            "ridge": {"coef": [0.0], "intercept": math.log1p(50.0)},
            "ridge_q10": {"coef": [0.0], "intercept": math.log1p(20.0)},
            "ridge_q90": {"coef": [0.0], "intercept": math.log1p(120.0)},
        }
        fv = {"price": 0.0}
        assert _predict_quantile(model, fv, "ridge_q10") == pytest.approx(20.0, rel=1e-6)
        assert _predict_quantile(model, fv, "ridge") == pytest.approx(50.0, rel=1e-6)
        assert _predict_quantile(model, fv, "ridge_q90") == pytest.approx(120.0, rel=1e-6)


class TestBoundaryOfResponsibility:
    """What this function deliberately does NOT do.

    Pinned so a future reader does not "fix" a non-bug, and so the caller's
    obligations stay visible from the unit's own tests.
    """

    def test_does_not_enforce_monotonicity_across_heads(self):
        """q10 > q90 is returned as-is; run_once() sorts the blend.

        price_predictions carries a q10<=q50<=q90 CHECK, and the caller
        satisfies it with `sorted((b10, b50, b90))`. If that sort is ever
        removed, this test documents that the constraint is NOT upheld here.
        """
        inverted = three_head_model(q10=900.0, q50=50.0, q90=10.0)
        assert _predict_quantile(inverted, FV, "ridge_q10") == pytest.approx(900.0)
        assert _predict_quantile(inverted, FV, "ridge_q90") == pytest.approx(10.0)

    def test_does_not_apply_the_sanity_band_or_blend_weight(self):
        """Both live in run_once, not here — this returns the raw head.

        _MODEL_SANITY_BAND rejects a model q50 wildly off the item's own
        comps, and _MODEL_BLEND_ALPHA weights model vs empirical only when
        the calibration gate passed. Neither is this function's job.
        """
        assert _MODEL_SANITY_BAND == 10.0
        assert _MODEL_BLEND_ALPHA == 0.7
        far_off = three_head_model(q10=1.0, q50=1_000_000.0, q90=2_000_000.0)
        assert _predict_quantile(far_off, FV, "ridge") == pytest.approx(1_000_000.0)
