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
import { formatPrice, getCurrencySymbol, UNPRICED_LABEL, isUnpriced, toPriceNum } from '@/lib/format';
import { ItemAttributesSection } from '@/components/ItemAttributesSection';
import { CategorySpecificSection } from '@/components/CategorySpecificSection';
import { categoryDisplayName } from '@/constants/categories';
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
  /** Collects edited attribute keys for the save handler. */
  onChangeAttribute?: (key: string, value: string) => void;
  /** Rendered under the attribute rows — the 'fill in from catalogue' action. */
  catalogAction?: React.ReactNode;
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
    editableName, editableCategory, editableCollection, editableCondition, editableValue,
    isGradingEligible, categorySlug, categoryIdMap,
    itemAttributes, taxonomyVersion, subtypeId, itemCollections,
    itemId, itemSizeValue, sizeSystem, sizeSaving, notes,
    onEditableName, onEditableValue,
    onShowCategoryPicker, onShowCollectionPicker, onShowConditionPicker,
    onChangeAttribute, catalogAction,
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
      {/* Name — EDIT MODE ONLY, exactly like the value row below.
          In read mode the title moved ABOVE the valuation card (2026-08-23),
          because this card is no longer the first thing on the screen: the
          spec table now sits BELOW the money, and a heading that stayed with
          it would have introduced "Category / Collection / Grade" while the
          figure it names sat further up with nothing above it.

          Editing is the same exception the value row already makes: there the
          name is a form field among the other form fields and belongs with
          them. `ItemTitleBlock` in `app/item/[id].tsx` renders the read-mode
          heading, and it is the ONLY other renderer — one fact, one renderer
          per mode. */}
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
      ) : null}

      {/* Category row */}
      <View style={styles.row} accessibilityLabel={`Category: ${categoryDisplayName(editableCategory)}`}>
        <Text style={[styles.label, { color: theme.muted }]}>Category</Text>
        {isDraft || isEditing ? (
          <Pressable
            onPress={onShowCategoryPicker}
            style={[styles.dropdownFieldRow, { borderBottomColor: theme.border }]}
            accessibilityRole="button"
            accessibilityLabel={`Category: ${editableCategory === 'Unknown category' ? 'not set' : categoryDisplayName(editableCategory)}. Tap to change`}
          >
            {/* `categoryDisplayName`, not the raw state. Reported from a
                screenshot: this dropdown read "yugioh". The read-mode branch
                below already resolved the slug; the EDIT branch printed
                `editableCategory` verbatim, so the one place a member is
                actively looking at the field was the one place it showed the
                database's word for it. Not `formatCategoryName` either — after
                a pick this state holds a display NAME, which that function
                would re-title-case into "Yu Gi Oh!". */}
            <Text style={[styles.dropdownFieldTextSmall, { color: editableCategory === 'Unknown category' ? theme.muted : theme.text }]}>
              {editableCategory === 'Unknown category' ? 'Select category' : categoryDisplayName(editableCategory)}
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
            accessibilityLabel={`View ${categoryDisplayName(editableCategory)} category`}
          >
            {/* The curated NAME, while navigation still uses the slug below.
                `editableCategory` holds whatever `items.category` stores, which
                is a slug — so this row read "mtg" on every Magic card. It can
                ALSO hold a display name, straight from the picker, which is why
                this resolves through `categoryDisplayName` rather than
                `formatCategoryName`: the latter is not idempotent. */}
            <Text style={[styles.value, { color: theme.accent }]}>
              {categoryDisplayName(editableCategory)}
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

      {/* Value row — EDIT MODE ONLY.
          In read mode the figure moved to the valuation card below, where the
          "Help improve our estimates" prompt lives. It used to sit here, four
          rows into a spec table at label/value weight, while the card asking
          whether it was wrong rendered it nowhere — so "Price seems off"
          referred to a number in a different card. It is also the only
          MONETARY fact on the screen and had the least emphasis of anything on
          it. Editing is different: there it is a form field among the other
          form fields, and belongs with them. */}
      {isDraft || isEditing ? (
      <View
        style={styles.row}
        accessibilityLabel={
          isUnpriced(editableValue)
            ? `Estimated value: ${UNPRICED_LABEL}`
            : `Estimated value: ${formatPrice(toNum(editableValue), settings.currency)}`
        }
      >
        <Text style={[styles.label, { color: theme.muted }]}>Estimated value</Text>
        {/* Always the input: this whole row is already gated on
            isDraft || isEditing above, so the read-mode display that
            used to be the `else` of a second, identical ternary was
            unreachable. The read-mode figure lives in the valuation
            card now. */}
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
      </View>
      ) : null}

      {/* The provenance chip moved WITH the number to the valuation card.
          Its own docstring is the reason: "one component, so the item card and
          the detail screen cannot end up describing the same number two ways"
          — leaving a copy here would have been exactly that. */}

      {/* Everything captured about the item, as rows in THIS card, directly
          under the value. The screen used to render this component again
          below the card from its own fetch — same title, same data, twice.

          `categorySlug`, not `editableCategory`: `getCategoryFields` is keyed
          by SLUG and the editable field holds a DISPLAY NAME, so passing the
          latter silently lost the category's field order and labels
          (docs/TAXONOMY.md, "Two vocabularies, and the one place they meet"). */}
      <ItemAttributesSection
        attributes={itemAttributes}
        category={categorySlug}
        taxonomyVersion={taxonomyVersion}
        subtypeId={subtypeId}
        collections={itemCollections}
        // Editable in the same edit mode as the fields above it, so brand,
        // rarity and set code are changed where they are read (2026-08-20).
        // Not on a draft: a draft has no row to PATCH yet.
        editable={isEditing && !isDraft}
        onChangeAttribute={onChangeAttribute}
        /* The labels THIS card already renders as rows above. Without them the
           list drew a second "Grade" four rows under the card's own — the
           playbook's "a kind of row has ONE renderer", broken across a
           component boundary instead of inside one.

           Derived from the same `isGradingEligible` expression that labels the
           row itself, rather than restated as a literal: two copies of a
           predicate is how the offers badge and the offers screen ended up
           disagreeing about what "needs you" means. */
        reservedLabels={['Category', 'Collection', isGradingEligible ? 'Grade' : 'Condition']}
      />

      {/* Directly under the rows it fills in. Hidden while editing: the member
          is already typing those fields by hand, and a button that overwrites
          them mid-edit is a trap. */}
      {!isEditing ? catalogAction : null}

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
  // `name` removed 2026-08-23 — the read-mode title moved to the screen as
  // `styles.itemTitle`, which carries these exact metrics. Left here it would
  // be a dead style that still LOOKS like the definition of the item title.
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
  label: {
    fontSize: text.md,
  },
  value: {
    fontSize: text.md,
    fontWeight: fontWeight.medium,
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
