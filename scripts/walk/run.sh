#!/bin/bash
# Run the screen sweep with the production Supabase URL/anon key from EAS (never
# written to disk) so dynamic routes get real ids for the walk account.
#
#   WALK_EMAIL=… WALK_PASSWORD=… scripts/walk/run.sh [sweep args]
#   npm run walk -- --locale nl
#
# The walk account is the throwaway test user, never a real member — the
# fixtures are read AS that user. Credentials come from your shell, not the repo.
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ -z "${WALK_EMAIL:-}" ] || [ -z "${WALK_PASSWORD:-}" ]; then
  echo "note: WALK_EMAIL/WALK_PASSWORD not set — routes that need ids will be SKIPPED" >&2
fi
args=$(printf ' %q' "$@")
exec npx eas env:exec production --non-interactive "node scripts/walk/sweep.mjs${args}"
