"""Prune keeps what is served + the 3 newest others; never guesses.

2026-09-27: 2,219 model versions for 54 categories (pokemon 49) — every
retrain writes a folder and nothing deleted them. Merle: keep active + last 3.
"""
from pathlib import Path

from app.ml.model_versions import prune_category, versions_to_prune


def _versions(cat: Path, names):
    for n in names:
        (cat / n).mkdir(parents=True)
        (cat / n / "model.json").write_text("{}")


NAMES = ["20260101_000000", "20260201_000000", "20260301_000000",
         "20260401_000000", "20260501_000000", "20260601_000000"]


def test_keeps_active_plus_three_newest(tmp_path):
    cat = tmp_path / "pokemon"
    _versions(cat, NAMES)
    (cat / "active").symlink_to(cat / "20260601_000000")
    assert sorted(p.name for p in versions_to_prune(cat)) == ["20260101_000000", "20260201_000000"]


def test_an_old_active_after_a_revert_is_never_pruned(tmp_path):
    # Revert: active points at an OLD version while newer ones exist.
    cat = tmp_path / "lorcana"
    _versions(cat, NAMES)
    (cat / "active").symlink_to(cat / "20260101_000000")
    doomed = {p.name for p in versions_to_prune(cat)}
    assert "20260101_000000" not in doomed
    assert doomed == {"20260201_000000", "20260301_000000"}   # 3 newest others kept


def test_every_pointer_is_protected(tmp_path):
    cat = tmp_path / "mtg"
    _versions(cat, NAMES)
    (cat / "active").symlink_to(cat / "20260601_000000")
    (cat / "canary").symlink_to(cat / "20260101_000000")
    assert "20260101_000000" not in {p.name for p in versions_to_prune(cat)}


def test_active_as_a_plain_file_is_a_pointer(tmp_path):
    cat = tmp_path / "funko"
    _versions(cat, NAMES)
    (cat / "active").write_text("20260101_000000\n")
    assert "20260101_000000" not in {p.name for p in versions_to_prune(cat)}


def test_no_resolvable_pointer_prunes_nothing(tmp_path):
    cat = tmp_path / "orphan"
    _versions(cat, NAMES)
    assert versions_to_prune(cat) == []
    (cat / "active").symlink_to(cat / "does_not_exist")
    assert versions_to_prune(cat) == []


def test_only_version_named_directories_are_candidates(tmp_path):
    cat = tmp_path / "lego"
    _versions(cat, NAMES)
    (cat / "notes").mkdir()
    (cat / "active").symlink_to(cat / "20260601_000000")
    assert "notes" not in {p.name for p in versions_to_prune(cat)}


def test_apply_deletes_and_dry_run_does_not(tmp_path):
    cat = tmp_path / "watches"
    _versions(cat, NAMES)
    (cat / "active").symlink_to(cat / "20260601_000000")
    assert prune_category(cat, apply=False) and (cat / "20260101_000000").exists()
    prune_category(cat, apply=True)
    left = sorted(p.name for p in cat.iterdir())
    assert left == ["20260301_000000", "20260401_000000", "20260501_000000", "20260601_000000", "active"]
    assert (cat / "active" / "model.json").exists()


def test_the_retrain_worker_prunes_after_logging_the_decision():
    import inspect
    import workers.model_retrain_worker as w
    src = inspect.getsource(w)
    assert src.index("_log_promotion_sync(\n        category") < src.index("prune_category(artifacts_root / category, apply=True)")
