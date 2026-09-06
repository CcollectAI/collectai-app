"""The access log must not put user coordinates on disk.

`app/legal/privacy-policy.tsx` tells users their precise location "is not
stored on our servers". Uvicorn's access log logs the full path by default, so
without the filter that sentence is false the first time anyone opens Nearby
Events.

These tests assert on the line that actually reaches a handler — capturing the
formatted output rather than the filter's return value, because a filter that
edited `record.msg` instead of `record.args` would pass the easy test and still
write GPS to bake.log.
"""

import logging
from io import StringIO

from app.logging_filters import (
    AccessLogRedactionFilter,
    install_access_log_redaction,
    redact_query,
)

UVICORN_ACCESS_FMT = '%s - "%s %s HTTP/%s" %d'


def _emit(path: str) -> str:
    """Log one uvicorn-shaped access record through the filter; return the line."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log = logging.getLogger("test.uvicorn.access")
    log.handlers = [handler]
    log.propagate = False
    log.setLevel(logging.INFO)
    log.filters = [AccessLogRedactionFilter()]
    log.info(UVICORN_ACCESS_FMT, "127.0.0.1:1", "GET", path, "1.1", 200)
    return stream.getvalue().strip()


def test_coordinates_never_reach_the_log():
    line = _emit("/events/nearby?lat=52.3676&lon=4.9041&radius_km=50")
    assert "52.3676" not in line, line
    assert "4.9041" not in line, line
    # The keys survive so the log stays debuggable, and radius_km is allowlisted.
    assert "lat=%3Credacted%3E" in line or "lat=<redacted>" in line, line
    assert "radius_km=50" in line, line


def test_fails_closed_on_an_unknown_parameter():
    """A parameter nobody thought about must be redacted, not passed through."""
    line = _emit("/search?some_future_param=merle@example.com")
    assert "merle" not in line, line


def test_allowlisted_pagination_stays_readable():
    line = _emit("/notifications/history?limit=20&offset=40")
    assert "limit=20" in line and "offset=40" in line, line


def test_paths_without_a_query_are_untouched():
    assert redact_query("/healthz") == "/healthz"


def test_unparseable_query_drops_rather_than_leaks():
    assert "secret" not in redact_query("/x?%%%=secret")


def test_install_is_idempotent():
    log = logging.getLogger("uvicorn.access")
    before = list(log.filters)
    install_access_log_redaction()
    install_access_log_redaction()
    added = [f for f in log.filters if isinstance(f, AccessLogRedactionFilter)]
    assert len(added) == 1
    log.filters = before + added[:1]
