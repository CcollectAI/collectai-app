import React from "react";
import { View, Text } from "react-native";

export default function MarketplaceScreen() {
  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#fef3c7",
      }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 8 }}>
        Marketplace
      </Text>
      <Text>Minimal marketplace screen.</Text>
    </View>
  );
}
