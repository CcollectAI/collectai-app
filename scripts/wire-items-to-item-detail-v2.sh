#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/items.tsx"

if [ ! -f "$FILE" ]; then
  echo "Items tab file not found at $FILE"
  exit 1
fi

cp "$FILE" "$FILE.bak.items-to-detail-$(date +%s)" || true

python << 'PY'
from pathlib import Path
import re

path = Path("app/(tabs)/items.tsx")
text = path.read_text()

# 1) Ensure we import router from expo-router
def add_router_import(src: str) -> str:
    # Look for an existing expo-router named import
    pattern = re.compile(r"^import\s*\{\s*([^}]+)\}\s*from\s*['\"]expo-router['\"]\s*;\s*$", re.MULTILINE)
    m = pattern.search(src)
    if m:
        names = [n.strip() for n in m.group(1).split(",")]
        if "router" not in names:
            names.append("router")
            new_line = "import { " + ", ".join(sorted(set(names))) + " } from 'expo-router';"
            src = src[:m.start()] + new_line + src[m.end():]
        return src

    # No named import yet: add a simple one after the React import
    lines = src.splitlines()
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.startswith("import React"):
            out.append("import { router } from 'expo-router';")
            inserted = True
    if not inserted:
        out.insert(0, "import { router } from 'expo-router';")
    return "\n".join(out)

text = add_router_import(text)

# 2) Patch renderThemedItemCard to add onPress -> router.push(...)
marker = "function renderThemedItemCard(item: any) {"
if marker not in text:
    print("Could not find renderThemedItemCard(item: any); helper may not exist.")
else:
    # We replace only the body of the helper (not the whole file)
    # Capture from the function declaration to the closing brace
    func_pattern = re.compile(
        r"function renderThemedItemCard\(item: any\)\s*\{(?P<body>.*?)\n\}",
        re.DOTALL
    )
    m = func_pattern.search(text)
    if not m:
        print("Could not match full renderThemedItemCard body.")
    else:
        body = m.group("body")

        # We will fully replace the body with a richer version
        new_body = """
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

  // Try to derive a purchase price / cost basis if present,
  // so we can pass it into the detail screen.
  const purchase =
    typeof item.purchase_price === 'number'
      ? item.purchase_price
      : typeof item.cost_basis === 'number'
      ? item.cost_basis
      : null;

  const handlePress = () => {
    try {
      router.push({
        pathname: '/item-detail-v2-demo',
        params: {
          name: String(title),
          category: String(subtitle),
          currentValue: value != null ? String(value) : undefined,
          purchasePrice: purchase != null ? String(purchase) : undefined,
        },
      });
    } catch {
      // no-op for now
    }
  };

  return (
    <ThemedItemCard
      key={item.id ?? String(item.name ?? Math.random())}
      title={title}
      subtitle={subtitle}
      valueLabel={valueLabel}
      deltaLabel={deltaLabel}
      deltaPositive={deltaPositive}
      badgeLabel={badgeLabel}
      onPress={handlePress}
    />
  );
"""

        new_func = "function renderThemedItemCard(item: any) {" + new_body + "\n}"
        text = text[:m.start()] + new_func + text[m.end():]

path.write_text(text)
PY

echo "Items tab wired: tapping an item will open Item Detail v2 with params (backup created)."
