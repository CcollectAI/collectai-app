"""Tests for app/features/build_paint_router.py — step template endpoints.

Build & Paint router serves static step template data.
No auth or DB required.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")

from starlette.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# GET /build-paint/step-templates — list all templates
# ---------------------------------------------------------------------------

class TestListStepTemplates:
    def test_list_step_templates_returns_200(self):
        """Returns 200 with a list of all step templates."""
        resp = client.get("/build-paint/step-templates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 5  # warhammer, gunpla, lego, scale_models, generic

    def test_list_step_templates_has_expected_categories(self):
        """Verify all 5 expected template categories are present."""
        resp = client.get("/build-paint/step-templates")
        data = resp.json()
        ids = {t["id"] for t in data}
        assert "warhammer" in ids
        assert "gunpla" in ids
        assert "lego" in ids
        assert "scale_models" in ids
        assert "generic" in ids

    def test_list_step_templates_structure(self):
        """Each template has id, display_name, and steps."""
        resp = client.get("/build-paint/step-templates")
        data = resp.json()
        for template in data:
            assert "id" in template
            assert "display_name" in template
            assert "steps" in template
            assert isinstance(template["steps"], list)
            assert len(template["steps"]) > 0
            # Each step has id, label, order
            for step in template["steps"]:
                assert "id" in step
                assert "label" in step
                assert "order" in step


# ---------------------------------------------------------------------------
# GET /build-paint/step-templates/{category_id} — get specific template
# ---------------------------------------------------------------------------

class TestGetStepTemplate:
    def test_get_warhammer_template(self):
        """Returns warhammer template with 12 steps."""
        resp = client.get("/build-paint/step-templates/warhammer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "warhammer"
        assert data["display_name"] == "Warhammer Miniatures"
        assert len(data["steps"]) == 12

    def test_get_gunpla_template(self):
        """Returns gunpla template with 12 steps."""
        resp = client.get("/build-paint/step-templates/gunpla")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "gunpla"
        assert len(data["steps"]) == 12

    def test_get_lego_template(self):
        """Returns lego template with 8 steps."""
        resp = client.get("/build-paint/step-templates/lego")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "lego"
        assert len(data["steps"]) == 8

    def test_get_generic_template(self):
        """Returns generic template with 7 steps."""
        resp = client.get("/build-paint/step-templates/generic")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "generic"
        assert len(data["steps"]) == 7

    def test_get_unknown_category_falls_back_to_generic(self):
        """Unknown category returns the generic template as fallback."""
        resp = client.get("/build-paint/step-templates/unknown_category")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "generic"

    def test_step_order_is_sequential(self):
        """Steps should have sequential order values starting from 1."""
        resp = client.get("/build-paint/step-templates/warhammer")
        data = resp.json()
        orders = [s["order"] for s in data["steps"]]
        assert orders == list(range(1, len(orders) + 1))
