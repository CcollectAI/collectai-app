#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/index.tsx"
if [ ! -f "$FILE" ]; then
  echo "ERROR: $FILE not found"
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
cp "$FILE" "${FILE}.bak_disable_hoverchart_${TS}"

# Remove named import that includes PortfolioHoverChart
perl -pi -e 's/^\s*import\s+\{([^}]*)\}\s+from\s+([\"\x27][^\"\x27]+[\"\x27]);\s*$/
  my $a=$1; my $b=$2;
  if ($a =~ /\bPortfolioHoverChart\b/) {
    $a =~ s/\bPortfolioHoverChart\b\s*,?\s*//g;
    $a =~ s/,\s*,/,/g;
    $a =~ s/^\s*,\s*//;
    $a =~ s/\s*,\s*$//;
    if ($a =~ /^\s*$/) { "" } else { "import {$a} from $b;\n" }
  } else {
    $_
  }
 /egm' "$FILE" || true

# Remove default import PortfolioHoverChart (if present)
perl -pi -e 's/^\s*import\s+PortfolioHoverChart\s+from\s+[\"\x27][^\"\x27]+[\"\x27];\s*$//gm' "$FILE" || true

# Replace the JSX usage with a spacer
perl -0777 -pi -e 's/<PortfolioHoverChart\b[\s\S]*?\/>/<View style={{ height: 220 }} \/>/g' "$FILE"

echo "OK: Disabled PortfolioHoverChart in $FILE"
echo "Backup: ${FILE}.bak_disable_hoverchart_${TS}"
