#!/usr/bin/env bash
# Tail the bake log on EC2 from your laptop. Edit SSH_TARGET to match your box.
set -euo pipefail
SSH_TARGET="${SSH_TARGET:-ubuntu@3.75.182.41}"
REMOTE_PATH="${REMOTE_PATH:-~/CcollectAI/bake.log}"
LINES="${1:-100}"

echo "→ tail -${LINES} ${SSH_TARGET}:${REMOTE_PATH}"
ssh "$SSH_TARGET" "tail -${LINES} ${REMOTE_PATH}"
