#!/usr/bin/env python3
"""
Audit env vars the server READS against what production actually SETS.

A missing env var almost never errors here. The code reads it, gets "" or None,
and takes a degraded path: an affiliate link ships without its tag and earns
nothing, an API client falls back to keyless mode, a Stripe checkout builds
with an empty price id. Same silent-failure shape as everything else in this
codebase — the feature looks present and simply does not work.

2026-07-25 first run: 16 affiliate IDs empty (every affiliate link earning EUR
0), PRICECHARTING_API_KEY empty (running keyless, which returns cross-category
false positives), all 8 STRIPE_PRICE_ID_* empty, REDIS_URL empty.

Every var must be in exactly one of three buckets:
  1. set in production
  2. EXPECTED_EMPTY   deliberately unset, WITH a reason
  3. otherwise        a finding
So a newly-read var cannot silently join the pile.

Usage:  python3 server/scripts/audit_env_coverage.py [--json]
Run on EC2 so /opt/collectors/.env is loaded.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
# Only vars read WITHOUT a fallback matter. `os.getenv("ANOMALY_Z", "3")` has a
# code default, so empty is the intended state and flagging it is pure noise --
# 202 findings, of which the ~16 that cost real money were invisible. A var read
# with no default is one whose absence the code cannot compensate for.
NO_DEFAULT_RE = re.compile(
    r"""os\.(?:getenv\(\s*["']([A-Z][A-Z0-9_]{3,})["']\s*\)"""     # getenv("X")  no 2nd arg
    r"""|environ\[\s*["']([A-Z][A-Z0-9_]{3,})["']\s*\]"""            # environ["X"]
    r"""|environ\.get\(\s*["']([A-Z][A-Z0-9_]{3,})["']\s*\))"""     # environ.get("X")
)

# Words the regex can pick up that are not env vars.
NOISE = {"TRUE", "FALSE", "NONE", "UTF", "POST", "JSON", "HTTP", "HTTPS", "NULL",
         "DEBUG", "INFO", "ERROR", "WARNING", "SELECT", "INSERT", "WHERE"}

# Deliberately unset in production, each with the reason. An entry is a
# decision; anything else empty is a finding.
EXPECTED_EMPTY: dict[str, str] = {
    "REDIS_URL": "No Redis in this deployment; callers fall back to in-process caching.",
    # SENTRY_DSN is set in production — kept out of EXPECTED_EMPTY so the stale
    # check stays meaningful.
    "DEV_USER_ID": "DEV_MODE is false in production, so the dev-user path is unreachable.",

    # -- third-party credentials we do not hold an account for (2026-08-08) ---
    # Each was checked individually rather than blanket-documented: the reason
    # has to be TRUE, or this list becomes the thing that stops the next
    # investigation (see audit_rls_coverage.py, where user_notifications was
    # excused with a false justification and sat unread for seven months).
    #
    # These all degrade to keyless/disabled rather than erroring, which is
    # exactly why they need a line here instead of being noticed in a year.
    "ANTHROPIC_API_KEY": "claude_estimator.py:477 guards on it and falls back to the Ridge model. Deliberately unset — the paid-scraper/LLM killswitch (project_paid_scraper_killswitches).",
    "BRICKLINK_CONSUMER_KEY": "No BrickLink developer account. The adapter degrades to keyless; lego supply comes from ebay (3,201 buyable rows, 7d).",
    "CARDMARKET_APP_TOKEN": "No Cardmarket API account. config.py:252 defaults it to ''. Cardmarket rows are scraped via Firecrawl, and are price-only (0 buyable) regardless.",
    "DISCOGS_TOKEN": "Dead var — no server code reads it. DISCOGS_AFFILIATE_TOKEN is the one actually used, and it IS set. Remove on the next config sweep.",
    "PRICECHARTING_API_KEY": "No PriceCharting subscription; the caller runs keyless behind the console guard (learning_keyless_pricecharting_needs_console_guard).",
    "STOCKX_API_KEY": "No StockX API account. Sneaker/collectible supply comes from ebay instead.",
    "TCGPLAYER_BEARER_TOKEN": "No TCGplayer API account. Its 256,848 rows arrive via scrape and are price-only (0 buyable), so a token would not change alert coverage.",

    # -- not credentials -----------------------------------------------------
    "DATABASE_URL": "Alembic CONSTRUCTS this in migrations/env.py from DB_USER/DB_PASS/DB_HOST/DB_PORT/DB_NAME; it is never read from the environment at runtime.",
    "MATVIEW_REFRESH_INTERVAL": "Read only by test_production_hardening.py as an escape hatch for the interval assertions. No production code path.",
}


def read_vars() -> set[str]:
    found: set[str] = set()
    for path in SERVER.rglob("*.py"):
        rel = str(path.relative_to(SERVER.parent))
        # Tests and e2e fixtures read service-role keys behind `or` fallbacks;
        # requiring them here only adds noise to a check whose value is that a
        # hit means a PRODUCTION path silently degraded.
        if "__pycache__" in rel or ".venv" in rel or rel.startswith("server/tests/"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for m in NO_DEFAULT_RE.finditer(text):
                name = next((g for g in m.groups() if g), None)
                if not name:
                    continue
                # `os.environ.get("A") or os.environ["B"]` has a fallback: the
                # absence of A is compensated, so it is not a finding.
                tail = text[m.end():m.end() + 12]
                if tail.lstrip().startswith(("or ", "or\n")):
                    continue
                found.add(name)
        except OSError:
            continue
    return {v for v in found if v not in NOISE}


def main() -> int:
    names = sorted(read_vars())
    empty = [n for n in names if not os.environ.get(n)]
    findings = [n for n in empty if n not in EXPECTED_EMPTY]
    stale = sorted(k for k in EXPECTED_EMPTY if os.environ.get(k))

    # Group findings so the output is scannable rather than a wall of names.
    def group(n: str) -> str:
        if "AFFILIATE" in n:
            return "affiliate (link ships untagged -> EUR 0 earned)"
        if "STRIPE" in n:
            return "stripe (checkout builds with an empty price id)"
        if n.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_KEY")):
            return "credential (client silently degrades to keyless/disabled)"
        return "other"

    if "--json" in sys.argv:
        print(json.dumps({"read": len(names), "empty": empty, "findings": findings,
                          "stale_expected_empty": stale}, indent=2))
    else:
        print("\n=== env coverage: read by code vs set in production ===\n")
        print(f"  read WITHOUT a code default  : {len(names)}")
        print(f"  empty in this environment    : {len(empty)}")
        print(f"  documented as expected-empty : {len(empty) - len(findings)}")
        print(f"  UNDOCUMENTED empty           : {len(findings)}\n")
        buckets: dict[str, list[str]] = {}
        for n in findings:
            buckets.setdefault(group(n), []).append(n)
        for b in sorted(buckets):
            print(f"  -- {b}")
            for n in sorted(buckets[b]):
                print(f"       {n}")
            print()
        for s in stale:
            print(f"    STALE  {s} is documented as expected-empty but is now set")
        if not findings and not stale:
            print("    clean — every var read by the server is set or documented\n")

    return 1 if (findings or stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
