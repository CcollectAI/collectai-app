/**
 * ValueSavedBanner — Instacart-style slide-down notification.
 *
 * Shows a brief, compelling summary of what CollectAI saved the user.
 * Slides down from top, auto-dismisses after 8s, tap to dismiss.
 * Framed for loss aversion: "Without CollectAI, you would have..."
 *
 * NOT a share card — purely a retention nudge.
 */

import React, { useEffect, useRef } from 'react';
import { View, Text, Pressable, Animated, StyleSheet, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/theme/useAppTheme';
import { fonts, colors as tokenColors } from '@/theme/tokens';
import { formatPrice } from '@/lib/format';
import { track } from '@/analytics/track';
import { fireHaptic, HapticIntent } from '@/haptics';
import type { ValueSummaryData } from '@/api/collectorsApi';
import type { SavingsTrigger } from '@/hooks/useValueSummary';

const AUTO_DISMISS_MS = 8000;

type Props = {
  data: ValueSummaryData;
  visible: boolean;
  trigger?: SavingsTrigger | null;
  onDismiss: () => void;
};

type CurrencyCode = 'EUR' | 'USD' | 'GBP' | 'JPY' | 'KRW' | 'AUD' | 'CAD';

function getSavingsMessage(
  data: ValueSummaryData,
  trigger: SavingsTrigger,
  currency: CurrencyCode,
  hasMoney: boolean,
  hasTime: boolean,
): { headline: string; subline: string } {
  switch (trigger) {
    case 'first_scan':
      return {
        headline: 'First scan complete!',
        subline: `That just saved you ~15 min of manual research`,
      };
    case 'scan_milestone':
      return {
        headline: `${data.total_scans} scans — ${data.hours_saved}h saved`,
        subline: hasMoney
          ? `plus ${formatPrice(data.total_money_saved, currency)} in smart decisions`
          : `across ${data.total_items_tracked} tracked items`,
      };
    case 'deal_complete':
      return {
        headline: hasMoney ? `You've saved ${formatPrice(data.total_money_saved, currency)}` : 'Deal closed!',
        subline: `${data.deal_count} deal${data.deal_count !== 1 ? 's' : ''} negotiated below asking price`,
      };
    case 'item_milestone':
      return {
        headline: `${data.total_items_tracked} items tracked`,
        subline: hasTime
          ? `${data.hours_saved}h of inventory management — handled`
          : `Your collection is growing fast`,
      };
    case 'duplicate_prevented':
      return {
        headline: 'Duplicate caught!',
        subline: hasMoney
          ? `Sparrow Collect has saved you ${formatPrice(data.total_money_saved, currency)} overall`
          : `${data.total_items_tracked} items tracked, no doubles`,
      };
    default: {
      // Periodic / generic fallback
      if (hasMoney && hasTime) {
        return {
          headline: `You've saved ${formatPrice(data.total_money_saved, currency)}`,
          subline: `and ${data.hours_saved}+ hours of research`,
        };
      }
      if (hasMoney) {
        return {
          headline: `You've saved ${formatPrice(data.total_money_saved, currency)}`,
          subline: `on ${data.smart_buy_count + data.deal_count} smart decisions`,
        };
      }
      return {
        headline: `${data.hours_saved}+ hours saved`,
        subline: `across ${data.total_scans} scans and ${data.total_items_tracked} items tracked`,
      };
    }
  }
}

export function ValueSavedBanner({ data, visible, trigger, onDismiss }: Props) {
  const { colors } = useAppTheme();
  const slideAnim = useRef(new Animated.Value(-200)).current;
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (visible) {
      track({ name: 'value_summary_shown', properties: { money: data.total_money_saved, hours: data.hours_saved } });
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT);

      Animated.spring(slideAnim, {
        toValue: 0,
        useNativeDriver: true,
        tension: 60,
        friction: 12,
      }).start();

      timerRef.current = setTimeout(() => {
        handleDismiss();
      }, AUTO_DISMISS_MS);
    }

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [visible]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDismiss = () => {
    Animated.timing(slideAnim, {
      toValue: -200,
      duration: 250,
      useNativeDriver: true,
    }).start(() => onDismiss());
  };

  if (!visible) return null;

  const hasMoney = data.total_money_saved > 0;
  const hasTime = data.hours_saved >= 0.5;
  const currency = (data.currency || 'EUR') as 'EUR' | 'USD' | 'GBP' | 'JPY' | 'KRW' | 'AUD' | 'CAD';

  // Contextual messaging based on what triggered the notification
  const { headline, subline } = getSavingsMessage(data, trigger ?? 'periodic', currency, hasMoney, hasTime);

  // Best find callout
  const hasBestFind = data.best_find_name && data.best_find_saved > 0;

  return (
    <Animated.View
      style={[
        styles.container,
        {
          paddingTop: 56, // Safe area top offset
          transform: [{ translateY: slideAnim }],
        },
      ]}
      accessibilityRole="alert"
      accessibilityLabel={`${headline} ${subline}`}
    >
      <Pressable
        style={[styles.banner, { backgroundColor: colors.card, borderColor: colors.border }]}
        onPress={handleDismiss}
        accessibilityRole="button"
        accessibilityLabel="Dismiss savings notification"
      >
        {/* Tiffany accent bar */}
        <View style={styles.accentBar} />

        <View style={styles.content}>
          {/* Icon */}
          <View style={styles.iconCircle}>
            <Ionicons name="trending-up" size={20} color={colors.card} />
          </View>

          {/* Text */}
          <View style={styles.textSection}>
            <Text style={[styles.headline, { color: colors.text }]} numberOfLines={1}>
              {headline}
            </Text>
            <Text style={[styles.subline, { color: colors.muted }]} numberOfLines={1}>
              {subline}
            </Text>
            {hasBestFind && (
              <Text style={[styles.bestFind, { color: colors.muted }]} numberOfLines={1}>
                Best find: {data.best_find_name} — saved {formatPrice(data.best_find_saved, currency)}
              </Text>
            )}
          </View>

          {/* Dismiss X */}
          <Pressable
            onPress={handleDismiss}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel="Close"
          >
            <Ionicons name="close" size={18} color={colors.muted} />
          </Pressable>
        </View>

        {/* Progress bar (auto-dismiss timer) */}
        <AutoDismissBar durationMs={AUTO_DISMISS_MS} />
      </Pressable>
    </Animated.View>
  );
}

