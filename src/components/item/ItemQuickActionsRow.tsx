/**
 * ItemQuickActionsRow — Edit / Share / List for Sale buttons shown below image.
 */
import React from 'react';
import { View, Text, StyleSheet, Share } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { formatPrice } from '@/lib/format';
import { AnimatedPressable } from '@/motion';

interface ItemQuickActionsRowProps {
  editableName: string;
  editableValue: string;
  isForSale: boolean;
  onEdit: () => void;
  onListForSale: () => void;
}

const toNum = (value: string | number | undefined | null): number | undefined => {
  if (value === undefined || value === null || value === '') return undefined;
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return undefined;
  return num;
};

export const ItemQuickActionsRow = React.memo(function ItemQuickActionsRow(props: ItemQuickActionsRowProps) {
  const { colors: theme } = useAppTheme();
  const { editableName, editableValue, isForSale, onEdit, onListForSale } = props;

  return (
    <View style={styles.quickActionsRow}>
      <AnimatedPressable
        onPress={onEdit}
        style={[styles.quickActionBtn, { backgroundColor: theme.card, borderColor: theme.border }]}
        accessibilityRole="button"
        accessibilityLabel="Edit item details"
      >
        <Ionicons name="create-outline" size={18} color={theme.accent} />
        <Text style={[styles.quickActionLabel, { color: theme.text }]}>Edit</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={async () => {
          try {
            await Share.share({
              message: `Check out ${editableName}${toNum(editableValue) ? ` - valued at ${formatPrice(toNum(editableValue))}` : ''} on CollectAI`,
            });
          } catch {
            // User cancelled
          }
        }}
        style={[styles.quickActionBtn, { backgroundColor: theme.card, borderColor: theme.border }]}
        accessibilityRole="button"
        accessibilityLabel="Share this item"
      >
        <Ionicons name="share-outline" size={18} color={theme.accent} />
        <Text style={[styles.quickActionLabel, { color: theme.text }]}>Share</Text>
      </AnimatedPressable>
      {!isForSale ? (
        <AnimatedPressable
          onPress={onListForSale}
          style={[styles.quickActionBtn, { backgroundColor: theme.accent + '12', borderColor: theme.accent }]}
          accessibilityRole="button"
          accessibilityLabel="List this item for sale on marketplaces"
        >
          <Ionicons name="storefront-outline" size={18} color={theme.accent} />
          <Text style={[styles.quickActionLabel, { color: theme.accent }]}>List for Sale</Text>
        </AnimatedPressable>
      ) : (
        <View style={[styles.quickActionBtn, { backgroundColor: '#D1FAE5', borderColor: '#059669' }]}>
          <Ionicons name="pricetag" size={18} color="#065F46" />
          <Text style={[styles.quickActionLabel, { color: '#065F46' }]}>Listed</Text>
        </View>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
  quickActionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 4,
  },
  quickActionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    minWidth: 70,
    paddingVertical: 12,
    paddingHorizontal: 4,
    borderRadius: 12,
    borderWidth: 1,
  },
  quickActionLabel: {
    fontSize: 13,
    fontWeight: '600',
  },
});
