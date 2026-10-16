"""Settings → Notifications → "Messages" OFF must stop chat pushes (2026-10-16).

Chat pushes call send_push_to_user directly, which never read preferences.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

import app.push as push  # noqa: E402
import app.lib.notify as notify  # noqa: E402


class Conn:
    async def fetch(self, sql, *a):
        return [{"push_token": "ExponentPushToken[x]"}]


def run(prefs, data, monkeypatch):
    sent, persisted = [], []

    async def _prefs(conn, uid):
        return prefs

    async def _persist(*a, **k):
        persisted.append(1)
        return "nid"

    async def _send(token, title, body, data=None):
        sent.append(data)
        return True

    monkeypatch.setattr(notify, "_get_user_prefs", _prefs)
    monkeypatch.setattr(push, "_persist_notification", _persist)
    monkeypatch.setattr(push, "send_push", _send)
    n = asyncio.run(push.send_push_to_user(Conn(), "user-1234", "Message from A", "hi", data=data))
    return n, sent, persisted


def test_messages_off_sends_no_chat_push_but_keeps_history(monkeypatch):
    n, sent, persisted = run({"chat_messages": False}, {"type": "chat_message", "thread_id": "t"}, monkeypatch)
    assert n == 0 and sent == []
    assert persisted == [1]


def test_messages_on_or_unset_still_pushes(monkeypatch):
    assert run({}, {"type": "chat_message"}, monkeypatch)[0] == 1
    assert run({"chat_messages": True}, {"type": "chat_message"}, monkeypatch)[0] == 1


def test_a_type_with_no_toggle_is_unaffected(monkeypatch):
    assert run({"chat_messages": False}, {"type": "catalog_mapped"}, monkeypatch)[0] == 1
