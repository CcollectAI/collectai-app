// External tab bar — rendered at RootStack level, outside the <Tabs>
// navigator. Builds #14-32 had the bottom-tab bar dead on cold launch:
// taps reached the root view at y≈790 (visible tab bar region) but never
// reached CustomTabBar's onTouchStart inside Tabs. Conclusion: the bar
// inside Tabs isn't in the hit-test hierarchy where it visually appears.
// Same pattern QuickNavBar has always used on non-tab screens — known
// good. See memory/project_tab_bar_bug_saga.md.

import React from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter, useSegments, type Href } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { useAppTheme } from "@/hooks/useAppTheme";
import { BETA_MODE } from "@/config/featureFlags";
import { fireHaptic, HapticIntent } from "@/haptics";
import { pushDebugLog } from "@/lib/debugLog";

type TabDef = {
  key: string;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconFocused: keyof typeof Ionicons.glyphMap;
  href: Href;
};

export const EXTERNAL_TAB_BAR_HEIGHT = 58;

export function ExternalTabBar() {
  const insets = useSafeAreaInsets();
  const { colors } = useAppTheme();
  const router = useRouter();
  const segments = useSegments();
  const { t } = useTranslation();

  const inTabsGroup = segments[0] === "(tabs)";
  if (!inTabsGroup) return null;

  const activeSegment = (segments[1] ?? "index") as string;
  const bottomPadding = Math.max(insets.bottom, 10);

  const tabs: TabDef[] = [
    {
      key: "index",
      label: t("nav.home"),
      icon: "pie-chart-outline",
      iconFocused: "pie-chart",
      href: "/(tabs)",
    },
    {
      key: "items",
      label: t("nav.items"),
      icon: "albums-outline",
      iconFocused: "albums",
      href: "/(tabs)/items",
    },
    {
      key: "add",
      label: t("nav.add"),
      icon: "add-circle-outline",
      iconFocused: "add-circle",
      href: "/(tabs)/add",
    },
    ...(BETA_MODE
      ? []
      : [
          {
            key: "events",
            label: "Events",
            icon: "calendar-outline" as const,
            iconFocused: "calendar" as const,
            href: "/(tabs)/events" as Href,
          },
        ]),
    {
      key: "marketplace",
      label: t("nav.search"),
      icon: "search-outline",
      iconFocused: "search",
      href: "/(tabs)/marketplace",
    },
  ];

  return (
    <View
      style={[
        styles.bar,
        {
          height: EXTERNAL_TAB_BAR_HEIGHT + bottomPadding,
          paddingBottom: bottomPadding,
          backgroundColor: colors.card,
          borderTopColor: colors.border,
        },
      ]}
      accessibilityRole="tablist"
      accessibilityLabel="Main navigation"
    >
      {tabs.map((tab) => {
        const isFocused = tab.key === activeSegment;
        const color = isFocused ? colors.accent : colors.muted;
        return (
          <Pressable
            key={tab.key}
            onPress={() => {
              pushDebugLog(`[EXT] press ${tab.key} focused=${isFocused}`);
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              if (!isFocused) router.replace(tab.href);
            }}
            style={styles.tab}
            accessibilityRole="tab"
            accessibilityLabel={tab.label}
            accessibilityState={{ selected: isFocused }}
            hitSlop={6}
          >
            <Ionicons
              name={isFocused ? tab.iconFocused : tab.icon}
              size={tab.key === "add" ? 26 : 22}
              color={color}
            />
            <Text style={[styles.label, { color }]}>{tab.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    borderTopWidth: 1,
    paddingTop: 8,
    zIndex: 50,
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
