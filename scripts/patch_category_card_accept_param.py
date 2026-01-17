from pathlib import Path
from datetime import datetime
import re

p = Path("app/category-card.tsx")
src = p.read_text(encoding="utf-8")
bak = p.with_suffix(p.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
bak.write_text(src, encoding="utf-8")

text = src

# Ensure useLocalSearchParams import
if "useLocalSearchParams" not in text:
    if 'from "expo-router"' in text:
        text = re.sub(r'from\s+"expo-router";', 'from "expo-router";', text)
    else:
        text = re.sub(
            r'^\s*import\s+React[^;]*;\s*$',
            lambda m: m.group(0) + '\nimport { useLocalSearchParams } from "expo-router";',
            text,
            flags=re.M,
            count=1
        )

# Replace component with param-aware header (keep your CategoryCard demo items for now)
text = re.sub(
    r'export default function CategoryCardDemo\(\)\s*\{[\s\S]*?\n\}',
    """export default function CategoryCardDemo() {
  const params = useLocalSearchParams();
  const category = String((params as any)?.category ?? "Category");

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: "#e7fbff" }}>
      <View style={{ padding: 16 }}>
        <Text style={{ fontSize: 18, fontWeight: "900", color: "#0b1f3a" }}>{category}</Text>
        <Text style={{ marginTop: 6, fontSize: 13, fontWeight: "600", color: "#5f6b7a" }}>
          Category overview (wired from Event ingress).
        </Text>

        <View style={{ marginTop: 14 }}>
          <CategoryCard
            title={category}
            subtitle="Demo stats · 7D +0.0%"
            badge="GOLD"
            valueText="€ 0.00"
            onPress={() => {}}
          />
        </View>
      </View>
    </SafeAreaView>
  );
}""",
    text,
    count=1
)

p.write_text(text, encoding="utf-8")
print(f"OK: patched {p} (backup: {bak.name})")
