/**
 * ItemAttributesSection Component
 * Displays item attributes_json data as a clean key-value list.
 * Renders nothing if attributes are null or empty.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { getCategoryFields } from '@/constants/categoryFields';

type ItemAttributesSectionProps = {
  attributes: Record<string, unknown> | null;
  category?: string;
  taxonomyVersion?: string;
  subtypeId?: string;
  collections?: string[];
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

  const rawEntries = hasAttributes
    ? Object.entries(attributes).filter(
        ([, val]) => val !== null && val !== undefined && val !== '',
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

  // If after filtering we still have nothing, bail out
  if (attributeEntries.length === 0 && !hasCollections && !hasSubtype) return null;

  return (
    <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
      {/* Header */}
      <View style={styles.sectionHeader}>
        <Ionicons name="document-text-outline" size={20} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Item Details</Text>
      </View>

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
      {attributeEntries.map(([key, val]) => (
        <View key={key} style={styles.attributeRow}>
          <Text style={[styles.attributeLabel, { color: colors.muted }]}>
            {formatLabel(key, categoryLabels)}
          </Text>
          <Text
            style={[styles.attributeValue, { color: colors.text }]}
            numberOfLines={2}
          >
            {formatValue(val)}
          </Text>
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
  section: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  attributeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
  },
  attributeLabel: {
    fontSize: 13,
    flex: 1,
  },
  attributeValue: {
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
    textAlign: 'right',
  },
  collectionsBlock: {
    marginTop: 8,
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
    fontSize: 11,
    marginTop: 12,
    textAlign: 'right',
    fontStyle: 'italic',
  },
});

export default ItemAttributesSection;
