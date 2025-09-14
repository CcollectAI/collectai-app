import React from "react";
import { Tabs } from "expo-router";
import { View, Text } from "react-native";
import { theme } from "@/theme";

const TabIcon = ({ label, active }: { label: string; active?: boolean }) => (
  <View style={{ alignItems:"center", paddingTop: 6 }}>
    <Text style={{ fontSize: 10, color: active ? theme.colors.text : theme.colors.subtext }}>{label}</Text>
  </View>
);

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.background },
        headerTintColor: theme.colors.text,
        tabBarStyle: {
          backgroundColor: theme.colors.card,
          borderTopColor: theme.colors.border,
          borderTopWidth: 1,
          height: 60
        },
        tabBarActiveTintColor: theme.colors.text,
        tabBarInactiveTintColor: theme.colors.subtext,
        headerTitle: "CollectAI",
        headerTitleStyle: { color: theme.colors.text }
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Portfolio",
          tabBarLabel: "Portfolio",
          tabBarIcon: ({ focused }) => <TabIcon label="📊" active={focused} />
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: "Items",
          tabBarLabel: "Items",
          tabBarIcon: ({ focused }) => <TabIcon label="📦" active={focused} />
        }}
      />
      <Tabs.Screen
        name="add"
        options={{
          title: "Add",
          tabBarLabel: "Add",
          tabBarIcon: ({ focused }) => <TabIcon label="＋" active={focused} />
        }}
      />
      <Tabs.Screen
        name="marketplace"
        options={{
          title: "Marketplace",
          tabBarLabel: "Marketplace",
          tabBarIcon: ({ focused }) => <TabIcon label="🏪" active={focused} />
        }}
      />
    </Tabs>
  );
}
