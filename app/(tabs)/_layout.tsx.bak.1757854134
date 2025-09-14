import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { TouchableOpacity } from "react-native";
import { useRouter } from "expo-router";
import { theme } from "../../src/theme";

export default function TabsLayout() {
  const router = useRouter();

  return (
    <Tabs
      screenOptions={{
        headerTitleAlign: "left",
        headerStyle: { backgroundColor: theme.colors.bg },
        headerTitleStyle: { color: theme.colors.text, fontWeight: "800" },
        tabBarActiveTintColor: theme.colors.brand.base,
        tabBarInactiveTintColor: theme.colors.muted,
        tabBarStyle: {
          backgroundColor: "#fff",
          borderTopColor: theme.colors.border,
          height: 64,
          paddingTop: 6,
        },
        headerRight: () => (
          <TouchableOpacity
            onPress={() => router.push("/settings")}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            style={{
              marginRight: 14,
              width: 36,
              height: 36,
              borderRadius: 18,
              backgroundColor: "#fff",
              alignItems: "center",
              justifyContent: "center",
              borderWidth: 1,
              borderColor: theme.colors.border,
              ...theme.shadow.card,
            }}
          >
            <Ionicons name="settings-outline" size={20} color="#0F172A" />
          </TouchableOpacity>
        ),
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarIcon: ({ color, size }) => <Ionicons name="home-outline" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="categories/index"
        options={{
          title: "Categories",
          tabBarIcon: ({ color, size }) => <Ionicons name="grid-outline" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="collection/index"
        options={{
          title: "Collection",
          tabBarIcon: ({ color, size }) => <Ionicons name="albums-outline" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="listings/index"
        options={{
          title: "Listings",
          tabBarIcon: ({ color, size }) => <Ionicons name="pricetags-outline" color={color} size={size} />,
        }}
      />
    </Tabs>
  );
}
