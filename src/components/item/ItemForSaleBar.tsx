/**
 * ItemForSaleBar — Shows listed status badge with Offers / Unlist actions.
 */
import React, { useEffect, useRef } from 'react';
import { View, Text, ActivityIndicator, StyleSheet, Animated as RNAnimated } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { formatPrice, parseMoney } from '@/lib/format';
import { AnimatedPressable } from '@/motion';
import { radius, text, fontWeight, gap } from '@/theme/tokens';
import { BETA_MODE, SELLING_ENABLED } from '@/config/featureFlags';

interface ItemForSaleBarProps {
  askingPriceValue: string;
  forSaleLoading: boolean;
  onUnlist: () => void;
}

export const ItemForSaleBar = React.memo(function ItemForSaleBar({ askingPriceValue, forSaleLoading, onUnlist }: ItemForSaleBarProps) {
  const { colors: theme } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();

  // Pulsing animation for the active listing dot
  const pulseAnim = useRef(new RNAnimated.Value(1)).current;
  useEffect(() => {
    const animation = RNAnimated.loop(
      RNAnimated.sequence([
        RNAnimated.timing(pulseAnim, { toValue: 0.3, duration: 1000, useNativeDriver: true }),
        RNAnimated.timing(pulseAnim, { toValue: 1, duration: 1000, useNativeDriver: true }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [pulseAnim]);

  return (
    <View style={styles.forSaleBar}>
      <View
        style={[styles.forSaleBadge, { backgroundColor: theme.successBg }]}
        accessibilityRole="text"
        accessibilityLabel={`Item listed for sale${askingPriceValue ? ` at ${formatPrice(parseMoney(askingPriceValue) ?? 0, settings.currency)}` : ''}`}
      >
        <RNAnimated.View style={[styles.activeDot, { backgroundColor: theme.success, opacity: pulseAnim }]} />
        <Ionicons name="pricetag" size={14} color={theme.success} />
        <Text style={[styles.forSaleBadgeText, { color: theme.success }]}>
          Listed{askingPriceValue ? ` ${formatPrice(parseMoney(askingPriceValue) ?? 0, settings.currency)}` : ''}
        </Text>
      </View>
      {/* Routes into the selling flow, so it follows SELLING_ENABLED too —
          BETA_MODE alone left it live while the rest of selling was gated. */}
      {!BETA_MODE && SELLING_ENABLED && (
        <AnimatedPressable
          onPress={() => router.push('/sell/offers')}
          style={[styles.editBarBtn, { backgroundColor: theme.accent + '12', borderColor: theme.accent }]}
          accessibilityRole="button"
          accessibilityLabel="View offers"
        >
          <Ionicons name="pricetags-outline" size={14} color={theme.accent} />
          <Text style={[styles.editBarBtnText, { color: theme.accent }]}>Offers</Text>
        </AnimatedPressable>
      )}
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
    gap: gap.md,
    marginBottom: 12,
  },
  forSaleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: gap.sm,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.xs,
    flex: 1,
  },
  forSaleBadgeText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  activeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  editBarBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: gap.sm,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: radius.xs,
    borderWidth: 1,
  },
  editBarBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
});
