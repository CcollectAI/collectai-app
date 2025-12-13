#!/usr/bin/env bash
set -euo pipefail
err(){ echo "[ERR]" "$@"; exit 1; }
[ -s env/.env ] || err "env missing"
grep -q '^API_AUTH_KEY=' env/.env || err "API_AUTH_KEY missing"
grep -q '^SUPABASE_URL=' env/.env || err "SUPABASE_URL missing"
grep -q '^ARTIFACT_BUCKET=' env/.env || err "ARTIFACT_BUCKET missing"
grep -q '^DATASET_BUCKET=' env/.env || err "DATASET_BUCKET missing"
[ -f config/gate.yaml ] || err "config/gate.yaml missing"
systemctl is-active --quiet collectors-merge.service || err "service not active"
curl -s -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/health | grep -q '^200$' || err "/health !=200"
echo "OK"
