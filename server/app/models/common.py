"""Common response models used across multiple endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """GET /healthz response."""
    status: str = Field(..., description="Service health status", examples=["ok"])
    version: str = Field(..., description="Service version string")
    db: str = Field("unchecked", description="Database connectivity status")


class VersionResponse(BaseModel):
    """GET /version response."""
    version: str = Field(..., description="Service version")
    env: str = Field("production", description="Environment name")


class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = Field(True, description="Whether the operation succeeded")
    message: str = Field("", description="Optional status message")
