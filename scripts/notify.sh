#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$HOME/collectors-merge-recovered"
set -a; [ -f "$APP_DIR/env/.env" ] && . "$APP_DIR/env/.env"; set +a
TXT="${1:-collectors-merge event}"
if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
  curl -sS -X POST -H 'Content-type: application/json' --data "{\"text\":\"${TXT}\"}" "$SLACK_WEBHOOK_URL" >/dev/null || true
fi
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_CHAT_ID}" -d text="${TXT}" >/dev/null || true
fi
