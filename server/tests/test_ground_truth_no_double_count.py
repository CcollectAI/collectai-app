"""One real sale must reach the training file ONCE, with its real condition.

Recording a verified sale writes TWO tables: `verified_sales` (with the
member's condition) and `price_ground_truths` (source='user_verified_sale',
no condition column, so the exporter hardcodes 'Good'). Between 2026-04-25 and
2026-09-20 `_export_ground_truths` selected from both without filtering, and
then wrote every row twice for weight — so one user-typed price landed in the
training file FOUR times, carrying two contradictory condition labels.

That matters twice over:
  * the least independent price signal (a member who saw our estimate before
    listing) outweighed scraped sold comps 2:1;
  * `_retrain_category` holds out the leading slice of this same file to score
    the new model. With the sale present under both sources, the holdout copy
    and a training copy were the same sale, so the promotion gate scored the
    model on data it had trained on.

These tests drive the real exporter against a fake connection that behaves
like the two tables, so they fail against the unfiltered query.
"""
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


class _Row(dict):
    """Stands in for an asyncpg Record (indexable + .get + .keys)."""


class FakeConn:
    """Answers the exporter's two queries the way Postgres would.

    Both tables hold the SAME £100 Mint sale, because recording it wrote both.
    `_apply_source_filter` is what the real WHERE clause does, so the filtered
    query returns one row and the unfiltered query returns two.
    """

    def __init__(self):
        self.verified_sales = [
            _Row(price=100.0, condition="Mint", ts=NOW),
        ]
        self.ground_truths = [
            # the duplicate of the verified sale above
            _Row(price=100.0, condition="Good", ts=NOW, source="user_verified_sale"),
            # A genuinely separate signal — must survive. Deliberately NEWER
            # than the verified sale so the ordering test can tell a real
            # newest-first merge from a plain `rows + gt_rows` concatenation,
            # which would put the older verified sale first.
            _Row(price=250.0, condition="Good", ts=NOW + timedelta(days=1),
                 source="sparrow_p2p"),
        ]

    async def fetch(self, sql, *args):
        if "verified_sales" in sql:
            return list(self.verified_sales)
        rows = self.ground_truths
        if "source <> 'user_verified_sale'" in sql:
            rows = [r for r in rows if r["source"] != "user_verified_sale"]
        return [_Row({k: v for k, v in r.items() if k != "source"}) for r in rows]


def _run_export(tmp_path, monkeypatch):
    from server.workers import model_retrain_worker as w
    monkeypatch.setattr(w, "DATA_DIR", tmp_path)
    conn = FakeConn()
    count = asyncio.run(w._export_ground_truths(conn, "pokemon", NOW - timedelta(days=30)))
    lines = [json.loads(l) for l in
             (tmp_path / "pokemon" / "train_ground_truth.jsonl").read_text().splitlines() if l.strip()]
    return count, lines


def test_one_sale_is_not_counted_twice(tmp_path, monkeypatch):
    _, lines = _run_export(tmp_path, monkeypatch)
    hundreds = [l for l in lines if l["price"] == 100.0]
    # 2 = the deliberate 2x weight. 4 = the sale counted under both sources.
    assert len(hundreds) == 2, (
        f"expected the £100 sale twice (2x weight), got {len(hundreds)} — "
        "it is being counted under verified_sales AND price_ground_truths"
    )


def test_the_members_real_condition_survives(tmp_path, monkeypatch):
    _, lines = _run_export(tmp_path, monkeypatch)
    scores = {l["features"]["condition_score"] for l in lines if l["price"] == 100.0}
    # Mint -> 0.95. The price_ground_truths copy hardcodes 'Good' -> 0.70.
    assert scores == {0.95}, (
        f"the same sale carries contradictory condition labels: {sorted(scores)}"
    )


def test_independent_ground_truths_are_kept(tmp_path, monkeypatch):
    _, lines = _run_export(tmp_path, monkeypatch)
    assert [l for l in lines if l["price"] == 250.0], \
        "sparrow_p2p/deal_desk rows are NOT duplicates and must stay in training"


def test_rows_are_merged_newest_first_across_both_sources(tmp_path, monkeypatch):
    """_retrain_category holds out the LEADING slice and calls it the newest."""
    _, lines = _run_export(tmp_path, monkeypatch)
    assert lines[0]["price"] == 250.0, (
        "the newest record across BOTH sources must lead the file; a plain "
        "rows+gt_rows concatenation leads with the newest verified sale even "
        "when a ground truth is more recent"
    )


def test_holdout_never_splits_a_weighted_pair():
    """The 2x weight is two ADJACENT lines; cutting between them leaks.

    One copy would land in the holdout and its identical twin stay in
    training, so `_retrain_category` would score the new model on a row it had
    just trained on. At HOLDOUT_FRACTION=0.20 an odd cut happens for ~40% of
    realistic file sizes.
    """
    from server.workers.model_retrain_worker import _holdout_size
    bad = [n for n in range(20, 401, 2) if _holdout_size(n) % 2]
    assert not bad, f"holdout splits a weighted pair for n_total={bad[:10]}"
