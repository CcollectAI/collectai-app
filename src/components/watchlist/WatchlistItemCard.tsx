/**
 * WatchlistItemCard — Single watchlist item with priority badge, price info,
 * reorder controls, multi-select checkbox, and swipeable delete.
 */
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";
import { SwipeableRow, SwipeActions } from "@/components/SwipeableRow";
import { fireHaptic, HapticIntent } from "@/haptics";
import { formatPrice } from "@/lib/format";
import type { WatchlistItem, CurrencyCode } from "@/data/types";

type WatchlistPriority = 'high' | 'medium' | 'low';

const PRIORITY_CONFIG: Record<WatchlistPriority, { label: string; color: string; bg: string }> = {
  high: { label: "High", color: "#DC2626", bg: "#DC262615" },
  medium: { label: "Medium", color: "#D97706", bg: "#D9770615" },
  low: { label: "Low", color: "#059669", bg: "#05966915" },
};

const TREND_INDICATOR: Record<string, { symbol: string; color: string }> = {
  up: { symbol: '\u25B2', color: '#059669' },
  down: { symbol: '\u25BC', color: '#DC2626' },
  stable: { symbol: '\u2550', color: '#6B7280' },
};

function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Not checked yet';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

type ThemeColors = {
  text: string;
  muted: string;
  card: string;
  border: string;
  accent: string;
  brand?: { dark?: string };
};

type Props = {
  item: WatchlistItem;
  colors: ThemeColors;
  currency: CurrencyCode;
  isMultiSelectMode: boolean;
  isSelected: boolean;
  isReordering: boolean;
  isFirst: boolean;
  isLast: boolean;
  hapticsEnabled: boolean;
  onToggleSelect: (id: string) => void;
  onLongPress: (id: string) => void;
  onDelete: (item: WatchlistItem) => void;
  onMoveUp: (id: string) => void;
  onMoveDown: (id: string) => void;
  onCloseReorder: () => void;
  categoryDisplayName: (slug: string) => string;
};

