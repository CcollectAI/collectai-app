#!/usr/bin/env bash
# ============================================================
# Atlantis — Run All Database Migrations
# ============================================================
# Runs all SQL migration files against your Supabase database
# in the correct order.
#
# Usage:
#   ./scripts/run_migrations.sh <DATABASE_URL>
#
# Example:
#   ./scripts/run_migrations.sh "postgresql://postgres:password@db.ykqrruipzmrrvjcvwfgp.supabase.co:5432/postgres"
#
# Or paste the connection string from Supabase > Settings > Database > Connection string (URI)
# ============================================================

set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: ./scripts/run_migrations.sh <DATABASE_URL>"
  echo ""
  echo "Get your DATABASE_URL from Supabase:"
  echo "  Dashboard > Settings > Database > Connection string (URI)"
  exit 1
fi

DB_URL="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0

echo ""
echo "═══════════════════════════════════════════════"
echo "  Atlantis — Database Migration Runner"
echo "═══════════════════════════════════════════════"
echo ""

# Migration files in order
MIGRATIONS=(
  "migrations/20251004_0001_init.sql"
  "migrations/20251004_0002_watchlist_category.sql"
  "migrations/20251004_0003_trigram.sql"
  "migrations/20251004_0004_alerts.sql"
  "migrations/20251004_0005_alert_endpoints.sql"
  "migrations/20251004_0006_alert_endpoints_slack.sql"
  "migrations/20251004_add_model_registry.sql"
  "migrations/001_agent_events.sql"
  "server/supabase/migrations/20260315_user_alert_preferences.sql"
)

for migration in "${MIGRATIONS[@]}"; do
  filepath="$SCRIPT_DIR/$migration"
  filename=$(basename "$migration")

  if [ ! -f "$filepath" ]; then
    printf "\033[33m⚠ Skipping (not found): %s\033[0m\n" "$filename"
    continue
  fi

  printf "  Running: %s ... " "$filename"

  if psql "$DB_URL" -f "$filepath" > /dev/null 2>&1; then
    printf "\033[32m✓\033[0m\n"
    PASS=$((PASS+1))
  else
    # Try again with error output visible
    if psql "$DB_URL" -f "$filepath" 2>&1 | grep -q "already exists"; then
      printf "\033[33m(already applied)\033[0m\n"
      PASS=$((PASS+1))
    else
      printf "\033[31m✗ FAILED\033[0m\n"
      FAIL=$((FAIL+1))
      echo "    Error details:"
      psql "$DB_URL" -f "$filepath" 2>&1 | head -5 | sed 's/^/    /'
    fi
  fi
done

echo ""
echo "═══════════════════════════════════════════════"
printf "  Results: \033[32m%d passed\033[0m, \033[31m%d failed\033[0m\n" "$PASS" "$FAIL"
echo "═══════════════════════════════════════════════"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "  Some migrations failed. Check the errors above."
  echo "  You may need to run them manually via Supabase SQL Editor."
  exit 1
else
  echo "  All migrations applied successfully!"
  echo ""
  echo "  Next: Enable Realtime on chat_messages_v1 table"
  echo "    Supabase Dashboard > Database > Replication > Enable on chat_messages_v1"
  echo ""
fi
