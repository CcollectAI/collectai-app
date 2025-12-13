set -euo pipefail
echo "[1/4] ensure venv + deps"
python3 -m venv .venv >/dev/null 2>&1 || true
. .venv/bin/activate
pip -q install requests numpy scikit-learn >/dev/null

echo "[2/4] train v0.1.1"
python - <<'PY'
import trainer
evt={"model":"price","version":"v0.1.1","dataset_csv":"s3://collectai-datasets/datasets/test.csv","category":"pokemon","params":{"alpha":1.0}}
print(trainer.handler(evt,None))
PY

echo "[3/4] write gate script if missing"
mkdir -p scripts
if [ ! -f scripts/eval_mae_and_gate.py ]; then
  cat > scripts/eval_mae_and_gate.py <<'PY'
import os, requests
SB=os.environ["SUPABASE_URL"]; KEY=os.environ["SUPABASE_SERVICE_KEY"]
TH=float(os.environ.get("GATE_IMPROVE_PCT","3"))
def rq(p,params=None,json=None,m="GET",pref=None):
    h={"apikey":KEY,"Authorization":f"Bearer {KEY}"}
    if json is not None: h["Content-Type"]="application/json"
    if pref: h["Prefer"]=pref
    r=requests.request(m,f"{SB}/rest/v1/{p}",headers=h,params=params,json=json,timeout=30)
    r.raise_for_status(); return r.json() if r.text else []
def latest_mae(c,v): r=rq("model_evals",{"select":"mae","category":"eq."+c,"version":"eq."+v,"order":"evaluated_at.desc","limit":"1"}); return r[0]["mae"] if r else None
def best(c): r=rq("model_evals",{"select":"version,mae","category":"eq."+c,"order":"evaluated_at.desc","limit":"50"}); return min(r,key=lambda x:(x["mae"] is None,x["mae"])) if r else None
def gate(c): r=rq("model_gate",{"select":"*","category":"eq."+c,"limit":"1"}); return (r[0] if r else None)
def upsert(c,**f): rq("model_gate",json={"category":c,**f},m="POST",pref="resolution=merge-duplicates")
def main(c):
    cand=best(c)
    if not cand or cand["mae"] is None: return
    g=gate(c) or {"active_version":None}
    act=g["active_version"]
    if not act: upsert(c,active_version=cand["version"],status="approved",note="bootstrap"); print("bootstrap",c,cand["version"]); return
    act_mae=latest_mae(c,act)
    if act_mae is None: upsert(c,active_version=cand["version"],status="approved",note="no active mae"); print("promote",c,cand["version"]); return
    improve=(act_mae-cand["mae"])/act_mae*100.0
    if improve>=TH: upsert(c,active_version=cand["version"],candidate_version=None,status="approved",note=f"improve={improve:.2f}%"); print("promote",c,cand["version"])
    else: upsert(c,active_version=act,candidate_version=cand["version"],status="rejected",note=f"improve={improve:.2f}%<{TH}%"); print("reject",c,cand["version"])
if __name__=="__main__": main("pokemon")
PY
fi

echo "[4/4] gate pokemon"
GATE_IMPROVE_PCT="${GATE_IMPROVE_PCT:-3}" python scripts/eval_mae_and_gate.py
echo "done"
