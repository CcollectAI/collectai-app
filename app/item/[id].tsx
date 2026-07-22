import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { router , useLocalSearchParams } from 'expo-router';
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



// Predefined options for dropdown menus
const COLLECTION_OPTIONS = ['Not set', 'Base Set', 'Jungle', 'Fossil', 'Team Rocket', 'Gym Heroes', 'Neo Genesis', 'Other'];
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
    category = "Unknown category",
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
    } catch {
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
  useEffect(() => {
    if (isDraft || !id) return;
    let cancelled = false;
    (async () => {
      const { data, error } = await supabase
        .from('items')
        .select('attrs, collection_name, canonical_key')
        .eq('id', id)
        .maybeSingle();
      if (cancelled || error || !data) return;
      const row = data as { attrs?: Record<string, unknown> | null; collection_name?: string | null; canonical_key?: string | null };
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

  // ── Consolidated local state (useItemDetail hook) ──────────────────────
  const detail = useItemDetail({
    id, isDraft,
    initialName: name, initialCategory: category, initialCollection: collection,
    initialCondition: condition, initialValue: value, initialNotes: initialNotes,
    imageUri, categorySlug: categorySlugRaw, q50,
    initialAttributes,
    catalogKey,
  });
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
  const notesLayoutY = useRef(0);


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
  const { width: screenWidth } = useWindowDimensions();
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
      logger.warn('[ItemDetail] size save error:', err);
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


  const scrollToNotes = () => {
    // Delay slightly to let keyboard height settle, then scroll notes into view
    setTimeout(() => {
      if (notesLayoutY.current > 0) {
        (scrollViewRef.current as ScrollView | null)?.scrollTo?.({
          y: notesLayoutY.current - 60,
          animated: true,
        });
      }
    }, 300);
  };

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
      logger.warn('[ItemDetail] intelligence refresh error:', err);
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
        keyboardVerticalOffset={Platform.OS === "ios" ? 80 : 0}
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
            { paddingBottom: keyboardVisible ? keyboardHeight + 40 : 120 },
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


            {/* Notes (editable) — top priority per user feedback */}
            <ItemNotesEditor
              notes={notes}
              onChangeNotes={setNotes}
              onSaveNotes={onSaveNotes}
              keyboardVisible={keyboardVisible}
              onLayout={(y) => { notesLayoutY.current = y; }}
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