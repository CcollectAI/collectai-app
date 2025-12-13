#!/usr/bin/env bash
set -euo pipefail

echo "== Health =="
curl -sS http://127.0.0.1:8081/healthz | jq .

echo "== Vision debug =="
curl -sS http://127.0.0.1:8081/ops/vision/debug | jq .

echo "== Artifacts =="
ls -lh ops/vision/faiss.index ops/vision/ids.jsonl || true
echo "== ids.jsonl count =="
if [[ -f ops/vision/ids.jsonl ]]; then wc -l ops/vision/ids.jsonl; fi

echo "== Text search smoke =="
curl -sS "http://127.0.0.1:8081/vision/search/text?q=lego%20set" | jq .

echo "== Enable timers =="
sudo systemctl enable --now spool-upload.timer || true
sudo systemctl enable --now vision-index.timer || true
sudo systemctl enable --now vision-batch-predict.timer || true
systemctl list-timers | grep -E 'spool-upload|vision-' || true

echo "== Done. If DB is disabled, that's fine. When ready, enable DB and rerun. =="
