"""
Affiliate Link Builder.

Turns a marketplace URL into one that earns Sparrow Collect a commission when
the user buys, and carries a per-click **sub-ID** so a network's conversion
report can be joined back to the deal / user that produced the sale (see
docs/AFFILIATE_SWITCH_ON.md → reconciliation).

A network is tagged only when BOTH hold:
  1. its env var is set, and the value has the shape that network issues, and
  2. we have checked the network's link format against its own docs.
Anything else returns the URL unchanged: an untagged link still works, while a
link built to a format the network does not read LOOKS earning and pays €0.

Link formats (checked 2026-09-28):
  - ``epn``        — eBay Partner Network. Params appended to the eBay URL:
                     mkcid=1, mkrid=<rotation id of THAT eBay site>, campid,
                     customid (sub-ID), toolid, mkevt. The env var is the
                     10-digit campaign id.
  - ``impact``     — impact.com. The env var is the tracking link the Impact
                     dashboard issues (``https://<brand>.pxf.io/c/<pub>/<ad>/<prog>``);
                     we add ``u=<url>`` (deep link) and ``subId1=<sub-ID>``.
  - ``partnerize`` — Partnerize. The env var is ``https://prf.hn/click/camref:<id>``;
                     we add ``/pubref:<sub-ID>/destination:<url>``. pubref
                     must precede destination or it lands on the shop's URL.

No link-level programme exists for Cardmarket (signup referral only, capped at
€10/month), Discogs or BrickLink, so they have no env var.

KEH, MPB, Master of Malt, PopMart, Drop, Chrono24 and AmiAmi run on networks
(ShareASale, FlexOffers, Sovrn, Affiliate Future, Digidip, direct) whose link
format has not been checked. Their env vars are read but never applied; a set
value logs a warning. To enable one: copy a deep link from the network's
dashboard at enrollment, add its format here, and a test for it.

Usage:
    url, source = build_affiliate_url("https://www.ebay.com/itm/12345", "ebay")
    url, source = build_affiliate_url(listing_url, "ebay", subid=deal_id)
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote, urlencode, urlparse, parse_qs, urlunparse

from app.config import (
    EBAY_AFFILIATE_CAMPAIGN_ID,
    TCGPLAYER_AFFILIATE_ID,
    MERCARI_AFFILIATE_ID,
    STOCKX_AFFILIATE_ID,
    WHATNOT_AFFILIATE_ID,
    CATAWIKI_AFFILIATE_ID,
    KEH_AFFILIATE_ID,
    MPB_AFFILIATE_ID,
    MASTEROFMALT_AFFILIATE_ID,
    POPMART_AFFILIATE_ID,
    DROP_AFFILIATE_ID,
    CHRONO24_AFFILIATE_ID,
    AMIAMI_AFFILIATE_ID,
)

logger = logging.getLogger(__name__)


_ALLOWED_SCHEMES = {"http", "https"}

# Fallback sub-ID when the caller has no per-click identifier to attribute.
_DEFAULT_SUBID = "sparrow"

# source → (link format, name of the module-level env value, reported source).
# The value is looked up by NAME at call time so tests can patch it.
_PROGRAMMES: dict[str, tuple[str, str, str]] = {
    "ebay": ("epn", "EBAY_AFFILIATE_CAMPAIGN_ID", "ebay_partner_network"),
    "tcgplayer": ("impact", "TCGPLAYER_AFFILIATE_ID", "tcgplayer_affiliate"),
    "stockx": ("impact", "STOCKX_AFFILIATE_ID", "stockx"),
    "whatnot": ("impact", "WHATNOT_AFFILIATE_ID", "whatnot"),
    "mercari": ("impact", "MERCARI_AFFILIATE_ID", "mercari"),
    "catawiki": ("partnerize", "CATAWIKI_AFFILIATE_ID", "catawiki"),
}

# Enrolled-but-unchecked: read so a set value is noticed, never applied.
_UNVERIFIED: dict[str, str] = {
    "keh": "KEH_AFFILIATE_ID",
    "mpb": "MPB_AFFILIATE_ID",
    "masterofmalt": "MASTEROFMALT_AFFILIATE_ID",
    "popmart": "POPMART_AFFILIATE_ID",
    "drop": "DROP_AFFILIATE_ID",
    "chrono24": "CHRONO24_AFFILIATE_ID",
    "amiami": "AMIAMI_AFFILIATE_ID",
}

# The shape of the value each network issues. A bare id pasted where a
# tracking link belongs would otherwise build a broken link.
_VALUE_SHAPE = {
    "epn": re.compile(r"^\d{10}$"),
    "impact": re.compile(r"^https://[a-z0-9.-]+/c/\d+/\d+/\d+/?$"),
    "partnerize": re.compile(r"^https://prf\.hn/click/camref:[A-Za-z0-9]+/?$"),
}

# EPN rotation id per eBay site. The link must carry the id of the site it
# opens; an eBay host missing from this table is left untagged.
_EPN_ROTATION_IDS = {
    "ebay.com": "711-53200-19255-0",
    "ebay.co.uk": "710-53481-19255-0",
    "ebay.de": "707-53477-19255-0",
    "ebay.nl": "1346-53482-19255-0",
    "ebay.fr": "709-53476-19255-0",
    "ebay.it": "724-53478-19255-0",
    "ebay.es": "1185-53479-19255-0",
    "ebay.be": "1553-53471-19255-0",
    "ebay.at": "5221-53469-19255-0",
    "ebay.ch": "5222-53480-19255-0",
    "ebay.ie": "5282-53468-19255-0",
    "ebay.ca": "706-53473-19255-0",
    "ebay.com.au": "705-53470-19255-0",
}

# Shop host → source. The HOST decides the programme when it names one: a
# scraper row (source 'crawl4ai' / 'firecrawl') that points at catawiki.com is
# a Catawiki link, and a row labelled 'tcgplayer' that points elsewhere is not.
_PROGRAMME_HOSTS = {
    "tcgplayer.com": "tcgplayer",
    "stockx.com": "stockx",
    "whatnot.com": "whatnot",
    "mercari.com": "mercari",
    "catawiki.com": "catawiki",
}

_warned: set[str] = set()


def _source_from_host(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if host == "ebay.com" or host.startswith("ebay.") or ".ebay." in host:
        return "ebay"
    for shop_host, source in _PROGRAMME_HOSTS.items():
        if host == shop_host or host.endswith("." + shop_host):
            return source
    return None


def _warn_once(key: str, msg: str, *args: object) -> None:
    if key not in _warned:
        _warned.add(key)
        logger.warning(msg, *args)


def build_affiliate_url(
    original_url: str,
    source: str,
    subid: str | None = None,
) -> tuple[str, str]:
    """Build an affiliate-tagged URL for a marketplace listing.

    Args:
        original_url: The original listing URL.
        source: Marketplace identifier ('ebay', 'tcgplayer', 'catawiki', etc.)
        subid: Optional per-click tracking token (e.g. a deal_id) used for
            conversion attribution. Defaults to the brand slug.

    Returns:
        Tuple of (affiliate_url, affiliate_source).
        If no checked programme is configured for the source,
        returns (original_url, '').
    """
    if not original_url or not source:
        return original_url or "", ""

    # Scheme validation — reject non-HTTP(S) URLs to prevent open redirect
    parsed = urlparse(original_url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        logger.warning("Rejected non-HTTP URL scheme: %s", parsed.scheme)
        return original_url, ""

    sub = subid or _DEFAULT_SUBID
    source_lower = _source_from_host(original_url) or source.lower()

    unverified_var = _UNVERIFIED.get(source_lower)
    if unverified_var:
        if globals()[unverified_var]:
            _warn_once(
                unverified_var,
                "%s is set but its link format is unchecked; %s links ship untagged",
                unverified_var, source_lower,
            )
        return original_url, ""

    programme = _PROGRAMMES.get(source_lower)
    if programme is None:
        return original_url, ""
    fmt, var, reported = programme
    value = globals()[var]
    if not value:
        return original_url, ""
    if not _VALUE_SHAPE[fmt].match(value):
        _warn_once(var, "%s does not look like a %s value; %s links ship untagged",
                   var, fmt, source_lower)
        return original_url, ""

    if fmt != "epn" and _source_from_host(original_url) != source_lower:
        # A network deep link is only honoured for the brand's own domain.
        return original_url, ""

    if fmt == "epn":
        tagged = _tag_epn(original_url, value, sub)
    elif fmt == "impact":
        tagged = _wrap_impact(original_url, value, sub)
    else:
        tagged = _wrap_partnerize(original_url, value, sub)
    if tagged is None:
        return original_url, ""
    return tagged, reported


def _tag_epn(url: str, campaign_id: str, subid: str) -> str | None:
    """Append eBay Partner Network params, with the rotation id of the URL's site."""
    # Already an eBay-issued EPN link for OUR campaign (Browse's
    # itemAffiliateWebUrl, which eBay says to use for API listings). Keep
    # eBay's own params (toolid=10049 etc.) and set only our per-click sub-id;
    # re-tagging would overwrite them with the hand-built 10001 set.
    if parse_qs(urlparse(url).query).get("campid") == [campaign_id]:
        return _append_params(url, {"customid": subid})
    host = (urlparse(url).hostname or "").lower()
    for prefix in ("www.", "m.", "befr.", "benl."):
        if host.startswith(prefix):
            host = host[len(prefix):]
            break
    rotation_id = _EPN_ROTATION_IDS.get(host)
    if rotation_id is None:
        _warn_once(f"epn:{host}", "No EPN rotation id for eBay host %r; link ships untagged", host)
        return None
    return _append_params(url, {
        "mkcid": "1",
        "mkrid": rotation_id,
        "campid": campaign_id,
        "customid": subid,
        "toolid": "10001",
        "mkevt": "1",
    })


def _wrap_impact(url: str, tracking_link: str, subid: str) -> str:
    """Deep-link through an Impact tracking link."""
    return tracking_link.rstrip("/") + "?" + urlencode({"u": url, "subId1": subid})


def _wrap_partnerize(url: str, click_link: str, subid: str) -> str:
    """Deep-link through a Partnerize click link; pubref before destination."""
    return f"{click_link.rstrip('/')}/pubref:{quote(subid, safe='')}/destination:{quote(url, safe='')}"


def _append_params(url: str, params: dict[str, str]) -> str:
    """Append query parameters to a URL, preserving existing params."""
    parsed = urlparse(url)
    existing = parse_qs(parsed.query, keep_blank_values=True)

    # Merge — new params override if key already exists
    for k, v in params.items():
        existing[k] = [v]

    # Rebuild query string
    flat: list[tuple[str, str]] = []
    for k, vals in existing.items():
        for v in vals:
            flat.append((k, v))

    new_query = urlencode(flat)
    return urlunparse(parsed._replace(query=new_query))
