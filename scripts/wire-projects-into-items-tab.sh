#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/items.tsx"

if [ ! -f "$FILE" ]; then
  echo "Items tab file not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.projects-link-$(date +%s)" || true

# 1) Ensure we can use Link from expo-router
# If there's already an import from 'expo-router', this will just add another line, which is valid.
perl -0pi -e '
  if ($_ !~ /import\s+\{\s*Link\s*\}\s+from\s+[\"\']expo-router[\"\']/) {
    s/(import\s+React[^\n]*\n)/$1import { Link } from '\''expo-router'\'';\n/;
  }
' "$FILE"

# 2) Inject a card linking to /projects before the closing </ScrollView>
perl -0pi -e '
  s#</ScrollView>#        <View style={{ marginTop: spacing.lg }}>\n          <Link\n            href="/projects"\n            style={{\n              borderRadius: radii.lg,\n              padding: spacing.md,\n              backgroundColor: colors.card,\n            }}\n          >\n            <Text\n              style={{\n                fontSize: 14,\n                fontWeight: '\''600'\'',\n                color: colors.text,\n                marginBottom: spacing.xs,\n              }}\n            >\n              Build & paint projects\n            </Text>\n            <Text\n              style={{\n                fontSize: 13,\n                color: colors.mutedText,\n              }}\n            >\n              Open your long-running build and paint projects log.\n            </Text>\n          </Link>\n        </View>\n\n    </ScrollView># if $. == 0 || /<\/ScrollView>/;
' "$FILE"

echo "Patched $FILE with a 'Build & paint projects' card linking to /projects. Backup created."
