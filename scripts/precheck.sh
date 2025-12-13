set -euo pipefail
echo "[precheck] checking ports and tools"
command -v python >/dev/null
command -v curl >/dev/null
echo "[precheck] ok"
