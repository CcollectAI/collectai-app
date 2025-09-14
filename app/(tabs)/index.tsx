import React from "react";
import { View, Text } from "react-native";
import { theme } from "@/theme";

export default function PortfolioScreen() {
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg, padding: 16 }}>
      <Text style={{ ...theme.font.title }}>CollectAI</Text>
      <Text style={{ ...theme.font.body, marginTop: 8 }}>
        Portfolio screen placeholder (chart + ranked items will render here).
      </Text>
    </View>
  );
}
