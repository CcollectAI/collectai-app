/**
 * MultiItemOverlay — bounding box overlay for multi-item detection.
 * Shows detected items over the captured photo with tap-to-select.
 */

import React from 'react';
import { View, Text, StyleSheet, Image, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import type { DetectedMultiItem } from '@/data/types';

const TIFFANY = '#81D8D0';
const { width: SCREEN_WIDTH } = Dimensions.get('window');
const OVERLAY_HEIGHT = SCREEN_WIDTH * 0.85;

const BOX_COLORS = [
  '#81D8D0', '#F59E0B', '#8B5CF6', '#EF4444', '#22C55E',
  '#3B82F6', '#EC4899', '#14B8A6', '#F97316', '#6366F1',
];

type Props = {
  imageUri: string;
  detectedItems: DetectedMultiItem[];
  selectedIndex: number | null;
  onSelectItem: (index: number) => void;
  onProcessAll: () => void;
  onProcessSelected: (index: number) => void;
};

export function MultiItemOverlay({
  imageUri,
  detectedItems,
  selectedIndex,
  onSelectItem,
  onProcessAll,
}: Props) {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {/* Image with bounding boxes */}
      <View style={styles.imageContainer}>
        <Image source={{ uri: imageUri }} style={styles.image} resizeMode="cover" />

        {detectedItems.map((item, idx) => {
          const isSelected = selectedIndex === idx;
          const boxColor = BOX_COLORS[idx % BOX_COLORS.length];
          return (
            <AnimatedPressable
              key={idx}
              style={[
                styles.boundingBox,
                {
                  left: `${item.boundingBox.x * 100}%`,
                  top: `${item.boundingBox.y * 100}%`,
                  width: `${item.boundingBox.w * 100}%`,
                  height: `${item.boundingBox.h * 100}%`,
                  borderColor: isSelected ? '#FFFFFF' : boxColor,
                  borderWidth: isSelected ? 3 : 2,
                },
              ]}
              onPress={() => onSelectItem(idx)}
              accessibilityRole="button"
              accessibilityLabel={`Select item ${idx + 1}: ${item.suggestedName ?? 'Unknown'}`}
            >
              <View style={[styles.boxLabel, { backgroundColor: boxColor }]}>
                <Text style={styles.boxLabelText}>{idx + 1}</Text>
              </View>
            </AnimatedPressable>
          );
        })}
      </View>

      {/* Item cards */}
      <View style={styles.itemList}>
        {detectedItems.map((item, idx) => {
          const isSelected = selectedIndex === idx;
          const boxColor = BOX_COLORS[idx % BOX_COLORS.length];
          return (
            <AnimatedPressable
              key={idx}
              style={[
                styles.itemCard,
                {
                  backgroundColor: colors.card,
                  borderColor: isSelected ? boxColor : colors.border,
                  borderWidth: isSelected ? 2 : 1,
                },
              ]}
              onPress={() => onSelectItem(idx)}
              accessibilityRole="button"
            >
              <View style={[styles.itemDot, { backgroundColor: boxColor }]}>
                <Text style={styles.itemDotText}>{idx + 1}</Text>
              </View>
              <View style={styles.itemInfo}>
                <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>
                  {item.suggestedName ?? 'Unknown Item'}
                </Text>
                {item.categoryHint && (
                  <Text style={[styles.itemCategory, { color: colors.muted }]}>
                    {item.categoryHint.replace(/_/g, ' ')}
                  </Text>
                )}
              </View>
              <Text style={[styles.itemConf, { color: colors.muted }]}>
                {Math.round(item.confidence * 100)}%
              </Text>
            </AnimatedPressable>
          );
        })}
      </View>

      {/* Action buttons */}
      <View style={[styles.actions, { borderTopColor: colors.border }]}>
        <AnimatedPressable
          style={[styles.processAllBtn, { backgroundColor: TIFFANY }]}
          onPress={onProcessAll}
          accessibilityRole="button"
          accessibilityLabel="Process all detected items"
        >
          <Ionicons name="layers" size={18} color="#FFFFFF" />
          <Text style={styles.processAllText}>Process All ({detectedItems.length})</Text>
        </AnimatedPressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  imageContainer: {
    width: SCREEN_WIDTH,
    height: OVERLAY_HEIGHT,
    position: 'relative',
  },
  image: {
    width: '100%',
    height: '100%',
  },
  boundingBox: {
    position: 'absolute',
    borderStyle: 'solid',
    borderRadius: 4,
  },
  boxLabel: {
    position: 'absolute',
    top: -12,
    left: -1,
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxLabelText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '800',
  },
  itemList: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 12,
    gap: 8,
  },
  itemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 12,
    gap: 10,
  },
  itemDot: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemDotText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '800',
  },
  itemInfo: {
    flex: 1,
    gap: 2,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '600',
  },
  itemCategory: {
    fontSize: 12,
    fontWeight: '400',
  },
  itemConf: {
    fontSize: 13,
    fontWeight: '600',
  },
  actions: {
    paddingHorizontal: 20,
    paddingBottom: 40,
    paddingTop: 14,
    borderTopWidth: 1,
  },
  processAllBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    borderRadius: 16,
  },
  processAllText: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
  },
});

export default MultiItemOverlay;
