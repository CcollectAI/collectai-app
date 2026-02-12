#!/usr/bin/env python3
import os, io, argparse, re, logging, pandas as pd, boto3, psycopg2, psycopg2.extras, pathlib

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
def conn():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT","5432"),
        dbname=os.environ["DB_DATABASE"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode=os.environ.get("DB_SSLMODE","require"))
def load_csv(local=None, s3=None):
    if local: return pd.read_csv(local)
    m=re.match(r"^s3://([^/]+)/(.+)$", s3 or "")
    if not m: raise SystemExit("Provide --local /path.csv or --s3 s3://bucket/key.csv")
    b,k=m.groups(); bio=io.BytesIO(); boto3.client("s3").download_fileobj(b,k,bio); bio.seek(0)
    return pd.read_csv(bio)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--local"); ap.add_argument("--s3")
    a=ap.parse_args()
    df=load_csv(local=a.local, s3=a.s3)
    need={"category","price","currency","source","observed_at"}
    missing=need - set(df.columns)
    if missing: raise SystemExit(f"CSV missing columns: {missing}")
    # item_ref optional for category backtest
    rows=df.to_dict(orient="records")
    c=conn(); c.autocommit=True; cur=c.cursor()
    sql=("insert into market_hits(item_ref, category, price, currency, source, observed_at) "
         "values (%s,%s,%s,%s,%s,%s)")
    n=0
    for r in rows:
        cur.execute(sql, (r.get("item_ref"), r["category"], r["price"], r["currency"], r["source"], r["observed_at"]))
        n+=1
    cur.close(); c.close()
    logger.info("inserted %d market rows", n)
if __name__=="__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
