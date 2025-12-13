import React from "react";
import { Tabs } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@/theme";

export default function TabsLayout() {
  const insets = useSafeAreaInsets();

  return (
    <Tabs
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: theme.colors.navy,
        tabBarInactiveTintColor: theme.colors.subtext,
        tabBarStyle: {
          backgroundColor: "#ffffff",
          borderTopColor: theme.colors.border,
          borderTopWidth: 1,
          height: 56 + insets.bottom,
          paddingBottom: Math.max(6, insets.bottom / 2),
        },
        sceneStyle: { backgroundColor: theme.colors.bg },
        tabBarLabelStyle: { fontSize: 11 },
        tabBarIcon: ({ color, size }) => {
          let name: keyof typeof Ionicons.glyphMap = "ellipse-outline";

          switch (route.name) {
            case "portfolio":
              name = "pie-chart-outline";
              break;
            case "items":
              name = "albums-outline";
              break;
            case "add":
              name = "add-circle-outline";
              break;
            case "marketplace":
              name = "chatbubbles-outline";
              break;
          }

          return <Ionicons name={name} size={size} color={color} />;
        },
      })}
    >
      <Tabs.Screen name="portfolio" options={{ title: "Portfolio" }} />
      <Tabs.Screen name="items" options={{ title: "Items" }} />
      <Tabs.Screen name="add" options={{ title: "Add" }} />
      <Tabs.Screen name="marketplace" options={{ title: "Marketplace" }} />
    </Tabs>
  );
}
