import React from "react";
import { Tabs, Link } from "expo-router";
import { Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { theme } from "@/theme";

const NAVY = theme.colors.brand.base;

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.card },
        headerTitleStyle: { color: NAVY, fontWeight: "800" },
        headerTintColor: NAVY,
        tabBarStyle: {
          backgroundColor: theme.colors.card,
          borderTopColor: theme.colors.border,
          borderTopWidth: 1,
          height: 62
        },
        tabBarActiveTintColor: NAVY,
        tabBarInactiveTintColor: "#94A3B8"
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "CollectAI",
          headerRight: () => (
            <Link href="/settings" asChild>
              <Pressable style={{ paddingHorizontal: 12 }}>
                <Ionicons name="settings-outline" size={22} color={NAVY} />
              </Pressable>
            </Link>
          ),
          tabBarLabel: "Portfolio",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home-outline" size={size} color={color} />
          )
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: "Items",
          tabBarLabel: "Items",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="albums-outline" size={size} color={color} />
          )
        }}
      />
      <Tabs.Screen
        name="add"
        options={{
          title: "Add",
          tabBarLabel: "Add",
          tabBarIcon: ({ color }) => (
            <Ionicons name="add-circle" size={28} color={color} />
          )
        }}
      />
      <Tabs.Screen
        name="marketplace"
        options={{
          title: "Marketplace",
          tabBarLabel: "Marketplace",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="storefront-outline" size={size} color={color} />
          )
        }}
      />
    </Tabs>
  );
}
