"""The buyer gallery contract: hero first, no duplicates, never a NULL.

WHY THIS EXISTS

`ListingOut.image_url` and `ListingOut.image_urls` are produced by DIFFERENT
expressions. The hero has its own COALESCE precedence —

    items.image_url  >  first item_images row  >  category_items.image_url

— while the gallery is an `array_agg` over `item_images` alone. So the hero is
NOT guaranteed to be the first gallery element: an item whose own `image_url`
is set outranks every `item_images` row.

Two derivations of one fact drift, and the drift here is visible: the listing
tile shows `image_url` and the detail screen opens on `image_urls[0]`, so a
mismatch means the photo a buyer taps is not the photo they land on.
`_gallery()` is the single place that reconciles them, and these cases pin it.

Also covered: `item_images` has had 0 rows in prod since the table was rebuilt
(P2P spec §1f), so the EMPTY-gallery fallback is not an edge case — it is what
every one of the 29 live listings hits today. A listing with a perfectly good
photo must not return an empty gallery.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.p2p_listing_router import _gallery  # noqa: E402


class TestGalleryOrdering:
    def test_hero_first_when_already_first(self):
        assert _gallery("a", ["a", "b", "c"]) == ["a", "b", "c"]

    def test_hero_promoted_and_not_duplicated(self):
        """items.image_url outranks item_images, so the hero can be mid-array."""
        assert _gallery("b", ["a", "b", "c"]) == ["b", "a", "c"]

    def test_hero_absent_from_gallery_is_prepended(self):
        """The catalogue hero is in no item_images row at all."""
        assert _gallery("z", ["a", "b"]) == ["z", "a", "b"]


class TestGalleryFallbacks:
    def test_empty_gallery_still_returns_the_hero(self):
        """The live case: 0 rows in item_images, one photo on the item."""
        assert _gallery("a", []) == ["a"]

    def test_null_gallery_still_returns_the_hero(self):
        assert _gallery("a", None) == ["a"]

    def test_no_hero_returns_the_gallery_unchanged(self):
        assert _gallery(None, ["a", "b"]) == ["a", "b"]

    def test_nothing_at_all_is_empty_not_none(self):
        """The FE reads `.length`; None would throw where [] renders a placeholder."""
        assert _gallery(None, None) == []


class TestGalleryNulls:
    def test_nulls_inside_the_gallery_are_dropped(self):
        """A NULL url would render as a broken frame the buyer can swipe onto."""
        assert _gallery("a", ["a", None, "b"]) == ["a", "b"]

    def test_gallery_of_only_nulls_collapses_to_empty(self):
        assert _gallery(None, [None, None]) == []

    def test_empty_string_hero_is_not_treated_as_a_photo(self):
        assert _gallery("", ["a"]) == ["a"]
