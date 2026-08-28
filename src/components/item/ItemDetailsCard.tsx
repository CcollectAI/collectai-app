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
import type { CurrencyCode } from '@/data/types';
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
  /** RAW cost basis as typed, in `purchaseCurrency`. '' when unset. */
  editablePurchasePrice: string;
  /** The currency the field above is denominated in. Typed as `CurrencyCode`
   *  rather than `string` because `getCurrencySymbol` only accepts the seven
   *  supported codes — a loose `string` here compiled the call and would have
   *  handed it whatever the column happened to hold. */
  purchaseCurrency?: CurrencyCode | null;
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
  onEditablePurchasePrice: (v: string) => void;
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
    editablePurchasePrice, purchaseCurrency,
    isGradingEligible, categorySlug, categoryIdMap,
    itemAttributes, taxonomyVersion, subtypeId, itemCollections,
    itemId, itemSizeValue, sizeSystem, sizeSaving, notes,
    onEditableName, onEditableValue, onEditablePurchasePrice,
    onShowCategoryPicker, onShowCollectionPicker, onShowConditionPicker,
    onChangeAttribute, catalogAction,
    onSizeChange, onSizeSystemChange, onSizeValueChange,
  } = props;

  /** The picker writes the literal string "Not set", and `app/item/[id].tsx`
   *  normalises a blank column to the same sentinel (`blankAs`), so there is
   *  ONE value meaning "unset" rather than three ("" / null / "Not set")
   *  — docs/ui-playbook.md, *"A destructuring default cannot express 'or
   *  blank'"*, which is the bug that left `""` unrecovered here before. */
  const isFieldSet = (v: string | null | undefined) =>
    !!v && v !== 'Not set';
  /** Read mode hides an unset optional row; edit and draft mode always show it,
   *  because the row IS the way to set it. */
  const inReadMode = !isDraft && !isEditing;
  const showCollectionRow = !inReadMode || isFieldSet(editableCollection);
  const showConditionRow = !inReadMode || isFieldSet(editableCondition);

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

      {/* AN UNSET OPTIONAL FIELD IS NOT A ROW (2026-08-28).
          Reported as *"Collection: Not set"* taking a full line to say nothing.
          Measured before fixing rather than assumed: 73 of 112 prod items have
          no collection and 76 of 112 no condition, so this is the COMMON case —
          two-thirds of members were reading a details card padded with its own
          blanks.

          `ItemAttributesSection` already states the rule for the rows directly
          below these: *"Read mode lists only what exists — an empty row is
          noise. But edit mode listing only what exists means a missing rarity
          can never be added."* These two rows are the same kind of row and were
          simply not covered by it, so the card was internally inconsistent: the
          attribute list hid its blanks while the card above printed its own.

          Edit and draft mode are UNCHANGED — that is the half that matters. A
          field hidden because it is empty is a field that can never be filled
          (`learning_removing_the_opener_strands_the_sheet`). */}
      {showCollectionRow ? (
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
      ) : null}

      {/* Condition / Grade row — same rule, same reason. */}
      {showConditionRow ? (
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
      ) : null}

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

      {/* WHAT YOU PAID — the cost basis, and until 2026-08-26 it could only be
          entered at creation. There was no field for it anywhere on this
          screen, so an item added without one could never gain one; measured
          on prod, 7 of 108 items had a purchase price. Everything downstream
          that says "gain" is built on this number, and `/portfolio/items`
          falls back to the earliest PREDICTION when it is missing — so for the
          rest of the collection the reported profit is model drift.

          It sits directly under Estimated value because the two are the same
          question asked twice ("what is it worth" / "what did it cost"), and a
          member reading one wants the other beside it.

          The CURRENCY LABEL is `purchaseCurrency` when the row already has
          one, NOT `settings.currency`. An item bought in JPY keeps its JPY
          figure; re-labelling that as the viewer's currency is how a stored
          amount silently changes meaning. Only a fresh entry uses the member's
          current setting, and the save path sends that currency explicitly so
          the server converts rather than the trigger assuming EUR. */}
      {isDraft || isEditing ? (
      <View style={styles.row} accessibilityLabel="What you paid">
        <Text style={[styles.label, { color: theme.muted }]}>What you paid</Text>
          <View style={styles.editableValueRow}>
            <Text style={[styles.currencySymbol, { color: theme.muted }]}>
              {getCurrencySymbol(purchaseCurrency || settings.currency)}
            </Text>
            <TextInput
              style={[styles.editableValueInput, { color: theme.text, borderBottomColor: theme.border, fontWeight: fontWeight.bold }]}
              value={editablePurchasePrice}
              onChangeText={onEditablePurchasePrice}
              placeholder="Not set"
              placeholderTextColor={theme.muted ?? '#64748B'}
              keyboardType="decimal-pad"
              returnKeyType="done"
              accessibilityLabel={`What you paid, in ${purchaseCurrency || settings.currency}`}
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
        reservedLabels={[
          'Category',
          // RESERVED ONLY WHILE THE ROW IS DRAWN. A label reserved by a parent
          // that has stopped rendering it deletes the child's copy of the same
          // fact and shows neither — the strand-the-opener shape, one component
          // up. These two now hide when unset, so the reservation has to move
          // with them or a captured `collection`/`grade` attribute would vanish
          // behind a row that is no longer there.
          ...(showCollectionRow ? ['Collection'] : []),
          ...(showConditionRow ? [isGradingEligible ? 'Grade' : 'Condition'] : []),
        ]}
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
