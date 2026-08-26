import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { router , useLocalSearchParams, Redirect } from 'expo-router';
import { isUuid } from '@/lib/ids';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  Pressable,
  Share,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Animated,
  RefreshControl,
  useWindowDimensions,
} from "react-native";
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from "@/hooks/useAppTheme";
import { showActionSheet } from "@/hooks/useActionSheetPicker";
import { useItemGallery } from "@/hooks/useItemGallery";
import { useItemGrading } from "@/hooks/useItemGrading";
import { useItemPriceTrend } from "@/hooks/useItemPriceTrend";
import { useItemProgress } from "@/hooks/useItemProgress";
import { useItemMarketplace } from "@/hooks/useItemMarketplace";
import { useItemDetail } from "@/hooks/useItemDetail";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useTranslation } from "react-i18next";
import { useToast } from "@/components/Toast";
import { dataProvider } from "@/data";
import { fetchItemValueById } from "@/data/providers/itemsProvider";
import { ImageZoomModal } from "@/components/ImageZoomModal";
import { PriceExplanationSheet } from "@/components/PriceExplanationSheet";
import {
  PriceEstimate,
  PriceExplanation,
  getConfidenceTier,
  DEFAULT_DISCLAIMER,
} from "@/types/priceExplanation";
import { featureFlags, LIVE_PRICE_FETCH_ENABLED } from "@/config/featureFlags";
import { radius, text, fontWeight, gap, shadow } from "@/theme/tokens";
import { collectorsApi } from "@/api/collectorsApi";
import { enrichOnDemand } from "@/api/marketplaceApi";
import logger from "@/utils/logger";
import { formatPrice, getCurrencySymbol, isUnpriced, UNPRICED_LABEL } from "@/lib/format";
import { ValueSourceChip } from "@/components/ValueSourceChip";
import type { CurrencyCode } from "@/data/types";
import { AnimatedPressable } from "@/motion";
import { isBuildableCategory } from "@/constants/buildStepTemplates";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { ConfettiBurst, ConfettiBurstRef } from '@/components/ConfettiBurst';
import { ListForSaleModal } from '@/components/ListForSaleModal';
import { useListForSale } from '@/hooks/useListForSale';
import { ItemProgressSection } from '@/components/ItemProgressSection';
import { GradingSection } from '@/components/GradingSection';
import type { GradingLookupResult, PopulationReport, GradingServiceInfo } from '@/components/GradingSection';
import { ItemGallerySection } from '@/components/ItemGallerySection';
import type { ItemImage } from '@/components/ItemGallerySection';
import { PriceFeedbackSection, PriceCorrectionRow } from '@/components/PriceFeedbackSection';
import { DossierReportSection } from '@/components/DossierReportSection';
import type { DossierData } from '@/components/DossierReportSection';
import { MarketplacePricesSection } from '@/components/MarketplacePricesSection';
import type { MarketHit } from '@/components/MarketplacePricesSection';
import { BuildProjectSection } from '@/components/BuildProjectSection';
// ProvenanceHistorySection ("Item History") removed 2026-07-22 — it duplicated the
// dossier's provenance[] and was empty for virtually every item. See render block.
// import { ProvenanceHistorySection } from '@/components/ProvenanceHistorySection';
import { track } from '@/analytics/track';
import { useBillingLimits } from '@/hooks/useBillingLimits';
import { LockedPreviewSection } from '@/components/LockedPreviewSection';
import { ItemDetailsCard } from '@/components/item/ItemDetailsCard';
import { MarketCompPrompt, shouldOfferComp } from '@/components/item/MarketCompPrompt';
import { ItemQuickActionsRow } from '@/components/item/ItemQuickActionsRow';
import { ItemShopSection } from '@/components/item/ItemShopSection';
import { ItemRefreshBar } from '@/components/item/ItemRefreshBar';
import { ItemDraftActions } from '@/components/item/ItemDraftActions';
import { ItemForSaleBar } from '@/components/item/ItemForSaleBar';
import { ItemEditBar } from '@/components/item/ItemEditBar';
import { ItemPriceSection } from '@/components/item/ItemPriceSection';
import { ItemNotesEditor } from '@/components/item/ItemNotesEditor';
import { ItemCatalogRefresh } from '@/components/item/ItemCatalogRefresh';
import { supabase } from '@/lib/supabase';
// SellTimingBadge hidden 2026-07-22 (see render block below) — restore both together.
// import { SellTimingBadge } from '@/components/SellTimingBadge';
// Pull from single source of truth — all 36 categories
import { CATEGORIES as ALL_CATS, CATEGORY_NAME_TO_SLUG, GRADING_ELIGIBLE_CATEGORIES, VALUATION_ELIGIBLE_CATEGORIES } from '@/constants/categories';
// DossierData and MarketHit types imported from extracted components

// Price trend data shape
interface PriceTrendData {
  data_points: { date: string; q50: number; q10: number; q90: number }[];
  direction: 'up' | 'down' | 'flat';
  pct_change: number;
  current_q50: number;
  period_days: number;
}

// Sneaker/watch sizes moved to CategorySpecificSection component

// Helper: parse string|number to number for formatPrice
const toNum = (value: string | number | undefined | null): number | undefined => {
  if (value === undefined || value === null || value === '') return undefined;
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return undefined;
  return num;
};



// Gap left between the bottom of the notes block and the top of the keyboard.
const NOTES_KEYBOARD_MARGIN = 16;

// Predefined options for dropdown menus
const COLLECTION_OPTIONS =['Not set', 'Base Set', 'Jungle', 'Fossil', 'Team Rocket', 'Gym Heroes', 'Neo Genesis', 'Other'];
const CONDITION_OPTIONS_GENERAL = ['Not set', 'Mint', 'Near Mint', 'Excellent', 'Good', 'Fair', 'Poor'];
const CONDITION_OPTIONS_GRADED = ['Not set', 'PSA 10', 'PSA 9', 'PSA 8', 'PSA 7', 'BGS 10', 'BGS 9.5', 'CGC 9.8', 'CGC 9.6', 'Raw', 'Mint', 'Near Mint', 'Excellent', 'Good', 'Fair', 'Poor'];

const CATEGORY_OPTIONS = [...ALL_CATS.map((c) => c.name), 'Other'];
const CATEGORY_ID_MAP: Record<string, string> = {
  ...CATEGORY_NAME_TO_SLUG,
  'Other': 'unknown',
};

