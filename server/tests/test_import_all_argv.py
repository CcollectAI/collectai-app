"""import_all.run_import must not race on sys.argv, and a pipeline's SystemExit
must not kill the run (2026-10-04).

The 2026-10-02 nightly died with "import_all.py: error: unrecognized
arguments: --parallel 4" and exit code 2: run_import swapped the process-global
sys.argv per call, one thread restored `--parallel 4` while another pipeline
was inside parse_args(), and the resulting SystemExit escaped `except
Exception` through future.result().
"""

import argparse
import os
import sys
import types
from pathlib import Path

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines import import_all  # noqa: E402


def _install(name, main):
    mod = types.ModuleType(f"pipelines.{name}")
    mod.main = main
    sys.modules[f"pipelines.{name}"] = mod
    return name


def test_run_import_leaves_sys_argv_alone(monkeypatch):
    seen = {}

    def main():
        seen["argv"] = list(sys.argv)

    name = _install("_fake_argv_reader", main)
    # A sentinel run_import could never build itself, so a per-call swap shows.
    monkeypatch.setattr(sys, "argv", ["sentinel-argv"])
    ok, err = import_all.run_import(name, "fake", "fake", dry_run=True)
    assert ok, err
    assert seen["argv"] == ["sentinel-argv"]
    assert sys.argv == ["sentinel-argv"]


def test_a_pipeline_argparse_error_is_that_pipelines_failure(monkeypatch):
    def main():
        p = argparse.ArgumentParser()
        p.add_argument("--dry-run", action="store_true")
        p.parse_args()   # sees --parallel 4 -> SystemExit(2)

    name = _install("_fake_strict_parser", main)
    monkeypatch.setattr(sys, "argv", ["import_all.py", "--parallel", "4"])
    ok, err = import_all.run_import(name, "fake", "fake", dry_run=False)
    assert not ok
    assert "exited with code 2" in err


def test_pipeline_argv_carries_only_the_run_wide_flags():
    assert import_all.pipeline_argv(False, False) == ["import_all"]
    assert import_all.pipeline_argv(True, True) == ["import_all", "--dry-run", "--cache-images"]
