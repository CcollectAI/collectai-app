#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/collectors-merge-recovered
# 1) build
python3 scripts/build_dataset_from_feedback.py pokemon
# 2) ship to s3 with date
d=$(date -u +%Y%m%d)
aws s3 cp /tmp/feedback_pokemon.csv s3://collectai-datasets/datasets/feedback_pokemon_$d.csv
# 3) train & eval/gate
python3 - <<PY
import trainer
ds=f"s3://collectai-datasets/datasets/feedback_pokemon_{'$d'}.csv"
evt={"model":"price","version":"v0.$d","dataset_csv":ds,"category":"pokemon","params":{"alpha":1.0}}
print(trainer.handler(evt,None))
PY
python3 scripts/eval_mae_and_gate.py pokemon
