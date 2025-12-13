#!/usr/bin/env bash
set -euo pipefail
APP="$HOME/collectors-merge-recovered"
URL="http://127.0.0.1:8080"
TOKEN="$(grep -m1 '^API_AUTH_KEY=' "$APP/env/.env" | cut -d= -f2-)"
code=$(curl -sS -o /tmp/health.json -w '%{http_code}' "$URL/health")
[ "$code" = "200" ] || { echo "health=$code"; cat /tmp/health.json; exit 1; }

# build a minimal suggest payload; fall back between condition string/object
REQ1='{"id":"smoke","title":"pokemon charizard","condition":"graded","category":"pokemon","features":{"year":2001,"rarity_score":0.6,"graded":1}}'
code=$(curl -sS -o /tmp/sugg.json -w '%{http_code}' -X POST "$URL/suggest" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$REQ1")
if [ "$code" != "200" ]; then
  REQ2='{"id":"smoke","title":"pokemon charizard","condition":{"grade":8,"service":"psa"},"category":"pokemon","features":{"year":2001,"rarity_score":0.6,"graded":1}}'
  code=$(curl -sS -o /tmp/sugg.json -w '%{http_code}' -X POST "$URL/suggest" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$REQ2")
fi
[ "$code" = "200" ] || { echo "suggest=$code"; cat /tmp/sugg.json; exit 2; }

jq -r '.model_version+" "+(.price|tostring)' /tmp/sugg.json
echo "OK"
