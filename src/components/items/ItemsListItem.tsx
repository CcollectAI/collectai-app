/**
 * ItemsListItem — Single item row in the collection SectionList.
 */
import React from 'react';
import { View, Text, Image, Animated, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { AnimatedPressable } from '@/motion';
import { CategoryPill } from '@/components/CategoryPill';
import { formatPrice } from '@/lib/format';
import { fireHaptic, HapticIntent } from '@/haptics';
import { GRADING_ELIGIBLE_CATEGORIES } from '@/constants/categories';

interface Item {
  id: string;
  name: string;
  category: string;
  collectionName: string;
  value: number;
  condition?: string;
  notes?: string;
  imageUrl?: string;
}

interface ItemsListItemProps {
  item: Item;
  isMultiSelectMode: boolean;
  isSelected: boolean;
  staggerStyle?: object;
  onPress: (item: Item) => void;
  onLongPress: (itemId: string) => void;
}

export const ItemsListItem = React.memo(function ItemsListItem({
  item,
  isMultiSelectMode,
  isSelected: selected,
  staggerStyle,
  onPress,
  onLongPress,
}: ItemsListItemProps) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  return (
    <Animated.View style={staggerStyle}>
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
        accessibilityLabel={`${item.name}, ${formatPrice(item.value)}`}
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
            <CategoryPill id={item.category} label={item.category} /> – {item.collectionName}
          </Text>
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
          <Text style={[styles.itemValue, { color: colors.text }]}>
            {formatPrice(item.value)}
          </Text>
        </View>
      </AnimatedPressable>
    </Animated.View>
  );
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