function ItemDetailScreen() {
  const { colors: theme } = useAppTheme();
  const { settings } = useSettings();
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { limits } = useBillingLimits();
  const params = useLocalSearchParams<{
    id?: string;
    draft?: string;
    name?: string;
    category?: string;
    collection?: string;
    condition?: string;
    value?: string;
    notes?: string;
    imageUri?: string;
    q10?: string;
    q50?: string;
    q90?: string;
    confidence?: string;
    explanation?: string;
    attributesJson?: string;
    // Catalog match key from QuickScan (passed via app/quickscan.tsx as
    // `catalogKey`). Forwarded to persistQuickscanDraft so the new item
    // gets its items.canonical_key populated for downstream JOINs.
    catalogKey?: string;
  }>();

  const {
    id,
    draft,
    // NOTE: these destructuring defaults fire ONLY on `undefined`. A route
    // param that arrives as an EMPTY STRING keeps the empty string, which is
    // why the Condition row rendered a label with nothing beside it while
    // Collection — set from a picker that writes the literal "Not set" —
    // looked fine one row above. Normalised below rather than here, because a
    // default cannot express "or blank".
    name: rawName = "Unknown item",
    category: rawCategory = "Not set",
    collection: rawCollection = "Not set",
    condition: rawCondition = "Not set",
    value = "0",
    notes: initialNotes = "",
    imageUri,
    q10,
    q50,
    q90,
    confidence,
    explanation,
    attributesJson: initialAttributesJson,
    catalogKey,
  } = params;

  // Blank is the same as unset for these four. Doing it once here means every
  // consumer — the detail card, the save payload, the a11y labels — sees one
  // representation instead of each guarding for '' separately.
  const blankAs = (v: string | undefined, fallback: string) =>
    v == null || v.trim() === '' ? fallback : v;
  const name = blankAs(rawName, "Unknown item");
  const category = blankAs(rawCategory, "Not set");
  const collection = blankAs(rawCollection, "Not set");
  const condition = blankAs(rawCondition, "Not set");

  const isDraft = id === 'draft' || draft === '1';
  const inlineEditPending = useRef(false);

  // ── Resolve category slug early — needed by grading, build, size, progress sections ──
  const categorySlugRaw = CATEGORY_ID_MAP[category] || category.toLowerCase().replace(/[^a-z0-9_]/g, '');

  // Parse extracted attributes from QuickScan (passed as JSON string).
  // For SAVED items (non-draft), the items list doesn't pass attrs as a route
  // param, so we lazy-fetch them below for ItemAttributesSection display.
  const initialAttributes = useMemo(() => {
    if (!initialAttributesJson) return null;
    try {
      return JSON.parse(initialAttributesJson) as Record<string, unknown>;
    } catch (e) {
      logger.error('[silent-catch] [id].tsx:184:', e);
      return null;
    }
  }, [initialAttributesJson]);

  // Persisted-item attrs + collection_name fetched lazily for the
  // ItemAttributesSection presentation (set_name, year, brand, rarity,
  // grade, etc). For drafts the data already lives in initialAttributes
  // via the QuickScan route param. For saved items we hit Supabase REST
  // (RLS-safe) once on mount.
  const [savedAttrs, setSavedAttrs] = useState<Record<string, unknown> | null>(null);
  const [savedCollectionName, setSavedCollectionName] = useState<string | null>(null);
  const [savedSubtypeId, setSavedSubtypeId] = useState<string | null>(null);
  const [savedCanonicalKey, setSavedCanonicalKey] = useState<string | null>(null);
  // Core fields fetched by id. The screen takes name/category/condition/value
  // from ROUTE PARAMS, which only works when the caller happens to pass them.
  // Three entry points push just an id — search.tsx, franchise/[id].tsx and
  // the offers screen — so opening an item from Search, a franchise page or a
  // sell offer rendered "Unknown item / Unknown category / 0". Nothing fetched
  // the name: this effect selected only attrs/collection_name/canonical_key and
  // useItemDetail selects only for_sale/asking_price.
  //
  // Params stay the fast path (no flash of placeholder when they are supplied);
  // this is the fallback so a bare id is enough.
  const [savedCore, setSavedCore] = useState<{
    name?: string | null; category?: string | null; condition?: string | null;
    value?: number | null; imageUrl?: string | null; notes?: string | null;
    valueSource?: string | null;
    /** What the member typed — needed to offer "keep mine" against the comp. */
    userEstimate?: number | null;
  } | null>(null);
  useEffect(() => {
    if (isDraft || !id) return;
    let cancelled = false;
    (async () => {
      const { data, error } = await supabase
        .from('items')
        .select('attrs, collection_name, canonical_key, name, title, category, condition, estimated_value, predicted_price_eur, image_url, notes')
        .eq('id', id)
        .maybeSingle();
      if (cancelled || error || !data) return;
      const row = data as {
        attrs?: Record<string, unknown> | null; collection_name?: string | null; canonical_key?: string | null;
        name?: string | null; title?: string | null; category?: string | null; condition?: string | null;
        estimated_value?: number | null; predicted_price_eur?: number | null; image_url?: string | null;
        notes?: string | null;
      };
      // THE value, from the one definition of it — not this screen's own
      // guess at the chain. Reading `predicted_price_eur ?? estimated_value`
      // off the row skips BOTH prediction tables, which is exactly the defect
      // `v_item_values_v1` was created to end: 15 of 34 items (44%) rendered
      // EUR 0 in the app while the server held a value. The list was repointed
      // 2026-08-11 and this screen was not, so the same item could show two
      // different numbers one tap apart — and since manual adds stopped
      // writing `predicted_price_eur` (2026-08-19), a newly added item would
      // have shown its value in the list and nothing here.
      //
      // Bounded by construction: installRequestTimeouts() wraps every .from()
      // at the client. Degrades to the row's own columns when the view cannot
      // answer, in the view's OWN rank order — a different order here would be
      // a fifth definition of value.
      let viewValue: { valueEur: number | null; source: string | null } | null = null;
      try {
        viewValue = await fetchItemValueById(id);
      } catch (e) {
        // logger.error, not warn: warn is stripped in release builds and this
        // degradation is invisible by nature.
        logger.error('[ItemDetail] value view read failed:', e);
      }
      if (cancelled) return;

      setSavedCore({
        // name and title are the two halves of the same pair — see the
        // paired-columns note in docs/ARCHITECTURE.md.
        name: row.name || row.title || null,
        category: row.category ?? null,
        condition: row.condition ?? null,
        value:
          viewValue?.valueEur ??
          // Mirrors the view's TAIL (predicted_price_eur then estimated_value).
          // The two prediction tables cannot be read from here at all — RLS
          // denies price_predictions to the client — so a fallback can only
          // ever cover the stored columns.
          row.predicted_price_eur ??
          row.estimated_value ??
          null,
        valueSource: viewValue?.source ?? null,
        userEstimate: row.estimated_value ?? row.predicted_price_eur ?? null,
        imageUrl: row.image_url ?? null,
        notes: row.notes ?? null,
      });
      setSavedAttrs(row.attrs ?? null);
      setSavedCollectionName(row.collection_name ?? null);
      setSavedCanonicalKey(row.canonical_key ?? null);
      // subtype_id was renamed into items.attrs jsonb (see itemsProvider.ts).
      const sub = (row.attrs as Record<string, unknown> | null | undefined)?.subtype_id;
      setSavedSubtypeId(typeof sub === 'string' ? sub : null);
    })();
    return () => { cancelled = true; };
  }, [id, isDraft]);

  // Pick whichever source has data. Drafts use the route-param attrs;
  // saved items use the lazily-fetched attrs.
  const displayAttributes = isDraft ? initialAttributes : savedAttrs;
  const displayCollections = savedCollectionName ? [savedCollectionName] : undefined;

  // Adopt the fetched core fields once they land.
  //
  // useItemDetail seeds its editable state with useState(initialName), which
  // captures the FIRST render only — so passing a better initialName later has
  // no effect. The screen has to push the values in.
  //
  // Guarded on the placeholder so this can never clobber a real route param or
  // something the user has typed: it only fills in when the field is still
  // "Unknown item" / "Unknown category" / unset.
  const adoptedCoreRef = useRef(false);

  // ── Consolidated local state (useItemDetail hook) ──────────────────────
  const detail = useItemDetail({
    id, isDraft,
    initialName: name, initialCategory: category, initialCollection: collection,
    initialCondition: condition, initialValue: value, initialNotes: initialNotes,
    imageUri, categorySlug: categorySlugRaw, q50,
    q10, q90, confidence,
    initialAttributes,
    catalogKey,
  });

  useEffect(() => {
    if (!savedCore || adoptedCoreRef.current) return;
    if (savedCore.name && detail.editableName === "Unknown item") {
      detail.setEditableName(savedCore.name);
    }
    if (savedCore.category && detail.editableCategory === "Not set") {
      detail.setEditableCategory(savedCore.category);
    }
    if (savedCore.condition && detail.editableCondition === "Not set") {
      detail.setEditableCondition(savedCore.condition);
    }
    if (savedCore.value != null && (detail.editableValue === "0" || !detail.editableValue)) {
      detail.setEditableValue(String(savedCore.value));
    }
    // Notes come from the DB, not just route params. Without this the save
    // fixed in useItemDetail would still LOOK broken: reopening the item (deep
    // link, notification tap, app restart) showed an empty box because
    // `initialNotes` is only ever populated by a navigation param.
    // Guarded on empty so a user mid-edit is never overwritten by the fetch.
    if (savedCore.notes && !detail.notes) {
      detail.setNotes(savedCore.notes);
    }
    adoptedCoreRef.current = true;
  }, [savedCore, detail]);
  const {
    isEditing, setIsEditing,
    editableName, setEditableName,
    editableCategory, setEditableCategory,
    editableCollection, setEditableCollection,
    editableCondition, setEditableCondition,
    editableValue, setEditableValue,
    notes, setNotes,
    savingNotes, savingDraft, saveError,
    onSaveNotes, onSaveDraft, onSaveEdits,
    showSalePriceInput, setShowSalePriceInput,
    salePrice, setSalePrice,
    submittingFeedback, feedbackMessage, feedbackSource,
    onSubmitSalePrice, onPriceDisagree,
    keyboardVisible, keyboardHeight,
    explanationExpanded, setExplanationExpanded,
    showPriceExplanation, setShowPriceExplanation,
    showStickyButton, setShowStickyButton,
    aiRefreshing, setAiRefreshing,
    pullRefreshing, setPullRefreshing,
    isForSale, setIsForSale,
    askingPriceValue, setAskingPriceValue,
    forSaleLoading, handleListForSale, handleUnlist,
    evidenceData, setEvidenceData,
    itemAttributes, taxonomyVersion, subtypeId, itemCollections,
    scarcityData, marketComps,
    linkedProject, setLinkedProject,
  } = detail;

  /**
   * Attribute edits, held until Save.
   *
   * A ref, not state: these fields are typed into on every keystroke and none
   * of them affects what renders, so state would re-render the whole item
   * screen per character. The rows are uncontrolled (`defaultValue`), which is
   * what makes that safe.
   *
   * Only CHANGED keys are sent. `PATCH /items/{id}/attributes` merges with
   * `attrs || $3::jsonb` server-side, so a partial object cannot drop the keys
   * it omits — which is also why this must not spread the whole existing attrs
   * back in ([[learning_stale_attrs_spread_into_merge]]: a stale spread into a
   * merge endpoint is a lost update).
   */
  const editedAttrsRef = React.useRef<Record<string, string>>({});
  const onChangeAttribute = useCallback((key: string, value: string) => {
    editedAttrsRef.current[key] = value;
  }, []);

  const saveEditsWithAttributes = useCallback(async () => {
    const edited = editedAttrsRef.current;
    if (id && !isDraft && Object.keys(edited).length > 0) {
      // Empty string means "clear this field", which the jsonb merge cannot
      // express — `{"rarity": ""}` stores an empty string rather than removing
      // the key. That is the honest behaviour for now: the row reads blank
      // either way, and inventing a delete protocol here would be a second
      // contract for the same endpoint.
      try {
        await collectorsApi.patch(`/items/${encodeURIComponent(String(id))}/attributes`, {
          attributes: edited,
        });
        // Reflect immediately: the screen reads `savedAttrs` and would
        // otherwise show the old values until a refetch, which reads as the
        // save having failed.
        setSavedAttrs((prev) => ({ ...(prev ?? {}), ...edited }));
        editedAttrsRef.current = {};
      } catch (e) {
        logger.error('[ItemDetail] attribute save failed:', e);
        showToast({ message: "Couldn't save those details", type: 'error' });
        return;
      }
    }
    await onSaveEdits();
  }, [id, isDraft, onSaveEdits, showToast]);

  // Photo & gallery management (extracted to useItemGallery hook)
  const gallery = useItemGallery(id, isDraft, imageUri);
  const {
    zoomVisible, setZoomVisible,
    zoomImageUri, setZoomImageUri,
    galleryLoading,
    galleryActiveIndex, setGalleryActiveIndex,
    imageUploading,
    flatListRef: galleryFlatListRef,
    displayImageUri,
    effectiveGalleryImages,
    photoUploading, photoError,
    handleGalleryUpload,
    handleGalleryDelete,
    handlePhotoUpload,
    showPhotoSourcePicker,
    showLabelPicker,
    IMAGE_LABELS,
    LABEL_DISPLAY,
  } = gallery;
  const GALLERY_HEIGHT = 260;

  // Confetti ref for draft result reveal
  const confettiRef = useRef<ConfettiBurstRef>(null);

  // Fire confetti + success haptic on draft result reveal
  useEffect(() => {
    if (isDraft && confidence && parseFloat(confidence) > 0) {
      // Small delay to let the screen render first
      const timer = setTimeout(() => {
        confettiRef.current?.burst();
        fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      }, 400);
      return () => clearTimeout(timer);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- fire once on mount

  const scrollViewRef = useRef<ScrollView>(null);
  // Live scroll offset. `scrollToNotes` scrolls by a DELTA (how much of the
  // notes block the keyboard covers), so it needs the current absolute offset;
  // the Animated `scrollY` value can't be read synchronously.
  const scrollOffsetRef = useRef(0);
  // Mirror of `keyboardHeight` for callbacks that run inside a setTimeout and
  // would otherwise close over the pre-keyboard value (0).
  const keyboardHeightRef = useRef(0);


  useEffect(() => { keyboardHeightRef.current = keyboardHeight; }, [keyboardHeight]);

  // Track item view on mount
  useEffect(() => {
    if (id) track({ name: 'item_viewed', properties: { item_id: id as string, category: editableCategory } });
  }, []);

  // Provenance + Dossier state managed by useItemMarketplace hook above

  const categorySlug = CATEGORY_ID_MAP[editableCategory] || editableCategory.toLowerCase().replace(/[^a-z0-9_]/g, '');

  // ── On-demand enrich state — paid scrape for thin-cat items
  const [enriching, setEnriching] = useState(false);
  const [enrichResult, setEnrichResult] = useState<string | null>(null);
  const onEnrichOnDemand = async () => {
    if (enriching) return;
    setEnriching(true);
    setEnrichResult(null);
    try {
      const r: any = await enrichOnDemand({
        item_ref: `${categorySlug}:${(editableName || '').toLowerCase().replace(/\s+/g, '-').slice(0, 80)}`,
        query: editableName || '',
        category: categorySlug,
      });
      if (r?.skipped) {
        if (r.reason === 'cache_fresh') setEnrichResult(t('items_detail.enrich_cache'));
        else if (r.reason === 'budget_exhausted') setEnrichResult(t('items_detail.enrich_budget'));
        else setEnrichResult(t('items_detail.enrich_unavailable'));
      } else {
        setEnrichResult(t('items_detail.enrich_done', { count: r?.hits_persisted ?? 0 }));
      }
    } catch (e) {
      logger.error('[silent-catch] [id].tsx:332:', e);
      setEnrichResult(t('items_detail.enrich_error'));
    } finally {
      setEnriching(false);
    }
  };

  // ── Grading service state ────────────────────────────────────────────
  const isGradingEligible = GRADING_ELIGIBLE_CATEGORIES.has(categorySlug);
  const conditionOptions = isGradingEligible ? CONDITION_OPTIONS_GRADED : CONDITION_OPTIONS_GENERAL;

  // Grading management (extracted to useItemGrading hook)
  const grading = useItemGrading(categorySlug, editableName);
  const {
    gradingExpanded, setGradingExpanded,
    gradingLookupResult, setGradingLookupResult,
    gradingLookupLoading,
    gradingPopulation, setGradingPopulation,
    gradingPopLoading,
    gradingServices,
    gradingModalVisible, setGradingModalVisible,
    gradingCertInput, setGradingCertInput,
    gradingServicePick, setGradingServicePick,
    loadGradingServices,
    handleGradingLookup,
    loadGradingPopulation,
  } = grading;

  // Marketplace, affiliates, dossier, provenance (extracted to useItemMarketplace hook)
  const marketplace = useItemMarketplace(id, isDraft, editableName, editableCategory);
  const {
    marketResults, marketLoading, marketExpanded, setMarketExpanded,
    marketScannedAt, marketError, loadMarketResults,
    affiliateLinks,
    dossierData, dossierLoading, dossierExpanded, setDossierExpanded,
    dossierError, loadDossier,
  } = marketplace;

  // Price trend (extracted to useItemPriceTrend hook)
  const priceTrend = useItemPriceTrend(id, isDraft);
  const {
    priceTrendLoading,
    priceTrendRange,
    priceTrendVisible, setPriceTrendVisible,
    handleRangeChange: handlePriceTrendRangeChange,
    chartData: priceTrendChartData,
    handleHover: handlePriceTrendHover,
  } = priceTrend;
  const { width: screenWidth, height: windowHeight } = useWindowDimensions();
  const GALLERY_WIDTH = screenWidth - 32; // 16px padding on each side


  /**
   * The member answers "use the market price, or keep yours?".
   *
   * Recorded in `attrs.value_choice`, which `v_item_values_v1` reads: 'mine'
   * puts their number above the model. Recording 'market' changes no value —
   * it only stops us asking again, which is the difference between a question
   * and nagging.
   */
  const [compBusy, setCompBusy] = useState(false);
  const onChooseValue = useCallback(async (choice: 'market' | 'mine') => {
    if (!id) return;
    setCompBusy(true);
    try {
      // ONLY the key being changed. The endpoint MERGES
      // (`SET attrs = COALESCE(attrs,'{}') || $3::jsonb`), so spreading the
      // locally-cached attrs back in would resurrect a stale copy over
      // anything written since — the size editor on this same screen calls the
      // same endpoint. A merge endpoint plus a client-side spread is a
      // lost-update waiting for two edits in one session.
      await collectorsApi.updateItemAttributes(id, { value_choice: choice });
      setSavedAttrs((prev) => ({ ...(prev ?? {}), value_choice: choice }));
      if (choice === 'mine' && savedCore?.userEstimate != null) {
        // Reflect it immediately rather than waiting for a refetch: the view
        // will now return their number, and the screen should not keep showing
        // ours after they said no.
        setSavedCore((prev) =>
          prev ? { ...prev, value: savedCore.userEstimate, valueSource: 'user_estimate' } : prev,
        );
        detail.setEditableValue(String(savedCore.userEstimate));
      }
      showToast({
        message: choice === 'mine' ? 'Keeping your estimate' : 'Using the market price',
        type: 'success',
      });
    } catch (e) {
      logger.error('[ItemDetail] value choice failed:', e);
      showToast({ message: 'Could not save that choice', type: 'error' });
    } finally {
      setCompBusy(false);
    }
  }, [id, savedCore?.userEstimate, showToast, detail]);

  // Multi-marketplace listing modal
  const listForSaleHook = useListForSale({
    itemId: id ?? '',
    itemName: editableName,
    currency: settings.currency,
    suggestedPrice: toNum(editableValue) || toNum(q50) || undefined,
  });

  // Build project state — for buildable categories
  const itemIsBuildable = isBuildableCategory(categorySlug);
  const buildAccent = theme.accent;

  // ── Size-specific pricing state (sneakers, watches) ──────────────────
  const [itemSizeValue, setItemSizeValue] = useState<string>(
    (itemAttributes?.size as string) || (itemAttributes?.case_size as string) || ''
  );
  const [sizeSystem, setSizeSystem] = useState<'us' | 'eu' | 'uk' | 'mm'>(
    categorySlug === 'watches' ? 'mm' : ((itemAttributes?.size_system as string)?.toLowerCase() as 'us' | 'eu' | 'uk') || 'us'
  );
  const [sizeSaving, setSizeSaving] = useState(false);

  // Save size change to backend
  const handleSizeChange = useCallback(async (sizeVal: string, system: string) => {
    if (!id || isDraft) return;
    setSizeSaving(true);
    try {
      const sizeAttrs: Record<string, unknown> = {};
      if (categorySlug === 'sneakers') {
        sizeAttrs.size = sizeVal;
        sizeAttrs.size_system = system;
      } else if (categorySlug === 'watches') {
        sizeAttrs.case_size = sizeVal;
      }
      await collectorsApi.updateItemAttributes(id, sizeAttrs, sizeVal, system);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Size saved', type: 'success' });
    } catch (err) {
      logger.error('[ItemDetail] size save error:', err);
      showToast({ message: 'Failed to save size', type: 'error' });
    } finally {
      setSizeSaving(false);
    }
  }, [id, isDraft, categorySlug, settings.hapticsEnabled]);

  // Sync size state when attributes load
  useEffect(() => {
    if (itemAttributes) {
      const sizeVal = (itemAttributes.size as string) || (itemAttributes.case_size as string) || '';
      if (sizeVal && sizeVal !== itemSizeValue) setItemSizeValue(sizeVal);
      const sys = (itemAttributes.size_system as string)?.toLowerCase();
      if (sys && ['us', 'eu', 'uk', 'mm'].includes(sys)) setSizeSystem(sys as typeof sizeSystem);
    }
  }, [itemAttributes]); // eslint-disable-line react-hooks/exhaustive-deps

  // Progress tracking (extracted to useItemProgress hook)
  const progress = useItemProgress(id, isDraft, categorySlug);
  const {
    progressConfig,
    hasProgressTracking,
    progressStatus,
    progressPct,
    progressNotes,
    progressLoading,
    progressSaving,
    handleStatusChange: handleProgressStatusChange,
    handlePctChange: handleProgressPctChange,
    handleNotesChange: handleProgressNotesChange,
  } = progress;

  // (Price Alert section removed)

  // ActionSheet handlers for dropdowns
  const showCategoryPicker = () => {
    showActionSheet('Select Category', CATEGORY_OPTIONS, (index) => {
      setEditableCategory(CATEGORY_OPTIONS[index]);
      if (inlineEditPending.current) {
        inlineEditPending.current = false;
        setTimeout(() => onSaveEdits(), 100);
      }
    }, () => {
      if (inlineEditPending.current) {
        inlineEditPending.current = false;
        setIsEditing(false);
      }
    });
  };

  const showCollectionPicker = () => {
    showActionSheet('Select Collection/Set', COLLECTION_OPTIONS, (index) => {
      setEditableCollection(COLLECTION_OPTIONS[index]);
      if (inlineEditPending.current) {
        inlineEditPending.current = false;
        setTimeout(() => onSaveEdits(), 100);
      }
    }, () => {
      if (inlineEditPending.current) {
        inlineEditPending.current = false;
        setIsEditing(false);
      }
    });
  };

  const showConditionPicker = () => {
    const title = isGradingEligible ? 'Select Grade' : 'Select Condition';
    showActionSheet(title, conditionOptions, (index) => {
      setEditableCondition(conditionOptions[index]);
      if (inlineEditPending.current) {
        inlineEditPending.current = false;
        setTimeout(() => onSaveEdits(), 100);
      }
    }, () => {
      if (inlineEditPending.current) {
        inlineEditPending.current = false;
        setIsEditing(false);
      }
    });
  };

  // Inline tap-to-edit handlers — auto-enter edit mode and open picker in one tap
  const inlineEditCategory = () => {
    if (!isDraft && !isEditing) {
      setIsEditing(true);
      inlineEditPending.current = true;
    }
    showCategoryPicker();
  };
  const inlineEditCollection = () => {
    if (!isDraft && !isEditing) {
      setIsEditing(true);
      inlineEditPending.current = true;
    }
    showCollectionPicker();
  };
  const inlineEditCondition = () => {
    if (!isDraft && !isEditing) {
      setIsEditing(true);
      inlineEditPending.current = true;
    }
    showConditionPicker();
  };

  const scrollY = useRef(new Animated.Value(0)).current;

  // Empty fallback data — no fabricated mock data shown to users

  // Provenance fetched by useItemMarketplace hook

  // Fetch linked build project (if buildable category)
  useEffect(() => {
    if (!id || isDraft || !itemIsBuildable) return;
    let cancelled = false;
    dataProvider.listBuildPaintProjectsByItem(id)
      .then((projects) => {
        if (cancelled) return;
        if (projects.length > 0) {
          const p = projects[0];
          setLinkedProject({ id: p.id, title: p.title, pct: p.percent ?? 0 });
        }
      })
      .catch((err) => logger.warn('[ItemDetail] fetch error:', err));
    return () => { cancelled = true; };
  }, [id, isDraft, itemIsBuildable]);

  // Affiliate links, price trend, dossier, scarcity, comps, evidence managed by hooks above

  // Grading, marketplace, dossier functions managed by hooks above

  // Build PriceEstimate object from URL params for new PriceCard component
  const priceEstimate = useMemo((): PriceEstimate | null => {
    if (!q10 || !q50 || !q90) return null;
    const confidenceValue = confidence ? parseFloat(confidence) * 100 : 50;
    return {
      priceBand: {
        q10: parseFloat(q10),
        q50: parseFloat(q50),
        q90: parseFloat(q90),
      },
      currency: settings.currency,
      confidenceTier: getConfidenceTier(confidenceValue),
      confidencePercent: Math.round(confidenceValue),
    };
  }, [q10, q50, q90, confidence]);

  // Build PriceExplanation object for the explanation sheet
  const priceExplanationData = useMemo((): PriceExplanation | null => {
    if (!priceEstimate) return null;

    // Use real evidence from backend when available, else fall back to defaults
    const summary = evidenceData?.explanation
      || explanation
      || 'Price estimated based on comparable sales and market data.';

    const keyFactors: string[] = [
      `Item condition: ${condition || 'Not specified'}`,
      `Category: ${editableCategory}`,
    ];
    if (evidenceData?.evidence_summary?.total_comps) {
      keyFactors.push(`Based on ${evidenceData.evidence_summary.total_comps} comparable sales`);
    } else {
      keyFactors.push('Based on recent market activity');
    }

    const compSources = evidenceData?.evidence_summary?.sources?.length
      ? evidenceData.evidence_summary.sources.map((s) => ({
          source: s.source,
          count: s.count,
          avgPrice: s.avg_price,
          dateRange: s.date_range,
        }))
      : [
          { source: 'eBay', count: 12, avgPrice: priceEstimate.priceBand.q50 * 0.95, dateRange: 'Last 90 days' },
          { source: 'TCGPlayer', count: 8, avgPrice: priceEstimate.priceBand.q50 * 1.02 },
        ];

    const calculatedAt = evidenceData?.prediction_at || new Date().toISOString();

    return {
      summary,
      keyFactors,
      compSources,
      confidenceTier: priceEstimate.confidenceTier,
      confidencePercent: priceEstimate.confidencePercent,
      disclaimer: DEFAULT_DISCLAIMER,
      calculatedAt,
    };
  }, [priceEstimate, explanation, condition, editableCategory, evidenceData]);


  // Scroll the notes block clear of the keyboard.
  //
  // The previous version scrolled to `notesLayoutY - 60`, where notesLayoutY
  // came from the block's own `onLayout`. That y is relative to the block's
  // PARENT — the details card at line ~841 — not to the scroll content, and
  // the card starts ~700pt down (gallery + title + valuation). So it scrolled
  // to a point far above the notes and the field stayed under the keyboard.
  //
  // ItemNotesEditor now reports its measured on-screen rect instead, and this
  // scrolls by the OVERLAP only: enough to clear the keyboard, never more.
  const scrollToNotes = useCallback((rect: { y: number; height: number }) => {
    const kb = keyboardHeightRef.current;
    if (kb <= 0) return;
    // iOS: the keyboard overlays the window, so the visible bottom is
    // windowHeight - keyboardHeight. Android runs edge-to-edge here too (SDK
    // 54 default), so the window does not resize and the same math holds.
    const keyboardTop = windowHeight - kb;
    const overlap = rect.y + rect.height + NOTES_KEYBOARD_MARGIN - keyboardTop;
    if (overlap <= 0) return; // already fully visible — don't move the screen
    scrollViewRef.current?.scrollTo?.({
      y: scrollOffsetRef.current + overlap,
      animated: true,
    });
  }, [windowHeight]);

  // Refresh all AI intelligence data at once
  const refreshAllIntelligence = useCallback(async () => {
    if (!id || isDraft || aiRefreshing) return;
    setAiRefreshing(true);
    try {
      await Promise.all([
        collectorsApi.getPriceEvidence(id).then(setEvidenceData).catch((err) => logger.warn('[ItemDetail] fetch error:', err)),
        priceTrendVisible ? handlePriceTrendRangeChange(priceTrendRange) : Promise.resolve(),
        ...(marketResults.length > 0 || marketScannedAt ? [loadMarketResults()] : []),
      ]);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    } catch (err) {
      logger.error('[ItemDetail] intelligence refresh error:', err);
    } finally {
      setAiRefreshing(false);
    }
  }, [id, isDraft, aiRefreshing, setAiRefreshing, setEvidenceData, priceTrendVisible, handlePriceTrendRangeChange, priceTrendRange, marketResults.length, marketScannedAt, loadMarketResults, settings.hapticsEnabled]);

  const handlePullRefresh = useCallback(async () => {
    if (isDraft || !id) return;
    setPullRefreshing(true);
    await refreshAllIntelligence();
    setPullRefreshing(false);
  }, [isDraft, id, setPullRefreshing, refreshAllIntelligence]);

  // Lifted out of ItemQuickActionsRow when Share left that row for Sell.
  // Optimised for messaging (WhatsApp / iMessage), where people actually
  // share: the details a recipient needs on their own lines plus a tappable
  // link. A per-item sparrowcollect.com/item link opens the app but 404s for a
  // recipient who does not have it, so it links the site.
  const handleShareItem = useCallback(async () => {
    try {
      const val = toNum(editableValue) ?? 0;
      const message =
        `Check out my ${editableName} on Sparrow Collect` +
        (editableCondition && editableCondition !== 'Not set' ? `\nCondition: ${editableCondition}` : '') +
        (val ? `\nEstimated value: ${formatPrice(val, settings.currency)}` : '') +
        `\n\nhttps://sparrowcollect.com`;
      await Share.share({ message });
    } catch (e) {
      // Not silent: if the only share path fails the control is decorative.
      logger.error('[item] share failed:', e);
    }
  }, [editableName, editableValue, editableCondition, settings.currency]);

  /**
   * Is there an UNRESOLVED "which number should we show?" question on screen?
   *
   * Hoisted out of the JSX (2026-08-23) when two places needed the same answer.
   * The second consumer — a gate that hid the feedback block while this was
   * pending — was deleted later the same day, so there is ONE reader again and
   * this could fold back inline. It stays hoisted because the expression is
   * four fields of `savedCore`/`savedAttrs` and reads better named than as a
   * condition in the middle of the tree. A plain const in the body — not a
   * hook, and not inside one.
   */
  const compChoicePending = shouldOfferComp({
    valueSource: savedCore?.valueSource,
    currentValue: savedCore?.value,
    userEstimate: savedCore?.userEstimate,
    existingChoice:
      typeof savedAttrs?.value_choice === 'string' ? savedAttrs.value_choice : null,
  });

  return (
    <View style={[styles.safeArea, { backgroundColor: theme.background }]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        // 0, not 80. This screen renders under the native stack header
        // (`iconOnlyHeader`), so the KAV's own frame already starts below it —
        // an 80pt offset added 80pt of phantom padding and shoved the whole
        // screen up that much further than the keyboard needed.
        // app/chat/[threadId].tsx uses 0 under the same header.
        keyboardVerticalOffset={0}
      >
        <View style={{ flex: 1 }}>
        {/* Confetti overlay for draft result reveal */}
        {isDraft && <ConfettiBurst ref={confettiRef} particleCount={18} spread={120} duration={800} style={{ zIndex: 999 }} />}

        <Animated.ScrollView
          ref={scrollViewRef}
          style={styles.scroll}
          contentContainerStyle={[
            styles.content,
            { backgroundColor: theme.background },
            // NOT `keyboardHeight + 40`: on iOS the KeyboardAvoidingView above
            // already shrinks this ScrollView by the keyboard height, so adding
            // it again here double-counted it — ~2× the keyboard in dead space
            // below the content, which is what made the screen lurch. The extra
            // 80 is just slack so a field near the bottom of the content can
            // still be scrolled clear of the keyboard.
            { paddingBottom: keyboardVisible ? 200 : 120 },
          ]}
          keyboardShouldPersistTaps="handled"
          refreshControl={
            !isDraft ? (
              <RefreshControl
                refreshing={pullRefreshing}
                onRefresh={handlePullRefresh}
                tintColor={theme.accent}
                colors={[theme.accent]}
              />
            ) : undefined
          }
          onScroll={Animated.event(
            [{ nativeEvent: { contentOffset: { y: scrollY } } }],
            {
              useNativeDriver: false,
              listener: (event: { nativeEvent: { contentOffset: { y: number } } }) => {
                const offsetY = event.nativeEvent.contentOffset.y;
                scrollOffsetRef.current = offsetY;
                setShowStickyButton(offsetY > 200);
              },
            }
          )}
          scrollEventThrottle={16}
        >
          {/* ── Image Gallery ─────────────────────────────────────────── */}
          {/* Share lives HERE, top-right over the image, with the same metrics
              as the marketplace tile (app/listings.tsx `shareBtn`: 30x30,
              top/right 6, background + 'E6') — the placement the playbook
              specifies for share. It is deliberately NOT in the nav header:
              that cluster is bell/bubble/gear, and a fourth icon stops reading
              as a cluster and starts reading as a toolbar. */}
          <View>
          <ItemGallerySection
            theme={theme}
            hapticsEnabled={settings.hapticsEnabled}
            galleryLoading={galleryLoading}
            effectiveGalleryImages={effectiveGalleryImages}
            galleryActiveIndex={galleryActiveIndex}
            GALLERY_WIDTH={GALLERY_WIDTH}
            GALLERY_HEIGHT={GALLERY_HEIGHT}
            galleryFlatListRef={galleryFlatListRef}
            isDraft={isDraft}
            id={id}
            isEditing={isEditing}
            imageUploading={imageUploading}
            photoUploading={photoUploading}
            photoError={photoError}
            displayImageUri={displayImageUri}
            editableName={editableName}
            showPhotoSourcePicker={showPhotoSourcePicker}
            onGalleryDelete={handleGalleryDelete}
            onZoomImage={(uri) => {
              setZoomImageUri(uri);
              setZoomVisible(true);
            }}
            onMomentumScrollEnd={setGalleryActiveIndex}
          />
            <AnimatedPressable
              onPress={handleShareItem}
              style={[styles.galleryShareBtn, { backgroundColor: theme.background + 'E6' }]}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel="Share this item"
            >
              <Ionicons name="share-outline" size={16} color={theme.text} />
            </AnimatedPressable>
          </View>

          {/* Save / Cancel bar — only in edit mode */}
          {!isDraft && id && isEditing && (
            <ItemEditBar
              onSave={() => saveEditsWithAttributes()}
              // Cancel must DROP the pending attribute edits. Without this the
              // ref survives the cancel, and the next unrelated save would
              // silently write the abandoned values — an edit the member
              // explicitly took back.
              onCancel={() => { editedAttrsRef.current = {}; setIsEditing(false); }}
            />
          )}

          {/* For-Sale status badge — shown when listed */}
          {!isDraft && id && !isEditing && isForSale && (
            <ItemForSaleBar
              askingPriceValue={askingPriceValue}
              forSaleLoading={forSaleLoading}
              onUnlist={handleUnlist}
            />
          )}

          {/* Draft mode - Quick actions row */}
          {isDraft && (
            <ItemDraftActions
              savingDraft={savingDraft}
              saveError={saveError}
              onSaveDraft={onSaveDraft}
            />
          )}

          {/* ── Quick Actions ─────────────────────────────────────── */}
          {!isDraft && id && !isEditing && (
            <ItemQuickActionsRow
              isForSale={isForSale}
              onEdit={() => setIsEditing(true)}
              onListForSale={() => listForSaleHook.open()}
              // Straight to the full sell flow with the item prefilled — the
              // same handoff app/sell/pick.tsx uses, including its rule that
              // only a price > 0 seeds the box (a prefilled 0 reads as
              // "worthless" and fails the server's price > 0 on submit).
              onSell={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                const numeric = toNum(editableValue) ?? 0;
                router.push({
                  pathname: '/sell/new',
                  params: {
                    itemId: String(id ?? ''),
                    itemName: editableName,
                    itemCategory: editableCategory === 'Not set' ? '' : editableCategory,
                    itemImage: imageUri ?? '',
                    itemValue: numeric > 0 ? String(Math.round(numeric * 100) / 100) : '',
                    itemCondition: editableCondition === 'Not set' ? '' : editableCondition,
                  },
                });
              }}
            />
          )}

          {/* ── THE ITEM'S NAME ───────────────────────────────────────
              Hoisted out of `ItemDetailsCard` (2026-08-23) so the screen can
              lead with identity and then value. Read mode only: in edit mode
              the name is a form field and stays in the card with the other
              fields, exactly as the value row already does. */}
          {!isDraft && !isEditing && (
            <Text
              style={[styles.itemTitle, { color: theme.text }]}
              accessibilityRole="header"
              accessibilityLabel={`Item: ${editableName}`}
            >
              {editableName}
            </Text>
          )}

          {/* ── ORDER OF THIS SCREEN (2026-08-23) ─────────────────────
              Reported as *"the full card area is not optimized and it looks
              cluttered — pricing/market price/sell need to logically emphasize
              certain parts"*, then again as *"assess the full card for a
              hierarchy of user needs"*.

              The money used to sit in the MIDDLE. Between the item's name and
              what it is worth sat the whole spec table — category, collection,
              grade, rarity, brand, set code — reference data the owner already
              knows, because they own it. So the screen answered "what are its
              attributes" before "what is it worth", and the one monetary fact
              arrived after a scroll.

              Now: identify (gallery, name) -> act (Edit/List/Sell) -> VALUE
              (the figure, its provenance, its comps, and the control that
              corrects it) -> reference (the spec table) -> the member's own
              record (notes, progress) -> upsell.

              "Where to buy" deliberately stays LOW despite being an action:
              these are items the member already OWNS, so a buying link is not
              a need the top of this screen serves.

              The comp prompt travels WITH the valuation card — it asks which
              number that card should show, so it is meaningless anywhere
              else. */}
          {/* Asked AFTER the save, never as a modal over it. See
              MarketCompPrompt for why "keep mine" needs the view's choice
              branch to be an honest option at all. */}
          {compChoicePending ? (
            <MarketCompPrompt
              marketValue={savedCore?.value as number}
              userEstimate={savedCore?.userEstimate as number}
              onChoose={onChooseValue}
              busy={compBusy}
            />
          ) : null}

          {/* THE VALUATION CARD — and it only renders when it has something in
              it (2026-08-20).

              Every child of `ItemPriceSection` is conditional (PriceCard needs
              `priceEstimate`; the legacy bands need q10/q50/q90; confidence,
              explanation, scarcity and comps each need their own data), so an
              item with none of them produced a **bordered card containing
              nothing** — reported as the empty box with too much padding
              between the details and "Help improve our estimates".

              That is the rule this repo already wrote down: a bordered card
              with no content does not read as "this field is empty", it reads
              as a component that failed to load. Guard on the CONTENT
              (docs/ui-playbook.md, 2026-08-17).

              The card survives when any of its other tenants — the feedback
              prompt, the refresh bar — have something to show, because those
              are the same "what is this worth" question. */}
          {/* Rendered only when it HAS something. Every child of
              `ItemPriceSection` is conditional — PriceCard needs
              `priceEstimate`, the legacy bands need q10/q50/q90, and
              confidence, explanation, scarcity and comps each need their own
              data — so an item with none of them drew a bordered card
              containing nothing. Reported as the empty box with too much
              padding above "Help improve our estimates".

              A bordered card with no content does not read as "this field is
              empty"; it reads as a component that failed to load
              (docs/ui-playbook.md, 2026-08-17). The feedback prompt and the
              refresh bar count as content — they answer the same "what is this
              worth" question — which is why a saved item still gets the card. */}
          {/* `!isUnpriced(editableValue)` added 2026-08-22: the card now leads
              with the figure, so a priced item must get the card even when the
              ML band is absent — which is the common case (this item shows a
              catalogue-sourced EUR 6 and no band). */}
          {(priceEstimate || q10 || q50 || q90 || confidence
            // The term MUST match the lead's own render condition exactly.
            // `!isUnpriced(...)` alone opened the card for a DRAFT with a
            // value: the lead is `!isDraft && !isEditing`, the feedback is
            // `!isDraft && id`, and with no ML band ItemPriceSection draws
            // nothing — so the card rendered bordered and completely empty,
            // which reads as a component that failed to load rather than as
            // "no data". A gate that admits content the body then declines to
            // draw is the same bug in reverse.
            || (!isDraft && !isEditing && !isUnpriced(editableValue))
            || (!isDraft && id)) ? (
          <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]} accessibilityRole="summary" accessibilityLabel={t('item_detail.valuation_a11y')}>
            {/* THE figure, and the card's lead.
                It used to be row 4 of the spec table above at label/value
                weight — the only MONETARY fact on the screen with the least
                emphasis on it — while THIS card asked "Price seems off?" about
                a number it did not render. One card now answers both halves of
                "what is it worth, and is that right?".
                The provenance chip comes with it, never a second copy: for the
                40+ categories with no sold-comp source the figure IS somebody's
                guess, and the chip is what says so. */}
            {!isDraft && !isEditing ? (
              <View
                style={[
                  styles.valuationHighlight,
                  { backgroundColor: theme.accent + '14', borderBottomColor: theme.accent + '33' },
                ]}
              >
              <View style={styles.valuationLead}>
                {isUnpriced(editableValue) ? (
                  <Text style={[styles.valuationUnpriced, { color: theme.muted }]}>
                    {UNPRICED_LABEL}
                  </Text>
                ) : (
                  <>
                    {/* Accent, not `text`: this is the one monetary fact on the
                        screen and the card exists to lead with it. The accent
                        BUDGET that allows it was freed on 2026-08-22 — 48 teal
                        usages were cut to one tier per job — so this reads as
                        the primary thing rather than as more decoration
                        (docs/ui-playbook.md, "48 accent usages"). */}
                    <Text style={[styles.valuationAmount, { color: theme.accent }]}>
                      {formatPrice(toNum(editableValue), settings.currency)}
                    </Text>
                    {savedCore?.valueSource ? <ValueSourceChip source={savedCore.valueSource} /> : null}
                  </>
                )}
              </View>

              {/* The correction lives INSIDE the tinted block, under the figure
                  — not merely inside the same card. It was already in the card
                  (2026-08-23) but rendered AFTER `ItemPriceSection`, so on a
                  priced item with bands, an explanation, scarcity and comps it
                  could sit a screen away from the number it is about. "Against
                  the number" has to mean the number, not the section.

                  Two gates, and they are not decoration:

                  `id` — the enclosing block is `!isDraft && !isEditing`, while
                  this control has always required `!isDraft && id &&
                  !isEditing`. Nesting it without `id` would widen it. The
                  effective condition is unchanged.

                  `!isUnpriced` — NEW, and it is the thing moving it here
                  exposes. The block renders "Not priced yet" for an unpriced
                  item, and "Price seems off?" underneath that asks a member to
                  dispute a number the screen just said does not exist. It was
                  survivable while the control sat far below; directly beneath
                  the label it is two adjacent lines contradicting each other.
                  `onPriceDisagree` submits a disagreement about a valuation, so
                  with no valuation there is nothing to disagree with. */}
              {!isDraft && id && !isEditing && !isUnpriced(editableValue) ? (
                <PriceCorrectionRow
                  theme={theme}
                  submittingFeedback={submittingFeedback}
                  feedbackMessage={feedbackSource === 'disagree' ? feedbackMessage : null}
                  onPriceDisagree={onPriceDisagree}
                />
              ) : null}
              </View>
            ) : null}

            {/* Price display — PriceCard, legacy bands, confidence, explanation, scarcity, comps */}
            <ItemPriceSection
              priceEstimate={priceEstimate}
              onWhyThisPrice={() => setShowPriceExplanation(true)}
              q10={q10}
              q50={q50}
              q90={q90}
              confidence={confidence}
              explanation={explanation}
              explanationExpanded={explanationExpanded}
              onToggleExplanation={() => setExplanationExpanded(!explanationExpanded)}
              scarcityData={scarcityData}
              marketComps={marketComps}
              toNum={toNum}
            />

            {/* Thin-category boost prompt — runs above the feedback section
                for cats with sparse market data so the "tell us what you paid"
                signal is more visible. List mirrors BOOST_CATEGORIES in the
                scrape scheduler. */}
            {LIVE_PRICE_FETCH_ENABLED && !isDraft && id && (() => {
              const thinCats = new Set([
                'ghibli','pens','whiskey','pop_fandom','action_figures',
                'keycaps','blind_box','taylor_swift',
              ]);
              if (!thinCats.has(categorySlug)) return null;
              return (
                <View style={[styles.thinCatPrompt, { backgroundColor: theme.accent + '14', borderColor: theme.accent }]}>
                  <Ionicons name="sparkles-outline" size={16} color={theme.accent} />
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.thinCatPromptText, { color: theme.accent }]}>
                      {t('items_detail.thin_cat_help')}
                    </Text>
                    <AnimatedPressable
                      onPress={onEnrichOnDemand}
                      disabled={enriching}
                      style={[styles.enrichBtn, { backgroundColor: theme.accent, opacity: enriching ? 0.6 : 1 }]}
                      accessibilityRole="button"
                      accessibilityLabel={t('items_detail.enrich_button_a11y')}
                    >
                      {enriching ? (
                        <ActivityIndicator size="small" color="#fff" />
                      ) : (
                        <Text style={styles.enrichBtnText}>{t('items_detail.enrich_button')}</Text>
                      )}
                    </AnimatedPressable>
                    {enrichResult && (
                      <Text style={[styles.enrichResultText, { color: theme.muted }]}>{enrichResult}</Text>
                    )}
                  </View>
                </View>
              );
            })()}

            {/* The CORRECTION moved UP INTO the tinted valuation block on
                2026-08-26 — it used to render here, which is inside the same
                card but after `ItemPriceSection`, i.e. potentially a screen
                below the figure it corrects. See the comment at its new site
                for the two gates that came with the move. One instance only:
                a second copy here is how "the fix lands on the dead path". */}

            {/* Refresh All Data — compact action bar above data panels */}
            {!isDraft && id && (
              <ItemRefreshBar
                predictionAt={evidenceData?.prediction_at}
                aiRefreshing={aiRefreshing}
                onRefresh={refreshAllIntelligence}
              />
            )}
          </View>
          ) : null}

          {/* Details card */}
          <ItemDetailsCard
            isDraft={isDraft}
            isEditing={isEditing}
            editableName={editableName}
            editableCategory={editableCategory}
            editableCollection={editableCollection}
            editableCondition={editableCondition}
            editableValue={editableValue}
            isGradingEligible={isGradingEligible}
            categorySlug={categorySlug}
            categoryIdMap={CATEGORY_ID_MAP}
            // The saved-row values, not `useItemDetail`'s parallel copy: that
            // hook skips the fetch entirely for drafts, so the draft branch had
            // no attributes at all. `displayAttributes` covers both (route
            // params while drafting, the fetched row after the save).
            itemAttributes={displayAttributes ?? itemAttributes}
            taxonomyVersion={taxonomyVersion}
            subtypeId={savedSubtypeId ?? subtypeId}
            itemCollections={displayCollections ?? itemCollections}
            itemId={id}
            itemSizeValue={itemSizeValue}
            sizeSystem={sizeSystem}
            sizeSaving={sizeSaving}
            notes={notes}
            onEditableName={setEditableName}
            onEditableValue={setEditableValue}
            onShowCategoryPicker={showCategoryPicker}
            onShowCollectionPicker={showCollectionPicker}
            onShowConditionPicker={showConditionPicker}
            onSizeChange={handleSizeChange}
            onSizeSystemChange={setSizeSystem}
            onSizeValueChange={setItemSizeValue}
            onChangeAttribute={onChangeAttribute}
            // Rendered by the card, immediately after the attribute rows, so
            // "fill in details from catalogue" sits with the details it fills.
            catalogAction={
              !isDraft && id ? (
                <ItemCatalogRefresh
                  itemId={id}
                  itemTitle={editableName}
                  itemCategory={categorySlug}
                  currentAttrs={savedAttrs}
                  currentCanonicalKey={savedCanonicalKey}
                  onUpdated={() => {
                    (async () => {
                      const { data } = await supabase
                        .from('items')
                        .select('attrs, collection_name, canonical_key')
                        .eq('id', id)
                        .maybeSingle();
                      const row = data as { attrs?: Record<string, unknown> | null; collection_name?: string | null; canonical_key?: string | null } | null;
                      if (row) {
                        setSavedAttrs(row.attrs ?? null);
                        setSavedCollectionName(row.collection_name ?? null);
                        setSavedCanonicalKey(row.canonical_key ?? null);
                        const sub = (row.attrs as Record<string, unknown> | null | undefined)?.subtype_id;
                        setSavedSubtypeId(typeof sub === 'string' ? sub : null);
                      }
                    })();
                  }}
                />
              ) : null
            }
          />

          {/* ── END OF THE CARD STACK ──────────────────────────────────

              (This comment used to say "END OF THE VALUATION CARD". After the
              2026-08-23 reorder the valuation card closes ~70 lines above and
              the SPEC table is what ends here — a comment that expired the
              moment the blocks moved, which is the failure this playbook keeps
              recording. The history below is still the reason the stack is
              flat, so it stays.)


              It used to close 250 lines further down, which meant the
              price, the feedback prompt, the refresh bar, Sell this,
              Notes, Shop this item, reading progress AND the Pro
              sections were all inside ONE bordered container labelled
              "valuation". That is why the screen read as a single
              endless card: nothing ever ended.

              The sections below are self-contained components with
              their own padding, and the scroller already owns the 16pt
              gutter (`styles.content`), so they need no wrapper — they
              simply stop being nested inside a card that is not about
              them. */}

            {/* ═══════════════ USER-OWNED SECTIONS (top) ═══════════════ */}
            {/* Reordered 2026-04-19: things the user OWNS (notes, build project,
                progress, shop) come FIRST so they don't have to scroll past
                paywalled sections to edit their own data. Pro-gated sections
                moved below. */}

            {/* The captured-attributes list used to be mounted HERE as well as
                inside the details card above — two mounts, two fetches, one
                "Item Details" heading rendered twice on the same screen. It now
                lives in the card, under the value it describes. */}

            {/* The catalogue action moved INTO the details card (2026-08-20),
                directly under the attribute rows it fills in. Down here it was
                a lone pill floating between two cards — it broke the flow and
                gave no clue which fields it changes. */}

            {/* "Sell this" removed 2026-08-22. Sell moved into the top action
                row (it replaced Share), so this was a SECOND entry point to the
                same thing, further down the same screen — and the two did not
                even agree: this one expanded an inline create form while the
                top row opens app/sell/new, the full flow that carries the
                8-photo gallery. Two impls of one action is how a fix lands on
                the dead path. The component still exists and is unused; see the
                note in the commit before deleting it. */}

            {/* Notes (editable) — top priority per user feedback */}
            <ItemNotesEditor
              notes={notes}
              onChangeNotes={setNotes}
              onSaveNotes={onSaveNotes}
              onFocus={scrollToNotes}
            />

            {/* Build Project — for buildable categories */}
            {!isDraft && id && itemIsBuildable && (
              <BuildProjectSection
                theme={theme}
                buildAccent={buildAccent}
                linkedProject={linkedProject}
                itemIsBuildable={itemIsBuildable}
                editableName={editableName}
                itemId={id}
                categorySlug={categorySlug}
              />
            )}

            {/* Reading / Play Progress — for manga, comics, games */}
            {!isDraft && id && hasProgressTracking && progressConfig && (
              <ItemProgressSection
                categorySlug={categorySlug}
                progressConfig={progressConfig}
                progressStatus={progressStatus}
                progressPct={progressPct}
                progressNotes={progressNotes}
                progressLoading={progressLoading}
                progressSaving={progressSaving}
                theme={theme}
                hapticsEnabled={settings.hapticsEnabled}
                onStatusChange={handleProgressStatusChange}
                onPctChange={handleProgressPctChange}
                onNotesChange={handleProgressNotesChange}
              />
            )}

            {/* Shop this Item — affiliate links */}
            {!isDraft && (
              <ItemShopSection affiliateLinks={affiliateLinks} />
            )}

            {/* Sell Timing Badge — HIDDEN 2026-07-22 (per request). It only ever
                showed a "Coming soon · Premium" teaser (the feature isn't built),
                so it read as dead weight on the detail screen. The component +
                the market_hits query behind it are intentionally untouched — flip
                this block back on once Sell Timing actually ships.
            {!isDraft && savedCanonicalKey && (
              <SellTimingBadge itemId={savedCanonicalKey} />
            )} */}

            {/* Condition Grading — SHELVED 2026-05-02.
                Other apps (PSA app, CGC app) do this well already; charging
                for it without a real PSA/CGC API integration would break
                trust. The /grading/* BE endpoints stay (server-gated to
                Pro+) so we can flip the FE back on once a real API is
                wired. The condition_grading limit flag and the
                useItemGrading hook are intentionally untouched. */}

            {/* ═══════════════ PRO FEATURES (bottom) ═══════════════ */}
            {/* Paywall-gated analytics features — shown last with realistic
                mock previews so free users see what they'd unlock. */}

            {/* Price Trend Chart — SHELVED 2026-05-02.
                Coverage is uneven across the 54 categories: big-3 TCG cats
                (mtg/pokemon/yugioh) have rich price_history but tail cats
                (whiskey 16/wk, ghibli 19/wk, designer_toys 40/wk) render
                "not enough data" for most items. Charging Pro for a
                feature that visibly fails on entire categories is unfair.
                The /predict/trend/{id} BE endpoint stays — flip this back
                on (or per-category gate) once the bake feeds enough
                comps to every cat. */}

            {/* Pro insight sections. CONSOLIDATED 2026-07-22:
                - "Item History" (provenance) removed — it's a subset of the
                  dossier (which already returns provenance[]) and is empty for
                  virtually every user item, so it read as dead weight.
                - "Valuation Report" (dossier) is now gated to
                  VALUATION_ELIGIBLE_CATEGORIES — prod price/comps data only
                  exists for those cats; elsewhere the dossier renders empty.
                - "Market Prices" always shows for Pro: it's a LIVE marketplace
                  search (eBay/Cardmarket/…), so it works for any category.
                Free users get ONE consolidated upgrade card. */}
            {!isDraft && id && (
              limits.advanced_analytics ? (
                <>
                  {VALUATION_ELIGIBLE_CATEGORIES.has(categorySlug) && (
                    <DossierReportSection
                      theme={theme}
                      dossierData={dossierData}
                      dossierLoading={dossierLoading}
                      dossierExpanded={dossierExpanded}
                      dossierError={dossierError}
                      onToggleExpanded={() => {
                        if (!dossierData && !dossierError) loadDossier();
                        else setDossierExpanded(!dossierExpanded);
                      }}
                      onRetry={() => loadDossier()}
                      itemId={id}
                      formatPrice={(v, c) => formatPrice(v, c as CurrencyCode)}
                      toNum={toNum}
                    />
                  )}
                  <MarketplacePricesSection
                    theme={theme}
                    marketResults={marketResults}
                    marketLoading={marketLoading}
                    marketExpanded={marketExpanded}
                    marketError={marketError}
                    editableName={editableName}
                    onToggleExpanded={() => {
                      if (marketResults.length === 0 && !marketError) loadMarketResults();
                      else setMarketExpanded(!marketExpanded);
                    }}
                    onRetry={() => loadMarketResults()}
                    formatPrice={(v, c) => formatPrice(v, c as CurrencyCode)}
                    toNum={toNum}
                  />
                </>
              ) : (
                /* The name comes from the PLAN, not from this screen.
                   docs/MONETIZATION.md sells one line — "Advanced analytics
                   (price trend, history, market prices)" — and the analytics
                   screen's own prompt already says "Advanced Analytics". This
                   card used to invent "Item Insights", a product name that
                   appears in no plan, no store listing and no paywall, so a
                   member could not tell whether it was the thing they were
                   already being sold ([[learning_copy_written_from_code_not_from_the_doc]]).
                   Sub-labels renamed to the doc's words too. */
                <LockedPreviewSection
                  title="Advanced analytics"
                  requiredPlan="Pro"
                  features={[
                    { label: 'Market prices', description: '— live listings from eBay, Mercari, Vinted & more' },
                    { label: 'Valuation report', description: '— full dossier with comps & confidence' },
                  ]}
                />
              )
            )}

            {/* ── THE ASK, LAST ────────────────────────────────────────
                "Help improve our estimates" + "I sold it for…", after
                everything the member actually came here for.

                Reported twice: *"i like improving our estimates but is this the
                right location for example?"*, then *"the location of the market
                estimate and price fix error aren't changed"* — the first time
                round I only hid this block conditionally and never moved it.

                It sat directly under the figure, so the valuation card read
                "EUR 78" -> "Help improve our estimates". The hierarchy this
                screen expresses is monetary value, and this block has none FOR
                THE MEMBER: it is a favour asked of them on behalf of the model.
                Every other tenant of the valuation card answers "what is it
                worth"; this one asks. An ask goes last.

                "Price seems off?" is NOT here — it went the other way, up
                against the figure it corrects (`PriceCorrectionRow`), because
                that one is a correction rather than a favour.

                No `compChoicePending` gate any more. It existed because the two
                blocks were four rows apart and asked contradictory questions
                about the same number; from the far end of the screen there is
                no contradiction left to resolve, so the gate — and the
                `showSalePriceInput` escape hatch that only existed to soften
                it — are complexity with nothing behind them. Deleted rather
                than carried. */}
            {!isDraft && id && !isEditing && (
              <PriceFeedbackSection
                theme={theme}
                showSalePriceInput={showSalePriceInput}
                salePrice={salePrice}
                submittingFeedback={submittingFeedback}
                feedbackMessage={feedbackSource === 'sale' ? feedbackMessage : null}
                onShowSalePriceInput={setShowSalePriceInput}
                onSalePriceChange={setSalePrice}
                onSubmitSalePrice={onSubmitSalePrice}
                onPriceDisagree={onPriceDisagree}
                onCancelSalePrice={() => setShowSalePriceInput(false)}
              />
            )}


            {/* Bottom spacer inside card */}

        </Animated.ScrollView>

        {/* Sticky Save Button — appears on scroll for drafts only */}
        {showStickyButton && !keyboardVisible && isDraft && (
          <View style={[styles.stickyButtonContainer, { backgroundColor: theme.card, borderTopColor: theme.border }]}>
            <Pressable
              onPress={onSaveDraft}
              disabled={savingDraft}
              style={[
                styles.stickyButton,
                { backgroundColor: theme.accent, opacity: savingDraft ? 0.7 : 1 },
              ]}
              accessibilityRole="button"
              accessibilityLabel={t('item_detail.save_a11y')}
            >
              {savingDraft ? (
                <ActivityIndicator size="small" color={theme.accentText} />
              ) : (
                <>
                  <Ionicons name="checkmark-circle" size={20} color={theme.accentText} />
                  <Text style={[styles.stickyButtonText, { color: theme.accentText }]}>{t('item_detail.save')}</Text>
                </>
              )}
            </Pressable>
          </View>
        )}
      </View>

      {/* Price Explanation Bottom Sheet */}
      {featureFlags.FEATURE_EXPLAINABLE_AI_INTERFACES && priceEstimate && (
        <PriceExplanationSheet
          visible={showPriceExplanation}
          onClose={() => setShowPriceExplanation(false)}
          explanation={priceExplanationData}
          priceBand={priceEstimate.priceBand}
          currency={priceEstimate.currency}
          affiliateLinks={affiliateLinks}
        />
      )}

      {/* Image Zoom Modal */}
      {(zoomImageUri || displayImageUri) && (
        <ImageZoomModal
          visible={zoomVisible}
          imageUri={zoomImageUri || displayImageUri || ''}
          onClose={() => { setZoomVisible(false); setZoomImageUri(null); }}
        />
      )}

      {/* Multi-Marketplace Listing Modal */}
      <ListForSaleModal
        hook={listForSaleHook}
        onSuccess={() => {
          setIsForSale(true);
          fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
          showToast({ message: `Listed on ${listForSaleHook.selectedIds.length} marketplace${listForSaleHook.selectedIds.length > 1 ? 's' : ''}!`, type: 'success' });
        }}
      />

      {/* Watchlist modal removed — users add from watchlist screen */}
    </KeyboardAvoidingView>
    <QuickNavBar />
    </View>
  );
}

