"""Tests for workers/grade_reminder_worker.py — the "rate your trade" nudge.

Three things are pinned, each because of a failure mode this repo has already
paid for:

  1. **It is REGISTERED.** A worker that exists and is not in the bake manifest
     is a feature reachable from nowhere; a worker in the manifest with no
     entry in `SCHEDULES` never fires. Both are silent
     (learning_complete_feature_reachable_from_nowhere).
  2. **It sends at most once per party per trade.** The idempotency guard lives
     in the query, not in the caller, so a re-run after a crash cannot double-
     nudge. Losing either NOT EXISTS is invisible until someone is spammed.
  3. **The 24h boundary is in the QUERY, not in the schedule.** A worker that
     oversleeps must still send the right thing — a docstring is not a schedule
     (learning_third_party_rate_bans_and_schedule_drift).
"""
import inspect
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")

from workers import grade_reminder_worker as w  # noqa: E402


class TestRegistration:
    def test_it_is_in_the_bake_manifest(self):
        from workers.bake_orchestrator import _WORKER_MANIFEST

        entry = [e for e in _WORKER_MANIFEST if e[0] == "grade_reminder_worker"]
        assert entry, "the worker exists but nothing runs it"
        name, module, fn, needs_db = entry[0]
        assert module == "workers.grade_reminder_worker"
        assert fn == "run_once"
        assert needs_db is True, "it reads p2p_offers — without a DSN it must skip"

    def test_it_has_a_schedule(self):
        from app.worker_registry import SCHEDULES

        assert SCHEDULES.get("grade_reminder_worker", 0) > 0, \
            "a manifest entry with no interval never fires"

    def test_its_output_is_declared_with_an_input_gate(self):
        """The honest steady state of this worker is 'nothing to send'.

        Without `input_exists_sql` the silent-writer probe would page every
        time it correctly did nothing — and a gate that cries wolf stops being
        read, which costs more than the bug.
        """
        from app.lib.worker_output_registry import WORKER_OUTPUTS

        out = WORKER_OUTPUTS["grade_reminder_worker"]
        assert out.table == "notification_history"
        assert out.where_clause and "p2p_grade_reminder" in out.where_clause, \
            "unscoped, this checks EVERY notification and can never go stale"
        assert out.input_exists_sql and "member_grades" in out.input_exists_sql


class TestSendsAtMostOncePerPartyPerTrade:
    def test_it_skips_a_party_who_already_rated(self):
        sql = w._PENDING_SQL
        assert "FROM public.member_grades g" in sql
        assert "g.rater_id = party.party_id" in sql, \
            "the guard must be per RATER — a trade where one side rated still owes the other"

    def test_it_never_sends_a_second_reminder(self):
        sql = w._PENDING_SQL
        assert "'p2p_grade_reminder'" in sql and "notification_history" in sql, \
            "nothing stops this worker nudging the same person every hour"
        assert "nh.data->>'offer_id'" in sql, \
            "scoped by kind only, one reminder would suppress every later trade's"

    def test_the_kind_it_writes_is_the_kind_it_reads_back(self):
        """The reminder's own notification IS its idempotency record. If the
        two strings drift, every run re-sends and nothing errors."""
        src = inspect.getsource(w)
        assert src.count('"p2p_grade_reminder"') + src.count("'p2p_grade_reminder'") >= 2
        assert '{"kind": "p2p_grade_reminder", "offer_id": offer_id}' in src


class TestWindowLivesInTheQuery:
    def test_both_bounds_are_sql(self):
        sql = w._PENDING_SQL
        assert "make_interval(hours => $1)" in sql, "the 24h wait is not enforced in SQL"
        assert "make_interval(days => $2)" in sql, \
            "no upper bound: first run against an existing DB would nudge every trade ever"

    def test_completion_time_is_derived_from_the_confirmations(self):
        """`updated_at` moves on any later touch of the row, which would reset
        the clock or push a trade out of the window silently."""
        assert "GREATEST(o.seller_confirmed_at, o.buyer_confirmed_at)" in w._PENDING_SQL
        assert "updated_at" not in w._PENDING_SQL

    def test_defaults_match_the_documented_behaviour(self):
        assert w.REMIND_AFTER_HOURS == 24
        assert w.REMIND_UNTIL_DAYS == 7


class TestDeliveryPosture:
    def test_the_reminder_respects_the_daily_cap(self):
        """Transactional pushes pass urgent=True to skip the per-plan cap. A
        reminder is exactly what that cap exists to hold back."""
        src = inspect.getsource(w.run_once)
        assert "urgent=False" in src, "the reminder bypasses the frequency cap"

    def test_it_deep_links_to_the_offer(self):
        src = inspect.getsource(w.run_once)
        assert 'deep_link=f"/offers?offerId={offer_id}"' in src

    def test_the_pool_registers_the_jsonb_codec(self):
        """Without `init=_init_conn` the notification INSERT dies with
        "expected str, got dict" while the cycle still reports success — and
        here it would also break idempotency, since the row it fails to write
        is the record this worker reads back (2026-08-12, deal_discovery)."""
        src = inspect.getsource(w.run_once)
        assert "init=_init_conn" in src
