"""A heavy worker holding the gate is not a wedged orchestrator.

2026-09-01: the watchdog paged "no worker runs in 19 mins, orchestrator may be
wedged". It was not. bake restarted at 11:34, valuation_worker took _HEAVY_LOCK
and ran 1466.9s — its ORDINARY duration (recent runs: 850s, 1053s, 1509s,
1234s, 1371s) — and lorcast/discogs/model_retrain each logged "waited ~1467s
for heavy gate". Every worker queues behind that lock, so while it is held
NOTHING writes a worker_runs row and `wr_recent == 0` is the normal state.

The ingest_stalled check directly above already had this exemption, added when
it "fired a daily false page". It was never applied to worker_runs_stalled, so
that one kept paging — the fix landed on one instance, not the class.
"""
import pathlib

SRC = (pathlib.Path(__file__).resolve().parents[1]
       / "workers" / "bake_orchestrator.py").read_text()


def _block(name: str) -> str:
    """The source between a check's marker and the next one."""
    i = SRC.index(name)
    return SRC[i:i + 2500]


class TestWorkerRunsStalledIsGateAware:
    def test_it_checks_the_heavy_holder_before_paging(self):
        blk = _block('"worker_runs_stalled"')
        # Look BEFORE the append, where the guard must sit.
        i = SRC.index('if wr_recent == 0:')
        guard = SRC[i:SRC.index('"worker_runs_stalled"')]
        assert "_HEAVY_HOLDER" in guard, (
            "worker_runs_stalled pages without consulting the heavy gate, so it "
            "fires after every restart while a normal heavy worker runs"
        )
        assert "_HEAVY_GATE_SANE_CAP_S" in guard

    def test_a_genuinely_wedged_holder_STILL_pages(self):
        # The exemption must not become a mute button: past the sane cap, or
        # with no holder at all, it must still page.
        i = SRC.index('if wr_recent == 0:')
        guard = SRC[i:SRC.index('"worker_runs_stalled"')]
        assert "holder is None or held_s > _HEAVY_GATE_SANE_CAP_S" in guard

    def test_the_benign_case_is_LOGGED_not_silent(self):
        # A check that goes quiet without saying why is indistinguishable from
        # a check that broke — docs/WATCHDOG.md, "Checks that go quiet".
        i = SRC.index('if wr_recent == 0:')
        blk = SRC[i:i + 3000]
        assert "benign queueing, not paging" in blk


class TestItMatchesTheIngestCheck:
    def test_both_checks_use_the_same_guard(self):
        # Two stall checks with different rules is how one of them drifts.
        assert SRC.count("holder is None or held_s > _HEAVY_GATE_SANE_CAP_S") == 2, (
            "ingest_stalled and worker_runs_stalled must share the exemption; "
            "if they diverge, one of them starts crying wolf again"
        )

    def test_the_sane_cap_still_bounds_it(self):
        # 3h, against a worst observed valuation_worker run of ~2.75h.
        assert "_HEAVY_GATE_SANE_CAP_S" in SRC
        assert "3 * 3600" in SRC
