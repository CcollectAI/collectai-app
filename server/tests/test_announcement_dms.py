"""Event announcement DMs went into a table nothing reads.

Found 2026-09-17 sweeping "success without a write". `_send_announcement_dms`
found-or-created a thread in `dm_threads` and then inserted the message into
`chat_messages_v1` — whose `thread_id` FK was repointed to `chat_threads_v1` on
2026-04-30. Verified on production the same day: `dm_threads` holds **0 rows**,
so every announcement made a fresh legacy row and every message insert then
violated the FK. The per-attendee `except` logged a warning, the summary line
said `sent=0` at INFO, and the host was told nothing. Five months.

These tests drive the function with a fake connection, so they assert the tables
it actually writes rather than the shape of the fix.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.features.events import events_announcements as ann  # noqa: E402

HOST = "00000000-0000-0000-0000-0000000000aa"
ATT_1 = "00000000-0000-0000-0000-000000000001"
ATT_2 = "00000000-0000-0000-0000-000000000002"
THREAD = "00000000-0000-0000-0000-0000000000ff"
EVENT = "00000000-0000-0000-0000-0000000000ee"


class _Row(dict):
    def __getitem__(self, k):
        return dict.__getitem__(self, k)


class _Conn:
    """Records every statement; answers the four reads this function makes."""

    def __init__(self, attendees, blocked=(), denied=()):
        self.attendees = attendees
        self.blocked = set(blocked)
        self.denied = set(denied)
        self.sql: list[str] = []

    def _log(self, q):
        self.sql.append(" ".join(q.split()))

    async def fetch(self, q, *args):
        self._log(q)
        return [_Row(user_id=a) for a in self.attendees]

    async def fetchval(self, q, *args):
        self._log(q)
        flat = " ".join(q.split())
        if "FROM user_blocks" in flat:
            return 1 if (args[1] in self.blocked or args[0] in self.blocked) else None
        if "chat_dm_requests_v1" in flat:
            return 1 if args[1] in self.denied else None
        if "INSERT INTO public.chat_threads_v1" in flat:
            return THREAD
        return None

    async def fetchrow(self, q, *args):
        self._log(q)
        if "rpc_send_message_v1" in " ".join(q.split()):
            return _Row(id="msg-1")
        return None

    async def execute(self, q, *args):
        self._log(q)
        return "INSERT 1"


class _Acquire:
    def __init__(self, conn):
        self._c = conn

    async def __aenter__(self):
        return self._c

    async def __aexit__(self, *e):
        return False


class _Pool:
    def __init__(self, conn):
        self._c = conn

    def acquire(self):
        return _Acquire(self._c)


async def _run(conn):
    await ann._send_announcement_dms(
        _Pool(conn), EVENT, HOST, "Card Fair Utrecht", "Doors open at 10", "Bring cash"
    )


def _joined(conn):
    return "\n".join(conn.sql)


class TestTheTablesItWrites:
    @pytest.mark.asyncio
    async def test_writes_the_live_thread_table_not_the_legacy_one(self):
        conn = _Conn([ATT_1])
        await _run(conn)
        sql = _joined(conn)
        assert "INSERT INTO public.chat_threads_v1" in sql
        # The bug itself: dm_threads is empty legacy and its ids fail the FK.
        assert "dm_threads" not in sql

    @pytest.mark.asyncio
    async def test_adds_both_members_and_sends_through_the_shared_rpc(self):
        conn = _Conn([ATT_1])
        await _run(conn)
        sql = _joined(conn)
        assert sql.count("INSERT INTO public.chat_thread_members_v1") == 2
        assert "rpc_send_message_v1" in sql
        # chat_router.send_message uses the same RPC — one writer for a DM.
        assert "INSERT INTO chat_messages_v1" not in sql

    @pytest.mark.asyncio
    async def test_bumps_the_thread_so_the_inbox_orders_it(self):
        conn = _Conn([ATT_1])
        await _run(conn)
        assert "UPDATE public.chat_threads_v1 SET updated_at = now()" in _joined(conn)

    @pytest.mark.asyncio
    async def test_only_attendees_that_still_have_an_account(self):
        conn = _Conn([ATT_1])
        await _run(conn)
        # event_attendees has no FK to auth.users; chat_threads_v1 does.
        assert "EXISTS (SELECT 1 FROM auth.users" in _joined(conn)


class TestWhoIsSkipped:
    @pytest.mark.asyncio
    async def test_a_blocked_member_gets_nothing(self):
        conn = _Conn([ATT_1], blocked=[ATT_1])
        await _run(conn)
        sql = _joined(conn)
        assert "INSERT INTO public.chat_threads_v1" not in sql
        assert "rpc_send_message_v1" not in sql

    @pytest.mark.asyncio
    async def test_a_denied_dm_request_is_respected(self):
        conn = _Conn([ATT_1], denied=[ATT_1])
        await _run(conn)
        assert "rpc_send_message_v1" not in _joined(conn)

    @pytest.mark.asyncio
    async def test_one_skip_does_not_stop_the_others(self):
        conn = _Conn([ATT_1, ATT_2], blocked=[ATT_1])
        await _run(conn)
        assert _joined(conn).count("rpc_send_message_v1") == 1


class TestItSaysWhenNothingWasSent:
    @pytest.mark.asyncio
    async def test_a_total_failure_logs_at_error(self, monkeypatch, caplog):
        class _Boom(_Conn):
            async def fetchval(self, q, *args):
                self._log(q)
                flat = " ".join(q.split())
                if "FROM user_blocks" in flat or "chat_dm_requests_v1" in flat:
                    return None
                raise RuntimeError("foreign key violation")

        conn = _Boom([ATT_1, ATT_2])
        with caplog.at_level("INFO"):
            await _run(conn)
        errors = [r for r in caplog.records if r.levelname == "ERROR" and "sent=0" in r.getMessage()]
        assert errors, [r.getMessage() for r in caplog.records]
