#!/usr/bin/env bash
set -euo pipefail
echo "== Timers =="; systemctl list-timers | grep -E 'spool-upload|vision-' || true
echo; echo "== Last logs ==";
for u in spool-upload.service vision-index.service vision-batch-predict.service; do
  echo "-- $u --"; journalctl -u "$u" -n 50 --no-pager || true; echo
done
echo "== Artifacts =="; ls -lh ops/vision/faiss.index ops/vision/ids.jsonl 2>/dev/null || true
[ -f ops/vision/ids.jsonl ] && echo "ids.jsonl lines: $(wc -l < ops/vision/ids.jsonl)"
echo; echo "== API =="; curl -sS http://127.0.0.1:8081/healthz | jq .; curl -sS http://127.0.0.1:8081/ops/vision/debug | jq .
