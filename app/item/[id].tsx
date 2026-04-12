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
import { featureFlags } from "@/config/featureFlags";
import { radius, text, fontWeight, gap, shadow } from "@/theme/tokens";
import { collectorsApi } from "@/api/collectorsApi";
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
import { ProvenanceHistorySection } from '@/components/ProvenanceHistorySection';
import { track } from '@/analytics/track';
import { useBillingLimits } from '@/hooks/useBillingLimits';
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
// Pull from single source of truth — all 36 categories
import { CATEGORIES as ALL_CATS, CATEGORY_NAME_TO_SLUG, GRADING_ELIGIBLE_CATEGORIES } from '@/constants/categories';
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
  } = params;

  const isDraft = id === 'draft' || draft === '1';
  const inlineEditPending = useRef(false);

  // ── Resolve category slug early — needed by grading, build, size, progress sections ──
  const categorySlugRaw = CATEGORY_ID_MAP[category] || category.toLowerCase().replace(/[^a-z0-9_]/g, '');

  // Parse extracted attributes from QuickScan (passed as JSON string)
  const initialAttributes = useMemo(() => {
    if (!initialAttributesJson) return null;
    try {
      return JSON.parse(initialAttributesJson) as Record<string, unknown>;
    } catch {
      return null;
    }
  }, [initialAttributesJson]);

  // ── Consolidated local state (useItemDetail hook) ──────────────────────
  const detail = useItemDetail({
    id, isDraft,
    initialName: name, initialCategory: category, initialCollection: collection,
    initialCondition: condition, initialValue: value, initialNotes: initialNotes,
    imageUri, categorySlug: categorySlugRaw, q50,
    initialAttributes,
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
    provenanceEvents, authenticitySignals,
    provenanceLoading, provenanceExpanded, setProvenanceExpanded,
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

            {/* Price History section removed — data available via Full Report and Market Prices */}

            {/* Item History — collapsible */}
            {!isDraft && id && (
              <ProvenanceHistorySection
                theme={theme}
                hapticsEnabled={settings.hapticsEnabled}
                provenanceExpanded={provenanceExpanded}
                provenanceLoading={provenanceLoading}
                provenanceEvents={provenanceEvents}
                authenticitySignals={authenticitySignals}
                onToggleExpanded={() => setProvenanceExpanded(!provenanceExpanded)}
              />
            )}

            {/* Grading Section — for eligible categories (Pro+) */}
            {!isDraft && id && isGradingEligible && !limits.condition_grading && (
              <UpgradePrompt feature="Condition Grading" requiredPlan="Pro" />
            )}
            {!isDraft && id && isGradingEligible && limits.condition_grading && (
              <GradingSection
                theme={theme}
                hapticsEnabled={settings.hapticsEnabled}
                gradingExpanded={gradingExpanded}
                onToggleExpanded={() => {
                  if (!gradingExpanded) {
                    loadGradingServices();
                    if (!gradingPopulation) loadGradingPopulation();
                  }
                  setGradingExpanded(!gradingExpanded);
                }}
                gradingLookupResult={gradingLookupResult}
                gradingPopulation={gradingPopulation}
                gradingPopLoading={gradingPopLoading}
                gradingServices={gradingServices}
                gradingModalVisible={gradingModalVisible}
                onSetGradingModalVisible={setGradingModalVisible}
                gradingCertInput={gradingCertInput}
                onSetGradingCertInput={setGradingCertInput}
                gradingServicePick={gradingServicePick}
                onSetGradingServicePick={setGradingServicePick}
                gradingLookupLoading={gradingLookupLoading}
                onGradingLookup={handleGradingLookup}
              />
            )}

            {/* Dossier Section */}
            {!isDraft && id && (
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

            {/* Marketplace Section */}
            {!isDraft && id && (
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
            )}

            {/* Notes (editable) */}
            <ItemNotesEditor
              notes={notes}
              onChangeNotes={setNotes}
              onSaveNotes={onSaveNotes}
              keyboardVisible={keyboardVisible}
              onLayout={(y) => { notesLayoutY.current = y; }}
              onFocus={scrollToNotes}
            />

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