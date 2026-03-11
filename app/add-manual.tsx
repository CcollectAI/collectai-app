import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { track } from '@/analytics/track';
import React, { useState, useMemo, useCallback } from "react";
import {
  ScrollView,
  View,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Animated,
} from "react-native";
// TextInput, ActivityIndicator, TouchableOpacity, Keyboard, Ionicons moved to extracted components
import { useRouter, Stack } from "expo-router";
import { supabase } from "@/lib/supabase";
import { useAppTheme } from "@/hooks/useAppTheme";
import { useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useFormField, validateAll } from "@/hooks/useFormField";
import { compose, required, maxLength, numeric } from "@/lib/validate";
import logger from "@/utils/logger";
import CatalogSuggestionModal from "@/components/CatalogSuggestionModal";
import { usePhotoUpload } from "@/hooks/usePhotoUpload";
import { showActionSheet } from "@/hooks/useActionSheetPicker";
import { QuickNavBar } from '@/components/QuickNavBar';
import {
  PhotoUploadSection,
  CategorySpecificFields,
  ConditionValueSection,
  AdditionalDetailsSection,
  AddManualIntroCard,
  AddManualStatusBanner,
  AddManualBasicInfoSection,
  AddManualSubmitSection,
} from '@/components/add-manual';

type SaveState = "idle" | "saving" | "success" | "error";

import { CATEGORY_NAME_TO_SLUG } from '@/constants/categories';
import { getCategoryFields } from '@/constants/categoryFields';

const ManualAddScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();

  const { pickAndUpload, uploading: photoUploading, error: photoError, photoUrl, clearError: clearPhotoError } = usePhotoUpload("manual-draft");

  const currencySymbol = settings.currency === 'EUR' ? '€' : settings.currency === 'USD' ? '$' : settings.currency === 'GBP' ? '£' : settings.currency === 'JPY' ? '¥' : settings.currency === 'KRW' ? '₩' : settings.currency === 'AUD' ? 'A$' : settings.currency === 'CAD' ? 'C$' : settings.currency;

  const nameField = useFormField(compose(required("Item name"), maxLength("Item name", 255)));
  const [category, setCategory] = useState("");
  const [gameOrSeries, setGameOrSeries] = useState("");
  const [conditionGrade, setConditionGrade] = useState("");
  const purchasePriceField = useFormField(numeric("Purchase price"));
  const estimatedValueField = useFormField(numeric("Estimated value"));
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");
  const [categoryAttrs, setCategoryAttrs] = useState<Record<string, string | boolean>>({});
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [catalogModalVisible, setCatalogModalVisible] = useState(false);
  const [categoryPickerOpen, setCategoryPickerOpen] = useState(false);

  const categorySlug = useMemo(() => CATEGORY_NAME_TO_SLUG[category] ?? '', [category]);
  const categoryFields = useMemo(() => getCategoryFields(categorySlug), [categorySlug]);

  const canSubmit = nameField.value.trim().length > 0 && saveState !== "saving" && !photoUploading && !nameField.error && !purchasePriceField.error && !estimatedValueField.error;

  const handlePhotoUpload = async (src: "camera" | "gallery") => {
    clearPhotoError();
    await pickAndUpload(src);
  };

  const showPhotoSourcePicker = useCallback(() => {
    showActionSheet('Add Photo', ['Take Photo', 'Choose from Library'], (index) => {
      handlePhotoUpload(index === 0 ? 'camera' : 'gallery');
    });
  }, []);

  const handleCategorySelect = useCallback((label: string) => {
    if (label !== category) setCategoryAttrs({});
    setCategory(label);
  }, [category]);

  const handleCategoryClear = useCallback(() => {
    setCategory('');
    setCategoryAttrs({});
  }, []);

  const handleCategoryAttrChange = useCallback((key: string, value: string | boolean) => {
    setCategoryAttrs((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSubmit = async () => {
    if (!validateAll(nameField, purchasePriceField, estimatedValueField)) return;
    if (!canSubmit) return;

    if (!supabase || typeof supabase.from !== "function") {
      setSaveState("error");
      setErrorText("Supabase client not configured. Manual entries are in demo mode only.");
      fireHaptic(HapticIntent.ALERT_TRIGGERED);
      return;
    }

    setSaveState("saving");
    setErrorText(null);

    try {
      const purchase = purchasePriceField.value ? Number(purchasePriceField.value) : null;
      const estimated = estimatedValueField.value ? Number(estimatedValueField.value) : null;

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
        fireHaptic(HapticIntent.ALERT_TRIGGERED);
        return;
      }

      track({ name: 'item_added', properties: { source: 'manual', category: categorySlug || category } });
      fireHaptic(HapticIntent.JUDGMENT_LOCKED);
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
    } catch (err: any) {
      logger.warn("[ManualAdd] unexpected error:", err);
      setSaveState("error");
      setErrorText(err?.message || "Unexpected error while saving item.");
      fireHaptic(HapticIntent.ALERT_TRIGGERED);
    } finally {
      setTimeout(() => { setSaveState("idle"); }, 2000);
    }
  };

  const bannerContent = (() => {
    if (saveState === "saving") return { type: "info" as const, text: "Saving item…" };
    if (saveState === "success") return { type: "success" as const, text: "Item saved successfully!" };
    if (saveState === "error") return { type: "error" as const, text: errorText || "Something went wrong while saving." };
    return null;
  })();

  // getBannerColors moved to AddManualStatusBanner

  return (
    <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: 'Add Manually' }} />
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
            {/* Intro Card */}
            <AddManualIntroCard />

            <PhotoUploadSection
              photoUrl={photoUrl}
              photoUploading={photoUploading}
              photoError={photoError}
              onShowSourcePicker={showPhotoSourcePicker}
            />

            {/* Status banner */}
            {bannerContent && (
              <AddManualStatusBanner
                type={bannerContent.type}
                text={bannerContent.text}
                isSaving={saveState === "saving"}
              />
            )}

            {/* Section: Basic Info */}
            <AddManualBasicInfoSection
              nameField={nameField}
              category={category}
              gameOrSeries={gameOrSeries}
              onGameOrSeriesChange={setGameOrSeries}
              categoryPickerOpen={categoryPickerOpen}
              onOpenCategoryPicker={() => setCategoryPickerOpen(true)}
              onCloseCategoryPicker={() => setCategoryPickerOpen(false)}
              onSelectCategory={handleCategorySelect}
              onClearCategory={handleCategoryClear}
              onSuggestNew={() => setCatalogModalVisible(true)}
            />

            <CategorySpecificFields
              categoryLabel={category}
              fields={categoryFields}
              values={categoryAttrs}
              onChange={handleCategoryAttrChange}
            />

            <ConditionValueSection
              conditionGrade={conditionGrade}
              onConditionChange={setConditionGrade}
              purchasePriceField={purchasePriceField}
              estimatedValueField={estimatedValueField}
              currencySymbol={currencySymbol}
            />

            <AdditionalDetailsSection
              source={source}
              onSourceChange={setSource}
              notes={notes}
              onNotesChange={setNotes}
            />

            {/* Submit Button */}
            <AddManualSubmitSection
              canSubmit={canSubmit}
              isSaving={saveState === "saving"}
              onSubmit={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED); handleSubmit(); }}
            />

            <View style={{ height: 32 }} />
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>

      <CatalogSuggestionModal
        visible={catalogModalVisible}
        onDismiss={() => setCatalogModalVisible(false)}
        source="manual"
        prefillName={nameField.value}
        inputData={{ name: nameField.value, category: category || undefined }}
      />
      <QuickNavBar />
    </View>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  keyboardView: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 16, paddingTop: 16 },
  // introCard, introIconWrap, introText, introTitle, introSubtitle moved to AddManualIntroCard
  // banner, bannerIconBox, bannerText moved to AddManualStatusBanner
  // section, sectionHeader, sectionTitle, card, fieldBlock, fieldLabel, inputWrap, inputIcon, input, fieldError, dropdownTrigger, dropdownText moved to AddManualBasicInfoSection
  // submitButton, submitButtonText, footerHint, footerHintText moved to AddManualSubmitSection
});

export default function ManualAddScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Add Manual">
      <ManualAddScreen />
    </ScreenErrorBoundary>
  );
}
