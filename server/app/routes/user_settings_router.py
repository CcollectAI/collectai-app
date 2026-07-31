"""
User settings router for managing per-user preferences.

Endpoints:
- GET  /settings - Return current user settings (currency, region, locale)
- PUT  /settings - Upsert user settings with validation
- GET  /settings/alert-preferences - Return user's alert preferences (or defaults)
- PATCH /settings/alert-preferences - Upsert alert preferences
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Literal, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/settings", tags=["Settings"])
logger = logging.getLogger(__name__)

# Per-user: 30 requests per minute for settings
_settings_user_limit = per_user_rate_limit(30, scope="settings")

# ---------------------------------------------------------------------------
# Allowed values
# ---------------------------------------------------------------------------
VALID_CURRENCIES = {"EUR", "USD", "JPY", "GBP", "KRW", "AUD", "CAD"}
VALID_REGIONS = {"americas", "europe", "japan", "korea", "oceania", "other"}
VALID_LOCALES = {"en-US", "de-DE", "ja-JP", "nl-NL", "ko-KR", "en-AU"}

# Defaults (match the DB column defaults)
DEFAULT_CURRENCY = "EUR"
DEFAULT_REGION = "europe"
DEFAULT_LOCALE = "de-DE"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class UserSettingsResponse(BaseModel):
    """Current user settings."""
    currency: str = Field(DEFAULT_CURRENCY, description="Preferred currency code")
    region: str = Field(DEFAULT_REGION, description="Preferred marketplace region")
    locale: str = Field(DEFAULT_LOCALE, description="Preferred locale for formatting")


class UserSettingsUpdateRequest(BaseModel):
    """Request body for updating user settings. All fields are optional."""
    currency: str | None = Field(
        None,
        description=f"Currency code. Valid: {', '.join(sorted(VALID_CURRENCIES))}",
    )
    region: str | None = Field(
        None,
        description=f"Marketplace region. Valid: {', '.join(sorted(VALID_REGIONS))}",
    )
    locale: str | None = Field(
        None,
        description=f"Display locale. Valid: {', '.join(sorted(VALID_LOCALES))}",
    )


class UserSettingsUpdateResponse(BaseModel):
    """Response from settings upsert."""
    success: bool
    settings: UserSettingsResponse


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=UserSettingsResponse, dependencies=[Depends(_settings_user_limit)], summary="Get user settings")
async def get_user_settings(user_id: str = Depends(get_current_user_id)):
    """
    Return current user settings.

    If no row exists for this user, returns the defaults
    (EUR, europe, de-DE) without inserting anything.
    """
    pool = get_db_pool()

    if pool is None:
        # Offline / no-DB mode: return defaults
        return UserSettingsResponse()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT currency, region, locale
                FROM user_settings
                WHERE user_id = $1
                """,
                user_id,
            )

        if row is None:
            return UserSettingsResponse()

        return UserSettingsResponse(
            currency=row["currency"],
            region=row["region"],
            locale=row["locale"],
        )

    except asyncpg.PostgresError as e:
        logger.error("[settings] Error fetching user settings: %s", e)
        raise error_response(500, "Failed to fetch settings", code="DB_ERROR")


