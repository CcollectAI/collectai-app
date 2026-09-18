#!/usr/bin/env python3
"""The server must not invent its own "today".

Measured on production 2026-09-18: the EC2 box is **Europe/Paris (CEST, +0200)**
and Postgres is **UTC**. So `date.today()` and `CURRENT_DATE` are different
dates between 00:00 and 02:00 CEST — two hours every night.

`events_core.py` used both for the SAME predicate: the list bound
`date.today()` into `date >= $N` while the nearby query wrote
`date >= CURRENT_DATE`, and `docs/EVENT_QUALITY_PLAN.md` names CURRENT_DATE as
the canonical gate for both. In that window an event happening today was still
upcoming on one screen and already gone from the other. `gamification_router`
had it too: a challenge ending today fell out of `start_date <= $2 AND
end_date >= $2`.

The rule, from `docs/ARCHITECTURE.md` — *"Derive it in SQL pinned to UTC
instead"*:

  * in SQL, write `CURRENT_DATE`; it binds nothing and cannot disagree with the
    rest of the statement;
  * in Python, call `app.lib.clock.utc_today()`.

A host-clock date that is genuinely right needs a reason on the line or just
above:

    # tz-ok: a lead-time score in whole days, never compared to a DB date

Not every one is a bug — the streak dates are written to AND compared against
`last_activity_date` and never meet `CURRENT_DATE`, so they cannot disagree with
the database, and moving them would shift every member's streak boundary. They
carry the marker and say so.

    python3 server/scripts/check_server_today.py    # 0 clean, 1 on findings
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = ["app", "workers"]

# A naive host-clock read. `datetime.now(timezone.utc)` and `datetime.now(tz)`
# are fine — only a bare call takes the box's idea of the time.
BARE = re.compile(r"\b(?:datetime\.)?date\.today\(\)|\bdatetime\.now\(\s*\)")
SKIP = {"app/lib/clock.py"}

findings = []
for base in SCAN:
    for f in sorted((ROOT / base).rglob("*.py")):
        rel = f.relative_to(ROOT).as_posix()
        if rel in SKIP:
            continue
        lines = f.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            # Strip BOTH comment styles. The first version stripped only `#`
            # and reported its own prose: a `-- CURRENT_DATE, not a bound
            # date.today()` note inside a triple-quoted SQL string matched.
            # A checker that reports the comment explaining the fix is failure
            # mode 1 of learning_four_ways_a_new_gate_is_wrong, and
            # check:cast-not-mapped hit it too.
            code = line.split("#", 1)[0].split("--", 1)[0]
            if not BARE.search(code):
                continue
            # 10 lines, not 4: these reasons need a paragraph, and the streak
            # note is seven lines long — a window shorter than the explanation
            # makes the marker unwritable where it is needed.
            near = "\n".join(lines[max(0, i - 10): i + 1])
            if "tz-ok:" in near:
                continue
            findings.append((rel, i + 1, line.strip()[:100]))

if findings:
    print(f"FAIL  {len(findings)} host-clock date(s) with no reason:")
    for rel, ln, txt in findings:
        print(f"   {rel}:{ln}")
        print(f"      {txt}")
    print()
    print("   In SQL use CURRENT_DATE; in Python use app.lib.clock.utc_today().")
    print("   Or add '# tz-ok: <why the host clock is right here>'.")
    sys.exit(1)

print("PASS  every server date comes from the database's clock, or says why not.")
