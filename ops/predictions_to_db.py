#!/usr/bin/env python3
import argparse
import glob
import json
import logging
import os
import pathlib

import psycopg2

logger = logging.getLogger(__name__)
# AUTOLOAD_DB_ENV
for _cand in ("/etc/collectors/db.env", "ops/db.env"):
    p=pathlib.Path(_cand)
    if p.exists():
        for ln in p.read_text().splitlines():
            ln=ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k,v=ln.split("=",1)
                os.environ.setdefault(k.strip(), v.strip())
        break
def connect():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT","5432"),
        dbname=os.environ["DB_DATABASE"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode=os.environ.get("DB_SSLMODE","require"))
def infer_category(rec):
    try: return rec["prediction"]["results"][0]["label"]
    except (KeyError, IndexError, TypeError) as e:
        logger.warning("infer_category failed: %s", e)
        return None
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dir", default="ops/vision")
    ap.add_argument("--model-version", default="clip-v1.0.0")
    args=ap.parse_args()
    files=sorted(glob.glob(os.path.join(args.dir,"predictions-*.jsonl")))
    if not files: logger.warning("no prediction files"); return 0
    con=connect(); con.autocommit=True; cur=con.cursor()
    sql=("insert into price_predictions(item_ref, category, model_version, q10,q50,q90, confidence, raw) "
         "values (%s,%s,%s,%s,%s,%s,%s,%s)")
    n=0
    for fp in files:
        with open(fp,"r",encoding="utf-8") as fh:
            for ln in fh:
                ln=ln.strip()
                if not ln or ln[0] not in "{[": continue
                try: rec=json.loads(ln)
                except (json.JSONDecodeError, ValueError): continue
                item_ref=rec.get("s3_key") or rec.get("item_ref")
                cat=infer_category(rec)
                results=(rec.get("prediction") or {}).get("results") or []
                conf=results[0].get("score") if results and isinstance(results[0],dict) else None
                cur.execute(sql,(item_ref,cat,args.model_version,None,None,None,conf,json.dumps(rec)))
                n+=1
    cur.close(); con.close()
    logger.info("wrote %d rows to price_predictions", n)
if __name__=="__main__":
    import os; os.path
    raise SystemExit(main())
