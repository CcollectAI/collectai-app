from pathlib import Path
from datetime import datetime
import re

p = Path("app/events/[eventId].tsx")
if not p.exists():
    raise SystemExit(f"Missing file: {p}")

src = p.read_text(encoding="utf-8")
bak = p.with_suffix(p.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
bak.write_text(src, encoding="utf-8")

text = src

# A) Remove the bad injected JSX inside the useEffect that starts right after `loadUserFlags();`
# We detect the pattern:
#   loadUserFlags();
#   return (
#     <> ... Category ingress block ... </View>
#   return () => { mounted = false; };
#   }, [event?.id]);
#
# Replace everything from `return (` up to just before `}, [event?.id]);` with a proper cleanup return.
pattern = re.compile(
    r"(loadUserFlags\(\);\s*)return\s*\(\s*(?:.|\n)*?\n\s*return\s*\(\s*\)\s*=>\s*\{\s*mounted\s*=\s*false;\s*\}\s*;\s*\n\s*\},\s*\[event\?\.\s*id\]\s*\)\s*;",
    re.IGNORECASE
)

def repl(m: re.Match) -> str:
    return m.group(1) + "return () => { mounted = false; };\n  }, [event?.id]);"

new_text = pattern.sub(repl, text)

# If the above didn't match (because formatting differs), do a more permissive fix:
if new_text == text:
    # Find within the file: "loadUserFlags();" then the next occurrence of "}, [event?.id]);"
    # and replace the whole middle with a cleanup return.
    idx = text.find("loadUserFlags();")
    end = text.find("}, [event?.id]);", idx if idx != -1 else 0)
    if idx != -1 and end != -1:
        # slice from after loadUserFlags(); to end marker
        after = idx + len("loadUserFlags();")
        chunk = text[after:end]
        if "return (" in chunk and "/category-card" in chunk:
            new_text = (
                text[:after]
                + "\n\n    return () => { mounted = false; };\n"
                + text[end:]
            )

# B) Ensure any accidental Python boolean is fixed
new_text = re.sub(r"\bmounted\s*=\s*True\b", "mounted = true", new_text)

# C) Insert the Category ingress button into the SCREEN render (component return),
# but only if not already present outside the hook.
if "/category-card" not in new_text or "Ingress: Category -> Category Card" not in new_text:
    # If somehow missing entirely, we’ll insert later, but your file already has it.
    pass

# If the category ingress exists but might still be inside the hook, re-inject safely at top-level render:
# We'll remove any remaining ingress block that appears BEFORE `}, [event?.id]);`
marker_end = new_text.find("}, [event?.id]);")
if marker_end != -1:
    head = new_text[:marker_end]
    tail = new_text[marker_end:]
    # Remove any ingress block in the head if it exists
    head = re.sub(
        r"\s*\{\s*/\*\s*Ingress:\s*Category\s*->\s*Category\s*Card\s*\*/\s*\}\s*(?:.|\n)*?router\.push\(\{\s*pathname:\s*\"/category-card\"(?:.|\n)*?\}\s*\)\s*;\s*(?:.|\n)*?</View>\s*",
        "\n",
        head,
        flags=re.IGNORECASE
    )
    new_text = head + tail

# Now insert the ingress block into the FIRST component-level return (not a hook return).
ingress_block = r'''
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

# Only inject if it's not already present somewhere in the file
if "Ingress: Category -> Category Card" not in new_text:
    # Inject after the FIRST "return (" that is followed by JSX.
    # This is a heuristic but works well for Expo screens.
    new_text = re.sub(
        r"return\s*\(\s*\n\s*<",
        lambda m: "return (\n" + ingress_block + "\n      <",
        new_text,
        count=1
    )

if new_text == src:
    print("WARN: patch made no changes. File may be in a different shape than expected.")
else:
    p.write_text(new_text, encoding="utf-8")
    print(f"OK: patched {p} (backup: {bak.name})")
