import React, { useMemo } from "react";
import { View, Text, ScrollView, Pressable } from "react-native";
import { theme } from "@/theme";
import ItemRow from "@/components/ItemRow";
import BadgeIcon from "@/components/BadgeIcon";
import { fmtMoney } from "@/utils/format";

type Item = { id: string; title: string; category: string; value: number; changePct: number };
const ITEMS: Item[] = [
  { id: "1", title: "Charizard Holo 1999", category: "Pokémon", value: 1240, changePct: +3.1 },
  { id: "2", title: "LEGO Falcon 75192", category: "LEGO", value: 680, changePct: -1.4 },
  { id: "3", title: "Funko Pop Pikachu", category: "Funko", value: 22, changePct: 0.0 },
  { id: "4", title: "PSA 10 Mewtwo", category: "Pokémon", value: 810, changePct: +0.8 },
];

export default function ItemsScreen() {
  const groups = useMemo(() => {
    const by: Record<string, Item[]> = {};
    for (const it of ITEMS) (by[it.category] ||= []).push(it);
    const arr = Object.entries(by).map(([category, items]) => ({
      category,
      items: items.sort((a, b) => b.value - a.value),
      total: items.reduce((s, x) => s + x.value, 0),
    }));
    return arr.sort((a, b) => b.total - a.total);
  }, []);

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <View style={{ padding: 16 }}>
        {/* Title + Share top-right */}
        <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 8 }}>
          <Text style={{ ...theme.font.title, fontSize: 28, flex: 1 }}>Items</Text>
          <Pressable onPress={() => {}} style={{ paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
            <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>Share</Text>
          </Pressable>
        </View>

        {groups.map(g => (
          <View key={g.category} style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, marginTop: 12 }}>
            <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: theme.colors.border }}>
              <Text style={{ ...theme.font.h1, flex: 1 }}>{g.category}</Text>
              <BadgeIcon tier={g.category === "Pokémon" ? "gold" : g.category === "LEGO" ? "silver" : "bronze"} />
            </View>
            <View style={{ paddingHorizontal: 12 }}>
              {g.items.map(it => (
                <ItemRow key={it.id} title={it.title} value={it.value} changePct={it.changePct} />
              ))}
              <View style={{ paddingVertical: 10, alignItems: "flex-end" }}>
                <Text style={{ color: theme.colors.subtext }}>Total: €{fmtMoney(g.total)}</Text>
              </View>
            </View>
          </View>
        ))}

        {/* Download bottom-center */}
        <View style={{ alignItems: "center", marginTop: 20, marginBottom: 40 }}>
          <Pressable onPress={() => {}} style={{ paddingHorizontal: 16, paddingVertical: 10, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
            <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>Download overview</Text>
          </Pressable>
        </View>
      </View>
    </ScrollView>
  );
}
