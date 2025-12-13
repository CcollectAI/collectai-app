#!/usr/bin/env bash
set -euo pipefail
CAT="${1:?usage: add_category <name>}"
install -d "data/${CAT}" "artifacts/${CAT}"
# 1) extend app/ml/features.py: add CatConfig with proper num/cat fields
# 2) synthetic dataset seed
tee "data/${CAT}/train.jsonl" >/dev/null <<JSON
{"features":{"f_numeric_1":1.0,"f_numeric_2":2.0,"f_categorical":"A"},"price":100.0}
{"features":{"f_numeric_1":2.0,"f_numeric_2":3.0,"f_categorical":"B"},"price":130.0}
JSON
echo "Now: add config for '${CAT}' in app/ml/features.py, then run: python3 -m pipelines.train_price --category ${CAT}"
