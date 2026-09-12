"""Outbound request URLs must not carry credentials into the log.

WHY (2026-09-12): httpx logs every request it makes at INFO, URL included, so
any secret travelling in a query string — or in the PATH, as Telegram's bot
token does — was written to `bake.log` in full. Measured on the live log:

    app.ticketmaster.com   apikey       896 lines
    api.seatgeek.com       client_id    752 lines
    api.scrape.do          token        298 lines
    api.telegram.org       bot<token>    81 lines

mode 0664, plus four rotated copies. Found while investigating why the watchdog
was paging hourly — the alert lines themselves contained the bot token.

This is the outbound twin of the uvicorn access-log redaction in the same
module, and it reuses that fail-closed allowlist: a query value is redacted
unless its key is explicitly safe, so the next vendor's parameter is covered on
the day it is added rather than on the day someone notices.

Each test asserts the UNREDACTED form really does leak before asserting the
redaction, so a fixture that stops reproducing the bug fails the suite rather
than passing vacuously.
"""
from __future__ import annotations

import logging

import pytest

from app.logging_filters import (
    OutboundLogRedactionFilter,
    install_outbound_log_redaction,
    redact_url,
)
from app.lib.telegram_ops import install_token_redaction

SECRET = "s3cr3t-value-that-must-never-be-logged"

VENDORS = [
    pytest.param(f"https://api.telegram.org/bot8622218314:{SECRET}/sendMessage", id="telegram-path"),
    pytest.param(f"https://app.ticketmaster.com/discovery/v2/events.json?apikey={SECRET}&size=50", id="ticketmaster-apikey"),
    pytest.param(f"https://api.seatgeek.com/2/events?client_id={SECRET}&per_page=50", id="seatgeek-client_id"),
    pytest.param(f"https://api.scrape.do?token={SECRET}&url=https%3A%2F%2Fexample.com", id="scrapedo-token"),
]


def _httpx_record(url: str) -> logging.LogRecord:
    """Exactly httpx's shape: the URL arrives through %-args, not in msg."""
    return logging.LogRecord(
        name="httpx", level=logging.INFO, pathname=__file__, lineno=1,
        msg='HTTP Request: %s %s "%s %d %s"',
        args=("GET", url, "HTTP/1.1", 200, "OK"), exc_info=None,
    )


@pytest.mark.parametrize("url", VENDORS)
def test_the_unredacted_record_really_does_leak(url):
    assert SECRET in _httpx_record(url).getMessage()


@pytest.mark.parametrize("url", VENDORS)
def test_secret_is_redacted_and_the_line_survives(url):
    record = _httpx_record(url)
    assert OutboundLogRedactionFilter().filter(record) is True
    out = record.getMessage()
    assert SECRET not in out
    assert "HTTP Request" in out and "200" in out
    # The host stays readable — redaction, not silence.
    assert "https://" in out


def test_safe_pagination_keys_stay_in_the_clear():
    """The allowlist is shared with the access log, so debugging still works."""
    out = redact_url("https://api.example.com/v1/things?limit=50&offset=100&apikey=" + SECRET)
    assert "limit=50" in out and "offset=100" in out
    assert SECRET not in out


def test_a_url_we_cannot_parse_loses_its_query_rather_than_leaking():
    out = redact_url("https://api.example.com/x?%%%&apikey=" + SECRET)
    assert SECRET not in out


def test_a_record_that_cannot_render_does_not_raise():
    """A logger must never be able to throw while reporting something."""
    record = logging.LogRecord(
        name="httpx", level=logging.INFO, pathname=__file__, lineno=1,
        msg="bad %d format", args=("not-an-int",), exc_info=None,
    )
    assert OutboundLogRedactionFilter().filter(record) is True


def test_install_is_idempotent_across_both_entry_points():
    """main.py installs it; importing telegram_ops installs it again."""
    install_outbound_log_redaction()
    install_token_redaction()
    install_outbound_log_redaction()
    installed = [
        f for f in logging.getLogger("httpx").filters
        if isinstance(f, OutboundLogRedactionFilter)
    ]
    assert len(installed) == 1


class _UrlObject:
    """Stand-in for `httpx.URL`, which is what httpx really passes.

    THE BUG THIS PINS: the first version of the filter guarded on
    `isinstance(arg, str)`, so it skipped every real request while the
    string-based tests above passed. An end-to-end run against the live vendors
    is what caught it — the fixture had been simpler than reality.
    """

    def __init__(self, url: str) -> None:
        self._url = url

    def __str__(self) -> str:
        return self._url


@pytest.mark.parametrize("url", VENDORS)
def test_a_url_OBJECT_is_redacted_too(url):
    record = logging.LogRecord(
        name="httpx", level=logging.INFO, pathname=__file__, lineno=1,
        msg='HTTP Request: %s %s "%s %d %s"',
        args=("GET", _UrlObject(url), "HTTP/1.1", 200, "OK"), exc_info=None,
    )
    assert SECRET in str(_UrlObject(url))          # the fixture still reproduces it
    OutboundLogRedactionFilter().filter(record)
    assert SECRET not in record.getMessage()
