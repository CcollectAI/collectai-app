import React from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import type { CategoryMissingItem } from '@/data';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  missingItems: CategoryMissingItem[];
  recentlyOwned: Set<string>;
  markingOwned: string | null;
  accentColor: string;
  onMarkOwned: (itemId: string) => void;
  onShopItem: (title: string) => void;
  onSeeMore: () => void;
  colors: AppTheme['colors'];
};

const MissingItemsChecklist: React.FC<Props> = ({
  missingItems,
  recentlyOwned,
  markingOwned,
  accentColor,
  onMarkOwned,
  onShopItem,
  onSeeMore,
  colors,
}) => {
  if (missingItems.length === 0) return null;

  return (
    <View style={[styles.missingCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.missingCardHeader}>
        <Text style={[styles.missingCardTitle, { color: colors.text }]}>
          Complete Your Collection
        </Text>
        <Text style={[styles.missingCardCount, { color: colors.muted }]}>
          {missingItems.length} left
        </Text>
      </View>
      {missingItems.slice(0, 3).map((item) => {
        const isOwned = recentlyOwned.has(item.id);
        const isMarking = markingOwned === item.id;

        return (
          <View
            key={item.id}
            style={[
              styles.missingChecklistRow,
              { borderBottomColor: colors.border },
            ]}
          >
            <View
              style={[
                styles.missingCheckbox,
                { borderColor: isOwned ? colors.accent : colors.border },
                isOwned && { backgroundColor: colors.accent },
              ]}
            >
              {isOwned && <Ionicons name="checkmark" size={12} color="#fff" />}
            </View>
            <View style={styles.missingInfo}>
              <Text
                style={[
                  styles.missingTitle,
                  { color: isOwned ? colors.muted : colors.text },
                  isOwned && styles.missingTitleOwned,
                ]}
                numberOfLines={1}
              >
                {item.title}
              </Text>
              {item.brand && (
                <Text style={[styles.missingBrand, { color: colors.muted }]} numberOfLines={1}>
                  {item.brand}
                </Text>
              )}
            </View>
            {!isOwned && (
              <AnimatedPressable
                style={[styles.missingFindBtn, { borderColor: accentColor }]}
                onPress={() => onShopItem(item.title)}
                accessibilityRole="button"
                accessibilityLabel={`Shop for ${item.title} on marketplaces`}
              >
                <Ionicons name="open-outline" size={16} color={accentColor} />
              </AnimatedPressable>
            )}
            <AnimatedPressable
              style={[
                styles.missingAddBtn,
                {
                  backgroundColor: isOwned ? 'transparent' : colors.accent,
                },
              ]}
              disabled={isMarking || isOwned}
              onPress={() => onMarkOwned(item.id)}
              accessibilityRole="button"
              accessibilityLabel={isOwned ? `${item.title} marked as owned` : `Add ${item.title}`}
            >
              {isMarking ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : isOwned ? (
                <Text style={[styles.missingAddBtnText, { color: colors.accent }]}>Added</Text>
              ) : (
                <Text style={styles.missingAddBtnText}>Add</Text>
              )}
            </AnimatedPressable>
          </View>
        );
      })}
      {missingItems.length > 3 && (
        <AnimatedPressable
          style={styles.missingFooter}
          onPress={onSeeMore}
          accessibilityRole="button"
          accessibilityLabel={`View ${missingItems.length - 3} more items to collect`}
        >
          <Text style={[styles.seeMore, { color: colors.accent }]}>
            +{missingItems.length - 3} more to collect
          </Text>
          <Ionicons name="arrow-forward" size={14} color={colors.accent} />
        </AnimatedPressable>
      )}
    </View>
  );
};

export default React.memo(MissingItemsChecklist);

const styles = StyleSheet.create({
  missingCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 20,
  },
  missingCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  missingCardTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  missingCardCount: {
    fontSize: 13,
    fontWeight: '500',
  },
  missingChecklistRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  missingCheckbox: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  missingInfo: {
    flex: 1,
  },
  missingTitle: {
    fontSize: 14,
    fontWeight: '500',
  },
  missingTitleOwned: {
    textDecorationLine: 'line-through',
  },
  missingBrand: {
    fontSize: 12,
    marginTop: 2,
  },
  missingFindBtn: {
    width: 32,
    height: 32,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 8,
  },
  missingAddBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 8,
    marginLeft: 8,
  },
  missingAddBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
  },
  missingFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingTop: 10,
  },
  seeMore: {
    fontSize: 13,
    fontWeight: '500',
    textAlign: 'center',
  },
});
