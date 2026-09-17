/**
 * QuickNavBar — Persistent bottom navigation bar for screens outside the (tabs) group.
 * Mirrors the 5 main tabs so users can jump to any section without hitting "back" repeatedly.
 *
 * Uses plain Pressable (not AnimatedPressable) because AnimatedPressable applies
 * the style prop to an inner Animated.View, which breaks flex: 1 in a row layout.
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter, usePathname, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';

type TabDef = {
  route: string;
  /** i18n key, resolved at render — the SAME keys app/(tabs)/_layout.tsx uses. */
  labelKey: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconFocused: keyof typeof Ionicons.glyphMap;
  matchPrefix?: string;
};

const TABS: TabDef[] = [
  // Order and membership must match the Tabs.Screen order in
  // app/(tabs)/_layout.tsx and the tabs array in ExternalTabBar — three
  // components render this one bar, and a screen shows whichever it mounts.
  //
  // Items came off the bar 2026-08-11: the collection is reached from the
  // Portfolio category breakdown (a card per category) and its "All items"
  // action. Search took the fifth slot, restored to the unified search it was
  // built for.
  //
  // TRANSLATED since 2026-09-17, with the same keys as the real tab bar, so the
  // two bars cannot disagree. The comment here used to say these were "left
  // as-is rather than half-translating" — that reason was not true: every one of
  // the five keys was already translated into all seven locales. Measured cost
  // of believing it: the Dutch screen sweep counted 184 English label renders
  // across 65 screens (Events 53, Add 45, Market 43, Explore 43), each sitting
  // beside a tab bar that DID say "Evenementen" and "Ontdek".
  { route: '/(tabs)', labelKey: 'nav.portfolio', icon: 'pie-chart-outline', iconFocused: 'pie-chart', matchPrefix: '/(tabs)' },
  { route: '/(tabs)/marketplace', labelKey: 'nav.market', icon: 'storefront-outline', iconFocused: 'storefront', matchPrefix: '/marketplace' },
  { route: '/(tabs)/add', labelKey: 'nav.add', icon: 'add-circle-outline', iconFocused: 'add-circle', matchPrefix: '/add' },
  { route: '/(tabs)/events', labelKey: 'nav.events', icon: 'calendar-outline', iconFocused: 'calendar', matchPrefix: '/events' },
  // Labelled "Explore" since 2026-08-18; the route stays `search`.
  { route: '/(tabs)/search', labelKey: 'nav.explore', icon: 'search-outline', iconFocused: 'search', matchPrefix: '/search' },
];

export function QuickNavBar() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const { colors } = useAppTheme();
  const router = useRouter();
  const pathname = usePathname();

  const bottomPadding = Math.max(insets.bottom, 10);

  return (
    <View
      style={[
        styles.container,
        {
          height: 58 + bottomPadding,
          paddingBottom: bottomPadding,
          backgroundColor: colors.card,
          borderTopColor: colors.border,
        },
      ]}
      // "tabbar" is an iOS-ONLY accessibilityRole. On Android react-native
      // throws `IllegalArgumentException: Invalid accessibility role value`
      // straight out of ReactAccessibilityDelegate and HARD-CRASHES the app
      // (verified 2026-08-01: FATAL EXCEPTION on navigating with this mounted).
      // "tablist" is the container role Android actually supports, and it is
      // valid on both platforms. Guarded by scripts/preflight_android.mjs.
      accessibilityRole="tablist"
      accessibilityLabel={t('common.main_navigation_a11y', { defaultValue: 'Main navigation' })}
    >
      {TABS.map((tab) => {
        const isActive = tab.matchPrefix ? pathname.startsWith(tab.matchPrefix) : false;
        const color = isActive ? colors.accent : colors.muted;

        return (
          <Pressable
            key={tab.route}
            style={styles.tab}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              router.replace(tab.route as Href);
            }}
            accessibilityRole="tab"
            accessibilityLabel={t(tab.labelKey)}
            accessibilityState={{ selected: isActive }}
          >
            <Ionicons
              name={isActive ? tab.iconFocused : tab.icon}
              size={22}
              color={color}
            />
            <Text style={[styles.label, { color }]}>{t(tab.labelKey)}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    borderTopWidth: 1,
    paddingTop: 8,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 2,
  },
  label: {
    fontSize: 11,
    fontWeight: '700',
  },
});
