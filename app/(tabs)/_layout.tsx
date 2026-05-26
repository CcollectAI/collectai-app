import React from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Tabs, useRouter, type Href } from "expo-router";
import type { BottomTabBarProps } from "@react-navigation/bottom-tabs";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { useAppTheme } from "@/hooks/useAppTheme";
import { BETA_MODE } from "@/config/featureFlags";
import { fireHaptic, HapticIntent } from "@/haptics";
import { pushDebugLog } from "@/lib/debugLog";

// Map react-navigation route name → expo-router href. Using expo-router's
// router.replace (same code path as QuickNavBar, which has always worked)
// instead of react-navigation's navigation.navigate.
const ROUTE_TO_HREF: Record<string, string> = {
  index: "/(tabs)",
  items: "/(tabs)/items",
  add: "/(tabs)/add",
  events: "/(tabs)/events",
  marketplace: "/(tabs)/marketplace",
};

// Routes registered in (tabs)/ that should NOT render in the bar.
// Wishlist and search are accessed from inside other screens, not as tabs.
const HIDDEN_ROUTES = new Set(["wishlist", "search"]);

function CustomTabBar({ state, descriptors }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const { colors } = useAppTheme();
  const router = useRouter();
  const bottomPadding = Math.max(insets.bottom, 10);

  React.useEffect(() => {
    const msg = `bar mounted routes=${state.routes.length} idx=${state.index} replace=${typeof router.replace}`;
    console.log("[TAB]", msg);
    pushDebugLog(`[TAB] ${msg}`);
  }, [state.routes, state.index, router.replace]);

  return (
    <View
      style={[
        styles.bar,
        {
          height: 58 + bottomPadding,
          paddingBottom: bottomPadding,
          backgroundColor: colors.card,
          borderTopColor: colors.border,
        },
      ]}
      accessibilityRole="tablist"
      accessibilityLabel="Main navigation"
      onTouchStart={(e) => {
        const t = e.nativeEvent.touches?.[0];
        const msg = `outer touchStart x=${t?.locationX?.toFixed(0)} y=${t?.locationY?.toFixed(0)}`;
        console.log("[TAB]", msg);
        pushDebugLog(`[TAB] ${msg}`);
      }}
    >
      {state.routes.map((route, index) => {
        if (HIDDEN_ROUTES.has(route.name)) return null;
        if (route.name === "events" && BETA_MODE) return null;

        const descriptor = descriptors[route.key];
        const { options } = descriptor;
        const isFocused = state.index === index;
        const color = isFocused ? colors.accent : colors.muted;

        const label =
          typeof options.tabBarLabel === "string"
            ? options.tabBarLabel
            : options.title ?? route.name;

        const icon = options.tabBarIcon
          ? options.tabBarIcon({ focused: isFocused, color, size: 22 })
          : null;

        const onPress = () => {
          const msg = `press fired ${route.name} focused=${isFocused}`;
          console.log("[TAB]", msg);
          pushDebugLog(`[TAB] ${msg}`);
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
          const href = ROUTE_TO_HREF[route.name];
          if (href && !isFocused) {
            router.replace(href as Href);
          }
        };

        return (
          <Pressable
            key={route.key}
            onPress={onPress}
            style={styles.tab}
            accessibilityRole="tab"
            accessibilityLabel={options.tabBarAccessibilityLabel ?? String(label)}
            accessibilityState={{ selected: isFocused }}
          >
            {icon}
            <Text style={[styles.label, { color }]}>{String(label)}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export default function TabsLayout() {
  const { t } = useTranslation();

  // 2026-05-25: native @react-navigation/bottom-tabs bar dropped touches from
  // build #14+ in production despite stripping all non-default config (commit
  // 7e11687) and disabling new architecture (build #27). Replaced with a plain
  // Pressable-based bar — same code path as QuickNavBar, which has always
  // worked on non-tab screens.
  // 2026-05-26: bar moved to <ExternalTabBar /> in app/_layout.tsx. The
  // bottom-tabs navigator's own bar is suppressed (tabBar returns null,
  // tabBarStyle display:none removes the reserved space). The Tabs.Screen
  // entries below still register the routes with expo-router; we just
  // render the bar elsewhere. CustomTabBar above is kept for one build
  // in case we need to revert. lazy:false kept as a safety net.
  return (
    <Tabs
      tabBar={() => null}
      screenOptions={{
        headerShown: false,
        lazy: false,
        tabBarStyle: { display: "none" },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: t("nav.home"),
          tabBarLabel: t("nav.home"),
          tabBarAccessibilityLabel: t("nav.home"),
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
          title: t("nav.items"),
          tabBarLabel: t("nav.items"),
          tabBarAccessibilityLabel: t("nav.items"),
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
          title: t("nav.add"),
          tabBarLabel: t("nav.add"),
          tabBarAccessibilityLabel: t("nav.add"),
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
          tabBarAccessibilityLabel: "Events tab — community events and drops",
          href: BETA_MODE ? null : undefined,
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "calendar" : "calendar-outline"}
              size={Math.max(18, size - 4)}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen name="wishlist" options={{ href: null }} />

      <Tabs.Screen
        name="marketplace"
        options={{
          title: t("nav.search"),
          tabBarLabel: t("nav.search"),
          tabBarAccessibilityLabel: t("nav.search"),
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "search" : "search-outline"}
              size={Math.max(18, size - 4)}
              color={color}
            />
          ),
        }}
      />

      <Tabs.Screen name="search" options={{ href: null }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    borderTopWidth: 1,
    paddingTop: 8,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
  },
  label: {
    fontSize: 11,
    fontWeight: "700",
  },
});
