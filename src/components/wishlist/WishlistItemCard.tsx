/**
 * WishlistItemCard — Single watchlist item card with priority dot, actions.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';
import type { WatchlistItem } from '@/data/types';

interface WishlistItemCardProps {
  item: WatchlistItem;
  onRemove: (item: WatchlistItem) => void;
  onEditTarget: (item: WatchlistItem) => void;
  onShop: (item: WatchlistItem) => void;
  onGotIt: (item: WatchlistItem) => void;
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export const WishlistItemCard = React.memo(function WishlistItemCard({
  item,
  onRemove,
  onEditTarget,
  onShop,
  onGotIt,
}: WishlistItemCardProps) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const priorityColor =
    item.priority === 'high'
      ? '#ef4444'
      : item.priority === 'medium'
      ? '#f59e0b'
      : '#22c55e';

  return (
    <View style={[styles.itemCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.itemHeader}>
        <View style={styles.itemTitleRow}>
          <View style={[styles.priorityDot, { backgroundColor: priorityColor }]} />
          <Text style={[styles.itemTitle, { color: colors.text }]} numberOfLines={1}>
            {item.title}
          </Text>
        </View>
        <AnimatedPressable onPress={() => onRemove(item)} style={styles.removeBtn} accessibilityRole="button" accessibilityLabel={`Remove ${item.title} from watchlist`}>
          <Ionicons name="close-circle" size={22} color={colors.muted} />
        </AnimatedPressable>
      </View>

      <View style={styles.itemMeta}>
        {item.category && (
          <View style={[styles.categoryBadge, { backgroundColor: colors.accent + '20' }]}>
            <Text style={[styles.categoryText, { color: colors.accent }]}>{item.category}</Text>
          </View>
        )}
        <AnimatedPressable
          onPress={() => onEditTarget(item)}
          style={styles.targetPressable}
          accessibilityRole="button"
          accessibilityLabel={item.targetPrice !== null ? `Target: ${formatPrice(item.targetPrice, settings.currency)}. Tap to edit` : 'Set target price'}
        >
          {item.targetPrice !== null ? (
            <Text style={[styles.targetPrice, { color: colors.text }]}>
              Target: {formatPrice(item.targetPrice, settings.currency)}
            </Text>
          ) : (
            <Text style={[styles.setTargetText, { color: colors.accent }]}>
              Set target price
            </Text>
          )}
          <Ionicons name="pencil-outline" size={12} color={colors.muted} />
        </AnimatedPressable>
      </View>

      {item.notes && (
        <Text style={[styles.notes, { color: colors.muted }]} numberOfLines={2}>
          {item.notes}
        </Text>
      )}

      {item.createdAt && (
        <Text style={[styles.dateAdded, { color: colors.muted }]}>
          Added {formatDate(item.createdAt)}
        </Text>
      )}

      {/* Action buttons */}
      <View style={styles.cardActions}>
        <AnimatedPressable
          style={[styles.shopBtn, { borderColor: colors.accent }]}
          onPress={() => onShop(item)}
          accessibilityRole="button"
          accessibilityLabel={`Shop for ${item.title}`}
        >
          <Ionicons name="cart-outline" size={16} color={colors.accent} />
          <Text style={[styles.shopBtnText, { color: colors.accent }]}>Shop</Text>
        </AnimatedPressable>
        <AnimatedPressable
          style={[styles.gotItBtn, { backgroundColor: colors.accent }]}
          onPress={() => onGotIt(item)}
          accessibilityRole="button"
          accessibilityLabel={`Mark ${item.title} as acquired`}
        >
          <Ionicons name="checkmark-circle" size={18} color="#fff" />
          <Text style={styles.gotItBtnText}>I Got It!</Text>
        </AnimatedPressable>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  itemCard: {
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
  },
  itemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  itemTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginRight: 8,
  },
  priorityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  itemTitle: {
    fontSize: 15,
    fontWeight: '600',
    flex: 1,
  },
  removeBtn: {
    padding: 4,
  },
  itemMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 10,
  },
  categoryBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
  },
  categoryText: {
    fontSize: 12,
    fontWeight: '500',
  },
  targetPrice: {
    fontSize: 13,
    fontWeight: '600',
  },
  targetPressable: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  setTargetText: {
    fontSize: 12,
    fontWeight: '500',
  },
  notes: {
    fontSize: 13,
    marginTop: 8,
    lineHeight: 18,
  },
  dateAdded: {
    fontSize: 11,
    marginTop: 6,
  },
  cardActions: {
    flexDirection: 'row',
    marginTop: 12,
    gap: 8,
  },
  shopBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 20,
    borderWidth: 1,
    gap: 6,
  },
  shopBtnText: {
    fontSize: 14,
    fontWeight: '600',
  },
  gotItBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 20,
    gap: 6,
  },
  gotItBtnText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
});
