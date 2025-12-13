#!/usr/bin/env bash
set -euo pipefail

# Find the uuid repair migration (adjust the glob if your name differs)
FILE="$(ls -1 supabase/migrations/*_label_events_uuid_repair.sql | head -n 1 || true)"
if [ -z "${FILE:-}" ] || [ ! -f "$FILE" ]; then
  echo "Could not find *_label_events_uuid_repair.sql to patch"; exit 1
fi

echo "Patching: $FILE"

# Ensure the WHERE uses session_id::text for regex, and keep the UPDATE cast as-is
# Replace "session_id ~*" with "session_id::text ~*"
tmp="$(mktemp)"
sed 's/session_id[[:space:]]\+~\*/session_id::text ~*/g' "$FILE" > "$tmp"
mv "$tmp" "$FILE"

# Also make sure we created the helper column before updating (idempotent)
if ! grep -q 'ADD COLUMN IF NOT EXISTS session_id_uuid uuid' "$FILE"; then
  cat <<'SQL' >> "$FILE"

-- Ensure helper uuid column exists
ALTER TABLE public.label_events
  ADD COLUMN IF NOT EXISTS session_id_uuid uuid;
SQL
fi

echo "Patched successfully."
