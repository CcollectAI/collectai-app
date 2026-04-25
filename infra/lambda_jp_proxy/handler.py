"""
JP-region HTML proxy — AWS Lambda in ap-northeast-1 (Tokyo).

Problem solved:
    EC2 main instance in eu-north-1 (Stockholm) is geo-filtered / served
    Google-Translate wrapper pages by Buyee (Yahoo Auctions JP proxy),
    Suruga-ya, and Booth. From a Tokyo IP, those same pages return real
    content.

Design:
    Pure HTML passthrough. Takes a target URL in the query string, fetches
    it from the JP region, returns the raw body. No parsing, no state. The
    existing adapter parsers (yahoo_auctions_caller, suruga_ya_caller,
    booth_caller) do the rest.

Auth:
    AWS IAM. Callers invoke via ``lambda.invoke(FunctionName=...)`` using
    credentials from the EC2 instance role (which has a narrow policy
    allowing only ``lambda:InvokeFunction`` on this specific ARN). No
    public HTTP endpoint, no shared secret to rotate.

Allow-list:
    Only proxies requests to known JP collectibles hosts. Prevents the
    URL from being used as an open proxy. Add hosts to ALLOW_HOSTS to
    extend.

Limits:
    * Lambda free tier: 1M invocations / 400K GB-seconds per month. Our
      expected volume is ~1-5K calls/day → well inside free tier.
    * Lambda max timeout: 15 min. We self-impose 25s so the caller can
      fail fast.
    * Payload limit: Lambda 6MB response. Typical JP marketplace HTML
      is 100-700KB.
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
    "buyee.jp",
    "www.buyee.jp",
    "auctions.yahoo.co.jp",
    "page.auctions.yahoo.co.jp",
    "suruga-ya.jp",
    "www.suruga-ya.jp",
    "booth.pm",
    "www.booth.pm",
    "www.hlj.com",
    "hlj.com",
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
    # Event shape: ``{"queryStringParameters": {"url": "..."}}`` when
    # invoked via boto3. IAM already gated the invocation — no secondary
    # token check needed here.
    qs = event.get("queryStringParameters") or {}

    # Validate target
    url = qs.get("url") or ""
    if not url.startswith("https://"):
        return _err(400, "url must start with https://")
    if not _host_allowed(url):
        return _err(403, f"host not in allow-list; current: {sorted(ALLOW_HOSTS)}")

    # Fetch
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _UA,
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            status = resp.status
            content_type = resp.headers.get("Content-Type", "text/html; charset=utf-8")
    except urllib.error.HTTPError as e:
        # Pass through non-2xx so caller can decide what to do with 403/429
        return _response(
            e.code,
            (e.read() or b"").decode("utf-8", errors="replace"),
            e.headers.get("Content-Type", "text/plain") if e.headers else "text/plain",
        )
    except Exception as e:
        logger.exception("fetch failed for %s", url)
        return _err(502, f"fetch failed: {e!r}")

    return _response(status, body.decode("utf-8", errors="replace"), content_type)
