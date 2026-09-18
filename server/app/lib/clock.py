"""One definition of "today" for the server.

The box is **Europe/Paris (CEST, +0200)** and Postgres is **UTC** (measured on
production 2026-09-18), so `date.today()` and `CURRENT_DATE` are different dates
between 00:00 and 02:00 CEST — two hours every night.

`events_core.py` used both for the SAME predicate: the main list bound
`date.today()` into `date >= $N` while the nearby-events query wrote
`date >= CURRENT_DATE`. In that window an event happening today was still listed
as upcoming on one screen and already dropped from the other.

`docs/ARCHITECTURE.md` already settles the direction — *"Derive it in SQL pinned
to UTC instead"* — so:

* **In SQL, write `CURRENT_DATE`.** It needs no parameter and cannot disagree
  with the rest of the statement.
* **In Python, call `utc_today()`.** Only for a date that is NOT going into a
  comparison the database also makes.

What is deliberately NOT converted: `gamification_router`'s streak dates. Those
bind `today` as `$3` and compare `last_activity_date` against `$3` — never
against `CURRENT_DATE` — so the write and the comparison already agree. Moving
them to UTC would shift every member's streak boundary by two hours and disagree
with every row already stored. They carry a `tz-ok:` marker saying so.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


def utc_today() -> date:
    """Today in UTC — the same day Postgres's CURRENT_DATE reports."""
    return datetime.now(timezone.utc).date()
