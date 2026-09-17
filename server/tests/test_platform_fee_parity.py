"""
The server, the app and the Terms must not disagree about the platform fee.

WHY (class sweep D, 2026-09-17): the 5% ticket fee was written SIX times — as
`int(ticket_price * 0.05)` in the ticket checkout, the same literal again in the
webhook that records what was charged, the organiser's hint under the ticket
price field, and twice in `app/legal/terms.tsx`. All six said 5%, which is how
this class always looks right up to the day someone changes one of them. Two of
the six are legal copy a member can hold us to, and one is what we actually
charge; a rate that drifts between those two is not a cosmetic bug.

Same arrangement as `test_currency_symbol_parity.py`: the constant lives on both
sides (`app.lib.money.PLATFORM_FEE_PCT` and `src/constants/fees.ts`), and this
test reads the TypeScript file so neither side can move alone. It also checks
that no NEW bare `* 0.05` fee literal has appeared next to the word fee, because
a seventh copy is how the sweep would have to happen again.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.lib.money import PLATFORM_FEE_PCT, platform_fee_cents

REPO = Path(__file__).resolve().parents[2]
FEES_TS = REPO / "src" / "constants" / "fees.ts"


def _client_pct() -> int:
    src = FEES_TS.read_text(encoding="utf-8")
    m = re.search(r"export const PLATFORM_FEE_PCT\s*=\s*(\d+(?:\.\d+)?)", src)
    assert m, f"PLATFORM_FEE_PCT not found in {FEES_TS}"
    value = float(m.group(1))
    return int(value) if value.is_integer() else value  # type: ignore[return-value]


def test_client_and_server_agree_on_the_rate() -> None:
    assert _client_pct() == PLATFORM_FEE_PCT


def test_fee_truncates_and_never_rounds_up_against_the_organiser() -> None:
    # 5% of 1999 cents is 99.95 — the organiser keeps the fraction.
    assert platform_fee_cents(1999) == 99
    assert platform_fee_cents(2000) == 100


def test_no_amount_means_no_fee() -> None:
    assert platform_fee_cents(0) == 0
    assert platform_fee_cents(None) == 0


def test_no_seventh_copy_of_the_rate() -> None:
    """No bare fee literal outside the two constants.

    Scans the server for `* 0.05`-style fee arithmetic and the client for a
    hard-coded "5% ... fee" sentence. The constants themselves are excluded by
    path; everything else must go through them.
    """
    offenders: list[str] = []

    for path in (REPO / "server" / "app").rglob("*.py"):
        if path.name == "money.py":
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\*\s*0\.0\d+", line) and re.search(r"fee", line, re.I):
                offenders.append(f"{path.relative_to(REPO)}:{i}  {line.strip()[:80]}")

    for sub in ("app", "src"):
        for path in (REPO / sub).rglob("*.tsx"):
            if "fees.ts" in path.name:
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                # BOTH orders: "5% platform fee" and "platform fee of 5%".
                # The first version only matched number→fee, so re-hard-coding
                # "A platform fee of 5% is applied" in the Terms went undetected.
                near = re.search(r"\b\d+(\.\d+)?%[^\n]{0,40}fee", line, re.I) or re.search(
                    r"fee[^\n]{0,40}\b\d+(\.\d+)?%", line, re.I
                )
                if near and "PLATFORM_FEE_PCT" not in line:
                    offenders.append(f"{path.relative_to(REPO)}:{i}  {line.strip()[:80]}")

    assert not offenders, "the platform fee is written somewhere else too:\n" + "\n".join(offenders)
