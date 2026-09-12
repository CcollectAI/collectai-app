#!/usr/bin/env python3
"""A bound parameter whose FIRST use is interval arithmetic must be cast.

WHY (2026-09-12): `value_change_worker` failed EVERY run from at least
2026-09-05 to 2026-09-12 with

    UndefinedFunctionError: operator does not exist:
    timestamp with time zone > interval

on this line:

    AND pp.generated_at > $2 - interval '30 days'

asyncpg sends Parse with **unspecified** parameter types and lets Postgres
infer them. `$2 - interval '30 days'` is satisfiable as *interval minus
interval*, so Postgres typed `$2` as `interval` — and then `timestamptz >
interval` has no operator. The Python side binds a `datetime`, so nothing in
the code reads as wrong, and lint / `check_sql_columns` pass: every column name
in the query is real.

The only symptom was an hourly Telegram page saying `value_change_worker: 2
consecutive errors` — that it failed, never why, which `docs/WATCHDOG.md`
already names as its own defect class. Sweeping found a second copy in
`insights_digest_worker.py`, latent only because the weekly digest is dark.

WHY ORDER MATTERS — and why the naive version of this check was wrong

The first draft flagged four `gamification_router.py` lines:

    WHEN ... last_activity_date = $3 THEN ...
    WHEN ... last_activity_date = $3 - INTERVAL '1 day' THEN ...

All four are FINE, and prod says so. Postgres resolves a parameter at its
FIRST occurrence: the bare `= $3` against a `date` column pins `$3` to `date`,
after which `$3 - INTERVAL '1 day'` is `date - interval`. `value_change_worker`
has the same two shapes in the OPPOSITE order, which is exactly why it failed.

Proven against prod, both directions:

    pinning use first   -> PREPARE OK
    ambiguous use first -> ERROR: operator does not exist: date = interval

So the rule is narrow on purpose: flag a parameter only when its **first**
occurrence in that SQL string is uncast interval arithmetic. A gate whose
findings are mostly false is a gate nobody runs — this repo has that scar
already (`learning_the_gate_existed_and_was_never_run`).

    python3 server/scripts/check_param_interval_cast.py    # 0 clean, 1 found

Related: memory `learning_asyncpg_interval_str_cast` — the `($1 || ' days')`
variant of the same footgun.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # server/

PARAM = re.compile(r"\$(\d+)")
# `$2 - interval '30 days'` / `$2 + INTERVAL '1 day'`, with no cast on the bind.
AMBIGUOUS_AFTER = re.compile(r"^\s*[-+]\s*interval\b", re.I)
CAST_AFTER = re.compile(r"^\s*::\s*\w+")


def strip_sql_comments(sql: str) -> str:
    """Blank out `-- …` tails, keeping offsets stable for line reporting."""
    out = []
    for line in sql.split("\n"):
        head = line.split("--", 1)[0]
        out.append(head + " " * (len(line) - len(head)))
    return "\n".join(out)


def offending_params(sql: str):
    """Yield (param_number, line_offset_in_string, text) for uncast first uses."""
    cleaned = strip_sql_comments(sql)
    seen: set[str] = set()
    for m in PARAM.finditer(cleaned):
        num = m.group(1)
        if num in seen:
            continue  # only the FIRST occurrence decides the inferred type
        seen.add(num)
        rest = cleaned[m.end():]
        if CAST_AFTER.match(rest):
            continue  # explicitly pinned — the fix
        if AMBIGUOUS_AFTER.match(rest):
            line_no = cleaned[: m.start()].count("\n")
            text = sql.split("\n")[line_no].strip()
            yield num, line_no, text


def sql_strings(tree: ast.AST):
    """Every string constant that looks like SQL carrying a bound parameter."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if "$" in v and "interval" in v.lower():
                yield node, v


def main() -> int:
    hits = []
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in {".venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue  # this file quotes the broken form on purpose
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for node, sql in sql_strings(tree):
            for num, line_off, text in offending_params(sql):
                hits.append((path.relative_to(ROOT.parent),
                             (node.lineno or 1) + line_off, num, text))

    if not hits:
        print("[param-interval-cast] PASS — no bound parameter is first used in "
              "uncast interval arithmetic.")
        return 0

    print(f"[param-interval-cast] FAIL — {len(hits)} parameter(s) first used in "
          "uncast interval arithmetic.")
    print("Postgres infers the parameter as `interval` at its FIRST use, and the "
          "comparison then has no operator.")
    print("This fails at RUNTIME on the query's first execution; no column check "
          "can see it.\n")
    for path, lineno, num, text in hits:
        print(f"  {path}:{lineno}  ${num} in: {text}")
    print("\nFix: cast the bind at its first use — "
          "`$2::timestamptz - interval '30 days'`.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
