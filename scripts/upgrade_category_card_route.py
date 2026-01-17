from pathlib import Path
from datetime import datetime

p = Path("app/category-card.tsx")
if not p.exists():
    raise SystemExit(f"Missing file: {p}")

src = p.read_text(encoding="utf-8")
bak = p.with_suffix(p.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
bak.write_text(src, encoding="utf-8")

new = """import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, SafeAreaView, Text, View, Pressable } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import CategoryCard from "@/components/CategoryCard";
import { getPortfolioItems } from "@/services/collectorsClient";

function formatEUR(v: number) {
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "EUR" }).format(v);
  } catch {
    return `€ ${v.toFixed(2)}`;
  }
}

export default function CategoryCardRoute() {
  const params = useLocalSearchParams();
  const router = useRouter();
  const category = String((params as any)?.category ?? "Pokémon Cards");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<any[]>([]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getPortfolioItems();
        if (cancelled) return;
        setItems(Array.isArray(data) ? data : []);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? "Failed to load items");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(() => {
    const arr = Array.isArray(items) ? items : [];
    const filtered = arr.filter((it) => {
      const c = String(it?.category ?? it?.category_label ?? it?.categoryLabel ?? "").trim();
      return c.toLowerCase() === category.toLowerCase();
    });

    const total = filtered.reduce((sum, it) => {
      const v =
        it?.estimated_value ??
        it?.value ??
        it?.current_value ??
        it?.currentValue ??
        it?.market_value ??
        it?.marketValue ??
        it?.price;
      return sum + (typeof v === "number" && isFinite(v) ? v : 0);
    }, 0);

    return { count: filtered.length, total };
  }, [items, category]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: "#e7fbff" }}>
      <View style={{ padding: 16 }}>
        <Text style={{ fontSize: 18, fontWeight: "900", color: "#0b1f3a" }}>
          Category
        </Text>
        <Text style={{ marginTop: 6, fontSize: 13, fontWeight: "700", color: "#5f6b7a" }}>
          {category}
        </Text>

        <View style={{ marginTop: 14 }}>
          {loading ? (
            <View style={{ paddingVertical: 24 }}>
              <ActivityIndicator />
            </View>
          ) : error ? (
            <View style={{ padding: 14, backgroundColor: "#ffffff", borderWidth: 1, borderColor: "#d7e6f2" }}>
              <Text style={{ fontWeight: "900", color: "#0b1f3a" }}>Couldn’t load</Text>
              <Text style={{ marginTop: 6, color: "#5f6b7a" }}>{error}</Text>
            </View>
          ) : (
            <>
              <CategoryCard
                title={category}
                subtitle={`${stats.count} items`}
                badge={stats.count > 100 ? "GOLD" : stats.count > 30 ? "SILVER" : "BRONZE"}
                valueText={formatEUR(stats.total)}
                onPress={() => {}}
              />

              <View style={{ marginTop: 14, flexDirection: "row", gap: 10 }}>
                <Pressable
                  onPress={() => router.back()}
              style={{ flex: 1, paddingVertical: 10, backgroundColor: "#ffffff", borderWidth: 1, borderColor: "#d7e6f2" }}>
                  <Text style={{ textAlign: "center", fontWeight: "900", color: "#0b1f3a" }}>Back</Text>
                </Pressable>

                <Pressable
                  onPress={() => router.push({ pathname: "/(tabs)/items", params: { category } } as any)}
                  style={{ flex: 1, paddingVertical: 10, backgroundColor: "#ffffff", borderWidth: 1, borderColor: "#d7e6f2" }}>
                  <Text style={{ textAlign: "center", fontWeight: "900", color: "#0b1f3a" }}>View items</Text>
                </Pressable>
              </View>
            </>
          )}
        </View>
      </View>
    </SafeAreaView>
  );
}
"""

p.write_text(new, encoding="utf-8")
print(f"OK: upgraded {p} (backup: {bak.name})")
