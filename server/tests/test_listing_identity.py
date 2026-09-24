"""Deal dedup keys a listing by identity, not by its decorated URL (2026-09-24)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.lib.listing_identity import listing_key  # noqa: E402

# Two real URLs for ONE eBay item, from two scans on prod (same item, new amdata).
A = ("https://www.ebay.com/itm/137771382482?_skw=Charizard+ex&hash=item2013d076d2:g:g64AAeSwlQNqtCMC"
     "&amdata=enc%3AAQALAAAA8ACCtXRWQnOEpyOq0JBkyE5928")
B = ("https://www.ebay.com/itm/137771382482?_skw=Charizard+ex&hash=item2013d076d2:g:g64AAeSwlQNqtCMC"
     "&amdata=enc%3AAQALAAAA8ACCtXRWQnOEpyOqvfMbY2RPQTw1w30YQbv6")


def test_one_ebay_item_is_one_key_across_scans():
    assert A != B
    assert listing_key(A) == listing_key(B) == "ebay:137771382482"


def test_ebay_item_same_across_country_sites_and_slug_form():
    assert listing_key("https://www.ebay.de/itm/137771382482") == "ebay:137771382482"
    assert listing_key("https://ebay.co.uk/itm/Charizard-ex-056/137771382482?var=1") == "ebay:137771382482"


def test_different_ebay_items_stay_different():
    assert listing_key("https://www.ebay.com/itm/137771382482") != listing_key("https://www.ebay.com/itm/137771382483")


def test_identity_in_the_query_is_kept_and_tracking_dropped():
    a = listing_key("https://shop.example/item?id=42&utm_source=x&gclid=1")
    b = listing_key("https://shop.example/item?id=42&utm_campaign=y")
    c = listing_key("https://shop.example/item?id=43&utm_source=x")
    assert a == b != c


def test_sparrow_listing_path_identity():
    assert listing_key("https://sparrowcollect.com/l/abc") == listing_key("https://www.sparrowcollect.com/l/abc/")


def test_empty():
    assert listing_key("") == "" and listing_key(None) == ""
