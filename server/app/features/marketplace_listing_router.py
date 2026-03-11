"""
Marketplace Listing Router — Multi-marketplace selling system.

Allows users to list collectibles for sale on external marketplaces
(eBay, Mercari, Cardmarket, StockX, BrickLink) from within CollectAI,
manage connected marketplace accounts, track listings, record sales,
and calculate estimated fees.

Endpoints:
  Accounts:
  - GET    /marketplace/listings/accounts              — list connected accounts
  - POST   /marketplace/listings/accounts              — connect a new account
  - DELETE /marketplace/listings/accounts/{account_id} — disconnect account

  Listings:
  - GET    /marketplace/listings                       — list user's listings
  - POST   /marketplace/listings                       — create a listing
  - GET    /marketplace/listings/{listing_id}          — listing detail
  - PATCH  /marketplace/listings/{listing_id}          — update listing
  - DELETE /marketplace/listings/{listing_id}          — delete / delist
  - POST   /marketplace/listings/{listing_id}/publish  — publish draft

  Sales:
  - GET    /marketplace/listings/sales                       — list sales
  - POST   /marketplace/listings/sales/{listing_id}/record   — record a sale

  Fees:
  - GET    /marketplace/listings/fees                  — all fee schedules
  - POST   /marketplace/listings/fees/calculate        — estimate fees + net
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.features.pagination import pagination_params
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/marketplace/listings", tags=["Marketplace Listings"])
logger = logging.getLogger(__name__)

_listing_write_limit = per_user_rate_limit(30, window_seconds=60, scope="marketplace_listing_write")
_listing_read_limit = per_user_rate_limit(60, window_seconds=60, scope="marketplace_listing_read")

# ---------------------------------------------------------------------------
# Valid marketplace identifiers
# ---------------------------------------------------------------------------
VALID_MARKETPLACES = {"collectai", "ebay", "mercari", "cardmarket", "stockx", "bricklink", "tcgplayer", "discogs"}

VALID_LISTING_STATUSES = {"draft", "active", "sold", "expired", "delisted", "error"}
VALID_LISTING_FORMATS = {"fixed_price", "auction", "best_offer"}
VALID_SHIPPING_METHODS = {"standard", "express", "local_pickup", "free"}
VALID_CONDITION_LABELS = {"New", "Like New", "Very Good", "Good", "Acceptable"}
VALID_SALE_STATUSES = {"pending", "paid", "shipped", "delivered", "completed", "disputed", "refunded"}


# ---------------------------------------------------------------------------
# UUID validation helper
# ---------------------------------------------------------------------------

def _validate_uuid(value: str, label: str = "id") -> str:
    """Validate a UUID string, raise 400 on invalid."""
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        raise error_response(400, f"Invalid UUID for {label}: {value}", code=ErrorCode.INVALID_UUID)


# ---------------------------------------------------------------------------
# Pydantic models — Accounts
# ---------------------------------------------------------------------------

class AccountResponse(BaseModel):
    id: str
    user_id: str
    marketplace_id: str
    seller_name: Optional[str] = None
    seller_id: Optional[str] = None
    scopes: Optional[List[str]] = None
    is_active: bool = True
    connected_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None


class AccountCreate(BaseModel):
    marketplace_id: str = Field(..., max_length=32, description="One of: ebay, mercari, cardmarket, stockx, bricklink, etc.")
    seller_name: Optional[str] = Field(None, max_length=255)
    seller_id: Optional[str] = Field(None, max_length=255)
    oauth_token_enc: Optional[str] = Field(None, description="Encrypted OAuth access token")
    refresh_token_enc: Optional[str] = Field(None, description="Encrypted OAuth refresh token")
    token_expires_at: Optional[datetime] = None
    scopes: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Pydantic models — Listings
# ---------------------------------------------------------------------------

class ListingResponse(BaseModel):
    id: str
    user_id: str
    item_id: str
    account_id: Optional[str] = None
    marketplace_id: str
    external_listing_id: Optional[str] = None
    listing_url: Optional[str] = None
    listing_title: str
    listing_description: Optional[str] = None
    price: float
    currency: str = "EUR"
    original_price: Optional[float] = None
    format: str = "fixed_price"
    auction_duration_days: Optional[int] = None
    auction_start_price: Optional[float] = None
    buy_it_now_price: Optional[float] = None
    quantity: int = 1
    condition_label: Optional[str] = None
    condition_notes: Optional[str] = None
    shipping_method: Optional[str] = "standard"
    shipping_cost: Optional[float] = 0
    ships_international: bool = False
    returns_accepted: bool = False
    returns_days: Optional[int] = 14
    status: str = "draft"
    status_message: Optional[str] = None
    views_count: int = 0
    watchers_count: int = 0
    offers_count: int = 0
    estimated_fees: Optional[float] = None
    estimated_net: Optional[float] = None
    fee_percentage: Optional[float] = None
    listed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    sold_at: Optional[datetime] = None
    synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ListingCreate(BaseModel):
    item_id: str = Field(..., description="UUID of the item to list")
    account_id: Optional[str] = Field(None, description="UUID of the connected marketplace account")
    marketplace_id: str = Field(..., max_length=32)
    listing_title: str = Field(..., min_length=1, max_length=500)
    listing_description: Optional[str] = Field(None, max_length=5000)
    price: float = Field(..., gt=0)
    currency: str = Field(default="EUR", max_length=3, pattern=r"^[A-Z]{3}$")
    format: str = Field(default="fixed_price")
    auction_duration_days: Optional[int] = None
    auction_start_price: Optional[float] = None
    buy_it_now_price: Optional[float] = None
    quantity: int = Field(default=1, ge=1)
    condition_label: Optional[str] = None
    condition_notes: Optional[str] = Field(None, max_length=1000)
    shipping_method: Optional[str] = "standard"
    shipping_cost: Optional[float] = Field(default=0, ge=0)
    ships_international: bool = False
    returns_accepted: bool = False
    returns_days: Optional[int] = Field(default=14, ge=0)
    status: str = Field(default="draft", description="'draft' or 'active'")


class ListingUpdate(BaseModel):
    listing_title: Optional[str] = Field(None, min_length=1, max_length=500)
    listing_description: Optional[str] = Field(None, max_length=5000)
    price: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=3, pattern=r"^[A-Z]{3}$")
    format: Optional[str] = None
    auction_duration_days: Optional[int] = None
    auction_start_price: Optional[float] = None
    buy_it_now_price: Optional[float] = None
    quantity: Optional[int] = Field(None, ge=0)
    condition_label: Optional[str] = None
    condition_notes: Optional[str] = Field(None, max_length=1000)
    shipping_method: Optional[str] = None
    shipping_cost: Optional[float] = Field(None, ge=0)
    ships_international: Optional[bool] = None
    returns_accepted: Optional[bool] = None
    returns_days: Optional[int] = Field(None, ge=0)
    status: Optional[str] = None
    status_message: Optional[str] = None
    external_listing_id: Optional[str] = None
    listing_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Pydantic models — Sales
# ---------------------------------------------------------------------------

class SaleResponse(BaseModel):
    id: str
    listing_id: str
    user_id: str
    buyer_name: Optional[str] = None
    buyer_marketplace_id: Optional[str] = None
    buyer_rating: Optional[float] = None
    sale_price: float
    currency: str = "EUR"
    shipping_cost_actual: Optional[float] = 0
    platform_fee: Optional[float] = 0
    payment_processing_fee: Optional[float] = 0
    net_proceeds: float
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    status: str = "pending"
    sold_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SaleRecord(BaseModel):
    sale_price: float = Field(..., gt=0)
    currency: str = Field(default="EUR", max_length=3, pattern=r"^[A-Z]{3}$")
    buyer_name: Optional[str] = Field(None, max_length=255)
    buyer_marketplace_id: Optional[str] = Field(None, max_length=255)
    buyer_rating: Optional[float] = Field(None, ge=0, le=5)
    shipping_cost_actual: Optional[float] = Field(default=0, ge=0)
    platform_fee: Optional[float] = Field(default=0, ge=0)
    payment_processing_fee: Optional[float] = Field(default=0, ge=0)
    tracking_number: Optional[str] = Field(None, max_length=255)
    carrier: Optional[str] = Field(None, max_length=100)


# ---------------------------------------------------------------------------
# Pydantic models — Fees
# ---------------------------------------------------------------------------

class FeeScheduleResponse(BaseModel):
    marketplace_id: str
    display_name: str
    base_fee_pct: float
    payment_processing_pct: float
    fixed_fee: float
    currency: str = "EUR"
    min_fee: Optional[float] = 0
    max_fee: Optional[float] = None
    notes: Optional[str] = None


class FeeCalculateRequest(BaseModel):
    marketplace_id: str = Field(..., max_length=32)
    price: float = Field(..., gt=0)
    shipping_cost: float = Field(default=0, ge=0)


class FeeCalculateResponse(BaseModel):
    marketplace_id: str
    price: float
    base_fee: float
    payment_processing_fee: float
    fixed_fee: float
    total_fees: float
    shipping_cost: float
    estimated_net: float


# ---------------------------------------------------------------------------
# Pydantic models — List responses with total_count
# ---------------------------------------------------------------------------

class ListingsListResponse(BaseModel):
    listings: List[ListingResponse]
    total_count: int


class SalesListResponse(BaseModel):
    sales: List[SaleResponse]
    total_count: int


# ===========================================================================================
# ACCOUNTS endpoints
# ===========================================================================================

@router.get("/accounts", response_model=List[AccountResponse], summary="List connected accounts")
async def list_accounts(
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_listing_read_limit),
):
    """List all connected marketplace accounts for the current user."""
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, marketplace_id, seller_name, seller_id,
                       scopes, is_active, connected_at, last_sync_at
                FROM marketplace_accounts
                WHERE user_id = $1
                ORDER BY connected_at DESC
                """,
                user_id,
            )
            return [
                AccountResponse(
                    id=str(r["id"]),
                    user_id=str(r["user_id"]),
                    marketplace_id=r["marketplace_id"],
                    seller_name=r["seller_name"],
                    seller_id=r["seller_id"],
                    scopes=r["scopes"],
                    is_active=r["is_active"],
                    connected_at=r["connected_at"],
                    last_sync_at=r["last_sync_at"],
                )
                for r in rows
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error listing accounts: %s", e)
        raise error_response(500, "Failed to list accounts", code=ErrorCode.DB_ERROR)


# Rate limit: accounts — connect (5/min per user)
@router.post("/accounts", response_model=AccountResponse, status_code=201, summary="Connect marketplace account")
async def connect_account(
    payload: AccountCreate,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_listing_write_limit),
):
    """Connect a new marketplace account (store OAuth credentials)."""
    if payload.marketplace_id not in VALID_MARKETPLACES:
        raise error_response(
            400,
            f"Invalid marketplace_id: {payload.marketplace_id}. Must be one of: {', '.join(sorted(VALID_MARKETPLACES))}",
            code=ErrorCode.VALIDATION_ERROR,
        )

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            # Check for existing connection
            existing = await conn.fetchrow(
                """
                SELECT id FROM marketplace_accounts
                WHERE user_id = $1 AND marketplace_id = $2
                """,
                user_id, payload.marketplace_id,
            )
            if existing:
                raise error_response(
                    409,
                    f"Already connected to {payload.marketplace_id}",
                    code=ErrorCode.ALREADY_EXISTS,
                )

            now = datetime.now(timezone.utc)
            row = await conn.fetchrow(
                """
                INSERT INTO marketplace_accounts
                    (user_id, marketplace_id, seller_name, seller_id,
                     oauth_token_enc, refresh_token_enc, token_expires_at,
                     scopes, connected_at, is_active, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, true, $9, $9)
                RETURNING id, user_id, marketplace_id, seller_name, seller_id,
                          scopes, is_active, connected_at, last_sync_at
                """,
                user_id, payload.marketplace_id, payload.seller_name,
                payload.seller_id, payload.oauth_token_enc,
                payload.refresh_token_enc, payload.token_expires_at,
                payload.scopes, now,
            )
            logger.info(
                "[marketplace-listings] Account connected: user=%s marketplace=%s",
                user_id, payload.marketplace_id,
            )
            return AccountResponse(
                id=str(row["id"]),
                user_id=str(row["user_id"]),
                marketplace_id=row["marketplace_id"],
                seller_name=row["seller_name"],
                seller_id=row["seller_id"],
                scopes=row["scopes"],
                is_active=row["is_active"],
                connected_at=row["connected_at"],
                last_sync_at=row["last_sync_at"],
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error connecting account: %s", e)
        raise error_response(500, "Failed to connect account", code=ErrorCode.DB_ERROR)


@router.delete("/accounts/{account_id}", status_code=200, summary="Disconnect marketplace account")
async def disconnect_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_listing_write_limit),
):
    """Disconnect (delete) a marketplace account."""
    account_id = _validate_uuid(account_id, "account_id")

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM marketplace_accounts WHERE id = $1 AND user_id = $2",
                account_id, user_id,
            )
            if result.endswith(" 0"):
                raise error_response(404, "Account not found", code=ErrorCode.NOT_FOUND)

            logger.info(
                "[marketplace-listings] Account disconnected: user=%s account=%s",
                user_id, account_id,
            )
            return {"ok": True, "deleted": account_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error disconnecting account: %s", e)
        raise error_response(500, "Failed to disconnect account", code=ErrorCode.DB_ERROR)


# ===========================================================================================
# LISTINGS endpoints
# ===========================================================================================

def _row_to_listing(r: dict) -> ListingResponse:
    """Convert a database row to a ListingResponse."""
    return ListingResponse(
        id=str(r["id"]),
        user_id=str(r["user_id"]),
        item_id=str(r["item_id"]),
        account_id=str(r["account_id"]) if r.get("account_id") else None,
        marketplace_id=r["marketplace_id"],
        external_listing_id=r.get("external_listing_id"),
        listing_url=r.get("listing_url"),
        listing_title=r["listing_title"],
        listing_description=r.get("listing_description"),
        price=float(r["price"]),
        currency=r.get("currency", "EUR"),
        original_price=float(r["original_price"]) if r.get("original_price") else None,
        format=r.get("format", "fixed_price"),
        auction_duration_days=r.get("auction_duration_days"),
        auction_start_price=float(r["auction_start_price"]) if r.get("auction_start_price") else None,
        buy_it_now_price=float(r["buy_it_now_price"]) if r.get("buy_it_now_price") else None,
        quantity=r.get("quantity", 1),
        condition_label=r.get("condition_label"),
        condition_notes=r.get("condition_notes"),
        shipping_method=r.get("shipping_method", "standard"),
        shipping_cost=float(r["shipping_cost"]) if r.get("shipping_cost") is not None else 0,
        ships_international=r.get("ships_international", False),
        returns_accepted=r.get("returns_accepted", False),
        returns_days=r.get("returns_days", 14),
        status=r.get("status", "draft"),
        status_message=r.get("status_message"),
        views_count=r.get("views_count", 0),
        watchers_count=r.get("watchers_count", 0),
        offers_count=r.get("offers_count", 0),
        estimated_fees=float(r["estimated_fees"]) if r.get("estimated_fees") is not None else None,
        estimated_net=float(r["estimated_net"]) if r.get("estimated_net") is not None else None,
        fee_percentage=float(r["fee_percentage"]) if r.get("fee_percentage") is not None else None,
        listed_at=r.get("listed_at"),
        expires_at=r.get("expires_at"),
        sold_at=r.get("sold_at"),
        synced_at=r.get("synced_at"),
        created_at=r.get("created_at"),
        updated_at=r.get("updated_at"),
    )


@router.get("", response_model=ListingsListResponse, summary="List my listings")
async def list_listings(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
    _rl: None = Depends(_listing_read_limit),
    status: Optional[str] = Query(None, description="Filter by status: draft, active, sold, expired, delisted, error"),
    marketplace_id: Optional[str] = Query(None, description="Filter by marketplace"),
):
    """List the current user's marketplace listings with optional filters and pagination."""
    limit, offset = pagination

    if status and status not in VALID_LISTING_STATUSES:
        raise error_response(
            400,
            f"Invalid status filter: {status}. Must be one of: {', '.join(sorted(VALID_LISTING_STATUSES))}",
            code=ErrorCode.VALIDATION_ERROR,
        )
    if marketplace_id and marketplace_id not in VALID_MARKETPLACES:
        raise error_response(
            400,
            f"Invalid marketplace_id filter: {marketplace_id}",
            code=ErrorCode.VALIDATION_ERROR,
        )

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            # Build WHERE clause dynamically
            conditions = ["user_id = $1"]
            params: list = [user_id]
            idx = 2

            if status:
                conditions.append(f"status = ${idx}")
                params.append(status)
                idx += 1

            if marketplace_id:
                conditions.append(f"marketplace_id = ${idx}")
                params.append(marketplace_id)
                idx += 1

            where_clause = " AND ".join(conditions)

            # Total count
            count_row = await conn.fetchrow(
                f"SELECT count(*) AS cnt FROM marketplace_listings WHERE {where_clause}",
                *params,
            )
            total_count = count_row["cnt"] if count_row else 0

            # Fetch page
            params.append(limit)
            params.append(offset)
            rows = await conn.fetch(
                f"""
                SELECT *
                FROM marketplace_listings
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx + 1}
                """,
                *params,
            )
            return ListingsListResponse(
                listings=[_row_to_listing(r) for r in rows],
                total_count=total_count,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error listing listings: %s", e)
        raise error_response(500, "Failed to list listings", code=ErrorCode.DB_ERROR)


# Rate limit: listings — create (10/min per user)
@router.post("", response_model=ListingResponse, status_code=201, summary="Create a listing")
async def create_listing(
    payload: ListingCreate,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_listing_write_limit),
):
    """Create a new listing (draft or active)."""
    item_id = _validate_uuid(payload.item_id, "item_id")
    if payload.account_id:
        _validate_uuid(payload.account_id, "account_id")

    if payload.marketplace_id not in VALID_MARKETPLACES:
        raise error_response(
            400,
            f"Invalid marketplace_id: {payload.marketplace_id}",
            code=ErrorCode.VALIDATION_ERROR,
        )
    if payload.format not in VALID_LISTING_FORMATS:
        raise error_response(
            400,
            f"Invalid format: {payload.format}. Must be one of: {', '.join(sorted(VALID_LISTING_FORMATS))}",
            code=ErrorCode.VALIDATION_ERROR,
        )
    if payload.status not in ("draft", "active"):
        raise error_response(
            400,
            "Status must be 'draft' or 'active' when creating a listing",
            code=ErrorCode.VALIDATION_ERROR,
        )
    if payload.condition_label and payload.condition_label not in VALID_CONDITION_LABELS:
        raise error_response(
            400,
            f"Invalid condition_label: {payload.condition_label}",
            code=ErrorCode.VALIDATION_ERROR,
        )
    if payload.shipping_method and payload.shipping_method not in VALID_SHIPPING_METHODS:
        raise error_response(
            400,
            f"Invalid shipping_method: {payload.shipping_method}",
            code=ErrorCode.VALIDATION_ERROR,
        )

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    now = datetime.now(timezone.utc)
    listed_at = now if payload.status == "active" else None

    try:
        async with pool.acquire() as conn:
            # Verify the item belongs to the user
            item_row = await conn.fetchrow(
                "SELECT id FROM items WHERE id = $1 AND user_id = $2",
                item_id, user_id,
            )
            if not item_row:
                raise error_response(404, "Item not found or not owned by user", code=ErrorCode.NOT_FOUND)

            # If account_id provided, verify it belongs to the user
            if payload.account_id:
                acct_row = await conn.fetchrow(
                    "SELECT id FROM marketplace_accounts WHERE id = $1 AND user_id = $2",
                    payload.account_id, user_id,
                )
                if not acct_row:
                    raise error_response(404, "Marketplace account not found", code=ErrorCode.NOT_FOUND)

            row = await conn.fetchrow(
                """
                INSERT INTO marketplace_listings
                    (user_id, item_id, account_id, marketplace_id,
                     listing_title, listing_description,
                     price, currency, format,
                     auction_duration_days, auction_start_price, buy_it_now_price,
                     quantity, condition_label, condition_notes,
                     shipping_method, shipping_cost, ships_international,
                     returns_accepted, returns_days,
                     status, listed_at, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                        $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $23)
                RETURNING *
                """,
                user_id, item_id, payload.account_id, payload.marketplace_id,
                payload.listing_title, payload.listing_description,
                payload.price, payload.currency, payload.format,
                payload.auction_duration_days, payload.auction_start_price,
                payload.buy_it_now_price,
                payload.quantity, payload.condition_label, payload.condition_notes,
                payload.shipping_method, payload.shipping_cost, payload.ships_international,
                payload.returns_accepted, payload.returns_days,
                payload.status, listed_at, now,
            )
            logger.info(
                "[marketplace-listings] Listing created: user=%s item=%s marketplace=%s status=%s",
                user_id, item_id, payload.marketplace_id, payload.status,
            )
            return _row_to_listing(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error creating listing: %s", e)
        raise error_response(500, "Failed to create listing", code=ErrorCode.DB_ERROR)


@router.get("/{listing_id}", response_model=ListingResponse, summary="Get listing detail")
async def get_listing(
    listing_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_listing_read_limit),
):
    """Get a single listing's full detail."""
    listing_id = _validate_uuid(listing_id, "listing_id")

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM marketplace_listings WHERE id = $1 AND user_id = $2",
                listing_id, user_id,
            )
            if not row:
                raise error_response(404, "Listing not found", code=ErrorCode.NOT_FOUND)
            return _row_to_listing(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error getting listing: %s", e)
        raise error_response(500, "Failed to get listing", code=ErrorCode.DB_ERROR)


@router.patch("/{listing_id}", response_model=ListingResponse, summary="Update a listing")
async def update_listing(
    listing_id: str,
    payload: ListingUpdate,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_listing_write_limit),
):
    """Update a listing's fields (price, status, description, etc.)."""
    listing_id = _validate_uuid(listing_id, "listing_id")

    # Validate enum fields if provided
    if payload.format and payload.format not in VALID_LISTING_FORMATS:
        raise error_response(400, f"Invalid format: {payload.format}", code=ErrorCode.VALIDATION_ERROR)
    if payload.status and payload.status not in VALID_LISTING_STATUSES:
        raise error_response(400, f"Invalid status: {payload.status}", code=ErrorCode.VALIDATION_ERROR)
    if payload.condition_label and payload.condition_label not in VALID_CONDITION_LABELS:
        raise error_response(400, f"Invalid condition_label: {payload.condition_label}", code=ErrorCode.VALIDATION_ERROR)
    if payload.shipping_method and payload.shipping_method not in VALID_SHIPPING_METHODS:
        raise error_response(400, f"Invalid shipping_method: {payload.shipping_method}", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    # Build SET clause from non-None fields
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise error_response(400, "No fields to update", code=ErrorCode.VALIDATION_ERROR)

    updates["updated_at"] = datetime.now(timezone.utc)

    # If price changes, store the old price as original_price
    set_parts = []
    params: list = []
    idx = 1
    for key, value in updates.items():
        set_parts.append(f"{key} = ${idx}")
        params.append(value)
        idx += 1

    params.append(listing_id)
    params.append(user_id)

    try:
        async with pool.acquire() as conn:
            # If updating price, capture original_price first
            if payload.price is not None:
                current = await conn.fetchrow(
                    "SELECT price, original_price FROM marketplace_listings WHERE id = $1 AND user_id = $2",
                    listing_id, user_id,
                )
                if current and current["original_price"] is None:
                    # Save the first original price
                    set_parts.append(f"original_price = ${idx}")
                    params.insert(-2, float(current["price"]))
                    idx += 1

            row = await conn.fetchrow(
                f"""
                UPDATE marketplace_listings
                SET {', '.join(set_parts)}
                WHERE id = ${idx} AND user_id = ${idx + 1}
                RETURNING *
                """,
                *params,
            )
            if not row:
                raise error_response(404, "Listing not found", code=ErrorCode.NOT_FOUND)

            logger.info("[marketplace-listings] Listing updated: listing=%s user=%s", listing_id, user_id)
            return _row_to_listing(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error updating listing: %s", e)
        raise error_response(500, "Failed to update listing", code=ErrorCode.DB_ERROR)


@router.delete("/{listing_id}", status_code=200, summary="Delist a listing")
async def delete_listing(
    listing_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_listing_write_limit),
):
    """Delete (delist) a listing. Sets status to 'delisted' rather than hard-deleting."""
    listing_id = _validate_uuid(listing_id, "listing_id")

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            now = datetime.now(timezone.utc)
            result = await conn.execute(
                """
                UPDATE marketplace_listings
                SET status = 'delisted', updated_at = $3
                WHERE id = $1 AND user_id = $2 AND status NOT IN ('sold', 'delisted')
                """,
                listing_id, user_id, now,
            )
            if result.endswith(" 0"):
                # Check if it exists at all
                exists = await conn.fetchrow(
                    "SELECT id, status FROM marketplace_listings WHERE id = $1 AND user_id = $2",
                    listing_id, user_id,
                )
                if not exists:
                    raise error_response(404, "Listing not found", code=ErrorCode.NOT_FOUND)
                raise error_response(
                    409,
                    f"Cannot delist a listing with status '{exists['status']}'",
                    code=ErrorCode.CONFLICT,
                )

            logger.info("[marketplace-listings] Listing delisted: listing=%s user=%s", listing_id, user_id)
            return {"ok": True, "listing_id": listing_id, "status": "delisted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error delisting: %s", e)
        raise error_response(500, "Failed to delist listing", code=ErrorCode.DB_ERROR)


# Rate limit: publish (5/min per user)
@router.post("/{listing_id}/publish", response_model=ListingResponse, summary="Publish a draft listing")
async def publish_listing(
    listing_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_listing_write_limit),
):
    """Publish a draft listing — sets status to 'active' and records listed_at."""
    listing_id = _validate_uuid(listing_id, "listing_id")

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            now = datetime.now(timezone.utc)
            row = await conn.fetchrow(
                """
                UPDATE marketplace_listings
                SET status = 'active', listed_at = $3, updated_at = $3
                WHERE id = $1 AND user_id = $2 AND status = 'draft'
                RETURNING *
                """,
                listing_id, user_id, now,
            )
            if not row:
                # Check why it failed
                exists = await conn.fetchrow(
                    "SELECT id, status FROM marketplace_listings WHERE id = $1 AND user_id = $2",
                    listing_id, user_id,
                )
                if not exists:
                    raise error_response(404, "Listing not found", code=ErrorCode.NOT_FOUND)
                raise error_response(
                    409,
                    f"Cannot publish a listing with status '{exists['status']}' (must be 'draft')",
                    code=ErrorCode.CONFLICT,
                )

            logger.info("[marketplace-listings] Listing published: listing=%s user=%s", listing_id, user_id)
            return _row_to_listing(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error publishing listing: %s", e)
        raise error_response(500, "Failed to publish listing", code=ErrorCode.DB_ERROR)


# ===========================================================================================
# SALES endpoints
# ===========================================================================================

@router.get("/sales", response_model=SalesListResponse, summary="List completed sales")
async def list_sales(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
    _rl: None = Depends(_listing_read_limit),
):
    """List the current user's completed sales with pagination."""
    limit, offset = pagination

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                "SELECT count(*) AS cnt FROM marketplace_sales WHERE user_id = $1",
                user_id,
            )
            total_count = count_row["cnt"] if count_row else 0

            rows = await conn.fetch(
                """
                SELECT *
                FROM marketplace_sales
                WHERE user_id = $1
                ORDER BY sold_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id, limit, offset,
            )
            sales = [
                SaleResponse(
                    id=str(r["id"]),
                    listing_id=str(r["listing_id"]),
                    user_id=str(r["user_id"]),
                    buyer_name=r.get("buyer_name"),
                    buyer_marketplace_id=r.get("buyer_marketplace_id"),
                    buyer_rating=float(r["buyer_rating"]) if r.get("buyer_rating") is not None else None,
                    sale_price=float(r["sale_price"]),
                    currency=r.get("currency", "EUR"),
                    shipping_cost_actual=float(r["shipping_cost_actual"]) if r.get("shipping_cost_actual") is not None else 0,
                    platform_fee=float(r["platform_fee"]) if r.get("platform_fee") is not None else 0,
                    payment_processing_fee=float(r["payment_processing_fee"]) if r.get("payment_processing_fee") is not None else 0,
                    net_proceeds=float(r["net_proceeds"]),
                    tracking_number=r.get("tracking_number"),
                    carrier=r.get("carrier"),
                    shipped_at=r.get("shipped_at"),
                    delivered_at=r.get("delivered_at"),
                    status=r.get("status", "pending"),
                    sold_at=r.get("sold_at"),
                    created_at=r.get("created_at"),
                    updated_at=r.get("updated_at"),
                )
                for r in rows
            ]
            return SalesListResponse(sales=sales, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error listing sales: %s", e)
        raise error_response(500, "Failed to list sales", code=ErrorCode.DB_ERROR)


# Rate limit: record sale (10/min per user)
@router.post("/sales/{listing_id}/record", response_model=SaleResponse, status_code=201, summary="Record a completed sale")
async def record_sale(
    listing_id: str,
    payload: SaleRecord,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_listing_write_limit),
):
    """Record a completed sale for a listing. Marks the listing as 'sold'."""
    listing_id = _validate_uuid(listing_id, "listing_id")

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    # Calculate net proceeds
    total_fees = (payload.platform_fee or 0) + (payload.payment_processing_fee or 0)
    net_proceeds = payload.sale_price - total_fees - (payload.shipping_cost_actual or 0)

    now = datetime.now(timezone.utc)

    try:
        async with pool.acquire() as conn:
            # Verify listing exists and belongs to user
            listing_row = await conn.fetchrow(
                "SELECT id, status FROM marketplace_listings WHERE id = $1 AND user_id = $2",
                listing_id, user_id,
            )
            if not listing_row:
                raise error_response(404, "Listing not found", code=ErrorCode.NOT_FOUND)
            if listing_row["status"] == "sold":
                raise error_response(409, "Sale already recorded for this listing", code=ErrorCode.CONFLICT)

            # Insert sale record
            sale_row = await conn.fetchrow(
                """
                INSERT INTO marketplace_sales
                    (listing_id, user_id, buyer_name, buyer_marketplace_id,
                     buyer_rating, sale_price, currency,
                     shipping_cost_actual, platform_fee, payment_processing_fee,
                     net_proceeds, tracking_number, carrier,
                     status, sold_at, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                        'pending', $14, $14, $14)
                RETURNING *
                """,
                listing_id, user_id, payload.buyer_name,
                payload.buyer_marketplace_id, payload.buyer_rating,
                payload.sale_price, payload.currency,
                payload.shipping_cost_actual or 0, payload.platform_fee or 0,
                payload.payment_processing_fee or 0,
                net_proceeds, payload.tracking_number, payload.carrier,
                now,
            )

            # Mark listing as sold
            await conn.execute(
                """
                UPDATE marketplace_listings
                SET status = 'sold', sold_at = $3, updated_at = $3
                WHERE id = $1 AND user_id = $2
                """,
                listing_id, user_id, now,
            )

            logger.info(
                "[marketplace-listings] Sale recorded: listing=%s user=%s net=%.2f",
                listing_id, user_id, net_proceeds,
            )
            return SaleResponse(
                id=str(sale_row["id"]),
                listing_id=str(sale_row["listing_id"]),
                user_id=str(sale_row["user_id"]),
                buyer_name=sale_row.get("buyer_name"),
                buyer_marketplace_id=sale_row.get("buyer_marketplace_id"),
                buyer_rating=float(sale_row["buyer_rating"]) if sale_row.get("buyer_rating") is not None else None,
                sale_price=float(sale_row["sale_price"]),
                currency=sale_row.get("currency", "EUR"),
                shipping_cost_actual=float(sale_row["shipping_cost_actual"]) if sale_row.get("shipping_cost_actual") is not None else 0,
                platform_fee=float(sale_row["platform_fee"]) if sale_row.get("platform_fee") is not None else 0,
                payment_processing_fee=float(sale_row["payment_processing_fee"]) if sale_row.get("payment_processing_fee") is not None else 0,
                net_proceeds=float(sale_row["net_proceeds"]),
                tracking_number=sale_row.get("tracking_number"),
                carrier=sale_row.get("carrier"),
                shipped_at=sale_row.get("shipped_at"),
                delivered_at=sale_row.get("delivered_at"),
                status=sale_row.get("status", "pending"),
                sold_at=sale_row.get("sold_at"),
                created_at=sale_row.get("created_at"),
                updated_at=sale_row.get("updated_at"),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error recording sale: %s", e)
        raise error_response(500, "Failed to record sale", code=ErrorCode.DB_ERROR)


# ===========================================================================================
# FEES endpoints
# ===========================================================================================

@router.get("/fees", response_model=List[FeeScheduleResponse], summary="Get fee schedules")
async def list_fee_schedules() -> list[FeeScheduleResponse]:
    """Get all marketplace fee schedules (public, no auth required)."""
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT marketplace_id, display_name, base_fee_pct,
                       payment_processing_pct, fixed_fee, currency,
                       min_fee, max_fee, notes
                FROM marketplace_fee_schedules
                ORDER BY marketplace_id
                """
            )
            return [
                FeeScheduleResponse(
                    marketplace_id=r["marketplace_id"],
                    display_name=r["display_name"],
                    base_fee_pct=float(r["base_fee_pct"]),
                    payment_processing_pct=float(r["payment_processing_pct"]),
                    fixed_fee=float(r["fixed_fee"]),
                    currency=r.get("currency", "EUR"),
                    min_fee=float(r["min_fee"]) if r.get("min_fee") is not None else 0,
                    max_fee=float(r["max_fee"]) if r.get("max_fee") is not None else None,
                    notes=r.get("notes"),
                )
                for r in rows
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error listing fee schedules: %s", e)
        raise error_response(500, "Failed to list fee schedules", code=ErrorCode.DB_ERROR)


@router.post("/fees/calculate", response_model=FeeCalculateResponse, summary="Calculate estimated fees")
async def calculate_fees(payload: FeeCalculateRequest) -> FeeCalculateResponse:
    """Calculate estimated fees and net proceeds for a price/marketplace combination (public)."""
    if payload.marketplace_id not in VALID_MARKETPLACES:
        raise error_response(
            400,
            f"Invalid marketplace_id: {payload.marketplace_id}",
            code=ErrorCode.VALIDATION_ERROR,
        )

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT base_fee_pct, payment_processing_pct, fixed_fee,
                       min_fee, max_fee
                FROM marketplace_fee_schedules
                WHERE marketplace_id = $1
                """,
                payload.marketplace_id,
            )
            if not row:
                raise error_response(
                    404,
                    f"No fee schedule found for marketplace: {payload.marketplace_id}",
                    code=ErrorCode.NOT_FOUND,
                )

            base_fee_pct = float(row["base_fee_pct"])
            processing_pct = float(row["payment_processing_pct"])
            fixed_fee = float(row["fixed_fee"])
            min_fee = float(row["min_fee"]) if row["min_fee"] is not None else 0
            max_fee = float(row["max_fee"]) if row["max_fee"] is not None else None

            # Calculate fees
            base_fee = round(payload.price * (base_fee_pct / 100), 2)
            processing_fee = round(payload.price * (processing_pct / 100), 2)
            total_fees = base_fee + processing_fee + fixed_fee

            # Apply min/max caps
            if total_fees < min_fee:
                total_fees = min_fee
            if max_fee is not None and total_fees > max_fee:
                total_fees = max_fee

            total_fees = round(total_fees, 2)
            estimated_net = round(payload.price - total_fees - payload.shipping_cost, 2)

            return FeeCalculateResponse(
                marketplace_id=payload.marketplace_id,
                price=payload.price,
                base_fee=base_fee,
                payment_processing_fee=processing_fee,
                fixed_fee=fixed_fee,
                total_fees=total_fees,
                shipping_cost=payload.shipping_cost,
                estimated_net=estimated_net,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[marketplace-listings] DB error calculating fees: %s", e)
        raise error_response(500, "Failed to calculate fees", code=ErrorCode.DB_ERROR)
