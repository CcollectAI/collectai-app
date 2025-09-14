import React from "react";
import { View, Text, ScrollView } from "react-native";
import { theme } from "@/theme";

export default function AddScreen() {
  return (
    <ScrollView style={{ flex:1, backgroundColor: theme.colors.background }} contentContainerStyle={{ padding: 16 }}>
      <Text style={{ fontSize: 22, fontWeight: "800", color: theme.colors.text, marginBottom: 12 }}>Add Item</Text>
      <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, padding: 12 }}>
        <Text style={{ color: theme.colors.subtext }}>Camera & AI intake coming next.</Text>
      </View>
    </ScrollView>
  );
}
