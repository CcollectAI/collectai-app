"""eBay marketplace-account-deletion notifications.

WHY THIS EXISTS (2026-10-05)
----------------------------------------------------------------------------
eBay requires every production app to "subscribe to eBay marketplace account
deletion/closure notifications; or follow the process to opt out", and opting
out is only allowed when "not persisting any eBay data". Failure "will result
in termination of your access to the Developer Tools, and/or reduced access to
all or some APIs" (developer.ebay.com/marketplace-account-deletion).

We persist eBay listing data in `market_hits`, so the opt-out does not fit and
we subscribe instead. The subscription is made through the Notification API
(topic MARKETPLACE_ACCOUNT_DELETION, application scope, no extra OAuth scope);
see docs/EBAY_MARKETPLACE_INSIGHTS.md.

WHAT WE DELETE
----------------------------------------------------------------------------
Nothing, because we hold nothing keyed to an eBay user: `market_hits` stores
listings, and its seller columns (`seller_rating`, `seller_score`) are empty
(0 non-null, 2026-10-05). If an eBay username, userId or eiasToken is ever
stored, this handler must delete it; the notification payload carries all
three. Until then it acknowledges and logs only the notification id, never the
user fields, since logging them would itself be persisting eBay user data.

THE CHALLENGE (eBay's spec, verbatim order)
----------------------------------------------------------------------------
GET <endpoint>?challenge_code=123 -> 200, Content-Type application/json,
{"challengeResponse": sha256(challengeCode + verificationToken + endpoint)}.
`endpoint` must be byte-identical to the URL registered with eBay, which is
why it is configured (EBAY_NOTIFICATION_ENDPOINT) rather than rebuilt from the
request: behind nginx the request URL is not the public one.

PUBLIC BY DESIGN: listed in docs/API.md "Every endpoint that answers WITHOUT
a token". The GET reveals nothing (a hash of a value eBay chose), and the POST
changes nothing.
"""

from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from app.config import EBAY_NOTIFICATION_ENDPOINT, EBAY_NOTIFICATION_VERIFICATION_TOKEN

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ebay", tags=["ebay"])


def challenge_response(challenge_code: str, verification_token: str, endpoint: str) -> str:
    """eBay's challenge hash: sha256(challengeCode + verificationToken + endpoint), hex."""
    h = hashlib.sha256()
    h.update(challenge_code.encode("utf-8"))
    h.update(verification_token.encode("utf-8"))
    h.update(endpoint.encode("utf-8"))
    return h.hexdigest()


@router.get("/marketplace-account-deletion", summary="eBay endpoint verification challenge")
async def account_deletion_challenge(
    challenge_code: str = Query(..., min_length=1, max_length=512),
):
    if not (EBAY_NOTIFICATION_ENDPOINT and EBAY_NOTIFICATION_VERIFICATION_TOKEN):
        # Unconfigured must not answer with a wrong hash, which eBay would
        # reject without saying why; say so plainly instead.
        logger.error("[ebay-notify] challenge received but endpoint/token not configured")
        return JSONResponse({"error": "not configured"}, status_code=503)
    return JSONResponse(
        {"challengeResponse": challenge_response(
            challenge_code, EBAY_NOTIFICATION_VERIFICATION_TOKEN, EBAY_NOTIFICATION_ENDPOINT)},
        status_code=200,
    )


@router.post("/marketplace-account-deletion", summary="eBay account deletion notification")
async def account_deletion_notification(request: Request):
    """Acknowledge at once (eBay accepts 200/201/202/204); we hold no eBay user data."""
    notification_id = topic = None
    try:
        body = await request.json()
        notification_id = (body.get("notification") or {}).get("notificationId")
        topic = (body.get("metadata") or {}).get("topic")
    except Exception as e:
        logger.warning("[ebay-notify] unreadable notification body: %s", type(e).__name__)
    logger.info("[ebay-notify] %s notification %s acknowledged (no eBay user data held)",
                topic or "?", notification_id or "?")
    return Response(status_code=204)
