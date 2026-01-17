#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime

TARGET = Path("app/(tabs)/index.tsx")

BTN_BLOCK = """\
      {/* DEV: quick access */}
      <Link href="/category-card" asChild>
        <Pressable
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            zIndex: 9999,
            paddingHorizontal: 10,
            paddingVertical: 6,
            backgroundColor: "#ffffff",
            borderWidth: 1,
            borderColor: "#d7e6f2",
            borderRadius: 0,
          }}
        >
          <Text style={{ fontSize: 12, fontWeight: "900", color: "#0b1f3a" }}>
            Category Card
          </Text>
        </Pressable>
      </Link>
"""

def backup(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak.{ts}")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return bak

def ensure_expo_router_link_import(src: str) -> str:
    # If there's already an expo-router import, add Link into it.
    m = re.search(r'^\s*import\s+\{([^}]+)\}\s+from\s+[\'"]expo-router[\'"];\s*$', src, flags=re.M)
    if m:
        items = [x.strip() for x in m.group(1).split(",") if x.strip()]
        if "Link" not in items:
            items.append("Link")
            new_line = f'import {{ {", ".join(items)} }} from "expo-router";'
            src = re.sub(r'^\s*import\s+\{[^}]+\}\s+from\s+[\'"]expo-router[\'"];\s*$',
                         new_line, src, flags=re.M)
        return src

    # Otherwise insert a new import near other imports
    lines = src.splitlines(True)
    insert_at = 0
    # place after last import line if exists
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            insert_at = i + 1
    lines.insert(insert_at, 'import { Link } from "expo-router";\n')
    return "".join(lines)

def ensure_pressable_in_react_native(src: str) -> str:
    # Handle: import { A, B } from 'react-native';
    m = re.search(r'^\s*import\s+\{([^}]+)\}\s+from\s+[\'"]react-native[\'"];\s*$', src, flags=re.M)
    if m:
        items = [x.strip() for x in m.group(1).split(",") if x.strip()]
        changed = False
        for need in ("Pressable",):
            if need not in items:
                items.append(need)
                changed = True
        if changed:
            new_line = f'import {{ {", ".join(items)} }} from "react-native";'
            src = re.sub(r'^\s*import\s+\{[^}]+\}\s+from\s+[\'"]react-native[\'"];\s*$',
                         new_line, src, flags=re.M)
        return src

    # If the file uses "from 'react-native'" only via default/namespace imports, add a named import.
    lines = src.splitlines(True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            insert_at = i + 1
    lines.insert(insert_at, 'import { Pressable } from "react-native";\n')
    return "".join(lines)

def already_has_button(src: str) -> bool:
    return 'href="/category-card"' in src or "Category Card" in src

def insert_after_safeareaview(src: str) -> str:
    if already_has_button(src):
        return src

    lines = src.splitlines(True)
    for i, line in enumerate(lines):
        if "<SafeAreaView" in line:
            # Insert immediately after this line
            indent = re.match(r'^(\s*)', line).group(1)
            block = "".join(indent + l if l.strip() else l for l in BTN_BLOCK.splitlines(True))
            lines.insert(i + 1, block)
            return "".join(lines)

    raise SystemExit("Could not find <SafeAreaView ...> in app/(tabs)/index.tsx to insert the button safely.")

def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"Missing target file: {TARGET}")

    src = TARGET.read_text(encoding="utf-8")

    bak = backup(TARGET)

    src = ensure_expo_router_link_import(src)
    src = ensure_pressable_in_react_native(src)
    src = insert_after_safeareaview(src)

    TARGET.write_text(src, encoding="utf-8")

    print(f"OK: wrote {TARGET}")
    print(f"Backup: {bak}")

if __name__ == "__main__":
    main()
