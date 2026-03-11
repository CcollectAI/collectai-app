/**
 * CatalogSuggestionModal — shown when an item isn't recognized.
 *
 * Reusable bottom sheet that lets the user tell us what the item is
 * and which category it belongs to, feeding the catalog learning pipeline.
 */

import React, { useState, useMemo, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  Modal,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Keyboard,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { collectorsApi } from "@/api/collectorsApi";
import { CATEGORIES } from "@/constants/categories";
import { useToast } from "@/components/Toast";
import logger from "@/utils/logger";

// In-memory dedup: don't re-show modal for same input within session
const _shownInputs = new Set<string>();

export type CatalogSuggestionSource = "barcode" | "photo" | "manual" | "url";

interface Props {
  visible: boolean;
  onDismiss: () => void;
  source: CatalogSuggestionSource;
  prefillName?: string;
  inputData?: Record<string, unknown>;
}

const CATEGORY_OPTIONS = CATEGORIES.map((c) => ({
  label: c.name,
  slug: c.slug,
}));

function CatalogSuggestionModalInner({
  visible,
  onDismiss,
  source,
  prefillName = "",
  inputData = {},
}: Props) {
  const { colors } = useAppTheme();
  const { showToast } = useToast();

  const [itemName, setItemName] = useState(prefillName);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [newCategoryText, setNewCategoryText] = useState("");
  const [categoryPickerOpen, setCategoryPickerOpen] = useState(false);
  const [categorySearch, setCategorySearch] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset form when modal opens
  React.useEffect(() => {
    if (visible) {
      setItemName(prefillName);
      setSelectedCategory("");
      setNewCategoryText("");
      setIsSubmitting(false);
    }
  }, [visible, prefillName]);

  // Session dedup — use sorted-key JSON for stable serialisation
  const dedupKey = useMemo(() => {
    const sorted = Object.keys(inputData).sort().reduce<Record<string, unknown>>((acc, k) => {
      acc[k] = inputData[k];
      return acc;
    }, {});
    return `${source}:${JSON.stringify(sorted)}`;
  }, [source, inputData]);

  const shouldShow = visible && !_shownInputs.has(dedupKey);

  const filteredCategories = useMemo(() => {
    const q = categorySearch.toLowerCase().trim();
    if (!q) return CATEGORY_OPTIONS;
    return CATEGORY_OPTIONS.filter((c) => c.label.toLowerCase().includes(q));
  }, [categorySearch]);

  const handleSubmit = useCallback(async () => {
    const name = itemName.trim();
    if (!name) return;

    setIsSubmitting(true);
    _shownInputs.add(dedupKey);

    const suggestedCategory = newCategoryText.trim() || selectedCategory || undefined;

    try {
      await collectorsApi.submitCatalogSuggestion({
        source,
        input_data: inputData,
        suggested_name: name,
        suggested_category: suggestedCategory,
      });

      fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
      showToast({ message: "Thanks for helping improve CollectAI!", type: "success" });
    } catch (err) {
      logger.warn("[CatalogSuggestion] Submit failed:", err);
      // Still dismiss — don't block the user
    } finally {
      setIsSubmitting(false);
      onDismiss();
    }
  }, [itemName, selectedCategory, newCategoryText, source, inputData, dedupKey, onDismiss, showToast]);

  const handleSkip = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    _shownInputs.add(dedupKey);
    onDismiss();
  }, [dedupKey, onDismiss]);

  if (!shouldShow) return null;

  return (
    <Modal
      visible
      animationType="slide"
      transparent
      onRequestClose={handleSkip}
    >
      <KeyboardAvoidingView
        style={styles.overlay}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <TouchableOpacity
          style={styles.backdrop}
          activeOpacity={1}
          onPress={handleSkip}
        />

        <View style={[styles.sheet, { backgroundColor: colors.card }]}>
          {/* Handle bar */}
          <View style={[styles.handleBar, { backgroundColor: colors.border }]} />

          {/* Header */}
          <View style={styles.header}>
            <Ionicons name="help-circle-outline" size={28} color={colors.accent} />
            <View style={styles.headerText}>
              <Text style={[styles.title, { color: colors.text }]}>
                We don't recognize this item yet
              </Text>
              <Text style={[styles.subtitle, { color: colors.muted }]}>
                Help us improve CollectAI by telling us what this is.
              </Text>
            </View>
          </View>

          {/* Item name */}
          <View style={styles.fieldBlock}>
            <Text style={[styles.fieldLabel, { color: colors.text }]}>Item name</Text>
            <TextInput
              style={[styles.input, {
                backgroundColor: colors.background,
                borderColor: colors.border,
                color: colors.text,
              }]}
              value={itemName}
              onChangeText={setItemName}
              placeholder="What is this item?"
              placeholderTextColor={colors.muted}
              maxLength={500}
              autoFocus={!prefillName}
              returnKeyType="next"
              onSubmitEditing={() => {
                if (itemName.trim()) {
                  Keyboard.dismiss();
                  setCategoryPickerOpen(true);
                  setCategorySearch("");
                }
              }}
            />
          </View>

          {/* Category selection */}
          <View style={styles.fieldBlock}>
            <Text style={[styles.fieldLabel, { color: colors.text }]}>Category</Text>
            <TouchableOpacity
              activeOpacity={0.7}
              onPress={() => { Keyboard.dismiss(); setCategoryPickerOpen(true); setCategorySearch(""); }}
              style={[styles.dropdownTrigger, {
                borderColor: selectedCategory ? colors.accent : colors.border,
                backgroundColor: colors.background,
              }]}
            >
              <Text
                style={[styles.dropdownText, {
                  color: selectedCategory ? colors.text : colors.muted,
                }]}
                numberOfLines={1}
              >
                {selectedCategory
                  ? (CATEGORY_OPTIONS.find((c) => c.slug === selectedCategory)?.label ?? selectedCategory)
                  : "Select a category"}
              </Text>
              <Ionicons name="chevron-down" size={16} color={colors.muted} />
            </TouchableOpacity>
          </View>

          {/* Suggest new category */}
          {!selectedCategory && (
            <View style={styles.fieldBlock}>
              <Text style={[styles.fieldLabel, { color: colors.muted }]}>
                Or suggest a new category
              </Text>
              <TextInput
                style={[styles.input, {
                  backgroundColor: colors.background,
                  borderColor: colors.border,
                  color: colors.text,
                }]}
                value={newCategoryText}
                onChangeText={setNewCategoryText}
                placeholder="e.g. Board Games, Coins..."
                placeholderTextColor={colors.muted}
                maxLength={100}
              />
            </View>
          )}

          {/* Actions */}
          <View style={styles.actions}>
            <AnimatedPressable
              style={[styles.submitButton, {
                backgroundColor: colors.accent,
                opacity: !itemName.trim() || isSubmitting ? 0.5 : 1,
              }]}
              onPress={handleSubmit}
              disabled={!itemName.trim() || isSubmitting}
              accessibilityRole="button"
              accessibilityLabel="Submit suggestion"
            >
              {isSubmitting ? (
                <ActivityIndicator size="small" color={colors.card} />
              ) : (
                <Text style={[styles.submitButtonText, { color: colors.card }]}>Submit</Text>
              )}
            </AnimatedPressable>

            <AnimatedPressable
              style={styles.skipButton}
              onPress={handleSkip}
              accessibilityRole="button"
              accessibilityLabel="Skip"
            >
              <Text style={[styles.skipButtonText, { color: colors.muted }]}>Skip</Text>
            </AnimatedPressable>
          </View>
        </View>

        {/* Category Picker Modal */}
        <Modal
          visible={categoryPickerOpen}
          animationType="slide"
          transparent
          onRequestClose={() => setCategoryPickerOpen(false)}
        >
          <View style={styles.pickerOverlay}>
            <View style={[styles.pickerSheet, { backgroundColor: colors.card }]}>
              <View style={[styles.pickerHeader, { borderBottomColor: colors.border }]}>
                <Text style={[styles.pickerTitle, { color: colors.text }]}>Select Category</Text>
                <TouchableOpacity onPress={() => setCategoryPickerOpen(false)} hitSlop={12}>
                  <Ionicons name="close" size={22} color={colors.muted} />
                </TouchableOpacity>
              </View>
              <View style={[styles.searchWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                <Ionicons name="search-outline" size={16} color={colors.muted} style={{ marginRight: 8 }} />
                <TextInput
                  value={categorySearch}
                  onChangeText={setCategorySearch}
                  placeholder="Search categories..."
                  placeholderTextColor={colors.muted}
                  style={[styles.searchInput, { color: colors.text }]}
                  autoFocus
                />
              </View>
              <FlatList
                data={filteredCategories}
                keyExtractor={(item) => item.slug}
                keyboardShouldPersistTaps="handled"
                renderItem={({ item }) => (
                  <TouchableOpacity
                    activeOpacity={0.6}
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                      setSelectedCategory(item.slug);
                      setNewCategoryText("");
                      setCategoryPickerOpen(false);
                    }}
                    style={[styles.pickerRow, { borderBottomColor: colors.border }]}
                  >
                    <Text style={[styles.pickerRowText, {
                      color: selectedCategory === item.slug ? colors.accent : colors.text,
                    }]}>
                      {item.label}
                    </Text>
                    {selectedCategory === item.slug && (
                      <Ionicons name="checkmark" size={18} color={colors.accent} />
                    )}
                  </TouchableOpacity>
                )}
                ListEmptyComponent={
                  <View style={styles.emptyList}>
                    <Text style={[styles.emptyText, { color: colors.muted }]}>
                      No categories match "{categorySearch}"
                    </Text>
                  </View>
                }
              />
            </View>
          </View>
        </Modal>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: "flex-end",
  },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
  },
  sheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingBottom: Platform.OS === "ios" ? 40 : 24,
    maxHeight: "70%",
  },
  handleBar: {
    width: 40,
    height: 4,
    borderRadius: 2,
    alignSelf: "center",
    marginTop: 10,
    marginBottom: 16,
  },
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    marginBottom: 20,
  },
  headerText: {
    flex: 1,
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    lineHeight: 20,
  },
  fieldBlock: {
    marginBottom: 14,
  },
  fieldLabel: {
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 6,
  },
  input: {
    height: 48,
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 14,
    fontSize: 15,
  },
  dropdownTrigger: {
    height: 48,
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  dropdownText: {
    fontSize: 15,
    flex: 1,
  },
  actions: {
    marginTop: 8,
    gap: 10,
  },
  submitButton: {
    height: 48,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  submitButtonText: {
    fontSize: 16,
    fontWeight: "600",
  },
  skipButton: {
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  skipButtonText: {
    fontSize: 14,
  },
  // Category picker sub-modal
  pickerOverlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.3)",
  },
  pickerSheet: {
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: "60%",
  },
  pickerHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
  },
  pickerTitle: {
    fontSize: 17,
    fontWeight: "600",
  },
  searchWrap: {
    flexDirection: "row",
    alignItems: "center",
    margin: 12,
    paddingHorizontal: 12,
    height: 40,
    borderRadius: 8,
    borderWidth: 1,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
  },
  pickerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  pickerRowText: {
    fontSize: 15,
  },
  emptyList: {
    padding: 24,
    alignItems: "center",
  },
  emptyText: {
    fontSize: 14,
  },
});

export default React.memo(CatalogSuggestionModalInner);
