"""
JP-region HTML proxy client.

Routes HTML fetches through an AWS Lambda function in ap-northeast-1
(Tokyo) so our EU-based EC2 can see JP sites that geo-filter non-JP IPs
(Buyee, Yahoo JP, Suruga-ya, Booth).

Invocation uses IAM (EC2 instance role has ``lambda:InvokeFunction`` on
the function ARN) rather than a public Function URL. Reason: Function
URLs with ``AuthType=NONE`` are blocked by AWS's account-level public
access restriction on newer accounts, regardless of resource policy.
IAM-auth invoke via boto3 sidesteps this entirely and is more secure —
no public endpoint, no shared secret.

When ``JP_PROXY_FUNCTION_NAME`` is unset, ``fetch_via_proxy()`` returns
None and the caller falls back to direct httpx (which typically fails
from EU IP — but preserves the pre-existing behavior in local dev).

See ``infra/lambda_jp_proxy/`` for the Lambda source + deploy guide.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Defaults — overridable via env. The function is deployed in Tokyo and
# its name is hardcoded in deploy.sh; exposing via env in case of rename.
_DEFAULT_FUNCTION_NAME = "collectai-jp-proxy"
_DEFAULT_REGION = "ap-northeast-1"


def configured() -> bool:
    # Presence of the env var flips the proxy path on. Absence = fall back
    # to direct httpx. We accept an empty string as unset.
    return bool(os.environ.get("JP_PROXY_FUNCTION_NAME"))


def _function_name() -> str:
    return os.environ.get("JP_PROXY_FUNCTION_NAME") or _DEFAULT_FUNCTION_NAME


def _region() -> str:
    return os.environ.get("JP_PROXY_REGION") or _DEFAULT_REGION


def _invoke_sync(url: str, timeout: float) -> Optional[str]:
    """Synchronous boto3 invoke. Called off the event loop via to_thread."""
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        logger.warning("[jp_proxy] boto3 not available; proxy disabled")
        return None

    client = boto3.client(
        "lambda",
        region_name=_region(),
        config=Config(
            connect_timeout=5,
            read_timeout=int(timeout),
            retries={"max_attempts": 1},  # circuit breaker handles retries
        ),
    )
    payload = json.dumps(
        {"queryStringParameters": {"url": url}},
    ).encode("utf-8")

    try:
        resp = client.invoke(
            FunctionName=_function_name(),
            InvocationType="RequestResponse",
            Payload=payload,
        )
    except Exception as e:
        logger.debug("[jp_proxy] invoke error for %s: %s", url, e)
        return None

    if resp.get("FunctionError"):
        logger.debug(
            "[jp_proxy] function error for %s: %s",
            url, resp.get("FunctionError"),
        )
        return None

    body_bytes = resp["Payload"].read()
    try:
        envelope = json.loads(body_bytes)
    except Exception:
        logger.debug("[jp_proxy] bad payload for %s", url)
        return None

    status = envelope.get("statusCode", 0)
    if status != 200:
        logger.debug(
            "[jp_proxy] upstream HTTP %d for %s (body head: %s)",
            status, url, (envelope.get("body") or "")[:200],
        )
        return None

    return envelope.get("body") or None


async def fetch_via_proxy(url: str, *, timeout: float = 30.0) -> Optional[str]:
    """Fetch *url* through the JP Lambda. Returns HTML body on success, None on failure.

    The Lambda has a host allow-list (see ``handler.py:ALLOW_HOSTS``) and
    imposes its own 25s fetch timeout. Our *timeout* is the total boto3
    invoke budget.
    """
    if not configured():
        return None
    # boto3 is sync — run in a thread to avoid blocking the event loop.
    return await asyncio.to_thread(_invoke_sync, url, timeout)
