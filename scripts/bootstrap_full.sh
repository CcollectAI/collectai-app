set -euo pipefail
python3 -m venv .venv >/dev/null 2>&1 || true
. .venv/bin/activate
pip -q install requests numpy scikit-learn fastapi uvicorn boto3 pydantic >/dev/null

# dataset with numeric features
cat > /tmp/dataset_real.csv <<'CSV'
label_value_eur,year,rarity_score,graded
10,1999,0.1,0
15.5,1999,0.2,0
22,2000,0.3,1
19,2000,0.4,0
37.2,2000,0.8,1
CSV
aws s3 cp /tmp/dataset_real.csv s3://collectai-datasets/datasets/real.csv

python - <<'PY'
import trainer
evt={"model":"price","version":"v0.2.1","dataset_csv":"s3://collectai-datasets/datasets/real.csv","category":"pokemon","params":{"alpha":1.0}}
print(trainer.handler(evt,None))
PY

python scripts/eval_mae_and_gate.py pokemon

echo "Smoke test: query evals + gate"
curl -sS "$SUPABASE_URL/rest/v1/model_evals?select=model,category,version,mae,rmse,r2&category=eq.pokemon&order=evaluated_at.desc&limit=2" \
  -H "apikey: $SUPABASE_SERVICE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" | jq
curl -sS "$SUPABASE_URL/rest/v1/model_gate?select=category,name,active_version,status,note&category=eq.pokemon" \
  -H "apikey: $SUPABASE_SERVICE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" | jq
