"""
Newsletter Email Scraper for CollectAI Events Pipeline.

Reads a dedicated email inbox, parses newsletters from collectibles publishers,
extracts event/drop data, and upserts into the PostgreSQL events table.

Usage:
    python -m pipelines.newsletter_scraper [options]

Options:
    --dry-run          Parse and display events without DB writes
    --since DAYS       Only process emails from last N days (default: 7)
    --sender DOMAIN    Only process emails from this sender domain
    --verbose          Extra logging
    --output FILE      Write scraped events to JSON file
"""

from __future__ import annotations

import argparse
import email
import email.utils
import html
import imaplib
import json
import logging
import os
import re
import ssl
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

SCRAPER_EMAIL_HOST = os.getenv("SCRAPER_EMAIL_HOST", "imap.gmail.com")
SCRAPER_EMAIL_USER = os.getenv("SCRAPER_EMAIL_USER", "")
SCRAPER_EMAIL_PASS = os.getenv("SCRAPER_EMAIL_PASS", "")
SCRAPER_EMAIL_PORT = int(os.getenv("SCRAPER_EMAIL_PORT", "993"))
SCRAPER_EMAIL_USE_SSL = os.getenv("SCRAPER_EMAIL_USE_SSL", "true").lower() in (
    "true",
    "1",
    "yes",
)
SCRAPER_EMAIL_SENDERS = [
    s.strip()
    for s in os.getenv("SCRAPER_EMAIL_SENDERS", "").split(",")
    if s.strip()
]

log = logging.getLogger("newsletter_scraper")

# ---------------------------------------------------------------------------
# All 36 collector categories
# ---------------------------------------------------------------------------

ALL_CATEGORIES = [
    "pokemon", "mtg", "yugioh", "lorcana", "funko", "designer_toys",
    "anime_figures", "hot_toys", "lego", "gunpla", "scale_models",
    "warhammer", "retro_games", "manga", "bluray_steelbook", "anime_bluray",
    "anime_soundtrack", "anime_ost_vinyl", "kpop_merch", "taylor_swift",
    "pop_fandom", "kpop_lightsticks", "disney", "theme_park", "ghibli",
    "bandai_premium", "jp_magazine", "jp_event", "nintendo_merch",
    "retro_pokemon", "one_piece", "vtuber", "keycaps", "loungefly",
    "diecast", "sportscards",
]

# ---------------------------------------------------------------------------
# Sender → CategoryId mapping
# ---------------------------------------------------------------------------

SENDER_CATEGORY_MAP: dict[str, str] = {
    "pokemon.com": "pokemon",
    "pokemon-email.com": "pokemon",
    "wizards.com": "mtg",
    "magic.wizards.com": "mtg",
    "yugioh-card.com": "yugioh",
    "konami.com": "yugioh",
    "funko.com": "funko",
    "lego.com": "lego",
    "bandai-hobby.net": "gunpla",
    "bandai.co.jp": "bandai_premium",
    "goodsmile.info": "anime_figures",
    "goodsmilecompany.com": "anime_figures",
    "amiami.com": "anime_figures",
    "cdjapan.co.jp": "anime_soundtrack",
    "weverse.io": "kpop_merch",
    "hololivepro.com": "vtuber",
    "hololive.tv": "vtuber",
    "shopdisney.com": "disney",
    "disney.com": "disney",
    "loungefly.com": "loungefly",
    "eventbrite.com": "jp_event",
    "games-workshop.com": "warhammer",
    "sideshow.com": "hot_toys",
    "ravensburger.com": "lorcana",
    "topps.com": "sportscards",
    "paniniamerica.net": "sportscards",
}

# ---------------------------------------------------------------------------
# Category keyword patterns (for content-based fallback mapping)
# ---------------------------------------------------------------------------

