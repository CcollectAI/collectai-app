set -euo pipefail
IMG=${IMG:-/etc/hosts}
echo "[smoke] FastPass"
curl -s -F "file=@${IMG}" -F "user_id=smoke" -F "watchlist=1" http://localhost:8080/ingest/fastpass_v2 | jq .
