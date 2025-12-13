#!/usr/bin/env bash
set -euo pipefail
set -a; [ -f ./.env ] && . ./.env; set +a

echo "== $(date -Is) daily start =="

# rebuild FTS (optional; safe/no-op if unchanged)
python services/collectors_merge/workers/build_fts_index.py || true

# evaluate alerts
python services/collectors_merge/workers/alerts_evaluator.py || true

# notify drain (console or Slack if SLACK_WEBHOOK set)
python services/collectors_merge/workers/notify_drain.py || true

# refresh calibration report (stub for now)
[ -f ml/evaluate.py ] && python ml/evaluate.py || true

echo "== $(date -Is) daily end =="
