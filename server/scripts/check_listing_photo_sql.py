#!/usr/bin/env python3
"""
Fail if a listing query writes its own photo expression.

WHY: the rule for "which photo does a listing show" was written FOUR times.
The detail endpoint gained an `item_images` arm; browse, favourites and
watchlist-matches did not. Measured on prod 2026-09-12: 4 of 4 active listings
had 3-8 photos each and the Marketplace grid rendered the empty placeholder for
every one of them.

`favorites_router.py` had ALREADY written the warning in a comment — "Two
copies of a photo rule drift, and the copy that drifts is the one nobody is
looking at" — and then drifted. A comment asserting sameness is not sameness.
`app/features/listing_photo_sql.py` is the one copy; this is what makes it so.

THE RULE
  A SQL string that joins `marketplace_listings` and aliases `AS image_url`
  must get that expression from the `{LISTING_IMAGE}` token, and the literal
  must be wrapped in `with_listing_photo(...)`. Both halves matter: the token
  alone would ship the literal text `{LISTING_IMAGE}` into Postgres, and the
  wrapper alone proves nothing about what it substituted.

Exit 1 = a violation. Exit 2 = could not run (a file would not parse), which
must not read as PASS.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # server/
TOKEN = "{LISTING_IMAGE}"
WRAPPER = "with_listing_photo"

# The module that DEFINES the expression, and this checker, obviously contain
# it. Path-based, so neither can be mistaken for a call site.
EXEMPT = {
    ROOT / "app" / "features" / "listing_photo_sql.py",
    ROOT / "scripts" / "check_listing_photo_sql.py",
}

# Not every `AS image_url` over marketplace_listings is the display rule.
# `_photo_catalogue_hook` reads the photo to CONTRIBUTE to the catalogue, and
# deliberately omits the ci.image_url arm: copying the catalogue's own image
# back into the catalogue is a no-op that looks like progress. That is a
# different question with a different correct answer, and this checker cannot
# tell the two apart from shape alone.
#
# So an exception must SAY what it is, inside the SQL, and the reason travels
# with the query rather than living in a list here that rots:
#
#     -- listing-photo-sql:exempt contribution, seller's own photo only
#
# A bare marker is not enough — the checker requires words after it.
EXEMPT_MARKER = "listing-photo-sql:exempt"


def main() -> int:
    problems: list[str] = []
    scanned = 0

    for path in sorted(ROOT.rglob("*.py")):
        if path in EXEMPT or "__pycache__" in path.parts or "_bak" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as e:
            print(f"[listing-photo-sql] could not parse {path}: {e}", file=sys.stderr)
            return 2
        scanned += 1

        # Which literals sit inside a with_listing_photo(...) call?
        wrapped_ids: set[int] = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == WRAPPER and node.args
                    and isinstance(node.args[0], ast.Constant)):
                wrapped_ids.add(id(node.args[0]))

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            sql = node.value
            rel = path.relative_to(ROOT)

            joins_listings = "marketplace_listings" in sql
            aliases_image = "AS image_url" in sql

            if joins_listings and aliases_image:
                if EXEMPT_MARKER in sql:
                    # Split the LINE first, then strip. Stripping first walks
                    # onto the next line and happily reads someone else's
                    # comment as the reason — which is exactly how this passed
                    # its own mutation test on the first attempt.
                    reason = sql.split(EXEMPT_MARKER, 1)[1].split("\n")[0].strip()
                    if len(reason) < 12:
                        problems.append(
                            f"{rel}:{node.lineno} {EXEMPT_MARKER} with no reason — "
                            f"say why this query is not the display rule"
                        )
                    continue
                if TOKEN not in sql:
                    problems.append(
                        f"{rel}:{node.lineno} a marketplace_listings query aliases "
                        f"AS image_url without the {TOKEN} token — that is a FIFTH "
                        f"copy of the photo rule"
                    )
                elif id(node) not in wrapped_ids:
                    problems.append(
                        f"{rel}:{node.lineno} holds {TOKEN} but is not wrapped in "
                        f"{WRAPPER}(...) — Postgres would receive the literal token"
                    )
            elif TOKEN in sql and id(node) not in wrapped_ids:
                problems.append(
                    f"{rel}:{node.lineno} holds {TOKEN} but is not wrapped in "
                    f"{WRAPPER}(...)"
                )

    if problems:
        print(f"[listing-photo-sql] FAIL — {len(problems)} problem(s):", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    print(f"[listing-photo-sql] PASS — {scanned} file(s); "
          f"every listing photo comes from listing_photo_sql.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
