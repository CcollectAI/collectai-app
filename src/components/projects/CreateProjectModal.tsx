/**
 * Create Project Modal for the Build & Paint Projects screen.
 *
 * Includes category picker, item linker, title input, step template preview,
 * and nested category/item picker modals.
 * Extracted from app/build-paint-projects.tsx to reduce file size.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  Modal,
  KeyboardAvoidingView,
  Platform,
  FlatList,
  Image,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { CATEGORIES, CATEGORY_VISUAL } from '@/data/categories';
import { BUILDABLE_CATEGORIES, getStepTemplateForCategory } from '@/constants/buildStepTemplates';
import { dataProvider, type Item } from '@/data';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import logger from '@/utils/logger';

interface CreateProjectModalProps {
  visible: boolean;
  onClose: () => void;
  onCreated: () => void;
  /** Pre-filled values when navigated from item detail */
  initialTitle?: string;
  initialCategoryId?: string | null;
  initialItem?: { id: string; name: string } | null;
}

export const CreateProjectModal = React.memo(function CreateProjectModal({
  visible,
  onClose,
  onCreated,
  initialTitle = '',
  initialCategoryId = null,
  initialItem = null,
}: CreateProjectModalProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const [newTitle, setNewTitle] = useState(initialTitle);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(initialCategoryId);
  const [selectedItem, setSelectedItem] = useState<Item | null>(
    initialItem ? ({ id: initialItem.id, name: initialItem.name } as Item) : null,
  );
  const [creating, setCreating] = useState(false);
  const [showCategoryPicker, setShowCategoryPicker] = useState(false);
  const [showItemPicker, setShowItemPicker] = useState(false);
  const [showAllCategories, setShowAllCategories] = useState(false);
  const [categoryItems, setCategoryItems] = useState<Item[]>([]);
  const [loadingItems, setLoadingItems] = useState(false);
  const [showStepPreview, setShowStepPreview] = useState(false);

  // Reset state when modal opens with new initial values
  useEffect(() => {
    if (visible) {
      setNewTitle(initialTitle);
      setSelectedCategoryId(initialCategoryId);
      setSelectedItem(
        initialItem ? ({ id: initialItem.id, name: initialItem.name } as Item) : null,
      );
    }
  }, [visible, initialTitle, initialCategoryId, initialItem]);

  const sortedCategories = useMemo(() => {
    const buildable = CATEGORIES.filter((c) =>
      (BUILDABLE_CATEGORIES as readonly string[]).includes(c.id),
    );
    const others = CATEGORIES.filter(
      (c) => !(BUILDABLE_CATEGORIES as readonly string[]).includes(c.id),
    );
    return showAllCategories ? [...buildable, ...others] : buildable;
  }, [showAllCategories]);

  const selectedTemplate = useMemo(() => {
    if (!selectedCategoryId) return null;
    return getStepTemplateForCategory(selectedCategoryId);
  }, [selectedCategoryId]);

  const handleSelectCategory = useCallback(async (catId: string) => {
    setSelectedCategoryId(catId);
    setSelectedItem(null);
    setShowCategoryPicker(false);

    setLoadingItems(true);
    try {
      const items = await dataProvider.listItems();
      setCategoryItems(items.filter((i) => i.category === catId));
    } catch (err) {
      logger.error('[CreateProjectModal] category items fetch failed:', err);
      setCategoryItems([]);
    } finally {
      setLoadingItems(false);
    }
  }, []);

  const handleSelectItem = useCallback((item: Item) => {
    setSelectedItem(item);
    setNewTitle(item.name);
    setShowItemPicker(false);
  }, []);

  const resetAndClose = useCallback(() => {
    setNewTitle('');
    setSelectedCategoryId(null);
    setSelectedItem(null);
    setShowAllCategories(false);
    setShowStepPreview(false);
    onClose();
  }, [onClose]);

  const handleCreateProject = useCallback(async () => {
    if (!newTitle.trim() || creating) return;

    setCreating(true);
    try {
      const catName = selectedCategoryId
        ? CATEGORIES.find((c) => c.id === selectedCategoryId)?.name ?? null
        : null;

      await dataProvider.createBuildPaintProject({
        title: newTitle.trim(),
        category: catName,
        categoryId: selectedCategoryId,
        itemId: selectedItem?.id ?? null,
      });
      resetAndClose();
      onCreated();
    } catch (err: unknown) {
      logger.error('[CreateProjectModal] create error:', err);
    } finally {
      setCreating(false);
    }
  }, [newTitle, creating, selectedCategoryId, selectedItem, resetAndClose, onCreated]);

  return (
    <>
      {/* Create Project Modal */}
      <Modal
        visible={visible}
        animationType="slide"
        transparent
        onRequestClose={resetAndClose}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <ScrollView showsVerticalScrollIndicator={false}>
              <View style={styles.modalHeader}>
                <Text style={[styles.modalTitle, { color: colors.text }]}>{t('projects.new_project')}</Text>
                <AnimatedPressable onPress={resetAndClose} accessibilityRole="button" accessibilityLabel="Close">
                  <Ionicons name="close" size={24} color={colors.muted} />
                </AnimatedPressable>
              </View>

              {/* Category Picker */}
              <Text style={[styles.inputLabel, { color: colors.text }]}>Category</Text>
              <AnimatedPressable
                onPress={() => setShowCategoryPicker(true)}
                style={[styles.pickerBtn, { borderColor: colors.border, backgroundColor: colors.background }]}
                accessibilityRole="button"
                accessibilityLabel={t('projects.select_category_a11y')}
              >
                {selectedCategoryId ? (
                  <View style={styles.pickerSelected}>
                    <View style={[styles.catDot, { backgroundColor: colors.accent }]} />
                    <Text style={[styles.pickerText, { color: colors.text }]}>
                      {CATEGORIES.find((c) => c.id === selectedCategoryId)?.name ?? selectedCategoryId}
                    </Text>
                  </View>
                ) : (
                  <Text style={[styles.pickerPlaceholder, { color: colors.muted }]}>
                    Select a category...
                  </Text>
                )}
                <Ionicons name="chevron-down" size={18} color={colors.muted} />
              </AnimatedPressable>

              {/* Item Picker (only when category is selected) */}
              {selectedCategoryId && (
                <>
                  <Text style={[styles.inputLabel, { color: colors.text, marginTop: 16 }]}>
                    Link to Item (optional)
                  </Text>
                  {loadingItems ? (
                    <ActivityIndicator size="small" color={colors.accent} style={{ marginVertical: 8 }} />
                  ) : selectedItem ? (
                    <View style={[styles.linkedItemRow, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      {selectedItem.imageUrl && (
                        <Image source={{ uri: selectedItem.imageUrl }} style={styles.linkedItemImg} />
                      )}
                      <View style={{ flex: 1 }}>
                        <Text style={[styles.linkedItemName, { color: colors.text }]} numberOfLines={1}>
                          {selectedItem.name}
                        </Text>
                        {selectedItem.price > 0 && (
                          <Text style={[styles.linkedItemPrice, { color: colors.muted }]}>
                            ~{formatPrice(selectedItem.price, settings.currency)}
                          </Text>
                        )}
                      </View>
                      <AnimatedPressable onPress={() => setSelectedItem(null)} accessibilityRole="button" accessibilityLabel={t('projects.remove_linked_item')}>
                        <Ionicons name="close-circle" size={20} color={colors.muted} />
                      </AnimatedPressable>
                    </View>
                  ) : categoryItems.length > 0 ? (
                    <AnimatedPressable
                      onPress={() => setShowItemPicker(true)}
                      style={[styles.pickerBtn, { borderColor: colors.border, backgroundColor: colors.background }]}
                      accessibilityRole="button"
                      accessibilityLabel={t('projects.link_to_portfolio_item')}
                    >
                      <Text style={[styles.pickerPlaceholder, { color: colors.muted }]}>
                        Link to a portfolio item ({categoryItems.length} items)
                      </Text>
                      <Ionicons name="chevron-down" size={18} color={colors.muted} />
                    </AnimatedPressable>
                  ) : (
                    <Text style={[styles.noItemsText, { color: colors.muted }]}>
                      No portfolio items in this category
                    </Text>
                  )}
                </>
              )}

              {/* Title */}
              <Text style={[styles.inputLabel, { color: colors.text, marginTop: 16 }]}>{t('projects.title_required')}</Text>
              <TextInput
                value={newTitle}
                onChangeText={setNewTitle}
                placeholder="e.g., Warhammer Kill Team squad"
                placeholderTextColor={colors.muted}
                accessibilityLabel={t('projects.title_a11y')}
                style={[
                  styles.textInput,
                  { color: colors.text, borderColor: colors.border, backgroundColor: colors.background },
                ]}
              />

              {/* Step template preview */}
              {selectedTemplate && selectedTemplate.steps.length > 0 && (
                <View style={styles.templatePreview}>
                  <AnimatedPressable
                    onPress={() => setShowStepPreview(!showStepPreview)}
                    style={styles.templateHeader}
                    accessibilityRole="button"
                    accessibilityLabel={showStepPreview ? 'Collapse step preview' : 'Expand step preview'}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.templateTitle, { color: colors.text }]}>
                        {selectedTemplate.steps.length} steps for {selectedTemplate.displayName}
                      </Text>
                      <Text style={[styles.templateHint, { color: colors.muted }]}>
                        Template steps will be added after creation
                      </Text>
                    </View>
                    <Ionicons
                      name={showStepPreview ? 'chevron-up' : 'chevron-down'}
                      size={18}
                      color={colors.muted}
                    />
                  </AnimatedPressable>
                  {showStepPreview && (
                    <View style={[styles.templateSteps, { borderTopColor: colors.border }]}>
                      {selectedTemplate.steps.map((s) => (
                        <View key={s.id} style={styles.templateStepRow}>
                          <Text style={[styles.templateStepNum, { color: colors.muted }]}>{s.order}.</Text>
                          <Text style={[styles.templateStepLabel, { color: colors.text }]}>{s.label}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
              )}

              <AnimatedPressable
                onPress={handleCreateProject}
                disabled={!newTitle.trim() || creating}
                style={[
                  styles.createBtn,
                  {
                    backgroundColor: newTitle.trim() ? colors.accent : colors.border,
                    opacity: creating ? 0.7 : 1,
                  },
                ]}
                accessibilityRole="button"
                accessibilityLabel={creating ? 'Creating project' : 'Create project'}
              >
                {creating ? (
                  <ActivityIndicator size="small" color={colors.accentText} />
                ) : (
                  <Text style={[styles.createBtnText, { color: colors.accentText }]}>{t('projects.create_project')}</Text>
                )}
              </AnimatedPressable>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Category Picker Modal */}
      <Modal
        visible={showCategoryPicker}
        animationType="slide"
        transparent
        onRequestClose={() => setShowCategoryPicker(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.pickerModalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>{t('projects.select_category')}</Text>
              <AnimatedPressable onPress={() => setShowCategoryPicker(false)} accessibilityRole="button" accessibilityLabel="Close">
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>
            <FlatList
              data={sortedCategories}
              keyExtractor={(item) => item.id}
              removeClippedSubviews={true}
              maxToRenderPerBatch={10}
              windowSize={5}
              renderItem={({ item: cat }) => {
                const vis = CATEGORY_VISUAL[cat.id];
                const isBuildable = (BUILDABLE_CATEGORIES as readonly string[]).includes(cat.id);
                return (
                  <AnimatedPressable
                    onPress={() => handleSelectCategory(cat.id)}
                    style={[styles.catPickerRow, { borderBottomColor: colors.border }]}
                    accessibilityRole="button"
                    accessibilityLabel={cat.name}
                  >
                    <View style={[styles.catDot, { backgroundColor: colors.accent }]} />
                    <Ionicons name={(vis?.iconName || 'cube-outline') as keyof typeof Ionicons.glyphMap} size={20} color={colors.accent} />
                    <View style={{ flex: 1, marginLeft: 10 }}>
                      <Text style={[styles.catPickerName, { color: colors.text }]}>{cat.name}</Text>
                    </View>
                    {isBuildable && (
                      <View style={[styles.buildBadge, { backgroundColor: colors.accent + '20' }]}>
                        <Text style={[styles.buildBadgeText, { color: colors.accent }]}>Build</Text>
                      </View>
                    )}
                  </AnimatedPressable>
                );
              }}
              ListFooterComponent={
                !showAllCategories ? (
                  <AnimatedPressable
                    onPress={() => setShowAllCategories(true)}
                    style={styles.showAllBtn}
                    accessibilityRole="button"
                    accessibilityLabel={t('projects.show_all_categories_a11y')}
                  >
                    <Text style={[styles.showAllText, { color: colors.accent }]}>
                      Show All Categories ({CATEGORIES.length - BUILDABLE_CATEGORIES.length} more)
                    </Text>
                  </AnimatedPressable>
                ) : null
              }
            />
          </View>
        </View>
      </Modal>

      {/* Item Picker Modal */}
      <Modal
        visible={showItemPicker}
        animationType="slide"
        transparent
        onRequestClose={() => setShowItemPicker(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.pickerModalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>{t('projects.link_item')}</Text>
              <AnimatedPressable onPress={() => setShowItemPicker(false)} accessibilityRole="button" accessibilityLabel="Close">
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>
            <FlatList
              data={categoryItems}
              keyExtractor={(item) => item.id}
              removeClippedSubviews={true}
              maxToRenderPerBatch={10}
              windowSize={5}
              renderItem={({ item }) => (
                <AnimatedPressable
                  onPress={() => handleSelectItem(item)}
                  style={[styles.itemPickerRow, { borderBottomColor: colors.border }]}
                  accessibilityRole="button"
                  accessibilityLabel={item.name}
                >
                  {item.imageUrl ? (
                    <Image source={{ uri: item.imageUrl }} style={styles.itemPickerImg} />
                  ) : (
                    <View style={[styles.itemPickerImgPlaceholder, { backgroundColor: colors.border }]}>
                      <Ionicons name="cube-outline" size={20} color={colors.muted} />
                    </View>
                  )}
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.itemPickerName, { color: colors.text }]} numberOfLines={1}>
                      {item.name}
                    </Text>
                    {item.price > 0 && (
                      <Text style={[styles.itemPickerPrice, { color: colors.muted }]}>
                        ~{formatPrice(item.price, settings.currency)}
                      </Text>
                    )}
                  </View>
                </AnimatedPressable>
              )}
              ListHeaderComponent={
                <AnimatedPressable
                  onPress={() => setShowItemPicker(false)}
                  style={[styles.itemPickerRow, { borderBottomColor: colors.border }]}
                  accessibilityRole="button"
                  accessibilityLabel="Skip"
                >
                  <Ionicons name="remove-circle-outline" size={20} color={colors.muted} style={{ marginRight: 12 }} />
                  <Text style={[styles.itemPickerName, { color: colors.muted }]}>{t('projects.skip_linked_item')}</Text>
                </AnimatedPressable>
              }
            />
          </View>
        </View>
      </Modal>
    </>
  );
});

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
    maxHeight: '85%',
  },
  pickerModalContent: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
    maxHeight: '70%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  textInput: {
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
  },
  pickerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  pickerSelected: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  pickerText: {
    fontSize: 15,
  },
  pickerPlaceholder: {
    fontSize: 15,
  },
  catDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  catPickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    gap: 8,
  },
  catPickerName: {
    fontSize: 15,
    fontWeight: '500',
  },
  buildBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  buildBadgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
  showAllBtn: {
    paddingVertical: 16,
    alignItems: 'center',
  },
  showAllText: {
    fontSize: 14,
    fontWeight: '600',
  },
  linkedItemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 12,
    padding: 10,
    gap: 10,
  },
  linkedItemImg: {
    width: 40,
    height: 40,
    borderRadius: 8,
  },
  linkedItemName: {
    fontSize: 14,
    fontWeight: '500',
  },
  linkedItemPrice: {
    fontSize: 12,
    marginTop: 2,
  },
  noItemsText: {
    fontSize: 13,
    fontStyle: 'italic',
    marginVertical: 4,
  },
  itemPickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    gap: 12,
  },
  itemPickerImg: {
    width: 40,
    height: 40,
    borderRadius: 8,
  },
  itemPickerImgPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemPickerName: {
    fontSize: 15,
    fontWeight: '500',
  },
  itemPickerPrice: {
    fontSize: 12,
    marginTop: 2,
  },
  templatePreview: {
    marginTop: 16,
  },
  templateHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
  },
  templateTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  templateHint: {
    fontSize: 12,
    marginTop: 2,
  },
  templateSteps: {
    borderTopWidth: 1,
    paddingTop: 8,
    marginTop: 4,
  },
  templateStepRow: {
    flexDirection: 'row',
    paddingVertical: 4,
    gap: 8,
  },
  templateStepNum: {
    fontSize: 12,
    width: 20,
    textAlign: 'right',
  },
  templateStepLabel: {
    fontSize: 13,
    flex: 1,
  },
  createBtn: {
    marginTop: 24,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  createBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },
});
