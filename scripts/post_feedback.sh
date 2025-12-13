#!/usr/bin/env bash
set -euo pipefail
APP="$HOME/collectors-merge-recovered"
set -a; . "$APP/env/.env"; set +a
REGION="${AWS_REGION:-eu-north-1}"
VER="$(aws s3 cp "s3://${ARTIFACT_BUCKET}/artifacts/price/ACTIVE.json" - --region "$REGION" | jq -r .version)"
TOKEN="$(grep -m1 '^API_AUTH_KEY=' "$APP/env/.env" | cut -d= -f2-)"
jq -n --arg ver "$VER" '{
  version:$ver, category:"pokemon",
  label_value_eur:25.0, accepted_price:25.0,
  features:{year:2001,rarity_score:0.7,graded:1},
  context:{source:"script"}
}' > /tmp/fb.json
curl -sS -o /tmp/fb.out -w 'HTTP %{http_code}\n' -X POST http://127.0.0.1:8080/feedback \
  -H "Authorization: Bearer '"$TOKEN"'" -H "Content-Type: application/json" \
  --data-binary @/tmp/fb.json
sed -n '1,200p' /tmp/fb.out
