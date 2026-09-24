"""DELETE /events/{id} must notify attendees — once, and never the host.

2026-09-24, walked on Android: the host's confirm dialog says "all attendees
will be notified", the server only flipped status to 'cancelled', and a
cancelled event drops out of every list. The attendee who was going got 0
notifications and simply lost the event. This drives the SQL path with a
recording connection and a recording notify_user.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.features.events import events_core  # noqa: E402

EVENT = "00000000-0000-0000-0000-0000000000e1"
HOST = "00000000-0000-0000-0000-0000000000a1"
GUEST = "00000000-0000-0000-0000-0000000000b2"


class _Conn:
    def __init__(self, already_cancelled=False):
        self.already_cancelled = already_cancelled

    async def fetchrow(self, q, *a):
        if q.lstrip().upper().startswith("UPDATE"):
            return None if self.already_cancelled else {"title": "Card night"}
        return None

    async def fetchval(self, q, *a):
        return 1  # the host owns it

    async def fetch(self, q, *a):
        # the attendee query excludes the host itself ($2); return only guests
        assert a[1] == HOST
        return [{"user_id": GUEST}]


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


def _wire(monkeypatch, conn):
    sent, spawned = [], []

    async def fake_notify(_conn, user_id, title, body, **kw):
        sent.append((user_id, title, kw.get("deep_link")))
        return 1

    def fake_spawn(coro, label):
        spawned.append(coro)

    monkeypatch.setattr(events_core, "get_db_pool", lambda: _Pool(conn))
    monkeypatch.setattr(events_core, "notify_user", fake_notify)
    monkeypatch.setattr(events_core, "spawn_bg", fake_spawn)
    return sent, spawned


@pytest.mark.asyncio
async def test_cancel_notifies_each_attendee(monkeypatch):
    sent, spawned = _wire(monkeypatch, _Conn())
    res = await events_core.delete_event(EVENT, user_id=HOST)
    assert res["success"] is True
    assert len(spawned) == 1, "cancel did not schedule the attendee notification"
    await spawned[0]
    assert sent == [(GUEST, "Event cancelled", f"/events/{EVENT}")]


@pytest.mark.asyncio
async def test_repeat_cancel_does_not_notify_again(monkeypatch):
    sent, spawned = _wire(monkeypatch, _Conn(already_cancelled=True))
    res = await events_core.delete_event(EVENT, user_id=HOST)
    assert res["success"] is True
    assert spawned == []
