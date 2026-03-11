/**
 * WishlistCategoryPicker — Modal for selecting a category.
 */
import React from 'react';
import { View, Text, Modal, ScrollView, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

interface WishlistCategoryPickerProps {
  visible: boolean;
  categories: string[];
  selectedCategory: string;
  onSelect: (cat: string) => void;
  onClose: () => void;
}

export const WishlistCategoryPicker = React.memo(function WishlistCategoryPicker({
  visible,
  categories,
  selectedCategory,
  onSelect,
  onClose,
}: WishlistCategoryPickerProps) {
  const { colors } = useAppTheme();

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <AnimatedPressable
        style={styles.pickerOverlay}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Close category picker"
      >
        <View style={[styles.pickerContent, { backgroundColor: colors.card }]}>
          <Text style={[styles.pickerTitle, { color: colors.text }]}>Select Category</Text>
          <ScrollView style={{ maxHeight: 300 }}>
          {categories.map((cat) => (
            <AnimatedPressable
              key={cat}
              style={[
                styles.pickerItem,
                selectedCategory === cat && { backgroundColor: colors.accent + '20' },
              ]}
              onPress={() => onSelect(cat)}
              accessibilityRole="button"
              accessibilityLabel={`${cat}${selectedCategory === cat ? ', selected' : ''}`}
            >
              <Text style={[styles.pickerItemText, { color: colors.text }]}>{cat}</Text>
              {selectedCategory === cat && (
                <Ionicons name="checkmark" size={20} color={colors.accent} />
              )}
            </AnimatedPressable>
          ))}
          </ScrollView>
        </View>
      </AnimatedPressable>
    </Modal>
  );
});

const styles = StyleSheet.create({
  pickerOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  pickerContent: {
    width: '100%',
    borderRadius: 16,
    padding: 16,
  },
  pickerTitle: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 12,
    textAlign: 'center',
  },
  pickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  pickerItemText: {
    fontSize: 15,
  },
});
