#!/usr/bin/env python3
"""
Local per-category model evaluation harness.

For each category with a trained Ridge model in artifacts/, computes:
  - Sample count
  - Cross-validated MAE (from model metadata)
  - Best alpha
  - Feature count
  - Inference smoke test (load + run a default prediction)

Surfaces underperforming categories so they can be prioritized for
more training data or feature engineering.

Usage:
    python -m scripts.eval_models_local
    python -m scripts.eval_models_local --category watches
    python -m scripts.eval_models_local --threshold 100  # only show MAE > 100
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"


def load_active_model(category: str) -> dict | None:
    """Load the active model.json for a category."""
    active_dir = ARTIFACTS_DIR / category / "active"
    model_path = active_dir / "model.json"
    if not model_path.exists():
        return None
    try:
        return json.loads(model_path.read_text())
    except Exception:
        return None


def smoke_test_inference(model: dict) -> tuple[bool, str]:
    """Run a sanity inference using default features."""
    try:
        feature_names = model.get("features", [])
        if not feature_names:
            return False, "no features"
        # Build default feature dict (all 0.5 except condition=0.9)
        feats = {f: 0.5 for f in feature_names}
        if "condition_score" in feats:
            feats["condition_score"] = 0.9
        # Manually compute Ridge prediction (skip sklearn import)
        coef = model.get("ridge", {}).get("coef", [])
        intercept = model.get("ridge", {}).get("intercept", 0.0)
        std = model.get("standardizer", {})
        means = std.get("mean", [0.0] * len(feature_names))
        stds = std.get("std", [1.0] * len(feature_names))
        x = [
            (feats[f] - means[i]) / (stds[i] if stds[i] > 0 else 1.0)
            for i, f in enumerate(feature_names)
        ]
        pred = intercept + sum(c * v for c, v in zip(coef, x))
        return True, f"€{pred:.2f}"
    except Exception as e:
        return False, str(e)[:40]


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained Ridge models")
    parser.add_argument("--category", help="Single category")
    parser.add_argument("--threshold", type=float, default=0,
                        help="Only show models with CV MAE > threshold")
    parser.add_argument("--csv", action="store_true", help="Output CSV")
    args = parser.parse_args()

    if not ARTIFACTS_DIR.exists():
        print(f"ERROR: artifacts dir not found at {ARTIFACTS_DIR}")
        sys.exit(1)

    categories: list[str] = []
    if args.category:
        categories = [args.category]
    else:
        categories = sorted([
            d.name for d in ARTIFACTS_DIR.iterdir()
            if d.is_dir() and (d / "active" / "model.json").exists()
        ])

    if not categories:
        print("No trained models found")
        sys.exit(0)

    if args.csv:
        print("category,mae,alpha,n_samples,n_features,smoke_test")
    else:
        print(f"\n{'='*70}")
        print(f"  MODEL EVALUATION REPORT — {len(categories)} categories")
        print(f"{'='*70}\n")

    rows = []
    for cat in categories:
        model = load_active_model(cat)
        if not model:
            continue

        mae = model.get("cv_mae", 0)
        alpha = model.get("alpha", 0)
        n = model.get("train_size", 0)
        n_feats = len(model.get("features", []))

        if args.threshold and mae <= args.threshold:
            continue

        ok, smoke_result = smoke_test_inference(model)
        smoke_status = "✓" if ok else "✗"

        rows.append({
            "category": cat,
            "mae": mae,
            "alpha": alpha,
            "n": n,
            "feats": n_feats,
            "smoke": f"{smoke_status} {smoke_result}",
        })

    # Sort by MAE descending (worst first)
    rows.sort(key=lambda r: -r["mae"])

    if args.csv:
        for r in rows:
            print(f"{r['category']},{r['mae']:.2f},{r['alpha']},{r['n']},{r['feats']},{r['smoke']}")
    else:
        print(
            f"  {'Category':<25}  {'MAE':>10}  {'Alpha':>8}  "
            f"{'N':>6}  {'Feats':>5}  Smoke"
        )
        print(f"  {'-'*25}  {'-'*10}  {'-'*8}  {'-'*6}  {'-'*5}  {'-'*15}")
        for r in rows:
            print(
                f"  {r['category']:<25}  €{r['mae']:>9.2f}  "
                f"{r['alpha']:>8.2f}  {r['n']:>6}  {r['feats']:>5}  {r['smoke']}"
            )

        print(f"\n  Total models: {len(rows)}")
        if rows:
            avg_mae = sum(r["mae"] for r in rows) / len(rows)
            print(f"  Average MAE:  €{avg_mae:.2f}")
            print(f"  Worst:        {rows[0]['category']} (€{rows[0]['mae']:.2f})")
            print(f"  Best:         {rows[-1]['category']} (€{rows[-1]['mae']:.2f})")


if __name__ == "__main__":
    main()
