import React from "react";
import { View, Text } from "react-native";
import { theme } from "@/theme";

export default function Settings() {
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg, padding: 16 }}>
      <Text style={{ ...theme.font.title }}>Settings</Text>
    </View>
  );
}
