#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD:$PYTHONPATH"
[ -d .venv ] && source .venv/bin/activate || true
need_restart=0

train_and_promote () {
  local cat="$1"
  echo "==> ${cat}: check active"
  if [ ! -f "artifacts/${cat}/active/model.pkl" ]; then
    echo "   no active model — training ${cat}…"
    python3 trainer.py --category "${cat}"
    latest_dir=$(ls -1dt "artifacts/${cat}/"*/ 2>/dev/null | head -n1 || true)
    if [ -z "${latest_dir}" ]; then
      echo "!! training did not produce artifacts for ${cat}"
      return 1
    fi
    ln -sfn "${latest_dir}" "artifacts/${cat}/active"
    echo "   promoted ${cat} -> ${latest_dir}"
    need_restart=1
  else
    echo "   active present: $(readlink -f artifacts/${cat}/active)"
  fi
}

train_and_promote diecast
train_and_promote lego

if [ "$need_restart" -eq 1 ]; then
  echo "==> restarting collectors-merge.service"
  sudo systemctl restart collectors-merge.service || true
  sleep 2
fi

echo "==> smoke tests"
curl -sf http://127.0.0.1:8081/health && echo "OK /health" || echo "!! /health failed"
echo "--- suggest(diecast) ---"
curl -s -X POST http://127.0.0.1:8081/suggest -H 'Content-Type: application/json' \
  -d '{"title":"smoke diecast","condition":"mint","category":"diecast","features":{"scale":"1:18","material":"diecast","maker":"AutoArt","year":2005,"package_condition_score":0.8,"recent_sale_z":0.6}}' | jq .
echo "--- suggest(lego) ---"
curl -s -X POST http://127.0.0.1:8081/suggest -H 'Content-Type: application/json' \
  -d '{"title":"smoke lego","condition":"new","category":"lego","features":{"piece_count":1500,"year":2018,"theme_popularity":0.7,"sealed":true,"box_condition_score":0.9,"recent_sale_z":0.4}}' | jq .
