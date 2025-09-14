import React from "react";
import { Stack } from "expo-router";
import { theme } from "@/theme";

export default function RootLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.card },
        headerTitleStyle: { color: theme.colors.brand.base, fontWeight: "800" },
        headerTintColor: theme.colors.brand.base,
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="settings" options={{ title: "Settings" }} />
    </Stack>
  );
}
