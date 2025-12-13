#!/usr/bin/env bash
set -euo pipefail

f="supa_test.env"
[ -f "$f" ] || { echo "❌ $f not found"; exit 1; }

# Normalize line endings + trim spaces
tmp="$(mktemp)"
tr -d '\r' < "$f" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' > "$tmp"

# If ANON_KEY line accidentally contains SERVICE_ROLE_KEY (concatenated), split it
if grep -q '^ANON_KEY=.*SERVICE_ROLE_KEY=' "$tmp"; then
  echo "⚠️  Detected concatenated ANON_KEY + SERVICE_ROLE_KEY; splitting…"
  awk '
    BEGIN{FS="="; OFS="="}
    /^ANON_KEY=/ {
      line=$0
      sub(/\r$/,"",line)
      # split at SERVICE_ROLE_KEY=
      split(line, parts, /SERVICE_ROLE_KEY=/)
      print parts[1]
      print "SERVICE_ROLE_KEY=" parts[2]
      next
    }
    {print}
  ' "$tmp" > "${tmp}.2" && mv "${tmp}.2" "$tmp"
fi

# Remove any surrounding quotes from values
tmp2="$(mktemp)"
awk -F= 'BEGIN{OFS="="}
  /^[A-Z_]+=/ {
    k=$1; v=$0; sub(/^[^=]*=/,"",v)
    # strip surrounding single/double quotes
    gsub(/^"/,"",v); gsub(/"$/,"",v)
    gsub(/^'\''/,"",v); gsub(/'\''$/,"",v)
    print k, v
    next
  }
  {print}
' "$tmp" > "$tmp2"

mv "$tmp2" "$f"
rm -f "$tmp"

echo "✅ Normalized $f"
echo
echo "— Current contents —"
nl -ba "$f"
echo "— End —"
