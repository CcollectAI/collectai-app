#!/usr/bin/env bash
set -euo pipefail
APP="$HOME/collectors-merge-recovered"; URL="http://127.0.0.1:8080"
TOKEN="$(grep -m1 '^API_AUTH_KEY=' "$APP/env/.env" | cut -d= -f2-)"
FILE="${1:?csv file: id,category,title,condition,json_features}"
[ -f "$FILE" ] || { echo "no file $FILE"; exit 2; }
python3 - "$URL" "$TOKEN" "$FILE" <<'PY'
import csv, json, sys, requests
url,token,f=sys.argv[1],sys.argv[2],sys.argv[3]
hdr={'Authorization':f'Bearer {token}','Content-Type':'application/json'}
with open(f) as fh:
  for r in csv.DictReader(fh):
    body={
      "id": r["id"], "category": r["category"],
      "title": r.get("title",""),
      "condition": r.get("condition","graded"),
      "features": json.loads(r["json_features"])
    }
    s=requests.post(f"{url}/suggest",headers=hdr,data=json.dumps(body),timeout=8)
    print(r["id"], s.status_code, s.text.strip())
PY
