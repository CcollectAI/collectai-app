/**
 * ItemsEmptyState — Empty state shown when no items match filters.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { useTranslation } from 'react-i18next';

export const ItemsEmptyState = React.memo(function ItemsEmptyState() {
  const { colors } = useAppTheme();
  const router = useRouter();
  const { t } = useTranslation();

  return (
    <View style={styles.emptyContainer}>
      <Text style={[styles.emptyText, { color: colors.muted }]}>
        No items match your filters yet.
      </Text>
      <AnimatedPressable
        onPress={() => router.push('/quickscan')}
        style={[styles.emptyCtaBtn, { backgroundColor: colors.accent }]}
        accessibilityRole="button"
        accessibilityLabel={t('items_empty.quickscan_ai_a11y')}
      >
        <Ionicons name="camera-outline" size={18} color="#fff" />
        <Text style={styles.emptyCtaBtnText}>{t('items_empty.quickscan_ai')}</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={() => router.push('/add-manual')}
        style={[styles.emptyCtaBtn, { borderColor: colors.border, borderWidth: 1, backgroundColor: colors.card }]}
        accessibilityRole="button"
        accessibilityLabel={t('items_empty.add_manually_a11y')}
      >
        <Ionicons name="add-circle-outline" size={18} color={colors.text} />
        <Text style={[styles.emptyCtaBtnTextSecondary, { color: colors.text }]}>{t('items_empty.add_manually')}</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={() => router.push('/barcode-scan')}
        style={[styles.emptyCtaBtn, { borderColor: colors.border, borderWidth: 1, backgroundColor: colors.card }]}
        accessibilityRole="button"
        accessibilityLabel={t('items_empty.scan_barcode_a11y')}
      >
        <Ionicons name="barcode-outline" size={18} color={colors.text} />
        <Text style={[styles.emptyCtaBtnTextSecondary, { color: colors.text }]}>{t('items_empty.scan_barcode')}</Text>
      </AnimatedPressable>
    </View>
  );
});

const styles = StyleSheet.create({
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  emptyText: {
    fontSize: 13,
    marginTop: 16,
  },
  emptyCtaBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 10,
    marginTop: 12,
  },
  emptyCtaBtnText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  emptyCtaBtnTextSecondary: {
    fontSize: 14,
    fontWeight: '600',
  },
});
