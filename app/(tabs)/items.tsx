import React from "react";
import { View, Text, ScrollView } from "react-native";
import { theme } from "@/theme";
import BadgeIcon from "@/components/BadgeIcon";

type Item = { id: string; title: string; category: string; value: number; changePct: number };
const ITEMS: Item[] = [
  { id: "1", title: "Charizard Holo 1999", category: "Pokémon", value: 1240, changePct: +3.1 },
  { id: "2", title: "LEGO Millennium Falcon 75192", category: "LEGO", value: 680, changePct: -1.4 },
  { id: "3", title: "Funko Pop Pikachu", category: "Funko", value: 22, changePct: 0.0 }
];

export default function ItemsScreen() {
  return (
    <ScrollView style={{ flex:1, backgroundColor: theme.colors.background }} contentContainerStyle={{ padding: 16 }}>
      <Text style={{ fontSize: 22, fontWeight: "800", color: theme.colors.text, marginBottom: 12 }}>Items</Text>
      <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border }}>
        {ITEMS.map((it, idx) => (
          <View key={it.id} style={{ paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: idx === ITEMS.length-1 ? 0 : 1, borderBottomColor: theme.colors.border, flexDirection:"row", alignItems:"center", gap: 10 }}>
            <View style={{ flex:1 }}>
              <Text style={{ fontWeight:"700", color: theme.colors.text }}>{it.title}</Text>
              <Text style={{ color: it.changePct >= 0 ? theme.colors.positive : theme.colors.negative }}>
                {it.changePct >= 0 ? "+" : ""}{it.changePct.toFixed(2)}%
              </Text>
            </View>
            <BadgeIcon tier="silver" />
          </View>
        ))}
      </View>
    </ScrollView>
  );
}
