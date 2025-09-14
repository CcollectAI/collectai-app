import React from "react";
import { View, Text } from "react-native";
import { theme } from "@/theme";

export default function MarketplaceScreen() {
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg, padding: 16 }}>
      <Text style={{ ...theme.font.title }}>Marketplace</Text>
      <Text style={{ ...theme.font.body, marginTop: 8 }}>
        Chat | Search | Sell segmented UI will be restored here.
      </Text>
    </View>
  );
}
