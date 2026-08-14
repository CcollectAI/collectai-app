/**
 * Header row for the Items screen showing title, portfolio total, and action icons.
 *
 * Extracted from app/(tabs)/items.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { TabBackButton } from '@/components/TabBackButton';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import { formatPrice } from '@/lib/format';

interface ItemsGridHeaderProps {
  portfolioTotal: number;
}

export const ItemsGridHeader = React.memo(function ItemsGridHeader({
  portfolioTotal,
}: ItemsGridHeaderProps) {
  const { colors } = useAppTheme();
  const router = useRouter();

  return (
    <View style={styles.headerRow}>
      <TabBackButton />
      <View style={styles.headerLeft}>
        <Text style={[styles.title, { color: colors.text }]}>Items</Text>
        <Text style={[styles.subtitle, { color: colors.muted }]}>
          Portfolio total: {formatPrice(portfolioTotal)}
        </Text>
      </View>
      {/* Same top-right cluster as every other screen: chat + settings. The
          chat icon may hide itself when community is gated with no unread, but
          settings is always present so the header never looks empty. */}
      <View style={styles.headerIcons}>
        <InboxHeaderButton color={colors.text} size={22} />
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
            router.push('/settings');
          }}
          style={styles.iconBtn}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessibilityRole="button"
          accessibilityLabel="Open settings"
        >
          <Ionicons name="settings-outline" size={22} color={colors.text} />
        </AnimatedPressable>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  headerLeft: {
    flex: 1,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  headerIcons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  iconBtn: { padding: 4 },
});
