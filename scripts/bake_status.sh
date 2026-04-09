#!/usr/bin/env bash
# Print a single-screen health snapshot for the bake.
# Hits /admin/bake-summary on the configured API host. Run from your laptop.
#
# Usage:
#   ./scripts/bake_status.sh                              # uses API_HOST + OPS_API_KEY from .env
#   API_HOST=http://3.75.182.41:8000 ./scripts/bake_status.sh
#   OPS_API_KEY=xxxx ./scripts/bake_status.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$REPO_ROOT/.env" ]; then
  set -a; . "$REPO_ROOT/.env"; set +a
fi

API_HOST="${API_HOST:-http://3.75.182.41:8000}"
KEY="${OPS_API_KEY:-}"

if [ -z "$KEY" ]; then
  echo "OPS_API_KEY not set (in env or .env). Aborting." >&2
  exit 1
fi

URL="$API_HOST/admin/bake-summary"
echo "→ GET $URL"
RESP=$(curl -fsS -H "X-Ops-Key: $KEY" "$URL" 2>&1) || {
  echo "request failed: $RESP" >&2
  exit 1
}

# Pretty-print with python (always available) — falls back to raw on no-python
if command -v python3 >/dev/null 2>&1; then
  echo "$RESP" | python3 -c "
import json, sys
d = json.load(sys.stdin)
def hr(): print('─' * 60)

hr()
print(f\"  CollectAI bake — {'✅ OK' if d.get('ok') else '⚠️  WARNINGS'}\")
hr()

# Workers
w = d.get('workers', {}).get('workers', [])
if w:
    print('Workers:')
    for x in w:
        status = x.get('last_status', '?')
        emoji = '✅' if status == 'ok' else ('⚠️ ' if status == 'overdue' else '❌')
        last  = x.get('last_run_at', 'never')
        runs  = x.get('run_count', 0)
        print(f\"  {emoji} {x.get('name', '?'):24s} runs={runs:5d}  last={last}\")
    print()

# Rows
r = d.get('rows', {})
if r:
    print('Rows:')
    fmt = lambda v: f'{v:>10,}' if isinstance(v, int) else f'{str(v):>10s}'
    print(f\"  category_items_total     {fmt(r.get('category_items_total'))}\")
    print(f\"  market_hits_total        {fmt(r.get('market_hits_total'))}\")
    print(f\"  market_hits_24h          {fmt(r.get('market_hits_24h'))}\")
    print(f\"  price_predictions_total  {fmt(r.get('price_predictions_total'))}\")
    print(f\"  price_predictions_24h    {fmt(r.get('price_predictions_24h'))}\")
    print(f\"  mandate_deals_total      {fmt(r.get('mandate_deals_total'))}\")
    print(f\"  alert_history_24h        {fmt(r.get('alert_history_24h'))}\")
    print()

# Spend
s = d.get('spend', {})
if s:
    pct = s.get('pct_used', 0) or 0
    bar = '█' * int(pct / 5) + '·' * (20 - int(pct / 5))
    print(f\"Spend: {bar}  {pct:5.1f}%   €{s.get('total_spent_eur', 0):.2f} / €{s.get('budget_eur', 0):.2f}\")
    print()

# Sources
ds = d.get('data_sources', {})
if ds:
    active = ds.get('_active_count', 0)
    print(f\"Data sources active: {active}\")
    keyed = [k for k, v in ds.items() if v and not k.startswith('_')]
    print(f\"  {', '.join(keyed)}\")
    print()

# Warnings
warns = d.get('warnings', [])
if warns:
    print('Warnings:')
    for w in warns:
        print(f\"  ⚠️  {w}\")
hr()
"
else
  echo "$RESP"
fi
