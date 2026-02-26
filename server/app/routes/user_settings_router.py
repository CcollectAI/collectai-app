"""
User settings router for managing per-user preferences.

Endpoints:
- GET  /settings - Return current user settings (currency, region, locale)
- PUT  /settings - Upsert user settings with validation
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool

router = APIRouter(prefix="/settings", tags=["settings"])
logger = logging.getLogger(__name__)

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
@router.get("", response_model=UserSettingsResponse)
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


@router.put("", response_model=UserSettingsUpdateResponse)
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
