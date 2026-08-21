"""
LLM extraction for newsletter emails — with a grounding gate in front of it.

WHY THIS EXISTS
---------------
`newsletter_scraper.EventbriteParser._EVENT_BLOCK_RE` takes "any 5-80 characters
that happen to precede a date" as a title and scans the whole document for a
location. Measured twice:

  2026-07-27  14 of 14 `source='newsletter'` rows were boilerplate, 9 of them
              live in the upcoming feed.
  2026-08-22  17 rows total; ~2 are real. "Site Navsito", "Stay Connected",
              "Frequently asked questions" and "Performance Cookies" all sit
              beside a genuine "Spielwarenmesse".

The question a title has to answer — *is this a thing that happens at a time and
a place?* — is SEMANTIC. `docs/EVENT_QUALITY_PLAN.md` §"NOT in scope" says "no ML
model for spam classification: rule-based beats a tiny model at <1k events/day",
and that judgement stands for CLASSIFYING an already-extracted event. This is a
different job: turning prose into fields at all. Rules have now failed at that
twice, with the numbers above.

⚠️ THE POINT OF THIS FILE IS THE GATE, NOT THE MODEL
----------------------------------------------------
An LLM's failure mode is the opposite of the regex's. The regex emitted obvious
garbage — markup residue, locations like "ic/media/pcenLogo" — which is exactly
what `event_quality.py`'s penalties were tuned to catch (`markup_in_title`,
`location_not_place_shaped`). A model emits *clean, plausible* fields, so every
one of those penalties scores a hallucinated event as fine. Swapping the
extractor without adding a gate would move us from visible junk to INVISIBLE
junk, which is strictly worse.

So the model is never trusted for content. It is asked to point at text, and
`verify()` — pure, deterministic, no network — checks that the text it pointed
at actually exists in the email:

  1. GROUNDING        every candidate carries `evidence`, a verbatim span from
                      the email. If that span is not in the source, the model
                      invented it. This is the load-bearing gate.
  2. TITLE-IN-SOURCE  the title must appear in the email too. A model that
                      summarises rather than extracts writes a headline nobody
                      sent.
  3. CHROME           a denylist built from rows that actually shipped.
  4. DATE SANITY      parses, and inside a sane window.
  5. CONFIDENCE       self-reported, and deliberately LAST — it is the weakest
                      signal here, because a confident hallucination is still a
                      hallucination. It can only reject, never rescue.

NOTHING IN THIS MODULE WRITES TO THE DATABASE. `extract_and_verify()` returns
verdicts; wiring it into `EventUpserter` is a separate, deliberate step that
must not happen until a dry run over a real inbox has been measured. The
existing source-level quarantine (`event_quality.UNRELIABLE_FREE_TEXT_SOURCES`)
stays ON until that measurement says otherwise — the 2026-07-27 version shipped
9 junk rows into the live feed, and the lesson is to get the number first.

Usage (dry run, writes nothing):
    python -m pipelines.newsletter_llm_extract --file sample.txt --sender pokemon.com
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger("newsletter_llm_extract")

MODEL = os.getenv("NEWSLETTER_EXTRACT_MODEL", "claude-haiku-4-5")
MAX_TOKENS_OUT = int(os.getenv("NEWSLETTER_EXTRACT_MAX_TOKENS", "2048"))

# A candidate must clear this to be accepted. Self-reported, so it is a floor
# and not evidence — see the module docstring.
MIN_CONFIDENCE = float(os.getenv("NEWSLETTER_EXTRACT_MIN_CONFIDENCE", "0.7"))

# An evidence span shorter than this proves nothing: "2026" appears in every
# newsletter ever written.
MIN_EVIDENCE_CHARS = 24

# How far ahead an event may sit. Beyond this it is far more likely a misparsed
# year than a real announcement. `Spielwarenmesse` 2027 is real and ~18 months
# out, so this is deliberately generous.
MAX_DAYS_AHEAD = 800

# Titles that ARE the failure mode. Every entry was taken from a row that
# actually shipped to prod, not imagined — see the measurements above.
_CHROME_TITLES = {
    "site navigation", "site navsito", "stay connected", "frequently asked questions",
    "performance cookies", "latest news", "support for private & trade visitors",
    "privacy policy", "terms of service", "cookie policy", "unsubscribe",
    "view in browser", "contact us", "about us", "follow us", "newsletter",
    "shop now", "read more", "learn more", "sign up", "log in",
}

# Chrome that arrives decorated ("**LATEST NEWS**", "12. Cruz roja argentina").
_STRIP_DECORATION = re.compile(r"^[\s*_#>\-–—•·]+|[\s*_#>\-–—•·]+$")
_LEADING_LIST_NUMBER = re.compile(r"^\d{1,2}[.)]\s+")


def _norm(s: str) -> str:
    """Whitespace- and case-insensitive form, for substring checks only.

    Newsletters arrive as HTML converted to text, so the same sentence can
    differ from the model's echo of it by line wrapping alone. Comparing on a
    collapsed form keeps grounding strict about CONTENT without making it
    brittle about layout.
    """
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def _clean_title(s: str) -> str:
    s = _STRIP_DECORATION.sub("", s or "")
    return _LEADING_LIST_NUMBER.sub("", s).strip()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    raw = value.strip().replace("Z", "+00:00")
    for parse in (datetime.fromisoformat, lambda v: datetime.strptime(v, "%Y-%m-%d")):
        try:
            dt = parse(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


@dataclass
class Candidate:
    """One thing the model claims it found. Untrusted until verified."""
    kind: str                      # 'event' | 'drop'
    title: str
    starts_at: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    confidence: float = 0.0
    evidence: str = ""             # VERBATIM span from the email


@dataclass
class Verdict:
    candidate: Candidate
    accepted: bool
    reasons: list[str] = field(default_factory=list)


def verify(c: Candidate, source_text: str, *, now: Optional[datetime] = None) -> Verdict:
    """The gate. Pure, deterministic, no network — so it is testable, and so a
    model or prompt change cannot silently loosen it.

    Order matters: grounding first, confidence LAST. A confident hallucination
    is still a hallucination, so confidence may only reject, never rescue.
    """
    reasons: list[str] = []
    src = _norm(source_text)
    title = _clean_title(c.title)

    # 1. GROUNDING — the load-bearing check.
    ev = _norm(c.evidence)
    if not ev:
        reasons.append("no_evidence")
    elif len(ev) < MIN_EVIDENCE_CHARS:
        reasons.append("evidence_too_short")
    elif ev not in src:
        # The model returned a span that is not in the email it was given.
        reasons.append("evidence_not_in_source")

    # 2. The title must be in the email too.
    if not title:
        reasons.append("empty_title")
    elif _norm(title) not in src:
        reasons.append("title_not_in_source")

    # 3. Chrome, measured rather than guessed.
    if _norm(title) in _CHROME_TITLES:
        reasons.append("chrome_title")

    # 4. Date sanity. An event with no date is not an event; a drop without one
    #    is still useful, so only events are required to carry one.
    if c.kind == "event":
        dt = _parse_dt(c.starts_at)
        if dt is None:
            reasons.append("unparseable_date")
        else:
            ref = now or datetime.now(timezone.utc)
            if dt < ref - timedelta(days=1):
                reasons.append("date_in_past")
            elif dt > ref + timedelta(days=MAX_DAYS_AHEAD):
                reasons.append("date_too_far_ahead")

    # 5. Confidence, last and lowest-weight.
    if c.confidence < MIN_CONFIDENCE:
        reasons.append("low_confidence")

    return Verdict(candidate=c, accepted=not reasons, reasons=reasons)


_SYSTEM_PROMPT = """You extract events and product drops from collectibles newsletters.

