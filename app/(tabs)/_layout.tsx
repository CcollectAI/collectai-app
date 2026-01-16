import React from "react";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

export default function TabsLayout() {
  const insets = useSafeAreaInsets();
return (
    <Tabs
      screenOptions={{
        headerShown: false,                 // remove title banner
        tabBarShowLabel: true,              // words under icons
        tabBarLabelPosition: "below-icon",
        tabBarLabelStyle: { fontSize: 11, fontWeight: "700" },
        tabBarIconStyle: { marginTop: 2 },
        tabBarStyle: {
          height: 58 + Math.max(insets.bottom, 10),
          paddingTop: 8,
          paddingBottom: Math.max(insets.bottom, 10),
          backgroundColor: "#FFFFFF",
          borderTopWidth: 1,
          borderTopColor: "rgba(11,31,58,0.10)",
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Portfolio",
          tabBarLabel: "Portfolio",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "pie-chart" : "pie-chart-outline"}
              size={Math.max(18, size - 4)}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="items"
        options={{
          title: "Items",
          tabBarLabel: "Items",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "albums" : "albums-outline"}
              size={Math.max(18, size - 4)}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="add"
        options={{
          title: "Add",
          tabBarLabel: "Add",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "add-circle" : "add-circle-outline"}
              size={Math.max(22, size)}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="events"
        options={{
          title: "Events",
          tabBarLabel: "Events",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "calendar" : "calendar-outline"}
              size={Math.max(18, size - 4)}
              color={color}
            />
          ),
        }}
      />

      {/* IMPORTANT: Search tab uses the real Search UI living in marketplace.tsx */}
      <Tabs.Screen
        name="marketplace"
        options={{
          title: "Search",
          tabBarLabel: "Search",
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "search" : "search-outline"}
              size={Math.max(18, size - 4)}
              color={color}
            />
          ),
        }}
      />

      {/* Hide hidden route so it doesn't appear as an extra tab */}
      <Tabs.Screen name="search" options={{ href: null }} />
    </Tabs>
  );
}
