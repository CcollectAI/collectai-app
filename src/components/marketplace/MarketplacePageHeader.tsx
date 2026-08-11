/**
 * Page header for the Marketplace screen showing title, subtitle, and action icons.
 *
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';

export const MarketplacePageHeader = React.memo(function MarketplacePageHeader() {
  const { colors } = useAppTheme();

  return (
    <View style={styles.headerRow}>
      <View style={styles.headerLeft}>
        {/* "Market", matching the tab that opens this screen (2026-08-11). The
            page called itself Search while the tab called itself Search and the
            app's actual unified search is a different route — so the one word
            named two things and neither of them was this page. */}
        <Text style={[styles.headerTitle, { color: colors.text }]}>
          Market
        </Text>
        <Text style={[styles.headerSubtitle, { color: colors.muted }]}>
          Buy, sell, and browse collectibles.
        </Text>
      </View>
      <View style={styles.headerIcons}>
        <InboxHeaderButton color={colors.text} size={22} />
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  headerLeft: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
  },
  headerSubtitle: {
    fontSize: 12,
    marginTop: 4,
  },
  headerIcons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
});
