"""What the pricing models actually being SERVED look like — for /admin/models.

Until 2026-09-27 /admin/models read `model_metrics` (last written 2026-04-24,
all `clip-v1.0.0`, n=0 — its writer went with the CLIP tier) and
`model_registry` (test rows "Demo", "TestCat"). The admin ML tab therefore
showed 61 "stale" CLIP models while serving used 54 Ridge models retrained
that same day.

Serving loads `<artifacts root>/<category>/active/model.json`
(app/ml/model_loader.py::_load_artifact_from_disk), and every retrain decision
is logged in `model_promotion_log` (workers/model_retrain_worker.py). This
module reads exactly those. Pure and root-injectable so it can be tested on
fixture trees.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _active_dir(cat_dir: Path) -> Optional[Path]:
    """Resolve `active` — a symlink on the box, or a file naming the version."""
    active = cat_dir / "active"
    if active.is_symlink() or active.is_dir():
        target = active.resolve()
        return target if target.is_dir() else None
    if active.is_file():
        try:
            cand = cat_dir / active.read_text().strip()
            return cand if cand.is_dir() else None
        except OSError:
            return None
    return None


def _parse_ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def serving_models(
    root: Optional[Path],
    promotions: dict[str, dict[str, Any]],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Per-category summary of the served model + its last retrain decision.

    `promotions` maps category -> the newest model_promotion_log row as a dict.
    Returns {"root", "models": [...], "unresolved": [...]}; `models` is empty
    and `root` None when no artifacts root exists — the caller must show that
    as "could not find the models", never as "no models".
    """
    now = now or datetime.now(timezone.utc)
    if root is None or not root.is_dir():
        return {"root": None, "models": [], "unresolved": []}

    models: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        category = cat_dir.name
        target = _active_dir(cat_dir)
        model_file = target / "model.json" if target else None
        if model_file is None or not model_file.is_file():
            unresolved.append(category)
            continue
        try:
            art = json.loads(model_file.read_text())
        except (OSError, ValueError):
            unresolved.append(category)
            continue

        fitted = _parse_ts(art.get("created_at")) or datetime.fromtimestamp(
            model_file.stat().st_mtime, tz=timezone.utc
        )
        versions_on_disk = sum(
            1 for p in cat_dir.iterdir() if p.is_dir() and not p.is_symlink() and p.name != "active"
        )
        decision = promotions.get(category)
        models.append({
            "category": category,
            "version": target.name,
            "model_type": art.get("model_type"),
            "fitted_at": fitted.isoformat(),
            "age_days": max(0, (now - fitted).days),
            "train_size": art.get("train_size"),
            # cv_mae is measured in the space the model is fitted in: with
            # log_scale it is a log-price error, not euros.
            "cv_mae": art.get("cv_mae"),
            "log_scale": bool(art.get("log_scale")),
            "versions_on_disk": versions_on_disk,
            "last_decision": None if decision is None else {
                "promoted": decision.get("promoted"),
                "holdout_n": decision.get("holdout_n"),
                "old_mae": decision.get("old_mae"),
                "new_mae": decision.get("new_mae"),
                "reason": decision.get("reason"),
                "at": decision.get("created_at"),
            },
        })
    return {"root": str(root), "models": models, "unresolved": unresolved}