/**
 * Thin animated progress bar that fills over the auto-dismiss duration.
 */
function AutoDismissBar({ durationMs }: { durationMs: number }) {
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(progress, {
      toValue: 1,
      duration: durationMs,
      useNativeDriver: false,
    }).start();
  }, [durationMs, progress]);

  const width = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  return (
    <View style={styles.progressTrack}>
      <Animated.View style={[styles.progressFill, { width }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 9999,
    paddingHorizontal: 12,
    paddingBottom: 8,
  },
  banner: {
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  accentBar: {
    height: 3,
    backgroundColor: tokenColors.brand.base,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 14,
    gap: 12,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: tokenColors.brand.dark,
    alignItems: 'center',
    justifyContent: 'center',
  },
  textSection: {
    flex: 1,
  },
  headline: {
    fontSize: 16,
    fontWeight: '800',
    fontFamily: fonts.bold,
    letterSpacing: -0.3,
  },
  subline: {
    fontSize: 13,
    fontWeight: '500',
    fontFamily: fonts.medium,
    marginTop: 2,
  },
  bestFind: {
    fontSize: 11,
    fontWeight: '500',
    fontFamily: fonts.medium,
    marginTop: 4,
    fontStyle: 'italic',
  },
  progressTrack: {
    height: 2,
    backgroundColor: 'rgba(0,0,0,0.04)',
  },
  progressFill: {
    height: 2,
    backgroundColor: tokenColors.brand.base,
    borderRadius: 1,
  },
});
