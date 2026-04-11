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
  colors,
}: Props) {
  const { t } = useTranslation();
  const [config, setConfig] = useState<FilterConfig>(currentConfig);
  const [presets, setPresets] = useState<FilterPreset[]>([]);
  const [showPresetModal, setShowPresetModal] = useState(false);
  const [presetName, setPresetName] = useState('');
  const [expandedSection, setExpandedSection] = useState<string | null>('sort');

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
      logger.warn('[FilterSheet] Failed to load presets:', err);
    }
  }, []);

  const savePresets = useCallback(async (newPresets: FilterPreset[]) => {
    try {
      await AsyncStorage.setItem(PRESETS_KEY, JSON.stringify(newPresets));
      setPresets(newPresets);
    } catch (err) {
      logger.warn('[FilterSheet] Failed to save presets:', err);
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
                {SORT_OPTIONS.map((option) => (
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

            {/* Category Section */}
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
                <View style={styles.chipGrid}>
                  {availableCategories.map((category) => (
                    <Pressable
                      key={category}
                      style={[
                        styles.chip,
                        { borderColor: colors.border },
                        config.categories.includes(category) && {
                          backgroundColor: colors.accent + '15',
                          borderColor: colors.accent,
                        },
                      ]}
                      onPress={() => handleToggleCategory(category)}
                      accessibilityRole="button"
                      accessibilityLabel={`${category}${config.categories.includes(category) ? ', selected' : ''}`}
                    >
                      <Text
                        style={[
                          styles.chipText,
                          {
                            color: config.categories.includes(category)
                              ? colors.accent
                              : colors.text,
                          },
                        ]}
                      >
                        {category}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              </View>
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
                  accessibilityLabel={`Condition filter${expandedSection === 'condition' ? ', expanded' : ', collapsed'}`}
                >
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="star-outline" size={20} color={colors.accent} />
                    <Text style={[styles.sectionTitle, { color: colors.text }]}>Condition</Text>
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