@router.put("", response_model=UserSettingsUpdateResponse, dependencies=[Depends(_settings_user_limit)], summary="Update user settings")
async def update_user_settings(
    request: UserSettingsUpdateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Upsert user settings.

    Accepts optional fields; only provided values are updated.
    Values are validated against allowed lists before persisting.
    Uses INSERT ... ON CONFLICT DO UPDATE for atomic upsert.
    """
    # --- Validation ---
    if request.currency is not None and request.currency not in VALID_CURRENCIES:
        raise error_response(
            400,
            f"Invalid currency. Valid: {', '.join(sorted(VALID_CURRENCIES))}",
            code="VALIDATION_ERROR",
        )
    if request.region is not None and request.region not in VALID_REGIONS:
        raise error_response(
            400,
            f"Invalid region. Valid: {', '.join(sorted(VALID_REGIONS))}",
            code="VALIDATION_ERROR",
        )
    if request.locale is not None and request.locale not in VALID_LOCALES:
        raise error_response(
            400,
            f"Invalid locale. Valid: {', '.join(sorted(VALID_LOCALES))}",
            code="VALIDATION_ERROR",
        )

    # At least one field must be provided
    if request.currency is None and request.region is None and request.locale is None:
        raise error_response(
            400,
            "At least one setting field must be provided",
            code="VALIDATION_ERROR",
        )

    pool = get_db_pool()

    if pool is None:
        # Offline mode: return the submitted values merged with defaults
        return UserSettingsUpdateResponse(
            success=True,
            settings=UserSettingsResponse(
                currency=request.currency or DEFAULT_CURRENCY,
                region=request.region or DEFAULT_REGION,
                locale=request.locale or DEFAULT_LOCALE,
            ),
        )

    try:
        # Pass None for unprovided fields so COALESCE preserves existing DB values
        now = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_settings (user_id, currency, region, locale, updated_at)
                VALUES ($1, COALESCE($2, 'EUR'), COALESCE($3, 'europe'), COALESCE($4, 'de-DE'), $5)
                ON CONFLICT (user_id) DO UPDATE SET
                    currency   = COALESCE($2, user_settings.currency),
                    region     = COALESCE($3, user_settings.region),
                    locale     = COALESCE($4, user_settings.locale),
                    updated_at = $5
                RETURNING currency, region, locale
                """,
                user_id,
                request.currency,
                request.region,
                request.locale,
                now,
            )

        logger.info(
            "[settings] Upserted settings for user=%s: currency=%s, region=%s, locale=%s",
            user_id, row["currency"], row["region"], row["locale"],
        )

        return UserSettingsUpdateResponse(
            success=True,
            settings=UserSettingsResponse(
                currency=row["currency"],
                region=row["region"],
                locale=row["locale"],
            ),
        )

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[settings] Error upserting user settings: %s", e)
        raise error_response(500, "Failed to save settings", code="DB_ERROR")


# ---------------------------------------------------------------------------
# Alert Preferences — models
# ---------------------------------------------------------------------------
VALID_FREQUENCIES = frozenset({"immediate", "daily", "weekly"})

DEFAULT_ALERT_PREFS: dict = {
    "price_drop_enabled": True,
    "price_drop_threshold": 10,
    "new_listing_enabled": True,
    "milestone_enabled": True,
    "price_increase_enabled": False,
    "price_increase_threshold": 20,
    "frequency": "daily",
}


class AlertPreferencesResponse(BaseModel):
    """User alert preference values."""
    price_drop_enabled: bool = Field(True, description="Enable price drop alerts")
    price_drop_threshold: int = Field(10, ge=1, le=100, description="Price drop % threshold")
    new_listing_enabled: bool = Field(True, description="Enable new listing alerts")
    milestone_enabled: bool = Field(True, description="Enable milestone alerts")
    price_increase_enabled: bool = Field(False, description="Enable price increase alerts")
    price_increase_threshold: int = Field(20, ge=1, le=100, description="Price increase % threshold")
    frequency: Literal["immediate", "daily", "weekly"] = Field("daily", description="Notification frequency")


class AlertPreferencesUpdateRequest(BaseModel):
    """Partial update for alert preferences. All fields optional."""
    price_drop_enabled: bool | None = None
    price_drop_threshold: int | None = Field(None, ge=1, le=100)
    new_listing_enabled: bool | None = None
    milestone_enabled: bool | None = None
    price_increase_enabled: bool | None = None
    price_increase_threshold: int | None = Field(None, ge=1, le=100)
    frequency: Literal["immediate", "daily", "weekly"] | None = None


