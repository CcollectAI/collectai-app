import React from "react";
import { View, Text, ScrollView, Pressable, Alert } from "react-native";
import { theme } from "@/theme";

export default function PortfolioScreen() {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.background }} contentContainerStyle={{ padding: 16 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <Text style={{ fontSize: 28, fontWeight: "800", color: theme.colors.text }}>CollectAI</Text>
        <Pressable onPress={() => Alert.alert("Settings")} style={{ padding: 8 }}>
          <Text style={{ fontSize: 18, color: theme.colors.text }}>⚙️</Text>
        </Pressable>
      </View>

      <Text style={{ color: theme.colors.subtext, marginBottom: 8 }}>Today</Text>
      <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, padding: 12 }}>
        <Text style={{ color: theme.colors.text }}>Line chart placeholder (1D/7D/30D)</Text>
      </View>

      <View style={{ height: 16 }} />

      <Text style={{ fontSize: 16, fontWeight: "700", color: theme.colors.text, marginBottom: 8 }}>Collection</Text>
      <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border }}>
        {[
          { title: "Charizard Holo 1999", value: 1240.0, changePct: +3.1 },
          { title: "LEGO Falcon 75192", value: 680.0, changePct: -1.4 }
        ].map((it, idx) => (
          <View key={idx} style={{ paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: idx === 1 ? 0 : 1, borderBottomColor: theme.colors.border }}>
            <Text style={{ fontWeight: "700", color: theme.colors.text }}>{it.title}</Text>
            <Text style={{ color: it.changePct >= 0 ? theme.colors.positive : theme.colors.negative }}>
              {it.changePct >= 0 ? "+" : ""}{it.changePct.toFixed(2)}%
            </Text>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}
