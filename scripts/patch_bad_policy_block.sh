#!/usr/bin/env bash
set -euo pipefail

# Locate the migration that has the broken policy EXECUTE $$CREATE POLICY...$$
# (Adjust the glob if your filename differs)
CANDIDATES=(supabase/migrations/*_training_items_dualwrite_patch.sql)

if [ ${#CANDIDATES[@]} -eq 0 ]; then
  echo "No *_training_items_dualwrite_patch.sql file found."
  exit 1
fi

BAD_FILE="${CANDIDATES[0]}"
if [ ! -f "$BAD_FILE" ]; then
  echo "File not found: $BAD_FILE"
  exit 1
fi

echo "Patching: $BAD_FILE"

# Remove any DO $$ ... END$$; block that contains the bad policy name
tmp="$(mktemp)"
awk '
  BEGIN { inblock=0; buf="" }
  {
    # Detect start of a DO $$ block
    if ($0 ~ /^DO[[:space:]]*\\$\\$/) {
      inblock=1
      buf=$0 ORS
      next
    }

    if (inblock) {
      buf = buf $0 ORS
      if ($0 ~ /END\\$\\$;/) {
        # End of DO block: drop it if it contains the offending policy
        if (buf ~ /service_role_full_access_training_items/) {
          # skip writing this block
        } else {
          printf "%s", buf
        }
        inblock=0
        buf=""
      }
      next
    }

    # Outside DO blocks: just print
    print
  }
' "$BAD_FILE" > "$tmp"

mv "$tmp" "$BAD_FILE"

# Append a safe policy for auth SELECT (uses proper quoting in EXECUTE string)
if ! grep -q 'auth_select_training_items' "$BAD_FILE"; then
cat >> "$BAD_FILE" <<'SQL'

-- Safe policy for authenticated SELECT on training_items (kept outside the broken block)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='training_items'
      AND policyname='auth_select_training_items'
  ) THEN
    EXECUTE 'CREATE POLICY "auth_select_training_items"
             ON public.training_items
             FOR SELECT
             TO authenticated
             USING (true)';
  END IF;
END$$;
SQL
fi

echo "Patched successfully."
