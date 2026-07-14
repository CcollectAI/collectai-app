import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { track } from '@/analytics/track';
import React, { useState, useMemo, useCallback, useEffect } from "react";
import {
  ScrollView,
  View,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Animated,
  Alert,
  Pressable,
  Text,
} from "react-native";
// TextInput, ActivityIndicator, TouchableOpacity, Keyboard, Ionicons moved to extracted components
import { useRouter, Stack, useLocalSearchParams } from "expo-router";
import { supabase } from "@/lib/supabase";
import { useAppTheme } from "@/hooks/useAppTheme";
import { useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useTranslation } from "react-i18next";
import { useFormField, validateAll } from "@/hooks/useFormField";
import { compose, required, maxLength, numeric } from "@/lib/validate";
import logger from "@/utils/logger";
import CatalogSuggestionModal from "@/components/CatalogSuggestionModal";
import { matchCatalog, revalueItem } from "@/api/itemsApi";
import { checkDuplicate } from "@/lib/duplicateCheck";
import { dataProvider } from "@/data";
import { usePhotoUpload } from "@/hooks/usePhotoUpload";
import { showActionSheet } from "@/hooks/useActionSheetPicker";
import { QuickNavBar } from '@/components/QuickNavBar';
import { useToast } from '@/components/Toast';
import { useFormDraft, FormDraftState } from '@/hooks/useFormDraft';
import { useUnsavedChanges } from '@/hooks/useUnsavedChanges';
import {
  PhotoUploadSection,
  CategorySpecificFields,
  ConditionValueSection,
  AdditionalDetailsSection,
  AddManualStatusBanner,
  AddManualBasicInfoSection,
  AddManualSubmitSection,
} from '@/components/add-manual';

import { CATEGORY_NAME_TO_SLUG } from '@/constants/categories';
import { CUSTOM_CATEGORY_SENTINEL } from '@/components/add-manual/CategoryPickerModal';
import { getCategoryFields } from '@/constants/categoryFields';

type SaveState = "idle" | "saving" | "success" | "error";

const ManualAddScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { t } = useTranslation();

  const { pickAndUpload, uploadFromUri, uploading: photoUploading, error: photoError, photoUrl, clearError: clearPhotoError } = usePhotoUpload("manual-draft");

  // QuickScan hands off here when it can't identify an item (low confidence or
  // the scan timed out). It passes the snapped image + its best on-device
  // category guess so the user lands on a pre-filled form instead of a blank one.
  const {
    imageUri: handoffImageUri,
    category: handoffCategory,
    name: handoffName,
    condition: handoffCondition,
    attrs: handoffAttrs,
  } = useLocalSearchParams<{ imageUri?: string; category?: string; name?: string; condition?: string; attrs?: string }>();
  const handoffConsumedRef = React.useRef(false);

  const currencySymbol = settings.currency === 'EUR' ? '€' : settings.currency === 'USD' ? '$' : settings.currency === 'GBP' ? '£' : settings.currency === 'JPY' ? '¥' : settings.currency === 'KRW' ? '₩' : settings.currency === 'AUD' ? 'A$' : settings.currency === 'CAD' ? 'C$' : settings.currency;

  const nameField = useFormField(compose(required("Item name"), maxLength("Item name", 255)));
  const [category, setCategory] = useState("");
  const [customCategoryText, setCustomCategoryText] = useState("");
  const isCustomCategory = category === CUSTOM_CATEGORY_SENTINEL;
  const [gameOrSeries, setGameOrSeries] = useState("");
  const [conditionGrade, setConditionGrade] = useState("");
  const purchasePriceField = useFormField(numeric("Purchase price"));
  const estimatedValueField = useFormField(numeric("Estimated value"));
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [acquisitionDate, setAcquisitionDate] = useState("");
  const [customFields, setCustomFields] = useState<{key: string; value: string}[]>([]);
  const [categoryAttrs, setCategoryAttrs] = useState<Record<string, string | boolean>>({});
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [catalogModalVisible, setCatalogModalVisible] = useState(false);
  const [categoryPickerOpen, setCategoryPickerOpen] = useState(false);

  const { showToast } = useToast();

  // Consume the QuickScan handoff exactly once: pre-fill the fields the vision
  // pass already extracted (name / category / condition / attributes) and
  // upload the snapped image, so the user confirms instead of retyping.
  useEffect(() => {
    if (handoffConsumedRef.current) return;
    if (!handoffImageUri && !handoffCategory && !handoffName && !handoffCondition && !handoffAttrs) return;
    handoffConsumedRef.current = true;
    if (handoffCategory) setCategory(handoffCategory);
    if (handoffName) nameField.setValue(handoffName);
    if (handoffCondition) setConditionGrade(handoffCondition);
    if (handoffAttrs) {
      try {
        const parsed = JSON.parse(handoffAttrs);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          const next: Record<string, string | boolean> = {};
          for (const [k, v] of Object.entries(parsed)) {
            if (v === null || v === undefined) continue;
            next[k] = typeof v === 'boolean' ? v : String(v);
          }
          if (Object.keys(next).length > 0) setCategoryAttrs(next);
        }
      } catch {
        // Malformed handoff payload — ignore, user fills manually.
      }
    }
    if (handoffImageUri) { void uploadFromUri(handoffImageUri); }
  }, [handoffImageUri, handoffCategory, handoffName, handoffCondition, handoffAttrs, uploadFromUri]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- Draft auto-save ---
  const formState = useMemo<FormDraftState>(() => ({
    name: nameField.value,
    category,
    gameOrSeries,
    conditionGrade,
    purchasePrice: purchasePriceField.value,
    estimatedValue: estimatedValueField.value,
    source,
    notes,
    categoryAttrs,
  }), [nameField.value, category, gameOrSeries, conditionGrade, purchasePriceField.value, estimatedValueField.value, source, notes, categoryAttrs]);

  const handleRestoreDraft = useCallback((draft: FormDraftState) => {
    if (typeof draft.name === 'string' && draft.name) nameField.setValue(draft.name);
    if (typeof draft.category === 'string') setCategory(draft.category);
    if (typeof draft.gameOrSeries === 'string') setGameOrSeries(draft.gameOrSeries);
    if (typeof draft.conditionGrade === 'string') setConditionGrade(draft.conditionGrade);
    if (typeof draft.purchasePrice === 'string' && draft.purchasePrice) purchasePriceField.setValue(draft.purchasePrice);
    if (typeof draft.estimatedValue === 'string' && draft.estimatedValue) estimatedValueField.setValue(draft.estimatedValue);
    if (typeof draft.source === 'string') setSource(draft.source);
    if (typeof draft.notes === 'string') setNotes(draft.notes);
    if (typeof draft.categoryAttrs === 'object' && draft.categoryAttrs !== null && !Array.isArray(draft.categoryAttrs)) {
      setCategoryAttrs(draft.categoryAttrs as Record<string, string | boolean>);
    }
  }, [nameField, purchasePriceField, estimatedValueField]);

  const { hasDraft, draftRestored, clearDraft } = useFormDraft({
    draftKey: 'add-manual',
    formState,
    onRestore: handleRestoreDraft,
  });

  // Show toast when draft is restored
  useEffect(() => {
    if (draftRestored) {
      showToast({ message: 'Draft restored', type: 'info' });
    }
  }, [draftRestored]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDiscardDraft = useCallback(async () => {
    nameField.reset();
    setCategory('');
    setGameOrSeries('');
    setConditionGrade('');
    purchasePriceField.reset();
    estimatedValueField.reset();
    setSource('');
    setNotes('');
    setQuantity('1');
    setAcquisitionDate('');
    setCustomFields([]);
    setCategoryAttrs({});
    await clearDraft();
    showToast({ message: 'Draft discarded', type: 'info' });
  }, [nameField, purchasePriceField, estimatedValueField, clearDraft, showToast]);

  // --- Unsaved changes warning ---
  const isDirty = useMemo(() => {
    return nameField.value.length > 0 ||
      category.length > 0 ||
      gameOrSeries.length > 0 ||
      conditionGrade.length > 0 ||
      purchasePriceField.value.length > 0 ||
      estimatedValueField.value.length > 0 ||
      source.length > 0 ||
      notes.length > 0 ||
      Object.keys(categoryAttrs).length > 0;
  }, [nameField.value, category, gameOrSeries, conditionGrade, purchasePriceField.value, estimatedValueField.value, source, notes, categoryAttrs]);

  useUnsavedChanges({
    isDirty,
    onDiscard: () => { clearDraft(); },
  });

  // For custom categories, slugify the user's free-text input.
  // For known categories, use the standard slug lookup.
  const categorySlug = useMemo(() => {
    if (isCustomCategory && customCategoryText.trim()) {
      return customCategoryText.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 64);
    }
    return CATEGORY_NAME_TO_SLUG[category] ?? '';
  }, [category, isCustomCategory, customCategoryText]);
  const categoryFields = useMemo(() => getCategoryFields(categorySlug), [categorySlug]);

  // Catalog auto-fill: when the user has typed a title + chosen a category
  // and we get a strong (>=0.75) catalog match, populate empty
  // category-specific fields (brand / set_code / rarity / year-shaped keys)
  // from the matched catalog row. Never overrides what the user has already
  // typed — only fills genuinely-empty fields. Debounced 600ms so it doesn't
  // fire on every keystroke. Same /catalog/match endpoint used by the
  // canonical_key writer at handleSubmit.
  const [autoFilledFromCatalog, setAutoFilledFromCatalog] = useState<string | null>(null);
  useEffect(() => {
    const t = nameField.value.trim();
    const c = categorySlug || category.trim();
    if (!t || !c || t.length < 3) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const m = await matchCatalog(t, c);
        if (cancelled) return;
        const best = m.best;
        if (!best || (best.match_score ?? 0) < 0.75) return;
        // Merge into categoryAttrs only on keys we have AND that are empty.
        setCategoryAttrs((prev) => {
          const next = { ...prev };
          const fillKeys: Array<[string, string | null | undefined]> = [
            ['brand', best.brand],
            ['set_code', best.set_code],
            ['set_name', best.set_code],  // some categories label it set_name
            ['rarity', best.rarity],
          ];
          for (const [k, v] of fillKeys) {
            if (v && (!prev[k] || prev[k] === '')) {
              next[k] = v;
            }
          }
          return next;
        });
        if (best.title) setAutoFilledFromCatalog(best.title);
      } catch {
        // Best-effort enrichment — silent on failure.
      }
    }, 600);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [nameField.value, categorySlug, category]);

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

  const doSave = async () => {
    setSaveState("saving");
    setErrorText(null);

    try {
      const purchase = purchasePriceField.value ? Number(purchasePriceField.value) : null;
      const estimated = estimatedValueField.value ? Number(estimatedValueField.value) : null;

      const attrs: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(categoryAttrs)) {
        if (v !== '' && v !== false && v !== undefined) attrs[k] = v;
      }

      // R48 — write to `items` table (not the legacy `portfolio_items` which
      // has an incompatible schema on this DB). Column mapping matches the
      // actual items table: title (not name), attrs (not attributes_json),
      // purchase_price_eur (not purchase_price), image_url (not user_photo_url).
      // Merge category-specific attrs with user-defined custom fields
      const mergedAttrs: Record<string, unknown> = { ...attrs };
      for (const cf of customFields) {
        const k = cf.key.trim();
        const v = cf.value.trim();
        if (k && v) mergedAttrs[k] = v;
      }

      const qty = parseInt(quantity, 10);

      // Match against the catalog so this manually-added item gets a
      // canonical_key — the JOIN key that links it to price_predictions /
      // price_history / valuation pipelines. Without this, every Premium
      // feature (price_trend, item_history, dossier, market_prices) is dark
      // for manually-added items. Same writer story as QuickScan, just
      // happening at save-time instead of via a route param. Silent fallback
      // to canonical_key=null when no strong match — the item still saves,
      // Premium features just stay dark for it (matching today's behavior).
      // Threshold 0.6 mirrors orchestrator.py's "probable match" cutoff.
      let canonicalKey: string | null = null;
      const trimmedTitle = nameField.value.trim();
      const effectiveCat = categorySlug || category.trim();
      if (trimmedTitle && effectiveCat) {
        try {
          const m = await matchCatalog(trimmedTitle, effectiveCat);
          if (m.best && (m.best.match_score ?? 0) >= 0.6 && m.best.item_key) {
            canonicalKey = m.best.item_key;
          }
        } catch (e) {
          logger.warn("[ManualAdd] catalog match failed (saving without canonical_key):", e);
        }
      }

      const { data: inserted, error } = await supabase.from("items").insert([
        {
          user_id: (await supabase.auth.getUser()).data.user?.id ?? null,
          title: trimmedTitle,
          category: effectiveCat || null,
          canonical_key: canonicalKey,
          condition_grade: conditionGrade.trim() || null,
          condition: conditionGrade.trim() || null,
          purchase_price_eur: Number.isNaN(purchase as number) ? null : purchase,
          predicted_price_eur: Number.isNaN(estimated as number) ? null : estimated,
          purchase_currency: settings.currency,
          purchased_at: acquisitionDate.trim() || null,
          quantity: Number.isNaN(qty) || qty < 1 ? 1 : qty,
          source: 'manual',
          notes: notes.trim() || null,
          attrs: Object.keys(mergedAttrs).length > 0 ? mergedAttrs : null,
          image_url: photoUrl || null,
        },
      ]).select("id").single();

      if (error) {
        logger.warn("[ManualAdd] insert error:", error.message);
        setSaveState("error");
        setErrorText(error.message || "Couldn't save item — check your connection and try again.");
        fireHaptic(HapticIntent.ALERT_TRIGGERED);
        return;
      }

      // Market valuation for the card (best-effort). This insert is client-side
      // so the server can't value it inline like POST /items does; when the
      // item is catalog-matched (canonicalKey set) ask the server to write a
      // quick_predictions row so its card shows a value. Fire-and-forget.
      if (canonicalKey && inserted?.id) {
        revalueItem(inserted.id).catch(() => { /* non-critical */ });
      }

      track({ name: 'item_added', properties: { source: 'manual', category: categorySlug || category } });
      fireHaptic(HapticIntent.JUDGMENT_LOCKED);
      setSaveState("success");
      showToast({ message: 'Item added to your collection', type: 'success' });
      await clearDraft();
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
      setErrorText(err?.message || "Something unexpected happened — try saving again.");
      fireHaptic(HapticIntent.ALERT_TRIGGERED);
    } finally {
      setTimeout(() => { setSaveState("idle"); }, 2000);
    }
  };

  const handleSubmit = async () => {
    if (!validateAll(nameField, purchasePriceField, estimatedValueField)) return;
    if (!canSubmit) return;

    if (!supabase || typeof supabase.from !== "function") {
      setSaveState("error");
      setErrorText("Supabase client not configured. Manual entries are in demo mode only.");
      fireHaptic(HapticIntent.ALERT_TRIGGERED);
      return;
    }

    // Duplicate check before saving
    const effectiveCategory = categorySlug || category.trim() || null;
    const { isDuplicate, existingName } = await checkDuplicate(
      nameField.value,
      effectiveCategory,
      dataProvider,
    );

    if (isDuplicate) {
      fireHaptic(HapticIntent.ALERT_TRIGGERED);
      track({ name: 'duplicate_detected', properties: { category: effectiveCategory ?? undefined } });
      Alert.alert(
        'Similar Item Found',
        `You already own '${existingName}'. Add another copy?`,
        [
          {
            text: 'Cancel',
            style: 'cancel',
            onPress: () => {
              showToast({ message: 'Duplicate caught — avoided a wasted purchase', type: 'info' });
            },
          },
          { text: 'Add Anyway', onPress: () => doSave() },
        ],
      );
      return;
    }

    await doSave();
  };

  const bannerContent = (() => {
    if (saveState === "saving") return { type: "info" as const, text: "Saving item…" };
    if (saveState === "success") return { type: "success" as const, text: "Item saved successfully!" };
    if (saveState === "error") return { type: "error" as const, text: errorText || "Couldn't save item — try again." };
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
            {hasDraft && (
              <Pressable
                onPress={handleDiscardDraft}
                style={styles.discardDraftButton}
                accessibilityRole="button"
                accessibilityLabel={t('add_manual.discard_draft_a11y')}
              >
                <Text style={[styles.discardDraftText, { color: colors.error ?? '#E53935' }]}>
                  Discard Draft
                </Text>
              </Pressable>
            )}

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
              customCategoryText={customCategoryText}
              onCustomCategoryTextChange={setCustomCategoryText}
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
              quantity={quantity}
              onQuantityChange={setQuantity}
              acquisitionDate={acquisitionDate}
              onAcquisitionDateChange={setAcquisitionDate}
              showCustomFields={isCustomCategory}
              customFields={customFields}
              onCustomFieldsChange={setCustomFields}
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
  discardDraftButton: { alignSelf: 'flex-end', paddingVertical: 6, paddingHorizontal: 4, marginBottom: 4 },
  discardDraftText: { fontSize: 13, fontWeight: '600' },
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
