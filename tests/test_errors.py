"""Tests for app.errors — ErrorResponse model and error_response() helper."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.errors import ErrorResponse, error_response


# ---------------------------------------------------------------------------
# ErrorResponse Pydantic model
# ---------------------------------------------------------------------------

class TestErrorResponseModel:
    def test_required_detail(self):
        resp = ErrorResponse(detail="Something went wrong")
        assert resp.detail == "Something went wrong"

    def test_default_code(self):
        resp = ErrorResponse(detail="fail")
        assert resp.code == "UNKNOWN_ERROR"

    def test_custom_code(self):
        resp = ErrorResponse(detail="Not found", code="ITEM_NOT_FOUND")
        assert resp.code == "ITEM_NOT_FOUND"

    def test_default_request_id(self):
        resp = ErrorResponse(detail="fail")
        assert resp.request_id == ""

    def test_custom_request_id(self):
        resp = ErrorResponse(detail="fail", request_id="abc123")
        assert resp.request_id == "abc123"

    def test_serialization(self):
        resp = ErrorResponse(detail="bad input", code="VALIDATION_ERROR", request_id="req-42")
        data = resp.model_dump()
        assert data == {
            "detail": "bad input",
            "code": "VALIDATION_ERROR",
            "request_id": "req-42",
        }

    def test_missing_detail_raises_validation_error(self):
        with pytest.raises(Exception):  # pydantic ValidationError
            ErrorResponse()


# ---------------------------------------------------------------------------
# error_response() helper
# ---------------------------------------------------------------------------

class TestErrorResponseHelper:
    def test_returns_http_exception(self):
        exc = error_response(404, "Item not found")
        assert isinstance(exc, HTTPException)

    def test_status_code(self):
        exc = error_response(422, "Invalid data")
        assert exc.status_code == 422

    def test_detail_is_dict(self):
        exc = error_response(500, "Server error", code="INTERNAL_ERROR")
        assert isinstance(exc.detail, dict)

    def test_detail_contains_all_fields(self):
        exc = error_response(400, "Bad request", code="BAD_REQUEST")
        assert exc.detail["detail"] == "Bad request"
        assert exc.detail["code"] == "BAD_REQUEST"
        assert "request_id" in exc.detail

    def test_default_code_in_detail(self):
        exc = error_response(500, "fail")
        assert exc.detail["code"] == "UNKNOWN_ERROR"

    def test_request_id_injected(self):
        """error_response should include the current request_id from context."""
        with patch("app.errors.get_request_id", return_value="req-abc"):
            exc = error_response(404, "Missing")
            assert exc.detail["request_id"] == "req-abc"

    def test_empty_request_id_when_no_context(self):
        """Outside a request context, request_id should be empty string."""
        with patch("app.errors.get_request_id", return_value=""):
            exc = error_response(404, "Missing")
            assert exc.detail["request_id"] == ""

    def test_various_status_codes(self):
        for code in [400, 401, 403, 404, 409, 422, 500, 503]:
            exc = error_response(code, f"Error {code}")
            assert exc.status_code == code
