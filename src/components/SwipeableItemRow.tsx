/**
 * SwipeableItemRow Component
 * An item row with swipe-to-reveal actions (watchlist, share, delete).
 * Includes long-press context menu for accessibility.
 */

import React, { useState, useCallback, memo } from 'react';
import { View, Text, StyleSheet, Share, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SwipeableRow, SwipeActions, SwipeAction } from './SwipeableRow';
import { ContextMenu } from './ContextMenu';
import { AnimatedPressable } from '@/motion';
import { CategoryPill } from '@/components/CategoryPill';
import { featureFlags } from '@/config/featureFlags';
import { logger } from '@/lib/logger';
import { formatPrice } from '@/lib/format';

type Item = {
  id: string;
  name: string;
  category: string;
  collectionName?: string;
  value: number;
  condition?: string;
};

type SwipeableItemRowProps = {
  item: Item;
  onPress: () => void;
  onLongPress?: () => void;
  isSelected?: boolean;
  isMultiSelectMode?: boolean;
  onToggleSelect?: () => void;
  onAddToWatchlist?: (itemId: string) => void;
  onDelete?: (itemId: string) => void;
  colors: {
    text: string;
    muted: string;
    border: string;
    card: string;
    accent: string;
  };
};

export function SwipeableItemRow({
  item,
  onPress,
  onLongPress,
  isSelected = false,
  isMultiSelectMode = false,
  onToggleSelect,
  onAddToWatchlist,
  onDelete,
  colors,
}: SwipeableItemRowProps) {
  const [contextMenuVisible, setContextMenuVisible] = useState(false);

  const handleShare = useCallback(async () => {
    try {
      await Share.share({
        title: item.name,
        message: `Check out ${item.name} on CcollectAI`,
      });
    } catch (error) {
      logger.error('[SwipeableItemRow] Share failed:', error);
    }
  }, [item.name]);

  const handleWatchlist = useCallback(() => {
    onAddToWatchlist?.(item.id);
  }, [item.id, onAddToWatchlist]);

  const handleDelete = useCallback(() => {
    Alert.alert(
      'Delete Item',
      `Are you sure you want to delete "${item.name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => onDelete?.(item.id),
        },
      ]
    );
  }, [item, onDelete]);

  // Build swipe actions
  const leftActions: SwipeAction[] = onAddToWatchlist
    ? [SwipeActions.watchlist(handleWatchlist)]
    : [];

  const rightActions: SwipeAction[] = [
    SwipeActions.share(handleShare),
    ...(onDelete ? [SwipeActions.delete(handleDelete)] : []),
  ];

  const allActions = [...leftActions, ...rightActions];

  const handleLongPressInternal = useCallback(() => {
    if (isMultiSelectMode && onLongPress) {
      onLongPress();
    } else if (featureFlags.FEATURE_GESTURE_THUMB_NAVIGATION && allActions.length > 0) {
      setContextMenuVisible(true);
    } else if (onLongPress) {
      onLongPress();
    }
  }, [isMultiSelectMode, onLongPress, allActions.length]);

  const handlePress = useCallback(() => {
    if (isMultiSelectMode && onToggleSelect) {
      onToggleSelect();
    } else {
      onPress();
    }
  }, [isMultiSelectMode, onToggleSelect, onPress]);

  const rowContent = (
    <AnimatedPressable
      style={[
        styles.itemRow,
        { borderColor: colors.border, backgroundColor: colors.card },
        isMultiSelectMode && isSelected && {
          backgroundColor: colors.accent + '15',
          borderColor: colors.accent,
        },
      ]}
      onPress={handlePress}
      onLongPress={handleLongPressInternal}
      delayLongPress={400}
      accessibilityRole="button"
      accessibilityLabel={`${item.name}, ${formatPrice(item.value)}${isMultiSelectMode && isSelected ? ', selected' : ''}`}
    >
      {/* Checkbox in multi-select mode */}
      {isMultiSelectMode && (
        <View style={styles.checkboxContainer}>
          <View
            style={[
              styles.checkbox,
              { borderColor: colors.border },
              isSelected && {
                backgroundColor: colors.accent,
                borderColor: colors.accent,
              },
            ]}
          >
            {isSelected && (
              <Ionicons name="checkmark" size={14} color="#fff" />
            )}
          </View>
        </View>
      )}

      <View style={{ flex: 1 }}>
        <Text style={[styles.itemName, { color: colors.text }]}>
          {item.name}
        </Text>
        <Text style={[styles.itemMeta, { color: colors.muted }]}>
          <CategoryPill id={item.category} label={item.category} />
          {item.collectionName ? ` – ${item.collectionName}` : ''}
        </Text>
        {item.condition && (
          <Text style={[styles.itemCondition, { color: colors.muted }]}>
            {item.condition}
          </Text>
        )}
      </View>

      <View style={styles.itemRight}>
        <Text style={[styles.itemValue, { color: colors.text }]}>
          {formatPrice(item.value)}
        </Text>
      </View>
    </AnimatedPressable>
  );

  // Wrap with SwipeableRow when gesture feature is enabled
  if (featureFlags.FEATURE_GESTURE_THUMB_NAVIGATION && !isMultiSelectMode) {
    return (
      <>
        <SwipeableRow
          leftActions={leftActions}
          rightActions={rightActions}
          onLongPress={handleLongPressInternal}
          disabled={isMultiSelectMode}
        >
          {rowContent}
        </SwipeableRow>

        <ContextMenu
          visible={contextMenuVisible}
          onClose={() => setContextMenuVisible(false)}
          actions={allActions}
          title={item.name}
          subtitle={item.category}
        />
      </>
    );
  }

  return rowContent;
}

const styles = StyleSheet.create({
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginTop: 6,
  },
  checkboxContainer: {
    marginRight: 12,
    justifyContent: "center",
    alignItems: "center",
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    justifyContent: "center",
    alignItems: "center",
  },
  itemName: {
    fontSize: 14,
    fontWeight: "600",
  },
  itemMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  itemCondition: {
    fontSize: 11,
    marginTop: 2,
  },
  itemRight: {
    marginLeft: 12,
    alignItems: "flex-end",
  },
  itemValue: {
    fontSize: 13,
    fontWeight: "700",
  },
});

export default memo(SwipeableItemRow);
