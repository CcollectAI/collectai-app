"""
Grading service integration router.

Provides lookup for certification numbers (PSA, CGC, BGS, Beckett),
population reports, and links to grading service submission pages.

Endpoints:
- GET /grading/lookup          — Look up a certification number
- GET /grading/population      — Get population report for an item
- GET /grading/services        — List available grading services with submission links

Eligible categories: pokemon, mtg, yugioh, sportscards, comic_books, retro_games
"""

from __future__ import annotations

import hashlib
import logging
import random
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import db_configured
from app.errors import error_response
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grading", tags=["grading"])

# Rate limit: 30 lookups per minute per user
_lookup_limit = per_user_rate_limit(30, window_seconds=60, scope="grading_lookup")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRADING_ELIGIBLE_CATEGORIES = frozenset([
    "pokemon", "mtg", "yugioh", "sportscards", "comic_books", "retro_games",
])

GRADING_SERVICES = {
    "psa": {
        "name": "PSA (Professional Sports Authenticator)",
        "short_name": "PSA",
        "website": "https://www.psacard.com",
        "submission_url": "https://www.psacard.com/submit",
        "cert_lookup_url": "https://www.psacard.com/cert/{cert_number}",
        "grade_scale": "1-10",
        "categories": ["pokemon", "mtg", "yugioh", "sportscards"],
        "turnaround": "20-65 business days (standard)",
        "price_range": "$20-$150 per card",
    },
    "cgc": {
        "name": "CGC (Certified Guaranty Company)",
        "short_name": "CGC",
        "website": "https://www.cgccomics.com",
        "submission_url": "https://www.cgccomics.com/submit",
        "cert_lookup_url": "https://www.cgccomics.com/certlookup/{cert_number}",
        "grade_scale": "0.5-10.0",
        "categories": ["comic_books", "pokemon", "mtg", "yugioh"],
        "turnaround": "25-50 business days (standard)",
        "price_range": "$25-$150 per item",
    },
    "bgs": {
        "name": "BGS (Beckett Grading Services)",
        "short_name": "BGS",
        "website": "https://www.beckett.com/grading",
        "submission_url": "https://www.beckett.com/grading/submit",
        "cert_lookup_url": "https://www.beckett.com/grading/card-lookup/{cert_number}",
        "grade_scale": "1-10 (with sub-grades)",
        "categories": ["pokemon", "mtg", "yugioh", "sportscards"],
        "turnaround": "30-60 business days (standard)",
        "price_range": "$20-$250 per card",
    },
    "beckett": {
        "name": "Beckett Authentication (BAS)",
        "short_name": "BAS",
        "website": "https://www.beckett.com/authentication",
        "submission_url": "https://www.beckett.com/authentication/submit",
        "cert_lookup_url": "https://www.beckett.com/authentication/cert/{cert_number}",
        "grade_scale": "Authentic / Not Authentic",
        "categories": ["sportscards"],
        "turnaround": "15-45 business days",
        "price_range": "$10-$50 per item",
    },
}

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class GradingLookupResponse(BaseModel):
    cert_number: str
    service: str
    service_name: str
    item_name: str | None = None
    grade: str | None = None
    grade_numeric: float | None = None
    sub_grades: dict[str, float] | None = None
    population_at_grade: int | None = None
    population_higher: int | None = None
    cert_verified: bool = False
    cert_url: str | None = None
    label_type: str | None = None
    year: str | None = None
    error: str | None = None


class PopulationEntry(BaseModel):
    grade: str
    count: int
    pct_of_total: float | None = None


class PopulationReportResponse(BaseModel):
    item_name: str
    category: str
    service: str
    total_graded: int
    population: list[PopulationEntry]
    avg_grade: float | None = None
    highest_grade: str | None = None
    last_updated: str | None = None


class GradingServiceInfo(BaseModel):
    id: str
    name: str
    short_name: str
    website: str
    submission_url: str
    grade_scale: str
    categories: list[str]
    turnaround: str
    price_range: str


class GradingServicesResponse(BaseModel):
    services: list[GradingServiceInfo]
    eligible_categories: list[str]


