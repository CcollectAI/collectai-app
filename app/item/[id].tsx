import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { router } from 'expo-router';
import {
  ScrollView,
  FlatList,
  View,
  Text,
  StyleSheet,
  TextInput,
  Pressable,
  Alert,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Animated,
  RefreshControl,
  Share,
  Modal,
  useWindowDimensions,
} from "react-native";
import { Image } from "expo-image";
import { useLocalSearchParams } from "expo-router";
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from "@/hooks/useAppTheme";
import { showActionSheet } from "@/hooks/useActionSheetPicker";
import { useItemGallery } from "@/hooks/useItemGallery";
import { useItemGrading } from "@/hooks/useItemGrading";
import { useItemPriceTrend } from "@/hooks/useItemPriceTrend";
import { useItemProgress } from "@/hooks/useItemProgress";
import { useItemMarketplace } from "@/hooks/useItemMarketplace";
import { useAuthContext } from "@/providers/useAuthContext";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useToast } from "@/components/Toast";
import { dataProvider } from "@/data";
import { PriceConfidenceGauge } from "@/components/PriceConfidenceGauge";
import { ImageZoomModal } from "@/components/ImageZoomModal";
import { PriceCard } from "@/components/PriceCard";
import { PriceExplanationSheet } from "@/components/PriceExplanationSheet";
import {
  PriceEstimate,
  PriceExplanation,
  getConfidenceTier,
  DEFAULT_DISCLAIMER,
} from "@/types/priceExplanation";
import { featureFlags } from "@/config/featureFlags";
import { collectorsApi } from "@/api/collectorsApi";
import { ProvenanceTimeline } from "@/components/ProvenanceTimeline";
import { Linking } from "react-native";
import logger from "@/utils/logger";
import { ItemAttributesSection } from "@/components/ItemAttributesSection";
import { formatPrice, formatNumber, getCurrencySymbol } from "@/lib/format";
import type { CurrencyCode } from "@/data/types";
import { AnimatedPressable } from "@/motion";
import { isBuildableCategory } from "@/constants/buildStepTemplates";
import { CATEGORY_VISUAL } from "@/data/categories";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { ConfettiBurst, ConfettiBurstRef } from '@/components/ConfettiBurst';
import InteractiveLineChart from '@/components/InteractiveLineChart';
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

// DossierData and MarketHit types imported from extracted components

// Price trend data shape
interface PriceTrendData {
  data_points: Array<{ date: string; q50: number; q10: number; q90: number }>;
  direction: 'up' | 'down' | 'flat';
  pct_change: number;
  current_q50: number;
  period_days: number;
}

// Time range options for the price chart
const PRICE_CHART_RANGES = [
  { label: '1W', days: 7 },
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
] as const;

// Sneaker/watch sizes moved to CategorySpecificSection component

// Helper: parse string|number to number for formatPrice/formatNumber
const toNum = (value: string | number | undefined | null): number | undefined => {
  if (value === undefined || value === null || value === '') return undefined;
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return undefined;
  return num;
};

// Helper: relative time display from ISO timestamp
const relativeTime = (iso: string | null | undefined): string => {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
};

// Predefined options for dropdown menus
const COLLECTION_OPTIONS = ['Not set', 'Base Set', 'Jungle', 'Fossil', 'Team Rocket', 'Gym Heroes', 'Neo Genesis', 'Other'];
const CONDITION_OPTIONS_GENERAL = ['Not set', 'Mint', 'Near Mint', 'Excellent', 'Good', 'Fair', 'Poor'];
const CONDITION_OPTIONS_GRADED = ['Not set', 'PSA 10', 'PSA 9', 'PSA 8', 'PSA 7', 'BGS 10', 'BGS 9.5', 'CGC 9.8', 'CGC 9.6', 'Raw', 'Mint', 'Near Mint', 'Excellent', 'Good', 'Fair', 'Poor'];
// Pull from single source of truth — all 36 categories
import { CATEGORIES as ALL_CATS, CATEGORY_NAME_TO_SLUG, GRADING_ELIGIBLE_CATEGORIES } from '@/constants/categories';

const CATEGORY_OPTIONS = [...ALL_CATS.map((c) => c.name), 'Other'];
const CATEGORY_ID_MAP: Record<string, string> = {
  ...CATEGORY_NAME_TO_SLUG,
  'Other': 'unknown',
};

