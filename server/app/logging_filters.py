"""Redaction filter for the uvicorn access log.

`docs/legal` and `app/legal/privacy-policy.tsx` promise users that precise
location "is not stored on our servers". Uvicorn's access log defeats that
promise by default: it writes the **full** request path including the query
string, so `GET /events/nearby?lat=52.3676&lon=4.9041` lands verbatim in
`/opt/collectors/bake.log` — precise GPS, on disk, attributable by timestamp.

The fix is here rather than at the call site on purpose. Redacting `lat`/`lon`
alone would leave the next sensitive query parameter to be discovered the same
way, so this **fails closed**: every query value is redacted unless its key is
on `SAFE_QUERY_KEYS`. Adding a parameter cannot leak by omission — only by an
explicit decision to allow it.

Keys are kept in the clear so the logs stay useful for debugging; only values
are replaced:

    GET /events/nearby?lat=52.3676&lon=4.9041   ->
    GET /events/nearby?lat=<redacted>&lon=<redacted>
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

REDACTED = "<redacted>"

# Values safe to log in the clear: pagination, ordering and bounded enums.
# Nothing user-authored (search terms, coordinates, emails, tokens, ids that
# identify a person) belongs here. When in doubt, leave it out — the cost is a
# less readable log line, and the cost of the other mistake is a privacy
# incident.
SAFE_QUERY_KEYS = frozenset({
    "limit", "offset", "page", "per_page", "cursor",
    "sort", "order", "direction", "range", "timeframe", "period",
    "radius_km", "status", "tab", "view", "format",
})


def redact_query(path: str) -> str:
    """Return *path* with every non-allowlisted query value redacted."""
    if "?" not in path:
        return path
    try:
        parts = urlsplit(path)
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        if not pairs:
            return path
        cleaned = [
            (k, v if k.lower() in SAFE_QUERY_KEYS else REDACTED) for k, v in pairs
        ]
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(cleaned), parts.fragment)
        )
    except Exception:
        # Never let logging raise. A path we cannot parse is a path we cannot
        # vouch for, so drop the query string entirely rather than pass it on.
        return path.split("?", 1)[0] + "?" + REDACTED


class AccessLogRedactionFilter(logging.Filter):
    """Redact query-string values in `uvicorn.access` records.

    Uvicorn formats access lines from `record.args`, a 5-tuple of
    ``(client_addr, method, full_path, http_version, status_code)``. Rewriting
    element 2 before formatting is what actually changes the bytes on disk;
    editing `record.msg` would not, because the path lives in the args.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            if "?" in args[2]:
                record.args = args[:2] + (redact_query(args[2]),) + args[3:]
        return True


def install_access_log_redaction() -> None:
    """Attach the filter to `uvicorn.access`. Safe to call more than once."""
    log = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, AccessLogRedactionFilter) for f in log.filters):
        log.addFilter(AccessLogRedactionFilter())

# ── Outbound requests ────────────────────────────────────────────────────────
#
# The same defect, the other direction (found 2026-09-12). httpx logs every
# request it makes at INFO, URL included, so third-party credentials that
# travel in a query string were written to `bake.log` in full. Measured on the
# live log:
#
#     app.ticketmaster.com   apikey       896 lines
#     api.seatgeek.com       client_id    752 lines
#     api.scrape.do          token        298 lines
#     api.telegram.org       bot<token>    81 lines  (in the PATH, not a param)
#
# mode 0664, plus four rotated copies. No line of our code was wrong — a
# dependency's default logging leaked the secrets, exactly as uvicorn's access
# log leaked GPS above.
#
# Reuses the fail-closed rule deliberately: an outbound query value is redacted
# unless its key is on the same allowlist. A new vendor with a new parameter
# name is covered on the day it is added, without anyone remembering to. Our
# own log lines already carry the useful context ("[Ticketmaster] anime expo/US
# → 1 raw / 0 on-topic"), so nothing diagnostic is lost.

# Secrets carried in the PATH rather than the query string. Telegram puts the
# bot token between `/bot` and the method name.
_PATH_SECRETS = (
    (re.compile(r"(api\.telegram\.org/bot)[^/\s]+"), r"\1" + REDACTED),
)


def redact_url(url: str) -> str:
    """Redact credentials in an outbound URL — query values and path secrets."""
    try:
        for pattern, replacement in _PATH_SECRETS:
            url = pattern.sub(replacement, url)
        return redact_query(url)
    except Exception:
        # A logger must never raise. Drop everything after the host instead.
        return url.split("?", 1)[0]



def _redact_arg(value):
    """Redact a log argument that carries a URL, whatever its type.

    ⚠️ httpx passes an **httpx.URL object**, not a string — an `isinstance(a,
    str)` guard here silently skipped every real request while the unit tests
    (which used plain strings) passed. Caught only by an end-to-end run against
    the live vendors; the fixture was simpler than reality. Anything whose
    `str()` contains a scheme is treated as a URL and rendered redacted.
    """
    if isinstance(value, str):
        return redact_url(value) if "://" in value else value
    try:
        text = str(value)
    except Exception:
        return value
    return redact_url(text) if "://" in text else value


class OutboundLogRedactionFilter(logging.Filter):
    """Redact URLs in `httpx` records.

    httpx formats its line from `record.args` — ``(method, url, http_version,
    status_code, reason)`` — so the URL must be rewritten in the ARGS. It also
    catches a URL already baked into `record.msg`, which is what happens when
    another logger re-emits one.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            args = record.args
            if isinstance(args, tuple):
                rewritten = tuple(_redact_arg(a) for a in args)
                if rewritten != args:
                    record.args = rewritten
            if isinstance(record.msg, str) and "://" in record.msg:
                redacted = redact_url(record.msg)
                if redacted != record.msg and not record.args:
                    record.msg = redacted
        except Exception:
            pass
        return True


def install_outbound_log_redaction() -> None:
    """Attach the outbound filter to httpx AND the root handlers.

    Both: the logger-level filter covers records httpx makes itself, and the
    handler-level one covers anything that re-emits a URL through a different
    logger — and survives httpx renaming its logger. Safe to call repeatedly.
    """
    def _attach(target) -> None:
        if not any(isinstance(f, OutboundLogRedactionFilter) for f in target.filters):
            target.addFilter(OutboundLogRedactionFilter())

    for name in ("httpx", "httpcore", "urllib3", "aiohttp.client"):
        _attach(logging.getLogger(name))
    for handler in logging.getLogger().handlers:
        _attach(handler)
