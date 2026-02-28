"""
Deal Desk Router — P2P offer/negotiation layer.

Endpoints:
- POST   /deals/offer                  - Propose an offer
- POST   /deals/{offer_id}/counter     - Counter-offer
- POST   /deals/{offer_id}/respond     - Accept or decline
- POST   /deals/{offer_id}/cancel      - Cancel pending offer
- POST   /deals/{offer_id}/ship        - Mark as shipped
- POST   /deals/{offer_id}/complete    - Confirm delivery + rate
- GET    /deals/active                 - List active offers
- GET    /deals/history                - Completed/cancelled deals
- GET    /deals/{offer_id}             - Offer detail with events
- GET    /deals/{offer_id}/evidence    - Dossier snapshot
- GET    /deals/reputation/{user_id}   - User reputation
- PUT    /items/{item_id}/for-sale     - Toggle for_sale + asking price
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode
from app.rate_limit import per_user_rate_limit

router = APIRouter(tags=["deals"])
logger = logging.getLogger(__name__)

# Rate limits
_deal_action_limit = per_user_rate_limit(20, window_seconds=60, scope="deal_action")
_deal_read_limit = per_user_rate_limit(60, window_seconds=60, scope="deal_read")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ProposeOfferRequest(BaseModel):
    item_id: str = Field(..., description="Item UUID")
    price: float = Field(..., gt=0, description="Offer price")
    message: Optional[str] = Field(None, max_length=2000)


class CounterOfferRequest(BaseModel):
    price: float = Field(..., gt=0, description="Counter price")
    message: Optional[str] = Field(None, max_length=2000)


class RespondOfferRequest(BaseModel):
    accept: bool = Field(..., description="True to accept, false to decline")
    message: Optional[str] = Field(None, max_length=2000)


class ShipRequest(BaseModel):
    tracking_info: Optional[str] = Field(None, max_length=500)


class CompleteRequest(BaseModel):
    stars: int = Field(..., ge=1, le=5, description="Rating 1-5 stars")
    comment: Optional[str] = Field(None, max_length=2000)


class ToggleForSaleRequest(BaseModel):
    for_sale: bool
    asking_price: Optional[float] = Field(None, gt=0)
    currency: str = Field("EUR", pattern=r"^(EUR|USD|GBP|JPY|KRW|AUD|CAD)$")


# ---------------------------------------------------------------------------
# Helper: validate UUID
# ---------------------------------------------------------------------------

def _validate_uuid(value: str, field_name: str = "id") -> str:
    try:
        UUID(value)
        return value
    except (ValueError, AttributeError):
        raise error_response(400, f"Invalid {field_name}", code=ErrorCode.INVALID_UUID)


# ---------------------------------------------------------------------------
# POST /deals/offer — Propose an offer
# ---------------------------------------------------------------------------

@router.post("/deals/offer")
async def propose_offer(
    body: ProposeOfferRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_action_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    item_id = _validate_uuid(body.item_id, "item_id")

    try:
        async with pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT rpc_propose_offer_v1($1::uuid, $2::numeric, $3::text, $4::uuid)",
                item_id, body.price, body.message, user_id,
            )

        try:
            data = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Invalid JSON from RPC: %s", e)
            raise error_response(500, "Invalid response from database", code=ErrorCode.INTERNAL_ERROR)
        return data
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise exc
        msg = str(exc)
        if "not found" in msg.lower():
            raise error_response(404, msg, code=ErrorCode.NOT_FOUND)
        if "own item" in msg.lower():
            raise error_response(400, msg, code=ErrorCode.VALIDATION_ERROR)
        logger.exception("propose_offer failed")
        raise error_response(500, "Failed to propose offer", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /deals/{offer_id}/counter — Counter-offer
# ---------------------------------------------------------------------------

@router.post("/deals/{offer_id}/counter")
async def counter_offer(
    offer_id: str,
    body: CounterOfferRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_action_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    offer_id = _validate_uuid(offer_id, "offer_id")

    try:
        async with pool.acquire() as conn:
            # Pre-flight ownership check: caller must be buyer or seller
            participant = await conn.fetchval(
                "SELECT 1 FROM offers WHERE id = $1::uuid AND (seller_id = $2::uuid OR buyer_id = $2::uuid)",
                offer_id, user_id,
            )
            if not participant:
                raise error_response(403, "Not authorized to act on this offer", code=ErrorCode.FORBIDDEN)

            result = await conn.fetchval(
                "SELECT rpc_counter_offer_v1($1::uuid, $2::numeric, $3::text)",
                offer_id, body.price, body.message,
            )

        try:
            data = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Invalid JSON from RPC: %s", e)
            raise error_response(500, "Invalid response from database", code=ErrorCode.INTERNAL_ERROR)
        return data
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise exc
        msg = str(exc)
        if "not found" in msg.lower():
            raise error_response(404, msg, code=ErrorCode.NOT_FOUND)
        if "not authorized" in msg.lower():
            raise error_response(403, msg, code=ErrorCode.FORBIDDEN)
        if "cannot be countered" in msg.lower():
            raise error_response(409, msg, code=ErrorCode.CONFLICT)
        logger.exception("counter_offer failed")
        raise error_response(500, "Failed to counter offer", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /deals/{offer_id}/respond — Accept or decline
# ---------------------------------------------------------------------------

@router.post("/deals/{offer_id}/respond")
async def respond_offer(
    offer_id: str,
    body: RespondOfferRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_action_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    offer_id = _validate_uuid(offer_id, "offer_id")

    try:
        async with pool.acquire() as conn:
            # Pre-flight ownership check: caller must be buyer or seller
            participant = await conn.fetchval(
                "SELECT 1 FROM offers WHERE id = $1::uuid AND (seller_id = $2::uuid OR buyer_id = $2::uuid)",
                offer_id, user_id,
            )
            if not participant:
                raise error_response(403, "Not authorized to act on this offer", code=ErrorCode.FORBIDDEN)

            result = await conn.fetchval(
                "SELECT rpc_respond_offer_v1($1::uuid, $2::boolean, $3::text)",
                offer_id, body.accept, body.message,
            )

        try:
            data = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Invalid JSON from RPC: %s", e)
            raise error_response(500, "Invalid response from database", code=ErrorCode.INTERNAL_ERROR)
        return data
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise exc
        msg = str(exc)
        if "not found" in msg.lower():
            raise error_response(404, msg, code=ErrorCode.NOT_FOUND)
        if "not authorized" in msg.lower():
            raise error_response(403, msg, code=ErrorCode.FORBIDDEN)
        if "cannot be responded" in msg.lower():
            raise error_response(409, msg, code=ErrorCode.CONFLICT)
        logger.exception("respond_offer failed")
        raise error_response(500, "Failed to respond to offer", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /deals/{offer_id}/cancel — Cancel pending offer
# ---------------------------------------------------------------------------

@router.post("/deals/{offer_id}/cancel")
async def cancel_offer(
    offer_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_action_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    offer_id = _validate_uuid(offer_id, "offer_id")

    try:
        async with pool.acquire() as conn:
            # Pre-flight ownership check: caller must be buyer or seller
            participant = await conn.fetchval(
                "SELECT 1 FROM offers WHERE id = $1::uuid AND (seller_id = $2::uuid OR buyer_id = $2::uuid)",
                offer_id, user_id,
            )
            if not participant:
                raise error_response(403, "Not authorized to act on this offer", code=ErrorCode.FORBIDDEN)

            result = await conn.fetchval(
                "SELECT rpc_cancel_offer_v1($1::uuid)",
                offer_id,
            )

        try:
            data = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Invalid JSON from RPC: %s", e)
            raise error_response(500, "Invalid response from database", code=ErrorCode.INTERNAL_ERROR)
        return data
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise exc
        msg = str(exc)
        if "not found" in msg.lower():
            raise error_response(404, msg, code=ErrorCode.NOT_FOUND)
        if "only the proposer" in msg.lower():
            raise error_response(403, msg, code=ErrorCode.FORBIDDEN)
        if "cannot be cancelled" in msg.lower():
            raise error_response(409, msg, code=ErrorCode.CONFLICT)
        logger.exception("cancel_offer failed")
        raise error_response(500, "Failed to cancel offer", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /deals/{offer_id}/ship — Mark as shipped
# ---------------------------------------------------------------------------

@router.post("/deals/{offer_id}/ship")
async def mark_shipped(
    offer_id: str,
    body: ShipRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_action_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    offer_id = _validate_uuid(offer_id, "offer_id")

    try:
        async with pool.acquire() as conn:
            # Pre-flight ownership check: only seller can mark shipped
            is_seller = await conn.fetchval(
                "SELECT 1 FROM offers WHERE id = $1::uuid AND seller_id = $2::uuid",
                offer_id, user_id,
            )
            if not is_seller:
                raise error_response(403, "Only the seller can mark as shipped", code=ErrorCode.FORBIDDEN)

            result = await conn.fetchval(
                "SELECT rpc_mark_shipped_v1($1::uuid, $2::text)",
                offer_id, body.tracking_info,
            )

        try:
            data = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Invalid JSON from RPC: %s", e)
            raise error_response(500, "Invalid response from database", code=ErrorCode.INTERNAL_ERROR)
        return data
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise exc
        msg = str(exc)
        if "not found" in msg.lower():
            raise error_response(404, msg, code=ErrorCode.NOT_FOUND)
        if "only the seller" in msg.lower():
            raise error_response(403, msg, code=ErrorCode.FORBIDDEN)
        if "must be accepted" in msg.lower():
            raise error_response(409, msg, code=ErrorCode.CONFLICT)
        logger.exception("mark_shipped failed")
        raise error_response(500, "Failed to mark shipped", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /deals/{offer_id}/complete — Confirm delivery + rate
# ---------------------------------------------------------------------------

@router.post("/deals/{offer_id}/complete")
async def complete_deal(
    offer_id: str,
    body: CompleteRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_action_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    offer_id = _validate_uuid(offer_id, "offer_id")

    try:
        async with pool.acquire() as conn:
            # Pre-flight ownership check: only buyer can complete
            is_buyer = await conn.fetchval(
                "SELECT 1 FROM offers WHERE id = $1::uuid AND buyer_id = $2::uuid",
                offer_id, user_id,
            )
            if not is_buyer:
                raise error_response(403, "Only the buyer can complete the deal", code=ErrorCode.FORBIDDEN)

            result = await conn.fetchval(
                "SELECT rpc_complete_deal_v1($1::uuid, $2::smallint, $3::text)",
                offer_id, body.stars, body.comment,
            )

        try:
            data = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Invalid JSON from RPC: %s", e)
            raise error_response(500, "Invalid response from database", code=ErrorCode.INTERNAL_ERROR)

        # Record ground truth for data moat feedback loop (best-effort)
        try:
            async with pool.acquire() as conn2:
                offer_row = await conn2.fetchrow(
                    "SELECT item_id, current_price, currency FROM offers WHERE id = $1::uuid",
                    offer_id,
                )
            if offer_row:
                from app.features.data_moat import record_price_ground_truth
                await record_price_ground_truth(
                    item_id=str(offer_row["item_id"]),
                    actual_price=float(offer_row["current_price"]),
                    currency=offer_row["currency"] or "EUR",
                    source="deal_desk",
                )
        except Exception:
            pass

        return data
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise exc
        msg = str(exc)
        if "not found" in msg.lower():
            raise error_response(404, msg, code=ErrorCode.NOT_FOUND)
        if "only the buyer" in msg.lower():
            raise error_response(403, msg, code=ErrorCode.FORBIDDEN)
        if "must be accepted" in msg.lower():
            raise error_response(409, msg, code=ErrorCode.CONFLICT)
        logger.exception("complete_deal failed")
        raise error_response(500, "Failed to complete deal", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /deals/active — List active offers
# ---------------------------------------------------------------------------

@router.get("/deals/active")
async def list_active_offers(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _rl: None = Depends(_deal_read_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            total_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM v_offer_summary_v1
                WHERE (seller_id = $1 OR buyer_id = $1)
                  AND status IN ('proposed', 'countered', 'accepted')
                """,
                user_id,
            )

            rows = await conn.fetch(
                """
                SELECT * FROM v_offer_summary_v1
                WHERE (seller_id = $1 OR buyer_id = $1)
                  AND status IN ('proposed', 'countered', 'accepted')
                ORDER BY updated_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )

        return {
            "offers": [_row_to_offer_summary(dict(r), user_id) for r in rows],
            "total_count": total_count or 0,
        }
    except Exception:
        logger.exception("list_active_offers failed")
        raise error_response(500, "Failed to list active offers", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /deals/history — Completed/cancelled/declined deals
# ---------------------------------------------------------------------------

@router.get("/deals/history")
async def list_deal_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _rl: None = Depends(_deal_read_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            total_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM v_offer_summary_v1
                WHERE (seller_id = $1 OR buyer_id = $1)
                  AND status IN ('completed', 'cancelled', 'declined', 'expired')
                """,
                user_id,
            )

            rows = await conn.fetch(
                """
                SELECT * FROM v_offer_summary_v1
                WHERE (seller_id = $1 OR buyer_id = $1)
                  AND status IN ('completed', 'cancelled', 'declined', 'expired')
                ORDER BY updated_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )

        return {
            "offers": [_row_to_offer_summary(dict(r), user_id) for r in rows],
            "total_count": total_count or 0,
        }
    except Exception:
        logger.exception("list_deal_history failed")
        raise error_response(500, "Failed to list deal history", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /deals/{offer_id} — Offer detail with events
# ---------------------------------------------------------------------------

@router.get("/deals/{offer_id}")
async def get_offer_detail(
    offer_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_read_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    offer_id = _validate_uuid(offer_id, "offer_id")

    try:
        async with pool.acquire() as conn:
            # Get offer summary
            row = await conn.fetchrow(
                """
                SELECT * FROM v_offer_summary_v1
                WHERE offer_id = $1
                  AND (seller_id = $2 OR buyer_id = $2)
                """,
                offer_id, user_id,
            )

            if not row:
                raise error_response(404, "Offer not found", code=ErrorCode.NOT_FOUND)

            # Get events
            events = await conn.fetch(
                """
                SELECT id, offer_id, actor_id, event_type, price,
                       message, metadata, created_at
                FROM offer_events
                WHERE offer_id = $1
                ORDER BY created_at ASC
                """,
                offer_id,
            )

        offer_data = _row_to_offer_summary(dict(row), user_id)
        events_data = [
            {
                "id": str(e["id"]),
                "offer_id": str(e["offer_id"]),
                "actor_id": str(e["actor_id"]),
                "event_type": e["event_type"],
                "price": float(e["price"]) if e["price"] else None,
                "message": e["message"],
                "metadata": e["metadata"] or {},
                "created_at": e["created_at"].isoformat() if e["created_at"] else None,
            }
            for e in events
        ]

        return {"offer": offer_data, "events": events_data}
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise exc
        logger.exception("get_offer_detail failed")
        raise error_response(500, "Failed to get offer detail", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /deals/{offer_id}/evidence — Dossier snapshot
# ---------------------------------------------------------------------------

@router.get("/deals/{offer_id}/evidence")
async def get_offer_evidence(
    offer_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_read_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    offer_id = _validate_uuid(offer_id, "offer_id")

    try:
        async with pool.acquire() as conn:
            # Verify access
            access = await conn.fetchval(
                "SELECT 1 FROM offers WHERE id = $1 AND (seller_id = $2 OR buyer_id = $2)",
                offer_id, user_id,
            )
            if not access:
                raise error_response(404, "Offer not found", code=ErrorCode.NOT_FOUND)

            row = await conn.fetchrow(
                """
                SELECT id, offer_id, dossier_json, market_comps, created_at
                FROM offer_evidence
                WHERE offer_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                offer_id,
            )

        if not row:
            return {"evidence": None}

        return {
            "evidence": {
                "id": str(row["id"]),
                "offer_id": str(row["offer_id"]),
                "dossier_json": row["dossier_json"],
                "market_comps": row["market_comps"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        }
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise exc
        logger.exception("get_offer_evidence failed")
        raise error_response(500, "Failed to get evidence", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /deals/reputation/{user_id} — User reputation
# ---------------------------------------------------------------------------

@router.get("/deals/reputation/{target_user_id}")
async def get_user_reputation(
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_read_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    target_user_id = _validate_uuid(target_user_id, "user_id")

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM v_user_reputation_v1 WHERE user_id = $1",
                target_user_id,
            )

        if not row:
            return {
                "user_id": target_user_id,
                "avg_stars": 0,
                "total_ratings": 0,
                "completed_deals": 0,
            }

        return {
            "user_id": str(row["user_id"]),
            "avg_stars": float(row["avg_stars"]) if row["avg_stars"] else 0,
            "total_ratings": int(row["total_ratings"]) if row["total_ratings"] else 0,
            "completed_deals": int(row["completed_deals"]) if row["completed_deals"] else 0,
        }
    except Exception:
        logger.exception("get_user_reputation failed")
        raise error_response(500, "Failed to get reputation", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# PUT /items/{item_id}/for-sale — Toggle for_sale + set asking price
# ---------------------------------------------------------------------------

@router.put("/items/{item_id}/for-sale")
async def toggle_for_sale(
    item_id: str,
    body: ToggleForSaleRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_action_limit),
):
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    item_id = _validate_uuid(item_id, "item_id")

    try:
        async with pool.acquire() as conn:
            # Verify ownership
            owner = await conn.fetchval(
                "SELECT user_id::text FROM items WHERE id = $1::uuid",
                item_id,
            )
            if not owner:
                raise error_response(404, "Item not found", code=ErrorCode.NOT_FOUND)
            if owner != user_id:
                raise error_response(403, "Not the item owner", code=ErrorCode.FORBIDDEN)

            # Update
            await conn.execute(
                """
                UPDATE items
                SET for_sale = $1,
                    asking_price = $2,
                    asking_currency = COALESCE($3, 'EUR'),
                    updated_at = now()
                WHERE id = $4::uuid
                """,
                body.for_sale,
                body.asking_price if body.for_sale else None,
                body.currency,
                item_id,
            )

        return {"item_id": item_id, "for_sale": body.for_sale, "asking_price": body.asking_price}
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise exc
        logger.exception("toggle_for_sale failed")
        raise error_response(500, "Failed to toggle for-sale", code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Helper: convert DB row to offer summary dict
# ---------------------------------------------------------------------------

def _row_to_offer_summary(row: dict, current_user_id: str) -> dict:
    """Convert a v_offer_summary_v1 row to API response dict."""
    seller_id = str(row.get("seller_id", ""))
    buyer_id = str(row.get("buyer_id", ""))
    is_seller = current_user_id == seller_id

    # Other party = the one that is NOT the current user
    other_user_id = buyer_id if is_seller else seller_id
    other_user_name = (row.get("buyer_name") if is_seller else row.get("seller_name")) or "Unknown"
    other_user_avatar = (row.get("buyer_avatar_url") if is_seller else row.get("seller_avatar_url"))

    return {
        "id": str(row.get("offer_id", "")),
        "item_id": str(row.get("item_id", "")),
        "item_title": row.get("item_title", "Untitled"),
        "item_image_url": row.get("item_image_url"),
        "seller_id": seller_id,
        "buyer_id": buyer_id,
        "status": row.get("status", "proposed"),
        "current_price": float(row["current_price"]) if row.get("current_price") else 0,
        "currency": row.get("currency", "EUR"),
        "dm_thread_id": str(row.get("dm_thread_id", "")),
        "other_user_id": other_user_id,
        "other_user_name": other_user_name,
        "other_user_avatar_url": other_user_avatar,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
        "expires_at": row["expires_at"].isoformat() if row.get("expires_at") else None,
    }
