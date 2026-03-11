"""
Build & Paint — step template endpoints.
Read-only reference data with rate limiting.
"""

from fastapi import APIRouter, Depends
from typing import List, Dict, Any

from app.errors import error_response
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/build-paint", tags=["Build & Paint"])

_build_paint_limit = per_user_rate_limit(30, window_seconds=60, scope="build_paint")

# Step templates (mirrors build_step_templates DB table + frontend constants)
STEP_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "warhammer": {
        "id": "warhammer",
        "display_name": "Warhammer Miniatures",
        "steps": [
            {"id": "wh-1", "label": "Unbox & inspect sprues", "order": 1},
            {"id": "wh-2", "label": "Clean mold lines & flash", "order": 2},
            {"id": "wh-3", "label": "Dry-fit & plan assembly", "order": 3},
            {"id": "wh-4", "label": "Assemble / sub-assemblies", "order": 4},
            {"id": "wh-5", "label": "Prime (zenithal or flat)", "order": 5},
            {"id": "wh-6", "label": "Base colors", "order": 6},
            {"id": "wh-7", "label": "Washes & shading", "order": 7},
            {"id": "wh-8", "label": "Layer highlights", "order": 8},
            {"id": "wh-9", "label": "Details (eyes, gems, metallics)", "order": 9},
            {"id": "wh-10", "label": "Basing", "order": 10},
            {"id": "wh-11", "label": "Varnish & seal", "order": 11},
            {"id": "wh-12", "label": "Photography & display", "order": 12},
        ],
    },
    "gunpla": {
        "id": "gunpla",
        "display_name": "Gunpla / Model Kits",
        "steps": [
            {"id": "gp-1", "label": "Unbox & organize runners", "order": 1},
            {"id": "gp-2", "label": "Nub removal & cleanup", "order": 2},
            {"id": "gp-3", "label": "Test fit / dry assembly", "order": 3},
            {"id": "gp-4", "label": "Panel line scribing (optional)", "order": 4},
            {"id": "gp-5", "label": "Surface prep & sanding", "order": 5},
            {"id": "gp-6", "label": "Primer coat", "order": 6},
            {"id": "gp-7", "label": "Base paint / color separation", "order": 7},
            {"id": "gp-8", "label": "Detail painting", "order": 8},
            {"id": "gp-9", "label": "Decals / waterslide", "order": 9},
            {"id": "gp-10", "label": "Panel lining", "order": 10},
            {"id": "gp-11", "label": "Top coat / clear coat", "order": 11},
            {"id": "gp-12", "label": "Final assembly & posing", "order": 12},
        ],
    },
    "lego": {
        "id": "lego",
        "display_name": "LEGO",
        "steps": [
            {"id": "lg-1", "label": "Unbox & verify all numbered bags", "order": 1},
            {"id": "lg-2", "label": "Sort pieces by bag number", "order": 2},
            {"id": "lg-3", "label": "Minifigure assembly", "order": 3},
            {"id": "lg-4", "label": "Build booklet 1 (base structure)", "order": 4},
            {"id": "lg-5", "label": "Build booklet 2 (mid sections)", "order": 5},
            {"id": "lg-6", "label": "Build booklet 3+ (upper / details)", "order": 6},
            {"id": "lg-7", "label": "Sticker / printed tile application", "order": 7},
            {"id": "lg-8", "label": "Technic functions test (if applicable)", "order": 8},
            {"id": "lg-9", "label": "Light kit installation (optional)", "order": 9},
            {"id": "lg-10", "label": "Missing pieces check & order", "order": 10},
            {"id": "lg-11", "label": "Final inspection & tightening", "order": 11},
            {"id": "lg-12", "label": "Display setup & photography", "order": 12},
        ],
    },
    "scale_models": {
        "id": "scale_models",
        "display_name": "Scale Models",
        "steps": [
            {"id": "sm-1", "label": "Research & reference gathering", "order": 1},
            {"id": "sm-2", "label": "Dry fit & test assembly", "order": 2},
            {"id": "sm-3", "label": "Cockpit / interior detail", "order": 3},
            {"id": "sm-4", "label": "Main assembly", "order": 4},
            {"id": "sm-5", "label": "Filling & sanding seams", "order": 5},
            {"id": "sm-6", "label": "Primer coat", "order": 6},
            {"id": "sm-7", "label": "Pre-shading", "order": 7},
            {"id": "sm-8", "label": "Base camouflage / color", "order": 8},
            {"id": "sm-9", "label": "Decals & markings", "order": 9},
            {"id": "sm-10", "label": "Weathering (washes, chipping, streaking)", "order": 10},
            {"id": "sm-11", "label": "Clear coat", "order": 11},
            {"id": "sm-12", "label": "Final details (antenna, lights, rigging)", "order": 12},
        ],
    },
    "generic": {
        "id": "generic",
        "display_name": "Generic / Other",
        "steps": [
            {"id": "gen-1", "label": "Preparation & planning", "order": 1},
            {"id": "gen-2", "label": "Assembly", "order": 2},
            {"id": "gen-3", "label": "Surface prep", "order": 3},
            {"id": "gen-4", "label": "Priming", "order": 4},
            {"id": "gen-5", "label": "Base coating", "order": 5},
            {"id": "gen-6", "label": "Detailing", "order": 6},
            {"id": "gen-7", "label": "Finishing & sealing", "order": 7},
        ],
    },
}


@router.get("/step-templates")
async def list_step_templates(_rl: None = Depends(_build_paint_limit)) -> List[Dict[str, Any]]:
    """Return all available step templates."""
    return list(STEP_TEMPLATES.values())


@router.get("/step-templates/{category_id}")
async def get_step_template(category_id: str, _rl: None = Depends(_build_paint_limit)) -> Dict[str, Any]:
    """Return step template for a specific category. Falls back to generic."""
    template = STEP_TEMPLATES.get(category_id)
    if not template:
        template = STEP_TEMPLATES.get("generic")
    if not template:
        raise error_response(404, "Template not found")
    return template
