"""
ONE expression for "which photo does this listing show".

WHY (2026-09-12, found walking the Marketplace on Android): every tile in the
grid rendered the empty-image placeholder. Measured on prod the same minute —
4 of 4 active listings, each with 3 to 8 rows in `item_images`:

    listing                             items_img  item_images  browse_shows  detail_shows
    DEMO Lorcana Azurite Sea Booster B  f          8            f             t
    DEMO LEGO Millennium Falcon 75192   f          3            f             t
    DEMO Blue-Eyes White Dragon         f          4            f             t
    DEMO Charizard Base Set Holo        f          6            f             t

A marketplace where nothing has a picture, and every listing has pictures. Tap
a tile and the photo is there, because the DETAIL query coalesces through
`item_images` and the BROWSE query did not.

`marketplace_listings` has no image column of its own. A photo can be in three
places and the order matters:

  1. `items.image_url`      — the seller's primary thumbnail
  2. `item_images`          — what POST /items/{id}/images actually writes, and
                              it does NOT backfill items.image_url
  3. `category_items.image_url` — the catalogue stock shot, last resort

Miss (2) and a seller who uploaded photos through the documented route shows a
catalogue stock shot, labelled "Catalog photo" — the §1h misrepresentation,
caused by us — or, when there is no catalogue row either, nothing at all.

The rule was written FOUR times. The detail endpoint got the item_images fix;
browse, favourites and watchlist-matches kept the two-arm version. The comment
in favorites_router.py had already called it:

    "Two copies of a photo rule drift, and the copy that drifts is the one
     nobody is looking at."

Three of the four were the copy nobody was looking at. So there is one copy
now, and `npm run check:listing-photo-sql` fails the build if a fifth appears.

Every query using these requires the same three aliases: `l` (the listing, for
l.item_id), `i` (public.items), `ci` (public.category_items).
"""
from __future__ import annotations

# The photo a listing shows. See the three-place ordering above.
LISTING_IMAGE_SQL = """COALESCE(
                     i.image_url,
                     (SELECT im.image_url FROM public.item_images im
                       WHERE im.item_id = l.item_id
                       ORDER BY im.position, im.created_at LIMIT 1),
                     ci.image_url
                   )"""

# TRUE only when the photo on screen really is the catalogue's. This MUST stay
# in step with the expression above: label a seller's own photo "Catalog photo"
# and the listing misrepresents itself in the opposite direction.
LISTING_IMAGE_IS_CATALOG_SQL = """(i.image_url IS NULL
                    AND NOT EXISTS (SELECT 1 FROM public.item_images im
                                     WHERE im.item_id = l.item_id)
                    AND ci.image_url IS NOT NULL)"""


def with_listing_photo(sql: str) -> str:
    """
    Substitute the photo expressions into a query.

    A token rather than an f-string on purpose: the listing DETAIL query
    contains braces of its own, and making it an f-string would mean escaping
    unrelated text — a silent way to corrupt SQL that no test exercises. The
    token is substituted here and nowhere else.

    Raises if a token is still present afterwards or if neither was found, so a
    typo'd token fails at import instead of shipping a query with the literal
    string `{LISTING_IMAGE}` in its SELECT list.
    """
    out = (sql
           .replace("{LISTING_IMAGE_IS_CATALOG}", LISTING_IMAGE_IS_CATALOG_SQL)
           .replace("{LISTING_IMAGE}", LISTING_IMAGE_SQL))
    if out == sql:
        raise ValueError("with_listing_photo() found no {LISTING_IMAGE} token to substitute")
    if "{LISTING_IMAGE" in out:
        raise ValueError(f"unsubstituted photo token remains: {out[out.index('{LISTING_IMAGE'):][:48]}")
    return out
