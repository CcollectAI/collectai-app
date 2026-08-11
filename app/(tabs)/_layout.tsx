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
    console.log(
      "[TAB] bar mounted routes=",
      state.routes.length,
      "idx=",
      state.index,
    );
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
        console.log("[TAB] outer touchStart x=", t?.locationX, "y=", t?.locationY);
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
          console.log("[TAB] press fired", route.name, "focused=", isFocused);
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
          /* "Portfolio", not "Home" (2026-08-11). The screen's own title is
             "Portfolio" and QuickNavBar already labelled it that; only the tab
             bar said Home, so the same destination had two names depending on
             which bar you read. `nav.home` is left in place — other locales'
             copy may still reference it. */
          title: t("nav.portfolio"),
          tabBarLabel: t("nav.portfolio"),
          tabBarAccessibilityLabel: t("nav.portfolio"),
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
          /*
           * Labelled "Market", not "Search" (2026-08-11).
           *
           * The slot has always opened `(tabs)/marketplace` while calling
           * itself Search, so the label described the search BAR at the top of
           * that screen rather than the screen itself — and the app's actual
           * unified search (`app/search.tsx`) is a different route entirely.
           * One name, one destination.
           *
           * `nav.market` is a new key, present in all 7 locales. It is NOT
           * `nav.marketplace` ("Marketplace" / "Marktplaats" / "마켓플레이스"),
           * which is an orphan key no screen reads: at 11pt in a five-up tab bar
           * those wrap. Changing the string here means changing it in
           * ExternalTabBar and QuickNavBar too — three components render this
           * same slot.
           */
          title: t("nav.market"),
          tabBarLabel: t("nav.market"),
          tabBarAccessibilityLabel: t("nav.market"),
          tabBarIcon: ({ color, size, focused }) => (
            <Ionicons
              name={focused ? "storefront" : "storefront-outline"}
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
