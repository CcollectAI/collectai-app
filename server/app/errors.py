"""
Standard error response model and helpers.

Usage:
    from app.errors import ErrorResponse, error_response

    # In endpoint:
    raise error_response(404, "Item not found", code="ITEM_NOT_FOUND")

    # Or use ErrorResponse as response_model for documentation:
    @router.get("/items/{id}", responses={404: {"model": ErrorResponse}})
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.request_id import get_request_id


class ErrorResponse(BaseModel):
    """Standard error response shape for all API errors."""
    message: str = Field(..., description="Human-readable error description")
    code: str = Field("UNKNOWN_ERROR", description="Machine-readable error code")
    request_id: str = Field("", description="Request ID for tracing")


def error_response(
    status_code: int,
    detail: str,
    code: str = "UNKNOWN_ERROR",
    headers: dict[str, str] | None = None,
) -> HTTPException:
    """Create an HTTPException with a standard error body including request_id."""
    return HTTPException(
        status_code=status_code,
        detail={
            "message": detail,
            "code": code,
            "request_id": get_request_id(),
        },
        headers=headers,
    )
