"""Prune old model versions: keep what is served + the 3 newest others.

Every retrain writes a new `artifacts/<category>/<YYYYMMDD_HHMMSS>/` folder and
flips `active` to it (pipelines/train_price.py). Nothing ever deleted the old
ones, and until 2026-09-27 every bake restart re-ran the weekly retrain
(class AT), so prod held 2,219 versions for 54 categories — pokemon 49.
Merle, 2026-09-27: "keep active plus last 3".

Rules, per category:
  - only real directories named like a version are candidates;
  - anything a pointer in the category folder targets is PROTECTED — `active`
    today, `canary` if it is ever used (model_loader supports that slot);
  - of the rest, the `keep_recent` newest (names sort by time) are kept;
  - if no pointer resolves, NOTHING is pruned: we cannot tell what is served.

Runs after the promotion decision in model_retrain_worker, so the version a
revert would restore (the pre-retrain `active`) is either still `active` or
among the newest kept.

    python -m app.ml.model_versions            # dry run: print what would go
    python -m app.ml.model_versions --apply    # delete
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

VERSION_RE = re.compile(r"^\d{8}_\d{6}$")
KEEP_RECENT = 3


def _pointer_targets(cat_dir: Path) -> set[Path]:
    """Resolved version dirs that any symlink or pointer file here names."""
    targets: set[Path] = set()
    for entry in cat_dir.iterdir():
        if entry.is_symlink():
            t = entry.resolve()
            if t.is_dir():
                targets.add(t)
        elif entry.is_file() and not VERSION_RE.match(entry.name):
            # `active` may be a plain file holding a version name (preflight_models)
            try:
                cand = cat_dir / entry.read_text().strip()
            except (OSError, UnicodeDecodeError):
                continue
            if cand.is_dir():
                targets.add(cand.resolve())
    return targets


def versions_to_prune(cat_dir: Path, keep_recent: int = KEEP_RECENT) -> list[Path]:
    protected = _pointer_targets(cat_dir)
    if not protected:
        return []  # cannot tell what is served — touch nothing
    versions = sorted(
        (p for p in cat_dir.iterdir()
         if p.is_dir() and not p.is_symlink() and VERSION_RE.match(p.name)),
        key=lambda p: p.name,
        reverse=True,
    )
    others = [v for v in versions if v.resolve() not in protected]
    return others[keep_recent:]


def prune_category(cat_dir: Path, keep_recent: int = KEEP_RECENT, apply: bool = False) -> list[str]:
    doomed = versions_to_prune(cat_dir, keep_recent)
    if apply:
        for d in doomed:
            shutil.rmtree(d)
    return [d.name for d in doomed]


def prune_all(root: Path, keep_recent: int = KEEP_RECENT, apply: bool = False) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink()):
        names = prune_category(cat_dir, keep_recent, apply)
        if names:
            out[cat_dir.name] = names
    return out


def main(argv: list[str]) -> int:
    from app.ml.model_loader import _resolve_artifacts_root

    root = _resolve_artifacts_root()
    if root is None:
        print("no artifacts root found", file=sys.stderr)
        return 2
    apply = "--apply" in argv
    result = prune_all(root, apply=apply)
    n = sum(len(v) for v in result.values())
    print(f"{'deleted' if apply else 'would delete'} {n} versions in {len(result)} categories under {root}")
    for cat, names in result.items():
        print(f"  {cat}: {len(names)} ({names[-1]} .. {names[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
