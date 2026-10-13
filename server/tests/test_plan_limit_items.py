"""Free-plan item cap (2026-10-13).

The cap itself is the DB trigger trg_items_free_cap
(supabase/migrations/20261013_free_item_cap.sql) -- proven on prod inside a
rolled-back transaction: the 101st active item of a free member raises
P0001 'PLAN_LIMIT_ITEMS: ...', archived rows, the trade-settlement exemption and
Pro members pass. These tests pin the server half: that error must reach the
app as the coded 403 it turns into a Pro offer, never as a 500.
"""

from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DB_ENABLED", "false")


def test_marker_detection():
    from app.subscription import is_plan_limit_items

    assert is_plan_limit_items(Exception("PLAN_LIMIT_ITEMS: the free plan holds 100 items"))
    assert not is_plan_limit_items(Exception("duplicate key value violates unique constraint"))
    assert not is_plan_limit_items(Exception("PLAN_LIMIT_WATCHLIST"))


def test_response_is_the_coded_403():
    from app.subscription import FREE_ITEM_CAP, plan_limit_items_response

    exc = plan_limit_items_response()
    assert exc.status_code == 403
    assert exc.detail["code"] == "PLAN_LIMIT_ITEMS"
    assert str(FREE_ITEM_CAP) in exc.detail["message"]


def test_global_handler_answers_403_not_500():
    """/intake/save and the marketplace-only listing do not catch DB errors, so
    the trigger's error reaches the global handler -- which used to 500."""
    from main import _global_exception_handler

    resp = asyncio.run(_global_exception_handler(
        None, Exception("PLAN_LIMIT_ITEMS: the free plan holds 100 items"),
    ))
    assert resp.status_code == 403
    assert json.loads(resp.body)["detail"]["code"] == "PLAN_LIMIT_ITEMS"


def test_cap_numbers_agree():
    """Trigger literal, server constant and PLAN_LIMITS must say the same number."""
    import pathlib
    import re

    from app.routes.billing_router import PLAN_LIMITS
    from app.subscription import FREE_ITEM_CAP

    sql = (pathlib.Path(__file__).resolve().parents[2]
           / "supabase/migrations/20261013_free_item_cap.sql").read_text()
    m = re.search(r"IF v_count >= (\d+) THEN", sql)
    assert m and int(m.group(1)) == FREE_ITEM_CAP == PLAN_LIMITS["free"]["max_items"]
    assert PLAN_LIMITS["pro"]["max_items"] is None
