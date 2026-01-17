from pathlib import Path
from datetime import datetime
import re

p = Path("app/events/[eventId].tsx")
src = p.read_text(encoding="utf-8")
bak = p.with_suffix(p.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
bak.write_text(src, encoding="utf-8")

# Ensure router is available (useRouter already exists in this file in most versions)
if "useRouter" not in src:
    raise SystemExit("Expected useRouter import/use already present. File differs; stop.")

# Insert ingress button right after the Top nav block comment if present.
needle = r"{/\*\s*Top nav\s*\*/}"
m = re.search(needle, src)
if not m:
    # fallback: after first <View style={styles.navRow}>
    m = re.search(r"<View\s+style=\{styles\.navRow\}>", src)
    if not m:
        raise SystemExit("Could not find nav block to anchor insertion.")

insert = """
        {/* Ingress: Category -> Category Card */}
        <View style={{ paddingHorizontal: 16, paddingTop: 10, paddingBottom: 6 }}>
          <Pressable
            onPress={() => {
              const cat =
                (typeof (event as any)?.category === "string" && (event as any).category) ||
                (typeof (event as any)?.categoryId === "string" && (event as any).categoryId) ||
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
            <Text style={{ fontSize: 12, fontWeight: "900", color: "#0b1f3a" }}>
              Category
            </Text>
          </Pressable>
        </View>
"""

# We want it AFTER the entire nav block, not inside it.
# Anchor after the navRow closing tag right after the navRow starts.
# Safer approach: insert after the first occurrence of the navRow block end comment.
# We'll insert right after the navRow closing </View> that follows the navRow start.
nav_start = re.search(r"<View\s+style=\{styles\.navRow\}>", src)
if not nav_start:
    raise SystemExit("navRow start not found.")

# Find the next "</View>" after navRow start
after = src[nav_start.start():]
end_idx = after.find("</View>")
if end_idx == -1:
    raise SystemExit("navRow end not found.")
# Move to end of that closing tag
end_pos = nav_start.start() + end_idx + len("</View>")

# Only insert if it isn't already there
if "/category-card" in src:
    # already has something; avoid duplicates
    print("OK: category ingress already present; no changes.")
    raise SystemExit(0)

patched = src[:end_pos] + insert + src[end_pos:]
p.write_text(patched, encoding="utf-8")
print(f"OK: patched {p} (backup: {bak.name})")
