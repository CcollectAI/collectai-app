#!/usr/bin/env bash
set -euo pipefail
CAT="${1:?cat}"
VER="${2:?version-dir}"
test -d "artifacts/${CAT}/${VER}" || { echo "missing artifacts/${CAT}/${VER}"; exit 1; }
ln -sfn "$(readlink -f "artifacts/${CAT}/${VER}")" "artifacts/${CAT}/active"
sudo systemctl restart collectors-merge.service
echo "${CAT} rolled back to ${VER}"
