"""One listing, one key — however the marketplace decorates its URL.

2026-09-24: the Deal Agent showed a member the SAME eBay item four times.
eBay's search API returns each item URL with a fresh per-request tracking
token (`amdata=…`, `hash=…`, `_skw=…`), and deal dedup compared full URLs,
so every scan "discovered" the listing again and stored another deal row.

`listing_key` is what dedup compares. It is never stored as the link and
never opened: the member still gets the URL the marketplace handed us.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit

_EBAY_ITEM = re.compile(r"/itm/(?:[^/]+/)?(\d{9,15})(?:[/?#]|$)")

# Parameters that change per request/session and say nothing about WHICH
# listing it is. Anything not listed here is kept: for some sites the query
# IS the identity, and dropping it would merge different listings.
_TRACKING = {
    "amdata", "hash", "_skw", "_trkparms", "_trksid", "var", "epid",
    "mkevt", "mkcid", "mkrid", "campid", "customid", "toolid", "siteid",
    "gclid", "fbclid", "ref", "ref_",
}


def listing_key(url: str | None) -> str:
    if not url:
        return ""
    raw = url.strip()
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    host = (parts.hostname or "").lower().removeprefix("www.")
    if host.startswith("ebay.") or ".ebay." in f".{host}":
        m = _EBAY_ITEM.search(parts.path + ("?" if parts.query else ""))
        if m:
            # Same item across ebay.com / ebay.de / ebay.co.uk.
            return f"ebay:{m.group(1)}"
    kept = sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING and not k.lower().startswith("utm_")
    )
    path = parts.path.rstrip("/") or "/"
    return f"{host}{path}" + (f"?{urlencode(kept)}" if kept else "")
