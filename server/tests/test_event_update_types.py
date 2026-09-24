"""PATCH /events/{id} must bind DATE/TIME columns as date/time objects.

2026-09-24, walked on Android: EVERY event edit 500'd with
"invalid input for query argument $6: '2026-09-30' ('str' object has no
attribute 'toordinal')". The request carries date/time as strings and asyncpg
will not coerce a str into a DATE; create_event converted them, update_event
did not. The router tests never saw it: they run on the in-memory fallback,
not the SQL path. This drives the SQL path with a recording connection.
"""
import os
import sys
from datetime import date, time as dt_time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.features.events import events_core  # noqa: E402
from app.features.events.events_helpers import UpdateEventRequest  # noqa: E402

EVENT = "00000000-0000-0000-0000-0000000000e1"
USER = "00000000-0000-0000-0000-0000000000a1"


class _Conn:
    def __init__(self):
        self.update_params = None

    def transaction(self):
        class _Tx:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *e):
                return False
        return _Tx()

    async def fetchrow(self, q, *a):
        if q.lstrip().upper().startswith("UPDATE"):
            self.update_params = a
            return None  # the handler then 404s — we only need the params
        return {"id": EVENT, "created_by": USER}


class _Pool:
    def __init__(self, c):
        self.c = c

    def acquire(self):
        c = self.c

        class _A:
            async def __aenter__(self):
                return c

            async def __aexit__(self, *e):
                return False
        return _A()


@pytest.mark.asyncio
async def test_date_and_time_are_bound_as_date_and_time(monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(events_core, "get_db_pool", lambda: _Pool(conn))
    req = UpdateEventRequest(title="Renamed", date="2026-09-30", time="19:30", end_date="2026-10-01")
    with pytest.raises(Exception):
        # fetchrow returns None for the UPDATE, so the handler raises 404 —
        # after binding, which is what this test inspects.
        await events_core.update_event(EVENT, req, user_id=USER)
    assert conn.update_params is not None, "the UPDATE never ran"
    bound = list(conn.update_params)
    assert date(2026, 9, 30) in bound
    assert date(2026, 10, 1) in bound
    assert dt_time(19, 30) in bound
    assert "2026-09-30" not in bound and "19:30" not in bound


class _SqlConn(_Conn):
    """Also records the UPDATE's SQL, to see which columns were set."""

    async def fetchrow(self, q, *a):
        if q.lstrip().upper().startswith("UPDATE"):
            self.update_sql = q
        return await super().fetchrow(q, *a)


@pytest.mark.asyncio
async def test_edit_saves_kind_category_coords_and_clears_with_null(monkeypatch):
    """The edit form offers kind, category and "use my location"; none of them
    reached the UPDATE, and a cleared end date (sent as null) was discarded by
    exclude_none. A null must clear an optional column and must NOT blank a
    required one such as the title."""
    conn = _SqlConn()
    monkeypatch.setattr(events_core, "get_db_pool", lambda: _Pool(conn))
    req = UpdateEventRequest(
        kind="convention", category_id="pokemon", latitude=52.37, longitude=4.89,
        end_date=None, title=None,
    )
    with pytest.raises(Exception):
        await events_core.update_event(EVENT, req, user_id=USER)
    sql = conn.update_sql
    for col in ("kind", "category_id", "latitude", "longitude", "end_date"):
        assert f"{col} = $" in sql, f"{col} not written"
    assert "title = $" not in sql, "a null title must be ignored, not written"
    assert None in list(conn.update_params), "the cleared end_date was not bound as NULL"
