import React from "react";
import { Stack } from "expo-router";

export default function RootLayout() {
  console.log("[RootLayout] v2025-12-05-STACK");
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
    </Stack>
  );
}
