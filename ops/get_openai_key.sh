#!/usr/bin/env bash
set -euo pipefail
DROPIN="/etc/systemd/system/collectors-merge.service.d/env.conf"
awk -F= '/^Environment=OPENAI_API_KEY=/{sub(/^Environment=OPENAI_API_KEY="?/,""); sub(/"$/,""); print}' "$DROPIN"
