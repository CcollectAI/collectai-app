#!/usr/bin/env bash
# Verdict on the latest nightly-ingest run — and it REFUSES to give one about a
# run that predates the fix being tested.
#
# The first version of this check just grepped the newest run. On 2026-09-05 it
# printed "Rows LOST: 2254" from a run that started 15h BEFORE the fix landed,
# which reads exactly like the fix failing. A check that does not name its
# subject is not a check.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

FIX="${1:-d43de93}"          # commit that must be present for the answer to mean anything

read -r RID SHA CREATED CONCL < <(
  gh run list --workflow=nightly-ingest.yml --limit 1 \
    --json databaseId,headSha,createdAt,conclusion \
    -q '.[0] | "\(.databaseId) \(.headSha) \(.createdAt) \(.conclusion)"'
)

echo "run $RID  started $CREATED  sha ${SHA:0:7}  -> $CONCL"

if ! git merge-base --is-ancestor "$FIX" "$SHA" 2>/dev/null; then
  echo
  echo "⏸  THIS RUN PREDATES THE FIX ($FIX) — it says nothing about it."
  echo "   nightly-ingest is cron '0 3 * * *' but actually starts ~07:15-07:35 UTC"
  echo "   (GitHub queues free-tier schedules). Check again after that window."
  exit 2
fi

echo
LOG=$(gh run view "$RID" --log 2>/dev/null)
LOST=$(printf '%s' "$LOG" | grep -oE "Rows LOST: [0-9]+" | tail -1)
CLOSED=$(printf '%s' "$LOG" | grep -c "client has been closed")
CIRCUIT=$(printf '%s' "$LOG" | grep -c "circuit open")

[ -z "$LOST" ] && LOST="Rows LOST: 0 (no loss line)"
echo "  $LOST"
echo "  'client has been closed' occurrences: $CLOSED   (want 0)"
echo "  circuit-breaker trips: $CIRCUIT   (>0 is SUCCESS — we stopped hammering a dead upstream)"
echo
if [ "$CLOSED" -eq 0 ] && printf '%s' "$LOST" | grep -q "LOST: 0"; then
  echo "✅ write-loss fix held."
else
  echo "❌ still losing rows — the race is not what we thought. Re-open docs/INGEST.md."
fi
