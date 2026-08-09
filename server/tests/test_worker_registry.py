"""Tests for app.worker_registry — record_run() and get_status()."""

import time
from unittest.mock import patch

import pytest

import app.worker_registry as wr


@pytest.fixture(autouse=True)
def _clear_registry():
    """Reset the in-memory registry before each test."""
    wr._registry.clear()
    yield
    wr._registry.clear()


# ---------------------------------------------------------------------------
# record_run
# ---------------------------------------------------------------------------

class TestRecordRun:
    def test_first_run_creates_entry(self):
        wr.record_run("price_monitor")
        assert "price_monitor" in wr._registry
        entry = wr._registry["price_monitor"]
        assert entry["runs"] == 1
        assert entry["errors"] == 0
        assert entry["last_status"] == "ok"
        assert "last_run" in entry

    def test_multiple_ok_runs_increment_count(self):
        wr.record_run("price_monitor")
        wr.record_run("price_monitor")
        wr.record_run("price_monitor")
        assert wr._registry["price_monitor"]["runs"] == 3
        assert wr._registry["price_monitor"]["errors"] == 0

    def test_error_run_increments_errors(self):
        wr.record_run("category_map_worker", status="error")
        entry = wr._registry["category_map_worker"]
        assert entry["runs"] == 1
        assert entry["errors"] == 1
        assert entry["last_status"] == "error"

    def test_mixed_runs(self):
        wr.record_run("vision_ingest", status="ok")
        wr.record_run("vision_ingest", status="ok")
        wr.record_run("vision_ingest", status="error")
        wr.record_run("vision_ingest", status="ok")
        entry = wr._registry["vision_ingest"]
        assert entry["runs"] == 4
        assert entry["errors"] == 1
        assert entry["last_status"] == "ok"

    def test_last_run_is_recent_timestamp(self):
        before = time.time()
        wr.record_run("price_monitor")
        after = time.time()
        last_run = wr._registry["price_monitor"]["last_run"]
        assert before <= last_run <= after

    def test_independent_workers(self):
        wr.record_run("price_monitor")
        wr.record_run("category_map_worker")
        assert wr._registry["price_monitor"]["runs"] == 1
        assert wr._registry["category_map_worker"]["runs"] == 1


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_initial_status_all_workers(self):
        """Without any runs, all scheduled workers should appear with None last_run."""
        status = wr.get_status()
        for name in wr.SCHEDULES:
            assert name in status
            assert status[name]["last_run_ago_s"] is None
            assert status[name]["last_status"] is None
            assert status[name]["total_runs"] == 0
            assert status[name]["total_errors"] == 0
            assert status[name]["overdue"] is False

    def test_after_run_fields_populated(self):
        wr.record_run("price_monitor", status="ok")
        status = wr.get_status()
        pm = status["price_monitor"]
        assert pm["last_run_ago_s"] is not None
        assert pm["last_run_ago_s"] >= 0
        assert pm["last_status"] == "ok"
        assert pm["total_runs"] == 1
        assert pm["total_errors"] == 0

    def test_overdue_detection(self):
        """A worker whose last run exceeds 1.5x its schedule should be overdue."""
        # price_monitor schedule = 6 * 3600 = 21600s
        # overdue threshold = 21600 * 1.5 = 32400s
        wr.record_run("price_monitor")
        # Simulate the last_run being far in the past
        wr._registry["price_monitor"]["last_run"] = time.time() - 40000
        status = wr.get_status()
        assert status["price_monitor"]["overdue"] is True

    def test_not_overdue_when_recent(self):
        wr.record_run("price_monitor")
        status = wr.get_status()
        assert status["price_monitor"]["overdue"] is False

    def test_on_demand_worker_never_overdue(self):
        """vision_ingest has schedule_interval=0, so it should never be overdue."""
        wr.record_run("vision_ingest")
        wr._registry["vision_ingest"]["last_run"] = time.time() - 999999
        status = wr.get_status()
        assert status["vision_ingest"]["overdue"] is False
        assert status["vision_ingest"]["schedule_interval_s"] is None

    def test_schedule_intervals_present(self):
        status = wr.get_status()
        assert status["price_monitor"]["schedule_interval_s"] == 6 * 3600
        assert status["category_map_worker"]["schedule_interval_s"] == 3600
        assert status["vision_ingest"]["schedule_interval_s"] is None

    def test_error_count_reflected(self):
        wr.record_run("category_map_worker", status="error")
        wr.record_run("category_map_worker", status="error")
        wr.record_run("category_map_worker", status="ok")
        status = wr.get_status()
        assert status["category_map_worker"]["total_runs"] == 3
        assert status["category_map_worker"]["total_errors"] == 2
