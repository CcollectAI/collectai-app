"""Every return URL the server hands Stripe must use the scheme the app registers.

2026-09-24: all ten Stripe success/cancel/return URLs said `collectai://`, a
scheme no build registers (app.json: "sparrow"). After paying for a ticket, a
sponsorship or a web subscription, the member hit a browser error with no way
back into the app. Nothing failed server-side, so nothing logged it.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import APP_URL_SCHEME  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def test_scheme_matches_app_json():
    scheme = json.loads((REPO / "app.json").read_text())["expo"]["scheme"]
    assert APP_URL_SCHEME == scheme


def test_no_hardcoded_foreign_scheme_urls():
    offenders = []
    for p in (REPO / "server" / "app").rglob("*.py"):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if re.search(r"""["'](?:collectai|collectorsai)://""", line):
                offenders.append(f"{p.relative_to(REPO)}:{i}")
    assert not offenders, "use APP_URL_SCHEME: " + ", ".join(offenders)
