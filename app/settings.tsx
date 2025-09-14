import React from "react";
import { View, Text } from "react-native";
import { theme } from "@/theme";

export default function Settings() {
  return (
    <View style={{ flex:1, backgroundColor: theme.colors.bg, padding:16 }}>
      <View style={{ backgroundColor: theme.colors.card, borderWidth:1, borderColor: theme.colors.border, padding:16 }}>
        <Text style={{ fontWeight:"800", color: theme.colors.navy, fontSize:18 }}>Settings</Text>
        <Text style={{ marginTop:8, color: theme.colors.subtext }}>Coming soon…</Text>
      </View>
    </View>
  );
}
