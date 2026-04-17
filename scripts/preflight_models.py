#!/usr/bin/env python3
"""
Pre-flight: verify Ridge model artifacts are structurally sound.

Checks the `active` symlink under each `server/artifacts/<category>/`.
For each active model.json:
  - JSON parses cleanly
  - ridge / ridge_q10 / ridge_q90 sections present
  - all intercepts + coefs are finite (no NaN, no Inf)
  - quantile intercepts are ordered q10 < q90 (warning only — log-scale
    models with large coefficients can legitimately have overlapping
    intercepts, but the common-case check still catches corruption)

This is a **warning-first** check — bad individual models log WARNING
rather than hard-failing boot, because one broken model shouldn't block
the whole bake. Set `--strict` to exit 1 on any issue.

Usage:
  python3 scripts/preflight_models.py
  python3 scripts/preflight_models.py --strict
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = os.path.join(REPO_ROOT, "server", "artifacts")


def _finite_list(xs) -> bool:
    if xs is None:
        return True
    try:
        return all(isinstance(v, (int, float)) and math.isfinite(v) for v in xs)
    except Exception:
        return False


def check_model_file(path: str) -> dict:
    entry = {"path": path, "ok": True, "issues": []}
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        entry["ok"] = False
        entry["issues"].append(f"JSON load failed: {e}")
        return entry

    entry["category"] = data.get("category")
    entry["version"] = data.get("version")

    for section in ("ridge", "ridge_q10", "ridge_q90"):
        s = data.get(section)
        if not isinstance(s, dict):
            entry["ok"] = False
            entry["issues"].append(f"missing section '{section}'")
            continue
        intercept = s.get("intercept")
        if not isinstance(intercept, (int, float)) or not math.isfinite(intercept):
            entry["ok"] = False
            entry["issues"].append(f"{section}.intercept not finite ({intercept!r})")
        if not _finite_list(s.get("coef")):
            entry["ok"] = False
            entry["issues"].append(f"{section}.coef contains NaN/Inf")

    # Soft check: q10 intercept should be ≤ q90 intercept on raw-price
    # (non-log-scale) models. For log-scale models this is still usually
    # true at the intercept level.
    q10 = (data.get("ridge_q10") or {}).get("intercept")
    q90 = (data.get("ridge_q90") or {}).get("intercept")
    if (isinstance(q10, (int, float)) and isinstance(q90, (int, float))
            and math.isfinite(q10) and math.isfinite(q90)
            and q10 > q90):
        entry["ok"] = False
        entry["issues"].append(f"quantile intercepts inverted: q10={q10} > q90={q90}")

    return entry


def discover_active_models() -> list[str]:
    """Return list of active model.json paths (one per category)."""
    if not os.path.isdir(ARTIFACTS_DIR):
        return []
    found: list[str] = []
    for category in sorted(os.listdir(ARTIFACTS_DIR)):
        cat_dir = os.path.join(ARTIFACTS_DIR, category)
        if not os.path.isdir(cat_dir):
            continue
        active = os.path.join(cat_dir, "active")
        # `active` can be a symlink to a version dir OR a plain file that
        # contains the version name as text.
        version_dir: str | None = None
        if os.path.islink(active) or os.path.isdir(active):
            resolved = os.path.realpath(active)
            if os.path.isdir(resolved):
                version_dir = resolved
        elif os.path.isfile(active):
            try:
                with open(active) as f:
                    version = f.read().strip()
                candidate = os.path.join(cat_dir, version)
                if os.path.isdir(candidate):
                    version_dir = candidate
            except Exception:
                pass

        # Fallback: newest version subdir
        if not version_dir:
            subdirs = [
                os.path.join(cat_dir, d) for d in os.listdir(cat_dir)
                if os.path.isdir(os.path.join(cat_dir, d)) and d != "active"
            ]
            if subdirs:
                version_dir = max(subdirs, key=os.path.getmtime)

        if version_dir:
            model_path = os.path.join(version_dir, "model.json")
            if os.path.isfile(model_path):
                found.append(model_path)
    return found


def main() -> int:
    p = argparse.ArgumentParser(description="Model artifact integrity pre-flight")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true",
                   help="exit 1 on any issue (default: warn only)")
    args = p.parse_args()

    paths = discover_active_models()
    if not paths:
        print("WARN: no model artifacts found under server/artifacts/")
        return 0

    results = [check_model_file(p) for p in paths]
    bad = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({
            "ok": not bad,
            "total": len(results),
            "bad": len(bad),
            "models": results,
        }, indent=2))
    else:
        print("─" * 72)
        print(f"  Model artifact pre-flight — {len(results)} active models")
        print("─" * 72)
        if not bad:
            print(f"✅ All {len(results)} active models are structurally sound.")
        else:
            print(f"⚠️  {len(bad)} model(s) have integrity issues:")
            for r in bad:
                print(f"  ✗ {r.get('category') or '?'} ({r.get('version') or '?'})")
                for issue in r["issues"]:
                    print(f"      {issue}")
            print()
            if args.strict:
                print("Strict mode: exiting 1. Retrain or roll back the listed models.")
            else:
                print("Warn-only mode: bake will boot but predictions from these")
                print("categories may be unreliable. Retrain or roll back.")
        print("─" * 72)
        verdict = "PASS" if not bad else ("FAIL" if args.strict else "WARN")
        print(f"  verdict: {verdict}")
        print("─" * 72)

    return 1 if (bad and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
