#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/items.tsx"

if [ ! -f "$FILE" ]; then
  echo "Items tab file not found at $FILE"
  exit 1
fi

cp "$FILE" "${FILE}.bak.themed-card-$(date +%s)" || true

python << 'PY'
from pathlib import Path

path = Path("app/(tabs)/items.tsx")
text = path.read_text()

# 1) Add ThemedItemCard import if missing
import_line = "import ThemedItemCard from '@/components/ThemedItemCard';"
if import_line not in text:
    lines = text.splitlines()
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        # Insert after the first non-empty import block
        if not inserted and line.startswith("import") and "React" in line:
            # We insert after the React import line
            new_lines.append(import_line)
            inserted = True
    if not inserted:
        new_lines.insert(0, import_line)
    text = "\n".join(new_lines)

# 2) Append a helper snippet at the end of the file (commented)
helper = """

// --- Themed item card helper (not wired yet) ---
// You can use this inside your items map instead of your current row.
// Example usage:
//   {items.map((item) => renderThemedItemCard(item))}
function renderThemedItemCard(item: any) {
  // TODO: adjust these field names to match your actual item shape.
  const title = item.name ?? item.title ?? 'Untitled item';
  const subtitle = item.category ?? item.category_name ?? '';
  const value = typeof item.current_value === 'number'
    ? item.current_value
    : typeof item.estimated_value === 'number'
    ? item.estimated_value
    : null;
  const pl = typeof item.pl_pct === 'number'
    ? item.pl_pct
    : null;

  const valueLabel = value != null
    ? new Intl.NumberFormat('de-DE', {
        style: 'currency',
        currency: 'EUR',
        maximumFractionDigits: 0,
      }).format(value)
    : undefined;

  let deltaLabel: string | undefined = undefined;
  let deltaPositive: boolean | null = null;
  if (pl != null && Number.isFinite(pl)) {
    const pct = Math.round(pl * 1000) / 10; // e.g. 0.124 -> 12.4
    deltaLabel = `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`;
    deltaPositive = pct > 0 ? true : pct < 0 ? false : null;
  }

  const badgeLabel =
    item.category ??
    item.category_name ??
    item.segment ??
    undefined;

  return (
    <ThemedItemCard
      key={item.id ?? String(item.name ?? Math.random())}
      title={title}
      subtitle={subtitle}
      valueLabel={valueLabel}
      deltaLabel={deltaLabel}
      deltaPositive={deltaPositive}
      badgeLabel={badgeLabel}
    />
  );
}
"""
if "Themed item card helper" not in text:
    text = text.rstrip() + helper + "\n"
else:
    print("Helper already present; not duplicating.")

path.write_text(text)
PY

echo "Prepared app/(tabs)/items.tsx with ThemedItemCard import + helper. Backup created."
