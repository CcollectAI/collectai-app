#!/usr/bin/env python3
"""
Pre-flight gate for the data bake pipeline.

Loads every active Ridge artifact in server/artifacts/<cat>/active/model.json,
runs a default-input inference smoke test, and fails with exit code 1 if any
model produces pathological output. Use this to block bad training runs from
being promoted to production.

Checks (in order):
  1. Artifact loads as valid JSON
  2. Required keys present (model_type, features, standardizer, ridge)
  3. Feature/coef length alignment
  4. Smoke inference returns a finite q10 ≤ q50 ≤ q90 triple
  5. All quantiles are non-negative
  6. q90 ≤ MAX_SANE_EUR (catches runaway intercepts)
  7. Optional: CV MAE ≤ --max-mae flag (default: disabled)

Usage:
    python -m scripts.verify_baked_models                 # run all gates, exit 0/1
    python -m scripts.verify_baked_models --max-mae 5000  # also gate on MAE
    python -m scripts.verify_baked_models --verbose       # print per-category results

Exit codes:
  0 — all models pass
  1 — one or more models failed a gate
  2 — artifacts directory missing (infra problem, not a model problem)

This is intentionally separate from eval_models_local.py:
  - eval_models_local.py is a *report* (always exits 0)
  - verify_baked_models.py is a *gate* (exits non-zero on failure)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# Allow `python -m scripts.verify_baked_models` from server/ without PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from inference import ridge_infer_quantiles

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
MAX_SANE_EUR = 50_000_000  # Grail-tier ceiling; matches test_inference.py


def build_default_features(feature_names: list[str]) -> dict[str, float]:
    """Construct a reasonable "average scan" input.

    Matches the smoke test in test_inference.py exactly so local tests and
    the verify gate catch the same regressions.
    """
    features: dict[str, float] = {f: 0.5 for f in feature_names}
    if "condition_score" in features:
        features["condition_score"] = 0.85  # Near Mint
    if "is_sealed" in features:
        features["is_sealed"] = 0.0
    if "is_graded" in features:
        features["is_graded"] = 0.0
    return features


def verify_one(category: str, artifact: dict, max_mae: float | None) -> tuple[bool, str]:
    """Run all gates against a single artifact. Returns (passed, reason)."""
    model_type = artifact.get("model_type", "")
    if model_type not in ("ridge_v1", "ridge_v2"):
        return False, f"unsupported model_type: {model_type!r}"

    feature_names = artifact.get("features", [])
    if not feature_names:
        return False, "empty features list"

    coef = artifact.get("ridge", {}).get("coef", [])
    if len(coef) != len(feature_names):
        return False, f"coef/features length mismatch ({len(coef)} vs {len(feature_names)})"

    features = build_default_features(feature_names)
    result = ridge_infer_quantiles(artifact, features)
    if result is None:
        return False, "ridge_infer_quantiles returned None"

    q10 = result.get("q10")
    q50 = result.get("q50")
    q90 = result.get("q90")
    if q10 is None or q50 is None or q90 is None:
        return False, f"missing quantile keys: {result}"

    for name, val in (("q10", q10), ("q50", q50), ("q90", q90)):
        if not math.isfinite(val):
            return False, f"{name} is not finite: {val}"
        if val < 0:
            return False, f"{name} is negative: {val}"

    if not (q10 <= q50 <= q90):
        return False, f"quantile ordering violated (q10={q10}, q50={q50}, q90={q90})"

    if q90 > MAX_SANE_EUR:
        return False, f"q90 exceeds €{MAX_SANE_EUR:,} sanity ceiling: €{q90:,.2f}"

    # Optional CV MAE gate
    if max_mae is not None:
        cv_mae = artifact.get("cv_mae")
        if cv_mae is not None and cv_mae > max_mae:
            return False, f"CV MAE €{cv_mae:,.2f} exceeds max €{max_mae:,.2f}"

    return True, f"q50=€{q50:,.2f} (q10=€{q10:,.2f} q90=€{q90:,.2f})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate baked Ridge models before production")
    parser.add_argument("--max-mae", type=float, default=None,
                        help="Fail if any model has CV MAE above this (EUR). Default: disabled.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print per-category results, not just failures")
    parser.add_argument("--category", help="Verify a single category")
    args = parser.parse_args()

    if not ARTIFACTS_DIR.exists():
        print(f"ERROR: artifacts dir missing at {ARTIFACTS_DIR}", file=sys.stderr)
        return 2

    failed: list[tuple[str, str]] = []
    passed = 0

    if args.category:
        categories = [args.category]
    else:
        categories = sorted(p.name for p in ARTIFACTS_DIR.iterdir() if p.is_dir())

    for cat in categories:
        model_path = ARTIFACTS_DIR / cat / "active" / "model.json"
        if not model_path.exists():
            if args.verbose:
                print(f"  SKIP {cat:30s} (no active model)")
            continue

        try:
            artifact = json.loads(model_path.read_text())
        except Exception as e:
            failed.append((cat, f"unreadable JSON: {e}"))
            continue

        ok, reason = verify_one(cat, artifact, args.max_mae)
        if ok:
            passed += 1
            if args.verbose:
                print(f"  PASS {cat:30s} {reason}")
        else:
            failed.append((cat, reason))

    total = passed + len(failed)
    print()
    print(f"Verified {total} models: {passed} passed, {len(failed)} failed")

    if failed:
        print()
        print("FAILURES:")
        for cat, reason in failed:
            print(f"  ✗ {cat}: {reason}")
        return 1

    print("All gates passed ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
