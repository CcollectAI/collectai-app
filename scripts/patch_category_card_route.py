from pathlib import Path
from datetime import datetime
import re

p = Path("app/category-card.tsx")
if not p.exists():
    raise SystemExit(f"Missing file: {p}")

src = p.read_text(encoding="utf-8")
bak = p.with_suffix(p.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
bak.write_text(src, encoding="utf-8")

text = src

# Ensure expo-router import
if "useLocalSearchParams" not in text:
    if re.search(r'from\s+"expo-router"', text):
        text = re.sub(
            r'import\s+\{([^}]+)\}\s+from\s+"expo-router";',
            lambda m: (
                m.group(0)
                if "useLocalSearchParams" in m.group(1)
                else f'import {{{m.group(1).strip()}, useLocalSearchParams}} from "expo-router";'
            ),
            text,
            count=1,
        )
    else:
        # insert after first import line
        lines = text.splitlines(True)
        inserted = False
        out = []
        for i, ln in enumerate(lines):
            out.append(ln)
            if not inserted and ln.startswith("import"):
                # insert after the first import statement block end (simple: after first line)
                out.append('import { useLocalSearchParams } from "expo-router";\n')
                inserted = True
                break
        if inserted:
            out.extend(lines[i+1:])
            text = "".join(out)

# Inject params usage inside component, right after function starts
if "useLocalSearchParams()" not in text:
    text = re.sub(
        r"export\s+default\s+function\s+CategoryCardDemo\s*\(\)\s*\{\s*",
        "export default function CategoryCardDemo() {\n  const params = useLocalSearchParams();\n  const category = String((params as any)?.category ?? 'Pokémon Cards');\n\n",
        text,
        count=1,
    )

# Replace the first demo card title with dynamic category + adjust subtitle
text = re.sub(
    r'title="Pokémon Cards"',
    'title={category}',
    text,
    count=1,
)

text = re.sub(
    r'subtitle="142 items · 7D \+3\.2%"',
    'subtitle="From Event → Category ingress"',
    text,
    count=1,
)

# Optional: if you want to show the category in the header too
text = re.sub(
    r"<Text style=\{\{ fontSize: 18, fontWeight: \"900\", color: \"#0b1f3a\" \}\}>Category Card</Text>",
    '<Text style={{ fontSize: 18, fontWeight: "900", color: "#0b1f3a" }}>Category: {category}</Text>',
    text,
    count=1,
)

p.write_text(text, encoding="utf-8")
print(f"OK: wrote {p} (backup: {bak.name})")
