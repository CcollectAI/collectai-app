#!/usr/bin/env bash
set -euo pipefail
REGION="${AWS_REGION:-eu-north-1}"
BUCKET="${ARTIFACT_BUCKET:-}"
PORT="${PORT:-8081}"

train_one () {
  local CAT="$1"
  echo "== train ${CAT}"
  python3 -m pipelines.train_price --category "${CAT}" | tee "/tmp/train_${CAT}.json"
  local VER=$(jq -r .version "/tmp/train_${CAT}.json")
  echo "   version=${VER}"
}

promote_s3 () {
  local CAT="$1"
  local VER="$(basename "$(readlink -f "artifacts/${CAT}/active")")"
  [[ -n "${BUCKET}" ]] || { echo "skip S3 promote (no bucket)"; return 0; }
  printf '{"version":"%s"}' "$VER" | aws s3 cp - "s3://${BUCKET}/artifacts/price/${CAT}/ACTIVE.json" --region "$REGION" --content-type application/json
}

smoke_one () {
  local CAT="$1"
  local VER="$(basename "$(readlink -f "artifacts/${CAT}/active")")"
  local PAY="/tmp/p_${CAT}.json"
  if [[ "${CAT}" == "diecast" ]]; then
    cat > "$PAY" <<JSON
{ "id":"smoke-${CAT}", "title":"${CAT} test", "condition":"mint", "category":"diecast",
  "features":{"scale":"1:18","material":"diecast","maker":"AutoArt","year":2005,"package_condition_score":0.8,"recent_sale_z":0.6}}
JSON
  else
    cat > "$PAY" <<JSON
{ "id":"smoke-${CAT}", "title":"${CAT} test", "condition":"new", "category":"lego",
  "features":{"piece_count":1500,"year":2018,"theme_popularity":0.7,"sealed":true,"box_condition_score":0.9,"recent_sale_z":0.4}}
JSON
  fi
  echo "== smoke ${CAT} pinned"
  curl -s -o "/tmp/${CAT}.out" -w 'HTTP %{http_code}\n' -X POST "http://127.0.0.1:${PORT}/suggest?version=${VER}" \
    -H 'Content-Type: application/json' --data-binary @"$PAY"
  jq . "/tmp/${CAT}.out"
}

train_one diecast
train_one lego
promote_s3 diecast || true
promote_s3 lego || true
smoke_one diecast
smoke_one lego
echo "DONE"
