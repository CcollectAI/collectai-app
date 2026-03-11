/**
 * ItemsEmptyState — Empty state shown when no items match filters.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

export const ItemsEmptyState = React.memo(function ItemsEmptyState() {
  const { colors } = useAppTheme();
  const router = useRouter();

  return (
    <View style={styles.emptyContainer}>
      <Text style={[styles.emptyText, { color: colors.muted }]}>
        No items match your filters yet.
      </Text>
      <AnimatedPressable
        onPress={() => router.push('/quickscan')}
        style={[styles.emptyCtaBtn, { backgroundColor: colors.accent }]}
        accessibilityRole="button"
        accessibilityLabel="QuickScan AI"
      >
        <Ionicons name="camera-outline" size={18} color="#fff" />
        <Text style={styles.emptyCtaBtnText}>QuickScan AI</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={() => router.push('/add-manual')}
        style={[styles.emptyCtaBtn, { borderColor: colors.border, borderWidth: 1, backgroundColor: colors.card }]}
        accessibilityRole="button"
        accessibilityLabel="Add item manually"
      >
        <Ionicons name="add-circle-outline" size={18} color={colors.text} />
        <Text style={[styles.emptyCtaBtnTextSecondary, { color: colors.text }]}>Add Item Manually</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={() => router.push('/barcode-scan')}
        style={[styles.emptyCtaBtn, { borderColor: colors.border, borderWidth: 1, backgroundColor: colors.card }]}
        accessibilityRole="button"
        accessibilityLabel="Scan a barcode"
      >
        <Ionicons name="barcode-outline" size={18} color={colors.text} />
        <Text style={[styles.emptyCtaBtnTextSecondary, { color: colors.text }]}>Scan Barcode</Text>
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
