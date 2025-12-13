#!/usr/bin/env bash
set -euo pipefail

read -rp "Paste ANON_KEY: " ANON_KEY
read -rp "Paste SERVICE_ROLE_KEY: " SERVICE_ROLE_KEY

# quick shape checks: JWT has two dots
case "$ANON_KEY" in
  *.*.*) ;; *) echo "❌ ANON_KEY doesn't look like a JWT"; exit 1;;
esac
case "$SERVICE_ROLE_KEY" in
  *.*.*) ;; *) echo "❌ SERVICE_ROLE_KEY doesn't look like a JWT"; exit 1;;
esac

cat > supa_test.env <<ENV
SUPA_REF=ykqrruipzmrrvjcvwfgp
ANON_KEY=$ANON_KEY
SERVICE_ROLE_KEY=$SERVICE_ROLE_KEY
TEST_EMAIL=tester@example.com
TEST_PASSWORD=SetAStrongTempPassword123!
ENV

echo "✅ Wrote supa_test.env"
nl -ba supa_test.env | sed -n '1,6p'
