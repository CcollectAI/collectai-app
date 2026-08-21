"""The watchdog digest must survive being too long.

On 2026-08-19 the daily digest was rejected by Telegram with

    400 ... can't parse entities: Can't find end tag corresponding to
    start tag "code"

and the ENTIRE report was lost. The cause was `body[:3800]` — a raw character
cut applied to MARKUP. When the cut landed between `<code>` and `</code>`,
Telegram refused the message, the send sat inside a `try/except` that only
printed to stderr, and nothing else carried the report.

The failure is worst precisely when it matters most: the longer the report,
the more findings it has, and the more likely the cut lands inside a tag.

These tests pin the fix and, more importantly, FAIL against the old
implementation — a test that passes either way would prove nothing.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.watchdog import _trim_html  # noqa: E402


def _unclosed(html: str, tag: str) -> int:
    return html.count("<%s" % tag) - html.count("</%s>" % tag)


def _digest_that_cuts_inside_a_code_tag(limit: int) -> str:
    """Build a body whose naive `[:limit]` lands between <code> and </code>."""
    head = "<b>Sparrow Ops</b>\n"
    payload = "SELECT 1 FROM a_very_long_table_name; " * 20
    # Grow the filler until the <code> element STRADDLES `limit`: it must open
    # before the cut and close after it. Computed, not eyeballed, so the
    # fixture cannot quietly stop reproducing the bug.
    lines, filler = [], ""
    i = 0
    while len(head) + len(filler) + len("\n<code>") + len(payload) < limit + 200:
        i += 1
        lines.append("<b>%d. [high] finding %d</b>\nsome detail text here" % (i, i))
        filler = "\n".join(lines)
    body = head + filler + "\n<code>" + payload + "</code>"
    assert len(body) > limit
    assert len(head) + len(filler) + len("\n<code>") < limit < len(body) - len("</code>")
    # precondition: the naive cut really does split the <code> element
    assert _unclosed(body[:limit], "code") == 1, "fixture no longer reproduces the bug"
    return body


def test_naive_slice_reproduces_the_telegram_rejection():
    """The bug is real: the old `body[:3800]` leaves <code> unclosed."""
    body = _digest_that_cuts_inside_a_code_tag(3800)
    assert _unclosed(body[:3800], "code") == 1


def test_trim_html_never_leaves_a_tag_open():
    body = _digest_that_cuts_inside_a_code_tag(3800)
    out = _trim_html(body, 3800)
    for tag in ("code", "b", "a"):
        assert _unclosed(out, tag) == 0, "%s left unbalanced: %r" % (tag, out[-200:])


def test_trim_html_respects_the_limit():
    body = _digest_that_cuts_inside_a_code_tag(3800)
    assert len(_trim_html(body, 3800)) <= 3800


def test_trim_html_is_a_noop_below_the_limit():
    short = "<b>all good</b>\n<code>SELECT 1;</code>"
    assert _trim_html(short, 3800) == short


def test_trim_html_says_it_truncated():
    body = _digest_that_cuts_inside_a_code_tag(3800)
    assert "truncated" in _trim_html(body, 3800)


def test_no_dangling_open_bracket():
    """Whatever we emit must not end mid-tag."""
    body = _digest_that_cuts_inside_a_code_tag(3800)
    out = _trim_html(body, 3800)
    tail = out[out.rfind("<"):] if "<" in out else ""
    assert ">" in tail, "output ends inside an unterminated tag: %r" % tail[:80]
