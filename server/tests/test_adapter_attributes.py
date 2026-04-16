"""
Tests for attribute extraction in marketplace adapters (eBay, Mercari US, Vinted).

Verifies that each adapter's normalize function populates the ``attributes`` key
with expected canonical fields from raw API-style fixture data.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# eBay Browse — _extract_browse_attrs
# ---------------------------------------------------------------------------

class TestEbayExtractBrowseAttrs:
    """Unit tests for app.agents.adapters.ebay_caller._extract_browse_attrs."""

    @staticmethod
    def _fn():
        from app.agents.adapters.ebay_caller import _extract_browse_attrs
        return _extract_browse_attrs

    def test_condition_extracted(self):
        fn = self._fn()
        attrs = fn({"condition": "Used"})
        assert attrs["condition"] == "Used"

    def test_condition_from_conditionId(self):
        fn = self._fn()
        attrs = fn({"conditionId": "3000"})
        assert attrs["condition"] == "3000"

    def test_localized_aspects_brand(self):
        fn = self._fn()
        item = {
            "localizedAspects": [
                {"name": "Brand", "value": "Nintendo"},
                {"name": "Year", "value": "1999"},
                {"name": "Color", "value": "Red"},
            ]
        }
        attrs = fn(item)
        assert attrs["brand"] == "Nintendo"
        assert attrs["year"] == "1999"
        assert attrs["color"] == "Red"

    def test_card_number_mapping(self):
        fn = self._fn()
        item = {"localizedAspects": [{"name": "Card Number", "value": "4"}]}
        attrs = fn(item)
        assert attrs["card_number"] == "4"

    def test_unknown_aspects_go_to_raw(self):
        fn = self._fn()
        item = {"localizedAspects": [{"name": "Weird Field", "value": "abc"}]}
        attrs = fn(item)
        assert "weird_field" in attrs.get("attributes_raw", {})

    def test_empty_item_returns_empty(self):
        fn = self._fn()
        assert fn({}) == {}

    def test_category_path(self):
        fn = self._fn()
        attrs = fn({"categoryPath": "Toys > Action Figures"})
        assert attrs["attributes_raw"]["ebay_category_path"] == "Toys > Action Figures"

    def test_null_aspect_values_skipped(self):
        fn = self._fn()
        item = {"localizedAspects": [{"name": "Brand", "value": None}]}
        attrs = fn(item)
        assert "brand" not in attrs

    def test_grade_mapping(self):
        fn = self._fn()
        item = {"localizedAspects": [{"name": "Professional Grader", "value": "PSA"}]}
        attrs = fn(item)
        assert attrs["grade"] == "PSA"


# ---------------------------------------------------------------------------
# Mercari US — _normalize_item attribute extraction
# ---------------------------------------------------------------------------

class TestMercariUSAttributes:
    """Verify that Mercari US _normalize_item populates hit['attributes']."""

    @staticmethod
    def _fn():
        from app.agents.adapters.mercari_us_caller import _normalize_item
        return _normalize_item

    def test_basic_attrs(self):
        fn = self._fn()
        item = {
            "id": "m123",
            "name": "Test Item",
            "price": 10.0,
            "itemConditionId": 2,
            "brandName": "Bandai",
        }
        hit = fn(item)
        assert "attributes" in hit
        assert hit["attributes"]["condition"] == "Like New"
        assert hit["attributes"]["brand"] == "Bandai"

    def test_no_attrs_returns_empty_dict(self):
        fn = self._fn()
        item = {"id": "m999", "name": "No Attrs", "price": 5.0}
        hit = fn(item)
        assert isinstance(hit.get("attributes", {}), dict)

    def test_size_extracted(self):
        fn = self._fn()
        item = {"id": "m1", "name": "T", "price": 1, "size": "Medium"}
        hit = fn(item)
        assert hit["attributes"].get("size") == "Medium"

    def test_color_extracted(self):
        fn = self._fn()
        item = {"id": "m2", "name": "T", "price": 1, "color": "Blue"}
        hit = fn(item)
        assert hit["attributes"].get("color") == "Blue"

    def test_tags_go_to_raw(self):
        fn = self._fn()
        item = {"id": "m3", "name": "T", "price": 1, "tags": [{"name": "Vintage"}]}
        hit = fn(item)
        raw = hit["attributes"].get("attributes_raw", {})
        assert "mercari_tags" in raw


# ---------------------------------------------------------------------------
# Vinted — _normalize_item attribute extraction
# ---------------------------------------------------------------------------

class TestVintedAttributes:
    """Verify that Vinted _normalize_item populates hit['attributes']."""

    @staticmethod
    def _fn():
        from app.agents.adapters.vinted_caller import _normalize_item
        return _normalize_item

    def test_condition_mapped(self):
        fn = self._fn()
        item = {"id": 1, "title": "T", "price": {"amount": 10, "currency_code": "EUR"}, "status_id": 3}
        hit = fn(item)
        assert hit["attributes"]["condition"] == "Very Good"

    def test_brand_extracted(self):
        fn = self._fn()
        item = {"id": 2, "title": "T", "price": 5, "brand_title": "Nike"}
        hit = fn(item)
        assert hit["attributes"]["brand"] == "Nike"

    def test_catalog_id_in_raw(self):
        fn = self._fn()
        item = {"id": 3, "title": "T", "price": 5, "catalog_id": 42}
        hit = fn(item)
        raw = hit["attributes"].get("attributes_raw", {})
        assert raw.get("vinted_catalog_id") == 42

    def test_empty_attrs_when_no_facets(self):
        fn = self._fn()
        item = {"id": 4, "title": "T", "price": 5}
        hit = fn(item)
        assert isinstance(hit.get("attributes", {}), dict)

    def test_size_extracted(self):
        fn = self._fn()
        item = {"id": 5, "title": "T", "price": 5, "size_title": "L"}
        hit = fn(item)
        assert hit["attributes"]["size"] == "L"
