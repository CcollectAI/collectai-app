"""The gate in front of the newsletter LLM extractor.

WHY THESE TESTS MATTER MORE THAN THE MODEL

The regex extractor failed loudly: it emitted "ic/media/pcenLogo" as a venue and
"Site Navsito" as a title, and `event_quality.py`'s penalties were tuned to
exactly that — `markup_in_title`, `location_not_place_shaped`. An LLM fails
QUIETLY: it returns a clean, plausible, well-formed event that was never in the
email. Every one of those penalties scores that as fine.

So swapping the extractor without a gate trades visible junk for invisible junk.
`verify()` is the gate, and it is pure and deterministic precisely so that it
can be pinned here — a prompt or model change must not be able to loosen it.

The junk titles below are not invented. They are rows that reached prod:
"Site Navsito", "Stay Connected", "Frequently asked questions",
"Performance Cookies", "12. Cruz roja argentina", "**LATEST NEWS**".
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.newsletter_llm_extract import (  # noqa: E402
    Candidate,
    MIN_CONFIDENCE,
    verify,
)

NOW = datetime(2026, 8, 22, tzinfo=timezone.utc)
SOON = (NOW + timedelta(days=30)).date().isoformat()

EMAIL = """
Spielwarenmesse 2027 takes place in Nuremberg from 2 to 6 February 2027.
Trade visitors can register from October. Stay Connected. Frequently asked
questions. Performance Cookies. Site Navigation.
"""


def _c(**kw) -> Candidate:
    base = dict(
        kind="event",
        title="Spielwarenmesse 2027",
        starts_at=SOON,
        confidence=0.95,
        evidence="Spielwarenmesse 2027 takes place in Nuremberg",
    )
    base.update(kw)
    return Candidate(**base)


class TestGrounding:
    """The load-bearing gate: the model must POINT AT text, not produce it."""

    def test_a_grounded_candidate_is_accepted(self):
        v = verify(_c(), EMAIL, now=NOW)
        assert v.accepted, v.reasons

    def test_fabricated_evidence_is_rejected(self):
        """The whole point. A clean, confident, well-formed event that the email
        never mentioned — the exact failure the regex could not produce and the
        quality score cannot catch."""
        v = verify(
            _c(
                title="Pokemon World Championships 2027",
                evidence="The Pokemon World Championships will be held in Osaka next August",
            ),
            EMAIL,
            now=NOW,
        )
        assert not v.accepted
        assert "evidence_not_in_source" in v.reasons

    def test_paraphrased_evidence_is_rejected(self):
        """Close is not verbatim. A model that rewords is a model that is
        deciding content, which is the thing we refuse to trust it for."""
        v = verify(_c(evidence="Spielwarenmesse 2027 will be held in Nuremberg"), EMAIL, now=NOW)
        assert not v.accepted
        assert "evidence_not_in_source" in v.reasons

    def test_line_wrapping_does_not_break_grounding(self):
        """HTML-to-text wraps lines, so grounding compares on collapsed
        whitespace. Strict about CONTENT, not about layout."""
        v = verify(_c(evidence="Spielwarenmesse   2027\n  takes place in Nuremberg"), EMAIL, now=NOW)
        assert v.accepted, v.reasons

    def test_trivially_short_evidence_is_rejected(self):
        """'2027' appears in every newsletter ever written."""
        v = verify(_c(evidence="2027"), EMAIL, now=NOW)
        assert not v.accepted
        assert "evidence_too_short" in v.reasons

    def test_missing_evidence_is_rejected(self):
        v = verify(_c(evidence=""), EMAIL, now=NOW)
        assert not v.accepted
        assert "no_evidence" in v.reasons

    def test_title_must_also_appear_in_the_email(self):
        """A model that SUMMARISES writes a headline nobody sent — even when it
        quotes a real span as evidence."""
        v = verify(_c(title="Nuremberg Toy Fair"), EMAIL, now=NOW)
        assert not v.accepted
        assert "title_not_in_source" in v.reasons


class TestChrome:
    """Every title here is a row that actually shipped to production."""

    def test_measured_chrome_titles_are_rejected(self):
        for junk in ("Stay Connected", "Frequently asked questions",
                     "Performance Cookies", "Site Navigation"):
            v = verify(
                _c(title=junk, evidence="Stay Connected. Frequently asked\nquestions. Performance Cookies."),
                EMAIL, now=NOW,
            )
            assert not v.accepted, junk
            assert "chrome_title" in v.reasons, junk

    def test_decorated_chrome_is_still_chrome(self):
        """`**LATEST NEWS**` and `12. Cruz roja argentina` both shipped. The
        decoration is stripped before the denylist is consulted, or the list
        would have to enumerate every way of dressing the same string."""
        email = "**LATEST NEWS** from the show floor this week, with more to follow."
        v = verify(
            _c(title="**LATEST NEWS**", evidence="**LATEST NEWS** from the show floor this week"),
            email, now=NOW,
        )
        assert not v.accepted
        assert "chrome_title" in v.reasons


class TestDates:
    def test_an_event_with_no_date_is_not_an_event(self):
        v = verify(_c(starts_at=None), EMAIL, now=NOW)
        assert not v.accepted
        assert "unparseable_date" in v.reasons

    def test_past_dates_are_rejected(self):
        v = verify(_c(starts_at=(NOW - timedelta(days=30)).date().isoformat()), EMAIL, now=NOW)
        assert not v.accepted
        assert "date_in_past" in v.reasons

    def test_absurdly_future_dates_are_rejected(self):
        v = verify(_c(starts_at="2099-01-01"), EMAIL, now=NOW)
        assert not v.accepted
        assert "date_too_far_ahead" in v.reasons

    def test_eighteen_months_out_is_allowed(self):
        """Spielwarenmesse 2027 is real and ~18 months away. A window that
        rejects it would hide the best row this source has produced."""
        v = verify(_c(starts_at="2027-02-02"), EMAIL, now=NOW)
        assert v.accepted, v.reasons

    def test_a_drop_needs_no_date(self):
        """A restock with no announced date is still a useful signal; only
        EVENTS are required to carry one."""
        v = verify(_c(kind="drop", starts_at=None), EMAIL, now=NOW)
        assert v.accepted, v.reasons


class TestConfidence:
    def test_low_confidence_is_rejected(self):
        v = verify(_c(confidence=MIN_CONFIDENCE - 0.01), EMAIL, now=NOW)
        assert not v.accepted
        assert "low_confidence" in v.reasons

    def test_confidence_cannot_rescue_an_ungrounded_candidate(self):
        """The ordering rule, pinned: a confident hallucination is still a
        hallucination. Confidence may only ever reject."""
        v = verify(_c(confidence=1.0, evidence="nothing like this appears in the email at all"),
                   EMAIL, now=NOW)
        assert not v.accepted
        assert "evidence_not_in_source" in v.reasons


class TestReasonsAreReported:
    def test_every_failing_reason_is_returned_not_just_the_first(self):
        """The reasons ARE the measurement. A dry run has to be able to say
        WHICH gate did the work, or we cannot tell a good model from a strict
        gate."""
        v = verify(
            # The evidence is LONG enough to reach the grounding check — the
            # evidence branch is an elif chain, so a too-short span would
            # short-circuit and this test would pin the wrong reason.
            Candidate(kind="event", title="Stay Connected", starts_at="1999-01-01",
                      confidence=0.1,
                      evidence="this sentence is comfortably long enough but appears nowhere"),
            EMAIL, now=NOW,
        )
        assert not v.accepted
        assert set(v.reasons) >= {
            "evidence_not_in_source", "chrome_title", "date_in_past", "low_confidence",
        }
