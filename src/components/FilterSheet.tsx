/**
 * FilterSheet - Bottom sheet for advanced filtering and sorting options.
 * Supports category, price range, condition, and saved presets.
 */

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  Pressable,
  ScrollView,
  TextInput,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fireHaptic, HapticIntent } from '@/haptics';
import { logger } from '@/lib/logger';
import { PriceRangeFilter } from '@/components/PriceRangeFilter';
import { useTranslation } from 'react-i18next';

export type SortOption = 'value_desc' | 'value_asc' | 'name_asc' | 'name_desc' | 'date_desc' | 'date_asc';

export interface FilterConfig {
  categories: string[];
  priceMin: number | null;
  priceMax: number | null;
  conditions: string[];
  sortBy: SortOption;
}

export interface FilterPreset {
  id: string;
  name: string;
  config: FilterConfig;
}

interface Props {
  visible: boolean;
  onClose: () => void;
  onApply: (config: FilterConfig) => void;
  currentConfig: FilterConfig;
  availableCategories: string[];
  availableConditions: string[];
  /** Display names for `availableCategories`, keyed by the value passed in.
   *  The VALUE written into FilterConfig.categories is always the key, never
   *  the label — a picker that writes display names into a slug column kills
   *  the join silently (learning_join_vocabulary_slug_vs_display_name).
   *  Unmapped entries fall back to the raw value. */
  categoryLabels?: Record<string, string>;
  /** Restricts and relabels the sort list. Callers that support fewer than the
   *  six default keys MUST narrow this: offering a sort the screen then maps
   *  onto something else leaves the sheet showing a selection that does not
   *  match the results. */
  sortOptions?: { value: SortOption; label: string }[];
  /** Heading for the `availableConditions` section. Overridable because not
   *  every caller uses that list for literal item conditions. */
  conditionsTitle?: string;
  /** Currency symbol for the price inputs, e.g. '€'. Pass it whenever the
   *  bounds are interpreted in a specific currency — otherwise the two fields
   *  are unitless numbers and the user has to guess. */
  priceCurrencySymbol?: string;
  colors: {
    background: string;
    card: string;
    text: string;
    muted: string;
    accent: string;
    border: string;
  };
}

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: 'value_desc', label: 'Value (High → Low)' },
  { value: 'value_asc', label: 'Value (Low → High)' },
  { value: 'name_asc', label: 'Name (A → Z)' },
  { value: 'name_desc', label: 'Name (Z → A)' },
  { value: 'date_desc', label: 'Recently Added' },
  { value: 'date_asc', label: 'Oldest First' },
];

/** Hoisted so the default identity is stable across renders — an inline `{}`
 *  in the destructure would be a fresh object every time and would defeat the
 *  memo on this component for callers that omit the prop. */
const NO_CATEGORY_LABELS: Record<string, string> = {};

const PRESETS_KEY = '@collectai/filter_presets';

const DEFAULT_CONFIG: FilterConfig = {
  categories: [],
  priceMin: null,
  priceMax: null,
  conditions: [],
  sortBy: 'value_desc',
};

