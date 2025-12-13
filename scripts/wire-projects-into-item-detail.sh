#!/usr/bin/env bash
set -euo pipefail

FILE="app/item/[id].tsx"

if [ ! -f "$FILE" ]; then
  echo "Item detail file not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.projects-link-$(date +%s)" || true

# 1) Ensure Link from expo-router is available
perl -0pi -e '
  if ($_ !~ /import\s+\{\s*Link\s*\}\s+from\s+[\"\']expo-router[\"\']/) {
    s/(import\s+React[^\n]*\n)/$1import { Link } from '\''expo-router'\'';\n/;
  }
' "$FILE"

# 2) Inject a small "Track as project (beta)" card before the closing </ScrollView>
perl -0pi -e '
  s#</ScrollView>#        <View style={{ marginTop: spacing.lg }}>\n          <Link\n            href="/projects"\n            style={{\n              borderRadius: radii.lg,\n              padding: spacing.md,\n              backgroundColor: colors.card,\n            }}\n          >\n            <Text\n              style={{\n                fontSize: 14,\n                fontWeight: '\''600'\'',\n                color: colors.text,\n                marginBottom: spacing.xs,\n              }}\n            >\n              Track as project (beta)\n            </Text>\n            <Text\n              style={{\n                fontSize: 13,\n                color: colors.mutedText,\n              }}\n            >\n              Later this will create a project for this specific item. For now it opens your projects log.\n            </Text>\n          </Link>\n        </View>\n\n    </ScrollView># if $. == 0 || /<\/ScrollView>/;
' "$FILE"

echo "Patched $FILE with a 'Track as project (beta)' card linking to /projects. Backup created."
