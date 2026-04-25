"""Warm-tier S3 parquet read endpoint.

Diagnostic + analytics endpoint that lets the app query historical data
that's been moved out of Postgres into S3 parquet. Service-role only for
v1 — once we wire it into trend-chart / dossier endpoints with a
trusted SQL builder we can open it to authenticated users.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.lib.warm_tier import (
    WARM_TIER_TABLES,
    warm_tier_count,
    warm_tier_read,
)
from app.auth import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/warm-tier", tags=["WarmTier"])


class WarmTierQuery(BaseModel):
    table: str = Field(..., description="One of: market_hits, price_predictions, price_history")
    year_from: int = Field(..., ge=2024, le=2099)
    month_from: int = Field(..., ge=1, le=12)
    year_to: int = Field(..., ge=2024, le=2099)
    month_to: int = Field(..., ge=1, le=12)
    where: Optional[str] = Field(None, max_length=500,
                                 description="SECURITY: caller's responsibility to whitelist")
    select: str = Field(default="*", max_length=500)
    limit: int = Field(default=100, ge=1, le=10_000)


class WarmTierCount(BaseModel):
    n: int


@router.post("/query", response_model=List[Dict[str, Any]],
             summary="Run a SELECT against warm-tier S3 parquet")
async def query(payload: WarmTierQuery, user_id: str = Depends(get_current_user_id)) -> List[Dict[str, Any]]:
    if payload.table not in WARM_TIER_TABLES:
        raise HTTPException(400, f"unknown table: {payload.table}")
    try:
        return warm_tier_read(
            payload.table,
            year_from=payload.year_from, month_from=payload.month_from,
            year_to=payload.year_to, month_to=payload.month_to,
            where=payload.where, select=payload.select, limit=payload.limit,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("warm-tier query failed: %s", e)
        raise HTTPException(502, f"Warm-tier query failed: {e!s}")


@router.post("/count", response_model=WarmTierCount,
             summary="Count rows in warm-tier S3 parquet")
async def count(payload: WarmTierQuery, user_id: str = Depends(get_current_user_id)) -> WarmTierCount:
    if payload.table not in WARM_TIER_TABLES:
        raise HTTPException(400, f"unknown table: {payload.table}")
    try:
        n = warm_tier_count(
            payload.table,
            year_from=payload.year_from, month_from=payload.month_from,
            year_to=payload.year_to, month_to=payload.month_to,
            where=payload.where,
        )
        return WarmTierCount(n=n)
    except Exception as e:
        logger.exception("warm-tier count failed: %s", e)
        raise HTTPException(502, f"Warm-tier count failed: {e!s}")
