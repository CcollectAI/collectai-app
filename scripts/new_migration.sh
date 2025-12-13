#!/usr/bin/env bash
set -euo pipefail
name="${1:-manual_patch}"
ts=$(date -u +%Y%m%d%H%M%S)
file="supabase/migrations/${ts}_${name}.sql"
: > "$file"; echo "Created $file"; printf "%s\n" "-- write SQL here" >> "$file"