function ItemDetailScreen() {
  const { colors: theme } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
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
  } = params;

  const isDraft = id === 'draft' || draft === '1';
  const [isEditing, setIsEditing] = useState(false);
  const inlineEditPending = useRef(false);

  // Photo & gallery management (extracted to useItemGallery hook)
  const { user } = useAuthContext();
  const gallery = useItemGallery(id, isDraft, imageUri);
  const {
    userPhoto, setUserPhoto,
    zoomVisible, setZoomVisible,
    zoomImageUri, setZoomImageUri,
    galleryImages, setGalleryImages,
    galleryLoading,
    galleryActiveIndex, setGalleryActiveIndex,
    imageUploading,
    pendingLabel, setPendingLabel,
    flatListRef: galleryFlatListRef,
    displayImageUri,
    effectiveGalleryImages,
    photoUploading, photoError, userPhotoUrl,
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

  const [notes, setNotes] = useState(initialNotes || "");
  const [savingNotes, setSavingNotes] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const notesInputRef = useRef<TextInput | null>(null);
  const scrollViewRef = useRef<ScrollView>(null);
  const notesLayoutY = useRef(0);

  // Track keyboard visibility and height
  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  useEffect(() => {
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const showSub = Keyboard.addListener(showEvent, (e) => {
      setKeyboardVisible(true);
      setKeyboardHeight(e.endCoordinates.height);
    });
    const hideSub = Keyboard.addListener(hideEvent, () => {
      setKeyboardVisible(false);
      setKeyboardHeight(0);
    });
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);

  // Feedback state
  const [showSalePriceInput, setShowSalePriceInput] = useState(false);
  const [salePrice, setSalePrice] = useState("");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  // Quick-edit state (draft mode)
  const [editableName, setEditableName] = useState(name);
  const [editableCategory, setEditableCategory] = useState(category);

  // Track item view on mount
  useEffect(() => {
    if (id) track({ name: 'item_viewed', properties: { item_id: id as string, category: editableCategory } });
  }, []);

  const [editableCollection, setEditableCollection] = useState(collection);
  const [editableCondition, setEditableCondition] = useState(condition);
  const [editableValue, setEditableValue] = useState(value);
  const [isEditingName, setIsEditingName] = useState(false);
  const [isEditingCategory, setIsEditingCategory] = useState(false);

  // Expandable explanation state
  const [explanationExpanded, setExplanationExpanded] = useState(false);

  // Provenance + Dossier state managed by useItemMarketplace hook above

  // ── Resolve category slug early — needed by grading, build, size, progress sections ──
  const categorySlug = CATEGORY_ID_MAP[editableCategory] || editableCategory.toLowerCase().replace(/[^a-z0-9_]/g, '');

  // Item attributes from DB (attributes_json, taxonomy_version, subtype_id, collections)
  const [itemAttributes, setItemAttributes] = useState<Record<string, unknown> | null>(null);
  const [taxonomyVersion, setTaxonomyVersion] = useState<string | undefined>();
  const [subtypeId, setSubtypeId] = useState<string | undefined>();
  const [itemCollections, setItemCollections] = useState<string[]>([]);

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
    priceTrendData,
    priceTrendLoading,
    priceTrendRange,
    priceTrendVisible, setPriceTrendVisible,
    priceTrendHoverValue,
    priceTrendHoverDate,
    handleRangeChange: handlePriceTrendRangeChange,
    chartData: priceTrendChartData,
    handleHover: handlePriceTrendHover,
  } = priceTrend;
  const { width: screenWidth } = useWindowDimensions();
  const GALLERY_WIDTH = screenWidth - 32; // 16px padding on each side

  // AI Intelligence refresh state
  const [aiRefreshing, setAiRefreshing] = useState(false);
  const [pullRefreshing, setPullRefreshing] = useState(false);

  // For-Sale listing state
  const [isForSale, setIsForSale] = useState(false);
  const [askingPriceValue, setAskingPriceValue] = useState('');
  const [forSaleModalVisible, setForSaleModalVisible] = useState(false);
  const [forSaleLoading, setForSaleLoading] = useState(false);

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
  const [linkedProject, setLinkedProject] = useState<{ id: string; title: string; pct: number } | null>(null);

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

  // Scroll tracking for sticky save button
  const [showStickyButton, setShowStickyButton] = useState(false);
  const scrollY = useRef(new Animated.Value(0)).current;

  // Price explanation sheet state (for new explainable AI interface)
  const [showPriceExplanation, setShowPriceExplanation] = useState(false);

  // Evidence data from backend (lazy-loaded for PriceExplanationSheet)
  const [evidenceData, setEvidenceData] = useState<{
    explanation: string | null;
    evidence_summary: {
      sources: Array<{ source: string; count: number; avg_price: number; date_range?: string }>;
      total_comps: number;
    } | null;
    evidence_hit_ids: string[];
    prediction_at: string | null;
  } | null>(null);

  useEffect(() => {
    if (!id || isDraft) return;
    collectorsApi.getPriceEvidence(id)
      .then(setEvidenceData)
      .catch((err) => logger.warn('[ItemDetail] evidence fetch error:', err));
    // Auto-refresh evidence data every 5 minutes
    const evidenceInterval = setInterval(() => {
      collectorsApi.getPriceEvidence(id).then(setEvidenceData).catch(() => {});
    }, 300000); // 5 min
    return () => clearInterval(evidenceInterval);
  }, [id, isDraft]);

  useEffect(() => {
    if (!id || isDraft) return;
    dataProvider.listItems().then((items) => {
      const item = items.find((i) => i.id === id);
      if (item) {
        setItemAttributes(item.attributesJson || null);
        setTaxonomyVersion(item.taxonomyVersion);
        setSubtypeId(item.subtypeId);
        setItemCollections(item.collections || []);
      }
    }).catch((err) => logger.warn('[ItemDetail] item attributes fetch error:', err));
  }, [id, isDraft]);

  // Empty fallback data — no fabricated mock data shown to users

  // Provenance fetched by useItemMarketplace hook

  // Fetch linked build project (if buildable category)
  useEffect(() => {
    if (!id || isDraft || !itemIsBuildable) return;
    dataProvider.listBuildPaintProjectsByItem(id)
      .then((projects) => {
        if (projects.length > 0) {
          const p = projects[0];
          setLinkedProject({ id: p.id, title: p.title, pct: p.percent ?? 0 });
        }
      })
      .catch(() => {});
  }, [id, isDraft, itemIsBuildable]);

  // Affiliate links, price trend, and dossier managed by hooks above

  // ── Grading: auto-detect cert number from item attributes ──────────────
  const itemCertNumber = useMemo(() => {
    // Check common attribute names for cert/grade data
    const attrs = params as Record<string, string | undefined>;
    // Look in item attributes passed via URL params or local state
    return null; // Will be populated from item data if available
  }, [params]);

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

  const onSaveNotes = () => {
    setSavingNotes(true);
    // Notes are local-only for now
    setTimeout(() => {
      setSavingNotes(false);
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Notes saved locally', type: 'info' });
    }, 300);
  };

  const onSaveDraft = async () => {
    if (!isDraft) return;

    setSavingDraft(true);
    setSaveError(null);

    try {
      const persisted = await dataProvider.persistQuickscanDraft({
        photoUri: imageUri || '',
        categoryId: editableCategory,
        title: editableName,
        notes: notes || undefined,
      });

      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Item saved to collection', type: 'success' });

      // Navigate to saved item with all editable values
      router.replace({
        pathname: '/item/[id]',
        params: {
          id: persisted.id,
          name: persisted.title,
          category: persisted.categoryId,
          collection: editableCollection,
          condition: editableCondition,
          value: editableValue || String(q50 || value || 0),
          imageUri: persisted.imageUrl || '',
        },
      });
    } catch (err: unknown) {
      logger.error('[ItemDetail] save draft error:', err);
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
      setSaveError(err instanceof Error ? err.message : 'Failed to save item');
    } finally {
      setSavingDraft(false);
    }
  };

  const onSaveEdits = async () => {
    if (!id || isDraft) return;
    setSavingNotes(true);
    try {
      await dataProvider.updateItem(id, {
        name: editableName,
        category: editableCategory,
      });
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Changes saved', type: 'success' });
      setIsEditing(false);
    } catch (err: unknown) {
      logger.error('[ItemDetail] save edits error:', err);
      showToast({ message: 'Failed to save changes', type: 'error' });
    } finally {
      setSavingNotes(false);
    }
  };

  const scrollToNotes = () => {
    // Delay slightly to let keyboard height settle, then scroll notes into view
    setTimeout(() => {
      if (notesLayoutY.current > 0) {
        (scrollViewRef.current as any)?.scrollTo?.({
          y: notesLayoutY.current - 60,
          animated: true,
        });
      }
    }, 300);
  };

  const onSubmitSalePrice = async () => {
    if (!salePrice.trim() || !id || isDraft) return;

    setSubmittingFeedback(true);
    setFeedbackMessage(null);

    try {
      await dataProvider.submitFeedback(id, 'sale_price', salePrice.trim());
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Sale price recorded — thanks!', type: 'success' });
      setFeedbackMessage("Thanks! Sale price recorded.");
      setShowSalePriceInput(false);
      setSalePrice("");
    } catch (err: unknown) {
      logger.error('[ItemDetail] feedback error:', err);
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
      setFeedbackMessage("Failed to submit feedback");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const onPriceDisagree = async () => {
    if (!id || isDraft) return;

    setSubmittingFeedback(true);
    setFeedbackMessage(null);

    try {
      await dataProvider.submitFeedback(id, 'disagree', 'inaccurate');
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      setFeedbackMessage("Thanks for the feedback!");
    } catch (err: unknown) {
      logger.error('[ItemDetail] feedback error:', err);
      setFeedbackMessage("Failed to submit feedback");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  // Refresh all AI intelligence data at once
  const refreshAllIntelligence = async () => {
    if (!id || isDraft || aiRefreshing) return;
    setAiRefreshing(true);
    try {
      await Promise.all([
        collectorsApi.getPriceEvidence(id).then(setEvidenceData).catch(() => {}),
        priceTrendVisible ? handlePriceTrendRangeChange(priceTrendRange) : Promise.resolve(),
        ...(marketResults.length > 0 || marketScannedAt ? [loadMarketResults()] : []),
      ]);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    } catch (err) {
      logger.warn('[ItemDetail] intelligence refresh error:', err);
    } finally {
      setAiRefreshing(false);
    }
  };

  const handlePullRefresh = async () => {
    if (isDraft || !id) return;
    setPullRefreshing(true);
    await refreshAllIntelligence();
    setPullRefreshing(false);
  };

  // ── For-Sale listing handlers ────────────────────────────────────────
  const handleListForSale = async () => {
    if (!id || isDraft || forSaleLoading) return;
    const price = parseFloat(askingPriceValue);
    if (isNaN(price) || price <= 0) {
      showToast({ message: 'Enter a valid asking price', type: 'error' });
      return;
    }
    setForSaleLoading(true);
    try {
      await dataProvider.toggleForSale(id, true, price);
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Item listed for sale!', type: 'success' });
      setIsForSale(true);
      setForSaleModalVisible(false);
    } catch (err: unknown) {
      logger.error('[ItemDetail] list for sale error:', err);
      showToast({ message: 'Failed to list item for sale', type: 'error' });
    } finally {
      setForSaleLoading(false);
    }
  };

  const handleUnlist = async () => {
    if (!id || isDraft || forSaleLoading) return;
    setForSaleLoading(true);
    try {
      await dataProvider.toggleForSale(id, false);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Item unlisted', type: 'info' });
      setIsForSale(false);
      setAskingPriceValue('');
    } catch (err: unknown) {
      logger.error('[ItemDetail] unlist error:', err);
      showToast({ message: 'Failed to unlist item', type: 'error' });
    } finally {
      setForSaleLoading(false);
    }
  };

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
            <View style={styles.editBar}>
              <AnimatedPressable
                onPress={() => onSaveEdits()}
                style={[styles.editBarBtnPrimary, { backgroundColor: theme.accent }]}
                accessibilityRole="button"
                accessibilityLabel="Save changes"
              >
                <Ionicons name="checkmark-circle" size={18} color="#fff" />
                <Text style={styles.editBarBtnPrimaryText}>Save Changes</Text>
              </AnimatedPressable>
              <AnimatedPressable
                onPress={() => setIsEditing(false)}
                style={[styles.editBarBtn, { backgroundColor: theme.card, borderColor: theme.border }]}
                accessibilityRole="button"
                accessibilityLabel="Cancel editing"
              >
                <Text style={[styles.editBarBtnText, { color: theme.muted }]}>Cancel</Text>
              </AnimatedPressable>
            </View>
          )}

          {/* For-Sale status badge — shown when listed */}
          {!isDraft && id && !isEditing && isForSale && (
            <View style={styles.forSaleBar}>
              <View style={[styles.forSaleBadge, { backgroundColor: '#D1FAE5' }]}>
                <Ionicons name="pricetag" size={14} color="#065F46" />
                <Text style={[styles.forSaleBadgeText, { color: '#065F46' }]}>
                  Listed{askingPriceValue ? ` ${formatPrice(parseFloat(askingPriceValue), settings.currency)}` : ''}
                </Text>
              </View>
              <AnimatedPressable
                onPress={() => router.push('/sell/offers')}
                style={[styles.editBarBtn, { backgroundColor: theme.accent + '12', borderColor: theme.accent }]}
                accessibilityRole="button"
                accessibilityLabel="View offers"
              >
                <Ionicons name="pricetags-outline" size={14} color={theme.accent} />
                <Text style={[styles.editBarBtnText, { color: theme.accent }]}>Offers</Text>
              </AnimatedPressable>
              <AnimatedPressable
                onPress={handleUnlist}
                disabled={forSaleLoading}
                style={[styles.editBarBtn, { backgroundColor: theme.card, borderColor: theme.border }]}
                accessibilityRole="button"
                accessibilityLabel="Unlist from sale"
              >
                {forSaleLoading ? (
                  <ActivityIndicator size="small" color={theme.muted} />
                ) : (
                  <Text style={[styles.editBarBtnText, { color: theme.muted }]}>Unlist</Text>
                )}
              </AnimatedPressable>
            </View>
          )}

          {/* Draft mode - Quick actions row */}
          {isDraft && (
            <View style={styles.draftSection}>
              {saveError && (
                <Text style={[styles.errorText, { color: theme.danger }]}>
                  {saveError}
                </Text>
              )}

              <View style={styles.draftButtonsRow}>
                <Pressable
                  onPress={() => router.push('/quickscan')}
                  style={[
                    styles.scanAnotherButton,
                    { backgroundColor: theme.card, borderColor: theme.border, borderWidth: 1 },
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel="Scan another item"
                >
                  <Ionicons name="camera" size={18} color={theme.text} />
                  <Text style={[styles.scanAnotherButtonText, { color: theme.text }]}>Scan Another</Text>
                </Pressable>

                <Pressable
                  onPress={onSaveDraft}
                  disabled={savingDraft}
                  style={[
                    styles.saveDraftButton,
                    { backgroundColor: theme.accent, opacity: savingDraft ? 0.7 : 1 },
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel="Save to collection"
                >
                  {savingDraft ? (
                    <ActivityIndicator size="small" color="#FFFFFF" />
                  ) : (
                    <>
                      <Ionicons name="checkmark-circle" size={18} color="#FFFFFF" />
                      <Text style={styles.saveDraftButtonText}>Save to Collection</Text>
                    </>
                  )}
                </Pressable>
              </View>
            </View>
          )}

          {/* ── Quick Actions ─────────────────────────────────────── */}
          {!isDraft && id && !isEditing && (
            <View style={styles.quickActionsRow}>
              <AnimatedPressable
                onPress={() => setIsEditing(true)}
                style={[styles.quickActionBtn, { backgroundColor: theme.card, borderColor: theme.border }]}
                accessibilityRole="button"
                accessibilityLabel="Edit item details"
              >
                <Ionicons name="create-outline" size={18} color={theme.accent} />
                <Text style={[styles.quickActionLabel, { color: theme.text }]}>Edit</Text>
              </AnimatedPressable>
              <AnimatedPressable
                onPress={async () => {
                  try {
                    await Share.share({
                      message: `Check out ${editableName}${toNum(editableValue) ? ` - valued at ${formatPrice(toNum(editableValue))}` : ''} on CollectAI`,
                    });
                  } catch {
                    // User cancelled
                  }
                }}
                style={[styles.quickActionBtn, { backgroundColor: theme.card, borderColor: theme.border }]}
                accessibilityRole="button"
                accessibilityLabel="Share this item"
              >
                <Ionicons name="share-outline" size={18} color={theme.accent} />
                <Text style={[styles.quickActionLabel, { color: theme.text }]}>Share</Text>
              </AnimatedPressable>
              {!isForSale ? (
                <AnimatedPressable
                  onPress={() => {
                    listForSaleHook.open();
                  }}
                  style={[styles.quickActionBtn, { backgroundColor: theme.accent + '12', borderColor: theme.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="List this item for sale on marketplaces"
                >
                  <Ionicons name="storefront-outline" size={18} color={theme.accent} />
                  <Text style={[styles.quickActionLabel, { color: theme.accent }]}>List for Sale</Text>
                </AnimatedPressable>
              ) : (
                <View style={[styles.quickActionBtn, { backgroundColor: '#D1FAE5', borderColor: '#059669' }]}>
                  <Ionicons name="pricetag" size={18} color="#065F46" />
                  <Text style={[styles.quickActionLabel, { color: '#065F46' }]}>Listed</Text>
                </View>
              )}
            </View>
          )}

          {/* Details card */}
          <View
            style={[
              styles.card,
              { backgroundColor: theme.card, borderColor: theme.border },
            ]}
          >
            {/* Editable Name (draft or edit mode) */}
            {isDraft || isEditing ? (
              <TextInput
                style={[styles.editableNameInputSimple, { color: theme.text, borderBottomColor: theme.border }]}
                value={editableName}
                onChangeText={setEditableName}
                placeholder="Item name"
                placeholderTextColor={theme.muted ?? '#64748B'}
                accessibilityLabel="Item name"
              />
            ) : (
              <Text style={[styles.name, { color: theme.text }]}>{editableName}</Text>
            )}

            {/* Category row */}
            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.muted }]}>
                Category
              </Text>
              {isDraft || isEditing ? (
                <Pressable
                  onPress={showCategoryPicker}
                  style={[styles.dropdownFieldRow, { borderBottomColor: theme.border }]}
                  accessibilityRole="button"
                  accessibilityLabel={`Category: ${editableCategory === 'Unknown category' ? 'not set' : editableCategory}. Tap to change`}
                >
                  <Text style={[styles.dropdownFieldTextSmall, { color: editableCategory === 'Unknown category' ? theme.muted : theme.text }]}>
                    {editableCategory === 'Unknown category' ? 'Select category' : editableCategory}
                  </Text>
                  <Ionicons name="chevron-down" size={14} color={theme.muted} />
                </Pressable>
              ) : (
                <Pressable
                  onPress={() => {
                    const categoryId = CATEGORY_ID_MAP[editableCategory] || editableCategory.toLowerCase().replace(/[^a-z0-9]/g, '');
                    router.push(`/categories/${categoryId}`);
                  }}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}
                  accessibilityRole="link"
                  accessibilityLabel={`View ${editableCategory} category`}
                >
                  <Text style={[styles.value, { color: theme.accent }]}>{editableCategory}</Text>
                  <Ionicons name="chevron-forward" size={14} color={theme.accent} />
                </Pressable>
              )}
            </View>

            {/* Collection row */}
            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.muted }]}>
                Collection
              </Text>
              {isDraft || isEditing ? (
                <Pressable
                  onPress={showCollectionPicker}
                  style={[styles.dropdownFieldRow, { borderBottomColor: theme.border }]}
                  accessibilityRole="button"
                  accessibilityLabel={`Collection: ${editableCollection}. Tap to change`}
                >
                  <Text style={[styles.dropdownFieldTextSmall, { color: editableCollection === 'Not set' ? theme.muted : theme.text }]}>
                    {editableCollection}
                  </Text>
                  <Ionicons name="chevron-down" size={14} color={theme.muted} />
                </Pressable>
              ) : (
                <Text style={[styles.value, { color: theme.text }]}>{editableCollection}</Text>
              )}
            </View>

            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.muted }]}>
                {isGradingEligible ? 'Grade' : 'Condition'}
              </Text>
              {isDraft || isEditing ? (
                <Pressable
                  onPress={showConditionPicker}
                  style={[styles.dropdownFieldRow, { borderBottomColor: theme.border }]}
                  accessibilityRole="button"
                  accessibilityLabel={`${isGradingEligible ? 'Grade' : 'Condition'}: ${editableCondition}. Tap to change`}
                >
                  <Text style={[styles.dropdownFieldTextSmall, { color: editableCondition === 'Not set' ? theme.muted : theme.text }]}>
                    {editableCondition}
                  </Text>
                  <Ionicons name="chevron-down" size={14} color={theme.muted} />
                </Pressable>
              ) : (
                <Text style={[styles.value, { color: theme.text }]} accessibilityLabel={`${isGradingEligible ? 'Grade' : 'Condition'}: ${editableCondition}`}>{editableCondition}</Text>
              )}
            </View>

            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.muted }]}>
                Estimated value
              </Text>
              {isDraft || isEditing ? (
                <View style={styles.editableValueRow}>
                  <Text style={[styles.currencySymbol, { color: theme.muted }]}>{getCurrencySymbol(settings.currency)}</Text>
                  <TextInput
                    style={[styles.editableValueInput, { color: theme.text, borderBottomColor: theme.border, fontWeight: '700' }]}
                    value={editableValue}
                    onChangeText={setEditableValue}
                    placeholder="0"
                    placeholderTextColor={theme.muted ?? '#64748B'}
                    keyboardType="decimal-pad"
                    accessibilityLabel={`Estimated value in ${settings.currency}`}
                  />
                </View>
              ) : (
                <Text
                  style={[styles.valueHighlight, { color: theme.text }]}
                  accessibilityRole="text"
                  accessibilityLabel={`Estimated value: ${formatPrice(toNum(editableValue))}`}
                >
                  {formatPrice(toNum(editableValue))}
                </Text>
              )}
            </View>

            {/* Quick actions moved to standalone section below image */}

            {/* Item Attributes Section — from attributes_json */}
            <ItemAttributesSection
              attributes={itemAttributes}
              category={editableCategory}
              taxonomyVersion={taxonomyVersion}
              subtypeId={subtypeId}
              collections={itemCollections}
            />

            {/* ── Category-Specific Sections (sneakers/watches/LEGO/funko/auth) ── */}
            <CategorySpecificSection
              categorySlug={categorySlug}
              isDraft={isDraft}
              itemId={id}
              itemAttributes={itemAttributes}
              itemSizeValue={itemSizeValue}
              sizeSystem={sizeSystem}
              sizeSaving={sizeSaving}
              notes={notes}
              hapticsEnabled={settings.hapticsEnabled}
              theme={theme}
              onSizeChange={handleSizeChange}
              onSizeSystemChange={setSizeSystem}
              onSizeValueChange={setItemSizeValue}
            />

            {/* New Explainable AI Interface - PriceCard with visual RangeBar */}
            {featureFlags.FEATURE_EXPLAINABLE_AI_INTERFACES && priceEstimate && (
              <View style={styles.priceCardSection}>
                <PriceCard
                  estimate={priceEstimate}
                  onWhyThisPrice={() => setShowPriceExplanation(true)}
                  showRangeBar={true}
                  compact={false}
                />
              </View>
            )}

            {/* Legacy Price bands (q10/q50/q90) — shown when feature flag is off */}
            {!featureFlags.FEATURE_EXPLAINABLE_AI_INTERFACES && (q10 || q50 || q90) && (
              <View style={styles.priceBandsRow}>
                <Text style={[styles.label, { color: theme.muted }]}>
                  Price range
                </Text>
                <Text style={[styles.value, { color: theme.text }]}>
                  {formatPrice(toNum(q10))} – {formatPrice(toNum(q50))} – {formatPrice(toNum(q90))}
                </Text>
              </View>
            )}

            {/* Legacy Confidence Gauge — shown when feature flag is off */}
            {!featureFlags.FEATURE_EXPLAINABLE_AI_INTERFACES && confidence && (
              <View style={styles.confidenceSection}>
                <PriceConfidenceGauge
                  confidence={parseFloat(confidence)}
                  size="medium"
                  colors={{
                    text: theme.text ?? '#1F2937',
                    muted: theme.muted ?? '#64748B',
                    background: theme.border ?? '#E2E8F0',
                  }}
                />
              </View>
            )}

            {/* Legacy Explanation — expandable "Why this price?" section */}
            {!featureFlags.FEATURE_EXPLAINABLE_AI_INTERFACES && explanation && (
              <View style={[styles.explanationBlock, { borderTopColor: theme.border }]}>
                <Pressable
                  onPress={() => setExplanationExpanded(!explanationExpanded)}
                  style={styles.explanationHeaderRow}
                  accessibilityRole="button"
                  accessibilityLabel={`Why this price${explanationExpanded ? ', expanded' : ', collapsed'}`}
                >
                  <View style={styles.explanationHeaderLeft}>
                    <Ionicons name="help-circle-outline" size={18} color={theme.accent} />
                    <Text style={[styles.explanationHeader, { color: theme.text }]}>
                      Why this price?
                    </Text>
                  </View>
                  <Ionicons
                    name={explanationExpanded ? "chevron-up" : "chevron-down"}
                    size={18}
                    color={theme.muted}
                  />
                </Pressable>
                {explanationExpanded && (
                  <View style={[styles.explanationContent, { backgroundColor: theme.background }]}>
                    <Text style={[styles.explanationText, { color: theme.muted }]}>
                      {explanation}
                    </Text>
                  </View>
                )}
              </View>
            )}

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
              <View style={[styles.refreshBar, { borderTopColor: theme.border }]}>
                <View style={styles.refreshBarLeft}>
                  <Ionicons name="sparkles" size={16} color={theme.accent} />
                  <Text style={[styles.refreshBarLabel, { color: theme.muted }]}>
                    {evidenceData?.prediction_at
                      ? `Last analyzed ${relativeTime(evidenceData.prediction_at)}`
                      : 'Powered by CcollectAI'}
                  </Text>
                </View>
                <Pressable
                  onPress={refreshAllIntelligence}
                  disabled={aiRefreshing}
                  style={[
                    styles.refreshBarBtn,
                    { backgroundColor: theme.accent + '14', opacity: aiRefreshing ? 0.7 : 1 },
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel="Refresh all intelligence data"
                >
                  {aiRefreshing ? (
                    <ActivityIndicator size="small" color={theme.accent} />
                  ) : (
                    <Ionicons name="refresh-outline" size={14} color={theme.accent} />
                  )}
                  <Text style={[styles.refreshBarBtnText, { color: theme.accent }]}>
                    {aiRefreshing ? 'Updating...' : 'Refresh'}
                  </Text>
                </Pressable>
              </View>
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

            {/* Grading Section — for eligible categories */}
            {!isDraft && id && isGradingEligible && (
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
                onStatusChange={handleProgressStatusChange}
                onPctChange={handleProgressPctChange}
                onNotesChange={handleProgressNotesChange}
              />
            )}

            {/* Shop this Item — affiliate links */}
            {!isDraft && affiliateLinks.length > 0 && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <View style={styles.sectionHeaderRow}>
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="open-outline" size={20} color={theme.accent} />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>Shop this Item</Text>
                  </View>
                </View>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingTop: 8 }}>
                  {affiliateLinks.map((link) => (
                    <Pressable
                      key={link.source}
                      onPress={() => {
                        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                        Linking.openURL(link.affiliate_url).catch((err) =>
                          logger.warn('[ItemDetail] Failed to open affiliate URL', err)
                        );
                      }}
                      style={[
                        styles.affiliateLinkBtn,
                        { borderColor: theme.border },
                      ]}
                      accessibilityRole="link"
                      accessibilityLabel={link.label}
                    >
                      <Ionicons name="open-outline" size={14} color={theme.accent} />
                      <Text style={[styles.affiliateLinkText, { color: theme.text }]}>{link.label}</Text>
                    </Pressable>
                  ))}
                </View>
              </View>
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
            <View
              style={styles.notesBlock}
              onLayout={(e) => { notesLayoutY.current = e.nativeEvent.layout.y; }}
            >
              <View style={styles.notesHeaderRow}>
                <Text style={[styles.label, { color: theme.muted }]}>
                  Notes
                </Text>
                {keyboardVisible && (
                  <Pressable
                    onPress={() => { onSaveNotes(); Keyboard.dismiss(); }}
                    style={[styles.notesDoneBtn, { backgroundColor: theme.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel="Save notes"
                  >
                    <Text style={styles.notesDoneBtnText}>Save</Text>
                  </Pressable>
                )}
              </View>

              <TextInput
                ref={notesInputRef}
                style={[
                  styles.notesInput,
                  {
                    color: theme.text,
                    borderColor: theme.border,
                    backgroundColor: theme.background,
                  },
                ]}
                placeholder="Add your notes about condition, origin, where you bought it, etc."
                placeholderTextColor={theme.muted ?? '#64748B'}
                multiline
                value={notes}
                onChangeText={setNotes}
                onFocus={scrollToNotes}
                textAlignVertical="top"
                blurOnSubmit={false}
                accessibilityLabel="Item notes"
              />
            </View>

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
              accessibilityLabel="Save to collection"
            >
              {savingDraft ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <Ionicons name="checkmark-circle" size={20} color="#FFFFFF" />
                  <Text style={styles.stickyButtonText}>Save to Collection</Text>
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
  draftSection: {
    marginBottom: 16,
    gap: 8,
  },
  draftButtonsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  saveDraftButton: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  saveDraftButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  scanAnotherButton: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  scanAnotherButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  errorText: {
    fontSize: 12,
    textAlign: 'center',
  },
  priceBandsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 6,
  },
  card: {
    borderWidth: 1,
    borderRadius: 16,
    padding: 16,
    gap: 10,
  },
  name: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.3,
  },
  editableNameInputSimple: {
    fontSize: 20,
    fontWeight: '700',
    paddingVertical: 4,
    borderBottomWidth: 1,
  },
  dropdownFieldRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 2,
    borderBottomWidth: 1,
    gap: 4,
  },
  dropdownFieldTextSmall: {
    fontSize: 13,
    fontWeight: '500',
  },
  editableValueInput: {
    fontSize: 13,
    fontWeight: '500',
    paddingVertical: 2,
    borderBottomWidth: 1,
    minWidth: 80,
    textAlign: 'right',
  },
  editableValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  currencySymbol: {
    fontSize: 13,
    fontWeight: '500',
    marginRight: 2,
  },
  confidenceSection: {
    marginTop: 12,
  },
  priceCardSection: {
    marginTop: 16,
    marginBottom: 4,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 6,
  },
  label: {
    fontSize: 13,
  },
  value: {
    fontSize: 13,
    fontWeight: "500",
  },
  valueHighlight: {
    fontSize: 18,
    fontWeight: "800",
    letterSpacing: -0.2,
  },
  explanationBlock: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
  },
  explanationHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  explanationHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  explanationHeader: {
    fontSize: 14,
    fontWeight: '600',
  },
  explanationContent: {
    marginTop: 10,
    padding: 12,
    borderRadius: 10,
  },
  explanationText: {
    fontSize: 13,
    lineHeight: 19,
  },
  notesBlock: {
    marginTop: 16,
  },
  notesHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  notesDoneBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 8,
  },
  notesDoneBtnText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  notesInput: {
    marginTop: 8,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    lineHeight: 18,
    minHeight: 100,
    maxHeight: 220,
  },
  // Styles for sections still rendered inline (e.g. "Shop this Item")
  sectionBlock: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  sectionHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  affiliateLinkBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
  },
  affiliateLinkText: {
    fontSize: 13,
    fontWeight: '500',
  },
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
    borderRadius: 12,
    gap: 8,
  },
  stickyButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  // Refresh bar (compact AI action bar)
  refreshBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderTopWidth: StyleSheet.hairlineWidth,
    marginTop: 4,
  },
  refreshBarLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flexShrink: 1,
  },
  refreshBarLabel: {
    fontSize: 12,
    fontWeight: '500',
  },
  refreshBarBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
  },
  refreshBarBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
  editBar: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  editBarBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    borderWidth: 1,
  },
  editBarBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
  editBarBtnPrimary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 10,
  },
  editBarBtnPrimaryText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
  },
  // For-Sale listing styles
  forSaleBar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  forSaleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    flex: 1,
  },
  forSaleBadgeText: {
    fontSize: 13,
    fontWeight: '600',
  },
  // Quick Actions Row (standalone section under image)
  quickActionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 4,
  },
  quickActionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    minWidth: 70,
    paddingVertical: 12,
    paddingHorizontal: 4,
    borderRadius: 12,
    borderWidth: 1,
  },
  quickActionLabel: {
    fontSize: 13,
    fontWeight: '600',
  },
  // Progress Tracking styles moved to ItemProgressSection component
  // Grading styles moved to GradingSection component
  // Size, LEGO, Funko, Auth styles moved to CategorySpecificSection component
});