# ---------------------------------------------------------------------------
# Alert Preferences — endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/alert-preferences",
    response_model=AlertPreferencesResponse,
    dependencies=[Depends(_settings_user_limit)],
    summary="Get alert preferences",
)
async def get_alert_preferences(user_id: str = Depends(get_current_user_id)) -> AlertPreferencesResponse:
    """
    Return the user's saved alert preferences.

    If no row exists, returns sensible defaults without inserting.
    """
    pool = get_db_pool()

    if pool is None:
        return AlertPreferencesResponse(**DEFAULT_ALERT_PREFS)

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT price_drop_enabled, price_drop_threshold,
                       new_listing_enabled, milestone_enabled,
                       price_increase_enabled, price_increase_threshold,
                       frequency
                FROM user_alert_preferences
                WHERE user_id = $1
                """,
                user_id,
            )

        if row is None:
            return AlertPreferencesResponse(**DEFAULT_ALERT_PREFS)

        return AlertPreferencesResponse(
            price_drop_enabled=row["price_drop_enabled"],
            price_drop_threshold=row["price_drop_threshold"],
            new_listing_enabled=row["new_listing_enabled"],
            milestone_enabled=row["milestone_enabled"],
            price_increase_enabled=row["price_increase_enabled"],
            price_increase_threshold=row["price_increase_threshold"],
            frequency=row["frequency"],
        )

    except asyncpg.PostgresError as e:
        logger.error("[settings] Error fetching alert preferences: %s", e)
        raise error_response(500, "Failed to fetch alert preferences", code="DB_ERROR")


@router.patch(
    "/alert-preferences",
    response_model=AlertPreferencesResponse,
    dependencies=[Depends(_settings_user_limit)],
    summary="Update alert preferences",
)
async def update_alert_preferences(
    request: AlertPreferencesUpdateRequest,
    user_id: str = Depends(get_current_user_id),
) -> AlertPreferencesResponse:
    """
    Upsert user alert preferences.

    Accepts partial updates — only provided fields are changed.
    Uses INSERT ... ON CONFLICT DO UPDATE for atomic upsert.
    """
    # Validate frequency if provided
    if request.frequency is not None and request.frequency not in VALID_FREQUENCIES:
        raise error_response(
            400,
            f"Invalid frequency. Valid: {', '.join(sorted(VALID_FREQUENCIES))}",
            code="VALIDATION_ERROR",
        )

    # At least one field must be provided
    update_data = request.model_dump(exclude_none=True)
    if not update_data:
        raise error_response(
            400,
            "At least one alert preference field must be provided",
            code="VALIDATION_ERROR",
        )

    pool = get_db_pool()

    if pool is None:
        merged = {**DEFAULT_ALERT_PREFS, **update_data}
        return AlertPreferencesResponse(**merged)

    try:
        now = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_alert_preferences (
                    user_id,
                    price_drop_enabled, price_drop_threshold,
                    new_listing_enabled, milestone_enabled,
                    price_increase_enabled, price_increase_threshold,
                    frequency, updated_at
                )
                VALUES (
                    $1,
                    COALESCE($2, true), COALESCE($3, 10),
                    COALESCE($4, true), COALESCE($5, true),
                    COALESCE($6, false), COALESCE($7, 20),
                    COALESCE($8, 'daily'), $9
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    price_drop_enabled     = COALESCE($2, user_alert_preferences.price_drop_enabled),
                    price_drop_threshold   = COALESCE($3, user_alert_preferences.price_drop_threshold),
                    new_listing_enabled    = COALESCE($4, user_alert_preferences.new_listing_enabled),
                    milestone_enabled      = COALESCE($5, user_alert_preferences.milestone_enabled),
                    price_increase_enabled = COALESCE($6, user_alert_preferences.price_increase_enabled),
                    price_increase_threshold = COALESCE($7, user_alert_preferences.price_increase_threshold),
                    frequency              = COALESCE($8, user_alert_preferences.frequency),
                    updated_at             = $9
                RETURNING price_drop_enabled, price_drop_threshold,
                          new_listing_enabled, milestone_enabled,
                          price_increase_enabled, price_increase_threshold,
                          frequency
                """,
                user_id,
                request.price_drop_enabled,
                request.price_drop_threshold,
                request.new_listing_enabled,
                request.milestone_enabled,
                request.price_increase_enabled,
                request.price_increase_threshold,
                request.frequency,
                now,
            )

        logger.info("[settings] Upserted alert preferences for user=%s", user_id)

        return AlertPreferencesResponse(
            price_drop_enabled=row["price_drop_enabled"],
            price_drop_threshold=row["price_drop_threshold"],
            new_listing_enabled=row["new_listing_enabled"],
            milestone_enabled=row["milestone_enabled"],
            price_increase_enabled=row["price_increase_enabled"],
            price_increase_threshold=row["price_increase_threshold"],
            frequency=row["frequency"],
        )

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[settings] Error upserting alert preferences: %s", e)
        raise error_response(500, "Failed to save alert preferences", code="DB_ERROR")


