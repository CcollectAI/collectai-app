import React from "react";
import { View, Text } from "react-native";
import { theme } from "@/theme";

export default function AddScreen() {
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg, padding: 16 }}>
      <Text style={{ ...theme.font.title }}>Add Item</Text>
      <Text style={{ ...theme.font.body, marginTop: 8 }}>
        Camera + AI recognition + form will be implemented here.
      </Text>
    </View>
  );
}
