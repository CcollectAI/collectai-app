#!/usr/bin/env bash
set -euo pipefail
BASE=${BASE:-http://127.0.0.1:8081}
declare -A payloads=(
  [mtg]='{"set":"mom","finish":"foil","rarity":"mythic","condition":"nm"}'
  [warhammer]='{"title":"Intercessors","faction":"space_marines","sealed":true,"condition":"new"}'
  [gunpla]='{"title":"RX-78","grade":"pg","sealed":true,"condition":"new"}'
  [diecast]='{"title":"Hot Wheels","scale":"1:64","condition":"new"}'
  [lego]='{"title":"Millennium Falcon","set_number":"75192","sealed":true,"condition":"new"}'
  [designer_toys]='{"title":"Kaws Companion","limited":true,"sealed":true,"condition":"new"}'
  [lorcana]='{"set":"tfc","finish":"foil","rarity":"legendary","condition":"nm"}'
  [fab]='{"set":"wtr","rarity":"rare","condition":"nm"}'
)
for c in "${!payloads[@]}"; do
  echo "== $c =="; curl -sS -H 'X-API-Key: '"${PUBLIC_API_KEY:-demo-key-123}" -H 'Content-Type: application/json' \
    -d "${payloads[$c]}" "$BASE/predict2/$c" | jq '.category,.suggested_price,.confidence,.model_name' ; echo
done
