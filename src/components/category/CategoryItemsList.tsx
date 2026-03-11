import React from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';
import type { Item } from '@/data';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  items: Item[];
  categoryName: string;
  accentColor: string;
  onItemPress: (item: Item) => void;
  onItemLongPress: (item: Item) => void;
  onShopPress: (item: Item) => void;
  onSeeAll: () => void;
  colors: AppTheme['colors'];
};

const CategoryItemsList: React.FC<Props> = ({
  items,
  categoryName,
  accentColor,
  onItemPress,
  onItemLongPress,
  onShopPress,
  onSeeAll,
  colors,
}) => (
  <View style={styles.section}>
    <Text style={[styles.sectionTitle, { color: colors.text }]}>Items in {categoryName}</Text>
    {items.length === 0 ? (
      <Text style={[styles.emptyText, { color: colors.muted }]}>No items yet in this category.</Text>
    ) : (
      items.slice(0, 6).map((item) => (
        <AnimatedPressable
          key={item.id}
          style={[styles.itemCard, { backgroundColor: colors.card, borderColor: colors.border }]}
          onPress={() => onItemPress(item)}
          onLongPress={() => onItemLongPress(item)}
          accessibilityRole="button"
          accessibilityLabel={`Shop for ${item.name}, ${formatPrice(item.price)}. Long press for more marketplaces.`}
        >
          {item.imageUrl ? (
            <Image source={{ uri: item.imageUrl }} style={styles.itemThumb} />
          ) : (
            <View style={[styles.itemThumbPlaceholder, { backgroundColor: colors.accent + '10' }]}>
              <Ionicons name="cube-outline" size={18} color={colors.accent} />
            </View>
          )}
          <View style={styles.itemInfo}>
            <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>
              {item.name}
            </Text>
            <Text style={[styles.itemCategory, { color: colors.muted }]}>
              {formatPrice(item.price)}
            </Text>
          </View>
          <AnimatedPressable
            onPress={() => onShopPress(item)}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={`Shop for ${item.name} on marketplaces`}
          >
            <Ionicons name="open-outline" size={20} color={colors.accent} />
          </AnimatedPressable>
        </AnimatedPressable>
      ))
    )}
    {items.length > 6 && (
      <AnimatedPressable
        style={styles.seeAllButton}
        onPress={onSeeAll}
        accessibilityRole="link"
        accessibilityLabel={`See all ${items.length} items in catalog`}
      >
        <Text style={[styles.seeAllText, { color: accentColor }]}>
          See all {items.length} items
        </Text>
        <Ionicons name="arrow-forward" size={14} color={accentColor} />
      </AnimatedPressable>
    )}
  </View>
);

export default React.memo(CategoryItemsList);

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  emptyText: {
    fontSize: 13,
  },
  itemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    marginBottom: 8,
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
  itemInfo: {
    flex: 1,
    marginRight: 8,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '600',
  },
  itemCategory: {
    fontSize: 12,
    marginTop: 2,
  },
  seeAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    gap: 4,
  },
  seeAllText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
