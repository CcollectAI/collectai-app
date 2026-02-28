/**
 * QuickNavBar — Persistent bottom navigation bar for screens outside the (tabs) group.
 * Mirrors the 5 main tabs so users can jump to any section without hitting "back" repeatedly.
 *
 * Uses plain Pressable (not AnimatedPressable) because AnimatedPressable applies
 * the style prop to an inner Animated.View, which breaks flex: 1 in a row layout.
 */
import React from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter, usePathname } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';

type TabDef = {
  route: string;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconFocused: keyof typeof Ionicons.glyphMap;
  matchPrefix?: string;
};

const TABS: TabDef[] = [
  { route: '/(tabs)', label: 'Portfolio', icon: 'pie-chart-outline', iconFocused: 'pie-chart', matchPrefix: '/(tabs)' },
  { route: '/(tabs)/items', label: 'Items', icon: 'albums-outline', iconFocused: 'albums', matchPrefix: '/items' },
  { route: '/(tabs)/add', label: 'Add', icon: 'add-circle-outline', iconFocused: 'add-circle', matchPrefix: '/add' },
  { route: '/(tabs)/events', label: 'Events', icon: 'calendar-outline', iconFocused: 'calendar', matchPrefix: '/events' },
  { route: '/(tabs)/marketplace', label: 'Search', icon: 'search-outline', iconFocused: 'search', matchPrefix: '/marketplace' },
];

export function QuickNavBar() {
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
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              router.replace(tab.route as any);
            }}
            accessibilityRole="tab"
            accessibilityLabel={tab.label}
            accessibilityState={{ selected: isActive }}
          >
            <Ionicons
              name={isActive ? tab.iconFocused : tab.icon}
              size={22}
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
