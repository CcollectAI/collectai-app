"""The webhook's failure logs must name the cause.

2026-08-30 cost two wrong hypotheses because the handler logged:

    revenuecat: ledger insert failed for 38A420F6-…

and nothing else on that line. The traceback WAS in bake.log, but on lines that
do not contain "revenuecat", so every grep scoped to the integration missed it
— and the actual cause (an FK violation naming the offending key) sat unread
while NOT NULL columns and revenue parsing were investigated instead.

`docs/WATCHDOG.md` already sets this rule for workers: **a failing writer must
say WHY.** These pin it for the billing webhook.

The asyncpg `detail` matters specifically: for the FK failure it carried
"Key (user_id)=(2b7db244-…) is not present in table users", which is the
sentence that identified the bug.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routes.billing_router import _rc_exc_detail


class _FakePgError(Exception):
    """Shaped like an asyncpg PostgresError: carries detail + constraint_name."""
    def __init__(self, msg, detail=None, constraint_name=None):
        super().__init__(msg)
        self.detail = detail
        self.constraint_name = constraint_name


def test_names_the_exception_type():
    assert "ValueError" in _rc_exc_detail(ValueError("boom"))


def test_includes_the_message():
    assert "boom" in _rc_exc_detail(ValueError("boom"))


def test_includes_asyncpg_detail_the_line_that_solved_it():
    exc = _FakePgError(
        'insert or update on table "subscription_events" violates foreign key constraint',
        detail="Key (user_id)=(2b7db244-13cb-478d-b612-ddf4acb60841) is not present in table \"users\".",
        constraint_name="subscription_events_user_id_fkey",
    )
    out = _rc_exc_detail(exc)
    assert "2b7db244" in out, "the offending key must survive into the log line"
    assert "subscription_events_user_id_fkey" in out, "name the constraint"


def test_survives_an_exception_with_no_detail_attrs():
    """Never let the logger itself throw while reporting a failure."""
    assert _rc_exc_detail(RuntimeError("plain")) .startswith("RuntimeError")


def test_is_one_line_so_a_grep_finds_it_whole():
    exc = _FakePgError("multi\nline\nmessage", detail="also\nmulti\nline")
    assert "\n" not in _rc_exc_detail(exc)
