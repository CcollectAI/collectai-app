/**
 * ItemDetailsCard — Editable details card showing name, category, collection, condition, value.
 * Includes ItemAttributesSection and CategorySpecificSection.
 */
import React from 'react';
import { View, Text, TextInput, Pressable, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { ValueSourceChip } from '@/components/ValueSourceChip';
import { formatPrice, getCurrencySymbol, UNPRICED_LABEL, isUnpriced, toPriceNum } from '@/lib/format';
import { ItemAttributesSection } from '@/components/ItemAttributesSection';
import { CategorySpecificSection } from '@/components/CategorySpecificSection';
import { formatCategoryName } from '@/constants/categories';
import { Skeleton, SkeletonList } from '@/components/Skeleton';
import { radius, text, fontWeight } from '@/theme/tokens';

interface ItemDetailsCardProps {
  loading?: boolean;
  isDraft: boolean;
  isEditing: boolean;
  editableName: string;
  editableCategory: string;
  editableCollection: string;
  editableCondition: string;
  editableValue: string;
  /** `v_item_values_v1.value_source` — where the figure beside it came from.
   *  Undefined while the row loads, or when the view could not answer; the
   *  chip renders nothing rather than claiming a provenance. */
  valueSource?: string | null;
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

// UNPRICED_LABEL / isUnpriced / toPriceNum moved to @/lib/format (2026-07-27) so
// the collection list row can apply the SAME rule instead of growing a second,
// drifting copy. `toNum` kept as a local alias to avoid churning 20 call sites.
const toNum = toPriceNum;

export const ItemDetailsCard = React.memo(function ItemDetailsCard(props: ItemDetailsCardProps) {
  const { colors: theme } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();

  const {
    loading,
    isDraft, isEditing,
    editableName, editableCategory, editableCollection, editableCondition, editableValue, valueSource,
    isGradingEligible, categorySlug, categoryIdMap,
    itemAttributes, taxonomyVersion, subtypeId, itemCollections,
    itemId, itemSizeValue, sizeSystem, sizeSaving, notes,
    onEditableName, onEditableValue,
    onShowCategoryPicker, onShowCollectionPicker, onShowConditionPicker,
    onSizeChange, onSizeSystemChange, onSizeValueChange,
  } = props;

  if (loading) {
    return (
      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Skeleton width="60%" height={24} borderRadius={radius.xs} />
        <SkeletonList count={4} type="row" />
      </View>
    );
  }

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
          returnKeyType="done"
          accessibilityLabel="Item name"
        />
      ) : (
        <Text style={[styles.name, { color: theme.text }]} accessibilityRole="header" accessibilityLabel={`Item: ${editableName}`}>{editableName}</Text>
      )}

      {/* Category row */}
      <View style={styles.row} accessibilityLabel={`Category: ${formatCategoryName(editableCategory)}`}>
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
            accessibilityLabel={`View ${formatCategoryName(editableCategory)} category`}
          >
            {/* The curated NAME, while navigation still uses the slug below.
                `editableCategory` holds whatever `items.category` stores, which
                is a slug — so this row read "mtg" on every Magic card. */}
            <Text style={[styles.value, { color: theme.accent }]}>
              {formatCategoryName(editableCategory)}
            </Text>
            <Ionicons name="chevron-forward" size={14} color={theme.accent} />
          </Pressable>
        )}
      </View>

      {/* Collection row */}
      <View style={styles.row} accessibilityLabel={`Collection: ${editableCollection}`}>
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
      <View style={styles.row} accessibilityLabel={`${isGradingEligible ? 'Grade' : 'Condition'}: ${editableCondition}`}>
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
      <View
        style={styles.row}
        accessibilityLabel={
          isUnpriced(editableValue)
            ? `Estimated value: ${UNPRICED_LABEL}`
            : `Estimated value: ${formatPrice(toNum(editableValue), settings.currency)}`
        }
      >
        <Text style={[styles.label, { color: theme.muted }]}>Estimated value</Text>
        {isDraft || isEditing ? (
          <View style={styles.editableValueRow}>
            <Text style={[styles.currencySymbol, { color: theme.muted }]}>{getCurrencySymbol(settings.currency)}</Text>
            <TextInput
              style={[styles.editableValueInput, { color: theme.text, borderBottomColor: theme.border, fontWeight: fontWeight.bold }]}
              value={editableValue}
              onChangeText={onEditableValue}
              placeholder="0"
              placeholderTextColor={theme.muted ?? '#64748B'}
              keyboardType="decimal-pad"
              returnKeyType="done"
              accessibilityLabel={`Estimated value in ${settings.currency}`}
            />
          </View>
        ) : (
          <Text
            style={[
              styles.valueHighlight,
              // Muted + smaller: it's an absence of data, not a headline figure.
              isUnpriced(editableValue)
                ? { color: theme.muted, fontSize: 15 }
                : { color: theme.text },
            ]}
            accessibilityRole="text"
            accessibilityLabel={
              isUnpriced(editableValue)
                ? `Estimated value: ${UNPRICED_LABEL}`
                : `Estimated value: ${formatPrice(toNum(editableValue), settings.currency)}`
            }
          >
            {isUnpriced(editableValue)
              ? UNPRICED_LABEL
              : formatPrice(toNum(editableValue), settings.currency)}
          </Text>
        )}
      </View>

      {/* WHERE that number came from. Not decoration: for the 40+ categories
          with no sold-comp source the figure above IS somebody's guess, and
          until 2026-08-19 it was rendered exactly like a comp-backed price.
          Hidden while editing — the member is replacing the number, so its
          old provenance is about to stop being true. */}
      {!isDraft && !isEditing && !isUnpriced(editableValue) && valueSource ? (
        <View style={styles.sourceRow}>
          <ValueSourceChip source={valueSource} />
        </View>
      ) : null}

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
    borderRadius: radius.md,
    padding: 16,
    gap: 10,
  },
  name: {
    fontSize: text['2xl'],
    fontWeight: fontWeight.extrabold,
    letterSpacing: -0.3,
  },
  editableNameInputSimple: {
    fontSize: text.xl,
    fontWeight: fontWeight.bold,
    paddingVertical: 4,
    borderBottomWidth: 1,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 6,
  },
  // Right-aligned under the figure it describes, so the eye reads
  // number-then-provenance rather than treating it as a separate field.
  sourceRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: 4,
  },
  label: {
    fontSize: text.md,
  },
  value: {
    fontSize: text.md,
    fontWeight: fontWeight.medium,
  },
  valueHighlight: {
    fontSize: text.xl,
    fontWeight: fontWeight.extrabold,
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
    fontSize: text.md,
    fontWeight: fontWeight.medium,
  },
  editableValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  editableValueInput: {
    fontSize: text.md,
    fontWeight: fontWeight.medium,
    paddingVertical: 2,
    borderBottomWidth: 1,
    minWidth: 80,
    textAlign: 'right',
  },
  currencySymbol: {
    fontSize: text.md,
    fontWeight: fontWeight.medium,
    marginRight: 2,
  },
});
