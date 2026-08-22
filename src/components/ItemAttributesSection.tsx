/**
 * ItemAttributesSection — the captured `items.attrs` as label/value rows.
 *
 * ONE renderer, ONE mount (2026-08-20). This used to be mounted TWICE on the
 * item screen — once inside `ItemDetailsCard`, once again standalone from
 * `app/item/[id].tsx` — each fed by its own fetch of the same row, so a
 * Pokemon card showed "Item Details" twice with different data underneath.
 * The two copies were not even equivalent:
 *
 *   - the inner one was passed `editableCategory`, a DISPLAY NAME, into
 *     `getCategoryFields`, which is keyed by SLUG (docs/TAXONOMY.md, "Two
 *     vocabularies"). It therefore lost category ordering and labels silently.
 *   - the outer one had the saved-row `subtypeId` and collections the inner
 *     one never received.
 *
 * The surviving mount is inside the details card, directly under Estimated
 * value, fed by the screen's saved-row state. It renders as ROWS IN THAT CARD
 * — no border, no icon header — because a bordered card nested inside a
 * bordered card is what "messy" means (docs/ui-playbook.md, "A profile that
 * opens with three card idioms in a row").
 *
 * `CategorySpecificSection` no longer renders plain attribute rows either
 * (same date): every one of its 71 rows read a key out of the same `attrs`
 * this component already lists, so "Card Details" was a third rendering of the
 * same facts. It keeps only what this cannot say — badges (Foil, 1st Edition,
 * Vaulted) and controls (size, build progress, authentication links).
 *
 * Renders nothing if there is nothing captured.
 */

import React from 'react';
import { View, Text, TextInput, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { getCategoryFields } from '@/constants/categoryFields';
import { formatCategoryName } from '@/constants/categories';
import { text, fontWeight } from '@/theme/tokens';

type ItemAttributesSectionProps = {
  attributes: Record<string, unknown> | null;
  category?: string;
  taxonomyVersion?: string;
  subtypeId?: string;
  collections?: string[];
  /**
   * Edit mode. Reported 2026-08-20: *"brand/rarity/set code are not
   * editable"* — and they were not, on any screen. The item card could edit
   * name, value, category, collection, condition and size; every captured
   * attribute was display-only, and `updateItem` accepted no path to them.
   *
   * The rows become inputs here rather than in a separate form so there is one
   * place a member reads an attribute and one place they change it.
   */
  editable?: boolean;
  /** Called per keystroke with the attribute key and its new string value. */
  onChangeAttribute?: (key: string, value: string) => void;
};

/**
 * Map of known attribute keys to human-readable labels.
 * Keys not in this map will be auto-formatted (capitalize + replace underscores).
 */
const KNOWN_LABELS: Record<string, string> = {
  condition: 'Condition',
  grade: 'Grade',
  edition: 'Edition',
  set_name: 'Set',
  set: 'Set',
  rarity: 'Rarity',
  artist: 'Artist',
  year: 'Year',
  isbn: 'ISBN',
  manufacturer: 'Manufacturer',
  language: 'Language',
  publisher: 'Publisher',
  series: 'Series',
  color: 'Color',
  material: 'Material',
  size: 'Size',
  weight: 'Weight',
  release_date: 'Release Date',
  model: 'Model',
  variant: 'Variant',
  printing: 'Printing',
  scale: 'Scale',
  certification: 'Certification',
  // Board Games
  designer: 'Designer',
  player_count: 'Player Count',
  play_time: 'Play Time',
  bgg_rating: 'BGG Rating',
  // City Pop Vinyl
  label: 'Label',
  pressing: 'Pressing',
  format: 'Format',
  obi: 'OBI Strip',
  // Fragrances
  house: 'House',
  fragrance_name: 'Fragrance Name',
  concentration: 'Concentration',
  size_ml: 'Size (ml)',
  gender: 'Gender',
  fragrance_family: 'Fragrance Family',
  fill_level: 'Fill Level',
  batch_code: 'Batch Code',
};

function formatLabel(key: string, catLabels?: Record<string, string>): string {
  if (catLabels?.[key]) return catLabels[key];
  if (KNOWN_LABELS[key]) return KNOWN_LABELS[key];
  // Capitalize first letter, replace underscores with spaces
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'string') return val;
  if (typeof val === 'number') return String(val);
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  if (Array.isArray(val)) return val.join(', ');
  return JSON.stringify(val);
}

