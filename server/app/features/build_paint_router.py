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
    "keycaps": {
        "id": "keycaps",
        "display_name": "Custom Keyboards / Keycaps",
        "steps": [
            {"id": "kc-1", "label": "Layout planning & parts inventory", "order": 1},
            {"id": "kc-2", "label": "PCB & plate assembly", "order": 2},
            {"id": "kc-3", "label": "Stabilizer tuning & lubing", "order": 3},
            {"id": "kc-4", "label": "Switch lubing & filming", "order": 4},
            {"id": "kc-5", "label": "Switch installation", "order": 5},
            {"id": "kc-6", "label": "Foam & dampening installation", "order": 6},
            {"id": "kc-7", "label": "Keycap mounting & alignment", "order": 7},
            {"id": "kc-8", "label": "Sound testing & final tuning", "order": 8},
        ],
    },
    "designer_toys": {
        "id": "designer_toys",
        "display_name": "Designer Toys",
        "steps": [
            {"id": "dt-1", "label": "Unboxing & inspection", "order": 1},
            {"id": "dt-2", "label": "Surface cleaning & prep", "order": 2},
            {"id": "dt-3", "label": "Custom paint planning & masking", "order": 3},
            {"id": "dt-4", "label": "Base coat application", "order": 4},
            {"id": "dt-5", "label": "Detail painting & accents", "order": 5},
            {"id": "dt-6", "label": "Dry brushing & weathering (optional)", "order": 6},
            {"id": "dt-7", "label": "Sealing & clear coat", "order": 7},
            {"id": "dt-8", "label": "Display setup & photography", "order": 8},
        ],
    },
    "diecast": {
        "id": "diecast",
        "display_name": "Diecast Models",
        "steps": [
            {"id": "dc-1", "label": "Inspection & reference gathering", "order": 1},
            {"id": "dc-2", "label": "Disassembly (body, chassis, interior)", "order": 2},
            {"id": "dc-3", "label": "Stripping factory paint (if repainting)", "order": 3},
            {"id": "dc-4", "label": "Custom paint & color coats", "order": 4},
            {"id": "dc-5", "label": "Detailing & weathering", "order": 5},
            {"id": "dc-6", "label": "Decal & tampo application", "order": 6},
            {"id": "dc-7", "label": "Reassembly & final fit", "order": 7},
            {"id": "dc-8", "label": "Display case setup & photography", "order": 8},
        ],
    },
}


