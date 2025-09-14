import React, { useMemo, useState } from "react";
import { View, Text, ScrollView, Pressable } from "react-native";
import { theme } from "@/theme";
import PortfolioChart, { Pt } from "@/components/PortfolioChart";
import ItemRow from "@/components/ItemRow";
import { fmtMoney } from "@/utils/format";

type Item = { id: string; title: string; value: number; changePct: number };
const ITEMS: Item[] = [
  { id: "1", title: "Charizard Holo 1999", value: 1240, changePct: +3.1 },
  { id: "2", title: "LEGO Falcon 75192", value: 680, changePct: -1.4 },
  { id: "3", title: "Funko Pop Pikachu", value: 22, changePct: 0.0 },
  { id: "4", title: "PSA 10 Mewtwo", value: 810, changePct: +0.8 },
];

const SERIES_1D: Pt[] = Array.from({ length: 24 }, (_, i) => ({ t: i, v: 4000 + Math.sin(i / 3) * 120 + i * 4 }));
const SERIES_7D: Pt[] = Array.from({ length: 7 }, (_, i) => ({ t: i, v: 3800 + Math.sin(i) * 220 + i * 50 }));
const SERIES_30D: Pt[] = Array.from({ length: 30 }, (_, i) => ({ t: i, v: 3000 + Math.sin(i/2) * 260 + i * 35 }));

export default function PortfolioScreen() {
  const [range, setRange] = useState<"1D" | "7D" | "30D">("1D");
  const series = range === "1D" ? SERIES_1D : range === "7D" ? SERIES_7D : SERIES_30D;
  const total = useMemo(() => ITEMS.reduce((s, x) => s + x.value, 0), []);
  const pct = useMemo(() => {
    // very rough mock: compare end vs start
    const start = series[0]?.v ?? 1;
    const end = series[series.length - 1]?.v ?? 1;
    return ((end - start) / start) * 100;
  }, [series]);

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <View style={{ padding: 16 }}>
        <Text style={{ ...theme.font.title, fontSize: 28, marginBottom: 2 }}>CollectAI</Text>
        <Text style={{ ...theme.font.h1, fontSize: 24, marginBottom: 4 }}>€{fmtMoney(total)}</Text>
        <Text style={{ color: pct >= 0 ? theme.colors.up : theme.colors.down, marginBottom: 12 }}>
          {pct >= 0 ? "+" : ""}{pct.toFixed(2)}% today
        </Text>

        <View style={{ alignItems: "flex-end", marginBottom: 8 }}>
          <View style={{ flexDirection: "row", gap: 8 }}>
            {(["1D","7D","30D"] as const).map(label => (
              <Pressable
                key={label}
                onPress={() => setRange(label)}
                style={{
                  paddingHorizontal: 10, paddingVertical: 6,
                  borderWidth: 1, borderColor: theme.colors.border,
                  backgroundColor: label === range ? theme.colors.card : "transparent"
                }}
              >
                <Text style={{ color: theme.colors.text, fontSize: 12 }}>{label}</Text>
              </Pressable>
            ))}
          </View>
        </View>

        <View style={{ borderWidth: 1, borderColor: theme.colors.border, marginBottom: 16 }}>
          <PortfolioChart data={series} height={180} width={Math.min(360, 1000)} />
        </View>

        <Text style={{ ...theme.font.h1, marginBottom: 8, color: theme.colors.brand.base }}>Collection</Text>
        <View style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
          {ITEMS
            .slice()
            .sort((a, b) => b.value - a.value)
            .map(it => (<ItemRow key={it.id} title={it.title} value={it.value} changePct={it.changePct} />))}
        </View>

        <Text style={{ ...theme.font.h1, marginTop: 24, marginBottom: 8, color: theme.colors.brand.base }}>Watchlist</Text>
        <View style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
          <ItemRow title="Pokémon Booster Box (Base Set)" value={127.0} changePct={+1.2} />
        </View>
        <View style={{ alignItems: "flex-start", marginTop: 8 }}>
          <Pressable style={{ paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
            <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>+ Add to watchlist</Text>
          </Pressable>
        </View>
      </View>
    </ScrollView>
  );
}
