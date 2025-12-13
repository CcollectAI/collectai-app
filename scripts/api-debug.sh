#!/usr/bin/env bash
set -euo pipefail

echo "=== collectors-merge.service status ==="
if command -v systemctl >/dev/null 2>&1; then
  systemctl status collectors-merge.service --no-pager || true
else
  echo "systemctl not available on this host."
fi

echo
echo "=== Listening ports near 808x ==="
if command -v ss >/dev/null 2>&1; then
  ss -tulpn | grep 808 || true
elif command -v netstat >/dev/null 2>&1; then
  netstat -tulpn | grep 808 || true
else
  echo "No ss/netstat available to inspect ports."
fi

echo
echo "=== curl http://127.0.0.1:8080/healthz (direct app) ==="
curl -sv http://127.0.0.1:8080/healthz 2>&1 || echo "[8080 /healthz failed]"

echo
echo "=== curl http://127.0.0.1:8082/healthz (if you have a proxy on 8082) ==="
curl -sv http://127.0.0.1:8082/healthz 2>&1 || echo "[8082 /healthz failed]"

echo
echo "=== curl QuickScan demo (POST /quickscan-advanced/single on 8080) ==="
curl -sv \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"demo_mode": true}' \
  http://127.0.0.1:8080/quickscan-advanced/single 2>&1 || echo "[QuickScan on 8080 failed]"

echo
echo "=== Done. Check for HTTP status codes and any 3xx Location headers above. ==="
