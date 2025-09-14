import React, { useMemo, useState } from "react";
import { View, Text, ScrollView, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";
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

const S1: Pt[] = Array.from({ length: 24 }, (_, i) => ({ t: i, v: 4000 + Math.sin(i / 3) * 120 + i * 4 }));
const S7: Pt[] = Array.from({ length: 7 },  (_, i) => ({ t: i, v: 3800 + Math.sin(i) * 220 + i * 50 }));
const S30: Pt[] = Array.from({ length: 30 },(_, i) => ({ t: i, v: 3000 + Math.sin(i/2) * 260 + i * 35 }));

export default function PortfolioScreen() {
  const [range, setRange] = useState<"1D" | "7D" | "30D">("1D");
  const series = range === "1D" ? S1 : range === "7D" ? S7 : S30;
  const total = useMemo(() => ITEMS.reduce((s, x) => s + x.value, 0), []);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 32 }}>
        {/* Settings top-right */}
        <Pressable
          onPress={() => {}}
          style={{ alignSelf: "flex-end", padding: 6, marginTop: 4 }}
        >
          <Ionicons name="settings-outline" size={22} color={theme.colors.text} />
        </Pressable>

        {/* Title & value */}
        <Text style={{ ...theme.font.title, fontSize: 28, marginTop: 4 }}>Collection Value</Text>
        <Text style={{ ...theme.font.h1, fontSize: 24, marginTop: 2, marginBottom: 12 }}>€{fmtMoney(total)}</Text>

        {/* Range buttons aligned right */}
        <View style={{ alignItems: "flex-end", marginBottom: 10 }}>
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

        {/* Chart block */}
        <PortfolioChart data={series} />

        {/* Collection list with more inner padding */}
        <Text style={{ ...theme.font.h1, marginTop: 16, marginBottom: 8, color: theme.colors.brand.base }}>Collection</Text>
        <View style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, paddingHorizontal: 8 }}>
          {ITEMS
            .slice()
            .sort((a, b) => b.value - a.value)
            .map(it => (<ItemRow key={it.id} title={it.title} value={it.value} changePct={it.changePct} />))}
        </View>

        {/* Watchlist */}
        <Text style={{ ...theme.font.h1, marginTop: 24, marginBottom: 8, color: theme.colors.brand.base }}>Watchlist</Text>
        <View style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, paddingHorizontal: 8 }}>
          <ItemRow title="Pokémon Booster Box (Base Set)" value={127.0} changePct={+1.2} />
        </View>

        {/* Centered Add to watchlist */}
        <View style={{ alignItems: "center", marginTop: 14 }}>
          <Pressable style={{ paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: theme.colors.brand.base, backgroundColor: theme.colors.card }}>
            <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>+ Add to watchlist</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