# ---------------------------------------------------------------------------
# Mock data generators (structured for easy swap to real API calls)
# ---------------------------------------------------------------------------


def _mock_cert_lookup(cert_number: str, service: str) -> GradingLookupResponse:
    """
    Generate a deterministic mock response based on cert number.

    In production, this function would be replaced with actual API calls to
    PSA, CGC, BGS, or Beckett verification endpoints.
    """
    svc = GRADING_SERVICES.get(service)
    if not svc:
        return GradingLookupResponse(
            cert_number=cert_number,
            service=service,
            service_name=service.upper(),
            cert_verified=False,
            error=f"Unknown grading service: {service}",
        )

    # Deterministic "random" based on cert number for consistent results
    seed = int(hashlib.md5(f"{cert_number}:{service}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Generate plausible mock data
    sample_items = [
        "Charizard Base Set Holo 1st Edition",
        "Pikachu Illustrator Promo",
        "Black Lotus (Alpha)",
        "Mickey Mantle 1952 Topps #311",
        "Amazing Spider-Man #129",
        "Super Mario Bros. (NES) CIB",
        "Pokemon Gold Star Espeon",
        "Dark Magician LOB-005 1st Edition",
        "Michael Jordan Fleer Rookie #57",
        "Action Comics #1 (Reprint)",
    ]

    grade_options_psa = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
    grade_options_cgc = ["0.5", "1.0", "2.0", "3.0", "4.0", "5.0", "6.0", "7.0", "8.0", "8.5", "9.0", "9.2", "9.4", "9.6", "9.8", "10.0"]

    item_name = rng.choice(sample_items)

    if service in ("psa", "bgs"):
        grade_str = rng.choice(grade_options_psa)
        grade_num = float(grade_str)
    elif service == "cgc":
        grade_str = rng.choice(grade_options_cgc)
        grade_num = float(grade_str)
    else:
        grade_str = "Authentic"
        grade_num = None

    sub_grades = None
    if service == "bgs":
        sub_grades = {
            "centering": round(rng.uniform(7.0, 10.0), 1),
            "edges": round(rng.uniform(7.0, 10.0), 1),
            "corners": round(rng.uniform(7.0, 10.0), 1),
            "surface": round(rng.uniform(7.0, 10.0), 1),
        }

    pop_at_grade = rng.randint(50, 5000)
    pop_higher = rng.randint(0, pop_at_grade // 2) if grade_num and grade_num < 10 else 0

    cert_url_template = svc.get("cert_lookup_url", "")
    cert_url = cert_url_template.replace("{cert_number}", cert_number) if cert_url_template else None

    label_types = ["standard", "first edition", "holo", "error", None]

    return GradingLookupResponse(
        cert_number=cert_number,
        service=service,
        service_name=svc["short_name"],
        item_name=item_name,
        grade=grade_str,
        grade_numeric=grade_num,
        sub_grades=sub_grades,
        population_at_grade=pop_at_grade,
        population_higher=pop_higher,
        cert_verified=True,
        cert_url=cert_url,
        label_type=rng.choice(label_types),
        year=str(rng.randint(1993, 2025)),
    )


def _mock_population_report(item_name: str, category: str, service: str) -> PopulationReportResponse:
    """
    Generate a mock population report.

    In production, this would query PSA/CGC/BGS population databases.
    """
    seed = int(hashlib.md5(f"{item_name}:{category}:{service}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    if service in ("psa", "bgs"):
        grades = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
    elif service == "cgc":
        grades = ["0.5", "1.0", "2.0", "3.0", "4.0", "5.0", "6.0", "7.0", "8.0", "8.5", "9.0", "9.2", "9.4", "9.6", "9.8", "10.0"]
    else:
        grades = ["Authentic", "Not Authentic"]

    # Distribution: more cards at mid-grades, fewer at extremes
    counts: list[int] = []
    for i, _ in enumerate(grades):
        # Bell curve-ish distribution
        mid = len(grades) // 2
        weight = max(1, 10 - abs(i - mid))
        counts.append(rng.randint(weight * 10, weight * 500))

    total = sum(counts)
    population = [
        PopulationEntry(
            grade=g,
            count=c,
            pct_of_total=round(c / total * 100, 1) if total > 0 else 0,
        )
        for g, c in zip(grades, counts)
    ]

    # Find the highest non-zero grade
    highest = grades[-1]
    for g, c in reversed(list(zip(grades, counts))):
        if c > 0:
            highest = g
            break

    # Average grade (numeric grades only)
    try:
        numeric_grades = [(float(p.grade), p.count) for p in population]
        weighted_sum = sum(g * c for g, c in numeric_grades)
        total_count = sum(c for _, c in numeric_grades)
        avg = round(weighted_sum / total_count, 2) if total_count > 0 else None
    except (ValueError, ZeroDivisionError):
        avg = None

    return PopulationReportResponse(
        item_name=item_name,
        category=category,
        service=service,
        total_graded=total,
        population=population,
        avg_grade=avg,
        highest_grade=highest,
        last_updated="2026-02-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/lookup", response_model=GradingLookupResponse)
async def grading_lookup(
    cert_number: str = Query(..., min_length=1, max_length=20, description="Certification number"),
    service: str = Query(..., pattern="^(psa|cgc|bgs|beckett)$", description="Grading service"),
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_lookup_limit),
) -> GradingLookupResponse:
    """
    Look up a grading certification number.

    Returns the item name, grade, population at that grade, and verification status.
    Currently returns structured mock data; designed for easy swap to real API integrations.
    """
    logger.info("[grading] Cert lookup: cert=%s service=%s user=%s", cert_number, service, user_id)

    # Validate service exists
    if service not in GRADING_SERVICES:
        raise error_response(400, f"Unsupported grading service: {service}", code="VALIDATION_ERROR")

    # Strip non-alphanumeric characters from cert number
    clean_cert = "".join(c for c in cert_number if c.isalnum())
    if not clean_cert:
        raise error_response(400, "Invalid certification number", code="VALIDATION_ERROR")

    # TODO: Replace with real API calls when keys are available
    # Example swap point:
    #   if service == "psa":
    #       return await _psa_api_lookup(clean_cert)
    #   elif service == "cgc":
    #       return await _cgc_api_lookup(clean_cert)
    result = _mock_cert_lookup(clean_cert, service)
    return result


@router.get("/population", response_model=PopulationReportResponse)
async def grading_population(
    item_name: str = Query(..., min_length=1, max_length=200, description="Item name to look up"),
    category: str = Query(..., description="Category ID"),
    service: str = Query(default="psa", pattern="^(psa|cgc|bgs|beckett)$", description="Grading service"),
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_lookup_limit),
) -> PopulationReportResponse:
    """
    Get population report for an item (how many graded at each level).

    Currently returns structured mock data; designed for easy swap to real API integrations.
    """
    if category not in GRADING_ELIGIBLE_CATEGORIES:
        raise error_response(
            400,
            f"Category '{category}' is not eligible for grading. Eligible: {', '.join(sorted(GRADING_ELIGIBLE_CATEGORIES))}",
            code="VALIDATION_ERROR",
        )

    logger.info("[grading] Population report: item=%s category=%s service=%s", item_name, category, service)

    # TODO: Replace with real population database queries
    result = _mock_population_report(item_name, category, service)
    return result


@router.get("/services", response_model=GradingServicesResponse)
async def list_grading_services(
    category: Optional[str] = Query(default=None, description="Filter services by category"),
    user_id: str = Depends(get_current_user_id),
) -> GradingServicesResponse:
    """
    List available grading services with submission links.

    Optionally filter by category to show only relevant services.
    """
    services: list[GradingServiceInfo] = []
    for svc_id, svc in GRADING_SERVICES.items():
        # Filter by category if specified
        if category and category not in svc["categories"]:
            continue
        services.append(
            GradingServiceInfo(
                id=svc_id,
                name=svc["name"],
                short_name=svc["short_name"],
                website=svc["website"],
                submission_url=svc["submission_url"],
                grade_scale=svc["grade_scale"],
                categories=svc["categories"],
                turnaround=svc["turnaround"],
                price_range=svc["price_range"],
            )
        )

    return GradingServicesResponse(
        services=services,
        eligible_categories=sorted(GRADING_ELIGIBLE_CATEGORIES),
    )
