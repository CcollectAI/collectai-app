"""The Telegram bot token must never reach a log line.

WHY (2026-09-12): Telegram carries the credential in the URL path and httpx
logs the full request line at INFO, so every ops alert wrote

    HTTP Request: POST https://api.telegram.org/bot<TOKEN>/sendMessage "200 OK"

into `bake.log` — **81 lines in the live log**, mode 0664, plus four rotated
copies. Found while investigating why the watchdog was paging hourly.

The test asserts the redactor against a record shaped exactly like httpx's, and
— the part that matters — it asserts the UNREDACTED form really does leak, so a
fixture that stops reproducing the bug fails the suite rather than passing
vacuously (the discipline `docs/WATCHDOG.md` records for the digest-trim test).
"""
from __future__ import annotations

import logging

from app.lib.telegram_ops import _RedactBotToken, install_token_redaction

FAKE_TOKEN = "8622218314:AAFexampleexampleexampleexampleexample"
URL = f"https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage"


def _httpx_style_record() -> logging.LogRecord:
    """What httpx actually emits: the URL arrives through %-args, not the msg."""
    return logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='HTTP Request: %s %s "%s %d %s"',
        args=("POST", URL, "HTTP/1.1", 200, "OK"),
        exc_info=None,
    )


def test_the_unredacted_record_really_does_leak():
    """If this stops being true the fixture no longer reproduces the bug."""
    assert FAKE_TOKEN in _httpx_style_record().getMessage()


def test_token_is_redacted_but_the_line_survives():
    record = _httpx_style_record()
    assert _RedactBotToken().filter(record) is True
    out = record.getMessage()
    assert FAKE_TOKEN not in out
    assert "8622218314" not in out
    assert "api.telegram.org/bot<redacted>/sendMessage" in out
    # Still a useful log line — redaction, not silence.
    assert "HTTP Request" in out and "200" in out


def test_other_hosts_are_untouched():
    record = logging.LogRecord(
        name="httpx", level=logging.INFO, pathname=__file__, lineno=1,
        msg="HTTP Request: %s %s", args=("GET", "https://api.ebay.com/buy/x?q=1"),
        exc_info=None,
    )
    _RedactBotToken().filter(record)
    assert "https://api.ebay.com/buy/x?q=1" in record.getMessage()


def test_a_record_that_cannot_render_does_not_raise():
    """A logger must never be able to throw while reporting something."""
    record = logging.LogRecord(
        name="httpx", level=logging.INFO, pathname=__file__, lineno=1,
        msg="bad %d format", args=("not-an-int",), exc_info=None,
    )
    assert _RedactBotToken().filter(record) is True


def test_install_is_idempotent():
    httpx_logger = logging.getLogger("httpx")
    install_token_redaction()
    install_token_redaction()
    installed = [f for f in httpx_logger.filters if isinstance(f, _RedactBotToken)]
    assert len(installed) == 1
