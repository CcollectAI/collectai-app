#!/usr/bin/env bash
set -euo pipefail
echo "== API health =="; curl -sS http://127.0.0.1:8081/healthz | jq .
echo "== Vision debug =="; curl -sS http://127.0.0.1:8081/ops/vision/debug | jq .
echo "== Index files =="; ls -lh ops/vision/faiss.index ops/vision/ids.jsonl || true
echo "== Predictions files =="; ls -lh ops/vision/predictions-*.jsonl 2>/dev/null | tail -n3 || true
echo "== Metrics exporter head =="; curl -sS http://127.0.0.1:9001/metrics | sed -n '1,20p' || true
echo "== Timers =="; systemctl list-timers | egrep 'vision-|spool-upload|curate-images|clean-small-s3|model-backtest' || true
