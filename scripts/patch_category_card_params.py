from pathlib import Path
from datetime import datetime
import re

p = Path("app/category-card.tsx")
src = p.read_text(encoding="utf-8")
bak = p.with_suffix(p.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
bak.write_text(src, encoding="utf-8")

if "useLocalSearchParams" not in src:
    src = src.replace(
        'import React from "react";',
        'import React from "react";\nimport { useLocalSearchParams } from "expo-router";'
    )

# Add param usage near component start
src = re.sub(
    r"export default function CategoryCardDemo\(\)\s*\{",
    'export default function CategoryCardDemo() {\n  const params = useLocalSearchParams();\n  const category = String((params as any)?.category ?? "uncategorized");',
    src
)

# Replace header line to show chosen category
src = src.replace(
    "<Text style={{ fontSize: 18, fontWeight: \"900\", color: \"#0b1f3a\" }}>Category Card</Text>",
    "<Text style={{ fontSize: 18, fontWeight: \"900\", color: \"#0b1f3a\" }}>Category: {category}</Text>"
)

p.write_text(src, encoding="utf-8")
print(f"OK: patched {p} (backup: {bak.name})")
