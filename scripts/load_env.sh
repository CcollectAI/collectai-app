#!/usr/bin/env bash
# source this on login: . ~/collectors-merge-recovered/scripts/load_env.sh
set -a
[ -f "$HOME/collectors-merge-recovered/env/.env" ] && . "$HOME/collectors-merge-recovered/env/.env"
set +a
if [ -d "$HOME/collectors-merge-recovered/.venv" ]; then
  . "$HOME/collectors-merge-recovered/.venv/bin/activate"
fi
export APP_DIR="$HOME/collectors-merge-recovered"
export LOG_DIR="$HOME/collectors-merge-recovered/logs"
mkdir -p "$LOG_DIR"