# ---------------------------------------------------------------------------
# Profile (username + bio)
# ---------------------------------------------------------------------------

# Mirrors profiles_bio_length_check. Validate here so the user gets a clear 400
# rather than a 23514 surfaced as a generic 500 — the exact shape that hid the
# currency/region/locale breakage for Korea and Oceania (see the 20260730
# migrations).
BIO_MAX_LEN = 300
USERNAME_MIN_LEN = 3
USERNAME_MAX_LEN = 30
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


class ProfileUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, max_length=USERNAME_MAX_LEN)
    bio: Optional[str] = Field(None, max_length=BIO_MAX_LEN)


class ProfileResponse(BaseModel):
    id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


@router.patch(
    "/profile",
    response_model=ProfileResponse,
    dependencies=[Depends(_settings_user_limit)],
    summary="Update the current user's profile (username, bio)",
)
async def update_profile(
    request: ProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
) -> ProfileResponse:
    """
    Partial update of the caller's own `profiles` row.

    Added 2026-07-31. `ProfileEditSection` had been calling this path since it
    shipped, but the route did not exist — a 404 the client never checked, so
    the modal closed with a success haptic and nothing was saved.

    Only `username` and `bio` are editable. `display_name` follows `username`
    when it was previously mirroring it (the signup trigger sets both to the
    username), so a rename does not leave a stale display name behind — but a
    display_name the user has deliberately diverged from their username is left
    alone.
    """
    update_data = request.model_dump(exclude_none=True)
    if not update_data:
        raise error_response(
            400, "Provide at least one of: username, bio", code="VALIDATION_ERROR"
        )

    username = request.username.strip() if request.username is not None else None
    bio = request.bio.strip() if request.bio is not None else None

    if username is not None:
        if len(username) < USERNAME_MIN_LEN:
            raise error_response(
                400,
                f"Username must be at least {USERNAME_MIN_LEN} characters",
                code="VALIDATION_ERROR",
            )
        if not _USERNAME_RE.match(username):
            raise error_response(
                400,
                "Username may only contain letters, numbers and underscores",
                code="VALIDATION_ERROR",
            )

    if bio is not None and len(bio) > BIO_MAX_LEN:
        raise error_response(
            400, f"Bio must be {BIO_MAX_LEN} characters or fewer", code="VALIDATION_ERROR"
        )

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    try:
        async with pool.acquire() as conn:
            if username is not None:
                # Case-insensitive, matching what handle_new_user does at signup.
                # profiles_username_key is case-SENSITIVE, so without this
                # 'Merle' and 'merle' could both exist.
                taken = await conn.fetchval(
                    "SELECT 1 FROM public.profiles WHERE lower(username) = lower($1) AND id <> $2::uuid",
                    username,
                    user_id,
                )
                if taken:
                    raise error_response(
                        409, "That username is already taken", code="USERNAME_TAKEN"
                    )

            row = await conn.fetchrow(
                """
                UPDATE public.profiles
                   SET username     = COALESCE($2, username),
                       bio          = CASE WHEN $3::boolean THEN $4 ELSE bio END,
                       -- Keep display_name aligned only while it mirrors the
                       -- username; never clobber a deliberately different one.
                       display_name = CASE
                                         WHEN $2::text IS NOT NULL
                                          AND (display_name IS NULL OR display_name = username)
                                         THEN $2
                                         ELSE display_name
                                      END
                 WHERE id = $1::uuid
             RETURNING id, username, display_name, bio, avatar_url
                """,
                user_id,
                username,
                "bio" in update_data,
                bio,
            )

        if row is None:
            raise error_response(404, "Profile not found", code="NOT_FOUND")

        logger.info("[settings] Updated profile for user=%s", user_id)
        return ProfileResponse(
            id=str(row["id"]),
            username=row["username"],
            display_name=row["display_name"],
            bio=row["bio"],
            avatar_url=row["avatar_url"],
        )

    except HTTPException:
        raise
    except asyncpg.UniqueViolationError:
        # Lost a race between the check above and the UPDATE.
        raise error_response(409, "That username is already taken", code="USERNAME_TAKEN")
    except asyncpg.PostgresError as e:
        logger.error("[settings] Error updating profile: %s", e)
        raise error_response(500, "Failed to save profile", code="DB_ERROR")
