/**
 * ItemsEmptyState — Hero empty state shown when the user has no items yet.
 *
 * Primary CTA jumps straight to the Add tab (the central add hub).
 * QuickScan and Scan Barcode are kept as secondary shortcuts.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { useTranslation } from 'react-i18next';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { text, fontWeight, radius } from '@/theme/tokens';

export const ItemsEmptyState = React.memo(function ItemsEmptyState() {
  const { colors } = useAppTheme();
  const router = useRouter();
  const { t } = useTranslation();
  const { settings } = useSettings();

  const haptic = (intent: HapticIntent) =>
    fireHaptic(intent, { enabled: settings.hapticsEnabled });

  return (
    <View style={styles.container}>
      <View style={[styles.iconCircle, { backgroundColor: colors.accent + '18' }]}>
        <Ionicons name="cube-outline" size={48} color={colors.accent} />
      </View>

      <Text style={[styles.title, { color: colors.text }]}>
        {t('items_empty.hero_title')}
      </Text>
      <Text style={[styles.subtitle, { color: colors.muted }]}>
        {t('items_empty.hero_subtitle')}
      </Text>

      <AnimatedPressable
        onPress={() => {
          haptic(HapticIntent.JUDGMENT_LOCKED);
          router.push('/(tabs)/add');
        }}
        style={[styles.primaryCta, { backgroundColor: colors.accent }]}
        accessibilityRole="button"
        accessibilityLabel={t('items_empty.add_first_a11y')}
      >
        <Ionicons name="add-circle" size={20} color={colors.accentText} />
        <Text style={[styles.primaryCtaText, { color: colors.accentText }]}>
          {t('items_empty.add_first')}
        </Text>
      </AnimatedPressable>

      <View style={styles.secondaryRow}>
        <AnimatedPressable
          onPress={() => {
            haptic(HapticIntent.CONFIRMATION_LIGHT);
            router.push('/quickscan');
          }}
          style={[styles.secondaryCta, { borderColor: colors.border, backgroundColor: colors.card }]}
          accessibilityRole="button"
          accessibilityLabel={t('items_empty.quickscan_ai_a11y')}
        >
          <Ionicons name="camera-outline" size={18} color={colors.text} />
          <Text style={[styles.secondaryCtaText, { color: colors.text }]}>
            {t('items_empty.quickscan_ai')}
          </Text>
        </AnimatedPressable>

        <AnimatedPressable
          onPress={() => {
            haptic(HapticIntent.CONFIRMATION_LIGHT);
            router.push('/barcode-scan');
          }}
          style={[styles.secondaryCta, { borderColor: colors.border, backgroundColor: colors.card }]}
          accessibilityRole="button"
          accessibilityLabel={t('items_empty.scan_barcode_a11y')}
        >
          <Ionicons name="barcode-outline" size={18} color={colors.text} />
          <Text style={[styles.secondaryCtaText, { color: colors.text }]}>
            {t('items_empty.scan_barcode')}
          </Text>
        </AnimatedPressable>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingVertical: 48,
  },
  iconCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: text.xl,
    fontWeight: fontWeight.extrabold,
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: text.md,
    textAlign: 'center',
    marginBottom: 28,
    lineHeight: 20,
  },
  primaryCta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: radius.md,
    minWidth: 240,
  },
  primaryCtaText: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
  secondaryRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 16,
  },
  secondaryCta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: radius.sm,
    borderWidth: 1,
  },
  secondaryCtaText: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
});
