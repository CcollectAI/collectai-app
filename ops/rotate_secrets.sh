#!/usr/bin/env bash
set -euo pipefail
UNIT=collectors-merge
RUNNER=/home/ubuntu/collectors-merge-recovered/ops/run-uvicorn.sh

usage(){ echo "Usage: $0 [--api-key] [--set-partner SECRET_NAME=VALUE ...]"; exit 1; }

API=0; PAIRS=()
while (( "$#" )); do
  case "$1" in
    --api-key) API=1; shift;;
    --set-partner) shift; [[ $# -gt 0 ]] || usage; PAIRS+=("$1"); shift;;
    *) usage;;
  esac
done

if [ $API -eq 1 ]; then
  NEW=$(openssl rand -hex 16)
  sed -i '/^export INGEST_API_KEY=/d' "$RUNNER"
  echo "export INGEST_API_KEY=$NEW" >> "$RUNNER"
  echo "Rotated INGEST_API_KEY -> $NEW"
fi

for kv in "${PAIRS[@]}"; do
  NAME=${kv%%=*}; VAL=${kv#*=}
  # write to systemd env drop-in so it survives runner edits
  sudo mkdir -p /etc/systemd/system/${UNIT}.service.d
  sudo bash -c "cat > /etc/systemd/system/${UNIT}.service.d/60-${NAME}.conf <<EOF
[Service]
Environment=${NAME}=${VAL}
EOF"
  echo "Set ${NAME}"
done

sudo systemctl daemon-reload
sudo systemctl restart "$UNIT"
echo "restarted $UNIT"
