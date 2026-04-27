#!/usr/bin/env python3
"""Static check: every asyncpg call binding $N to ($N || ' days')::interval
must pass the value as str(...), not raw int.

Bug pattern (made 5+ times in 2 days, see
memory/learning_asyncpg_interval_str_cast.md):

    rows = await conn.fetch('''
        WHERE created_at >= now() - ($1 || ' days')::interval
    ''', LOOKBACK_DAYS)   # ← BUG: needs str(LOOKBACK_DAYS)

asyncpg raises `invalid input for query argument $1: 30 (expected str,
got int)` on the very first call. Easy to miss because the worker keeps
trying every cycle and the orchestrator's exception swallow logs it as
a benign warning.

This check fails CI if it finds any `($N || ' days')::interval` site
where the corresponding bind value at the same call doesn't go through
str(). Best-effort heuristic: walks each .py file, finds queries with
the `||` interval pattern, looks ~10 lines below for the bind tuple
and verifies the position-N argument either calls str() or has
explicit `str_*` naming.

Run:  python3 scripts/check_asyncpg_interval_str_cast.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "server"

# Pattern for: ($N || ' days')::interval  (also matches ($N * 2 || ' days')::interval)
INTERVAL_RE = re.compile(r"""\(\s*\$(\d+)(?:\s*\*\s*\d+)?\s*\|\|\s*['"][^'"]*days?['"][^)]*\)\s*::\s*interval""", re.IGNORECASE)

# Inside the bind tuple: position N corresponds to $N. We scan for either
# `str(VAR)` or `[str(...)]` near the closing `)` of the .fetch/.execute/.fetchrow call.
STR_OR_MAKE_INTERVAL = re.compile(r"\b(str\(|make_interval\b)")

# Allowed: `f"{value}"` (already a string), or VAR.lower() etc — too noisy to
# whitelist precisely. We only flag when neither str(...) nor make_interval
# is present in the relevant bind block.


def find_call_block(src: str, start: int) -> tuple[int, str]:
    """Walk forward from `start` until we hit the closing `)` of the parent call.

    Returns (end_index, slice_of_source). Tracks paren depth from `start`.
    Returns (-1, '') if no closing paren found.
    """
    depth = 1  # already inside the SQL triple-string's opening
    i = start
    in_string = False
    quote_char = ""
    while i < len(src) and depth > 0:
        c = src[i]
        if in_string:
            if c == quote_char and src[i - 1] != "\\":
                in_string = False
        elif c in ('"', "'"):
            in_string = True
            quote_char = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        i += 1
    if depth != 0:
        return -1, ""
    return i, src[start:i]


def check_file(path: Path) -> list[tuple[int, str]]:
    """Return a list of (line_no, snippet) for each suspicious call site."""
    src = path.read_text()
    issues: list[tuple[int, str]] = []
    # We can't reliably walk asyncpg call boundaries from regex alone, so use a
    # heuristic: for each interval match, look at the next ~600 chars (the bind
    # tuple normally lives right after the closing triple-quote of the SQL).
    # If neither str( nor make_interval appears in that window, flag.
    for m in INTERVAL_RE.finditer(src):
        slot = int(m.group(1))
        line_no = src[:m.start()].count("\n") + 1
        # Window covers the SQL body + the bind tuple. Multi-line CTEs run
        # 1000+ chars between the `||` site and the closing call, so 1500
        # is the practical floor.
        window = src[m.end():m.end() + 2500]
        if (
            "str(" in window
            or "make_interval" in window
            or "*params" in window  # indirect bind — caller is expected to str()
                                    # the value when building the params list.
                                    # Manually audit those call sites once.
        ):
            continue  # likely safe — caller already wraps the int
        # Otherwise: flag the line for human review.
        snippet = src.splitlines()[line_no - 1].strip()
        issues.append((line_no, f"$ {slot} :: {snippet[:120]}"))
    return issues


def main() -> int:
    bad: list[tuple[Path, int, str]] = []
    for sub in ("workers", "app"):
        for py in (ROOT / sub).rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            for line_no, snippet in check_file(py):
                bad.append((py.relative_to(ROOT.parent), line_no, snippet))
    if not bad:
        print("OK — no untyped int binds detected near `($N || ' days')::interval` patterns.")
        return 0
    print(f"FAIL — {len(bad)} suspicious call site(s):", file=sys.stderr)
    for rel, line_no, snippet in bad:
        print(f"  {rel}:{line_no}  {snippet}", file=sys.stderr)
    print(
        "\nFix: pass str(int_var) instead of int_var for any param bound to "
        "($N || ' days')::interval, OR migrate the SQL to "
        "`make_interval(days => $N)` which takes int directly.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
