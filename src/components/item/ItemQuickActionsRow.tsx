/**
 * ItemQuickActionsRow — Edit / Share / List for Sale buttons shown below image.
 */
import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, Share } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { formatPrice } from '@/lib/format';
import { AnimatedPressable } from '@/motion';
import { radius, text, fontWeight as fw, gap } from '@/theme/tokens';
import { logger } from '@/lib/logger';
import { SELLING_ENABLED } from '@/config/featureFlags';

interface ItemQuickActionsRowProps {
  editableName: string;
  editableValue: string;
  editableCondition?: string;
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
  const { editableName, editableValue, editableCondition, isForSale, onEdit, onListForSale } = props;
  const [busy, setBusy] = useState(false);

  const handleShare = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      // Optimized for messaging (WhatsApp / iMessage), where users actually
      // share: the details a recipient needs (name, condition, value) on their
      // own lines + a tappable link. A per-item sparrowcollect.com/item link
      // opens the app but 404s for recipients without it, so link the site.
      const val = toNum(editableValue);
      const message =
        `Check out my ${editableName} on Sparrow Collect` +
        (editableCondition ? `\nCondition: ${editableCondition}` : '') +
        (val ? `\nEstimated value: ${formatPrice(val)}` : '') +
        `\n\nhttps://sparrowcollect.com`;
      await Share.share({ message });
    } catch (e) {
      logger.error('[silent-catch] ItemQuickActionsRow.tsx:48:', e);
      // User cancelled
    } finally {
      setBusy(false);
    }
  }, [busy, editableName, editableValue, editableCondition]);

  return (
    <View style={styles.quickActionsRow}>
      <AnimatedPressable
        onPress={onEdit}
        disabled={busy}
        style={[styles.quickActionBtn, { backgroundColor: theme.card, borderColor: theme.border }, busy && { opacity: 0.5 }]}
        accessibilityRole="button"
        accessibilityLabel="Edit item details"
      >
        <Ionicons name="create-outline" size={18} color={theme.accent} />
        <Text style={[styles.quickActionLabel, { color: theme.text }]}>Edit</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={handleShare}
        disabled={busy}
        style={[styles.quickActionBtn, { backgroundColor: theme.card, borderColor: theme.border }, busy && { opacity: 0.5 }]}
        accessibilityRole="button"
        accessibilityLabel="Share this item"
      >
        <Ionicons name="share-outline" size={18} color={theme.accent} />
        <Text style={[styles.quickActionLabel, { color: theme.text }]}>Share</Text>
      </AnimatedPressable>
      {/* Second selling entry point — gated with the Seller Dashboard, or a user
          could still create a listing that goes nowhere (no marketplace account
          can be connected). Gating only the dashboard would have missed this. */}
      {!SELLING_ENABLED ? null : !isForSale ? (
        <AnimatedPressable
          onPress={onListForSale}
          disabled={busy}
          style={[styles.quickActionBtn, { backgroundColor: theme.accent + '12', borderColor: theme.accent }, busy && { opacity: 0.5 }]}
          accessibilityRole="button"
          accessibilityLabel="List this item for sale on marketplaces"
        >
          <Ionicons name="storefront-outline" size={18} color={theme.accent} />
          <Text style={[styles.quickActionLabel, { color: theme.accent }]}>List for Sale</Text>
        </AnimatedPressable>
      ) : (
        <View
          style={[styles.quickActionBtn, { backgroundColor: theme.successBg, borderColor: theme.success }]}
          accessibilityRole="text"
          accessibilityLabel="Item is currently listed for sale"
        >
          <Ionicons name="pricetag" size={18} color={theme.success} />
          <Text style={[styles.quickActionLabel, { color: theme.success }]}>Listed</Text>
        </View>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
  quickActionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: gap.md,
    marginBottom: 4,
  },
  quickActionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: gap.sm,
    minWidth: 70,
    paddingVertical: 12,
    paddingHorizontal: 4,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  quickActionLabel: {
    fontSize: text.md,
    fontWeight: fw.semibold,
  },
});
