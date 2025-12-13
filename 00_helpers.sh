#!/usr/bin/env bash
set -euo pipefail

# --- defaults (all overridable before sourcing) ---
APP_DIR="${APP_DIR:-$HOME/collectai}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
LOG_DIR="${LOG_DIR:-$HOME/collectai/logs}"   # user path (no sudo)
SYSTEM_USER="${SYSTEM_USER:-$USER}"
API_PORT="${API_PORT:-8080}"
TZ_SET="${TZ_SET:-Europe/Paris}"
ARTIFACT_BUCKET="${ARTIFACT_BUCKET:-collectai-models}"
DATASET_BUCKET="${DATASET_BUCKET:-collectai-datasets}"
EVAL_DATASET_KEY="${EVAL_DATASET_KEY:-eval/heldout.csv}"
AWS_REGION="${AWS_REGION:-eu-west-1}"

mkdir -p "$APP_DIR" "$LOG_DIR"

# write_file TARGET TAG PAYLOAD  (TAG is ignored; payload written exactly)
write_file() {
  local target="$1"
  local _unused="$2"
  local payload="$3"
  mkdir -p "$(dirname "$target")"
  [ -f "$target" ] && cp -f "$target" "${target}.bak.$(date +%s)" || true
  printf '%s' "$payload" > "$target"
}
