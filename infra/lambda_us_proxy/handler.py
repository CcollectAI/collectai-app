"""
US-region HTML proxy — AWS Lambda in us-east-1 (Virginia).

Problem solved:
    Mercari US and a handful of US-first marketplaces geo-filter non-US
    IPs. From a US IP, those pages return real content. Mirror of the
    JP Lambda at infra/lambda_jp_proxy/.

Design:
    Pure HTML passthrough. Takes a target URL in the query string, fetches
    it from the US region, returns the raw body. Existing adapter parsers
    (mercari_us_caller, etc.) do the parsing.

Auth:
    AWS IAM. EC2 instance role has a narrow ``lambda:InvokeFunction``
    policy on this specific ARN. No public endpoint, no shared secret.

Allow-list:
    Mercari US + small expansion list. Prevents use as an open proxy.
"""

from __future__ import annotations

import json
import logging
import os
from urllib.parse import urlparse
import urllib.error
import urllib.request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TIMEOUT = int(os.environ.get("FETCH_TIMEOUT_SECONDS", "25"))

ALLOW_HOSTS: set[str] = {
    "mercari.com",
    "www.mercari.com",
    "api.mercari.com",
    # US-first marketplaces we may add later
    "stockx.com",
    "www.stockx.com",
    "grailed.com",
    "www.grailed.com",
    "depop.com",
    "www.depop.com",
}

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.6 Safari/605.1.15"
)


def _response(status: int, body: str, content_type: str = "application/json") -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": content_type,
            "Cache-Control": "no-store",
        },
        "body": body,
    }


def _err(status: int, msg: str) -> dict:
    return _response(status, json.dumps({"error": msg}))


def _host_allowed(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in ALLOW_HOSTS


def handler(event: dict, _context) -> dict:
    qs = event.get("queryStringParameters") or {}
    url = qs.get("url") or ""
    if not url.startswith("https://"):
        return _err(400, "url must start with https://")
    if not _host_allowed(url):
        return _err(403, f"host not in allow-list; current: {sorted(ALLOW_HOSTS)}")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _UA,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            status = resp.status
            content_type = resp.headers.get("Content-Type", "text/html; charset=utf-8")
    except urllib.error.HTTPError as e:
        return _response(
            e.code,
            (e.read() or b"").decode("utf-8", errors="replace"),
            e.headers.get("Content-Type", "text/plain") if e.headers else "text/plain",
        )
    except Exception as e:
        logger.exception("fetch failed for %s", url)
        return _err(502, f"fetch failed: {e!r}")

    return _response(status, body.decode("utf-8", errors="replace"), content_type)
