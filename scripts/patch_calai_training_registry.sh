#!/usr/bin/env bash
set -euo pipefail
FILE="supabase/migrations/20250921113204_calai_training_registry.sql"

if [ ! -f "$FILE" ]; then
  echo "Could not find $FILE. List your migrations and adjust the FILE path." >&2
  ls -1 supabase/migrations | sed 's/^/ - /'
  exit 1
fi

cp "$FILE" "$FILE.bak.$(date -u +%Y%m%d%H%M%S)"

# Rewrite the view block: remove "IF NOT EXISTS", add DROP IF EXISTS + CREATE VIEW
awk '
BEGIN{printed=0}
/^[[:space:]]*--/ { print; next }
{
  buf = buf $0 ORS
}
END{
  # Replace any CREATE VIEW IF NOT EXISTS ... with DROP + CREATE
  gsub(/create[[:space:]]+view[[:space:]]+if[[:space:]]+not[[:space:]]+exists[[:space:]]+public\.v_training_dataset[[:space:]]+as/i,
       "DROP VIEW IF EXISTS public.v_training_dataset;\n\nCREATE VIEW public.v_training_dataset AS", buf)
  print buf
}
' "$FILE" > "$FILE.tmp"

# Ensure model_registry create block is idempotent
# (If it already uses CREATE TABLE IF NOT EXISTS, we keep it)
mv "$FILE.tmp" "$FILE"

echo "Patched $FILE (backup at $FILE.bak.$(date -u +%Y%m%d%H%M%S))"
