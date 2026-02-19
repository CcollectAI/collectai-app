import React, { useState, useMemo, useRef } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  TextInput,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Animated,
  Modal,
  FlatList,
  TouchableOpacity,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useFormField, validateAll } from "@/hooks/useFormField";
import { compose, required, maxLength, numeric } from "@/lib/validate";
import logger from "@/utils/logger";

type SaveState = "idle" | "saving" | "success" | "error";

import { CATEGORIES as ALL_CATS } from '@/constants/categories';

const ICON_MAP: Record<string, string> = {
  pokemon: 'flash-outline', mtg: 'sparkles-outline', yugioh: 'layers-outline',
  lorcana: 'star-outline', funko: 'cube-outline', lego: 'grid-outline',
  warhammer: 'skull-outline', gunpla: 'rocket-outline', retro_games: 'game-controller-outline',
  manga: 'book-outline', sportscards: 'football-outline', designer_toys: 'color-palette-outline',
  anime_figures: 'person-outline', hot_toys: 'flame-outline', diecast: 'car-outline',
  kpop_merch: 'musical-notes-outline', taylor_swift: 'musical-note-outline',
  disney: 'heart-outline', keycaps: 'keypad-outline', one_piece: 'boat-outline',
};

const CATEGORY_OPTIONS = ALL_CATS.map((c) => ({
  label: c.name,
  slug: c.slug,
  icon: ICON_MAP[c.slug] ?? 'pricetag-outline',
}));

// Common condition grades for quick selection
const CONDITION_CHIPS = [
  { label: "Mint", short: "M" },
  { label: "Near Mint", short: "NM" },
  { label: "Excellent", short: "EX" },
  { label: "Good", short: "G" },
  { label: "PSA 10", short: "10" },
  { label: "PSA 9", short: "9" },
  { label: "Raw", short: "Raw" },
];

const ManualAddScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();

  const nameField = useFormField(compose(required("Item name"), maxLength("Item name", 255)));
  const [category, setCategory] = useState("");
  const [gameOrSeries, setGameOrSeries] = useState("");
  const [conditionGrade, setConditionGrade] = useState("");
  const purchasePriceField = useFormField(numeric("Purchase price"));
  const estimatedValueField = useFormField(numeric("Estimated value"));
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");

  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);

  const [categoryPickerOpen, setCategoryPickerOpen] = useState(false);
  const [categorySearch, setCategorySearch] = useState("");

  const canSubmit = nameField.value.trim().length > 0 && saveState !== "saving" && !nameField.error && !purchasePriceField.error && !estimatedValueField.error;

  const filteredCategories = useMemo(() => {
    const q = categorySearch.toLowerCase().trim();
    if (!q) return CATEGORY_OPTIONS;
    return CATEGORY_OPTIONS.filter((c) => c.label.toLowerCase().includes(q));
  }, [categorySearch]);

  const selectedCategoryIcon = useMemo(() => {
    const match = CATEGORY_OPTIONS.find((c) => c.label === category);
    return match?.icon ?? 'pricetag-outline';
  }, [category]);

  const handleSubmit = async () => {
    if (!validateAll(nameField, purchasePriceField, estimatedValueField)) return;
    if (!canSubmit) return;

    if (!supabase || typeof supabase.from !== "function") {
      setSaveState("error");
      setErrorText(
        "Supabase client not configured. Manual entries are in demo mode only."
      );
      return;
    }

    setSaveState("saving");
    setErrorText(null);

    try {
      const purchase = purchasePriceField.value ? Number(purchasePriceField.value) : null;
      const estimated = estimatedValueField.value ? Number(estimatedValueField.value) : null;

      const { error } = await supabase.from("portfolio_items").insert([
        {
          name: nameField.value.trim(),
          category: category.trim() || null,
          game_or_series: gameOrSeries.trim() || null,
          condition_grade: conditionGrade.trim() || null,
          purchase_price: Number.isNaN(purchase as number) ? null : purchase,
          estimated_value: Number.isNaN(estimated as number) ? null : estimated,
          currency: "EUR",
          source: source.trim() || null,
          notes: notes.trim() || null,
        },
      ]);

      if (error) {
        logger.warn("[ManualAdd] insert error:", error.message);
        setSaveState("error");
        setErrorText(error.message || "Failed to save item.");
        return;
      }

      setSaveState("success");
      nameField.reset();
      setCategory("");
      setGameOrSeries("");
      setConditionGrade("");
      purchasePriceField.reset();
      estimatedValueField.reset();
      setSource("");
      setNotes("");
    } catch (err: unknown) {
      logger.warn("[ManualAdd] unexpected error:", err);
      setSaveState("error");
      setErrorText(err?.message || "Unexpected error while saving item.");
    } finally {
      setTimeout(() => {
        setSaveState("idle");
      }, 2000);
    }
  };

  const bannerContent = (() => {
    if (saveState === "saving")
      return { type: "info" as const, text: "Saving item…" };
    if (saveState === "success")
      return {
        type: "success" as const,
        text: "Item saved successfully!",
      };
    if (saveState === "error")
      return {
        type: "error" as const,
        text: errorText || "Something went wrong while saving.",
      };
    return null;
  })();

  const getBannerColors = (type: string) => {
    if (type === "error") {
      return { bg: "#FEF2F2", border: "#EF4444", icon: "warning-outline" as const, iconColor: "#EF4444" };
    }
    if (type === "success") {
      return { bg: colors.accent + "15", border: colors.accent, icon: "checkmark-circle-outline" as const, iconColor: colors.accent };
    }
    return { bg: "#FEF3C7", border: "#F59E0B", icon: "time-outline" as const, iconColor: "#F59E0B" };
  };

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 0}
      >
        {/* Header */}
        <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
          <AnimatedPressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); router.back(); }} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Add Manually</Text>
          <View style={{ width: 32 }} />
        </View>

        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
            {/* Intro Card */}
            <View style={[styles.introCard, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '30' }]}>
              <View style={[styles.introIconWrap, { backgroundColor: colors.accent + '20' }]}>
                <Ionicons name="create-outline" size={20} color={colors.accent} />
              </View>
              <View style={styles.introText}>
                <Text style={[styles.introTitle, { color: colors.text }]}>Manual Entry</Text>
                <Text style={[styles.introSubtitle, { color: colors.muted }]}>
                  Enter item details yourself for full control
                </Text>
              </View>
            </View>

            {/* Status banner */}
            {bannerContent && (
              <View
                style={[
                  styles.banner,
                  {
                    backgroundColor: getBannerColors(bannerContent.type).bg,
                    borderColor: getBannerColors(bannerContent.type).border,
                  },
                ]}
              >
                <View style={styles.bannerIconBox}>
                  {saveState === "saving" ? (
                    <ActivityIndicator size="small" color={colors.accent} />
                  ) : (
                    <Ionicons
                      name={getBannerColors(bannerContent.type).icon}
                      size={18}
                      color={getBannerColors(bannerContent.type).iconColor}
                    />
                  )}
                </View>
                <Text style={[styles.bannerText, { color: colors.text }]}>
                  {bannerContent.text}
                </Text>
              </View>
            )}

            {/* Section: Basic Info */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="information-circle-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Basic Information</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {/* Name */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>
                    Item name <Text style={{ color: colors.accent }}>*</Text>
                  </Text>
                  <View style={[styles.inputWrap, { borderColor: nameField.touched && nameField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="text-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={nameField.value}
                      onChangeText={nameField.onChange}
                      onBlur={nameField.onBlur}
                      placeholder="e.g. Charizard GX (Alt Art)"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      accessibilityLabel="Item name"
                    />
                  </View>
                  {nameField.touched && nameField.error && (
                    <Text style={styles.fieldError}>{nameField.error}</Text>
                  )}
                </View>

                {/* Category Dropdown */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Category</Text>
                  <TouchableOpacity
                    activeOpacity={0.7}
                    onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setCategoryPickerOpen(true); setCategorySearch(""); }}
                    style={[styles.dropdownTrigger, { borderColor: category ? colors.accent : colors.border, backgroundColor: colors.background }]}
                    accessibilityRole="button"
                    accessibilityLabel={category ? `Category: ${category}` : "Select a category"}
                  >
                    <Ionicons
                      name={(category ? selectedCategoryIcon : 'pricetag-outline') as keyof typeof Ionicons.glyphMap}
                      size={16}
                      color={category ? colors.accent : colors.muted}
                      style={styles.inputIcon}
                    />
                    <Text style={[styles.dropdownText, { color: category ? colors.text : colors.muted }]} numberOfLines={1}>
                      {category || "Select a category"}
                    </Text>
                    <Ionicons name="chevron-down" size={16} color={colors.muted} />
                  </TouchableOpacity>
                </View>

                {/* Category Picker Modal */}
                <Modal visible={categoryPickerOpen} animationType="slide" transparent>
                  <View style={styles.modalOverlay}>
                    <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
                      <View style={[styles.modalHeader, { borderBottomColor: colors.border }]}>
                        <Text style={[styles.modalTitle, { color: colors.text }]}>Select Category</Text>
                        <TouchableOpacity onPress={() => setCategoryPickerOpen(false)} hitSlop={12}>
                          <Ionicons name="close" size={22} color={colors.muted} />
                        </TouchableOpacity>
                      </View>
                      <View style={[styles.modalSearchWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                        <Ionicons name="search-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                        <TextInput
                          value={categorySearch}
                          onChangeText={setCategorySearch}
                          placeholder="Search categories..."
                          placeholderTextColor={colors.muted}
                          style={[styles.input, { color: colors.text }]}
                          autoFocus
                        />
                        {categorySearch.length > 0 && (
                          <TouchableOpacity onPress={() => setCategorySearch("")} hitSlop={8}>
                            <Ionicons name="close-circle" size={16} color={colors.muted} />
                          </TouchableOpacity>
                        )}
                      </View>
                      <FlatList
                        data={filteredCategories}
                        keyExtractor={(item) => item.slug}
                        keyboardShouldPersistTaps="handled"
                        style={styles.modalList}
                        renderItem={({ item }) => {
                          const isSelected = category === item.label;
                          return (
                            <TouchableOpacity
                              activeOpacity={0.6}
                              onPress={() => {
                                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                                setCategory(item.label);
                                setCategoryPickerOpen(false);
                              }}
                              style={[
                                styles.modalRow,
                                { borderBottomColor: colors.border },
                                isSelected && { backgroundColor: colors.accent + '12' },
                              ]}
                            >
                              <Ionicons
                                name={item.icon as keyof typeof Ionicons.glyphMap}
                                size={18}
                                color={isSelected ? colors.accent : colors.muted}
                                style={{ marginRight: 12 }}
                              />
                              <Text style={[styles.modalRowText, { color: isSelected ? colors.accent : colors.text }]}>
                                {item.label}
                              </Text>
                              {isSelected && (
                                <Ionicons name="checkmark" size={18} color={colors.accent} />
                              )}
                            </TouchableOpacity>
                          );
                        }}
                        ListEmptyComponent={
                          <View style={styles.modalEmpty}>
                            <Text style={[styles.modalEmptyText, { color: colors.muted }]}>No categories match "{categorySearch}"</Text>
                          </View>
                        }
                      />
                    </View>
                  </View>
                </Modal>

                {/* Game / Series */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Set / Series</Text>
                  <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="albums-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={gameOrSeries}
                      onChangeText={setGameOrSeries}
                      placeholder="e.g. Scarlet & Violet, Master Grade"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      accessibilityLabel="Set or series"
                    />
                  </View>
                </View>
              </View>
            </View>

            {/* Section: Condition & Value */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="diamond-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Condition & Value</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {/* Condition */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Condition / Grade</Text>
                  <View style={styles.chipRow}>
                    {CONDITION_CHIPS.map((chip) => {
                      const isSelected = conditionGrade === chip.label;
                      return (
                        <AnimatedPressable
                          key={chip.label}
                          style={[
                            styles.conditionChip,
                            {
                              backgroundColor: isSelected ? colors.accent + '20' : colors.background,
                              borderColor: isSelected ? colors.accent : colors.border,
                            },
                          ]}
                          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setConditionGrade(chip.label); }}
                          accessibilityRole="button"
                          accessibilityLabel={`${chip.label} condition${isSelected ? ', selected' : ''}`}
                        >
                          <Text
                            style={[
                              styles.conditionChipText,
                              { color: isSelected ? colors.accent : colors.text },
                            ]}
                          >
                            {chip.short}
                          </Text>
                        </AnimatedPressable>
                      );
                    })}
                  </View>
                  {conditionGrade && !CONDITION_CHIPS.find(c => c.label === conditionGrade) && (
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background, marginTop: 8 }]}>
                      <Ionicons name="ribbon-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                      <TextInput
                        value={conditionGrade}
                        onChangeText={setConditionGrade}
                        placeholder="Custom condition"
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                      />
                    </View>
                  )}
                </View>

                {/* Prices */}
                <View style={styles.fieldRow}>
                  <View style={[styles.fieldBlock, { flex: 1, marginRight: 8 }]}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Purchase Price</Text>
                    <View style={[styles.inputWrap, { borderColor: purchasePriceField.touched && purchasePriceField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                      <Text style={[styles.currencyPrefix, { color: colors.muted }]}>€</Text>
                      <TextInput
                        value={purchasePriceField.value}
                        onChangeText={purchasePriceField.onChange}
                        onBlur={purchasePriceField.onBlur}
                        keyboardType="decimal-pad"
                        placeholder="0.00"
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                        accessibilityLabel="Purchase price in euros"
                      />
                    </View>
                    {purchasePriceField.touched && purchasePriceField.error && (
                      <Text style={styles.fieldError}>{purchasePriceField.error}</Text>
                    )}
                  </View>
                  <View style={[styles.fieldBlock, { flex: 1 }]}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Estimated Value</Text>
                    <View style={[styles.inputWrap, { borderColor: estimatedValueField.touched && estimatedValueField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                      <Text style={[styles.currencyPrefix, { color: colors.muted }]}>€</Text>
                      <TextInput
                        value={estimatedValueField.value}
                        onChangeText={estimatedValueField.onChange}
                        onBlur={estimatedValueField.onBlur}
                        keyboardType="decimal-pad"
                        placeholder="0.00"
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                        accessibilityLabel="Estimated value in euros"
                      />
                    </View>
                    {estimatedValueField.touched && estimatedValueField.error && (
                      <Text style={styles.fieldError}>{estimatedValueField.error}</Text>
                    )}
                  </View>
                </View>
              </View>
            </View>

            {/* Section: Additional Details */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="document-text-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Additional Details</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {/* Source */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Source</Text>
                  <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="storefront-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={source}
                      onChangeText={setSource}
                      placeholder="Twitch stream, local shop, Cardmarket…"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      accessibilityLabel="Source where item was purchased"
                    />
                  </View>
                </View>

                {/* Notes */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Notes</Text>
                  <View style={[styles.inputWrapMultiline, { borderColor: colors.border, backgroundColor: colors.background }]}>
                    <TextInput
                      value={notes}
                      onChangeText={setNotes}
                      multiline
                      numberOfLines={3}
                      placeholder="Print line, story, plans, etc."
                      placeholderTextColor={colors.muted}
                      style={[styles.inputMultiline, { color: colors.text }]}
                      textAlignVertical="top"
                      accessibilityLabel="Notes"
                    />
                  </View>
                </View>
              </View>
            </View>

            {/* Submit Button */}
            <AnimatedPressable
              onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED); handleSubmit(); }}
              disabled={!canSubmit}
              style={[
                styles.submitButton,
                {
                  backgroundColor: canSubmit ? colors.accent : colors.border,
                },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Save to collection"
            >
              {saveState === "saving" ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <Ionicons name="checkmark-circle-outline" size={20} color="#FFFFFF" />
                  <Text style={styles.submitButtonText}>Save to Collection</Text>
                </>
              )}
            </AnimatedPressable>

            {/* Footer hint */}
            <View style={styles.footerHint}>
              <Ionicons name="bulb-outline" size={14} color={colors.muted} />
              <Text style={[styles.footerHintText, { color: colors.muted }]}>
                Tip: Use QuickScan for faster entry with AI assistance
              </Text>
            </View>

            <View style={{ height: 32 }} />
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: "600",
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  introCard: {
    flexDirection: "row",
    alignItems: "center",
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 20,
  },
  introIconWrap: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  introText: {
    flex: 1,
  },
  introTitle: {
    fontSize: 15,
    fontWeight: "600",
    marginBottom: 2,
  },
  introSubtitle: {
    fontSize: 13,
  },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 16,
  },
  bannerIconBox: {
    width: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 10,
  },
  bannerText: {
    fontSize: 13,
    flex: 1,
    fontWeight: "500",
  },
  section: {
    marginBottom: 20,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
  },
  fieldBlock: {
    marginBottom: 14,
  },
  fieldRow: {
    flexDirection: "row",
  },
  fieldLabel: {
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
  },
  inputWrap: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 44,
  },
  inputWrapMultiline: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    minHeight: 88,
  },
  inputIcon: {
    marginRight: 8,
  },
  currencyPrefix: {
    fontSize: 14,
    fontWeight: "600",
    marginRight: 4,
  },
  input: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 0,
  },
  inputMultiline: {
    flex: 1,
    fontSize: 14,
    minHeight: 64,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  dropdownTrigger: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 44,
  },
  dropdownText: {
    flex: 1,
    fontSize: 14,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  modalSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "70%",
    paddingBottom: Platform.OS === "ios" ? 34 : 16,
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: "600",
  },
  modalSearchWrap: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 40,
    marginHorizontal: 16,
    marginVertical: 12,
  },
  modalList: {
    flexGrow: 0,
  },
  modalRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  modalRowText: {
    flex: 1,
    fontSize: 15,
    fontWeight: "500",
  },
  modalEmpty: {
    paddingVertical: 32,
    alignItems: "center",
  },
  modalEmptyText: {
    fontSize: 14,
  },
  conditionChip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    minWidth: 44,
    alignItems: 'center',
  },
  conditionChipText: {
    fontSize: 12,
    fontWeight: "600",
  },
  submitButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 4,
  },
  submitButtonText: {
    fontSize: 15,
    fontWeight: "600",
    color: "#FFFFFF",
  },
  footerHint: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: 16,
  },
  footerHintText: {
    fontSize: 12,
  },
  fieldError: {
    fontSize: 12,
    color: '#EF4444',
    marginTop: 4,
    marginLeft: 4,
  },
});

export default ManualAddScreen;
