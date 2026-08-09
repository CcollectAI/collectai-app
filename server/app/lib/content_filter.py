"""Filter objectionable text before it is published to other members.

Apple App Review Guideline 1.2 asks apps with user-generated content for four
things. Sparrow had three of them — a report path, blocking, and a zero-tolerance
EULA clause. This is the fourth: "a method for filtering objectionable material
from being posted to the app". Its absence was an App Review exposure, and once
the Acceptable Use Policy and Marketplace Terms started asserting a
zero-tolerance stance the gap got worse: the documents claimed a standard the
code did not enforce.

## What this is, and firmly is not

It is a **cheap, deterministic pre-publication check** on short seller-authored
strings: listing titles, descriptions and condition notes. It rejects a small
set of unambiguous slurs and hard-prohibited content, and it is not a
moderation system. Real moderation is the DSA Art 16 report path plus the Art 17
decision endpoint, which already exist and which a human drives.

Deliberately NOT attempted here:

* **Cleverness.** No leetspeak normalisation, no ML classifier, no
  fuzzy matching. Each of those trades a small recall gain for false positives,
  and a false positive here silently blocks a member from selling a legitimate
  item — the failure this codebase pays for most often. A determined abuser
  routes around any wordlist; the report path is what catches them.
* **Profanity policing.** Swearing is not objectionable content. Filtering it
  would reject "this thing is in shit condition", which is an honest and useful
  description. Only slurs and hard-prohibited categories are listed.
* **Silence.** A rejection returns the offending term so the seller can fix
  their listing. Rejecting with a generic message is how a user concludes the
  app is broken and stops trying.

## Word boundaries matter more than the list

Substring matching is what produces the Scunthorpe problem — a naive `in` check
rejects "Scunthorpe", "Sussex", "assassin", "classic". Matching is therefore on
WORD BOUNDARIES only, which is also why the list can stay short and readable.
`test_content_filter.py` pins those exact false-positive cases; if the matching
is ever loosened they fail.
"""
from __future__ import annotations

import re
from typing import Optional

# Slurs and hard-prohibited content only. Kept short on purpose — see the module
# docstring. Lowercase; matching is case-insensitive and boundary-anchored.
#
# The sexual-content entries exist because listing titles are shown in a browse
# grid to every member including minors (the app is 13+/16+ EU), and the
# marketplace terms already prohibit them.
_BLOCKED = {
    # racial / ethnic slurs
    "nigger", "nigga", "chink", "spic", "kike", "gook", "wetback", "coon",
    # homophobic / transphobic slurs
    "faggot", "fag", "tranny", "dyke",
    # ableist slur
    "retard", "retarded",
    # prohibited sale categories the marketplace terms already name
    "childporn", "cp", "loli", "shota",
}

# Word-boundary match, case-insensitive. Built once — recompiling per call on a
# create-listing path is waste, and this is called on every publish.
_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(_BLOCKED)) + r")\b",
    re.IGNORECASE,
)


def find_blocked_term(*texts: Optional[str]) -> Optional[str]:
    """Return the first blocked term found across `texts`, else None.

    Returns the TERM rather than a bool so the caller can tell the user what to
    change. Accepts several fields so one call covers a whole listing.
    """
    for text in texts:
        if not text:
            continue
        m = _PATTERN.search(text)
        if m:
            return m.group(1).lower()
    return None
