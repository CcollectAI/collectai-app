import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import React, { useState, useMemo } from "react";
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
  Keyboard,
  Image,
  ActionSheetIOS,
  Alert,
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
import CatalogSuggestionModal from "@/components/CatalogSuggestionModal";
import { usePhotoUpload } from "@/hooks/usePhotoUpload";

type SaveState = "idle" | "saving" | "success" | "error";

import { CATEGORIES as ALL_CATS, CATEGORY_NAME_TO_SLUG } from '@/constants/categories';
import { getCategoryFields, type CategoryField } from '@/constants/categoryFields';

const CATEGORY_OPTIONS = ALL_CATS.map((c) => ({
  label: c.name,
  slug: c.slug,
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

  // Photo upload
  const { pickAndUpload, uploading: photoUploading, error: photoError, photoUrl, clearError: clearPhotoError } = usePhotoUpload("manual-draft");

  // Currency symbol helper
  const currencySymbol = settings.currency === 'EUR' ? '€' : settings.currency === 'USD' ? '$' : settings.currency === 'GBP' ? '£' : settings.currency === 'JPY' ? '¥' : settings.currency === 'KRW' ? '₩' : settings.currency === 'AUD' ? 'A$' : settings.currency === 'CAD' ? 'C$' : settings.currency;

  const nameField = useFormField(compose(required("Item name"), maxLength("Item name", 255)));
  const [category, setCategory] = useState("");
  const [gameOrSeries, setGameOrSeries] = useState("");
  const [conditionGrade, setConditionGrade] = useState("");
  const purchasePriceField = useFormField(numeric("Purchase price"));
  const estimatedValueField = useFormField(numeric("Estimated value"));
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");

  // Category-specific attribute values (keyed by attribute key)
  const [categoryAttrs, setCategoryAttrs] = useState<Record<string, string | boolean>>({});

  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);

  // Catalog suggestion modal state
  const [catalogModalVisible, setCatalogModalVisible] = useState(false);

  const [categoryPickerOpen, setCategoryPickerOpen] = useState(false);
  const [categorySearch, setCategorySearch] = useState("");

  // Resolve current category slug + specific fields
  const categorySlug = useMemo(() => CATEGORY_NAME_TO_SLUG[category] ?? '', [category]);
  const categoryFields = useMemo(() => getCategoryFields(categorySlug), [categorySlug]);

  const canSubmit = nameField.value.trim().length > 0 && saveState !== "saving" && !photoUploading && !nameField.error && !purchasePriceField.error && !estimatedValueField.error;

  const handlePhotoUpload = async (source: "camera" | "gallery") => {
    clearPhotoError();
    await pickAndUpload(source);
  };

  const showPhotoSourcePicker = () => {
    if (Platform.OS === "ios") {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ["Cancel", "Take Photo", "Choose from Library"],
          cancelButtonIndex: 0,
          title: "Add Photo",
        },
        (buttonIndex) => {
          if (buttonIndex === 1) handlePhotoUpload("camera");
          if (buttonIndex === 2) handlePhotoUpload("gallery");
        },
      );
    } else {
      Alert.alert("Add Photo", "Choose a source", [
        { text: "Take Photo", onPress: () => handlePhotoUpload("camera") },
        { text: "Choose from Library", onPress: () => handlePhotoUpload("gallery") },
        { text: "Cancel", style: "cancel" },
      ]);
    }
  };

  const filteredCategories = useMemo(() => {
    const q = categorySearch.toLowerCase().trim();
    if (!q) return CATEGORY_OPTIONS;
    return CATEGORY_OPTIONS.filter((c) => c.label.toLowerCase().includes(q));
  }, [categorySearch]);

  const POPULAR_CATEGORIES = [
    'Pokemon TCG', 'Magic: The Gathering', 'Funko Pop', 'LEGO',
    'Sports Cards', 'Manga', 'Anime Figures', 'Yu-Gi-Oh!',
  ];

  // Condition dropdown state
  const [conditionPickerOpen, setConditionPickerOpen] = useState(false);
  const [customCondition, setCustomCondition] = useState('');

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

      // Build attributes_json from category-specific fields
      const attrs: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(categoryAttrs)) {
        if (v !== '' && v !== false && v !== undefined) attrs[k] = v;
      }

      const { error } = await supabase.from("portfolio_items").insert([
        {
          name: nameField.value.trim(),
          category: categorySlug || category.trim() || null,
          game_or_series: gameOrSeries.trim() || null,
          condition_grade: conditionGrade.trim() || null,
          purchase_price: Number.isNaN(purchase as number) ? null : purchase,
          estimated_value: Number.isNaN(estimated as number) ? null : estimated,
          currency: settings.currency,
          source: source.trim() || null,
          notes: notes.trim() || null,
          attributes_json: Object.keys(attrs).length > 0 ? attrs : null,
          user_photo_url: photoUrl || null,
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
      setCategoryAttrs({});
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

            {/* Photo Section */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="camera-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Photo (Optional)</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <View style={styles.photoContent}>
                  {photoUrl ? (
                    <Image source={{ uri: photoUrl }} style={styles.photoPreview} />
                  ) : (
                    <View style={[styles.photoPlaceholder, { borderColor: colors.border }]}>
                      <Ionicons name="camera-outline" size={32} color={colors.muted} />
                    </View>
                  )}

                  {photoUploading ? (
                    <View style={styles.photoUploadingRow}>
                      <ActivityIndicator size="small" color={colors.accent} />
                      <Text style={[styles.photoUploadingText, { color: colors.muted }]}>Uploading…</Text>
                    </View>
                  ) : (
                    <AnimatedPressable
                      onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); showPhotoSourcePicker(); }}
                      style={[styles.addPhotoBtn, { borderColor: colors.accent }]}
                      accessibilityRole="button"
                      accessibilityLabel={photoUrl ? "Change photo" : "Add photo"}
                    >
                      <Ionicons name={photoUrl ? "swap-horizontal-outline" : "camera-outline"} size={16} color={colors.accent} />
                      <Text style={[styles.addPhotoBtnText, { color: colors.accent }]}>{photoUrl ? "Change" : "Add Photo"}</Text>
                    </AnimatedPressable>
                  )}

                  {photoError && (
                    <Text style={styles.photoError}>{photoError}</Text>
                  )}
                </View>
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
                  {/* Quick-pick category chips */}
                  <View style={styles.categoryChipsRow}>
                    {POPULAR_CATEGORIES.map((cat) => {
                      const isActive = category === cat;
                      return (
                        <TouchableOpacity
                          key={cat}
                          activeOpacity={0.7}
                          onPress={() => {
                            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                            if (isActive) {
                              setCategory("");
                              setCategoryAttrs({});
                            } else {
                              if (cat !== category) setCategoryAttrs({});
                              setCategory(cat);
                            }
                          }}
                          style={[
                            styles.categoryChip,
                            { borderColor: isActive ? colors.accent : colors.border, backgroundColor: isActive ? colors.accent + '15' : colors.background },
                          ]}
                          accessibilityRole="button"
                          accessibilityLabel={`${cat}${isActive ? ', selected' : ''}`}
                          accessibilityState={{ selected: isActive }}
                        >
                          <Text style={[styles.categoryChipText, { color: isActive ? colors.accent : colors.text }]} numberOfLines={1}>
                            {cat}
                          </Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                  <TouchableOpacity
                    activeOpacity={0.7}
                    onPress={() => { Keyboard.dismiss(); fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setCategoryPickerOpen(true); setCategorySearch(""); }}
                    style={[styles.dropdownTrigger, { borderColor: category ? colors.accent : colors.border, backgroundColor: colors.background }]}
                    accessibilityRole="button"
                    accessibilityLabel={category ? `Category: ${category}` : "See All Categories"}
                  >
                    <Text style={[styles.dropdownText, { color: category ? colors.text : colors.muted }]} numberOfLines={1}>
                      {category || "See All Categories"}
                    </Text>
                    <Ionicons name="chevron-down" size={16} color={colors.muted} />
                  </TouchableOpacity>
                </View>

                {/* Category Picker Modal */}
                <Modal visible={categoryPickerOpen} animationType="slide" transparent onRequestClose={() => setCategoryPickerOpen(false)}>
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
                          accessibilityLabel="Search categories"
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
                        ListHeaderComponent={
                          category && !categorySearch ? (
                            <TouchableOpacity
                              activeOpacity={0.6}
                              onPress={() => {
                                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                                setCategory("");
                                setCategoryAttrs({});
                                setCategoryPickerOpen(false);
                              }}
                              style={[styles.modalRow, { borderBottomColor: colors.border }]}
                            >
                              <Ionicons name="close-circle-outline" size={18} color={colors.muted} style={{ marginRight: 12 }} />
                              <Text style={[styles.modalRowText, { color: colors.muted, fontStyle: 'italic' }]}>None (clear selection)</Text>
                            </TouchableOpacity>
                          ) : null
                        }
                        renderItem={({ item }) => {
                          const isSelected = category === item.label;
                          return (
                            <TouchableOpacity
                              activeOpacity={0.6}
                              onPress={() => {
                                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                                if (item.label !== category) setCategoryAttrs({});
                                setCategory(item.label);
                                setCategoryPickerOpen(false);
                              }}
                              style={[
                                styles.modalRow,
                                { borderBottomColor: colors.border },
                                isSelected && { backgroundColor: colors.accent + '12' },
                              ]}
                            >
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
                        ListFooterComponent={
                          <TouchableOpacity
                            activeOpacity={0.6}
                            onPress={() => {
                              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                              setCategoryPickerOpen(false);
                              setCatalogModalVisible(true);
                            }}
                            style={[styles.modalRow, { borderBottomColor: colors.border }]}
                          >
                            <Ionicons name="add-circle-outline" size={18} color={colors.accent} style={{ marginRight: 12 }} />
                            <Text style={[styles.modalRowText, { color: colors.accent, fontWeight: '600' }]}>
                              Suggest a new category
                            </Text>
                          </TouchableOpacity>
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

            {/* Category-Specific Details (dynamic based on selected category) */}
            {categoryFields.length > 0 && (
              <View style={styles.section}>
                <View style={styles.sectionHeader}>
                  <Ionicons name="options-outline" size={16} color={colors.accent} />
                  <Text style={[styles.sectionTitle, { color: colors.text }]}>
                    {category} Details
                  </Text>
                </View>

                <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                  {categoryFields.map((field: CategoryField) => {
                    const val = categoryAttrs[field.key];

                    // Boolean toggle field
                    if (field.type === 'boolean') {
                      return (
                        <TouchableOpacity
                          key={field.key}
                          activeOpacity={0.7}
                          onPress={() => {
                            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                            setCategoryAttrs((prev) => ({ ...prev, [field.key]: !prev[field.key] }));
                          }}
                          style={[styles.booleanRow, { borderBottomColor: colors.border }]}
                          accessibilityRole="switch"
                          accessibilityLabel={field.label}
                          accessibilityState={{ checked: !!val }}
                        >
                          <View style={styles.booleanLeft}>
                            <Ionicons
                              name={(field.icon ?? 'checkbox-outline') as keyof typeof Ionicons.glyphMap}
                              size={16}
                              color={val ? colors.accent : colors.muted}
                              style={{ marginRight: 8 }}
                            />
                            <Text style={[styles.fieldLabel, { color: colors.text, marginBottom: 0 }]}>{field.label}</Text>
                          </View>
                          <View style={[styles.toggleTrack, val ? { backgroundColor: colors.accent } : { backgroundColor: colors.border }]}>
                            <View style={[styles.toggleThumb, val ? styles.toggleThumbOn : undefined]} />
                          </View>
                        </TouchableOpacity>
                      );
                    }

                    // Select field (chips for few options, dropdown for many)
                    if (field.type === 'select' && field.options) {
                      return (
                        <View key={field.key} style={styles.fieldBlock}>
                          <Text style={[styles.fieldLabel, { color: colors.text }]}>{field.label}</Text>
                          <View style={styles.chipRow}>
                            {field.options.map((opt) => {
                              const isSelected = val === opt;
                              return (
                                <AnimatedPressable
                                  key={opt}
                                  style={[
                                    styles.selectChip,
                                    {
                                      backgroundColor: isSelected ? colors.accent + '20' : colors.background,
                                      borderColor: isSelected ? colors.accent : colors.border,
                                    },
                                  ]}
                                  onPress={() => {
                                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                                    setCategoryAttrs((prev) => ({
                                      ...prev,
                                      [field.key]: prev[field.key] === opt ? '' : opt,
                                    }));
                                  }}
                                  accessibilityRole="button"
                                  accessibilityLabel={`${field.label}: ${opt}`}
                                  accessibilityState={{ selected: isSelected }}
                                >
                                  <Text style={[styles.selectChipText, { color: isSelected ? colors.accent : colors.text }]}>
                                    {opt}
                                  </Text>
                                </AnimatedPressable>
                              );
                            })}
                          </View>
                        </View>
                      );
                    }

                    // Default: text input
                    return (
                      <View key={field.key} style={styles.fieldBlock}>
                        <Text style={[styles.fieldLabel, { color: colors.text }]}>{field.label}</Text>
                        <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                          <Ionicons
                            name={(field.icon ?? 'text-outline') as keyof typeof Ionicons.glyphMap}
                            size={16}
                            color={colors.muted}
                            style={styles.inputIcon}
                          />
                          <TextInput
                            value={typeof val === 'string' ? val : ''}
                            onChangeText={(text) => setCategoryAttrs((prev) => ({ ...prev, [field.key]: text }))}
                            placeholder={field.placeholder ?? ''}
                            placeholderTextColor={colors.muted}
                            style={[styles.input, { color: colors.text }]}
                            accessibilityLabel={field.label}
                          />
                        </View>
                      </View>
                    );
                  })}
                </View>
              </View>
            )}

            {/* Section: Condition & Value */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="diamond-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Condition & Value</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {/* Condition Dropdown */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Condition / Grade</Text>
                  <TouchableOpacity
                    activeOpacity={0.7}
                    onPress={() => { Keyboard.dismiss(); fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setConditionPickerOpen(true); }}
                    style={[styles.dropdownTrigger, { borderColor: conditionGrade ? colors.accent : colors.border, backgroundColor: colors.background }]}
                    accessibilityRole="button"
                    accessibilityLabel={conditionGrade ? `Condition: ${conditionGrade}` : "Select condition"}
                  >
                    <Text style={[styles.dropdownText, { color: conditionGrade ? colors.text : colors.muted }]} numberOfLines={1}>
                      {conditionGrade || "Select condition"}
                    </Text>
                    <Ionicons name="chevron-down" size={16} color={colors.muted} />
                  </TouchableOpacity>
                </View>

                {/* Condition Picker Modal */}
                <Modal visible={conditionPickerOpen} animationType="slide" transparent onRequestClose={() => setConditionPickerOpen(false)}>
                  <View style={styles.modalOverlay}>
                    <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
                      <View style={[styles.modalHeader, { borderBottomColor: colors.border }]}>
                        <Text style={[styles.modalTitle, { color: colors.text }]}>Select Condition</Text>
                        <TouchableOpacity onPress={() => setConditionPickerOpen(false)} hitSlop={12}>
                          <Ionicons name="close" size={22} color={colors.muted} />
                        </TouchableOpacity>
                      </View>
                      <FlatList
                        data={CONDITION_CHIPS}
                        keyExtractor={(item) => item.label}
                        keyboardShouldPersistTaps="handled"
                        style={styles.modalList}
                        ListHeaderComponent={
                          conditionGrade && !CONDITION_CHIPS.find(c => c.label === conditionGrade) ? null : (
                            conditionGrade ? (
                              <TouchableOpacity
                                activeOpacity={0.6}
                                onPress={() => {
                                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                                  setConditionGrade("");
                                  setConditionPickerOpen(false);
                                }}
                                style={[styles.modalRow, { borderBottomColor: colors.border }]}
                              >
                                <Text style={[styles.modalRowText, { color: colors.muted, fontStyle: 'italic' }]}>None (clear selection)</Text>
                              </TouchableOpacity>
                            ) : null
                          )
                        }
                        renderItem={({ item }) => {
                          const isSelected = conditionGrade === item.label;
                          return (
                            <TouchableOpacity
                              activeOpacity={0.6}
                              onPress={() => {
                                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                                setConditionGrade(item.label);
                                setCustomCondition('');
                                setConditionPickerOpen(false);
                              }}
                              style={[
                                styles.modalRow,
                                { borderBottomColor: colors.border },
                                isSelected && { backgroundColor: colors.accent + '12' },
                              ]}
                            >
                              <Text style={[styles.modalRowText, { color: isSelected ? colors.accent : colors.text }]}>
                                {item.label}
                              </Text>
                              {isSelected && (
                                <Ionicons name="checkmark" size={18} color={colors.accent} />
                              )}
                            </TouchableOpacity>
                          );
                        }}
                        ListFooterComponent={
                          <View style={{ paddingHorizontal: 20, paddingVertical: 14 }}>
                            <Text style={[styles.fieldLabel, { color: colors.muted }]}>Custom</Text>
                            <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                              <TextInput
                                value={customCondition}
                                onChangeText={setCustomCondition}
                                placeholder="Enter custom condition..."
                                placeholderTextColor={colors.muted}
                                style={[styles.input, { color: colors.text }]}
                                accessibilityLabel="Custom condition"
                                returnKeyType="done"
                                onSubmitEditing={() => {
                                  if (customCondition.trim()) {
                                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                                    setConditionGrade(customCondition.trim());
                                    setCustomCondition('');
                                    setConditionPickerOpen(false);
                                  }
                                }}
                              />
                            </View>
                          </View>
                        }
                      />
                    </View>
                  </View>
                </Modal>

                {/* Prices */}
                <View style={styles.fieldRow}>
                  <View style={[styles.fieldBlock, { flex: 1, marginRight: 8 }]}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Purchase Price</Text>
                    <View style={[styles.inputWrap, { borderColor: purchasePriceField.touched && purchasePriceField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                      <Text style={[styles.currencyPrefix, { color: colors.muted }]}>{currencySymbol}</Text>
                      <TextInput
                        value={purchasePriceField.value}
                        onChangeText={purchasePriceField.onChange}
                        onBlur={purchasePriceField.onBlur}
                        keyboardType="decimal-pad"
                        placeholder="0.00"
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                        accessibilityLabel="Purchase price"
                      />
                    </View>
                    {purchasePriceField.touched && purchasePriceField.error && (
                      <Text style={styles.fieldError}>{purchasePriceField.error}</Text>
                    )}
                  </View>
                  <View style={[styles.fieldBlock, { flex: 1 }]}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Estimated Value</Text>
                    <View style={[styles.inputWrap, { borderColor: estimatedValueField.touched && estimatedValueField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                      <Text style={[styles.currencyPrefix, { color: colors.muted }]}>{currencySymbol}</Text>
                      <TextInput
                        value={estimatedValueField.value}
                        onChangeText={estimatedValueField.onChange}
                        onBlur={estimatedValueField.onBlur}
                        keyboardType="decimal-pad"
                        placeholder="0.00"
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                        accessibilityLabel="Estimated value"
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
                    {notes.trim().length > 0 && (
                      <TouchableOpacity
                        onPress={() => Keyboard.dismiss()}
                        style={[styles.notesDoneBtn, { backgroundColor: colors.accent }]}
                        accessibilityRole="button"
                        accessibilityLabel="Done editing notes"
                      >
                        <Ionicons name="checkmark" size={18} color="#fff" />
                      </TouchableOpacity>
                    )}
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
              accessibilityState={{ disabled: !canSubmit }}
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

      {/* Catalog Learning Suggestion Modal */}
      <CatalogSuggestionModal
        visible={catalogModalVisible}
        onDismiss={() => setCatalogModalVisible(false)}
        source="manual"
        prefillName={nameField.value}
        inputData={{ name: nameField.value, category: category || undefined }}
      />
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
  notesDoneBtn: {
    position: 'absolute',
    bottom: 8,
    right: 8,
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
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
  // Photo section styles
  photoContent: {
    alignItems: 'center',
    paddingVertical: 4,
  },
  photoPreview: {
    width: 120,
    height: 120,
    borderRadius: 12,
    marginBottom: 12,
  },
  photoPlaceholder: {
    width: 120,
    height: 120,
    borderRadius: 12,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  addPhotoBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
  },
  addPhotoBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
  photoUploadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  photoUploadingText: {
    fontSize: 13,
  },
  photoError: {
    fontSize: 12,
    color: '#EF4444',
    marginTop: 8,
    textAlign: 'center',
  },
  // Category-specific field styles
  booleanRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  booleanLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  toggleTrack: {
    width: 44,
    height: 24,
    borderRadius: 12,
    justifyContent: 'center',
    paddingHorizontal: 2,
  },
  toggleThumb: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#FFFFFF',
  },
  toggleThumbOn: {
    alignSelf: 'flex-end',
  },
  selectChip: {
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 8,
    borderWidth: 1,
  },
  selectChipText: {
    fontSize: 12,
    fontWeight: '500',
  },
  categoryChipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 10,
  },
  categoryChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  categoryChipText: {
    fontSize: 13,
    fontWeight: '500',
  },
});

export default function ManualAddScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Add Manual">
      <ManualAddScreen />
    </ScreenErrorBoundary>
  );
}
