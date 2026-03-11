import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { AnimatedPressable } from '@/motion';
import type { AppTheme } from '@/hooks/useAppTheme';

type RelatedCategory = {
  id: string;
  name: string;
  tagline: string;
};

type Props = {
  categories: RelatedCategory[];
  onCategoryPress: (categoryId: string) => void;
  colors: AppTheme['colors'];
};

const RelatedCategoriesSection: React.FC<Props> = ({ categories, onCategoryPress, colors }) => {
  if (categories.length === 0) return null;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>Related Categories</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.relatedRow}>
        {categories.map((rc) => (
          <AnimatedPressable
            key={rc.id}
            style={[styles.relatedCard, { backgroundColor: colors.card, borderColor: colors.border }]}
            onPress={() => onCategoryPress(rc.id)}
            accessibilityRole="button"
            accessibilityLabel={`Browse ${rc.name}`}
          >
            <Text style={[styles.relatedName, { color: colors.text }]} numberOfLines={2}>{rc.name}</Text>
            <Text style={[styles.relatedTagline, { color: colors.muted }]} numberOfLines={2}>{rc.tagline}</Text>
          </AnimatedPressable>
        ))}
      </ScrollView>
    </View>
  );
};

export default React.memo(RelatedCategoriesSection);

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  relatedRow: {
    gap: 10,
  },
  relatedCard: {
    width: 160,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  relatedName: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 4,
  },
  relatedTagline: {
    fontSize: 11,
    lineHeight: 15,
  },
});
