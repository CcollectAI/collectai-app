"""fetch_json is the READ side and its retry rule is the opposite of the write side.

Third-party GETs are idempotent and a 5xx from someone else's server is
weather, so it is retried. A 4xx is that server's verdict on our request and
fails identically on replay, so it is not. And no upstream is retried without
a budget: tcgcsv.com banned this application for overuse on 2026-07-31.
"""

from __future__ import annotations

import httpx
import pytest

from pipelines import import_common as ic


class _Resp:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload if payload is not None else {"data": []}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("GET", "http://up.test/x"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _fast_and_clean(monkeypatch):
    monkeypatch.setattr(ic.time, "sleep", lambda *_: None)
    ic.reset_host_circuit()
    yield
    ic.reset_host_circuit()


def _client(responses):
    seq = list(responses)

    class _C:
        calls = 0

        def get(self, url, params=None, headers=None):
            _C.calls += 1
            return seq.pop(0)

    c = _C()
    return c


def test_5xx_is_retried_then_succeeds(monkeypatch):
    c = _client([_Resp(500), _Resp(502), _Resp(200, {"data": [1]})])
    monkeypatch.setattr(ic, "get_http_client", lambda: c)
    assert ic.fetch_json("http://up.test/x") == {"data": [1]}
    assert type(c).calls == 3


def test_4xx_is_NOT_retried(monkeypatch):
    """A 404 burned three attempts and three seconds to reach the same answer."""
    c = _client([_Resp(404), _Resp(200, {"data": [1]})])
    monkeypatch.setattr(ic, "get_http_client", lambda: c)
    with pytest.raises(httpx.HTTPStatusError):
        ic.fetch_json("http://up.test/x")
    assert type(c).calls == 1, "a 4xx was retried; it fails identically on replay"


def test_all_429s_raise_instead_of_returning_None(monkeypatch):
    """The rate-limit branch `continue`d, so the loop fell out returning None.

    Every caller does data.get("data", []) on the result, so this surfaced as
    an AttributeError far from its cause.
    """
    c = _client([_Resp(429), _Resp(429), _Resp(429)])
    monkeypatch.setattr(ic, "get_http_client", lambda: c)
    with pytest.raises(Exception) as ei:
        ic.fetch_json("http://up.test/x")
    assert ei.value is not None
    assert not isinstance(ei.value, AttributeError)


def test_transport_error_is_retried(monkeypatch):
    """"The read operation timed out" was escaping unretried (only ConnectError was caught)."""
    calls = {"n": 0}

    class _C:
        def get(self, url, params=None, headers=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ReadTimeout("The read operation timed out")
            return _Resp(200, {"data": [1]})

    monkeypatch.setattr(ic, "get_http_client", lambda: _C())
    assert ic.fetch_json("http://up.test/x") == {"data": [1]}
    assert calls["n"] == 2


def test_circuit_opens_after_repeated_5xx_and_stops_calling(monkeypatch):
    """The outbound budget: stop hammering a struggling free API."""
    monkeypatch.setattr(ic, "_HOST_FAIL_LIMIT", 4)
    calls = {"n": 0}

    class _C:
        def get(self, url, params=None, headers=None):
            calls["n"] += 1
            return _Resp(500)

    monkeypatch.setattr(ic, "get_http_client", lambda: _C())

    with pytest.raises(httpx.HTTPStatusError):
        ic.fetch_json("http://up.test/x")          # 3 attempts, 3 failures
    before = calls["n"]

    # Next call trips the limit and then fails fast with NO further network use.
    with pytest.raises(Exception):
        ic.fetch_json("http://up.test/y")
    with pytest.raises(RuntimeError, match="circuit open"):
        ic.fetch_json("http://up.test/z")

    assert calls["n"] < before + 10, "the circuit did not stop outbound calls"


def test_success_resets_the_circuit(monkeypatch):
    """A blip must not count towards a ban budget forever."""
    monkeypatch.setattr(ic, "_HOST_FAIL_LIMIT", 3)
    c = _client([_Resp(500), _Resp(200, {"data": [1]})])
    monkeypatch.setattr(ic, "get_http_client", lambda: c)
    assert ic.fetch_json("http://up.test/x") == {"data": [1]}
    assert ic._host_failures.get("up.test", 0) == 0
