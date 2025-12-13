#!/usr/bin/env python3
import os, json
# AUTOLOAD_DB_ENV
import os, pathlib
for _cand in ("/etc/collectors/db.env", "ops/db.env"):
    _p = pathlib.Path(_cand)
    if _p.exists():
        for _ln in _p.read_text().splitlines():
            _ln=_ln.strip()
            if not _ln or _ln.startswith("#"): continue
            if "=" in _ln:
                _k,_v = _ln.split("=",1)
                os.environ.setdefault(_k.strip(), _v.strip())
        break
, argparse, glob, psycopg2
# AUTOLOAD_DB_ENV
import os, pathlib
for _cand in ("/etc/collectors/db.env", "ops/db.env"):
    _p = pathlib.Path(_cand)
    if _p.exists():
        for _ln in _p.read_text().splitlines():
            _ln=_ln.strip()
            if not _ln or _ln.startswith("#"): continue
            if "=" in _ln:
                _k,_v = _ln.split("=",1)
                os.environ.setdefault(_k.strip(), _v.strip())
        break

from datetime import datetime, timezone
from decimal import Decimal

def connect():
    return psycopg2.connect(
        host=os.environ["DB_HOST"], port=os.environ.get("DB_PORT","5432"),
        dbname=os.environ["DB_DATABASE"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], sslmode=os.environ.get("DB_SSLMODE","require"))

def fetch_market(cur, window_days=7):
    cur.execute("""
      select item_ref, category, price, currency, observed_at
      from market_hits
      where observed_at >= now() - interval '%s days'
    """, (window_days,))
    by_key={}
    for item_ref, cat, price, ccy, ts in cur.fetchall():
        by_key[item_ref] = (cat, float(price))
    return by_key

def latest_predictions(cur, model_version):
    cur.execute("""
      select distinct on (item_ref) item_ref, category, model_version, q50, raw
      from price_predictions
      where model_version=%s
      order by item_ref, created_at desc
    """, (model_version,))
    preds=[]
    for item_ref, cat, mv, q50, raw in cur.fetchall():
        # fallback: if no q50 in schema yet, try to derive a pseudo-score-based price (not ideal)
        price = float(q50) if q50 is not None else None
        preds.append((item_ref, cat, mv, price, raw))
    return preds

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model-version", default="clip-v1.0.0")
    ap.add_argument("--window-days", type=int, default=30)
    ap.add_argument("--window", default="30d")
    args=ap.parse_args()

    conn=connect(); conn.autocommit=True; cur=conn.cursor()
    market=fetch_market(cur, args.window_days)
    preds=latest_predictions(cur, args.model_version)

    per={}
    for item_ref, cat, mv, price, raw in preds:
        if item_ref not in market or price is None: continue
        mcat, actual = market[item_ref]
        cat = cat or mcat
        err = abs(price - actual)
        pe = (err / actual * 100.0) if actual else None
        d = per.setdefault(cat, {"errs":[], "pes":[], "n":0})
        if pe is not None:
            d["errs"].append(err); d["pes"].append(pe); d["n"]+=1

    ins="""insert into model_metrics(model_version, category, mae, mape, n, window)
           values (%s,%s,%s,%s,%s,%s)"""
    now=datetime.now(timezone.utc).isoformat()
    wrote=0
    for cat, v in per.items():
        if v["n"]==0: continue
        mae = sum(v["errs"])/v["n"]
        mape = sum(v["pes"])/v["n"]
        cur.execute(ins, (args.model_version, cat, mae, mape, v["n"], args.window))
        print(f"[{now}] {cat}: n={v['n']} MAE={mae:.2f} MAPE={mape:.1f}%")
        wrote+=1
    cur.close(); conn.close()
    print(f"✅ wrote {wrote} rows to model_metrics")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
