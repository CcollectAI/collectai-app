import React from "react";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { useAppTheme } from "@/hooks/useAppTheme";
import { fireHaptic, HapticIntent } from "@/haptics";
import { BETA_MODE } from "@/config/featureFlags";

export default function TabsLayout() {
  const insets = useSafeAreaInsets();
  const { colors } = useAppTheme();
  const { t } = useTranslation();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: true,
        tabBarLabelPosition: "below-icon",
        tabBarLabelStyle: { fontSize: 11, fontWeight: "700" },
        tabBarIconStyle: { marginTop: 2 },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: {
          height: 58 + Math.max(insets.bottom, 10),
          paddingTop: 8,
          paddingBottom: Math.max(insets.bottom, 10),
          backgroundColor: colors.card,
          borderTopWidth: 1,
          borderTopColor: colors.border,
        },
      }}
      screenListeners={{
        tabPress: () => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: t('nav.home'),
          tabBarLabel: t('nav.home'),
          tabBarAccessibilityLabel: t('nav.home'),
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "pie-chart" : "pie-chart-outline"}
              size={Math.max(18, size - 4)}
              color={color}
              accessibilityElementsHidden
            />
          ),
        }}
      />

      <Tabs.Screen
        name="items"
        options={{
          title: t('nav.items'),
          tabBarLabel: t('nav.items'),
          tabBarAccessibilityLabel: t('nav.items'),
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "albums" : "albums-outline"}
              size={Math.max(18, size - 4)}
              color={color}
              accessibilityElementsHidden
            />
          ),
        }}
      />

      <Tabs.Screen
        name="add"
        options={{
          title: t('nav.add'),
          tabBarLabel: t('nav.add'),
          tabBarAccessibilityLabel: t('nav.add'),
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "add-circle" : "add-circle-outline"}
              size={Math.max(22, size)}
              color={color}
              accessibilityElementsHidden
            />
          ),
        }}
      />

      <Tabs.Screen
        name="events"
        options={{
          title: "Events",
          tabBarLabel: "Events",
          tabBarAccessibilityLabel: "Events tab — community events and drops",
          href: BETA_MODE ? null : undefined,
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "calendar" : "calendar-outline"}
              size={Math.max(18, size - 4)}
              color={color}
              accessibilityElementsHidden
            />
          ),
        }}
      />

      {/* Hide wishlist from tabs - accessible via Items screen only */}
      <Tabs.Screen name="wishlist" options={{ href: null }} />

      {/* IMPORTANT: Search tab uses the real Search UI living in marketplace.tsx */}
      <Tabs.Screen
        name="marketplace"
        options={{
          title: t('nav.search'),
          tabBarLabel: t('nav.search'),
          tabBarAccessibilityLabel: t('nav.search'),
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "search" : "search-outline"}
              size={Math.max(18, size - 4)}
              color={color}
              accessibilityElementsHidden
            />
          ),
        }}
      />

      {/* Hide stub route so it doesn't appear as an extra tab */}
      <Tabs.Screen name="search" options={{ href: null }} />
    </Tabs>
  );
}
