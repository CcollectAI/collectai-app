"""The shared ingest HTTP client must survive a sibling pipeline's shutdown.

Regression test for the 2026-09-03/04/05 nightlies: 13 failed batches,
**2,254 rows lost**, exit 1, three nights running, with

    Upsert catalog batch 3/5 (200 rows LOST) failed:
    Cannot send a request, as the client has been closed.

The 2026-08-29 fix made `SupabaseIngest.client` a property that re-resolves
per call. That narrows the window but cannot close it: a property cannot fix
a time-of-check/time-of-use race.

    thread A: self.client           -> returns a LIVE client
    thread B: close_http_client()   -> closes that very object
    thread A: client.post(...)      -> RuntimeError, 200 rows lost

Both halves of the fix are asserted here: ownership (a sibling's close is a
no-op while the orchestrator holds the client) and recovery (a closed client
is retryable, because get_http_client() rebuilds).
"""

from __future__ import annotations

import httpx
import pytest

from pipelines import import_common as ic


@pytest.fixture(autouse=True)
def _reset_client_state():
    """Never leak held-state or a live client between tests."""
    ic._http_client_held = False
    ic.close_http_client()
    yield
    ic._http_client_held = False
    ic.close_http_client()


def test_sibling_close_is_a_noop_while_held():
    """The exact 2,254-row bug: an early finisher closing a shared client."""
    ic.hold_http_client()
    client = ic.get_http_client()

    ic.close_http_client()          # a sibling pipeline finishing

    assert not client.is_closed, (
        "a sibling's close_http_client() closed the client its siblings are "
        "still writing through — this is the 2,254-row nightly failure"
    )
    assert ic.get_http_client() is client, "the held client was swapped out"


def test_release_actually_closes():
    """Ownership must not turn close into a permanent leak."""
    ic.hold_http_client()
    client = ic.get_http_client()
    ic.release_http_client()

    assert client.is_closed, "release_http_client() did not close the client"
    assert not ic._http_client_held


def test_release_is_safe_without_a_hold():
    """The --category path never calls hold; release must still work."""
    client = ic.get_http_client()
    ic.release_http_client()
    assert client.is_closed


def test_closed_client_is_retried_with_a_fresh_one(monkeypatch):
    """A closed client mid-flight must cost a retry, not 200 rows."""
    monkeypatch.setattr(ic, "_POST_BASE_DELAY_S", 0.0)
    calls: list[str] = []

    class _DeadClient:
        is_closed = False

        def post(self, *a, **k):
            calls.append("dead")
            raise RuntimeError("Cannot send a request, as the client has been closed.")

    class _LiveClient:
        is_closed = False

        def post(self, *a, **k):
            calls.append("live")
            return "OK"

    monkeypatch.setattr(ic, "get_http_client", lambda: _LiveClient())

    result = ic._post_with_retry(_DeadClient(), "http://x", headers={}, json=[])

    assert result == "OK"
    assert calls == ["dead", "live"], (
        "the closed-client RuntimeError was not retried against a fresh client"
    )


def test_other_runtime_errors_are_not_swallowed(monkeypatch):
    """Only the closed-client message is retryable. A real bug must surface."""
    monkeypatch.setattr(ic, "_POST_BASE_DELAY_S", 0.0)

    class _BuggyClient:
        is_closed = False

        def post(self, *a, **k):
            raise RuntimeError("something else entirely")

    with pytest.raises(RuntimeError, match="something else entirely"):
        ic._post_with_retry(_BuggyClient(), "http://x", headers={}, json=[])


def test_transport_errors_still_retry(monkeypatch):
    """The 08-30 stale-keep-alive behaviour must not regress."""
    monkeypatch.setattr(ic, "_POST_BASE_DELAY_S", 0.0)
    calls: list[int] = []

    class _FlakyClient:
        is_closed = False

        def post(self, *a, **k):
            calls.append(1)
            if len(calls) < 2:
                raise httpx.ConnectError("Server disconnected")
            return "OK"

    assert ic._post_with_retry(_FlakyClient(), "http://x", headers={}, json=[]) == "OK"
    assert len(calls) == 2
