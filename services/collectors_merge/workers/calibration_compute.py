from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import numpy as np
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]


def db():
    return psycopg2.connect(DATABASE_URL)


def run():
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
          select e.item_id,
                 (regexp_replace(e.label, 'sale_price:',''))::numeric as actual,
                 pp.q10, pp.q50, pp.q90
          from public.feedback e
          join lateral (
            select q10, q50, q90 from public.price_predictions p
            where p.item_id = e.item_id order by p.asof desc limit 1
          ) pp on true
          where e.label like 'sale_price:%%'
        """
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    if not rows:
        rep = {
            "coverage_q10_q90": None,
            "ace": None,
            "n": 0,
            "asof": datetime.now(timezone.utc).isoformat() + "Z",
        }
        with open("calibration_report.json", "w") as f:
            f.write(json.dumps(rep, indent=2))
        logger.info("no rows; wrote empty report")
        return

    actual = np.array([float(r["actual"]) for r in rows])
    q10 = np.array([float(r["q10"]) for r in rows])
    q90 = np.array([float(r["q90"]) for r in rows])
    q50 = np.array([float(r["q50"]) for r in rows])
    picp = float(np.mean((actual >= q10) & (actual <= q90)))
    ace = float(np.mean(np.abs(q50 - actual) / np.maximum(1.0, actual)))
    rep = {
        "coverage_q10_q90": round(picp, 4),
        "ace": round(ace, 4),
        "n": int(len(rows)),
        "asof": datetime.now(timezone.utc).isoformat() + "Z",
    }
    with open("calibration_report.json", "w") as f:
        f.write(json.dumps(rep, indent=2))
    logger.info("wrote calibration_report.json: %s", rep)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [calibration] %(levelname)s: %(message)s")
    run()
