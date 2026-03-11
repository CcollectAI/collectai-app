/**
 * EventRelatedCategory — Card linking to the event's related collectible category.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

interface CategoryInfo {
  id: string;
  name: string;
  tagline?: string;
}

interface EventRelatedCategoryProps {
  category: CategoryInfo;
  onPress: () => void;
}

export const EventRelatedCategory = React.memo(function EventRelatedCategory({
  category,
  onPress,
}: EventRelatedCategoryProps) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>
        Related category
      </Text>
      <AnimatedPressable
        onPress={onPress}
        style={[styles.categoryCard, { backgroundColor: colors.card, borderColor: colors.border }]}
        accessibilityRole="link"
        accessibilityLabel={`View ${category.name} category`}
      >
        <Text style={[styles.categoryName, { color: colors.text }]}>
          {category.name}
        </Text>
        {category.tagline && (
          <Text style={[styles.categoryTagline, { color: colors.muted }]} numberOfLines={2}>
            {category.tagline}
          </Text>
        )}
      </AnimatedPressable>
    </View>
  );
});

const styles = StyleSheet.create({
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 8,
  },
  categoryCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
  },
  categoryName: {
    fontSize: 15,
    fontWeight: '600',
  },
  categoryTagline: {
    fontSize: 13,
    marginTop: 4,
  },
});
