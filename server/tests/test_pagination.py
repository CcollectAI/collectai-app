"""
Tests for app/features/pagination.py — shared pagination dependency.

Covers:
  - Direct function call: default values, custom values, boundary values
  - Via endpoint: pagination params are passed through correctly via Depends()
  - Edge cases: negative values, values exceeding limits
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

from app.features.pagination import pagination_params  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Direct function tests
# ---------------------------------------------------------------------------


class TestPaginationParamsDirect:
    """Test pagination_params function directly."""

    def test_default_values(self):
        """Default limit=50, offset=0 when called with explicit values.

        Note: calling pagination_params() with no args returns FastAPI Query
        descriptor objects, not plain ints. The defaults are resolved by
        FastAPI's dependency injection. Test via endpoint params instead.
        """
        limit, offset = pagination_params(limit=50, offset=0)
        assert limit == 50
        assert offset == 0

    def test_custom_values(self):
        """Custom limit and offset are returned as-is."""
        limit, offset = pagination_params(limit=10, offset=20)
        assert limit == 10
        assert offset == 20

    def test_boundary_limit_min(self):
        """limit=1 is the minimum valid value."""
        limit, offset = pagination_params(limit=1, offset=0)
        assert limit == 1

    def test_boundary_limit_max(self):
        """limit=200 is the maximum valid value."""
        limit, offset = pagination_params(limit=200, offset=0)
        assert limit == 200

    def test_return_type_is_tuple(self):
        """Return value is a tuple of two ints."""
        result = pagination_params(limit=25, offset=5)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)


# ---------------------------------------------------------------------------
# Via endpoint tests — use /provenance/items/{item_id} which accepts pagination
# ---------------------------------------------------------------------------


class TestPaginationViaEndpoint:
    """Test pagination params via an actual endpoint that uses Depends(pagination_params)."""

    def test_default_pagination_no_params(self):
        """Endpoint works with default pagination (no query params)."""
        item_id = str(uuid4())
        resp = client.get(f"/provenance/items/{item_id}")
        assert resp.status_code == 200

    def test_custom_limit_and_offset(self):
        """Custom limit and offset are accepted via query params."""
        item_id = str(uuid4())
        resp = client.get(f"/provenance/items/{item_id}?limit=5&offset=10")
        assert resp.status_code == 200

    def test_limit_zero_returns_422(self):
        """limit=0 is below ge=1 and returns 422 validation error."""
        item_id = str(uuid4())
        resp = client.get(f"/provenance/items/{item_id}?limit=0")
        assert resp.status_code == 422

    def test_limit_exceeds_max_returns_422(self):
        """limit=201 exceeds le=200 and returns 422 validation error."""
        item_id = str(uuid4())
        resp = client.get(f"/provenance/items/{item_id}?limit=201")
        assert resp.status_code == 422

    def test_negative_offset_returns_422(self):
        """offset=-1 is below ge=0 and returns 422 validation error."""
        item_id = str(uuid4())
        resp = client.get(f"/provenance/items/{item_id}?offset=-1")
        assert resp.status_code == 422

    def test_negative_limit_returns_422(self):
        """limit=-5 is below ge=1 and returns 422 validation error."""
        item_id = str(uuid4())
        resp = client.get(f"/provenance/items/{item_id}?limit=-5")
        assert resp.status_code == 422

    def test_limit_at_boundary_200(self):
        """limit=200 (the max) is accepted."""
        item_id = str(uuid4())
        resp = client.get(f"/provenance/items/{item_id}?limit=200")
        assert resp.status_code == 200

    def test_limit_at_boundary_1(self):
        """limit=1 (the min) is accepted."""
        item_id = str(uuid4())
        resp = client.get(f"/provenance/items/{item_id}?limit=1")
        assert resp.status_code == 200
