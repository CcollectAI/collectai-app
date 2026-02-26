/**
 * QuickNavBar — Persistent bottom navigation bar for screens outside the (tabs) group.
 * Mirrors the 5 main tabs so users can jump to any section without hitting "back" repeatedly.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter, usePathname } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
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

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: colors.card,
          borderTopColor: colors.border,
          paddingBottom: Math.max(insets.bottom, 10),
        },
      ]}
    >
      {TABS.map((tab) => {
        const isActive = tab.matchPrefix ? pathname.startsWith(tab.matchPrefix) : false;
        const color = isActive ? colors.accent : colors.muted;

        return (
          <AnimatedPressable
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
          </AnimatedPressable>
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