export const WatchlistItemCard = React.memo(function WatchlistItemCard({
  item,
  colors,
  currency,
  isMultiSelectMode,
  isSelected: isItemSelected,
  isReordering,
  isFirst,
  isLast,
  hapticsEnabled,
  onToggleSelect,
  onLongPress,
  onDelete,
  onMoveUp,
  onMoveDown,
  onCloseReorder,
  categoryDisplayName,
}: Props) {
  const priorityConfig = PRIORITY_CONFIG[item.priority] ?? PRIORITY_CONFIG.medium;

  const cardContent = (
    <AnimatedPressable
      onPress={isMultiSelectMode ? () => onToggleSelect(item.id) : undefined}
      onLongPress={() => onLongPress(item.id)}
      delayLongPress={400}
      style={[
        styles.itemCard,
        { backgroundColor: colors.card, borderColor: colors.border },
        isItemSelected && { borderColor: colors.accent, backgroundColor: colors.accent + '08' },
        isReordering && { borderColor: colors.accent, borderWidth: 2 },
      ]}
      accessibilityRole="button"
      accessibilityLabel={`${item.title}${isItemSelected ? ', selected' : ''}`}
    >
      <View style={styles.itemCardMain}>
        {/* Checkbox in multi-select mode */}
        {isMultiSelectMode && (
          <View style={styles.checkboxWrap}>
            <View style={[
              styles.checkbox,
              { borderColor: isItemSelected ? colors.accent : colors.border },
              isItemSelected && { backgroundColor: colors.accent },
            ]}>
              {isItemSelected && (
                <Ionicons name="checkmark" size={14} color="#FFFFFF" />
              )}
            </View>
          </View>
        )}

        <View style={styles.itemCardLeft}>
          <View style={styles.itemTitleRow}>
            <Text style={[styles.itemTitle, { color: colors.text }]} numberOfLines={2}>
              {item.title}
            </Text>
            <View
              style={[
                styles.priorityBadge,
                { backgroundColor: priorityConfig.bg },
              ]}
            >
              <Text
                style={[styles.priorityBadgeText, { color: priorityConfig.color }]}
              >
                {priorityConfig.label}
              </Text>
            </View>
          </View>

          {/* Category label */}
          {item.category ? (
            <Text style={[styles.categoryLabel, { color: colors.muted }]} numberOfLines={1}>
              {categoryDisplayName(item.category)}
            </Text>
          ) : null}

          {item.targetPrice != null && (
            <View style={[styles.targetBadge, { backgroundColor: colors.accent + '12' }]}>
              <Ionicons name="flag" size={12} color={colors.brand?.dark ?? colors.accent} />
              <Text style={[styles.targetBadgeText, { color: colors.brand?.dark ?? colors.accent }]}>
                Target: {formatPrice(item.targetPrice, currency)}
              </Text>
            </View>
          )}

          {/* Market price + trend indicator */}
          {item.lastMarketPrice != null && (
            <View style={styles.marketRow}>
              <Text style={[styles.marketLabel, { color: colors.muted }]}>Market: </Text>
              <Text style={[styles.marketPrice, { color: colors.text }]}>
                {formatPrice(item.lastMarketPrice, currency)}
              </Text>
              {item.priceTrend && TREND_INDICATOR[item.priceTrend] && (
                <Text style={{ color: TREND_INDICATOR[item.priceTrend].color, fontSize: 12, marginLeft: 4 }}>
                  {TREND_INDICATOR[item.priceTrend].symbol}
                </Text>
              )}
              {item.marketHitCount != null && item.marketHitCount > 0 && (
                <Text style={[styles.hitCount, { color: colors.muted }]}>
                  {` \u00B7 ${item.marketHitCount} listing${item.marketHitCount === 1 ? '' : 's'}`}
                </Text>
              )}
            </View>
          )}

          {/* Last checked timestamp */}
          {item.lastCheckedAt && (
            <Text style={[styles.lastChecked, { color: colors.muted }]}>
              Checked {timeAgo(item.lastCheckedAt)}
            </Text>
          )}

          {item.notes && (
            <Text style={[styles.itemNotes, { color: colors.muted }]} numberOfLines={2}>
              {item.notes}
            </Text>
          )}
        </View>

        {/* Reorder controls (visible on long-press) */}
        {isReordering && !isMultiSelectMode && (
          <View style={styles.reorderControls}>
            <AnimatedPressable
              style={[
                styles.reorderBtn,
                { backgroundColor: isFirst ? colors.border + '40' : colors.accent + '15' },
              ]}
              onPress={() => onMoveUp(item.id)}
              disabled={isFirst}
              accessibilityRole="button"
              accessibilityLabel="Move up"
            >
              <Ionicons
                name="chevron-up"
                size={18}
                color={isFirst ? colors.muted : colors.accent}
              />
            </AnimatedPressable>
            <AnimatedPressable
              style={[
                styles.reorderBtn,
                { backgroundColor: isLast ? colors.border + '40' : colors.accent + '15' },
              ]}
              onPress={() => onMoveDown(item.id)}
              disabled={isLast}
              accessibilityRole="button"
              accessibilityLabel="Move down"
            >
              <Ionicons
                name="chevron-down"
                size={18}
                color={isLast ? colors.muted : colors.accent}
              />
            </AnimatedPressable>
            <AnimatedPressable
              style={[styles.reorderBtn, { backgroundColor: colors.border + '30' }]}
              onPress={onCloseReorder}
              accessibilityRole="button"
              accessibilityLabel="Close reorder controls"
            >
              <Ionicons name="close" size={16} color={colors.muted} />
            </AnimatedPressable>
          </View>
        )}

        {/* Default delete button (non-multi-select, non-reorder) */}
        {!isMultiSelectMode && !isReordering && (
          <AnimatedPressable
            style={styles.deleteBtn}
            onPress={() => { fireHaptic(HapticIntent.ALERT_TRIGGERED); onDelete(item); }}
            accessibilityRole="button"
            accessibilityLabel={`Remove ${item.title} from watchlist`}
          >
            <Ionicons name="trash-outline" size={18} color={colors.muted} />
          </AnimatedPressable>
        )}
      </View>
    </AnimatedPressable>
  );

  // Wrap in SwipeableRow only when not in multi-select mode
  if (isMultiSelectMode) {
    return cardContent;
  }

  return (
    <SwipeableRow
      rightActions={[
        SwipeActions.delete(() => onDelete(item)),
      ]}
      enableHaptics={hapticsEnabled}
    >
      {cardContent}
    </SwipeableRow>
  );
});

const styles = StyleSheet.create({
  itemCard: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
    marginBottom: 10,
  },
  itemCardMain: {
    flexDirection: "row",
  },
  itemCardLeft: {
    flex: 1,
  },
  itemTitleRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    marginBottom: 4,
  },
  itemTitle: {
    flex: 1,
    fontSize: 15,
    fontWeight: "600",
    lineHeight: 20,
  },
  priorityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  priorityBadgeText: {
    fontSize: 11,
    fontWeight: "700",
  },
  categoryLabel: {
    fontSize: 11,
    marginBottom: 4,
  },
  targetBadge: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    marginBottom: 4,
  },
  targetBadgeText: {
    fontSize: 12,
    fontWeight: "600",
  },
  marketRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 4,
  },
  marketLabel: {
    fontSize: 12,
  },
  marketPrice: {
    fontSize: 12,
    fontWeight: "700",
  },
  hitCount: {
    fontSize: 11,
  },
  lastChecked: {
    fontSize: 10,
    marginBottom: 2,
  },
  itemNotes: {
    fontSize: 12,
    marginTop: 4,
    lineHeight: 16,
  },
  deleteBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 8,
  },
  checkboxWrap: {
    justifyContent: "center",
    marginRight: 12,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
  },
  reorderControls: {
    justifyContent: "center",
    alignItems: "center",
    marginLeft: 8,
    gap: 4,
  },
  reorderBtn: {
    width: 32,
    height: 28,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
});
