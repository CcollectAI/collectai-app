#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"; ROOT="$(cd -- "$ROOT/.." && pwd -P)"
cd "$ROOT"
[ -d .venv ] && source .venv/bin/activate || true
export PYTHONPATH="$PWD:$PYTHONPATH"
python3 trainer.py --category diecast
python3 trainer.py --category lego
echo "D_VER=$(basename "$(readlink -f artifacts/diecast/active)")"
echo "L_VER=$(basename "$(readlink -f artifacts/lego/active)")"
