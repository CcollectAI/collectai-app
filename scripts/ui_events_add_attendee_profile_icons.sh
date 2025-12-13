#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/events.tsx"
[ -f "$FILE" ] || { echo "❌ Missing $FILE"; exit 1; }

TS="$(date +%Y%m%d_%H%M%S)"
cp "$FILE" "$FILE.bak_attendees_$TS"
echo "✅ Backup: $FILE.bak_attendees_$TS"

# We patch by appending a small block at the bottom and injecting a render section
python3 - <<'PY'
import re, pathlib
p = pathlib.Path("app/(tabs)/events.tsx")
s = p.read_text()

# Ensure useRouter is imported
if "useRouter" not in s:
    # expo-router import
    if re.search(r'from\s+"expo-router";', s):
        s = re.sub(r'from\s+"expo-router";',
                   'from "expo-router";\nimport { useRouter } from "expo-router";',
                   s, count=1)
    else:
        # add a new import line after existing imports
        s = re.sub(r'(\n)(\s*export\s+default\s+function|\s*export\s+default\s*\()',
                   '\nimport { useRouter } from "expo-router";\n\\2',
                   s, count=1)

# If already has our marker, don't duplicate
if "MEETUP_ATTENDEES__MOCK" in s:
    p.write_text(s)
    print("✅ Attendee block already present; no duplicate changes.")
    raise SystemExit(0)

# Inject: inside default component, add router const
s = re.sub(
    r'(export\s+default\s+function\s+\w+\s*\(\)\s*{\s*)',
    r'\1\n  const router = useRouter();\n',
    s,
    count=1
)

# Find a place to insert UI: before final closing of main return container.
# We'll insert before the last occurrence of "</ScrollView>" OR before the last "</View>" if no ScrollView.
insert_block = r'''
        {/* Meetups: attendees (opt-in) */}
        <View style={{ marginTop: 14 }}>
          <Text style={{ fontSize: 14, fontWeight: "900", color: "#0b1f3a", marginBottom: 8 }}>
            Attendees
          </Text>

          <View style={{ flexDirection: "row", gap: 10, flexWrap: "wrap" }}>
            {MEETUP_ATTENDEES__MOCK.filter(a => a.optedIn).map((a) => (
              <Pressable
                key={a.id}
                onPress={() =>
                  router.push({
                    pathname: "/users/[id]",
                    params: {
                      id: a.id,
                      name: a.name,
                      handle: a.handle,
                      city: a.city,
                      bio: a.bio,
                    },
                  })
                }
                hitSlop={10}
                style={{ alignItems: "center" }}
              >
                <AvatarBubble label={a.name} />
              </Pressable>
            ))}
          </View>
        </View>
'''

if "</ScrollView>" in s:
    s = s.replace("</ScrollView>", insert_block + "\n      </ScrollView>", 1)
else:
    # try insert before last return close
    m = list(re.finditer(r'\n\s*return\s*\(\s*', s))
    if not m:
        raise SystemExit("❌ Could not find return( in events.tsx")
    # insert before last closing of component: safest at end, before final ');'
    s = s.replace("\n  );\n}", insert_block + "\n  );\n}", 1)

# Append helper + mock data near bottom (before styles if possible)
append = r'''

// --- Meetups Attendees (opt-in) ---
// Replace with real attendee data later.
const MEETUP_ATTENDEES__MOCK = [
  { id: "u1", name: "Mina", handle: "@mina.cards", city: "Amsterdam", bio: "Pokémon + Lorcana. Meetups & trades.", optedIn: true },
  { id: "u2", name: "Jay", handle: "@jay.collects", city: "Utrecht", bio: "Funko + Diecast. Looking for swaps.", optedIn: true },
  { id: "u3", name: "Sofia", handle: "@sofia.tcgs", city: "Rotterdam", bio: "MTG sealed. Casual meetups.", optedIn: false },
];

function AvatarBubble({ label }: { label: string }) {
  const ch = (label?.trim()?.[0] ?? "C").toUpperCase();
  return (
    <View
      style={{
        width: 34,
        height: 34,
        borderRadius: 17,
        backgroundColor: "rgba(20,184,166,0.18)",
        alignItems: "center",
        justifyContent: "center",
        borderWidth: 1,
        borderColor: "rgba(11,31,58,0.08)",
      }}
    >
      <Text style={{ fontWeight: "900", color: "#0b1f3a" }}>{ch}</Text>
    </View>
  );
}
'''

# Put append before StyleSheet.create if present
if "StyleSheet.create" in s:
    s = re.sub(r'(const\s+styles\s*=\s*StyleSheet\.create\()', append + r'\n\1', s, count=1)
else:
    s += "\n" + append

p.write_text(s)
print("✅ Patched events.tsx with tappable attendee avatars → /users/[id].")
PY

echo "✅ Events attendees icons added."
echo "🛑 SANITY CHECK: npx expo start --tunnel"
