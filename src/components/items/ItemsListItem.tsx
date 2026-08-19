/**
 * ItemsListItem — Single item row in the collection SectionList.
 *
 * Swipe-left reveals Archive + Delete actions when not in multi-select.
 * In multi-select mode the swipe is suppressed so it doesn't fight with
 * tap-to-toggle.
 */
import React from 'react';
import { View, Text, Image, Animated, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { AnimatedPressable } from '@/motion';
import { CategoryPill } from '@/components/CategoryPill';
import { formatPrice, UNPRICED_LABEL, isUnpriced } from '@/lib/format';
import { ValueSourceChip } from '@/components/ValueSourceChip';
import { fireHaptic, HapticIntent } from '@/haptics';
import { GRADING_ELIGIBLE_CATEGORIES, formatCategoryName } from '@/constants/categories';
import { SwipeableRow, SwipeActions, type SwipeAction } from '@/components/SwipeableRow';

interface Item {
  id: string;
  name: string;
  category: string;
  collectionName: string;
  value: number;
  condition?: string;
  notes?: string;
  imageUrl?: string;
  // Rich detail (2026-07-15 enrichment) — shown as a compact subtitle line.
  brand?: string;
  year?: number;
  series?: string;
  editionLabel?: string;
  // `purchasePriceEur` / `purchasedAt` were read here for the Paid + P/L
  // lines, removed 2026-08-19. They stay off this interface deliberately: a
  // prop nothing renders is how a dead path survives a cleanup. Both numbers
  // live on the item's own screen.
  /** `v_item_values_v1.value_source`. Undefined on callers that map their own
   *  item shape — the chip renders nothing rather than guessing. */
  valueSource?: string | null;
}

interface ItemsListItemProps {
  item: Item;
  isMultiSelectMode: boolean;
  isSelected: boolean;
  staggerStyle?: object;
  onPress: (item: Item) => void;
  onLongPress: (itemId: string) => void;
  /** Optional swipe-action callbacks. When omitted the row isn't swipeable. */
  onArchive?: (itemId: string) => void;
  onDelete?: (itemId: string) => void;
}

export const ItemsListItem = React.memo(function ItemsListItem({
  item,
  isMultiSelectMode,
  isSelected: selected,
  staggerStyle,
  onPress,
  onLongPress,
  onArchive,
  onDelete,
}: ItemsListItemProps) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  // Same rule as ItemDetailsCard: a missing-or-zero per-item value means "we
  // could not price this", not "this is worth nothing". The row rendered "€ 0"
  // for every unpriced item while the detail screen for that same item said
  // "Cannot estimate value" — one of the two was lying.
  const unpriced = isUnpriced(item.value);
  const valueLabel = unpriced ? UNPRICED_LABEL : formatPrice(item.value);

  const card = (
    <AnimatedPressable
        style={[
          styles.itemRow,
          { borderColor: colors.border },
          isMultiSelectMode && selected && {
            backgroundColor: colors.accent + '15',
            borderColor: colors.accent,
          },
        ]}
        onPress={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          onPress(item);
        }}
        onLongPress={() => onLongPress(item.id)}
        delayLongPress={400}
        accessibilityRole="button"
        accessibilityLabel={`${item.name}, ${valueLabel}`}
        accessibilityHint={isMultiSelectMode ? 'Tap to select or deselect' : 'Long press to select multiple items'}
      >
        {isMultiSelectMode && (
          <View style={styles.checkboxContainer}>
            <View
              style={[
                styles.checkbox,
                { borderColor: colors.border },
                selected && {
                  backgroundColor: colors.accent,
                  borderColor: colors.accent,
                },
              ]}
              accessibilityRole="checkbox"
              accessibilityState={{ checked: selected }}
              accessibilityLabel={`Select ${item.name}`}
            >
              {selected && (
                <Ionicons name="checkmark" size={14} color="#fff" />
              )}
            </View>
          </View>
        )}
        {item.imageUrl ? (
          <Image source={{ uri: item.imageUrl }} style={styles.itemThumb} accessibilityLabel={`Photo of ${item.name}`} />
        ) : (
          <View style={[styles.itemThumbPlaceholder, { backgroundColor: colors.accent + '10' }]} accessibilityLabel={`No photo for ${item.name}`}>
            <Ionicons name="image-outline" size={18} color={colors.accent + '40'} />
          </View>
        )}
        <View style={{ flex: 1 }}>
          <Text style={[styles.itemName, { color: colors.text }]}>
            {item.name}
          </Text>
          <Text style={[styles.itemMeta, { color: colors.muted }]}>
            <CategoryPill id={item.category} label={formatCategoryName(item.category)} />
            {item.collectionName ? ` – ${item.collectionName}` : ''}
          </Text>
          {/* Rich detail subtitle: brand · year · series · edition. Series is
              dropped when it duplicates the collection name shown above. */}
          {(() => {
            const parts = [
              item.brand,
              typeof item.year === 'number' ? String(item.year) : null,
              item.series && item.series !== item.collectionName ? item.series : null,
              item.editionLabel,
            ].filter(Boolean);
            return parts.length ? (
              <Text style={[styles.itemDetail, { color: colors.muted }]} numberOfLines={1}>
                {parts.join(' · ')}
              </Text>
            ) : null;
          })()}
          {item.condition ? (
            GRADING_ELIGIBLE_CATEGORIES.has(item.category) ? (
              <View style={[styles.gradeBadge, { backgroundColor: colors.accent + '15' }]}>
                <Ionicons name="shield-checkmark-outline" size={11} color={colors.accent} />
                <Text style={[styles.gradeBadgeText, { color: colors.accent }]}>
                  {item.condition}
                </Text>
              </View>
            ) : (
              <Text style={[styles.itemCondition, { color: colors.muted }]}>
                {item.condition}
              </Text>
            )
          ) : null}
        </View>
        <View style={styles.itemRight}>
          {/* The send-to-chat button was here (added 2026-08-13, removed
              2026-08-19). It was DEAD: `app/(tabs)/items.tsx` rendered
              <ShareToChatSheet> only inside the first-run loading branch, so
              the sheet did not exist on any screen where a row — and therefore
              the button — was visible. Tapping it set state and opened nothing.
              Removed on request rather than repaired; sharing a listing still
              lives on the marketplace tile (docs/ui-playbook.md). */}
          <Text
            style={[
              styles.itemValue,
              // Muted + smaller: it's an absence of data, not a headline figure.
              // Mirrors ItemDetailsCard's treatment of the same state.
              unpriced ? { color: colors.muted, fontSize: 11, fontWeight: '500' as const } : { color: colors.text },
            ]}
            numberOfLines={1}
          >
            {valueLabel}
          </Text>
          {/* Inline, not a pill: a list row is a reference row, and a bordered
              chip per row is a wall of colour (ui-playbook). Suppressed when
              the item is unpriced — "Not priced yet" beside the unpriced label
              would say the same thing twice. */}
          {!unpriced ? <ValueSourceChip source={item.valueSource} inline /> : null}
          {/* "Paid EUR X" and the profit/loss delta were here (removed
              2026-08-19, reported as clutter). A four-line right column —
              value, source chip, paid, P/L — on a ~56pt row is a wall of
              figures per item, and this is a REFERENCE ROW, not a position
              blotter (docs/ui-playbook.md, "a list card is a reference row").
              Both numbers are still on the item's own screen, where there is
              room to read them, and the portfolio-wide P/L still has its own
              surface in analytics. */}
        </View>
      </AnimatedPressable>
  );

  const swipeable = !isMultiSelectMode && (onArchive || onDelete);
  const wrapped = swipeable ? (
    <SwipeableRow
      rightActions={[
        ...(onArchive
          ? [
              {
                key: 'archive',
                label: 'Archive',
                icon: 'archive-outline' as const,
                color: '#f59e0b',
                onPress: () => onArchive(item.id),
              } satisfies SwipeAction,
            ]
          : []),
        ...(onDelete ? [SwipeActions.delete(() => onDelete(item.id))] : []),
      ]}
      enableHaptics={settings.hapticsEnabled}
    >
      {card}
    </SwipeableRow>
  ) : (
    card
  );

  return <Animated.View style={staggerStyle}>{wrapped}</Animated.View>;
});

const styles = StyleSheet.create({
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginTop: 6,
  },
  itemThumb: {
    width: 40,
    height: 40,
    borderRadius: 8,
    marginRight: 10,
  },
  itemThumbPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 8,
    marginRight: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemName: {
    fontSize: 14,
    fontWeight: '600',
  },
  itemMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  itemCondition: {
    fontSize: 11,
    marginTop: 2,
  },
  itemDetail: {
    fontSize: 11,
    marginTop: 2,
  },
  gradeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 3,
    marginTop: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  gradeBadgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
  itemRight: {
    marginLeft: 12,
    alignItems: 'flex-end',
  },
  // 16pt glyph in a 24pt box; `hitSlop` carries the rest of the touch target
  // up to the 44pt minimum without the box pushing the row taller.
  itemValue: {
    fontSize: 13,
    fontWeight: '700',
  },
  checkboxContainer: {
    marginRight: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
