import React from "react";
import { Stack } from "expo-router";
import { theme } from "@/theme";
import useSession from "@/auth/session";
import { View, Text } from "react-native";

export default function RootLayout() {
  const { ready } = useSession();
  if (!ready) {
    return <View style={{flex:1,justifyContent:"center",alignItems:"center"}}><Text>Loading…</Text></View>;
  }
  return (
    <Stack screenOptions={{
      headerStyle: { backgroundColor: theme.colors.background },
      headerTintColor: theme.colors.text,
      contentStyle: { backgroundColor: theme.colors.background }
    }} />
  );
}
