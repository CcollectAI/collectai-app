"""Shared pagination dependency for feature routers."""

from __future__ import annotations

from fastapi import Query


def pagination_params(
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> tuple[int, int]:
    """Return (limit, offset) validated by FastAPI Query constraints."""
    return limit, offset
