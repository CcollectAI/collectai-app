import React from "react";
import { View, Text, ScrollView } from "react-native";
import { theme } from "@/theme";

export default function ItemsScreen() {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <View style={{ padding: 16 }}>
        <Text style={{ ...theme.font.title }}>Items</Text>
        <Text style={{ ...theme.font.body, marginTop: 8 }}>
          Grouped-by-category list will render here (badge right, % under item).
        </Text>
      </View>
    </ScrollView>
  );
}
