from pathlib import Path
from datetime import datetime
import re

p = Path("app/events/[eventId].tsx")
src = p.read_text(encoding="utf-8")

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
bak = p.with_suffix(p.suffix + f".bak.{ts}")
bak.write_text(src, encoding="utf-8")

text = src

# 1) Remove duplicate useLocalSearchParams declarations in EventDetailScreen block
# Keep: const params = useLocalSearchParams();
# Replace: const { eventId } = useLocalSearchParams<{ eventId?: string }>(); -> derive from params
text = re.sub(
    r'^\s*const\s+\{\s*eventId\s*\}\s*=\s*useLocalSearchParams<\{[^}]*\}>\(\)\s*;\s*$',
    '  const eventId = String((params as any)?.eventId ?? "");',
    text,
    flags=re.M
)

# 2) Fix "Event not found" block: remove stray </> and keep proper closing
# Replace the invalid snippet:
#   return (
#     <View ...>...</View>
#   </> );
# into:
#   return (
#     <View ...>...</View>
#   );
text = re.sub(
    r'return\s*\(\s*\n(\s*<View\b[\s\S]*?\n\s*</View>\s*)\n\s*</>\s*\n\s*\);\s*',
    r'return (\n\1\n    );',
    text,
    flags=re.M
)

# 3) Move "isAttending" hook out of openExternal (remove any hook line inside openExternal)
text = re.sub(
    r'^\s*//\s*RSVP state[\s\S]*?const\s+\[isAttending,\s*setIsAttending\]\s*=\s*useState\([^)]+\);\s*$',
    '',
    text,
    flags=re.M
)

# Ensure RSVP state is defined once at top-level near other state.
# Insert after saved/alerts state if not already present.
if "const [isAttending, setIsAttending]" not in text:
    text = re.sub(
        r'(const\s+\[saved,\s*setSaved\]\s*=\s*useState\([^)]+\);\s*)',
        r'\1\n\n  // RSVP state (wire persistence later)\n  const [isAttending, setIsAttending] = useState(false);\n',
        text,
        count=1
    )

# 4) Ensure router exists
if "const router = useRouter();" not in text:
    text = re.sub(
        r'(export default function EventDetailScreen\(\)\s*\{\s*\n)',
        r'\1  const router = useRouter();\n',
        text,
        count=1
    )

# Ensure useRouter import exists
if "useRouter" not in text:
    m = re.search(r'^\s*import\s+\{([^}]+)\}\s+from\s+[\'"]expo-router[\'"]\s*;\s*$', text, flags=re.M)
    if m:
        inside = m.group(1).strip()
        if "useRouter" not in inside:
            text = re.sub(
                r'^\s*import\s+\{[^}]+\}\s+from\s+[\'"]expo-router[\'"]\s*;\s*$',
                f'import {{ {inside}, useRouter }} from "expo-router";',
                text,
                flags=re.M,
                count=1
            )
    else:
        # add a new import after React import
        text = re.sub(
            r'^\s*import\s+React[^;]*;\s*$',
            lambda mm: mm.group(0) + '\nimport { useRouter } from "expo-router";',
            text,
            flags=re.M,
            count=1
        )

# Ensure Pressable/Text/View imported from react-native (most files already have them)
# We won't try to rework imports heavily; just ensure Category ingress uses existing components.

# 5) Inject Category ingress button inside the MAIN render (the ScrollView return)
# We inject right after the Hero card opening comment OR right after <ScrollView ...> open.
if "/category-card" not in text:
    ingress = """
        {/* Ingress: Category -> Category Card */}
        <View style={{ paddingHorizontal: 16, paddingTop: 10, paddingBottom: 0 }}>
          <Pressable
            onPress={() => {
              const cat =
                (typeof (relatedCategory as any)?.name === "string" && (relatedCategory as any).name) ||
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
            accessibilityRole="button"
            accessibilityLabel="Open category card"
          >
            <Text style={{ fontSize: 12, fontWeight: "900", color: "#0b1f3a" }}>Category</Text>
          </Pressable>
        </View>
"""

    # Insert after the <ScrollView ...> line, before Top nav
    text2 = re.sub(
        r'(\n\s*return\s*\(\s*\n\s*<ScrollView[\s\S]*?>\s*\n)',
        r'\1' + ingress + '\n',
        text,
        count=1
    )
    text = text2

p.write_text(text, encoding="utf-8")
print(f"OK: patched {p} (backup: {bak.name})")
