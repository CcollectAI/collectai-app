#!/usr/bin/env bash
set -euo pipefail

APPDIR=/home/ubuntu/collectors-merge-recovered
DB_DSN=$("$APPDIR/ops/get_dsn.sh")

echo "== services =="
systemctl --no-pager --full status collectors-merge.service collectors-vision.service collectors-valuation.service 2>/dev/null | sed -n '1,50p'

echo
echo "== healthz =="
curl -fsS http://127.0.0.1:8081/healthz || echo "healthz failed"

echo
echo "== vision_predict_log (last 5) =="
psql "$DB_DSN" <<SQL
SELECT id, item_ref, predicted_label, score, created_at
FROM public.vision_predict_log
ORDER BY created_at DESC
LIMIT 5;
SQL

echo
echo "== price_predictions (last 5) =="
psql "$DB_DSN" <<SQL
SELECT item_ref, q10, q50, q90, generated_at
FROM public.price_predictions
ORDER BY generated_at DESC
LIMIT 5;
SQL

echo
echo "== v_item_signal (last 5) =="
psql "$DB_DSN" <<SQL
SELECT *
FROM public.v_item_signal
ORDER BY vision_at DESC
LIMIT 5;
SQL
