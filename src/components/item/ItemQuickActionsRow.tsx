/**
 * ItemQuickActionsRow — Edit / Sell buttons shown below the image.
 *
 * Share LEFT this row on 2026-08-21 and became a 30x30 icon overlaid on the
 * gallery, top-right, with the same metrics as the marketplace tile
 * (app/listings.tsx `shareBtn`) — the placement docs/ui-playbook.md already
 * specifies for share. Two reasons it could not go in the nav header instead:
 * that cluster is bell/bubble/gear and a FOURTH icon stops reading as a
 * cluster and starts reading as a toolbar, which is why the avatar was removed
 * from it in the first place.
 *
 * Sell took the freed slot. It is the REVENUE action and it was previously
 * only reachable from a collapsed section near the bottom of the screen, below
 * a request for price feedback — a data-collection ask outranking the thing
 * that makes money. `List for Sale` (external marketplaces, SELLING_ENABLED)
 * is a different destination and stays gated.
 */
import React, { useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { radius, text, fontWeight as fw, gap } from '@/theme/tokens';
import { SELLING_ENABLED } from '@/config/featureFlags';

interface ItemQuickActionsRowProps {
  isForSale: boolean;
  onEdit: () => void;
  /** Opens the full sell flow (app/sell/new) with this item prefilled. */
  onSell: () => void;
  onListForSale: () => void;
}


export const ItemQuickActionsRow = React.memo(function ItemQuickActionsRow(props: ItemQuickActionsRowProps) {
  const { colors: theme } = useAppTheme();
  const { isForSale, onEdit, onListForSale, onSell } = props;
  const [busy, setBusy] = useState(false);



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
      {/* THE primary action on this screen, and the only filled accent on it.
          Everything else here is outline or muted — 48 accent usages across
          this screen and its components meant nothing read as primary.

          HIDDEN ONCE THE ITEM IS LISTED (2026-08-27). An item already for sale
          renders a "Listed for sale" badge with an "Unlist" button directly
          above this row; offering "Sell" underneath asked the member to do a
          thing they have already done, next to the control for undoing it.
          The screen was telling them two different states of the same fact.

          When it is listed, Edit takes the full width rather than leaving a
          gap where the primary action was — a row that keeps its slot empty
          reads as a control that failed to load. */}
      {!isForSale ? (
        <AnimatedPressable
          onPress={onSell}
          disabled={busy}
          style={[styles.quickActionBtn, { backgroundColor: theme.accent, borderColor: theme.accent }, busy && { opacity: 0.5 }]}
          accessibilityRole="button"
          accessibilityLabel="Sell this on the Sparrow marketplace"
        >
          {/* accentText, never '#fff': in high-contrast dark the accent fill IS
              white and a hardcoded white label disappears. */}
          <Ionicons name="pricetag" size={18} color={theme.accentText} />
          <Text style={[styles.quickActionLabel, { color: theme.accentText }]}>Sell</Text>
        </AnimatedPressable>
      ) : null}
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
