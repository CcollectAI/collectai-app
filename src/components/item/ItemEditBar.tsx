/**
 * ItemEditBar — Save Changes / Cancel bar for edit mode.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

interface ItemEditBarProps {
  onSave: () => void;
  onCancel: () => void;
}

export const ItemEditBar = React.memo(function ItemEditBar({ onSave, onCancel }: ItemEditBarProps) {
  const { colors: theme } = useAppTheme();

  return (
    <View style={styles.editBar}>
      <AnimatedPressable
        onPress={onSave}
        style={[styles.editBarBtnPrimary, { backgroundColor: theme.accent }]}
        accessibilityRole="button"
        accessibilityLabel="Save changes"
      >
        <Ionicons name="checkmark-circle" size={18} color="#fff" />
        <Text style={styles.editBarBtnPrimaryText}>Save Changes</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={onCancel}
        style={[styles.editBarBtn, { backgroundColor: theme.card, borderColor: theme.border }]}
        accessibilityRole="button"
        accessibilityLabel="Cancel editing"
      >
        <Text style={[styles.editBarBtnText, { color: theme.muted }]}>Cancel</Text>
      </AnimatedPressable>
    </View>
  );
});

const styles = StyleSheet.create({
  editBar: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  editBarBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    borderWidth: 1,
  },
  editBarBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
  editBarBtnPrimary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 10,
  },
  editBarBtnPrimaryText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
  },
});