function FilterSheetInner({
  visible,
  onClose,
  onApply,
  currentConfig,
  availableCategories,
  availableConditions,
  categoryLabels = NO_CATEGORY_LABELS,
  sortOptions = SORT_OPTIONS,
  conditionsTitle = 'Condition',
  priceCurrencySymbol,
  colors,
}: Props) {
  const { t } = useTranslation();
  const [config, setConfig] = useState<FilterConfig>(currentConfig);
  const [presets, setPresets] = useState<FilterPreset[]>([]);
  const [showPresetModal, setShowPresetModal] = useState(false);
  const [presetName, setPresetName] = useState('');
  const [expandedSection, setExpandedSection] = useState<string | null>('sort');
  // Anchored category menu (2026-08-29). Separate from `expandedSection`: the
  // section still expands to reveal the TRIGGER, and the menu is a layer above
  // that. Folding the two together made the whole section vanish while the
  // menu was open.
  const [categoryMenuOpen, setCategoryMenuOpen] = useState(false);

  // Load presets on mount
  useEffect(() => {
    loadPresets();
  }, []);

  // Sync config when visible changes
  useEffect(() => {
    if (visible) {
      setConfig(currentConfig);
    }
  }, [visible, currentConfig]);

  const loadPresets = useCallback(async () => {
    try {
      const stored = await AsyncStorage.getItem(PRESETS_KEY);
      if (stored) {
        setPresets(JSON.parse(stored));
      }
    } catch (err) {
      logger.error('[FilterSheet] Failed to load presets:', err);
    }
  }, []);

  const savePresets = useCallback(async (newPresets: FilterPreset[]) => {
    try {
      await AsyncStorage.setItem(PRESETS_KEY, JSON.stringify(newPresets));
      setPresets(newPresets);
    } catch (err) {
      logger.error('[FilterSheet] Failed to save presets:', err);
    }
  }, []);

  const handleToggleCategory = useCallback((category: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    setConfig((prev) => ({
      ...prev,
      categories: prev.categories.includes(category)
        ? prev.categories.filter((c) => c !== category)
        : [...prev.categories, category],
    }));
  }, []);

  const handleToggleCondition = useCallback((condition: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    setConfig((prev) => ({
      ...prev,
      conditions: prev.conditions.includes(condition)
        ? prev.conditions.filter((c) => c !== condition)
        : [...prev.conditions, condition],
    }));
  }, []);

  const handleSetSort = useCallback((sortBy: SortOption) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    setConfig((prev) => ({ ...prev, sortBy }));
  }, []);

  const handlePriceChange = useCallback((field: 'priceMin' | 'priceMax', value: string) => {
    const numValue = value === '' ? null : parseFloat(value);
    setConfig((prev) => ({
      ...prev,
      [field]: isNaN(numValue as number) ? null : numValue,
    }));
  }, []);

  const handleReset = useCallback(() => {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED);
    setConfig(DEFAULT_CONFIG);
  }, []);

  const handleApply = useCallback(() => {
    fireHaptic(HapticIntent.CONFIDENCE_HIGH);
    onApply(config);
    onClose();
  }, [config, onApply, onClose]);

  const handleSavePreset = useCallback(() => {
    if (!presetName.trim()) return;

    fireHaptic(HapticIntent.CONFIDENCE_HIGH);
    const newPreset: FilterPreset = {
      id: Date.now().toString(),
      name: presetName.trim(),
      config: { ...config },
    };
    savePresets([...presets, newPreset]);
    setShowPresetModal(false);
    setPresetName('');
  }, [presetName, config, presets]);

  const handleLoadPreset = useCallback((preset: FilterPreset) => {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED);
    setConfig(preset.config);
  }, []);

  const handleDeletePreset = useCallback((presetId: string) => {
    fireHaptic(HapticIntent.ALERT_TRIGGERED);
    savePresets(presets.filter((p) => p.id !== presetId));
  }, [presets]);

  const toggleSection = useCallback((section: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    setExpandedSection((prev) => (prev === section ? null : section));
  }, []);

  const hasActiveFilters = useMemo(
    () =>
      config.categories.length > 0 ||
      config.conditions.length > 0 ||
      config.priceMin !== null ||
      config.priceMax !== null,
    [config.categories, config.conditions, config.priceMin, config.priceMax],
  );

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <Pressable style={styles.overlay} onPress={onClose}>
        <View
          style={[styles.sheet, { backgroundColor: colors.card }]}
          onStartShouldSetResponder={() => true}
        >
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerLeft}>
              <Text style={[styles.headerTitle, { color: colors.text }]}>
                Filters & Sort
              </Text>
              {hasActiveFilters && (
                <View style={[styles.activeBadge, { backgroundColor: colors.accent }]}>
                  <Text style={styles.activeBadgeText}>Active</Text>
                </View>
              )}
            </View>
            <Pressable onPress={onClose} style={styles.closeBtn} accessibilityRole="button" accessibilityLabel={t('filters.close_a11y')}>
              <Ionicons name="close" size={24} color={colors.text} />
            </Pressable>
          </View>

          <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
            {/* Saved Presets */}
            {presets.length > 0 && (
              <View style={styles.presetsSection}>
                <Text style={[styles.presetsLabel, { color: colors.muted }]}>
                  Saved Presets
                </Text>
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.presetsRow}
                >
                  {presets.map((preset) => (
                    <Pressable
                      key={preset.id}
                      style={[styles.presetChip, { borderColor: colors.border }]}
                      onPress={() => handleLoadPreset(preset)}
                      onLongPress={() => handleDeletePreset(preset.id)}
                      accessibilityRole="button"
                      accessibilityLabel={`Load preset: ${preset.name}`}
                      accessibilityHint="Long press to delete"
                    >
                      <Text style={[styles.presetChipText, { color: colors.text }]}>
                        {preset.name}
                      </Text>
                    </Pressable>
                  ))}
                </ScrollView>
              </View>
            )}

            {/* Sort Section */}
            <Pressable
              style={[styles.sectionHeader, { borderColor: colors.border }]}
              onPress={() => toggleSection('sort')}
              accessibilityRole="button"
              accessibilityLabel={`Sort By${expandedSection === 'sort' ? ', expanded' : ', collapsed'}`}
            >
              <View style={styles.sectionHeaderLeft}>
                <Ionicons name="swap-vertical" size={20} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>{t('filters.sort_by')}</Text>
              </View>
              <Ionicons
                name={expandedSection === 'sort' ? 'chevron-up' : 'chevron-down'}
                size={20}
                color={colors.muted}
              />
            </Pressable>
            {expandedSection === 'sort' && (
              <View style={styles.sectionContent}>
                {sortOptions.map((option) => (
                  <Pressable
                    key={option.value}
                    style={[
                      styles.sortOption,
                      { borderColor: colors.border },
                      config.sortBy === option.value && {
                        backgroundColor: colors.accent + '15',
                        borderColor: colors.accent,
                      },
                    ]}
                    onPress={() => handleSetSort(option.value)}
                    accessibilityRole="button"
                    accessibilityLabel={`Sort by ${option.label}${config.sortBy === option.value ? ', selected' : ''}`}
                  >
                    <Text
                      style={[
                        styles.sortOptionText,
                        { color: config.sortBy === option.value ? colors.accent : colors.text },
                      ]}
                    >
                      {option.label}
                    </Text>
                    {config.sortBy === option.value && (
                      <Ionicons name="checkmark" size={18} color={colors.accent} />
                    )}
                  </Pressable>
                ))}
              </View>
            )}

            {/* Category Section — hidden when there is nothing to choose from,
                the same guard the conditions section below already uses. The
                marketplace feeds this from live-listing facets, so an empty
                marketplace produced a section that expanded to a blank gap:
                a control you can open that contains nothing. Caught on device,
                not by any test. */}
            {availableCategories.length > 0 && (
              <>
            <Pressable
              style={[styles.sectionHeader, { borderColor: colors.border }]}
              onPress={() => toggleSection('category')}
              accessibilityRole="button"
              accessibilityLabel={`Category filter${expandedSection === 'category' ? ', expanded' : ', collapsed'}`}
            >
              <View style={styles.sectionHeaderLeft}>
                <Ionicons name="folder-outline" size={20} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Category</Text>
                {config.categories.length > 0 && (
                  <View style={[styles.countBadge, { backgroundColor: colors.accent }]}>
                    <Text style={styles.countBadgeText}>{config.categories.length}</Text>
                  </View>
                )}
              </View>
              <Ionicons
                name={expandedSection === 'category' ? 'chevron-up' : 'chevron-down'}
                size={20}
                color={colors.muted}
              />
            </Pressable>
            {expandedSection === 'category' && (
              <View style={styles.sectionContent}>
                {/* Bubble menu, not a chip grid (2026-08-29, by request:
                    "i dont want chips menus but rather bubble ios menus").

                    STILL MULTI-SELECT. `config.categories` is an array and the
                    marketplace genuinely filters on several at once, so this is
                    a pill TRIGGER over an anchored checklist rather than a
                    CompactSelect — swapping to that primitive would have looked
                    right and silently removed multi-category filtering, which
                    nobody asked for.

                    The trigger states the selection rather than just naming the
                    control, because "Category" alone makes you open it to learn
                    what you already picked. */}
                <Pressable
                  onPress={() => setCategoryMenuOpen(true)}
                  style={[styles.bubbleTrigger, { backgroundColor: colors.card, borderColor: colors.border }]}
                  accessibilityRole="button"
                  accessibilityLabel={
                    config.categories.length === 0
                      ? 'Category, all categories'
                      : `Category, ${config.categories.length} selected`
                  }
                >
                  <Text style={[styles.bubbleTriggerText, { color: colors.text }]} numberOfLines={1}>
                    {config.categories.length === 0
                      ? 'All categories'
                      : config.categories.length === 1
                        ? (categoryLabels[config.categories[0]] ?? config.categories[0])
                        : `${config.categories.length} selected`}
                  </Text>
                  <Ionicons name="chevron-down" size={16} color={colors.muted} />
                </Pressable>
              </View>
            )}

            <Modal
              visible={categoryMenuOpen}
              transparent
              animationType="fade"
              onRequestClose={() => setCategoryMenuOpen(false)}
            >
              <Pressable
                onPress={() => setCategoryMenuOpen(false)}
                style={styles.menuBackdrop}
                accessibilityRole="button"
                accessibilityLabel="Close category menu"
              >
                {/* Stop the backdrop press from closing when the sheet itself
                    is tapped — without this every row press also dismissed. */}
                <Pressable
                  onPress={(e) => e.stopPropagation()}
                  style={[styles.menuCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                >
                  <Text style={[styles.menuTitle, { color: colors.text }]}>Category</Text>
                  <ScrollView style={styles.menuScroll} keyboardShouldPersistTaps="handled">
                    {/* "All categories" clears rather than selecting a value —
                        an empty array already means unfiltered everywhere
                        downstream, so this must not invent a sentinel. */}
                    <Pressable
                      onPress={() => setConfig((prev) => ({ ...prev, categories: [] }))}
                      style={styles.menuRow}
                      accessibilityRole="button"
                      accessibilityLabel={`All categories${config.categories.length === 0 ? ', selected' : ''}`}
                    >
                      <Text style={[styles.menuRowText, { color: colors.text }]}>All categories</Text>
                      {config.categories.length === 0 && (
                        <Ionicons name="checkmark" size={18} color={colors.accent} />
                      )}
                    </Pressable>
                    {availableCategories.map((category) => {
                      // Label for humans, `category` for the filter value.
                      const label = categoryLabels[category] ?? category;
                      const selected = config.categories.includes(category);
                      return (
                        <Pressable
                          key={category}
                          onPress={() => handleToggleCategory(category)}
                          style={styles.menuRow}
                          accessibilityRole="button"
                          accessibilityLabel={`${label}${selected ? ', selected' : ''}`}
                        >
                          <Text style={[styles.menuRowText, { color: colors.text }]} numberOfLines={1}>
                            {label}
                          </Text>
                          {selected && <Ionicons name="checkmark" size={18} color={colors.accent} />}
                        </Pressable>
                      );
                    })}
                  </ScrollView>
                  <Pressable
                    onPress={() => setCategoryMenuOpen(false)}
                    style={[styles.menuDone, { backgroundColor: colors.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel="Done choosing categories"
                  >
                    <Text style={[styles.menuDoneText, { color: colors.background }]}>Done</Text>
                  </Pressable>
                </Pressable>
              </Pressable>
            </Modal>
              </>
            )}

            {/* Price Range Section */}
            <Pressable
              style={[styles.sectionHeader, { borderColor: colors.border }]}
              onPress={() => toggleSection('price')}
              accessibilityRole="button"
              accessibilityLabel={`Price Range filter${expandedSection === 'price' ? ', expanded' : ', collapsed'}`}
            >
              <View style={styles.sectionHeaderLeft}>
                <Ionicons name="pricetag-outline" size={20} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>{t('filters.price_range')}</Text>
                {(config.priceMin !== null || config.priceMax !== null) && (
                  <View style={[styles.countBadge, { backgroundColor: colors.accent }]}>
                    <Ionicons name="checkmark" size={12} color="#fff" />
                  </View>
                )}
              </View>
              <Ionicons
                name={expandedSection === 'price' ? 'chevron-up' : 'chevron-down'}
                size={20}
                color={colors.muted}
              />
            </Pressable>
            {expandedSection === 'price' && (
              <View style={styles.sectionContent}>
                <PriceRangeFilter
                  priceMin={config.priceMin}
                  priceMax={config.priceMax}
                  onPriceChange={handlePriceChange}
                  currencySymbol={priceCurrencySymbol}
                  colors={colors}
                />
              </View>
            )}

            {/* Condition Section */}
            {availableConditions.length > 0 && (
              <>
                <Pressable
                  style={[styles.sectionHeader, { borderColor: colors.border }]}
                  onPress={() => toggleSection('condition')}
                  accessibilityRole="button"
                  accessibilityLabel={`${conditionsTitle} filter${expandedSection === 'condition' ? ', expanded' : ', collapsed'}`}
                >
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="star-outline" size={20} color={colors.accent} />
                    <Text style={[styles.sectionTitle, { color: colors.text }]}>{conditionsTitle}</Text>
                    {config.conditions.length > 0 && (
                      <View style={[styles.countBadge, { backgroundColor: colors.accent }]}>
                        <Text style={styles.countBadgeText}>{config.conditions.length}</Text>
                      </View>
                    )}
                  </View>
                  <Ionicons
                    name={expandedSection === 'condition' ? 'chevron-up' : 'chevron-down'}
                    size={20}
                    color={colors.muted}
                  />
                </Pressable>
                {expandedSection === 'condition' && (
                  <View style={styles.sectionContent}>
                    <View style={styles.chipGrid}>
                      {availableConditions.map((condition) => (
                        <Pressable
                          key={condition}
                          style={[
                            styles.chip,
                            { borderColor: colors.border },
                            config.conditions.includes(condition) && {
                              backgroundColor: colors.accent + '15',
                              borderColor: colors.accent,
                            },
                          ]}
                          onPress={() => handleToggleCondition(condition)}
                          accessibilityRole="button"
                          accessibilityLabel={`${condition}${config.conditions.includes(condition) ? ', selected' : ''}`}
                        >
                          <Text
                            style={[
                              styles.chipText,
                              {
                                color: config.conditions.includes(condition)
                                  ? colors.accent
                                  : colors.text,
                              },
                            ]}
                          >
                            {condition}
                          </Text>
                        </Pressable>
                      ))}
                    </View>
                  </View>
                )}
              </>
            )}
          </ScrollView>

          {/* Footer Actions */}
          <View style={[styles.footer, { borderColor: colors.border }]}>
            <Pressable style={styles.footerBtnSecondary} onPress={handleReset} accessibilityRole="button" accessibilityLabel={t('filters.reset_a11y')}>
              <Text style={[styles.footerBtnSecondaryText, { color: colors.muted }]}>
                Reset
              </Text>
            </Pressable>

            <Pressable
              style={styles.footerBtnSecondary}
              onPress={() => setShowPresetModal(true)}
              accessibilityRole="button"
              accessibilityLabel={t('filters.save_preset_a11y')}
            >
              <Ionicons name="bookmark-outline" size={16} color={colors.accent} />
              <Text style={[styles.footerBtnSecondaryText, { color: colors.accent }]}>
                Save Preset
              </Text>
            </Pressable>

            <Pressable
              style={[styles.footerBtnPrimary, { backgroundColor: colors.accent }]}
              onPress={handleApply}
              accessibilityRole="button"
              accessibilityLabel={t('filters.apply_a11y')}
            >
              <Text style={styles.footerBtnPrimaryText}>{t('filters.apply')}</Text>
            </Pressable>
          </View>
        </View>
      </Pressable>

      {/* Save Preset Modal */}
      <Modal
        visible={showPresetModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowPresetModal(false)}
      >
        <Pressable
          style={styles.presetModalOverlay}
          onPress={() => setShowPresetModal(false)}
        >
          <View
            style={[styles.presetModalContent, { backgroundColor: colors.card }]}
            onStartShouldSetResponder={() => true}
          >
            <Text style={[styles.presetModalTitle, { color: colors.text }]}>
              Save Filter Preset
            </Text>
            <TextInput
              style={[
                styles.presetInput,
                { borderColor: colors.border, color: colors.text },
              ]}
              placeholder={t('filters.preset_name_placeholder')}
              placeholderTextColor={colors.muted}
              value={presetName}
              onChangeText={setPresetName}
              autoFocus
              accessibilityLabel={t('filters.preset_name_a11y')}
            />
            <View style={styles.presetModalActions}>
              <Pressable
                style={styles.presetModalCancel}
                onPress={() => setShowPresetModal(false)}
                accessibilityRole="button"
                accessibilityLabel="Cancel"
              >
                <Text style={[styles.presetModalCancelText, { color: colors.muted }]}>
                  Cancel
                </Text>
              </Pressable>
              <Pressable
                style={[styles.presetModalSave, { backgroundColor: colors.accent }]}
                onPress={handleSavePreset}
                accessibilityRole="button"
                accessibilityLabel={t('filters.save_preset_btn_a11y')}
              >
                <Text style={styles.presetModalSaveText}>Save</Text>
              </Pressable>
            </View>
          </View>
        </Pressable>
      </Modal>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  sheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '85%',
    paddingBottom: 34,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 12,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  activeBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  activeBadgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '600',
  },
  closeBtn: {
    padding: 4,
  },
  content: {
    paddingHorizontal: 20,
  },
  presetsSection: {
    marginBottom: 16,
  },
  presetsLabel: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 8,
  },
  presetsRow: {
    gap: 8,
  },
  presetChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  presetChipText: {
    fontSize: 13,
    fontWeight: '500',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  sectionHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  countBadge: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 4,
  },
  countBadgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '700',
  },
  sectionContent: {
    paddingVertical: 12,
  },
  sortOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 6,
  },
  sortOptionText: {
    fontSize: 14,
  },
  // Bubble trigger + anchored menu, replacing the category chip grid.
  bubbleTrigger: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 6,
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 12,
    maxWidth: '100%',
  },
  bubbleTriggerText: {
    fontSize: 14,
    fontWeight: '600',
    flexShrink: 1,
  },
  menuBackdrop: {
    // Literal, matching the two backdrops already in this file. The `colors`
    // prop here is a narrow six-token subset with no `overlay`, and widening
    // it for one modal would change every call site.
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  menuCard: {
    borderWidth: 1,
    borderRadius: 14,
    paddingTop: 14,
    paddingBottom: 10,
    paddingHorizontal: 6,
    maxHeight: '70%',
  },
  menuTitle: {
    fontSize: 13,
    fontWeight: '700',
    paddingHorizontal: 12,
    paddingBottom: 8,
  },
  menuScroll: {
    flexGrow: 0,
  },
  menuRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 12,
  },
  menuRowText: {
    fontSize: 15,
    flexShrink: 1,
  },
  menuDone: {
    marginTop: 8,
    marginHorizontal: 6,
    borderRadius: 10,
    paddingVertical: 11,
    alignItems: 'center',
  },
  menuDoneText: {
    fontSize: 15,
    fontWeight: '700',
  },
  chipGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 16,
    borderWidth: 1,
  },
  chipText: {
    fontSize: 13,
    fontWeight: '500',
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 16,
    borderTopWidth: StyleSheet.hairlineWidth,
    gap: 12,
  },
  footerBtnSecondary: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  footerBtnSecondaryText: {
    fontSize: 14,
    fontWeight: '600',
  },
  footerBtnPrimary: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  footerBtnPrimaryText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '700',
  },
  presetModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  presetModalContent: {
    width: '100%',
    borderRadius: 16,
    padding: 20,
  },
  presetModalTitle: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 16,
  },
  presetInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    marginBottom: 16,
  },
  presetModalActions: {
    flexDirection: 'row',
    gap: 12,
  },
  presetModalCancel: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
  },
  presetModalCancelText: {
    fontSize: 14,
    fontWeight: '600',
  },
  presetModalSave: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  presetModalSaveText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '700',
  },
});

export const FilterSheet = React.memo(FilterSheetInner);
export default FilterSheet;