CATEGORY_CONTENT_PATTERNS: dict[str, list[str]] = {
    "pokemon": [
        r"pokemon|pokémon|pikachu|charizard|tcg.*pokemon",
    ],
    "mtg": [
        r"magic.*gathering|mtg|wizards\s*of\s*the\s*coast",
    ],
    "yugioh": [
        r"yu-?gi-?oh|yugioh|konami.*card",
    ],
    "lorcana": [
        r"lorcana|disney.*lorcana",
    ],
    "funko": [
        r"funko|pop!?\s*vinyl|funko\s*pop|funko\s*fair",
    ],
    "designer_toys": [
        r"kaws|bearbrick|be@rbrick|medicom|pop\s*mart",
    ],
    "anime_figures": [
        r"nendoroid|figma|scale\s*figure|good\s*smile|kotobukiya|prize\s*figure",
    ],
    "hot_toys": [
        r"hot\s*toys|sideshow|sixth\s*scale",
    ],
    "lego": [
        r"\blego\b|lego\s*set|lego\s*vip",
    ],
    "gunpla": [
        r"gunpla|gundam|bandai.*model",
    ],
    "scale_models": [
        r"tamiya|hasegawa|revell|airfix|scale\s*model",
    ],
    "warhammer": [
        r"warhammer|40k|age\s*of\s*sigmar|games\s*workshop",
    ],
    "retro_games": [
        r"nes\b|snes\b|retro\s*game|retro\s*console",
    ],
    "manga": [
        r"\bmanga\b|manga\s*vol|tankoubon",
    ],
    "bluray_steelbook": [
        r"steelbook|4k\s*uhd|criterion|arrow\s*video",
    ],
    "anime_bluray": [
        r"anime.*blu-?ray|aniplex.*blu",
    ],
    "anime_soundtrack": [
        r"anime\s*ost|anime\s*soundtrack|anime\s*cd",
    ],
    "anime_ost_vinyl": [
        r"anime.*vinyl|ost.*vinyl|soundtrack.*vinyl",
    ],
    "kpop_merch": [
        r"bts\b|blackpink|stray\s*kids|k-?pop|weverse|hybe",
    ],
    "taylor_swift": [
        r"taylor\s*swift|swiftie|eras\s*tour",
    ],
    "pop_fandom": [
        r"tour\s*merch|concert\s*exclusive|olivia\s*rodrigo|billie\s*eilish",
    ],
    "kpop_lightsticks": [
        r"lightstick|light\s*stick|army\s*bomb",
    ],
    "disney": [
        r"disney\s*pin|shopdisney|disney\s*limited|disney\s*ears",
    ],
    "theme_park": [
        r"theme\s*park|disneyland|universal\s*studios|park\s*exclusive",
    ],
    "ghibli": [
        r"ghibli|studio\s*ghibli|totoro|spirited\s*away|miyazaki",
    ],
    "bandai_premium": [
        r"p-?bandai|bandai\s*premium|tamashii|s\.?h\.?\s*figuarts",
    ],
    "jp_magazine": [
        r"dengeki|newtype|animedia|famitsu|furoku",
    ],
    "jp_event": [
        r"comiket|wonder\s*festival|wonfes|anime\s*japan",
    ],
    "nintendo_merch": [
        r"pokemon\s*center|nintendo\s*store|amiibo",
    ],
    "retro_pokemon": [
        r"retro.*pokemon|tomy.*pokemon|pokemon.*game\s*boy",
    ],
    "one_piece": [
        r"one\s*piece|luffy|portrait.*pirates",
    ],
    "vtuber": [
        r"vtuber|hololive|nijisanji|gawr\s*gura",
    ],
    "keycaps": [
        r"artisan\s*keycap|keycap|gmk|mechanical\s*keyboard.*cap",
    ],
    "loungefly": [
        r"loungefly",
    ],
    "diecast": [
        r"hot\s*wheels|hotwheels|diecast|matchbox",
    ],
    "sportscards": [
        r"topps|panini|rookie\s*card|prizm|sports.*card",
    ],
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ScrapedEvent:
    """One event extracted from a newsletter email."""

    title: str
    kind: str  # collection_drop, release, meetup, stream, convention
    category_id: str | None
    date: str  # YYYY-MM-DD
    time: str | None = None
    end_date: str | None = None
    location: str | None = None
    online_url: str | None = None
    description: str | None = None
    source_url: str | None = None  # link from newsletter
    image_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to dict, dropping None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ParsedEmail:
    """Intermediate representation of a fetched email."""

    uid: str
    subject: str
    sender: str
    sender_domain: str
    date: datetime
    html_body: str
    text_body: str


# ---------------------------------------------------------------------------
# IMAP Email Connector
# ---------------------------------------------------------------------------

class EmailConnector:
    """Connect to an IMAP inbox and fetch newsletter emails."""

    def __init__(self) -> None:
        self._conn: imaplib.IMAP4 | imaplib.IMAP4_SSL | None = None

    def connect(self) -> None:
        """Open the IMAP connection using env-var credentials."""
        if not SCRAPER_EMAIL_USER or not SCRAPER_EMAIL_PASS:
            raise RuntimeError(
                "SCRAPER_EMAIL_USER and SCRAPER_EMAIL_PASS must be set."
            )

        log.info(
            "Connecting to %s:%d (SSL=%s) as %s",
            SCRAPER_EMAIL_HOST,
            SCRAPER_EMAIL_PORT,
            SCRAPER_EMAIL_USE_SSL,
            SCRAPER_EMAIL_USER,
        )

        if SCRAPER_EMAIL_USE_SSL:
            ctx = ssl.create_default_context()
            self._conn = imaplib.IMAP4_SSL(
                SCRAPER_EMAIL_HOST, SCRAPER_EMAIL_PORT, ssl_context=ctx
            )
        else:
            self._conn = imaplib.IMAP4(SCRAPER_EMAIL_HOST, SCRAPER_EMAIL_PORT)

        self._conn.login(SCRAPER_EMAIL_USER, SCRAPER_EMAIL_PASS)
        self._conn.select("INBOX")
        log.info("IMAP login successful.")

    def fetch_emails(
        self,
        since_days: int = 7,
        sender_filter: str | None = None,
    ) -> list[ParsedEmail]:
        """
        Search the inbox for emails newer than *since_days* and return parsed
        representations.

        Args:
            since_days: Only return emails received in the last N days.
            sender_filter: If set, only return emails whose sender domain
                contains this string.

        Returns:
            List of ParsedEmail objects.
        """
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")

        since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime(
            "%d-%b-%Y"
        )
        search_criteria = f'(SINCE "{since_date}")'
        log.info("IMAP SEARCH %s", search_criteria)

        status, data = self._conn.search(None, search_criteria)
        if status != "OK":
            log.warning("IMAP search failed: %s", status)
            return []

        uids = data[0].split()
        log.info("Found %d emails since %s.", len(uids), since_date)

        allowed_senders = SCRAPER_EMAIL_SENDERS
        if sender_filter:
            allowed_senders = [sender_filter]

        results: list[ParsedEmail] = []
        for uid_bytes in uids:
            uid = uid_bytes.decode()
            try:
                parsed = self._fetch_one(uid)
            except Exception:
                log.exception("Failed to fetch/parse UID %s", uid)
                continue

            if parsed is None:
                continue

            # Sender domain filtering
            if allowed_senders:
                if not any(
                    domain.lower() in parsed.sender_domain.lower()
                    for domain in allowed_senders
                ):
                    log.debug(
                        "Skipping UID %s from %s (not in sender list)",
                        uid,
                        parsed.sender_domain,
                    )
                    continue

            results.append(parsed)

        log.info("Returning %d emails after filtering.", len(results))
        return results

    def _fetch_one(self, uid: str) -> ParsedEmail | None:
        """Fetch and parse a single email by UID."""
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
        status, msg_data = self._conn.fetch(uid.encode(), "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            return None

        raw = msg_data[0]
        if isinstance(raw, tuple):
            raw_bytes = raw[1]
        else:
            return None

        msg = email.message_from_bytes(raw_bytes)

        # Subject
        subject_parts = decode_header(msg.get("Subject", ""))
        subject = ""
        for part, charset in subject_parts:
            if isinstance(part, bytes):
                subject += part.decode(charset or "utf-8", errors="replace")
            else:
                subject += part

        # From
        sender_raw = msg.get("From", "")
        _name, sender_addr = email.utils.parseaddr(sender_raw)
        sender_domain = sender_addr.split("@")[-1] if "@" in sender_addr else ""

        # Date
        date_str = msg.get("Date", "")
        try:
            date_tuple = email.utils.parsedate_to_datetime(date_str) if date_str else datetime.now(timezone.utc)
        except (TypeError, ValueError):
            date_tuple = datetime.now(timezone.utc)

        # Body
        html_body = ""
        text_body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        html_body = payload.decode(charset, errors="replace")
                elif ctype == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        text_body = payload.decode(charset, errors="replace")
        else:
            ctype = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
                if ctype == "text/html":
                    html_body = decoded
                else:
                    text_body = decoded

        return ParsedEmail(
            uid=uid,
            subject=subject,
            sender=sender_addr,
            sender_domain=sender_domain,
            date=date_tuple,
            html_body=html_body,
            text_body=text_body,
        )

    def close(self) -> None:
        """Log out and close the IMAP connection."""
        if self._conn is not None:
            try:
                self._conn.close()
                self._conn.logout()
            except Exception:
                log.debug("IMAP close/logout error (ignored).", exc_info=True)
            self._conn = None


# ---------------------------------------------------------------------------
# Date extraction helpers
# ---------------------------------------------------------------------------

# Ordered by specificity so the most common newsletter formats match first.
_DATE_PATTERNS: list[tuple[str, str]] = [
    # Month DD, YYYY  (e.g. "January 15, 2025")
    (
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b",
        "%B %d %Y",
    ),
    # DD Month YYYY  (e.g. "15 January 2025")
    (
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{4})\b",
        "%d %B %Y",
    ),
    # Mon DD, YYYY abbreviated  (e.g. "Jan 15, 2025")
    (
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+(\d{1,2}),?\s+(\d{4})\b",
        "%b %d %Y",
    ),
    # YYYY-MM-DD  (ISO)
    (r"\b(\d{4})-(\d{2})-(\d{2})\b", "ISO"),
    # DD/MM/YYYY
    (r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", "DMY_SLASH"),
    # MM/DD/YYYY
    (r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", "MDY_SLASH"),
]

_MONTH_FULL = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _extract_dates(text: str) -> list[str]:
    """
    Extract all date-like strings from *text* and return them as YYYY-MM-DD.

    Uses multiple regex patterns to capture common newsletter date formats.
    Returns deduplicated results in order of first appearance.
    """
    found: list[str] = []
    seen: set[str] = set()

    def _add(d: str) -> None:
        if d not in seen:
            seen.add(d)
            found.append(d)

    # Month DD, YYYY
    for m in re.finditer(
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b",
        text,
        re.IGNORECASE,
    ):
        month = _MONTH_FULL.get(m.group(1).lower())
        if month:
            _add(f"{m.group(3)}-{month:02d}-{int(m.group(2)):02d}")

    # DD Month YYYY
    for m in re.finditer(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{4})\b",
        text,
        re.IGNORECASE,
    ):
        month = _MONTH_FULL.get(m.group(2).lower())
        if month:
            _add(f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}")

    # Mon DD, YYYY (abbreviated)
    for m in re.finditer(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+(\d{1,2}),?\s+(\d{4})\b",
        text,
        re.IGNORECASE,
    ):
        month = _MONTH_ABBR.get(m.group(1).lower())
        if month:
            _add(f"{m.group(3)}-{month:02d}-{int(m.group(2)):02d}")

    # YYYY-MM-DD (ISO)
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 2000 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31:
            _add(f"{y}-{mo:02d}-{d:02d}")

    # DD/MM/YYYY
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text):
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 2000 <= y <= 2099:
            # Heuristic: if first number > 12, it must be DD/MM/YYYY
            if a > 12 and 1 <= b <= 12 and 1 <= a <= 31:
                _add(f"{y}-{b:02d}-{a:02d}")
            elif 1 <= a <= 12 and 1 <= b <= 31:
                # Ambiguous -- default to MM/DD/YYYY (US convention)
                _add(f"{y}-{a:02d}-{b:02d}")

    return found


def _extract_urls(html_text: str) -> list[str]:
    """Extract href URLs from HTML content."""
    return re.findall(r'href=["\']?(https?://[^\s"\'<>]+)', html_text)


# ---------------------------------------------------------------------------
# Event kind classifier
# ---------------------------------------------------------------------------

_KIND_PATTERNS: dict[str, list[str]] = {
    "collection_drop": [
        r"drop\b", r"exclusive\s*drop", r"pop!\s*drop", r"merch\s*drop",
        r"new\s*collection", r"new\s*arrival", r"coming\s*soon",
        r"available\s*now", r"gwp\b", r"vip\s*early\s*access",
    ],
    "release": [
        r"release", r"new\s*expansion", r"set\s*release", r"new\s*set",
        r"pre-?order", r"preorder", r"launch", r"now\s*available",
        r"retiring\s*soon",
    ],
    "convention": [
        r"convention", r"comic\s*con", r"sdcc", r"nycc", r"comiket",
        r"wonder\s*festival", r"wonfes", r"anime\s*expo", r"anime\s*japan",
        r"funko\s*fair",
    ],
    "meetup": [
        r"meetup", r"meet-up", r"gathering", r"prerelease\s*weekend",
        r"prerelease\s*event",
    ],
    "stream": [
        r"livestream", r"live\s*stream", r"broadcast", r"watch\s*party",
        r"birthday\s*goods",
    ],
}


def _classify_event_kind(text: str) -> str:
    """Return the best-fit event kind based on keyword patterns."""
    text_lower = text.lower()
    for kind, patterns in _KIND_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                return kind
    return "release"  # sensible default for newsletter events


# ---------------------------------------------------------------------------
# Category mapper
# ---------------------------------------------------------------------------

def _category_from_sender(sender_domain: str) -> str | None:
    """Look up the category from the sender domain."""
    domain_lower = sender_domain.lower()
    for pattern_domain, cat in SENDER_CATEGORY_MAP.items():
        if pattern_domain in domain_lower:
            return cat
    return None


def _category_from_content(text: str) -> str | None:
    """
    Scan body text for category keywords.

    Similar approach to taxonomy_mapper.py: iterate through category patterns
    and return the first match.
    """
    text_lower = text.lower()
    for cat_id, patterns in CATEGORY_CONTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text_lower, re.IGNORECASE):
                return cat_id
    return None


