/**
 * ItemDetailsCard — Editable details card showing name, category, collection, condition, value.
 * Includes ItemAttributesSection and CategorySpecificSection.
 */
import React from 'react';
import { View, Text, TextInput, Pressable, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { formatPrice, getCurrencySymbol } from '@/lib/format';
import { ItemAttributesSection } from '@/components/ItemAttributesSection';
import { CategorySpecificSection } from '@/components/CategorySpecificSection';

interface ItemDetailsCardProps {
  isDraft: boolean;
  isEditing: boolean;
  editableName: string;
  editableCategory: string;
  editableCollection: string;
  editableCondition: string;
  editableValue: string;
  isGradingEligible: boolean;
  categorySlug: string;
  categoryIdMap: Record<string, string>;
  itemAttributes: Record<string, unknown> | null;
  taxonomyVersion?: string;
  subtypeId?: string;
  itemCollections: string[];
  itemId?: string;
  itemSizeValue: string;
  sizeSystem: 'us' | 'eu' | 'uk' | 'mm';
  sizeSaving: boolean;
  notes: string;
  onEditableName: (v: string) => void;
  onEditableValue: (v: string) => void;
  onShowCategoryPicker: () => void;
  onShowCollectionPicker: () => void;
  onShowConditionPicker: () => void;
  onSizeChange: (sizeVal: string, system: string) => void;
  onSizeSystemChange: (s: 'us' | 'eu' | 'uk' | 'mm') => void;
  onSizeValueChange: (v: string) => void;
}

const toNum = (value: string | number | undefined | null): number | undefined => {
  if (value === undefined || value === null || value === '') return undefined;
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return undefined;
  return num;
};

export const ItemDetailsCard = React.memo(function ItemDetailsCard(props: ItemDetailsCardProps) {
  const { colors: theme } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();

  const {
    isDraft, isEditing,
    editableName, editableCategory, editableCollection, editableCondition, editableValue,
    isGradingEligible, categorySlug, categoryIdMap,
    itemAttributes, taxonomyVersion, subtypeId, itemCollections,
    itemId, itemSizeValue, sizeSystem, sizeSaving, notes,
    onEditableName, onEditableValue,
    onShowCategoryPicker, onShowCollectionPicker, onShowConditionPicker,
    onSizeChange, onSizeSystemChange, onSizeValueChange,
  } = props;

  return (
    <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
      {/* Editable Name (draft or edit mode) */}
      {isDraft || isEditing ? (
        <TextInput
          style={[styles.editableNameInputSimple, { color: theme.text, borderBottomColor: theme.border }]}
          value={editableName}
          onChangeText={onEditableName}
          placeholder="Item name"
          placeholderTextColor={theme.muted ?? '#64748B'}
          accessibilityLabel="Item name"
        />
      ) : (
        <Text style={[styles.name, { color: theme.text }]}>{editableName}</Text>
      )}

      {/* Category row */}
      <View style={styles.row}>
        <Text style={[styles.label, { color: theme.muted }]}>Category</Text>
        {isDraft || isEditing ? (
          <Pressable
            onPress={onShowCategoryPicker}
            style={[styles.dropdownFieldRow, { borderBottomColor: theme.border }]}
            accessibilityRole="button"
            accessibilityLabel={`Category: ${editableCategory === 'Unknown category' ? 'not set' : editableCategory}. Tap to change`}
          >
            <Text style={[styles.dropdownFieldTextSmall, { color: editableCategory === 'Unknown category' ? theme.muted : theme.text }]}>
              {editableCategory === 'Unknown category' ? 'Select category' : editableCategory}
            </Text>
            <Ionicons name="chevron-down" size={14} color={theme.muted} />
          </Pressable>
        ) : (
          <Pressable
            onPress={() => {
              const categoryId = categoryIdMap[editableCategory] || editableCategory.toLowerCase().replace(/[^a-z0-9]/g, '');
              router.push(`/categories/${categoryId}`);
            }}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}
            accessibilityRole="link"
            accessibilityLabel={`View ${editableCategory} category`}
          >
            <Text style={[styles.value, { color: theme.accent }]}>{editableCategory}</Text>
            <Ionicons name="chevron-forward" size={14} color={theme.accent} />
          </Pressable>
        )}
      </View>

      {/* Collection row */}
      <View style={styles.row}>
        <Text style={[styles.label, { color: theme.muted }]}>Collection</Text>
        {isDraft || isEditing ? (
          <Pressable
            onPress={onShowCollectionPicker}
            style={[styles.dropdownFieldRow, { borderBottomColor: theme.border }]}
            accessibilityRole="button"
            accessibilityLabel={`Collection: ${editableCollection}. Tap to change`}
          >
            <Text style={[styles.dropdownFieldTextSmall, { color: editableCollection === 'Not set' ? theme.muted : theme.text }]}>
              {editableCollection}
            </Text>
            <Ionicons name="chevron-down" size={14} color={theme.muted} />
          </Pressable>
        ) : (
          <Text style={[styles.value, { color: theme.text }]}>{editableCollection}</Text>
        )}
      </View>

      {/* Condition / Grade row */}
      <View style={styles.row}>
        <Text style={[styles.label, { color: theme.muted }]}>
          {isGradingEligible ? 'Grade' : 'Condition'}
        </Text>
        {isDraft || isEditing ? (
          <Pressable
            onPress={onShowConditionPicker}
            style={[styles.dropdownFieldRow, { borderBottomColor: theme.border }]}
            accessibilityRole="button"
            accessibilityLabel={`${isGradingEligible ? 'Grade' : 'Condition'}: ${editableCondition}. Tap to change`}
          >
            <Text style={[styles.dropdownFieldTextSmall, { color: editableCondition === 'Not set' ? theme.muted : theme.text }]}>
              {editableCondition}
            </Text>
            <Ionicons name="chevron-down" size={14} color={theme.muted} />
          </Pressable>
        ) : (
          <Text style={[styles.value, { color: theme.text }]} accessibilityLabel={`${isGradingEligible ? 'Grade' : 'Condition'}: ${editableCondition}`}>{editableCondition}</Text>
        )}
      </View>

      {/* Value row */}
      <View style={styles.row}>
        <Text style={[styles.label, { color: theme.muted }]}>Estimated value</Text>
        {isDraft || isEditing ? (
          <View style={styles.editableValueRow}>
            <Text style={[styles.currencySymbol, { color: theme.muted }]}>{getCurrencySymbol(settings.currency)}</Text>
            <TextInput
              style={[styles.editableValueInput, { color: theme.text, borderBottomColor: theme.border, fontWeight: '700' }]}
              value={editableValue}
              onChangeText={onEditableValue}
              placeholder="0"
              placeholderTextColor={theme.muted ?? '#64748B'}
              keyboardType="decimal-pad"
              accessibilityLabel={`Estimated value in ${settings.currency}`}
            />
          </View>
        ) : (
          <Text
            style={[styles.valueHighlight, { color: theme.text }]}
            accessibilityRole="text"
            accessibilityLabel={`Estimated value: ${formatPrice(toNum(editableValue))}`}
          >
            {formatPrice(toNum(editableValue))}
          </Text>
        )}
      </View>

      {/* Item Attributes Section */}
      <ItemAttributesSection
        attributes={itemAttributes}
        category={editableCategory}
        taxonomyVersion={taxonomyVersion}
        subtypeId={subtypeId}
        collections={itemCollections}
      />

      {/* Category-Specific Sections */}
      <CategorySpecificSection
        categorySlug={categorySlug}
        isDraft={isDraft}
        itemId={itemId}
        itemAttributes={itemAttributes}
        itemSizeValue={itemSizeValue}
        sizeSystem={sizeSystem}
        sizeSaving={sizeSaving}
        notes={notes}
        hapticsEnabled={settings.hapticsEnabled}
        theme={theme}
        onSizeChange={onSizeChange}
        onSizeSystemChange={onSizeSystemChange}
        onSizeValueChange={onSizeValueChange}
      />
    </View>
  );
});

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    borderRadius: 16,
    padding: 16,
    gap: 10,
  },
  name: {
    fontSize: 22,
    fontWeight: '800',
    letterSpacing: -0.3,
  },
  editableNameInputSimple: {
    fontSize: 20,
    fontWeight: '700',
    paddingVertical: 4,
    borderBottomWidth: 1,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 6,
  },
  label: {
    fontSize: 13,
  },
  value: {
    fontSize: 13,
    fontWeight: '500',
  },
  valueHighlight: {
    fontSize: 18,
    fontWeight: '800',
    letterSpacing: -0.2,
  },
  dropdownFieldRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 2,
    borderBottomWidth: 1,
    gap: 4,
  },
  dropdownFieldTextSmall: {
    fontSize: 13,
    fontWeight: '500',
  },
  editableValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  editableValueInput: {
    fontSize: 13,
    fontWeight: '500',
    paddingVertical: 2,
    borderBottomWidth: 1,
    minWidth: 80,
    textAlign: 'right',
  },
  currencySymbol: {
    fontSize: 13,
    fontWeight: '500',
    marginRight: 2,
  },
});
