/**
 * Filter chips / tabs for project status on the Build & Paint Projects screen.
 *
 * Allows toggling between All / Active / Completed views with haptic feedback.
 * Extracted from app/build-paint-projects.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';

export type ProjectFilterStatus = 'all' | 'in_progress' | 'finished' | 'wishlist';

interface ProjectFiltersProps {
  selected: ProjectFilterStatus;
  onSelect: (status: ProjectFilterStatus) => void;
  counts: { all: number; in_progress: number; finished: number; wishlist: number };
  hapticsEnabled?: boolean;
}

const FILTERS: { key: ProjectFilterStatus; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'finished', label: 'Finished' },
  { key: 'wishlist', label: 'Wishlist' },
];

export const ProjectFilters = React.memo(function ProjectFilters({
  selected,
  onSelect,
  counts,
  hapticsEnabled = true,
}: ProjectFiltersProps) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.container}>
      {FILTERS.map((filter) => {
        const isSelected = selected === filter.key;
        const count = counts[filter.key];
        return (
          <AnimatedPressable
            key={filter.key}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
              onSelect(filter.key);
            }}
            style={[
              styles.chip,
              {
                backgroundColor: isSelected ? colors.accent + '20' : colors.card,
                borderColor: isSelected ? colors.accent : colors.border,
              },
            ]}
            accessibilityRole="button"
            accessibilityLabel={`${filter.label} (${count})`}
            accessibilityState={{ selected: isSelected }}
          >
            <Text
              style={[
                styles.chipText,
                { color: isSelected ? colors.accent : colors.muted },
              ]}
            >
              {filter.label}
            </Text>
            <Text
              style={[
                styles.chipCount,
                { color: isSelected ? colors.accent : colors.muted },
              ]}
            >
              {count}
            </Text>
          </AnimatedPressable>
        );
      })}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
  },
  chipText: {
    fontSize: 13,
    fontWeight: '600',
  },
  chipCount: {
    fontSize: 12,
    fontWeight: '500',
  },
});
