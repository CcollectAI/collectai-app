/**
 * AddManualBasicInfoSection — Name, category picker, and set/series fields.
 */

import React from 'react';
import { View, Text, TextInput, TouchableOpacity, Keyboard, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { CategoryPickerModal, CUSTOM_CATEGORY_SENTINEL } from './CategoryPickerModal';

interface FormField {
  value: string;
  error?: string | null;
  touched?: boolean;
  onChange: (text: string) => void;
  onBlur: () => void;
}

interface AddManualBasicInfoSectionProps {
  nameField: FormField;
  category: string;
  customCategoryText: string;
  onCustomCategoryTextChange: (text: string) => void;
  gameOrSeries: string;
  onGameOrSeriesChange: (text: string) => void;
  categoryPickerOpen: boolean;
  onOpenCategoryPicker: () => void;
  onCloseCategoryPicker: () => void;
  onSelectCategory: (label: string) => void;
  onClearCategory: () => void;
  onSuggestNew: () => void;
}

export const AddManualBasicInfoSection = React.memo(function AddManualBasicInfoSection({
  nameField,
  category,
  customCategoryText,
  onCustomCategoryTextChange,
  gameOrSeries,
  onGameOrSeriesChange,
  categoryPickerOpen,
  onOpenCategoryPicker,
  onCloseCategoryPicker,
  onSelectCategory,
  onClearCategory,
  onSuggestNew,
}: AddManualBasicInfoSectionProps) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name="information-circle-outline" size={16} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Basic Information</Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {/* Name */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>
            Item name <Text style={{ color: colors.accent }}>*</Text>
          </Text>
          <View style={[styles.inputWrap, { borderColor: nameField.touched && nameField.error ? colors.danger : colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="text-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={nameField.value}
              onChangeText={nameField.onChange}
              onBlur={nameField.onBlur}
              placeholder="e.g. Charizard GX (Alt Art)"
              placeholderTextColor={colors.muted}
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel="Item name"
              testID="name-input"
              returnKeyType="next"
            />
          </View>
          {nameField.touched && nameField.error && (
            <Text style={[styles.fieldError, { color: colors.danger }]}>{nameField.error}</Text>
          )}
        </View>

        {/* Category Dropdown */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>Category</Text>
          <TouchableOpacity
            activeOpacity={0.7}
            onPress={() => { Keyboard.dismiss(); fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onOpenCategoryPicker(); }}
            style={[styles.dropdownTrigger, { borderColor: category ? colors.accent : colors.border, backgroundColor: colors.background }]}
            accessibilityRole="button"
            accessibilityLabel={category === CUSTOM_CATEGORY_SENTINEL ? 'Custom category selected' : category ? `Category: ${category}` : "Select a category"}
          >
            <Text style={[styles.dropdownText, { color: category ? colors.text : colors.muted }]} numberOfLines={1}>
              {category === CUSTOM_CATEGORY_SENTINEL ? 'Other (custom)' : category || "Select a category"}
            </Text>
            <Ionicons name="chevron-down" size={16} color={colors.muted} />
          </TouchableOpacity>
        </View>

        {/* Custom category free-text input — visible only when "Other" is selected */}
        {category === CUSTOM_CATEGORY_SENTINEL && (
          <View style={styles.fieldBlock}>
            <Text style={[styles.fieldLabel, { color: colors.text }]}>Custom category name</Text>
            <View style={[styles.inputWrap, { borderColor: colors.accent, backgroundColor: colors.background }]}>
              <Ionicons name="create-outline" size={16} color={colors.accent} style={styles.inputIcon} />
              <TextInput
                value={customCategoryText}
                onChangeText={onCustomCategoryTextChange}
                placeholder="e.g. Vintage Lamps, Wine, Coins"
                placeholderTextColor={colors.muted}
                style={[styles.input, { color: colors.text }]}
                autoFocus
                maxLength={64}
                accessibilityLabel="Custom category name"
                returnKeyType="next"
              />
            </View>
            <Text style={[styles.customHint, { color: colors.muted }]}>
              Custom categories won't have AI pricing — you set the value yourself
            </Text>
          </View>
        )}

        <CategoryPickerModal
          visible={categoryPickerOpen}
          selectedCategory={category}
          onSelect={onSelectCategory}
          onClear={onClearCategory}
          onClose={onCloseCategoryPicker}
          onSuggestNew={onSuggestNew}
        />

        {/* Game / Series */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>Set / Series</Text>
          <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="albums-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={gameOrSeries}
              onChangeText={onGameOrSeriesChange}
              placeholder="e.g. Scarlet & Violet, Master Grade"
              placeholderTextColor={colors.muted}
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel="Set or series"
              returnKeyType="next"
            />
          </View>
        </View>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  section: { marginBottom: 20 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  sectionTitle: { fontSize: 14, fontWeight: '600' },
  card: { borderRadius: 12, borderWidth: 1, padding: 14 },
  fieldBlock: { marginBottom: 14 },
  fieldLabel: { fontSize: 13, fontWeight: '600', marginBottom: 6 },
  inputWrap: {
    flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, height: 44,
  },
  inputIcon: { marginRight: 8 },
  input: { flex: 1, fontSize: 14, paddingVertical: 0 },
  fieldError: { fontSize: 12, marginTop: 4, marginLeft: 4 },
  dropdownTrigger: {
    flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, height: 44,
  },
  dropdownText: { flex: 1, fontSize: 14 },
  customHint: { fontSize: 12, marginTop: 4, marginLeft: 4, fontStyle: 'italic' },
});