# Category-specific project status pipelines
# Each status has: id (stored in DB), label (displayed), order, color_hint
STATUS_PIPELINES: Dict[str, List[Dict[str, Any]]] = {
    "warhammer": [
        {"id": "wishlist", "label": "Wishlist", "order": 0, "color_hint": "muted"},
        {"id": "purchased", "label": "Purchased", "order": 1, "color_hint": "info"},
        {"id": "unassembled", "label": "Unassembled", "order": 2, "color_hint": "info"},
        {"id": "assembled", "label": "Assembled", "order": 3, "color_hint": "warning"},
        {"id": "primed", "label": "Primed", "order": 4, "color_hint": "warning"},
        {"id": "battle_ready", "label": "Battle Ready", "order": 5, "color_hint": "accent"},
        {"id": "parade_ready", "label": "Parade Ready", "order": 6, "color_hint": "accent"},
        {"id": "finished", "label": "Finished", "order": 7, "color_hint": "success"},
    ],
    "scale_models": [
        {"id": "wishlist", "label": "Wishlist", "order": 0, "color_hint": "muted"},
        {"id": "purchased", "label": "Purchased", "order": 1, "color_hint": "info"},
        {"id": "unassembled", "label": "Unassembled", "order": 2, "color_hint": "info"},
        {"id": "assembled", "label": "Assembled", "order": 3, "color_hint": "warning"},
        {"id": "primed", "label": "Primed", "order": 4, "color_hint": "warning"},
        {"id": "painted", "label": "Painted", "order": 5, "color_hint": "accent"},
        {"id": "weathered", "label": "Weathered", "order": 6, "color_hint": "accent"},
        {"id": "decaled", "label": "Decaled", "order": 7, "color_hint": "accent"},
        {"id": "finished", "label": "Finished", "order": 8, "color_hint": "success"},
    ],
    "gunpla": [
        {"id": "wishlist", "label": "Wishlist", "order": 0, "color_hint": "muted"},
        {"id": "purchased", "label": "Purchased", "order": 1, "color_hint": "info"},
        {"id": "unassembled", "label": "On Sprue", "order": 2, "color_hint": "info"},
        {"id": "assembled", "label": "Snap Built", "order": 3, "color_hint": "warning"},
        {"id": "primed", "label": "Primed", "order": 4, "color_hint": "warning"},
        {"id": "painted", "label": "Painted", "order": 5, "color_hint": "accent"},
        {"id": "decaled", "label": "Decaled", "order": 6, "color_hint": "accent"},
        {"id": "top_coated", "label": "Top Coated", "order": 7, "color_hint": "accent"},
        {"id": "finished", "label": "Finished", "order": 8, "color_hint": "success"},
    ],
    "lego": [
        {"id": "wishlist", "label": "Wishlist", "order": 0, "color_hint": "muted"},
        {"id": "purchased", "label": "Purchased", "order": 1, "color_hint": "info"},
        {"id": "sealed", "label": "Sealed (Investment)", "order": 2, "color_hint": "info"},
        {"id": "in_progress", "label": "Building", "order": 3, "color_hint": "warning"},
        {"id": "built", "label": "Built", "order": 4, "color_hint": "accent"},
        {"id": "modified", "label": "Modified / MOC", "order": 5, "color_hint": "accent"},
        {"id": "displayed", "label": "Displayed", "order": 6, "color_hint": "success"},
    ],
    "keycaps": [
        {"id": "wishlist", "label": "Wishlist", "order": 0, "color_hint": "muted"},
        {"id": "purchased", "label": "Parts Ordered", "order": 1, "color_hint": "info"},
        {"id": "parts_received", "label": "Parts Received", "order": 2, "color_hint": "info"},
        {"id": "lubing", "label": "Lubing & Modding", "order": 3, "color_hint": "warning"},
        {"id": "assembled", "label": "Assembled", "order": 4, "color_hint": "accent"},
        {"id": "tuned", "label": "Tuned & Sound Tested", "order": 5, "color_hint": "accent"},
        {"id": "finished", "label": "Finished", "order": 6, "color_hint": "success"},
    ],
    "designer_toys": [
        {"id": "wishlist", "label": "Wishlist", "order": 0, "color_hint": "muted"},
        {"id": "purchased", "label": "Purchased", "order": 1, "color_hint": "info"},
        {"id": "unboxed", "label": "Unboxed", "order": 2, "color_hint": "info"},
        {"id": "customizing", "label": "Customizing", "order": 3, "color_hint": "warning"},
        {"id": "painted", "label": "Painted", "order": 4, "color_hint": "accent"},
        {"id": "sealed", "label": "Sealed & Protected", "order": 5, "color_hint": "accent"},
        {"id": "displayed", "label": "Displayed", "order": 6, "color_hint": "success"},
    ],
    "diecast": [
        {"id": "wishlist", "label": "Wishlist", "order": 0, "color_hint": "muted"},
        {"id": "purchased", "label": "Purchased", "order": 1, "color_hint": "info"},
        {"id": "stock", "label": "Stock / Unmodified", "order": 2, "color_hint": "info"},
        {"id": "disassembled", "label": "Disassembled", "order": 3, "color_hint": "warning"},
        {"id": "painted", "label": "Repainted", "order": 4, "color_hint": "accent"},
        {"id": "detailed", "label": "Detailed & Weathered", "order": 5, "color_hint": "accent"},
        {"id": "finished", "label": "Finished", "order": 6, "color_hint": "success"},
    ],
    "generic": [
        {"id": "wishlist", "label": "Wishlist", "order": 0, "color_hint": "muted"},
        {"id": "purchased", "label": "Purchased", "order": 1, "color_hint": "info"},
        {"id": "in_progress", "label": "In Progress", "order": 2, "color_hint": "warning"},
        {"id": "finished", "label": "Finished", "order": 3, "color_hint": "success"},
    ],
}

# Terminal (finished) statuses per category
FINISHED_STATUSES = {"finished", "completed", "displayed"}


@router.get("/status-pipelines")
async def list_status_pipelines(_rl: None = Depends(_build_paint_limit)) -> Dict[str, Any]:
    """Return all category-specific status pipelines."""
    return STATUS_PIPELINES


@router.get("/status-pipelines/{category_id}")
async def get_status_pipeline(category_id: str, _rl: None = Depends(_build_paint_limit)) -> List[Dict[str, Any]]:
    """Return status pipeline for a specific category. Falls back to generic."""
    pipeline = STATUS_PIPELINES.get(category_id)
    if not pipeline:
        pipeline = STATUS_PIPELINES.get("generic")
    if not pipeline:
        raise error_response(404, "Pipeline not found")
    return pipeline


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