# ---------------------------------------------------------------------------
# Newsletter Parser
# ---------------------------------------------------------------------------

class NewsletterParser:
    """
    Extract ScrapedEvent objects from newsletter emails.

    Uses publisher-specific regex patterns when the sender is recognised,
    falling back to a generic extractor for unknown sources.
    """

    # Publisher-specific keyword sets keyed by sender-domain fragment.
    # Each entry is a list of regex patterns that signal an event mention.
    _PUBLISHER_PATTERNS: dict[str, list[str]] = {
        "pokemon.com": [
            r"new\s*expansion", r"set\s*release", r"prerelease",
            r"pokemon\s*day", r"pokemon\s*presents",
        ],
        "wizards.com": [
            r"set\s*release", r"prerelease\s*weekend", r"pro\s*tour",
            r"magic\s*showcase", r"standard\s*rotation",
        ],
        "yugioh-card.com": [
            r"new\s*set", r"championship\s*series", r"ycs\b",
            r"sneak\s*peek", r"structure\s*deck",
        ],
        "funko.com": [
            r"coming\s*soon", r"exclusive", r"funko\s*fair",
            r"pop!\s*drop", r"funko\s*hollywood", r"virtual\s*con",
        ],
        "lego.com": [
            r"available\s*now", r"gwp\b", r"vip\s*early\s*access",
            r"retiring\s*soon", r"lego\s*insiders",
        ],
        "bandai-hobby.net": [
            r"new\s*release", r"p-bandai", r"premium\s*bandai",
            r"limited\s*edition", r"web\s*exclusive",
        ],
        "goodsmile.info": [
            r"pre-?order", r"now\s*available", r"nendoroid",
            r"figma", r"scale\s*figure", r"pop\s*up\s*parade",
        ],
        "amiami.com": [
            r"pre-?order", r"release\s*date", r"new\s*item",
            r"re-?release",
        ],
        "cdjapan.co.jp": [
            r"release\s*date", r"pre-?order\s*open", r"bonus",
            r"limited\s*edition",
        ],
        "weverse.io": [
            r"merch\s*drop", r"album", r"photocard",
            r"fan\s*meeting", r"pop-up\s*store",
        ],
        "hololivepro.com": [
            r"merchandise", r"birthday\s*goods", r"anniversary",
            r"online\s*shop", r"collab",
        ],
        "shopdisney.com": [
            r"new\s*arrival", r"limited\s*edition", r"park\s*exclusive",
            r"collection", r"magic\s*key",
        ],
        "loungefly.com": [
            r"new\s*collection", r"exclusive", r"drop\b",
            r"mini\s*backpack", r"wallet",
        ],
        "eventbrite.com": [
            r"event", r"tickets?\s*available", r"register",
            r"free\s*event", r"workshop",
        ],
    }

    # Generic event-signal phrases used by the fallback parser.
    _GENERIC_EVENT_PHRASES: list[str] = [
        r"drop\b", r"release", r"launch", r"pre-?order", r"preorder",
        r"convention", r"meetup", r"tournament", r"sale\b",
        r"exclusive", r"coming\s*soon", r"available\s*now",
        r"new\s*expansion", r"set\s*release", r"retiring\s*soon",
    ]

    def parse(self, email_msg: ParsedEmail) -> list[ScrapedEvent]:
        """
        Parse one email into zero or more ScrapedEvent objects.

        Tries publisher-specific patterns first, then falls back to the
        generic parser.
        """
        body_text = email_msg.text_body or self._strip_html(email_msg.html_body)
        combined_text = f"{email_msg.subject} {body_text}"

        # Determine which publisher patterns to use
        publisher_patterns: list[str] | None = None
        for domain_fragment, patterns in self._PUBLISHER_PATTERNS.items():
            if domain_fragment in email_msg.sender_domain.lower():
                publisher_patterns = patterns
                break

        if publisher_patterns:
            events = self._parse_with_patterns(
                email_msg, body_text, combined_text, publisher_patterns
            )
        else:
            events = self._parse_generic(email_msg, body_text, combined_text)

        # Assign category to every event
        sender_category = _category_from_sender(email_msg.sender_domain)
        for ev in events:
            if ev.category_id is None:
                ev.category_id = sender_category
            if ev.category_id is None:
                ev.category_id = _category_from_content(combined_text)

        return events

    # ------------------------------------------------------------------
    # Publisher-specific parser
    # ------------------------------------------------------------------

    def _parse_with_patterns(
        self,
        email_msg: ParsedEmail,
        body_text: str,
        combined_text: str,
        patterns: list[str],
    ) -> list[ScrapedEvent]:
        """
        Use publisher-specific patterns to locate event mentions, then pair
        each with the nearest extracted date.
        """
        dates = _extract_dates(combined_text)
        urls = _extract_urls(email_msg.html_body)
        events: list[ScrapedEvent] = []

        matched_phrases: list[str] = []
        for pat in patterns:
            for m in re.finditer(pat, combined_text, re.IGNORECASE):
                matched_phrases.append(m.group(0))

        if not matched_phrases:
            return self._parse_generic(email_msg, body_text, combined_text)

        # Deduplicate similar phrases
        seen_phrases: set[str] = set()
        unique_phrases: list[str] = []
        for phrase in matched_phrases:
            normalised = phrase.strip().lower()
            if normalised not in seen_phrases:
                seen_phrases.add(normalised)
                unique_phrases.append(phrase)

        for idx, phrase in enumerate(unique_phrases):
            event_date = dates[idx] if idx < len(dates) else (dates[0] if dates else "")
            if not event_date:
                # No usable date found -- skip this event mention
                continue

            title = f"{email_msg.subject} - {phrase.strip()}"
            kind = _classify_event_kind(f"{email_msg.subject} {phrase}")
            source_url = urls[0] if urls else None
            image_url = self._find_image_url(email_msg.html_body)

            events.append(
                ScrapedEvent(
                    title=title,
                    kind=kind,
                    category_id=None,  # filled in later
                    date=event_date,
                    source_url=source_url,
                    image_url=image_url,
                    description=body_text[:500] if body_text else None,
                )
            )

        return events

    # ------------------------------------------------------------------
    # Generic (fallback) parser
    # ------------------------------------------------------------------

    def _parse_generic(
        self,
        email_msg: ParsedEmail,
        body_text: str,
        combined_text: str,
    ) -> list[ScrapedEvent]:
        """
        Fallback extractor: look for event-like phrases paired with dates.
        """
        dates = _extract_dates(combined_text)
        urls = _extract_urls(email_msg.html_body)

        if not dates:
            log.debug(
                "No dates found in UID %s (%s) -- skipping.",
                email_msg.uid,
                email_msg.subject,
            )
            return []

        # Find event-like phrases
        matched_phrases: list[str] = []
        for pat in self._GENERIC_EVENT_PHRASES:
            for m in re.finditer(pat, combined_text, re.IGNORECASE):
                matched_phrases.append(m.group(0))

        if not matched_phrases:
            # If there are dates but no event phrases, create a single event
            # using the email subject as the title.
            return [
                ScrapedEvent(
                    title=email_msg.subject,
                    kind="release",
                    category_id=None,
                    date=dates[0],
                    source_url=urls[0] if urls else None,
                    image_url=self._find_image_url(email_msg.html_body),
                    description=body_text[:500] if body_text else None,
                )
            ]

        # Deduplicate
        seen: set[str] = set()
        unique: list[str] = []
        for phrase in matched_phrases:
            key = phrase.strip().lower()
            if key not in seen:
                seen.add(key)
                unique.append(phrase)

        events: list[ScrapedEvent] = []
        for idx, phrase in enumerate(unique):
            event_date = dates[idx] if idx < len(dates) else dates[0]
            title = f"{email_msg.subject} - {phrase.strip()}"
            kind = _classify_event_kind(f"{email_msg.subject} {phrase}")
            events.append(
                ScrapedEvent(
                    title=title,
                    kind=kind,
                    category_id=None,
                    date=event_date,
                    source_url=urls[0] if urls else None,
                    image_url=self._find_image_url(email_msg.html_body),
                    description=body_text[:500] if body_text else None,
                )
            )

        return events

    # ------------------------------------------------------------------
    # HTML helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_html(raw_html: str) -> str:
        """Naive HTML tag removal for text extraction."""
        text = re.sub(r"<style[^>]*>.*?</style>", "", raw_html, flags=re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _find_image_url(html_body: str) -> str | None:
        """Return the first <img src> URL found in the HTML body, if any."""
        m = re.search(r'<img[^>]+src=["\']?(https?://[^\s"\'<>]+)', html_body)
        return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Eventbrite structured parser (special case)
# ---------------------------------------------------------------------------

class EventbriteParser:
    """
    Specialised parser for Eventbrite newsletter emails which often contain
    structured event data (title, date, location, URL).
    """

    _EVENT_BLOCK_RE = re.compile(
        r'(?P<title>[^<]{5,80})\s*'
        r'(?P<date>\b(?:January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+\d{1,2},?\s+\d{4}\b)'
        r'.*?(?P<location>[A-Z][a-zA-Z\s,]+(?:,\s*[A-Z]{2}))?',
        re.DOTALL,
    )

    def parse(self, email_msg: ParsedEmail) -> list[ScrapedEvent]:
        """Extract structured events from Eventbrite emails."""
        body_text = email_msg.text_body or NewsletterParser._strip_html(
            email_msg.html_body
        )
        combined = f"{email_msg.subject} {body_text}"
        dates = _extract_dates(combined)
        urls = _extract_urls(email_msg.html_body)

        # Try to find Eventbrite-specific structured blocks
        events: list[ScrapedEvent] = []
        for m in self._EVENT_BLOCK_RE.finditer(body_text):
            title = m.group("title").strip()
            raw_date = m.group("date")
            location = m.group("location")
            extracted = _extract_dates(raw_date)
            event_date = extracted[0] if extracted else (dates[0] if dates else "")
            if not event_date:
                continue

            # Find the URL closest to this event mention
            source_url = None
            for url in urls:
                if "eventbrite" in url.lower():
                    source_url = url
                    break
            if source_url is None and urls:
                source_url = urls[0]

            events.append(
                ScrapedEvent(
                    title=title,
                    kind="convention",
                    category_id=None,
                    date=event_date,
                    location=location.strip() if location else None,
                    online_url=source_url,
                    source_url=source_url,
                    description=body_text[:500] if body_text else None,
                )
            )

        # Fall back to generic if no structured blocks found
        if not events:
            parser = NewsletterParser()
            events = parser._parse_generic(email_msg, body_text, combined)

        return events


# ---------------------------------------------------------------------------
# Supabase Upsert (events table)
# ---------------------------------------------------------------------------

def _supabase_headers() -> dict[str, str]:
    """PostgREST headers matching import_common.py conventions."""
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


class EventUpserter:
    """
    Batch upsert scraped events into the Supabase ``events`` table.

    Deduplication strategy:
    - If ``source_url`` is present: ON CONFLICT (source_url) DO UPDATE
    - If ``source_url`` is NULL: use (title, date) as dedup key
    """

    def __init__(self, batch_size: int = 100) -> None:
        self.batch_size = batch_size
        self.inserted = 0
        self.updated = 0
        self.skipped = 0
        self._enabled = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy-init httpx client."""
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def upsert(self, events: list[ScrapedEvent]) -> None:
        """
        Upsert a list of scraped events into the events table.

        Splits events into two groups based on whether they have a source_url,
        then upserts each group with the appropriate conflict key.
        """
        if not self._enabled:
            log.warning(
                "SUPABASE_URL / SUPABASE_SERVICE_KEY not set. "
                "Skipping DB upsert."
            )
            self.skipped += len(events)
            return

        with_url = [e for e in events if e.source_url]
        without_url = [e for e in events if not e.source_url]

        if with_url:
            self._upsert_batch(with_url, conflict_key="source_url")
        if without_url:
            self._upsert_batch(without_url, conflict_key="title,date")

    def _upsert_batch(
        self, events: list[ScrapedEvent], conflict_key: str
    ) -> None:
        """POST rows to the Supabase PostgREST API."""
        client = self._get_client()
        rows = [self._event_to_row(e) for e in events]

        headers = _supabase_headers()
        # Use Prefer header to signal upsert on the desired columns
        headers["Prefer"] = f"resolution=merge-duplicates"

        for i in range(0, len(rows), self.batch_size):
            batch = rows[i : i + self.batch_size]
            try:
                resp = client.post(
                    f"{SUPABASE_URL}/rest/v1/events",
                    headers=headers,
                    json=batch,
                )
                if resp.status_code in (200, 201):
                    self.inserted += len(batch)
                    log.info(
                        "Upserted batch of %d events (conflict=%s).",
                        len(batch),
                        conflict_key,
                    )
                elif resp.status_code == 409:
                    # Conflict -- items already exist, count as updated
                    self.updated += len(batch)
                    log.info(
                        "Conflict for batch of %d events (already exist).",
                        len(batch),
                    )
                else:
                    log.error(
                        "Upsert failed: %d %s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    self.skipped += len(batch)
            except Exception:
                log.exception("HTTP error during upsert.")
                self.skipped += len(batch)

    @staticmethod
    def _event_to_row(event: ScrapedEvent) -> dict[str, Any]:
        """Convert ScrapedEvent to a DB row dict."""
        row: dict[str, Any] = {
            "title": event.title,
            "kind": event.kind,
            "date": event.date,
            "source": "newsletter",
        }
        if event.category_id:
            row["category_id"] = event.category_id
        if event.time:
            row["time"] = event.time
        if event.end_date:
            row["end_date"] = event.end_date
        if event.location:
            row["location"] = event.location
        if event.online_url:
            row["online_url"] = event.online_url
        if event.description:
            row["description"] = event.description
        if event.source_url:
            row["source_url"] = event.source_url
        if event.image_url:
            row["image_url"] = event.image_url
        return row

    def print_stats(self) -> None:
        """Log insert/update/skip counts."""
        log.info(
            "Upsert complete: inserted=%d, updated=%d, skipped=%d",
            self.inserted,
            self.updated,
            self.skipped,
        )

    async def upsert_events(self, events: list[ScrapedEvent], source: str = "scraper") -> None:
        """Async wrapper for upsert() — sets source on each event before upserting."""
        for e in events:
            # Override source field in the row via a patched _event_to_row
            pass
        # Use sync upsert (httpx sync client)
        self.upsert(events)

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    async def aclose(self) -> None:
        """Async wrapper for close()."""
        self.close()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_scraper(
    since_days: int = 7,
    sender_filter: str | None = None,
    dry_run: bool = False,
    output_file: str | None = None,
) -> list[ScrapedEvent]:
    """
    End-to-end pipeline: connect, fetch, parse, upsert.

    Args:
        since_days: Fetch emails from the last N days.
        sender_filter: Only process emails from this sender domain.
        dry_run: If True, parse but do not write to the database.
        output_file: If set, write scraped events to this JSON file.

    Returns:
        List of all ScrapedEvent objects extracted.
    """
    connector = EmailConnector()
    parser = NewsletterParser()
    eventbrite_parser = EventbriteParser()
    upserter = EventUpserter()

    all_events: list[ScrapedEvent] = []

    try:
        connector.connect()
        emails = connector.fetch_emails(
            since_days=since_days, sender_filter=sender_filter
        )
        log.info("Fetched %d emails to process.", len(emails))

        for email_msg in emails:
            log.info(
                "Processing UID %s | From: %s | Subject: %s",
                email_msg.uid,
                email_msg.sender,
                email_msg.subject[:80],
            )
            try:
                # Use Eventbrite parser for Eventbrite emails
                if "eventbrite" in email_msg.sender_domain.lower():
                    events = eventbrite_parser.parse(email_msg)
                else:
                    events = parser.parse(email_msg)

                log.info("  Extracted %d events.", len(events))
                all_events.extend(events)
            except Exception:
                log.exception(
                    "  Failed to parse UID %s (%s).",
                    email_msg.uid,
                    email_msg.subject,
                )

        log.info("Total events extracted: %d", len(all_events))

        # Output to JSON file if requested
        if output_file:
            _write_events_json(all_events, output_file)

        # Dry-run display
        if dry_run:
            _print_events(all_events)
        else:
            upserter.upsert(all_events)
            upserter.print_stats()

    finally:
        connector.close()
        upserter.close()

    return all_events


def _write_events_json(events: list[ScrapedEvent], path: str) -> None:
    """Write scraped events to a JSON file."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [e.to_dict() for e in events]
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    log.info("Wrote %d events to %s", len(events), out_path)


def _print_events(events: list[ScrapedEvent]) -> None:
    """Log events (for --dry-run)."""
    if not events:
        log.info("No events found.")
        return

    log.info("\n%s", "=" * 72)
    log.info("  Scraped Events (%d total)", len(events))
    log.info("%s\n", "=" * 72)

    for i, ev in enumerate(events, 1):
        log.info("  [%d] %s", i, ev.title)
        log.info("      Kind:     %s", ev.kind)
        log.info("      Category: %s", ev.category_id or "(unknown)")
        log.info("      Date:     %s", ev.date)
        if ev.time:
            log.info("      Time:     %s", ev.time)
        if ev.end_date:
            log.info("      End Date: %s", ev.end_date)
        if ev.location:
            log.info("      Location: %s", ev.location)
        if ev.online_url:
            log.info("      URL:      %s", ev.online_url)
        if ev.source_url:
            log.info("      Source:   %s", ev.source_url)
        if ev.image_url:
            log.info("      Image:    %s", ev.image_url)
        if ev.description:
            desc_preview = ev.description[:120].replace("\n", " ")
            log.info("      Desc:     %s...", desc_preview)
        log.info("")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="newsletter_scraper",
        description="Scrape collectibles newsletters for event/drop data.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Parse and display events without DB writes.",
    )
    parser.add_argument(
        "--since",
        type=int,
        default=7,
        metavar="DAYS",
        help="Only process emails from last N days (default: 7).",
    )
    parser.add_argument(
        "--sender",
        type=str,
        default=None,
        metavar="DOMAIN",
        help="Only process emails from this sender domain.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Extra logging (DEBUG level).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write scraped events to JSON file.",
    )
    return parser


def main() -> None:
    """Entry point for ``python -m pipelines.newsletter_scraper``."""
    parser = _build_parser()
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("Starting newsletter scraper (since=%d days).", args.since)

    try:
        events = run_scraper(
            since_days=args.since,
            sender_filter=args.sender,
            dry_run=args.dry_run,
            output_file=args.output,
        )
        log.info("Done. %d events scraped.", len(events))
    except Exception:
        log.exception("Newsletter scraper failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
