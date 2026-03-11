/**
 * ItemForSaleBar — Shows listed status badge with Offers / Unlist actions.
 */
import React from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import { AnimatedPressable } from '@/motion';

interface ItemForSaleBarProps {
  askingPriceValue: string;
  forSaleLoading: boolean;
  onUnlist: () => void;
}

export const ItemForSaleBar = React.memo(function ItemForSaleBar({ askingPriceValue, forSaleLoading, onUnlist }: ItemForSaleBarProps) {
  const { colors: theme } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();

  return (
    <View style={styles.forSaleBar}>
      <View style={[styles.forSaleBadge, { backgroundColor: '#D1FAE5' }]}>
        <Ionicons name="pricetag" size={14} color="#065F46" />
        <Text style={[styles.forSaleBadgeText, { color: '#065F46' }]}>
          Listed{askingPriceValue ? ` ${formatPrice(parseFloat(askingPriceValue), settings.currency)}` : ''}
        </Text>
      </View>
      <AnimatedPressable
        onPress={() => router.push('/sell/offers')}
        style={[styles.editBarBtn, { backgroundColor: theme.accent + '12', borderColor: theme.accent }]}
        accessibilityRole="button"
        accessibilityLabel="View offers"
      >
        <Ionicons name="pricetags-outline" size={14} color={theme.accent} />
        <Text style={[styles.editBarBtnText, { color: theme.accent }]}>Offers</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={onUnlist}
        disabled={forSaleLoading}
        style={[styles.editBarBtn, { backgroundColor: theme.card, borderColor: theme.border }]}
        accessibilityRole="button"
        accessibilityLabel="Unlist from sale"
      >
        {forSaleLoading ? (
          <ActivityIndicator size="small" color={theme.muted} />
        ) : (
          <Text style={[styles.editBarBtnText, { color: theme.muted }]}>Unlist</Text>
        )}
      </AnimatedPressable>
    </View>
  );
});

const styles = StyleSheet.create({
  forSaleBar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  forSaleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    flex: 1,
  },
  forSaleBadgeText: {
    fontSize: 13,
    fontWeight: '600',
  },
  editBarBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    borderWidth: 1,
  },
  editBarBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
