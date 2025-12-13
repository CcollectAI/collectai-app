#!/usr/bin/env bash
set -euo pipefail

DROPIN="/etc/systemd/system/collectors-merge.service.d/env.conf"

VAL=$(awk -F= '/^Environment=DB_DSN=/{sub(/^Environment=DB_DSN="?/, ""); sub(/"$/, ""); print}' "$DROPIN")
echo "$VAL"
