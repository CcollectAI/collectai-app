"""
Tests for app/features/grading_router.py — grading service integration endpoints.

Covers:
  - GET /grading/lookup          — cert number lookup (happy path, schema, edge cases)
  - GET /grading/population      — population report (happy path, schema, edge cases)
  - GET /grading/services        — list grading services (all, filtered, empty filter)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /grading/lookup — happy paths
# ---------------------------------------------------------------------------


class TestGradingLookupHappyPath:
    """Tests for GET /grading/lookup happy path scenarios."""

    def test_psa_lookup_returns_cert_url(self):
        """PSA lookup returns a cert_url for manual verification."""
        resp = client.get("/grading/lookup", params={"cert_number": "12345678", "service": "psa"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["cert_number"] == "12345678"
        assert data["service"] == "psa"
        assert data["service_name"] == "PSA"
        assert data["cert_verified"] is False
        assert "12345678" in data["cert_url"]
        assert "psacard.com" in data["cert_url"]

    def test_cgc_lookup_returns_cert_url(self):
        """CGC lookup returns the correct service-specific cert URL."""
        resp = client.get("/grading/lookup", params={"cert_number": "9876543", "service": "cgc"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "cgc"
        assert data["service_name"] == "CGC"
        assert "cgccomics.com" in data["cert_url"]
        assert "9876543" in data["cert_url"]

    def test_bgs_lookup_returns_cert_url(self):
        """BGS lookup returns the correct cert URL."""
        resp = client.get("/grading/lookup", params={"cert_number": "55555", "service": "bgs"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "bgs"
        assert data["service_name"] == "BGS"
        assert "beckett.com/grading" in data["cert_url"]

    def test_beckett_lookup_returns_cert_url(self):
        """Beckett (BAS) lookup returns the correct cert URL."""
        resp = client.get("/grading/lookup", params={"cert_number": "ABC123", "service": "beckett"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "beckett"
        assert data["service_name"] == "BAS"
        assert "beckett.com/authentication" in data["cert_url"]


# ---------------------------------------------------------------------------
# GET /grading/lookup — schema validation
# ---------------------------------------------------------------------------


class TestGradingLookupSchema:
    """Tests for response schema of GET /grading/lookup."""

    def test_response_has_all_expected_fields(self):
        """Verify all expected fields exist in the response and have correct types."""
        resp = client.get("/grading/lookup", params={"cert_number": "10001", "service": "psa"})
        assert resp.status_code == 200
        data = resp.json()

        assert isinstance(data["cert_number"], str)
        assert isinstance(data["service"], str)
        assert isinstance(data["service_name"], str)
        assert isinstance(data["cert_verified"], bool)
        # item_name, grade, grade_numeric, sub_grades may be None
        assert "item_name" in data
        assert "grade" in data
        assert "grade_numeric" in data
        assert "sub_grades" in data
        assert "population_at_grade" in data
        assert "population_higher" in data
        assert "cert_url" in data
        assert "label_type" in data
        assert "year" in data
        assert "error" in data

    def test_error_field_contains_message(self):
        """The error field explains that live verification needs API credentials."""
        resp = client.get("/grading/lookup", params={"cert_number": "10001", "service": "psa"})
        data = resp.json()
        assert data["error"] is not None
        assert "credentials" in data["error"].lower() or "cert_url" in data["error"].lower()

    def test_cert_number_is_cleaned_alphanumeric(self):
        """Non-alphanumeric characters are stripped from the cert number."""
        resp = client.get("/grading/lookup", params={"cert_number": "12-345-678", "service": "psa"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["cert_number"] == "12345678"
        # cert_url should contain the cleaned number
        assert "12345678" in data["cert_url"]


# ---------------------------------------------------------------------------
# GET /grading/lookup — edge cases / validation errors
# ---------------------------------------------------------------------------


class TestGradingLookupEdgeCases:
    """Tests for GET /grading/lookup edge cases and validation."""

    def test_missing_cert_number_returns_422(self):
        """Missing required cert_number param triggers 422."""
        resp = client.get("/grading/lookup", params={"service": "psa"})
        assert resp.status_code == 422

    def test_missing_service_returns_422(self):
        """Missing required service param triggers 422."""
        resp = client.get("/grading/lookup", params={"cert_number": "12345"})
        assert resp.status_code == 422

    def test_invalid_service_returns_422(self):
        """Invalid service value (not in pattern) triggers 422."""
        resp = client.get("/grading/lookup", params={"cert_number": "12345", "service": "invalid"})
        assert resp.status_code == 422

    def test_empty_cert_number_returns_422(self):
        """Empty cert_number triggers 422 due to min_length=1."""
        resp = client.get("/grading/lookup", params={"cert_number": "", "service": "psa"})
        assert resp.status_code == 422

    def test_only_special_chars_cert_number_returns_400(self):
        """Cert number with only special characters returns 400 after cleaning."""
        resp = client.get("/grading/lookup", params={"cert_number": "---", "service": "psa"})
        assert resp.status_code == 400

    def test_cert_number_too_long_returns_422(self):
        """Cert number exceeding max_length=20 triggers 422."""
        long_cert = "A" * 21
        resp = client.get("/grading/lookup", params={"cert_number": long_cert, "service": "psa"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /grading/population — happy paths
# ---------------------------------------------------------------------------


class TestGradingPopulationHappyPath:
    """Tests for GET /grading/population happy path scenarios."""

    def test_population_returns_empty_data(self):
        """Population endpoint returns structured empty data (no live API)."""
        resp = client.get("/grading/population", params={
            "item_name": "Charizard Base Set",
            "category": "pokemon",
            "service": "psa",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_name"] == "Charizard Base Set"
        assert data["category"] == "pokemon"
        assert data["service"] == "psa"
        assert data["total_graded"] == 0
        assert data["population"] == []
        assert data["avg_grade"] is None
        assert data["highest_grade"] is None
        assert data["last_updated"] is None

    def test_population_with_different_service(self):
        """Population report works with CGC service."""
        resp = client.get("/grading/population", params={
            "item_name": "Amazing Spider-Man #129",
            "category": "comic_books",
            "service": "cgc",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "cgc"
        assert data["category"] == "comic_books"

    def test_population_default_service_is_psa(self):
        """When no service param is given, default is psa."""
        resp = client.get("/grading/population", params={
            "item_name": "Black Lotus",
            "category": "mtg",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "psa"


# ---------------------------------------------------------------------------
# GET /grading/population — schema validation
# ---------------------------------------------------------------------------


class TestGradingPopulationSchema:
    """Tests for response schema of GET /grading/population."""

    def test_response_has_all_expected_fields(self):
        """Verify all expected fields exist in the response."""
        resp = client.get("/grading/population", params={
            "item_name": "Test Card",
            "category": "pokemon",
        })
        assert resp.status_code == 200
        data = resp.json()

        assert isinstance(data["item_name"], str)
        assert isinstance(data["category"], str)
        assert isinstance(data["service"], str)
        assert isinstance(data["total_graded"], int)
        assert isinstance(data["population"], list)
        # These are None for the empty response
        assert "avg_grade" in data
        assert "highest_grade" in data
        assert "last_updated" in data


# ---------------------------------------------------------------------------
# GET /grading/population — edge cases / validation errors
# ---------------------------------------------------------------------------


class TestGradingPopulationEdgeCases:
    """Tests for GET /grading/population edge cases and validation."""

    def test_ineligible_category_returns_400(self):
        """A category not in GRADING_ELIGIBLE_CATEGORIES returns 400."""
        resp = client.get("/grading/population", params={
            "item_name": "Some Watch",
            "category": "watches",
            "service": "psa",
        })
        assert resp.status_code == 400

    def test_missing_item_name_returns_422(self):
        """Missing required item_name param triggers 422."""
        resp = client.get("/grading/population", params={
            "category": "pokemon",
        })
        assert resp.status_code == 422

    def test_missing_category_returns_422(self):
        """Missing required category param triggers 422."""
        resp = client.get("/grading/population", params={
            "item_name": "Charizard",
        })
        assert resp.status_code == 422

    def test_invalid_service_returns_422(self):
        """Invalid service value triggers 422."""
        resp = client.get("/grading/population", params={
            "item_name": "Card",
            "category": "pokemon",
            "service": "unknown_service",
        })
        assert resp.status_code == 422

    def test_empty_item_name_returns_422(self):
        """Empty item_name triggers 422 due to min_length=1."""
        resp = client.get("/grading/population", params={
            "item_name": "",
            "category": "pokemon",
        })
        assert resp.status_code == 422

    def test_all_eligible_categories_accepted(self):
        """All categories in GRADING_ELIGIBLE_CATEGORIES are accepted."""
        eligible = ["pokemon", "mtg", "yugioh", "sportscards", "comic_books", "retro_games"]
        for cat in eligible:
            resp = client.get("/grading/population", params={
                "item_name": "Test Item",
                "category": cat,
            })
            assert resp.status_code == 200, f"Category {cat} was rejected"


# ---------------------------------------------------------------------------
# GET /grading/services — happy paths
# ---------------------------------------------------------------------------


class TestGradingServicesHappyPath:
    """Tests for GET /grading/services happy path scenarios."""

    def test_returns_all_services(self):
        """Without category filter, returns all 4 grading services."""
        resp = client.get("/grading/services")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["services"]) == 4
        service_ids = [s["id"] for s in data["services"]]
        assert "psa" in service_ids
        assert "cgc" in service_ids
        assert "bgs" in service_ids
        assert "beckett" in service_ids

    def test_returns_eligible_categories(self):
        """Response includes the sorted list of eligible categories."""
        resp = client.get("/grading/services")
        data = resp.json()
        eligible = data["eligible_categories"]
        assert isinstance(eligible, list)
        assert len(eligible) == 6
        # Should be sorted
        assert eligible == sorted(eligible)
        assert "pokemon" in eligible
        assert "comic_books" in eligible

    def test_filter_by_pokemon_category(self):
        """Filtering by 'pokemon' returns PSA, CGC, and BGS (not Beckett BAS)."""
        resp = client.get("/grading/services", params={"category": "pokemon"})
        assert resp.status_code == 200
        data = resp.json()
        service_ids = [s["id"] for s in data["services"]]
        assert "psa" in service_ids
        assert "cgc" in service_ids
        assert "bgs" in service_ids
        # Beckett BAS is only for sportscards
        assert "beckett" not in service_ids

    def test_filter_by_sportscards_includes_beckett(self):
        """Filtering by 'sportscards' includes Beckett BAS."""
        resp = client.get("/grading/services", params={"category": "sportscards"})
        assert resp.status_code == 200
        data = resp.json()
        service_ids = [s["id"] for s in data["services"]]
        assert "beckett" in service_ids
        assert "psa" in service_ids

    def test_filter_by_nonexistent_category_returns_empty(self):
        """Filtering by a category no service supports returns empty list."""
        resp = client.get("/grading/services", params={"category": "lego"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["services"] == []
        # eligible_categories is still returned
        assert len(data["eligible_categories"]) == 6


# ---------------------------------------------------------------------------
# GET /grading/services — schema validation
# ---------------------------------------------------------------------------


class TestGradingServicesSchema:
    """Tests for response schema of GET /grading/services."""

    def test_service_entry_has_all_fields(self):
        """Each service entry has all expected fields with correct types."""
        resp = client.get("/grading/services")
        data = resp.json()
        for svc in data["services"]:
            assert isinstance(svc["id"], str)
            assert isinstance(svc["name"], str)
            assert isinstance(svc["short_name"], str)
            assert isinstance(svc["website"], str)
            assert isinstance(svc["submission_url"], str)
            assert isinstance(svc["grade_scale"], str)
            assert isinstance(svc["categories"], list)
            assert isinstance(svc["turnaround"], str)
            assert isinstance(svc["price_range"], str)
            # Website URLs should be HTTPS
            assert svc["website"].startswith("https://")
            assert svc["submission_url"].startswith("https://")

    def test_services_have_valid_categories(self):
        """All categories listed in services are in the eligible set."""
        resp = client.get("/grading/services")
        data = resp.json()
        eligible = set(data["eligible_categories"])
        for svc in data["services"]:
            for cat in svc["categories"]:
                assert cat in eligible, f"Service {svc['id']} has invalid category: {cat}"