export function ItemAttributesSection({
  attributes,
  category,
  taxonomyVersion,
  subtypeId,
  collections,
  editable = false,
  onChangeAttribute,
}: ItemAttributesSectionProps) {
  const { colors } = useAppTheme();

  // Don't render anything if no meaningful data
  const hasAttributes = attributes && Object.keys(attributes).length > 0;
  const hasCollections = collections && collections.length > 0;
  const hasSubtype = !!subtypeId;

  if (!hasAttributes && !hasCollections && !hasSubtype) return null;

  // Get category-aware field ordering
  const categoryFieldDefs = category ? getCategoryFields(category) : [];
  const fieldOrder = categoryFieldDefs.map((f) => f.key);
  // Build label lookup from category fields
  const categoryLabels: Record<string, string> = {};
  for (const f of categoryFieldDefs) {
    categoryLabels[f.key] = f.label;
  }

  /**
   * A brand that only restates the category is not a fact about the item.
   *
   * `formatCategoryName('lorcana')` IS the literal string 'Disney Lorcana', so
   * a Lorcana card rendered Category "Disney Lorcana" and, two rows down,
   * Brand "Disney Lorcana" — the group key repeated inside the group
   * (docs/ui-playbook.md, "a grouped list should not repeat its group key in
   * every member"). Reported as *"is brand not the same as category?"*.
   *
   * Compared on a NORMALISED form rather than verbatim: prod stores brand
   * "Yu-Gi-Oh" against a display name of "Yu-Gi-Oh!", so `===` would miss one
   * of the two rows this exists for. The SLUG is compared too, since some
   * categories store their brand as the slug.
   *
   * Measured on prod 2026-08-22 rather than assumed — 4 of the 5 brand values
   * present restate their category (lorcana, yugioh, mtg); the fifth is
   * "Bunnahabhain" on `whiskey`, a real brand, and this keeps it.
   *
   * READ MODE ONLY. In edit mode the row stays: hiding a field is how a wrong
   * value becomes impossible to correct — the same reason `editableEntries`
   * below adds back the category's empty fields.
   */
  // Diacritics are FOLDED, not stripped. `[^a-z0-9]` alone turns 'Pokémon'
  // into 'pokmon' while a stored brand of 'Pokemon' becomes 'pokemon', so the
  // largest category in the app would never match — found by auditing this
  // very change, not by reading it. The `normalize` guard keeps the failure
  // pointing the safe way: if the engine lacks it, a redundant row is SHOWN
  // rather than a real brand hidden.
  const norm = (v: string) =>
    (typeof v.normalize === 'function' ? v.normalize('NFD').replace(/[\u0300-\u036f]/g, '') : v)
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '');
  const categoryAliases = new Set(
    category ? [norm(category), norm(formatCategoryName(category))].filter(Boolean) : [],
  );
  const restatesCategory = (key: string, val: unknown) =>
    key === 'brand' && typeof val === 'string' && categoryAliases.has(norm(val));

  const rawEntries = hasAttributes
    ? Object.entries(attributes).filter(
        ([key, val]) =>
          val !== null &&
          val !== undefined &&
          val !== '' &&
          (editable || !restatesCategory(key, val)),
      )
    : [];

  // Sort: category-defined fields first (in config order), then remaining alphabetically
  const attributeEntries = rawEntries.sort(([a], [b]) => {
    const idxA = fieldOrder.indexOf(a);
    const idxB = fieldOrder.indexOf(b);
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    return a.localeCompare(b);
  });

  /**
   * In EDIT mode, offer the category's declared fields even when they are
   * empty. Read mode lists only what exists — an empty row is noise. But edit
   * mode listing only what exists means **a missing rarity can never be
   * added**: the row that would hold it is exactly the row that is absent.
   * That is the difference between "display the data" and "edit the record".
   */
  const editableEntries = editable
    ? (() => {
        const present = new Map(attributeEntries);
        for (const key of fieldOrder) if (!present.has(key)) present.set(key, '');
        return Array.from(present.entries());
      })()
    : attributeEntries;

  // If after filtering we still have nothing, bail out
  if (editableEntries.length === 0 && !hasCollections && !hasSubtype) return null;

  return (
    <View style={styles.section}>

      {/* Subtype row */}
      {hasSubtype && (
        <View style={styles.attributeRow}>
          <Text style={[styles.attributeLabel, { color: colors.muted }]}>Subtype</Text>
          <Text style={[styles.attributeValue, { color: colors.text }]}>
            {subtypeId!
              .split('_')
              .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
              .join(' ')}
          </Text>
        </View>
      )}

      {/* Attribute rows */}
      {editableEntries.map(([key, val]) => (
        <View key={key} style={styles.attributeRow}>
          <Text style={[styles.attributeLabel, { color: colors.muted }]}>
            {formatLabel(key, categoryLabels)}
          </Text>
          {editable ? (
            <TextInput
              style={[styles.attributeInput, { color: colors.text, borderBottomColor: colors.border }]}
              defaultValue={formatValue(val) === '-' ? '' : formatValue(val)}
              onChangeText={(t) => onChangeAttribute?.(key, t)}
              placeholder="—"
              placeholderTextColor={colors.muted}
              autoCapitalize="none"
              autoCorrect={false}
              returnKeyType="done"
              accessibilityLabel={`${formatLabel(key, categoryLabels)} value`}
            />
          ) : (
            <Text
              style={[styles.attributeValue, { color: colors.text }]}
              numberOfLines={2}
            >
              {formatValue(val)}
            </Text>
          )}
        </View>
      ))}

      {/* Collection tags */}
      {hasCollections && (
        <View style={styles.collectionsBlock}>
          <Text style={[styles.attributeLabel, { color: colors.muted, marginBottom: 6 }]}>
            Collections
          </Text>
          <View style={styles.tagsRow}>
            {collections!.map((tag) => (
              <View
                key={tag}
                style={[styles.tag, { backgroundColor: (colors.accent as string) + '18' }]}
              >
                <Text style={[styles.tagText, { color: colors.accent }]}>
                  {tag
                    .split('_')
                    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                    .join(' ')}
                </Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* Taxonomy version footer */}
      {taxonomyVersion && (
        <Text style={[styles.taxonomyFooter, { color: colors.muted }]}>
          Taxonomy {taxonomyVersion}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  // Rows in the details card, not a card of their own. The metrics below
  // deliberately COPY `ItemDetailsCard`'s `row` / `label` / `value` — two
  // components drawing the same kind of row at two type sizes is what made the
  // old nested card read as a different app (docs/ui-playbook.md, "Two label
  // languages in one form").
  // ONE rhythm with the rows above, and no rule between them (2026-08-22).
  //
  // These rows sit in `ItemDetailsCard`, whose card carries `gap: 10` and whose
  // `row` adds `marginTop: 6` — so Category/Collection/Condition are 16pt
  // apart. The attribute rows are children of THIS view, not of the card, so
  // the card's gap never reached them and they sat 6pt apart. Reported as
  // "collection category condition has different spacing than rarity brand set
  // code", and it was exactly that: two containers, one of which had the gap.
  //
  // `gap: 10` here restates the card's own gap, so 10 + `attributeRow`'s 6 = 16
  // between attribute rows, and 10 (card) + 6 (row) = 16 from Condition to the
  // first one. Change the card's gap and this has to change with it.
  //
  // The hairline and its 18pt of padding are gone with it: the two groups are
  // one continuous list of label/value rows, and a rule that separates them
  // asserts a distinction the data does not have.
  section: {
    gap: 10,
  },
  attributeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 6,
    gap: 12,
  },
  attributeLabel: {
    fontSize: text.md,
    flexShrink: 1,
  },
  // Same metrics as `attributeValue` plus the underline every other editable
  // field on this card uses — two controls in one form must be one size
  // (docs/ui-playbook.md).
  attributeInput: {
    fontSize: text.md,
    fontWeight: fontWeight.medium,
    flexShrink: 1,
    minWidth: 120,
    textAlign: 'right',
    paddingVertical: 2,
    borderBottomWidth: 1,
  },
  attributeValue: {
    fontSize: text.md,
    fontWeight: fontWeight.medium,
    flexShrink: 1,
    textAlign: 'right',
  },
  collectionsBlock: {
    marginTop: 6,
  },
  tagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  tag: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  tagText: {
    fontSize: 12,
    fontWeight: '500',
  },
  taxonomyFooter: {
    // `sm`, not the 11pt literal it carried: the type scale bans anything
    // below 12 for text a user reads (docs/ui-playbook.md).
    fontSize: text.sm,
    marginTop: 12,
    textAlign: 'right',
    fontStyle: 'italic',
  },
});

export default ItemAttributesSection;
