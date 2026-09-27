"""The admin ML tab shows the SERVED models; Worker Health says "disabled".

2026-09-27: /admin/models read model_metrics (dead since 2026-04-24, all
clip-v1.0.0) and model_registry (test rows) while serving used Ridge models
fitted that day; Worker Health called 15 deliberately-off workers "never run".
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.lib.model_summary import serving_models
from app import worker_registry as wr

NOW = datetime(2026, 9, 27, 21, 0, tzinfo=timezone.utc)


def _model(cat_dir: Path, version: str, created_at: str, **extra) -> Path:
    v = cat_dir / version
    v.mkdir(parents=True)
    (v / "model.json").write_text(json.dumps({
        "created_at": created_at, "cv_mae": 0.86, "train_size": 1000,
        "model_type": "ridge_v2", "log_scale": True, **extra,
    }))
    return v


def test_reads_the_active_symlink_and_counts_versions(tmp_path):
    # A REVERTED retrain: the newest directory exists but `active` still points
    # at the older one (lorcana, 2026-08-29). Serving loads the older one.
    cat = tmp_path / "pokemon"
    _model(cat, "20260920_000000", "2026-09-20T00:00:00+00:00")
    _model(cat, "20260927_173914", "2026-09-27T17:39:14+00:00")
    (cat / "active").symlink_to(cat / "20260920_000000")
    out = serving_models(tmp_path, {"pokemon": {"promoted": False, "holdout_n": 3, "reason": "reverted"}}, NOW)
    m = out["models"][0]
    assert m["version"] == "20260920_000000"          # what serving loads, not the newest dir by name
    assert m["age_days"] == 7
    assert m["versions_on_disk"] == 2                  # the symlink itself is not a version
    assert m["log_scale"] is True and m["cv_mae"] == 0.86
    assert m["last_decision"]["promoted"] is False
    assert out["unresolved"] == []


def test_active_as_a_plain_file_naming_the_version(tmp_path):
    cat = tmp_path / "lorcana"
    _model(cat, "20260410_085331", "2026-04-10T08:53:31+00:00")
    (cat / "active").write_text("20260410_085331\n")
    m = serving_models(tmp_path, {}, NOW)["models"][0]
    assert m["version"] == "20260410_085331"
    assert m["age_days"] == 170
    assert m["last_decision"] is None


def test_a_category_without_an_active_model_is_reported_not_dropped(tmp_path):
    (tmp_path / "artifacts").mkdir()          # the stray nested dir on prod
    out = serving_models(tmp_path, {}, NOW)
    assert out["models"] == [] and out["unresolved"] == ["artifacts"]


def test_no_root_is_could_not_ask_not_no_models(tmp_path):
    assert serving_models(None, {}, NOW)["root"] is None
    assert serving_models(tmp_path / "missing", {}, NOW)["root"] is None


def test_disabled_workers_are_not_never_run(monkeypatch):
    monkeypatch.setattr(wr, "_registry", {})
    monkeypatch.setattr(wr, "_enabled", None)
    monkeypatch.setattr(wr, "SCHEDULES", {"started_w": 3600, "switched_off_w": 3600})
    # Orchestrator not started (tests, scripts): nothing is called disabled.
    by = {w["name"]: w["status"] for w in wr.get_worker_health()["workers"]}
    assert by == {"started_w": "never_run", "switched_off_w": "never_run"}
    wr.mark_enabled("started_w")
    h = wr.get_worker_health()
    by = {w["name"]: w["status"] for w in h["workers"]}
    assert by == {"started_w": "never_run", "switched_off_w": "disabled"}
    assert h["summary"]["disabled"] == 1 and h["summary"]["never_run"] == 1


def test_a_disabled_worker_is_never_overdue(monkeypatch):
    import time
    monkeypatch.setattr(wr, "SCHEDULES", {"switched_off_w": 60})
    monkeypatch.setattr(wr, "_registry", {"switched_off_w": {"last_run": time.time() - 99999, "runs": 1, "errors": 0}})
    monkeypatch.setattr(wr, "_enabled", {"something_else"})
    assert wr.get_overdue_workers() == []


def test_the_orchestrator_marks_every_loop_it_starts():
    import inspect
    import workers.bake_orchestrator as bo
    src = inspect.getsource(bo.start_all_workers)
    assert "mark_enabled(registry_name)" in src
    assert 'mark_enabled(_mv)' in src and '"matview_demand"' in src
    assert 'mark_enabled("task_worker")' in src
