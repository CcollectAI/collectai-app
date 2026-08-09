"""One place that turns a DB row into something `json.dumps` can handle.

Why this module exists
----------------------
Three routers had each hand-rolled the same loop, and one of them was wrong for
as long as it had existed::

    for k, v in row.items():
        if hasattr(v, "isoformat"):
            row[k] = v.isoformat()
        elif hasattr(v, "hex"):          # meant for UUID / bytes
            row[k] = str(v)

**Floats have a .hex() method.** ``(642.64).hex() == '0x1.4147ae147ae14p+9'``,
so the second branch swallowed every float in the result set and ``str()``'d it.
``/search/unified`` shipped ``"642.64"`` where the client tests
``typeof priceEur === 'number'``, and every priced row rendered "No price yet" —
a live feature that looked exactly like missing data (fixed 2026-08-09,
commit fe3b143).

The lesson is not "handle floats". It is that a **conversion** must ask
*what IS this?* (``isinstance``) and never *does this quack?* (``hasattr``).
``hasattr`` widens itself to every future type that happens to share a method
name, so the blast radius grows without anyone editing the line. With
``isinstance``, a new type has to be handled on purpose.

Duplicating this loop is the other half of the bug: a fix lands on one copy and
silently misses the others (learning_duplicate_impl_silently_drops_the_fix).
Call these helpers instead. ``scripts/check-duck-typed-serialization.mjs``
(``npm run check:serialization``) fails the build if the hand-rolled shape comes
back.

Conversions
-----------
==========================================  ==========================
``datetime`` / ``date`` / ``time``          ISO-8601 string
``uuid.UUID`` / ``bytes`` / ``bytearray``   ``str(v)``
``Decimal``                                 ``float(v)``
``dict`` / ``list`` / ``tuple``             converted element-wise
everything else                             passed through untouched
==========================================  ==========================

``float`` is deliberately absent from that table: it is already JSON, and
turning it into anything else is the bug this module was written to prevent.

``Decimal`` becomes ``float`` because every consumer of a price in this codebase
already treats it as a number. That trades exactness for usability, which is the
right call for display values and the wrong one for ledger arithmetic — do money
math in ``Decimal`` server-side and only pass through here at the response seam.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

# datetime is a subclass of date, so isinstance covers both in one tuple.
_TEMPORAL = (datetime, date, time)
_STRINGY = (uuid.UUID, bytes, bytearray, memoryview)


def json_safe_value(v: Any) -> Any:
    """Convert one value into something ``json.dumps`` accepts.

    Recurses into containers: a ``Decimal`` nested inside a ``jsonb`` dict is
    just as unserialisable as a top-level one, and previously raised a 500 at
    the encoder instead of being caught here.
    """
    if isinstance(v, _TEMPORAL):
        return v.isoformat()
    if isinstance(v, _STRINGY):
        return str(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, dict):
        return {k: json_safe_value(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [json_safe_value(x) for x in v]
    return v


def json_safe_row(row: dict) -> dict:
    """Return a new dict with every value made JSON-safe."""
    return {k: json_safe_value(v) for k, v in row.items()}


def json_safe_rows(rows: list) -> list:
    """Return a new list of JSON-safe dicts.

    Accepts anything dict-like per row (``asyncpg.Record`` included), so callers
    can drop the ``[dict(r) for r in rows]`` step.
    """
    return [json_safe_row(dict(r)) for r in rows]
