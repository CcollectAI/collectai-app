import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { router , useLocalSearchParams, Redirect } from 'expo-router';
import { isUuid } from '@/lib/ids';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  Pressable,
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
import { formatPrice, getCurrencySymbol } from "@/lib/format";
import type { CurrencyCode } from "@/data/types";
import { AnimatedPressable } from "@/motion";
import { isBuildableCategory } from "@/constants/buildStepTemplates";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { ConfettiBurst, ConfettiBurstRef } from '@/components/ConfettiBurst';
import { Skeleton } from '@/components/Skeleton';
import { ListForSaleModal } from '@/components/ListForSaleModal';
import { useListForSale } from '@/hooks/useListForSale';
import { CategorySpecificSection } from '@/components/CategorySpecificSection';
import { ItemProgressSection } from '@/components/ItemProgressSection';
import { GradingSection } from '@/components/GradingSection';
import type { GradingLookupResult, PopulationReport, GradingServiceInfo } from '@/components/GradingSection';
import { ItemGallerySection } from '@/components/ItemGallerySection';
import type { ItemImage } from '@/components/ItemGallerySection';
import { PriceFeedbackSection } from '@/components/PriceFeedbackSection';
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
import { UpgradePrompt } from '@/components/UpgradePrompt';
import { ItemDetailsCard } from '@/components/item/ItemDetailsCard';
import { ItemQuickActionsRow } from '@/components/item/ItemQuickActionsRow';
import { ItemShopSection } from '@/components/item/ItemShopSection';
import { ItemRefreshBar } from '@/components/item/ItemRefreshBar';
import { ItemDraftActions } from '@/components/item/ItemDraftActions';
import { ItemForSaleBar } from '@/components/item/ItemForSaleBar';
import { ItemEditBar } from '@/components/item/ItemEditBar';
import { ItemPriceSection } from '@/components/item/ItemPriceSection';
import { ItemNotesEditor } from '@/components/item/ItemNotesEditor';
import { SellOnSparrowSection } from '@/components/item/SellOnSparrowSection';
import { ItemAttributesSection } from '@/components/ItemAttributesSection';
import { ItemCatalogRefresh } from '@/components/item/ItemCatalogRefresh';
import { supabase } from '@/lib/supabase';
import { PriceTrendChart } from '@/components/PriceTrendChart';
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
    name = "Unknown item",
    category = "Not set",
    collection = "Not set",
    condition = "Not set",
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
          row.predicted_price_eur ??
          row.estimated_value ??
          null,
        valueSource: viewValue?.source ?? null,
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
    submittingFeedback, feedbackMessage,
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

          {/* Save / Cancel bar — only in edit mode */}
          {!isDraft && id && isEditing && (
            <ItemEditBar onSave={() => onSaveEdits()} onCancel={() => setIsEditing(false)} />
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
              editableName={editableName}
              editableValue={editableValue}
              editableCondition={editableCondition}
              isForSale={isForSale}
              onEdit={() => setIsEditing(true)}
              onListForSale={() => listForSaleHook.open()}
            />
          )}

          {/* Details card */}
          <ItemDetailsCard
            isDraft={isDraft}
            isEditing={isEditing}
            editableName={editableName}
            editableCategory={editableCategory}
            editableCollection={editableCollection}
            editableCondition={editableCondition}
            editableValue={editableValue}
            valueSource={savedCore?.valueSource ?? null}
            isGradingEligible={isGradingEligible}
            categorySlug={categorySlug}
            categoryIdMap={CATEGORY_ID_MAP}
            itemAttributes={itemAttributes}
            taxonomyVersion={taxonomyVersion}
            subtypeId={subtypeId}
            itemCollections={itemCollections}
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
          />

          <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]} accessibilityRole="summary" accessibilityLabel={t('item_detail.valuation_a11y')}>
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

            {/* Feedback section — shown for saved items */}
            {!isDraft && id && (
              <PriceFeedbackSection
                theme={theme}
                showSalePriceInput={showSalePriceInput}
                salePrice={salePrice}
                submittingFeedback={submittingFeedback}
                feedbackMessage={feedbackMessage}
                onShowSalePriceInput={setShowSalePriceInput}
                onSalePriceChange={setSalePrice}
                onSubmitSalePrice={onSubmitSalePrice}
                onPriceDisagree={onPriceDisagree}
                onCancelSalePrice={() => setShowSalePriceInput(false)}
              />
            )}

            {/* Refresh All Data — compact action bar above data panels */}
            {!isDraft && id && (
              <ItemRefreshBar
                predictionAt={evidenceData?.prediction_at}
                aiRefreshing={aiRefreshing}
                onRefresh={refreshAllIntelligence}
              />
            )}

            {/* ═══════════════ USER-OWNED SECTIONS (top) ═══════════════ */}
            {/* Reordered 2026-04-19: things the user OWNS (notes, build project,
                progress, shop) come FIRST so they don't have to scroll past
                paywalled sections to edit their own data. Pro-gated sections
                moved below. */}

            {/* Captured attributes — set_name / year / brand / rarity / grade / etc.
                Was a silent capture-without-consume bug: items.attrs jsonb has
                been populated by QuickScan + add-manual for months, but the
                presentation component was never mounted. Renders nothing when
                attrs is empty, so safe to always include. Uses
                displayAttributes which switches between draft route-params
                and the lazily-fetched saved-item row. */}
            <ItemAttributesSection
              attributes={displayAttributes}
              category={categorySlug}
              subtypeId={savedSubtypeId ?? undefined}
              collections={displayCollections}
            />

            {/* Re-match against catalog (post-save user-initiated). Helps
                older items that were created before the catalog had this
                entry, or before the canonical_key writer was wired. */}
            {!isDraft && id && (
              <ItemCatalogRefresh
                itemId={id}
                itemTitle={editableName}
                itemCategory={categorySlug}
                currentAttrs={savedAttrs}
                currentCanonicalKey={savedCanonicalKey}
                onUpdated={() => {
                  // Re-fetch so the just-applied attrs + canonical_key render
                  // immediately on the same screen without a navigation cycle.
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
            )}


            {/* Sell on the member marketplace (P2P Stage 1). Placed with the
                other user-OWNED actions, above the paywalled sections: this is
                something you do with YOUR item, not a feature to unlock.
                See docs/P2P_MARKETPLACE_SPEC.md. */}
            {!isDraft && id && !isEditing && (
              <SellOnSparrowSection
                itemId={id as string}
                colors={theme}
                currency={settings.currency}
                hapticsEnabled={settings.hapticsEnabled}
                suggestedPrice={priceEstimate?.priceBand?.q50 ?? null}
                canonicalKey={savedCanonicalKey}
                hasPhoto={Boolean(imageUri)}
              />
            )}

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
                <LockedPreviewSection
                  title="Item Insights"
                  requiredPlan="Pro"
                  features={[
                    { label: 'Market Prices', description: '— live listings from eBay, Mercari, Vinted & more' },
                    { label: 'Valuation Report', description: '— full dossier with comps & confidence' },
                  ]}
                />
              )
            )}

            {/* Bottom spacer inside card */}

          </View>
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