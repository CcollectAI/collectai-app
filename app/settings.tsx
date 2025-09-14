import React from "react";
import { SafeAreaView, View, Text } from "react-native";
import { theme } from "@/theme";

export default function SettingsScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <View style={{ padding: theme.spacing.lg }}>
        <Text style={{ fontSize: theme.font.h1, fontWeight: "700", color: theme.colors.text }}>
          Settings
        </Text>
        <Text style={{ marginTop: theme.spacing.sm, color: theme.colors.subtext }}>
          (Placeholder) – we’ll wire this up after the UI stabilization pass.
        </Text>
      </View>
    </SafeAreaView>
  );
}
