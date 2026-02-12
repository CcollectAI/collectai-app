import datetime as dt
import logging
import os

import requests

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def upsert_eval(cat, ver, metrics, n):
    url = f"{SUPABASE_URL}/rest/v1/model_evals?on_conflict=category,model_version"
    r = requests.post(
        url,
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
        json={
            "category": cat,
            "model_version": ver,
            "mae": metrics["mae"],
            "mape": metrics.get("mape"),
            "p50": metrics.get("p50"),
            "p90": metrics.get("p90"),
            "sample_size": int(n),
            # timezone-aware UTC (no deprecation)
            "evaluated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
        timeout=30,
    )
    if not r.ok:
        raise SystemExit(f"HTTP {r.status_code} → {r.text}")
    return r.json() if r.text else {"status": r.status_code}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    out = upsert_eval(
        cat="pokemon",
        ver="v0.1.0",
        metrics={"mae": 12.34, "mape": 0.11, "p50": 10.0, "p90": 20.0},
        n=123,
    )
    logger.info("%s", out)