export default function ItemDetailScreenWithBoundary() {
  // Backstop for the id-shape seam. This screen is keyed by `items.id` (uuid);
  // every query below does `.eq('id', id)`, which PostgREST rejects with
  // `22P02 invalid input syntax for type uuid` for anything else. The call
  // sites route through `itemHref()` now, but deep links, push payloads and
  // future callers can still land here directly — so bounce a non-uuid id to
  // the catalog screen rather than rendering an "Unknown item" shell whose
  // every fetch fails silently.
  const { id, draft } = useLocalSearchParams<{ id?: string; draft?: string }>();
  const isDraftRoute = id === 'draft' || draft === '1';
  if (id && !isDraftRoute && !isUuid(id)) {
    return <Redirect href={{ pathname: '/catalog-item/[key]', params: { key: id } }} />;
  }

  return (
    <ScreenErrorBoundary screenName="Item Detail">
      <ItemDetailScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  // The item's name, now that it leads the screen rather than heading the spec
  // card. VERBATIM the metrics `ItemDetailsCard.name` carried — checked against
  // that style rather than described from memory, because the first version of
  // this block said "same metrics" over `text.xl`/`bold` and would have shrunk
  // every item title on the app while the comment claimed nothing had changed.
  //
  // It matches `valuationAmount` exactly, and that is fine BECAUSE of the tint:
  // the figure is set apart by an accent surface and accent text, not by
  // out-sizing the title. Name is the title, value is the headline.
  itemTitle: {
    fontSize: text['2xl'],
    fontWeight: fontWeight.extrabold,
    letterSpacing: -0.3,
    marginTop: 12,
    marginBottom: 4,
  },
  /**
   * The value block is a HIGHLIGHTED AREA, not more accent text.
   *
   * Asked for as *"highlight and differentiate the card with the tiffany
   * blue/teal, highlighted areas"*. The tempting version — teal on the label,
   * the chip, the comps — is exactly what docs/ui-playbook.md's "48 accent
   * usages is why nothing read as primary" records undoing: teal as default
   * decoration stops being a signal, and the accent table reserves the FILLED
   * tier for Sell, one per screen.
   *
   * A tinted SURFACE is a different axis from accent text, and the precedent is
   * already in this file (`thinCatPrompt`, `accent + '14'`). So the figure keeps
   * its accent text, nothing else gains any, and the region around it is what
   * differentiates the card. Alpha suffixes rather than a second palette entry
   * because `theme.accent` differs per theme — including high-contrast dark,
   * where a hardcoded tint would stop matching.
   */
  valuationHighlight: {
    marginHorizontal: -16,   // bleed to the card's edges; the card pads 16
    marginTop: -16,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 12,
    // NO `marginBottom` — `styles.card` carries `gap: 10`, so a margin here
    // would ADD to it. That is verbatim "Two containers, one `gap`", written
    // into this playbook this morning and re-earned four hours later.
    borderTopLeftRadius: radius.md,
    borderTopRightRadius: radius.md,
    borderBottomWidth: 1,
  },
  valuationLead: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 },
  // The money leads. 2xl/extrabold is the page-title spec, used here because
  // this figure is what the screen is about — the item's NAME is the title,
  // and its VALUE is the headline.
  valuationAmount: { fontSize: text['2xl'], fontWeight: fontWeight.extrabold, lineHeight: 30 },
  // An absence of data is not a headline: muted and body-sized, so "Not yet
  // priced" does not shout the way a real figure should.
  valuationUnpriced: { fontSize: text.md, fontWeight: fontWeight.semibold },
  // Same metrics as app/listings.tsx `shareBtn`, so the affordance is in the
  // same place and the same size wherever a member meets it.
  galleryShareBtn: {
    position: 'absolute', top: 6, right: 6, zIndex: 2,
    width: 30, height: 30, borderRadius: 15,
    alignItems: 'center', justifyContent: 'center',
  },
  safeArea: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
  thinCatPrompt: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 12,
  },
  thinCatPromptText: {
    flex: 1,
    fontSize: 13,
    fontWeight: '600',
  },
  enrichBtn: {
    marginTop: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    alignItems: 'center',
    alignSelf: 'flex-start',
  },
  enrichBtnText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '700',
  },
  enrichResultText: {
    marginTop: 6,
    fontSize: 12,
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 32,
  },
  // draftSection, draftButtonsRow, saveDraftButton, scanAnotherButton, errorText moved to ItemDraftActions
  card: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 16,
    gap: 10,
    // Two bordered cards with nothing between them read as overlapping — the
    // seam a screenshot was circled around. A container `gap` would have been
    // the tidier fix and is WRONG here: six direct children of `content`
    // already own a bottom margin (4/12/12/16/16), so a gap would add to each.
    marginBottom: 12,
  },
  // name, editableNameInputSimple, dropdownFieldRow, editableValueInput, editableValueRow, currencySymbol moved to ItemDetailsCard
  // priceBandsRow, confidenceSection, priceCardSection, label, explanationBlock/Header/Content/Text moved to ItemPriceSection
  // scarcityBadge, scarcityRow, scarcityLabel, scarcityMeta, compsSection, compsTitle, compRow, compTitle, compSource, compPrice moved to ItemPriceSection
  // notesBlock, notesHeaderRow, notesDoneBtn, notesDoneBtnText, notesInput moved to ItemNotesEditor
  // sectionBlock, sectionHeaderRow, sectionHeaderLeft, sectionTitle, affiliateLinkBtn, affiliateLinkText moved to ItemShopSection
  stickyButtonContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: 16,
    paddingVertical: 12,
    paddingBottom: 24,
    borderTopWidth: 1,
  },
  stickyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: radius.md,
    gap: gap.md,
  },
  stickyButtonText: {
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
  },
  // refreshBar, editBar, forSaleBar, quickActionsRow styles moved to extracted components
  // Progress Tracking styles moved to ItemProgressSection component
  // Grading styles moved to GradingSection component
  // Size, LEGO, Funko, Auth styles moved to CategorySpecificSection component
});