You are reading an email converted from HTML to text, so it contains navigation,
footers, cookie notices and legal boilerplate alongside any real content. Most
emails contain NO event and NO drop. Returning an empty list is the correct and
common answer.

An EVENT is something a person attends at a time and a place: a convention, a
tournament, a launch party, a signing, a store opening.
A DROP is a product becoming buyable at a time: a set release, a restock, a
preorder opening, a numbered edition going on sale.

NEVER return: navigation labels, section headings, cookie or privacy notices,
article headlines, "shop now"/"read more" calls to action, or anything whose
title you cannot find written in the email.

For every item you return, `evidence` MUST be copied VERBATIM from the email — a
contiguous span of at least 24 characters containing the claim. Do not
paraphrase, do not reformat, do not fix typos. If you cannot copy a verbatim
span that supports the item, do not return the item."""

_TOOL = {
    "name": "submit_extracted",
    "description": "Return the events and drops found in this email, or an empty list.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["event", "drop"]},
                        "title": {"type": "string"},
                        "starts_at": {"type": "string", "description": "ISO 8601 date or datetime; omit if unknown"},
                        "location": {"type": "string"},
                        "description": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "evidence": {"type": "string", "description": "VERBATIM span copied from the email"},
                    },
                    "required": ["kind", "title", "confidence", "evidence"],
                },
            }
        },
        "required": ["items"],
    },
}


def _to_candidates(payload: dict[str, Any]) -> list[Candidate]:
    out: list[Candidate] = []
    for raw in payload.get("items") or []:
        if not isinstance(raw, dict):
            continue
        try:
            out.append(Candidate(
                kind=str(raw.get("kind") or "event"),
                title=str(raw.get("title") or ""),
                starts_at=raw.get("starts_at") or None,
                location=raw.get("location") or None,
                description=raw.get("description") or None,
                confidence=float(raw.get("confidence") or 0.0),
                evidence=str(raw.get("evidence") or ""),
            ))
        except (TypeError, ValueError) as e:
            logger.warning("[newsletter_llm] unusable item %r: %s", raw, e)
    return out


async def extract(email_text: str, sender: str = "") -> list[Candidate]:
    """Ask the model for candidates.

    Returns [] on every failure path, and LOGS AT ERROR each time. A source we
    could not read must not be indistinguishable from a source with nothing in
    it — that is the `[]`-is-not-`None` rule this repo already applies to the
    watchdog's Logflare collector.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.error("[newsletter_llm] ANTHROPIC_API_KEY not set — extraction skipped")
        return []
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        logger.error("[newsletter_llm] anthropic SDK not installed; pip install anthropic")
        return []

    # The same budget gate every other model call in this repo goes through, so
    # one runaway inbox cannot spend the month's allowance.
    try:
        from app.lib.spend_tracker import SpendTracker
        tracker = SpendTracker.instance() if hasattr(SpendTracker, "instance") else SpendTracker()
        tracker.check("newsletter_extract")
    except Exception as e:  # noqa: BLE001 — covers BudgetExceededError + import failure
        logger.warning("[newsletter_llm] budget gate blocked: %s", e)
        return []

    client = AsyncAnthropic()
    try:
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_OUT,
            system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "submit_extracted"},
            messages=[{"role": "user", "content": f"Sender: {sender}\n\n{email_text}"}],
        )
    except Exception as e:  # noqa: BLE001
        logger.error("[newsletter_llm] API call failed: %s", e)
        return []

    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return _to_candidates(getattr(block, "input", {}) or {})
    logger.error("[newsletter_llm] no tool_use block in response")
    return []


async def extract_and_verify(email_text: str, sender: str = "") -> list[Verdict]:
    """Extract, then gate. Returns EVERY candidate with its verdict — rejected
    ones included, because the rejection reasons ARE the measurement that says
    whether this is safe to wire up at all."""
    return [verify(c, email_text) for c in await extract(email_text, sender)]


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Dry-run the newsletter extractor. Writes nothing.")
    ap.add_argument("--file", required=True, help="Path to an email body (text)")
    ap.add_argument("--sender", default="", help="Sender domain, for category hints")
    args = ap.parse_args(argv)

    with open(args.file, encoding="utf-8", errors="replace") as fh:
        body = fh.read()
    verdicts = asyncio.run(extract_and_verify(body, args.sender))

    accepted = [v for v in verdicts if v.accepted]
    print(f"\n{len(verdicts)} candidate(s), {len(accepted)} accepted\n")
    for v in verdicts:
        mark = "ACCEPT" if v.accepted else "reject"
        print(f"[{mark}] {v.candidate.kind:5} {v.candidate.title[:60]!r}")
        if not v.accepted:
            print(f"         reasons: {', '.join(v.reasons)}")
    print("\nNothing was written. Wiring this into EventUpserter is a separate step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
