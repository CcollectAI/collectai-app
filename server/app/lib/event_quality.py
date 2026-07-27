"""
Event quality scoring — Phase 1 of the event-safeguards plan.

Design: docs/EVENT_QUALITY_PLAN.md

Two cheap rule-based outputs stamped at ingest time:
  - trust_tier: string ∈ {verified, publisher, unverified, community}
  - quality_score: int 0-100 (rule sum; higher = more trustworthy)

Intent:
  - `quality_score < 40` → UX should hide from default feed
  - `40-69` → show with "Unverified" label
  - `≥ 70` → normal display
  - See docs/EVENT_QUALITY_PLAN.md for the rationale behind each weight.

Runtime: pure function, no I/O, no network. Safe to call in the hot
ingest path; called once per ScrapedEvent before the upsert.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Source → trust tier mapping
# ---------------------------------------------------------------------------

_TRUST_TIER_BY_SOURCE: dict[str, str] = {
    # First-party APIs — verified
    "ticketmaster": "verified",
    "seatgeek": "verified",
    "bandsintown": "verified",
    "musicbrainz": "verified",
    # Publisher feeds / newsletters — publisher
    "newsletter": "publisher",
    "rss": "publisher",
    "limitless_tcg": "publisher",
    "pokemon_com": "publisher",
    "wizards_com": "publisher",
    "warhammer_community": "publisher",
    "lego_com": "publisher",
    "funko_blog": "publisher",
    "taylorswift_com": "publisher",
    "goodsmile_news": "publisher",
    # Generic scrapes — unverified
    "firecrawl": "unverified",
    "crawl4ai": "unverified",
    "scraper": "unverified",
    "eventbrite_scrape": "unverified",
    # User submissions — community
    "user_submission": "community",
    "community": "community",
    # POST /events writes source='user' (events_core.py), not
    # 'user_submission'. Without this entry the lookup fell through to the
    # `unverified` default and mislabelled every in-app submission.
    "user": "community",
}


def map_source_to_trust_tier(source: str | None) -> str:
    """Return the trust tier for a given `events.source` string.

    Unknown sources default to `unverified`. Callers pass the raw
    source passed into EventUpserter.upsert(..., source="...").
    """
    if not source:
        return "unverified"
    return _TRUST_TIER_BY_SOURCE.get(source.lower().strip(), "unverified")


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

_SPAM_KEYWORDS = (
    "free iphone",
    "click here",
    "100% guaranteed",
    "limited time offer",
    "bit.ly/",
    "tinyurl.com/",
    "goo.gl/",
    "t.co/",
)

# Rough emoji heuristic: any codepoint ≥ 0x1F300 (Symbols and Pictographs block onward).
def _emoji_count(s: str) -> int:
    return sum(1 for c in s if ord(c) >= 0x1F300)


# Markdown-link syntax or a raw URL appearing inside a field that should
# hold a human-readable value. Used by the penalties in score_event().
_MD_OR_URL_RESIDUE = re.compile(r"\]\(|https?://|www\.", re.IGNORECASE)


# Single-token location values that are legitimate answers rather than
# extractor debris. No live row uses these today (every structured feed
# writes "Venue, City, Country"), but an online-only or unannounced event
# is a real thing and must not be hidden for lacking a comma.
_VENUELESS_BUT_VALID: frozenset[str] = frozenset(
    {"online", "virtual", "worldwide", "tba", "tbd", "tbc", "remote", "livestream"}
)


# Sources whose events are produced by free-text/regex extraction over
# newsletter and RSS bodies rather than a structured feed. The parser
# (pipelines/newsletter_scraper.py::EventbriteParser._EVENT_BLOCK_RE)
# takes "any 5-80 characters that happen to precede a date" as the title
# and scans the whole document for a location, so it emits page chrome —
# measured 2026-07-27 as 14 of 14 rows being boilerplate, 9 of them in
# the live upcoming feed. Rows from these sources are withheld from the
# default feed until that extractor is rewritten to validate title, date
# and venue independently. This is a source-level gate on a KNOWN-broken
# producer, not a judgement about newsletters as a category.
UNRELIABLE_FREE_TEXT_SOURCES: frozenset[str] = frozenset({"newsletter"})


def is_display_ready(source: str | None, quality_score: int | None) -> bool:
    """Whether an event may appear in the default feed.

    Mirrors the SQL predicate applied in the events read path, so Python
    callers and the database agree on one rule. `quality_score IS NULL`
    counts as display-ready: rows predating the Phase-1 backfill have no
    score, and failing them closed would empty the feed.
    """
    if source and source.lower().strip() in UNRELIABLE_FREE_TEXT_SOURCES:
        return False
    if quality_score is None:
        return True
    return quality_score >= 40


class _EventLike(Protocol):
    """Structural type covering both ScrapedEvent and dict events."""
    title: str
    date: str
    location: Any
    source_url: Any
    image_url: Any
    description: Any


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def score_event(event: Any, trust_tier: str = "unverified") -> tuple[int, str]:
    """Return (score, reason_codes) for an event.

    `event` may be a ScrapedEvent dataclass, an asdict of one, or any
    object exposing the same attribute/key set.  `reason_codes` is a
    pipe-joined string of fired rule codes for debug/audit; `ok` when
    no penalties fired. Max score = 100.
    """
    if isinstance(event, dict):
        get = event.get
    else:
        def get(key, default=None):
            return getattr(event, key, default)

    title = _as_str(get("title"))
    date_str = _as_str(get("date"))
    location = _as_str(get("location"))
    source_url = _as_str(get("source_url")) or _as_str(get("url"))
    image_url = _as_str(get("image_url"))
    description = _as_str(get("description"))

    score = 0
    failures: list[str] = []

    # +10: title length 8-120
    if 8 <= len(title) <= 120:
        score += 10
    else:
        failures.append("bad_title_length")

    # +10: title not all-caps, <=3 emojis
    letters = [c for c in title if c.isalpha()]
    caps_ratio = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0.0
    if caps_ratio < 0.6 and _emoji_count(title) <= 3:
        score += 10
    else:
        failures.append("spammy_title")

    # +15: location with city+country (comma + length)
    if "," in location and len(location) > 10:
        score += 15
    else:
        failures.append("missing_location")

    # +15: date 1-365 days in the future
    date_delta: int | None = None
    if date_str:
        try:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            date_delta = (d - date.today()).days
        except (ValueError, TypeError):
            date_delta = None
    if date_delta is not None and 1 <= date_delta <= 365:
        score += 15
    elif date_delta is None:
        failures.append("no_date")
    else:
        failures.append("bad_date_range")

    # +10: source_url present and https(s)
    if source_url and re.match(r"^https?://", source_url):
        score += 10
    else:
        failures.append("no_source_url")

    # +10: image_url present and http(s)
    if image_url and re.match(r"^https?://", image_url):
        score += 10
    else:
        failures.append("no_image")

    # +10: description ≥ 50 chars
    if len(description) >= 50:
        score += 10
    else:
        failures.append("short_description")

    # +15: no spam keywords in title/description
    combined = (title + " " + description).lower()
    if not any(kw in combined for kw in _SPAM_KEYWORDS):
        score += 15
    else:
        failures.append("spam_keywords")

    # +5: trust-tier bonus for verified / publisher
    if trust_tier in ("verified", "publisher"):
        score += 5

    # -----------------------------------------------------------------
    # PENALTIES (added 2026-07-27).
    #
    # Everything above asks a STRUCTURAL question, and page chrome
    # answers all of them correctly: "Site Navigation" is 8-120 chars,
    # not all-caps, carries an http source_url and a 500-char body dump,
    # and sits on a future date. That banks 65 before anything semantic
    # runs, which is why 14 of 14 `source='newsletter'` rows — every one
    # of them boilerplate, not an event — scored 50-80 and displayed as
    # normal. Positive-only scoring cannot separate them; the score has
    # to be able to go DOWN. See docs/EVENT_QUALITY_PLAN.md.
    #
    # Each signal below was measured against all 2042 live rows before
    # being added, and fires on ZERO of the 2028 non-newsletter rows.
    # Deliberately NOT included: "location starts with a lowercase
    # letter". It catches 13 of 14 junk rows, but `indigo at The O2,
    # London, Great Britain` is a real Ticketmaster venue that is
    # genuinely stylised lowercase — a rule that hides real events to
    # catch boilerplate is a worse bug than the one it fixes.
    # -----------------------------------------------------------------

    # Markdown-link or raw-URL residue. A human-facing event title or
    # venue never contains "](" or "http" — their presence means the
    # extractor handed us a slice of source markup rather than a value.
    # Measured: 8/14 newsletter locations, 2/14 titles, 0/2028 elsewhere.
    if _MD_OR_URL_RESIDUE.search(title):
        score -= 40
        failures.append("markup_in_title")
    if _MD_OR_URL_RESIDUE.search(location):
        score -= 40
        failures.append("markup_in_location")

    # A POPULATED location that is not "Venue, City, Country"-shaped.
    # Every structured feed writes at least one comma; measured 0 of 2028
    # non-newsletter rows lack one, against 12 of 14 newsletter rows
    # ("e Events", "ional Sites & Searchricerc", "ic/media/pcenLogo").
    #
    # The emptiness case is deliberately excluded rather than folded in:
    # 1453 limitless_tcg tournaments are online and legitimately carry no
    # venue at all. They already forgo the +15; penalising them on top
    # would hide the single largest source in the table.
    #
    # -40 rather than -30 because the base score is inflated by rewards
    # this data earns for free: a 500-char body dump satisfies
    # "description >= 50" and an article URL satisfies "source_url is
    # http". At -30 "Site Navigation" landed on 45 and stayed visible.
    # The magnitude is safe to raise because the TRIGGER is what carries
    # false-positive risk, and the trigger fires on 0 of 2028 real rows.
    _loc = location.strip()
    if _loc and "," not in _loc and _loc.lower() not in _VENUELESS_BUT_VALID:
        score -= 40
        failures.append("location_not_place_shaped")

    # Description that merely repeats the title carries no independent
    # information; in practice it means the parser found one string and
    # used it for both fields.
    if description and description.strip() == title.strip():
        score -= 20
        failures.append("description_is_title")

    return max(0, min(100, score)), "|".join(failures) if failures else "ok"


# ---------------------------------------------------------------------------
# Display helpers for downstream code + tests
# ---------------------------------------------------------------------------

def display_state(score: int) -> str:
    """Map a quality_score to one of three UX buckets."""
    if score < 40:
        return "hidden"
    if score < 70:
        return "unverified"
    return "normal"
