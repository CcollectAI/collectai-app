"""Standardized error codes for API responses."""


class ErrorCode:
    """Constants for the `code` field in error responses."""

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_UUID = "INVALID_UUID"

    # Auth
    AUTH_REQUIRED = "AUTH_REQUIRED"
    FORBIDDEN = "FORBIDDEN"

    # Resources
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"

    # Database
    DB_UNAVAILABLE = "DB_UNAVAILABLE"
    DB_ERROR = "DB_ERROR"

    # Rate limiting
    RATE_LIMITED = "RATE_LIMITED"

    # External
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"

    # Payment
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"

    # Generic
    INTERNAL_ERROR = "INTERNAL_ERROR"
