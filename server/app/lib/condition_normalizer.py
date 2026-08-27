"""Normalise the free-text `condition` on a market hit to a closed set.

WHY (2026-08-27)
----------------
Serious collectors value a card by pulling sold comps **filtered to a matching
grade** — a PSA 8 and a PSA 10 of the same card differ by five to ten times, and
mixing raw with certified comps is the single most-cited way an automated
valuation loses credibility.

We cannot do that yet, and measuring said why. `market_hits.condition` is
populated on 2,927,536 of 2,927,565 sold comps in the last 90 days — 100%. But:

* **2,926,015 of them are the literal string `NM`**, written by the bulk TCG
  feeds which assume Near Mint for everything. So the column is a CONSTANT, not
  a signal, and filtering on it today would change nothing.
* The remainder is unnormalised across case AND language:
  `New` / `new` / `Brand New` / `New/Factory Sealed` / `Neu`,
  `used` / `Used`, `Ungraded` / `Nicht bewertet`, `complete-in-box`, `Graded`.
  Grade-matching would fail on capitalisation before it ever reached semantics.

So this is deliberately **prep, not a behaviour change**. It gives the write
path one vocabulary so that when graded comps do start arriving — from eBay
Marketplace Insights, or from our own members marking sales — grade-matched
comps become a query rather than a data-cleaning project. Nothing filters on
`condition_norm` yet, and valuation is untouched.

THE CLOSED SET
--------------
Four buckets plus an explicit unknown. Kept small on purpose: every value a
writer can emit is a value some reader has to handle, and
`learning_keyword_filters_need_per_category_false_positive_audit` is about what
happens when a vocabulary grows by accident.

    graded:<company>:<grade>   a certified card, e.g. "graded:psa:9"
    sealed                     factory sealed / unopened
    raw                        an ungraded single in stated condition
    used                       pre-owned non-card goods (figures, consoles)
    unknown                    nothing usable was said

`raw` carries no grade letter on purpose. `NM`/`LP`/`MP` are a SELLER's claim
about an ungraded card, not a certification, and treating a seller's "NM" as
comparable to a PSA 9 is the raw-vs-certified conflation this module exists to
make possible to avoid.
"""
from __future__ import annotations

import re
from typing import Optional

# Grading companies we recognise, longest-first so "bgs" cannot match inside
# a longer token before the longer one is tried.
_GRADERS = ("psa", "bgs", "cgc", "sgc", "ace", "tag")

# Multi-language. Every entry below was observed in the live column, not
# imagined: `Neu` and `Nicht bewertet` are German rows from a real adapter.
_SEALED = {
    "sealed", "factory sealed", "new/factory sealed", "brand new", "new",
    "neu", "nieuw", "scellé", "nuovo", "unopened", "mint sealed",
}
_USED = {
    "used", "gebraucht", "gebruikt", "pre-owned", "preowned", "second hand",
    "complete-in-box", "complete in box", "cib", "loose",
    # "unsealed" is an OPENED item, i.e. the opposite of sealed. Listed here
    # explicitly rather than left to the substring guard below: the guard only
    # fires once a token has already matched on a word boundary, and "sealed"
    # inside "unsealed" does not, so it fell through to `unknown` — safe, but
    # less informative than the seller actually was.
    "unsealed", "opened", "open box",
}
# Ungraded singles: the seller's own grade claim. Mapped to `raw`, NOT kept as
# a grade — see the module docstring.
_RAW = {
    "nm", "near mint", "mint", "m", "lp", "lightly played", "ex", "excellent",
    "mp", "moderately played", "hp", "heavily played", "gd", "good", "played",
    "poor", "damaged", "ungraded", "nicht bewertet", "raw", "vg", "very good",
}

UNKNOWN = "unknown"


def normalize_condition(raw: Optional[str]) -> str:
    """Map a free-text condition to the closed set. Never raises."""
    if not raw:
        return UNKNOWN
    s = str(raw).strip().lower()
    if not s:
        return UNKNOWN

    # 1. Certified grade first — it is the most specific claim, and a title can
    #    legitimately contain both "PSA 9" and "mint".
    #    Matches "psa 9", "psa9", "PSA 10", "bgs 9.5".
    m = re.search(r"\b(%s)\s*[-:]?\s*(10|\d(?:\.5)?)\b" % "|".join(_GRADERS), s)
    if m:
        grade = m.group(2)
        # "9.0" and "9" are the same grade; normalise the trailing zero away so
        # the two cannot form separate buckets.
        if grade.endswith(".0"):
            grade = grade[:-2]
        return f"graded:{m.group(1)}:{grade}"

    # A grader named with no number is a claim of certification without a
    # grade. It is NOT raw, and it is not a specific grade either.
    if any(re.search(r"\b%s\b" % g, s) for g in _GRADERS) or s == "graded":
        return "graded:unknown:unknown"

    if s in _SEALED:
        return "sealed"
    if s in _USED:
        return "used"
    if s in _RAW:
        return "raw"

    # Substring fallbacks, applied ONLY after the exact-match sets, and only on
    # word boundaries. `learning_keyword_filters_need_per_category_false_
    # positive_audit`: "sealed" inside "unsealed" would otherwise invert the
    # meaning, and plain `in` matching is what put "tin" inside "Sting".
    for token, bucket in (("sealed", "sealed"), ("new", "sealed"),
                          ("used", "used"), ("mint", "raw"), ("played", "raw")):
        if re.search(r"(^|[^a-z])%s([^a-z]|$)" % token, s):
            # "unsealed"/"not sealed" must not read as sealed.
            if bucket == "sealed" and re.search(r"\b(un|not)\s*-?\s*sealed\b", s):
                return "used"
            return bucket

    return UNKNOWN
