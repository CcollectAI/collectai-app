from pathlib import Path
from datetime import datetime
import re

p = Path("app/events/[eventId].tsx")
if not p.exists():
    raise SystemExit(f"Missing file: {p}")

src = p.read_text(encoding="utf-8")
bak = p.with_suffix(p.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
bak.write_text(src, encoding="utf-8")

# If already present, don't double-insert
if "/category-card" in src and "Ingress: Category" in src:
    print("OK: category ingress already present; no changes made.")
    raise SystemExit(0)

text = src

# Ensure router is available. If file imports useRouter, fine. If not, try to add it.
# We'll only add import if expo-router import exists.
if "useRouter" not in text:
    # If there's an expo-router import line, extend it. Otherwise, add a new one.
    m = re.search(r'^\s*import\s+\{([^}]+)\}\s+from\s+[\'"]expo-router[\'"]\s*;\s*$', text, flags=re.M)
    if m:
        inside = m.group(1).strip()
        if "useRouter" not in inside:
            new_inside = inside + ", useRouter"
            text = re.sub(r'^\s*import\s+\{[^}]+\}\s+from\s+[\'"]expo-router[\'"]\s*;\s*$',
                          f'import {{ {new_inside} }} from "expo-router";',
                          text, flags=re.M, count=1)
    else:
        # add after first React import
        text = re.sub(r'^\s*import\s+React[^;]*;\s*$',
                      lambda mm: mm.group(0) + '\nimport { useRouter } from "expo-router";',
                      text, flags=re.M, count=1)

# Ensure Pressable/Text/View are imported (most likely already are). We'll add if missing.
def ensure_named_import(module: str, names):
    nonlocal_text = text
    m = re.search(rf'^\s*import\s+\{{([^}}]+)\}}\s+from\s+[\'"]{re.escape(module)}[\'"]\s*;\s*$', nonlocal_text, flags=re.M)
    if not m:
        return nonlocal_text
    inside = [x.strip() for x in m.group(1).split(",")]
    changed = False
    for n in names:
        if n not in inside:
            inside.append(n)
            changed = True
    if changed:
        inside_str = ", ".join(inside)
        nonlocal_text = re.sub(rf'^\s*import\s+\{{[^}}]+\}}\s+from\s+[\'"]{re.escape(module)}[\'"]\s*;\s*$',
                               f'import {{ {inside_str} }} from "{module}";',
                               nonlocal_text, flags=re.M, count=1)
    return nonlocal_text

text = ensure_named_import("react-native", ["Pressable", "Text", "View"])

# If the component doesn't have router yet, ensure there's a const router = useRouter();
if "const router = useRouter()" not in text:
    # place it near other hooks: after useLocalSearchParams() or near top of component
    text = re.sub(
        r'(const\s+params\s*=\s*useLocalSearchParams\(\)\s*;)',
        r'\1\n  const router = useRouter();',
        text,
        count=1
    )

ingress = r'''
      {/* Ingress: Category -> Category Card */}
      <View style={{ paddingHorizontal: 16, paddingTop: 10, paddingBottom: 6 }}>
        <Pressable
          onPress={() => {
            const cat =
              (typeof (event as any)?.category === "string" && (event as any).category) ||
              (typeof (params as any)?.category === "string" && (params as any).category) ||
              "uncategorized";
            router.push({ pathname: "/category-card", params: { category: cat } } as any);
          }}
          style={{
            alignSelf: "flex-start",
            paddingHorizontal: 10,
            paddingVertical: 6,
            borderWidth: 1,
            borderColor: "#d7e6f2",
            backgroundColor: "#ffffff",
            borderRadius: 0,
          }}
        >
          <Text style={{ fontSize: 12, fontWeight: "900", color: "#0b1f3a" }}>Category</Text>
        </Pressable>
      </View>
'''

# Inject ingress into the MAIN render return:
# We insert right after the first fragment "<>" OR right after the first top-level container open.
inserted = False

# Try: after "return (" followed by "<>"
text2 = re.sub(r'return\s*\(\s*\n\s*<>\s*',
               lambda m: m.group(0) + "\n" + ingress,
               text, count=1)
if text2 != text:
    text = text2
    inserted = True

if not inserted:
    # Try: after "return (" then first "<SafeAreaView" / "<ScrollView" / "<View"
    text2 = re.sub(r'return\s*\(\s*\n\s*(<SafeAreaView\b|<ScrollView\b|<View\b)',
                   lambda m: "return (\n" + ingress + "\n      " + m.group(1),
                   text, count=1)
    if text2 != text:
        text = text2
        inserted = True

if not inserted:
    raise SystemExit("ERROR: Could not find a safe render insertion point. Please paste the first 80 lines of the component render.")

p.write_text(text, encoding="utf-8")
print(f"OK: patched {p} (backup: {bak.name})")
