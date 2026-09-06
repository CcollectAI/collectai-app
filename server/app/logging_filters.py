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
