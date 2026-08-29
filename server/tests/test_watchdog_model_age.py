"""The serving-model-age check.

On 2026-08-29, 53 of 54 `active` models on the box dated from 2026-04-10 --
141 days -- and nothing anywhere reported it. `preflight_models.py` validates a
model FILE (finite coefficients, structure) and never its AGE; the calibration
worker measures PICP/ACE/MAE of the predictions but never asks when the model
behind them was fitted.

These exercise the real resolver against real fixture trees, known-BAD and
known-GOOD, because a check that has only ever produced one verdict has not
been shown to discriminate.
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.watchdog import serving_model_ages, serving_artifact_roots

DAY = 86400


def _make_category(root: Path, name: str, version: str, age_days: float,
                   link: bool = True) -> None:
    """Create artifacts/<name>/<version>/model.json aged `age_days`, plus
    an `active` pointer -- a symlink like the box, or a plain text file."""
    vdir = root / name / version
    vdir.mkdir(parents=True)
    mj = vdir / "model.json"
    mj.write_text('{"coef": [0.1], "intercept": 0.0}')
    stamp = time.time() - age_days * DAY
    os.utime(mj, (stamp, stamp))
    active = root / name / "active"
    if link:
        active.symlink_to(version)
    else:
        active.write_text(version)


def test_reports_the_real_age_of_each_active_model(tmp_path):
    """KNOWN-BAD: the shape actually found on the box."""
    root = tmp_path / "artifacts"
    _make_category(root, "pokemon", "20260410_085335", 141)
    _make_category(root, "mtg", "20260410_192059", 141)
    _make_category(root, "retro_games", "20260722_181725", 38)

    ages = dict(serving_model_ages([root]))
    assert ages["pokemon"] == 141
    assert ages["mtg"] == 141
    assert ages["retro_games"] == 38

    STALE = 90
    stale = [c for c, d in ages.items() if d > STALE]
    assert sorted(stale) == ["mtg", "pokemon"], \
        "the check must separate the stale ones from the freshly trained one"


def test_a_fresh_box_produces_no_finding(tmp_path):
    """KNOWN-GOOD: same code path, opposite verdict. Without this the test
    above passes for a checker that simply calls everything stale."""
    root = tmp_path / "artifacts"
    _make_category(root, "pokemon", "v1", 2)
    _make_category(root, "mtg", "v1", 5)

    ages = serving_model_ages([root])
    assert len(ages) == 2
    assert max(d for _, d in ages) == 5
    assert [c for c, d in ages if d > 90] == []


def test_an_active_pointer_that_is_a_plain_file_still_resolves(tmp_path):
    """preflight_models accepts `active` as a text file naming the version.
    If this resolver only understood symlinks it would report a false UNKNOWN
    on a box that is actually fine."""
    root = tmp_path / "artifacts"
    _make_category(root, "funko", "20260410_085428", 141, link=False)
    assert dict(serving_model_ages([root]))["funko"] == 141


def test_a_missing_root_returns_empty_so_the_caller_says_UNKNOWN(tmp_path):
    """`[]` here means could-not-ask. The caller must never render it as
    'models are fresh' -- the failure this watchdog keeps relearning."""
    assert serving_model_ages([tmp_path / "does_not_exist"]) == []


def test_a_category_with_no_active_pointer_is_skipped_not_counted_fresh(tmp_path):
    root = tmp_path / "artifacts"
    (root / "orphan" / "20260410_1").mkdir(parents=True)
    (root / "orphan" / "20260410_1" / "model.json").write_text("{}")
    _make_category(root, "pokemon", "v1", 141)
    ages = dict(serving_model_ages([root]))
    assert "orphan" not in ages, "no active pointer means we do not know what serves"
    assert ages["pokemon"] == 141


def test_roots_match_the_order_model_loader_uses(tmp_path):
    """If these drift apart the watchdog inspects a different tree than the
    one serving loads from, and reports confidently about the wrong files."""
    roots = [str(r) for r in serving_artifact_roots()]
    assert roots[0] == "/opt/collectors/server/artifacts"
    assert roots[1].endswith("artifacts")
