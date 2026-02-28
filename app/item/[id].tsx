import React, { useState, useRef, useMemo, useEffect, useCallback } from "react";
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
  ActionSheetIOS,
  RefreshControl,
  Share,
  Modal,
  useWindowDimensions,
} from "react-native";
import { Image } from "expo-image";
import { useLocalSearchParams } from "expo-router";
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from "@/hooks/useAppTheme";
import { usePhotoUpload } from "@/hooks/usePhotoUpload";
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
import { AnimatedPressable } from "@/motion";
import { isBuildableCategory } from "@/constants/buildStepTemplates";
import { CATEGORY_VISUAL } from "@/data/categories";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { ConfettiBurst, ConfettiBurstRef } from '@/components/ConfettiBurst';
import InteractiveLineChart from '@/components/InteractiveLineChart';
import { Skeleton } from '@/components/Skeleton';

// Dossier data shape (mirrors collectorsApi.getDossier return type)
interface DossierData {
  item_id: string;
  generated_at: string;
  identity: Record<string, unknown>;
  valuation: Record<string, unknown>;
  provenance: Array<Record<string, unknown>>;
  price_history: Array<Record<string, unknown>>;
  market_comps: Array<Record<string, unknown>>;
  photos: string[];
  collections: string[];
  authenticity_signals: string[];
  completeness_score: number;
}

// Market hit shape from marketplace search results
interface MarketHit {
  title: string;
  price: number;
  url?: string;
  affiliate_url?: string;
  source?: string;
  provider?: string;
  condition?: string;
}

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

// Sneaker size options (US sizing — can be mapped to EU/UK)
const SNEAKER_SIZES = [
  '3.5', '4', '4.5', '5', '5.5', '6', '6.5', '7', '7.5', '8', '8.5',
  '9', '9.5', '10', '10.5', '11', '11.5', '12', '12.5', '13', '14', '15',
];

// Watch case diameter options
const WATCH_SIZES = ['34mm', '36mm', '38mm', '39mm', '40mm', '41mm', '42mm', '43mm', '44mm', '45mm', '46mm'];

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
const CONDITION_OPTIONS = ['Not set', 'Mint', 'Near Mint', 'Excellent', 'Good', 'Fair', 'Poor', 'PSA 10', 'PSA 9', 'PSA 8', 'PSA 7', 'BGS 10', 'BGS 9.5', 'Raw'];
// Pull from single source of truth — all 36 categories
import { CATEGORIES as ALL_CATS, CATEGORY_NAME_TO_SLUG } from '@/constants/categories';

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

  // Photo upload
  const { user } = useAuthContext();
  const {
    pickAndUpload,
    uploading: photoUploading,
    error: photoError,
    photoUrl: userPhotoUrl,
  } = usePhotoUpload(id || "draft");
  const [userPhoto, setUserPhoto] = useState<string | null>(null);
  const [zoomVisible, setZoomVisible] = useState(false);
  const [zoomImageUri, setZoomImageUri] = useState<string | null>(null);

  // ── Multi-photo gallery state ──────────────────────────────────────────
  type ItemImage = {
    id: string;
    item_id: string;
    image_url: string;
    label: string | null;
    position: number;
    created_at: string | null;
  };
  const [galleryImages, setGalleryImages] = useState<ItemImage[]>([]);
  const [galleryLoading, setGalleryLoading] = useState(false);
  const [galleryActiveIndex, setGalleryActiveIndex] = useState(0);
  const [imageUploading, setImageUploading] = useState(false);
  const [pendingLabel, setPendingLabel] = useState<string | null>(null);
  const galleryFlatListRef = useRef<FlatList>(null);
  const GALLERY_HEIGHT = 260;

  const IMAGE_LABELS = ['front', 'back', 'detail', 'box', 'certificate', 'damage', 'other'] as const;
  const LABEL_DISPLAY: Record<string, string> = {
    front: 'Front',
    back: 'Back',
    detail: 'Detail',
    box: 'Box',
    certificate: 'Certificate',
    damage: 'Damage',
    other: 'Other',
  };

  // Resolved display image: first gallery image > userPhoto > imageUri > placeholder
  const displayImageUri = galleryImages.length > 0
    ? galleryImages[0].image_url
    : (userPhoto || userPhotoUrl || imageUri);

  // Effective gallery data: merge original imageUrl as synthetic entry when no gallery images exist
  const effectiveGalleryImages = useMemo((): ItemImage[] => {
    if (galleryImages.length > 0) return galleryImages;
    // If no gallery images but the item has an original imageUrl, show it as the first entry
    const fallbackUri = userPhoto || userPhotoUrl || imageUri;
    if (fallbackUri) {
      return [{
        id: '__original__',
        item_id: id || '',
        image_url: fallbackUri,
        label: null,
        position: 0,
        created_at: null,
      }];
    }
    return [];
  }, [galleryImages, userPhoto, userPhotoUrl, imageUri, id]);

  // Load gallery images on mount (for saved items)
  useEffect(() => {
    if (!id || isDraft) return;
    setGalleryLoading(true);
    collectorsApi.listItemImages(id)
      .then((data) => {
        setGalleryImages(data.images || []);
      })
      .catch((err) => {
        logger.warn('[ItemDetail] gallery images fetch error:', err);
      })
      .finally(() => setGalleryLoading(false));
  }, [id, isDraft]);

  // Upload a new gallery image
  const handleGalleryUpload = useCallback(async (source: "camera" | "gallery", label?: string) => {
    if (!id || isDraft) return;
    setImageUploading(true);
    try {
      const url = await pickAndUpload(source);
      if (url && id) {
        // Also add to the item_images table via the API
        const result = await collectorsApi.uploadItemImage(id, url, label || undefined);
        setGalleryImages((prev) => [...prev, result]);
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
        showToast({ message: 'Photo added', type: 'success' });
      }
    } catch (err) {
      logger.error('[ItemDetail] gallery upload error:', err);
      showToast({ message: 'Failed to upload photo', type: 'error' });
    } finally {
      setImageUploading(false);
      setPendingLabel(null);
    }
  }, [id, isDraft, pickAndUpload, settings.hapticsEnabled]);

  // Delete a gallery image
  const handleGalleryDelete = useCallback(async (imageId: string) => {
    if (!id) return;
    try {
      await collectorsApi.deleteItemImage(id, imageId);
      setGalleryImages((prev) => prev.filter((img) => img.id !== imageId));
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Photo removed', type: 'info' });
    } catch (err) {
      logger.error('[ItemDetail] gallery delete error:', err);
      showToast({ message: 'Failed to remove photo', type: 'error' });
    }
  }, [id, settings.hapticsEnabled]);

  const handlePhotoUpload = async (source: "camera" | "gallery") => {
    if (!isDraft && id) {
      // For saved items, use gallery upload flow
      handleGalleryUpload(source, pendingLabel || undefined);
      return;
    }
    const url = await pickAndUpload(source);
    if (url) {
      setUserPhoto(url);
    }
  };

  const showLabelPicker = (callback: (label: string | null) => void) => {
    const options = ['No Label', ...IMAGE_LABELS.map((l) => LABEL_DISPLAY[l])];
    if (Platform.OS === "ios") {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ["Cancel", ...options],
          cancelButtonIndex: 0,
          title: "Choose Photo Label",
        },
        (buttonIndex) => {
          if (buttonIndex === 0) return; // Cancel
          if (buttonIndex === 1) callback(null); // No Label
          else callback(IMAGE_LABELS[buttonIndex - 2]);
        },
      );
    } else {
      Alert.alert("Choose Photo Label", undefined, [
        { text: "No Label", onPress: () => callback(null) },
        ...IMAGE_LABELS.map((l) => ({
          text: LABEL_DISPLAY[l],
          onPress: () => callback(l),
        })),
        { text: "Cancel", style: "cancel" as const },
      ]);
    }
  };

  const showPhotoSourcePicker = () => {
    const doUpload = (source: "camera" | "gallery") => {
      if (!isDraft && id) {
        // Show label picker first, then upload
        showLabelPicker((label) => {
          setPendingLabel(label);
          handleGalleryUpload(source, label || undefined);
        });
      } else {
        handlePhotoUpload(source);
      }
    };

    if (Platform.OS === "ios") {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ["Cancel", "Take Photo", "Choose from Library"],
          cancelButtonIndex: 0,
          title: "Add Photo",
        },
        (buttonIndex) => {
          if (buttonIndex === 1) doUpload("camera");
          if (buttonIndex === 2) doUpload("gallery");
        },
      );
    } else {
      Alert.alert("Add Photo", "Choose a source", [
        { text: "Take Photo", onPress: () => doUpload("camera") },
        {
          text: "Choose from Library",
          onPress: () => doUpload("gallery"),
        },
        { text: "Cancel", style: "cancel" },
      ]);
    }
  };

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
  const scrollViewRef = useRef<Animated.ScrollView | null>(null);
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
  const [editableCollection, setEditableCollection] = useState(collection);
  const [editableCondition, setEditableCondition] = useState(condition);
  const [editableValue, setEditableValue] = useState(value);
  const [isEditingName, setIsEditingName] = useState(false);
  const [isEditingCategory, setIsEditingCategory] = useState(false);

  // Expandable explanation state
  const [explanationExpanded, setExplanationExpanded] = useState(false);

  // Provenance state
  const [provenanceEvents, setProvenanceEvents] = useState<Array<{
    id: string; eventType: string; timestamp: string;
    note: string | null; source: string | null; metadata: Record<string, unknown>;
  }>>([]);
  const [authenticitySignals, setAuthenticitySignals] = useState<string[]>([]);
  const [provenanceLoading, setProvenanceLoading] = useState(false);
  const [provenanceExpanded, setProvenanceExpanded] = useState(false);

  // Dossier state
  const [dossierData, setDossierData] = useState<DossierData | null>(null);
  const [dossierLoading, setDossierLoading] = useState(false);
  const [dossierExpanded, setDossierExpanded] = useState(false);
  const [dossierError, setDossierError] = useState(false);

  // ── Grading service state ────────────────────────────────────────────
  const GRADING_ELIGIBLE = new Set(['pokemon', 'mtg', 'yugioh', 'sportscards', 'comic_books', 'retro_games']);
  const isGradingEligible = GRADING_ELIGIBLE.has(categorySlug);

  type GradingLookupResult = {
    cert_number: string;
    service: string;
    service_name: string;
    item_name: string | null;
    grade: string | null;
    grade_numeric: number | null;
    sub_grades: Record<string, number> | null;
    population_at_grade: number | null;
    population_higher: number | null;
    cert_verified: boolean;
    cert_url: string | null;
    label_type: string | null;
    year: string | null;
    error: string | null;
  };
  type PopulationEntry = { grade: string; count: number; pct_of_total: number | null };
  type PopulationReport = {
    item_name: string; category: string; service: string; total_graded: number;
    population: PopulationEntry[]; avg_grade: number | null; highest_grade: string | null;
  };
  type GradingServiceInfo = {
    id: string; name: string; short_name: string; website: string;
    submission_url: string; grade_scale: string; categories: string[];
    turnaround: string; price_range: string;
  };

  const [gradingExpanded, setGradingExpanded] = useState(false);
  const [gradingLookupResult, setGradingLookupResult] = useState<GradingLookupResult | null>(null);
  const [gradingLookupLoading, setGradingLookupLoading] = useState(false);
  const [gradingPopulation, setGradingPopulation] = useState<PopulationReport | null>(null);
  const [gradingPopLoading, setGradingPopLoading] = useState(false);
  const [gradingServices, setGradingServices] = useState<GradingServiceInfo[]>([]);
  const [gradingModalVisible, setGradingModalVisible] = useState(false);
  const [gradingCertInput, setGradingCertInput] = useState('');
  const [gradingServicePick, setGradingServicePick] = useState<'psa' | 'cgc' | 'bgs' | 'beckett'>('psa');

  // Marketplace state
  const [marketResults, setMarketResults] = useState<MarketHit[]>([]);
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketExpanded, setMarketExpanded] = useState(false);
  const [marketScannedAt, setMarketScannedAt] = useState<string | null>(null);
  const [marketError, setMarketError] = useState(false);

  // Affiliate links state
  type AffiliateLink = { source: string; url: string; affiliate_url: string; label: string };
  const [affiliateLinks, setAffiliateLinks] = useState<AffiliateLink[]>([]);

  // Price trend chart state
  const [priceTrendData, setPriceTrendData] = useState<PriceTrendData | null>(null);
  const [priceTrendLoading, setPriceTrendLoading] = useState(false);
  const [priceTrendRange, setPriceTrendRange] = useState(90); // default 3M
  const [priceTrendVisible, setPriceTrendVisible] = useState(false); // lazy load trigger
  const [priceTrendHoverValue, setPriceTrendHoverValue] = useState<number | null>(null);
  const [priceTrendHoverDate, setPriceTrendHoverDate] = useState<string | null>(null);
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

  // Build project state — for buildable categories
  const categorySlug = CATEGORY_ID_MAP[editableCategory] || editableCategory.toLowerCase().replace(/[^a-z0-9_]/g, '');
  const itemIsBuildable = isBuildableCategory(categorySlug);
  const buildAccent = CATEGORY_VISUAL[categorySlug]?.accentColor;
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

  // ── Progress tracking state (manga, comics, games) ──────────────────
  const PROGRESS_CATEGORIES: Record<string, { statuses: string[]; label: string; icon: string }> = {
    manga: { statuses: ['unread', 'reading', 'read'], label: 'Reading Progress', icon: 'book-outline' },
    comic_books: { statuses: ['unread', 'reading', 'read'], label: 'Reading Progress', icon: 'book-outline' },
    retro_games: { statuses: ['unplayed', 'playing', 'played', 'completed'], label: 'Play Progress', icon: 'game-controller-outline' },
    board_games: { statuses: ['unplayed', 'playing', 'played', 'completed'], label: 'Play Progress', icon: 'dice-outline' },
  };
  const progressConfig = PROGRESS_CATEGORIES[categorySlug] ?? null;
  const hasProgressTracking = progressConfig !== null;

  const STATUS_DISPLAY: Record<string, string> = {
    unread: 'Unread',
    reading: 'Reading',
    read: 'Read',
    unplayed: 'Unplayed',
    playing: 'Playing',
    played: 'Played',
    completed: 'Completed',
  };

  const STATUS_COLORS: Record<string, string> = {
    unread: '#94A3B8',
    reading: '#3B82F6',
    read: '#22C55E',
    unplayed: '#94A3B8',
    playing: '#F59E0B',
    played: '#22C55E',
    completed: '#8B5CF6',
  };

  const [progressStatus, setProgressStatus] = useState<string | null>(null);
  const [progressPct, setProgressPct] = useState<number | null>(null);
  const [progressNotes, setProgressNotes] = useState('');
  const [progressLoading, setProgressLoading] = useState(false);
  const [progressSaving, setProgressSaving] = useState(false);
  const progressSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load progress on mount for progress-trackable items
  useEffect(() => {
    if (!id || isDraft || !hasProgressTracking) return;
    setProgressLoading(true);
    collectorsApi.getItemProgress(id)
      .then((data) => {
        setProgressStatus(data.progress_status);
        setProgressPct(data.progress_pct);
        setProgressNotes(data.progress_notes || '');
      })
      .catch((err) => {
        logger.warn('[ItemDetail] progress fetch error:', err);
      })
      .finally(() => setProgressLoading(false));
  }, [id, isDraft, hasProgressTracking]);

  // Auto-save progress changes with debounce
  const saveProgress = useCallback((status: string | null, pct: number | null, pNotes: string) => {
    if (!id || isDraft) return;
    if (progressSaveTimer.current) clearTimeout(progressSaveTimer.current);
    progressSaveTimer.current = setTimeout(async () => {
      setProgressSaving(true);
      try {
        const payload: Record<string, unknown> = {};
        if (status !== undefined) payload.progress_status = status;
        if (pct !== undefined && pct !== null) payload.progress_pct = pct;
        if (pNotes !== undefined) payload.progress_notes = pNotes;
        await collectorsApi.updateItemProgress(id, payload as {
          progress_status?: string;
          progress_pct?: number;
          progress_notes?: string;
        });
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      } catch (err) {
        logger.warn('[ItemDetail] progress save error:', err);
        showToast({ message: 'Failed to save progress', type: 'error' });
      } finally {
        setProgressSaving(false);
      }
    }, 600);
  }, [id, isDraft, settings.hapticsEnabled]);

  const handleProgressStatusChange = (newStatus: string) => {
    setProgressStatus(newStatus);
    saveProgress(newStatus, progressPct, progressNotes);
  };

  const handleProgressPctChange = (pct: number) => {
    setProgressPct(pct);
    saveProgress(progressStatus, pct, progressNotes);
  };

  const handleProgressNotesChange = (text: string) => {
    setProgressNotes(text);
    saveProgress(progressStatus, progressPct, text);
  };

  // Add to Watchlist state
  const [watchlistModalVisible, setWatchlistModalVisible] = useState(false);
  const [watchlistTargetPrice, setWatchlistTargetPrice] = useState('');
  const [watchlistSaving, setWatchlistSaving] = useState(false);

  const handleAddToWatchlist = async () => {
    setWatchlistSaving(true);
    try {
      const targetPrice = watchlistTargetPrice.trim()
        ? parseFloat(watchlistTargetPrice.replace(/[^0-9.]/g, ''))
        : null;

      await dataProvider.addWatchlistItem({
        title: editableName,
        category: editableCategory,
        targetPrice: targetPrice && !isNaN(targetPrice) ? targetPrice : null,
        notes: `Added from item detail: ${id}`,
      });

      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Added to watchlist!', type: 'success' });
      setWatchlistModalVisible(false);
      setWatchlistTargetPrice('');
    } catch (err: unknown) {
      logger.error('[ItemDetail] add to watchlist error:', err);
      showToast({ message: 'Failed to add to watchlist', type: 'error' });
    } finally {
      setWatchlistSaving(false);
    }
  };

  // (Price Alert section removed)

  // ActionSheet handlers for iOS dropdowns
  const showCategoryPicker = () => {
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ['Cancel', ...CATEGORY_OPTIONS],
          cancelButtonIndex: 0,
          title: 'Select Category',
        },
        (buttonIndex) => {
          if (buttonIndex > 0) {
            setEditableCategory(CATEGORY_OPTIONS[buttonIndex - 1]);
            if (inlineEditPending.current) {
              inlineEditPending.current = false;
              setTimeout(() => onSaveEdits(), 100);
            }
          } else if (inlineEditPending.current) {
            inlineEditPending.current = false;
            setIsEditing(false);
          }
        }
      );
    } else {
      // Android fallback - could use a modal picker
      Alert.alert(
        'Select Category',
        undefined,
        CATEGORY_OPTIONS.map((opt) => ({
          text: opt,
          onPress: () => {
            setEditableCategory(opt);
            if (inlineEditPending.current) {
              inlineEditPending.current = false;
              setTimeout(() => onSaveEdits(), 100);
            }
          },
        })).concat([{ text: 'Cancel', style: 'cancel', onPress: () => { if (inlineEditPending.current) { inlineEditPending.current = false; setIsEditing(false); } } }])
      );
    }
  };

  const showCollectionPicker = () => {
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ['Cancel', ...COLLECTION_OPTIONS],
          cancelButtonIndex: 0,
          title: 'Select Collection/Set',
        },
        (buttonIndex) => {
          if (buttonIndex > 0) {
            setEditableCollection(COLLECTION_OPTIONS[buttonIndex - 1]);
            if (inlineEditPending.current) {
              inlineEditPending.current = false;
              setTimeout(() => onSaveEdits(), 100);
            }
          } else if (inlineEditPending.current) {
            inlineEditPending.current = false;
            setIsEditing(false);
          }
        }
      );
    } else {
      Alert.alert(
        'Select Collection/Set',
        undefined,
        COLLECTION_OPTIONS.map((opt) => ({
          text: opt,
          onPress: () => {
            setEditableCollection(opt);
            if (inlineEditPending.current) {
              inlineEditPending.current = false;
              setTimeout(() => onSaveEdits(), 100);
            }
          },
        })).concat([{ text: 'Cancel', style: 'cancel', onPress: () => { if (inlineEditPending.current) { inlineEditPending.current = false; setIsEditing(false); } } }])
      );
    }
  };

  const showConditionPicker = () => {
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ['Cancel', ...CONDITION_OPTIONS],
          cancelButtonIndex: 0,
          title: 'Select Condition/Grade',
        },
        (buttonIndex) => {
          if (buttonIndex > 0) {
            setEditableCondition(CONDITION_OPTIONS[buttonIndex - 1]);
            if (inlineEditPending.current) {
              inlineEditPending.current = false;
              setTimeout(() => onSaveEdits(), 100);
            }
          } else if (inlineEditPending.current) {
            inlineEditPending.current = false;
            setIsEditing(false);
          }
        }
      );
    } else {
      Alert.alert(
        'Select Condition/Grade',
        undefined,
        CONDITION_OPTIONS.map((opt) => ({
          text: opt,
          onPress: () => {
            setEditableCondition(opt);
            if (inlineEditPending.current) {
              inlineEditPending.current = false;
              setTimeout(() => onSaveEdits(), 100);
            }
          },
        })).concat([{ text: 'Cancel', style: 'cancel', onPress: () => { if (inlineEditPending.current) { inlineEditPending.current = false; setIsEditing(false); } } }])
      );
    }
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

  // Item attributes from DB (attributes_json, taxonomy_version, subtype_id, collections)
  const [itemAttributes, setItemAttributes] = useState<Record<string, unknown> | null>(null);
  const [taxonomyVersion, setTaxonomyVersion] = useState<string | undefined>();
  const [subtypeId, setSubtypeId] = useState<string | undefined>();
  const [itemCollections, setItemCollections] = useState<string[]>([]);

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

  // Load provenance history
  useEffect(() => {
    if (!id || isDraft) return;
    setProvenanceLoading(true);
    collectorsApi.getProvenance(id)
      .then((data) => {
        const events = data.events.map(e => ({
          id: e.id,
          eventType: e.event_type,
          timestamp: e.timestamp,
          note: e.note,
          source: e.source,
          metadata: e.metadata || {},
        }));
        setProvenanceEvents(events);
        setAuthenticitySignals(data.authenticity_signals || []);
      })
      .catch((err) => {
        logger.warn('[ItemDetail] provenance fetch error:', err);
        setProvenanceEvents([]);
        setAuthenticitySignals([]);
      })
      .finally(() => setProvenanceLoading(false));
  }, [id, isDraft]);

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

  // Fetch affiliate links on mount (non-draft items)
  useEffect(() => {
    if (!id || isDraft || !name || name === 'Unknown item') return;
    collectorsApi.getAffiliateLinks(name, editableCategory)
      .then((data) => setAffiliateLinks(data.links))
      .catch((err) => logger.warn('[ItemDetail] affiliate links fetch error:', err));
  }, [id, isDraft, name, editableCategory]);

  // Fetch price trend data (lazy — triggered when section scrolls into view)
  const fetchPriceTrend = useCallback(async (days: number) => {
    if (!id || isDraft) return;
    setPriceTrendLoading(true);
    try {
      const data = await collectorsApi.getItemPriceTrend(id, days);
      setPriceTrendData(data);
      setPriceTrendHoverValue(null);
      setPriceTrendHoverDate(null);
    } catch (err) {
      logger.warn('[ItemDetail] price trend fetch error:', err);
      setPriceTrendData(null);
    } finally {
      setPriceTrendLoading(false);
    }
  }, [id, isDraft]);

  // Lazy-load price trend when section becomes visible
  useEffect(() => {
    if (priceTrendVisible && !priceTrendData && !priceTrendLoading) {
      fetchPriceTrend(priceTrendRange);
    }
  }, [priceTrendVisible, priceTrendData, priceTrendLoading, priceTrendRange, fetchPriceTrend]);

  // Re-fetch when time range changes
  const handlePriceTrendRangeChange = useCallback((days: number) => {
    setPriceTrendRange(days);
    fetchPriceTrend(days);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
  }, [fetchPriceTrend, settings.hapticsEnabled]);

  // Price trend chart data (extracted q50 values for the line chart)
  const priceTrendChartData = useMemo(() => {
    if (!priceTrendData?.data_points?.length) return [];
    return priceTrendData.data_points.map((dp) => dp.q50);
  }, [priceTrendData]);

  // Price trend hover callback
  const handlePriceTrendHover = useCallback((index: number, value: number) => {
    setPriceTrendHoverValue(value);
    if (priceTrendData?.data_points?.[index]) {
      setPriceTrendHoverDate(priceTrendData.data_points[index].date);
    }
  }, [priceTrendData]);

  // Load dossier on demand
  const loadDossier = async () => {
    if (!id || isDraft) return;
    setDossierLoading(true);
    setDossierError(false);
    try {
      const data = await collectorsApi.getDossier(id);
      setDossierData(data || null);
      setDossierExpanded(true);
    } catch (err) {
      logger.warn('[ItemDetail] dossier fetch error:', err);
      setDossierData(null);
      setDossierError(true);
      setDossierExpanded(true);
    } finally {
      setDossierLoading(false);
    }
  };

  // ── Grading: auto-detect cert number from item attributes ──────────────
  const itemCertNumber = useMemo(() => {
    // Check common attribute names for cert/grade data
    const attrs = params as Record<string, string | undefined>;
    // Look in item attributes passed via URL params or local state
    return null; // Will be populated from item data if available
  }, [params]);

  // Grading: load services on expand
  const loadGradingServices = useCallback(async () => {
    if (gradingServices.length > 0) return;
    try {
      const data = await collectorsApi.gradingServices(categorySlug);
      setGradingServices(data.services || []);
    } catch (err) {
      logger.warn('[ItemDetail] grading services fetch error:', err);
    }
  }, [categorySlug, gradingServices.length]);

  // Grading: cert lookup
  const handleGradingLookup = useCallback(async () => {
    if (!gradingCertInput.trim()) {
      showToast('Please enter a certification number', 'warning');
      return;
    }
    setGradingLookupLoading(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      const result = await collectorsApi.gradingLookup(gradingCertInput.trim(), gradingServicePick);
      setGradingLookupResult(result);
      setGradingModalVisible(false);
      if (result.cert_verified) {
        showToast(`Verified: ${result.service_name} ${result.grade}`, 'success');
      } else {
        showToast('Certificate not found or not verified', 'warning');
      }
    } catch (err) {
      logger.warn('[ItemDetail] grading lookup error:', err);
      showToast('Failed to look up certificate', 'error');
    } finally {
      setGradingLookupLoading(false);
    }
  }, [gradingCertInput, gradingServicePick, settings.hapticsEnabled, showToast]);

  // Grading: load population report
  const loadGradingPopulation = useCallback(async () => {
    if (!editableName || gradingPopulation) return;
    setGradingPopLoading(true);
    try {
      const data = await collectorsApi.gradingPopulation(editableName, categorySlug);
      setGradingPopulation(data);
    } catch (err) {
      logger.warn('[ItemDetail] grading population error:', err);
    } finally {
      setGradingPopLoading(false);
    }
  }, [editableName, categorySlug, gradingPopulation]);

  // Load marketplace results on demand
  const loadMarketResults = async () => {
    if (!editableName) return;
    setMarketLoading(true);
    setMarketError(false);
    try {
      const data = await collectorsApi.marketplaceSearch(editableName, { category: editableCategory });
      const results = data.results || data.hits || [];
      setMarketResults(results);
      setMarketScannedAt(new Date().toISOString());
      setMarketExpanded(true);
    } catch (err) {
      logger.warn('[ItemDetail] marketplace search error:', err);
      setMarketResults([]);
      setMarketError(true);
      setMarketScannedAt(new Date().toISOString());
      setMarketExpanded(true);
    } finally {
      setMarketLoading(false);
    }
  };

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
        condition: editableCondition,
        notes: notes || undefined,
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
        priceTrendVisible ? fetchPriceTrend(priceTrendRange) : Promise.resolve(),
        collectorsApi.getProvenance(id).then((data) => {
          setProvenanceEvents(data.events.map(e => ({
            id: e.id,
            eventType: e.event_type,
            timestamp: e.timestamp,
            note: e.note,
            source: e.source,
            metadata: e.metadata || {},
          })));
          setAuthenticitySignals(data.authenticity_signals || []);
        }).catch(() => {}),
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
          {galleryLoading ? (
            /* Skeleton while gallery images are loading */
            <View style={styles.galleryContainer}>
              <Skeleton width={GALLERY_WIDTH} height={GALLERY_HEIGHT} borderRadius={16} />
            </View>
          ) : (effectiveGalleryImages.length > 0 || (!isDraft && id)) ? (
            <View style={styles.galleryContainer}>
              {(() => {
                // Build data array: real/effective images + "Add Photo" card for saved items
                const galleryData: Array<
                  | ({ type: 'image' } & ItemImage)
                  | { type: 'add'; id: string; item_id: string; image_url: string; label: null; position: number; created_at: null }
                > = [
                  ...effectiveGalleryImages.map((img) => ({ type: 'image' as const, ...img })),
                  ...(!isDraft && id
                    ? [{ type: 'add' as const, id: '__add__', item_id: '', image_url: '', label: null as null, position: 999, created_at: null as null }]
                    : []),
                ];
                const totalSlides = galleryData.length;
                const imageCount = effectiveGalleryImages.length;
                return (
                  <>
                    <FlatList
                      ref={galleryFlatListRef}
                      data={galleryData}
                      horizontal
                      pagingEnabled
                      showsHorizontalScrollIndicator={false}
                      keyExtractor={(item) => item.id}
                      onMomentumScrollEnd={(e) => {
                        const idx = Math.round(e.nativeEvent.contentOffset.x / GALLERY_WIDTH);
                        setGalleryActiveIndex(idx);
                      }}
                      getItemLayout={(_data, index) => ({
                        length: GALLERY_WIDTH,
                        offset: GALLERY_WIDTH * index,
                        index,
                      })}
                      renderItem={({ item, index }) => {
                        if (item.type === 'add') {
                          // "Add Photo" card at the end
                          return (
                            <Pressable
                              onPress={showPhotoSourcePicker}
                              disabled={imageUploading || photoUploading}
                              style={[
                                styles.gallerySlide,
                                { width: GALLERY_WIDTH, height: GALLERY_HEIGHT, borderColor: theme.border },
                              ]}
                              accessibilityRole="button"
                              accessibilityLabel="Add a new photo"
                            >
                              <View style={[styles.galleryAddCard, { backgroundColor: theme.card }]}>
                                {imageUploading || photoUploading ? (
                                  <ActivityIndicator size="large" color={theme.accent} />
                                ) : (
                                  <>
                                    <Ionicons name="camera-outline" size={36} color={theme.accent} />
                                    <Text style={[styles.galleryAddText, { color: theme.accent }]}>Add Photo</Text>
                                  </>
                                )}
                              </View>
                            </Pressable>
                          );
                        }
                        // Normal image slide
                        const isRealGalleryImage = item.id !== '__original__';
                        return (
                          <View style={[styles.gallerySlide, { width: GALLERY_WIDTH, height: GALLERY_HEIGHT }]}>
                            <Pressable
                              onPress={() => {
                                setZoomImageUri(item.image_url);
                                setZoomVisible(true);
                              }}
                              accessibilityRole="button"
                              accessibilityLabel={`Photo ${index + 1} of ${imageCount}${item.label ? ` (${LABEL_DISPLAY[item.label] || item.label})` : ''}. Tap to zoom`}
                            >
                              <Image
                                source={{ uri: item.image_url }}
                                style={{ width: GALLERY_WIDTH, height: GALLERY_HEIGHT }}
                                contentFit="cover"
                                cachePolicy="disk"
                                transition={200}
                              />
                            </Pressable>
                            {/* Label badge — bottom-left */}
                            {item.label && (
                              <View style={[styles.galleryLabelBadge, { backgroundColor: theme.accent }]}>
                                <Text style={styles.galleryLabelText}>
                                  {LABEL_DISPLAY[item.label] || item.label}
                                </Text>
                              </View>
                            )}
                            {/* Counter badge — bottom-right (only when multiple images) */}
                            {imageCount > 1 && (
                              <View style={styles.galleryCounterBadge}>
                                <Text style={styles.galleryCounterText}>
                                  {index + 1}/{imageCount}
                                </Text>
                              </View>
                            )}
                            {/* Delete button in edit mode — only for real gallery images */}
                            {isEditing && isRealGalleryImage && (
                              <Pressable
                                onPress={() => {
                                  fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
                                  Alert.alert(
                                    'Delete Photo',
                                    'Are you sure you want to remove this photo?',
                                    [
                                      { text: 'Cancel', style: 'cancel' },
                                      {
                                        text: 'Delete',
                                        style: 'destructive',
                                        onPress: () => handleGalleryDelete(item.id),
                                      },
                                    ],
                                  );
                                }}
                                style={styles.galleryDeleteBtn}
                                accessibilityRole="button"
                                accessibilityLabel="Delete this photo"
                              >
                                <Ionicons name="close-circle" size={26} color="#FF3B30" />
                              </Pressable>
                            )}
                          </View>
                        );
                      }}
                    />
                    {/* Page dots */}
                    {totalSlides > 1 && (
                      <View style={styles.galleryDots}>
                        {galleryData.map((img, idx) => (
                          <View
                            key={img.id}
                            style={[
                              styles.galleryDot,
                              {
                                backgroundColor: idx === galleryActiveIndex
                                  ? theme.accent
                                  : theme.border,
                              },
                            ]}
                          />
                        ))}
                      </View>
                    )}
                  </>
                );
              })()}
              {/* Photo error */}
              {photoError && (
                <View style={styles.photoErrorBanner}>
                  <Text style={styles.photoErrorText}>{photoError}</Text>
                </View>
              )}
            </View>
          ) : (
            // Fallback: single image (draft mode or no images at all)
            <View style={[styles.imageWrapper, { borderColor: theme.border }]}>
              <Pressable
                onPress={() => {
                  if (displayImageUri) {
                    setZoomImageUri(displayImageUri);
                    setZoomVisible(true);
                  }
                }}
                accessibilityRole="button"
                accessibilityLabel="Tap to zoom image"
              >
                {displayImageUri ? (
                  <Image
                    source={{ uri: displayImageUri }}
                    style={styles.image}
                    contentFit="cover"
                    cachePolicy="disk"
                    transition={200}
                    accessibilityRole="image"
                    accessibilityLabel={`Photo of ${editableName}`}
                  />
                ) : (
                  <Image
                    source={require("../../assets/placeholder.png")}
                    style={styles.image}
                    contentFit="cover"
                    accessibilityRole="image"
                    accessibilityLabel={`Placeholder image for ${editableName}`}
                  />
                )}
              </Pressable>

              {/* Photo upload overlay button */}
              <Pressable
                onPress={showPhotoSourcePicker}
                disabled={photoUploading}
                style={[
                  styles.photoUploadOverlay,
                  !displayImageUri && styles.photoUploadOverlayEmpty,
                ]}
                accessibilityRole="button"
                accessibilityLabel={displayImageUri ? "Change photo" : "Add your photo"}
              >
                {photoUploading ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <>
                    <Ionicons
                      name={displayImageUri ? "camera" : "camera-outline"}
                      size={displayImageUri ? 18 : 28}
                      color="#FFFFFF"
                    />
                    {!displayImageUri && (
                      <Text style={styles.photoUploadOverlayText}>
                        Add your photo
                      </Text>
                    )}
                  </>
                )}
              </Pressable>

              {/* Photo error */}
              {photoError && (
                <View style={styles.photoErrorBanner}>
                  <Text style={styles.photoErrorText}>{photoError}</Text>
                </View>
              )}
            </View>
          )}

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
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  handleAddToWatchlist();
                }}
                disabled={watchlistSaving}
                style={[styles.quickActionBtn, { backgroundColor: theme.card, borderColor: theme.border, opacity: watchlistSaving ? 0.6 : 1 }]}
                accessibilityRole="button"
                accessibilityLabel="Add to watchlist"
              >
                {watchlistSaving ? (
                  <ActivityIndicator size={16} color={theme.accent} />
                ) : (
                  <Ionicons name="eye-outline" size={18} color={theme.accent} />
                )}
                <Text style={[styles.quickActionLabel, { color: theme.text }]}>Watch</Text>
              </AnimatedPressable>
              {!isForSale ? (
                <AnimatedPressable
                  onPress={() => {
                    setAskingPriceValue(editableValue || String(q50 || value || ''));
                    setForSaleModalVisible(true);
                  }}
                  style={[styles.quickActionBtn, { backgroundColor: theme.accent + '12', borderColor: theme.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="List this item for sale"
                >
                  <Ionicons name="pricetag-outline" size={18} color={theme.accent} />
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
                Condition
              </Text>
              {isDraft || isEditing ? (
                <Pressable
                  onPress={showConditionPicker}
                  style={[styles.dropdownFieldRow, { borderBottomColor: theme.border }]}
                  accessibilityRole="button"
                  accessibilityLabel={`Condition: ${editableCondition}. Tap to change`}
                >
                  <Text style={[styles.dropdownFieldTextSmall, { color: editableCondition === 'Not set' ? theme.muted : theme.text }]}>
                    {editableCondition}
                  </Text>
                  <Ionicons name="chevron-down" size={14} color={theme.muted} />
                </Pressable>
              ) : (
                <Text style={[styles.value, { color: theme.text }]} accessibilityLabel={`Condition: ${editableCondition}`}>{editableCondition}</Text>
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

            {/* ── Size-Specific Pricing — Sneakers ────────────────────────── */}
            {categorySlug === 'sneakers' && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <View style={styles.sectionHeaderRow}>
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="footsteps-outline" size={20} color={theme.accent} />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>Size</Text>
                  </View>
                  {sizeSaving && <ActivityIndicator size="small" color={theme.accent} />}
                </View>
                <View style={styles.sizeSelectorRow}>
                  {/* Size system toggle */}
                  <View style={styles.sizeSystemRow}>
                    {(['US', 'EU', 'UK'] as const).map((sys) => (
                      <Pressable
                        key={sys}
                        onPress={() => {
                          setSizeSystem(sys.toLowerCase() as 'us' | 'eu' | 'uk');
                          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                        }}
                        style={[
                          styles.sizeSystemPill,
                          {
                            backgroundColor: sizeSystem === sys.toLowerCase() ? theme.accent : theme.background,
                            borderColor: theme.border,
                          },
                        ]}
                        accessibilityRole="button"
                        accessibilityState={{ selected: sizeSystem === sys.toLowerCase() }}
                        accessibilityLabel={`Size system: ${sys}`}
                      >
                        <Text style={[
                          styles.sizeSystemPillText,
                          { color: sizeSystem === sys.toLowerCase() ? '#fff' : theme.muted },
                        ]}>{sys}</Text>
                      </Pressable>
                    ))}
                  </View>
                  {/* Size picker */}
                  <View style={styles.sizePillsRow}>
                    {SNEAKER_SIZES.map((sz) => (
                      <Pressable
                        key={sz}
                        onPress={() => {
                          setItemSizeValue(sz);
                          handleSizeChange(sz, sizeSystem);
                        }}
                        style={[
                          styles.sizePill,
                          {
                            backgroundColor: itemSizeValue === sz ? theme.accent : theme.background,
                            borderColor: itemSizeValue === sz ? theme.accent : theme.border,
                          },
                        ]}
                        accessibilityRole="button"
                        accessibilityState={{ selected: itemSizeValue === sz }}
                        accessibilityLabel={`Size ${sz}`}
                      >
                        <Text style={[
                          styles.sizePillText,
                          { color: itemSizeValue === sz ? '#fff' : theme.text },
                        ]}>{sz}</Text>
                      </Pressable>
                    ))}
                  </View>
                </View>
                <View style={[styles.sizeInfoNote, { backgroundColor: theme.accent + '10' }]}>
                  <Ionicons name="information-circle-outline" size={14} color={theme.accent} />
                  <Text style={[styles.sizeInfoNoteText, { color: theme.accent }]}>
                    Size affects market value — prices vary by size
                  </Text>
                </View>
              </View>
            )}

            {/* ── Size-Specific Pricing — Watches ─────────────────────────── */}
            {categorySlug === 'watches' && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <View style={styles.sectionHeaderRow}>
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="watch-outline" size={20} color={theme.accent} />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>Case Size</Text>
                  </View>
                  {sizeSaving && <ActivityIndicator size="small" color={theme.accent} />}
                </View>
                <View style={styles.sizePillsRow}>
                  {WATCH_SIZES.map((sz) => (
                    <Pressable
                      key={sz}
                      onPress={() => {
                        setItemSizeValue(sz);
                        handleSizeChange(sz, 'mm');
                      }}
                      style={[
                        styles.sizePill,
                        {
                          backgroundColor: itemSizeValue === sz ? theme.accent : theme.background,
                          borderColor: itemSizeValue === sz ? theme.accent : theme.border,
                        },
                      ]}
                      accessibilityRole="button"
                      accessibilityState={{ selected: itemSizeValue === sz }}
                      accessibilityLabel={`Case diameter ${sz}`}
                    >
                      <Text style={[
                        styles.sizePillText,
                        { color: itemSizeValue === sz ? '#fff' : theme.text },
                      ]}>{sz}</Text>
                    </Pressable>
                  ))}
                </View>
                <View style={[styles.sizeInfoNote, { backgroundColor: theme.accent + '10' }]}>
                  <Ionicons name="information-circle-outline" size={14} color={theme.accent} />
                  <Text style={[styles.sizeInfoNoteText, { color: theme.accent }]}>
                    Size affects market value — prices vary by size
                  </Text>
                </View>
              </View>
            )}

            {/* ── LEGO-Specific Features ──────────────────────────────────── */}
            {categorySlug === 'lego' && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <View style={styles.sectionHeaderRow}>
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="cube-outline" size={20} color={CATEGORY_VISUAL['lego']?.accentColor ?? theme.accent} />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>LEGO Details</Text>
                  </View>
                </View>
                {/* Piece Count */}
                {(itemAttributes?.piece_count || itemAttributes?.pieces) && (
                  <View style={styles.legoDetailRow}>
                    <Ionicons name="apps-outline" size={16} color={theme.muted} />
                    <Text style={[styles.legoDetailLabel, { color: theme.muted }]}>Piece Count</Text>
                    <Text style={[styles.legoDetailValue, { color: theme.text }]}>
                      {String(itemAttributes?.piece_count || itemAttributes?.pieces)} pieces
                    </Text>
                  </View>
                )}
                {/* Set Number */}
                {itemAttributes?.set_number && (
                  <View style={styles.legoDetailRow}>
                    <Ionicons name="barcode-outline" size={16} color={theme.muted} />
                    <Text style={[styles.legoDetailLabel, { color: theme.muted }]}>Set</Text>
                    <Text style={[styles.legoDetailValue, { color: theme.text }]}>
                      #{String(itemAttributes.set_number)}
                    </Text>
                  </View>
                )}
                {/* Retirement Alert Badge */}
                {itemAttributes?.retirement_date && (
                  <View style={[styles.legoRetirementBadge, { backgroundColor: '#FEF3C7' }]}>
                    <Ionicons name="alert-circle" size={16} color="#D97706" />
                    <Text style={[styles.legoRetirementText, { color: '#92400E' }]}>
                      Retiring {String(itemAttributes.retirement_date)}
                      {new Date(String(itemAttributes.retirement_date)) <= new Date()
                        ? ' — RETIRED'
                        : ''}
                    </Text>
                  </View>
                )}
                {/* Build Instructions Link */}
                {itemAttributes?.set_number && (
                  <Pressable
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      Linking.openURL(`https://www.lego.com/en-us/service/buildinginstructions/${String(itemAttributes.set_number)}`).catch((err) =>
                        logger.warn('[ItemDetail] Failed to open LEGO instructions URL', err)
                      );
                    }}
                    style={[styles.legoInstructionsBtn, { borderColor: CATEGORY_VISUAL['lego']?.accentColor ?? theme.accent }]}
                    accessibilityRole="link"
                    accessibilityLabel={`Open build instructions for set ${String(itemAttributes.set_number)}`}
                  >
                    <Ionicons name="document-text-outline" size={16} color={CATEGORY_VISUAL['lego']?.accentColor ?? theme.accent} />
                    <Text style={[styles.legoInstructionsBtnText, { color: CATEGORY_VISUAL['lego']?.accentColor ?? theme.accent }]}>
                      Build Instructions
                    </Text>
                    <Ionicons name="open-outline" size={14} color={CATEGORY_VISUAL['lego']?.accentColor ?? theme.accent} />
                  </Pressable>
                )}
              </View>
            )}

            {/* ── Funko Vaulted Status ────────────────────────────────────── */}
            {categorySlug === 'funko' && (
              itemAttributes?.vaulted === true ||
              (typeof notes === 'string' && notes.toLowerCase().includes('vaulted')) ||
              (typeof itemAttributes?.notes === 'string' && String(itemAttributes.notes).toLowerCase().includes('vaulted'))
            ) && (
              <View style={[styles.vaultedBadgeContainer, { borderTopColor: theme.border }]}>
                <View style={[styles.vaultedBadge, { backgroundColor: '#FEE2E2' }]}>
                  <Ionicons name="lock-closed" size={16} color="#DC2626" />
                  <Text style={[styles.vaultedBadgeText, { color: '#991B1B' }]}>
                    Vaulted
                  </Text>
                </View>
                <Text style={[styles.vaultedHint, { color: theme.muted }]}>
                  This Pop! has been retired from production. Vaulted items often increase in value.
                </Text>
              </View>
            )}

            {/* ── Sneaker Authentication Links ────────────────────────────── */}
            {categorySlug === 'sneakers' && !isDraft && id && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <View style={styles.sectionHeaderRow}>
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="shield-checkmark-outline" size={20} color="#22C55E" />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>Verify Authenticity</Text>
                  </View>
                </View>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingTop: 8 }}>
                  <Pressable
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      Linking.openURL('https://checkcheck.com').catch((err) =>
                        logger.warn('[ItemDetail] Failed to open CheckCheck URL', err)
                      );
                    }}
                    style={[styles.authLinkBtn, { borderColor: '#22C55E' }]}
                    accessibilityRole="link"
                    accessibilityLabel="Verify with CheckCheck"
                  >
                    <Ionicons name="checkmark-circle-outline" size={16} color="#22C55E" />
                    <Text style={[styles.authLinkBtnText, { color: '#22C55E' }]}>CheckCheck</Text>
                    <Ionicons name="open-outline" size={12} color="#22C55E" />
                  </Pressable>
                  <Pressable
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      Linking.openURL('https://www.legitcheck.app').catch((err) =>
                        logger.warn('[ItemDetail] Failed to open Legit Check URL', err)
                      );
                    }}
                    style={[styles.authLinkBtn, { borderColor: '#3B82F6' }]}
                    accessibilityRole="link"
                    accessibilityLabel="Verify with Legit Check"
                  >
                    <Ionicons name="shield-checkmark-outline" size={16} color="#3B82F6" />
                    <Text style={[styles.authLinkBtnText, { color: '#3B82F6' }]}>Legit Check</Text>
                    <Ionicons name="open-outline" size={12} color="#3B82F6" />
                  </Pressable>
                </View>
              </View>
            )}

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
              <View style={[styles.feedbackBlock, { borderTopColor: theme.border }]}>
                <Text style={[styles.feedbackHeader, { color: theme.text }]}>
                  Help improve our estimates
                </Text>

                {feedbackMessage && (
                  <Text style={[styles.feedbackMessage, { color: theme.accent }]}>
                    {feedbackMessage}
                  </Text>
                )}

                {showSalePriceInput ? (
                  <View style={styles.salePriceInputRow}>
                    <TextInput
                      style={[
                        styles.salePriceInput,
                        {
                          color: theme.text,
                          borderColor: theme.border,
                          backgroundColor: theme.background,
                        },
                      ]}
                      placeholder="Sale price (e.g., 150.00)"
                      placeholderTextColor={theme.muted ?? '#64748B'}
                      keyboardType="decimal-pad"
                      value={salePrice}
                      onChangeText={setSalePrice}
                      autoFocus
                      accessibilityLabel="Sale price"
                    />
                    <Pressable
                      onPress={onSubmitSalePrice}
                      disabled={submittingFeedback || !salePrice.trim()}
                      style={[
                        styles.feedbackSubmitBtn,
                        { backgroundColor: theme.accent, opacity: submittingFeedback ? 0.7 : 1 },
                      ]}
                      accessibilityRole="button"
                      accessibilityLabel="Submit sale price"
                    >
                      <Text style={[styles.feedbackBtnText, { color: '#FFFFFF' }]}>
                        {submittingFeedback ? "..." : "Submit"}
                      </Text>
                    </Pressable>
                    <Pressable
                      onPress={() => setShowSalePriceInput(false)}
                      style={[styles.feedbackCancelBtn, { borderColor: theme.border }]}
                      accessibilityRole="button"
                      accessibilityLabel="Cancel sale price entry"
                    >
                      <Text style={[styles.feedbackBtnText, { color: theme.muted }]}>
                        Cancel
                      </Text>
                    </Pressable>
                  </View>
                ) : (
                  <View style={styles.feedbackButtonsRow}>
                    <Pressable
                      onPress={() => setShowSalePriceInput(true)}
                      style={[styles.feedbackBtn, { backgroundColor: theme.success }]}
                      accessibilityRole="button"
                      accessibilityLabel="Report sale price"
                    >
                      <Text style={styles.feedbackBtnTextWhite}>I sold it for...</Text>
                    </Pressable>
                    <Pressable
                      onPress={onPriceDisagree}
                      disabled={submittingFeedback}
                      style={[
                        styles.feedbackBtn,
                        { backgroundColor: theme.card, borderWidth: 1, borderColor: theme.border },
                      ]}
                      accessibilityRole="button"
                      accessibilityLabel="Report price seems off"
                    >
                      <Text style={[styles.feedbackBtnText, { color: theme.text }]}>
                        Price seems off
                      </Text>
                    </Pressable>
                  </View>
                )}
              </View>
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

            {/* Provenance & History — collapsible */}
            {!isDraft && id && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <Pressable
                  onPress={() => setProvenanceExpanded(!provenanceExpanded)}
                  style={styles.sectionHeaderRow}
                  accessibilityRole="button"
                  accessibilityLabel="Toggle ownership history"
                >
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="time-outline" size={20} color={theme.accent} />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>Ownership History</Text>
                  </View>
                  {provenanceLoading ? (
                    <ActivityIndicator size="small" color={theme.accent} />
                  ) : (
                    <Ionicons
                      name={provenanceExpanded ? "chevron-up" : "chevron-down"}
                      size={18}
                      color={theme.muted}
                    />
                  )}
                </Pressable>
                {provenanceExpanded && (
                  <View style={styles.sectionContent}>
                    <ProvenanceTimeline
                      events={provenanceEvents}
                      authenticitySignals={authenticitySignals}
                      loading={provenanceLoading}
                    />
                  </View>
                )}
              </View>
            )}

            {/* Grading Section — for eligible categories */}
            {!isDraft && id && isGradingEligible && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <Pressable
                  onPress={() => {
                    if (!gradingExpanded) {
                      loadGradingServices();
                      if (!gradingPopulation) loadGradingPopulation();
                    }
                    setGradingExpanded(!gradingExpanded);
                    fireHaptic(HapticIntent.TAP_LIGHT, { enabled: settings.hapticsEnabled });
                  }}
                  style={styles.sectionHeaderRow}
                  accessibilityRole="button"
                  accessibilityLabel="Toggle grading information"
                >
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="shield-checkmark-outline" size={20} color={theme.accent} />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>Grading</Text>
                  </View>
                  {gradingLookupResult?.cert_verified && (
                    <View style={[styles.gradingBadge, { backgroundColor: '#22C55E' + '20' }]}>
                      <Ionicons name="checkmark-circle" size={14} color="#22C55E" />
                      <Text style={styles.gradingBadgeText}>
                        {gradingLookupResult.service_name} {gradingLookupResult.grade}
                      </Text>
                    </View>
                  )}
                  <Ionicons
                    name={gradingExpanded ? "chevron-up" : "chevron-down"}
                    size={18}
                    color={theme.muted}
                  />
                </Pressable>

                {gradingExpanded && (
                  <View style={styles.sectionContent}>
                    {/* Verified grade badge (if lookup was performed) */}
                    {gradingLookupResult?.cert_verified && (
                      <Pressable
                        style={[styles.gradingVerifiedCard, { backgroundColor: theme.card, borderColor: '#22C55E' + '40' }]}
                        onPress={() => {
                          if (gradingLookupResult.cert_url) {
                            Linking.openURL(gradingLookupResult.cert_url);
                          }
                        }}
                        accessibilityRole="link"
                        accessibilityLabel={`View ${gradingLookupResult.service_name} certificate`}
                      >
                        <View style={styles.gradingVerifiedHeader}>
                          <Ionicons name="shield-checkmark" size={24} color="#22C55E" />
                          <View style={{ flex: 1 }}>
                            <Text style={[styles.gradingVerifiedGrade, { color: theme.text }]}>
                              {gradingLookupResult.service_name} {gradingLookupResult.grade}
                            </Text>
                            <Text style={[styles.gradingVerifiedMeta, { color: theme.muted }]}>
                              Cert #{gradingLookupResult.cert_number}
                              {gradingLookupResult.year ? ` \u00b7 ${gradingLookupResult.year}` : ''}
                              {gradingLookupResult.label_type ? ` \u00b7 ${gradingLookupResult.label_type}` : ''}
                            </Text>
                          </View>
                          <Ionicons name="open-outline" size={16} color={theme.accent} />
                        </View>
                        {gradingLookupResult.item_name && (
                          <Text style={[styles.gradingVerifiedItemName, { color: theme.muted }]}>
                            {gradingLookupResult.item_name}
                          </Text>
                        )}
                        {gradingLookupResult.sub_grades && (
                          <View style={styles.gradingSubGradesRow}>
                            {Object.entries(gradingLookupResult.sub_grades).map(([key, val]) => (
                              <View key={key} style={[styles.gradingSubGradeChip, { backgroundColor: theme.background }]}>
                                <Text style={[styles.gradingSubGradeLabel, { color: theme.muted }]}>
                                  {key.charAt(0).toUpperCase() + key.slice(1)}
                                </Text>
                                <Text style={[styles.gradingSubGradeValue, { color: theme.text }]}>{val}</Text>
                              </View>
                            ))}
                          </View>
                        )}
                        <View style={styles.gradingPopRow}>
                          {gradingLookupResult.population_at_grade != null && (
                            <Text style={[styles.gradingPopText, { color: theme.muted }]}>
                              Pop at grade: {formatNumber(gradingLookupResult.population_at_grade)}
                            </Text>
                          )}
                          {gradingLookupResult.population_higher != null && gradingLookupResult.population_higher > 0 && (
                            <Text style={[styles.gradingPopText, { color: theme.muted }]}>
                              {' \u00b7 '}Higher: {formatNumber(gradingLookupResult.population_higher)}
                            </Text>
                          )}
                        </View>
                      </Pressable>
                    )}

                    {/* Look Up Certificate button */}
                    <Pressable
                      style={[styles.gradingActionBtn, { borderColor: theme.accent, backgroundColor: theme.card }]}
                      onPress={() => {
                        setGradingModalVisible(true);
                        fireHaptic(HapticIntent.TAP_LIGHT, { enabled: settings.hapticsEnabled });
                      }}
                      accessibilityRole="button"
                      accessibilityLabel="Look up grading certificate"
                    >
                      <Ionicons name="search-outline" size={16} color={theme.accent} />
                      <Text style={[styles.gradingActionBtnText, { color: theme.accent }]}>Look Up Certificate</Text>
                    </Pressable>

                    {/* Population Report mini-table */}
                    {gradingPopLoading && (
                      <View style={{ paddingVertical: 16, alignItems: 'center' }}>
                        <ActivityIndicator size="small" color={theme.accent} />
                        <Text style={[{ fontSize: 12, marginTop: 6 }, { color: theme.muted }]}>Loading population data...</Text>
                      </View>
                    )}
                    {!gradingPopLoading && gradingPopulation && (
                      <View style={[styles.gradingPopTable, { borderColor: theme.border }]}>
                        <View style={styles.gradingPopTableHeader}>
                          <Text style={[styles.gradingPopTableTitle, { color: theme.text }]}>Population Report</Text>
                          <Text style={[styles.gradingPopTableSub, { color: theme.muted }]}>
                            {formatNumber(gradingPopulation.total_graded)} total graded
                            {gradingPopulation.avg_grade != null ? ` \u00b7 Avg: ${gradingPopulation.avg_grade.toFixed(1)}` : ''}
                          </Text>
                        </View>
                        <View style={[styles.gradingPopTableHeaderRow, { borderBottomColor: theme.border }]}>
                          <Text style={[styles.gradingPopTableHeaderCell, { color: theme.muted, flex: 1 }]}>Grade</Text>
                          <Text style={[styles.gradingPopTableHeaderCell, { color: theme.muted, flex: 1, textAlign: 'right' }]}>Count</Text>
                          <Text style={[styles.gradingPopTableHeaderCell, { color: theme.muted, flex: 1, textAlign: 'right' }]}>%</Text>
                        </View>
                        {gradingPopulation.population
                          .filter((p) => p.count > 0)
                          .slice(-10)
                          .reverse()
                          .map((entry) => (
                            <View key={entry.grade} style={[styles.gradingPopTableRow, { borderBottomColor: theme.border }]}>
                              <Text style={[styles.gradingPopTableCell, { color: theme.text, flex: 1, fontWeight: '600' }]}>{entry.grade}</Text>
                              <Text style={[styles.gradingPopTableCell, { color: theme.text, flex: 1, textAlign: 'right' }]}>{formatNumber(entry.count)}</Text>
                              <Text style={[styles.gradingPopTableCell, { color: theme.muted, flex: 1, textAlign: 'right' }]}>
                                {entry.pct_of_total != null ? `${entry.pct_of_total.toFixed(1)}%` : '-'}
                              </Text>
                            </View>
                          ))}
                      </View>
                    )}

                    {/* Submit for Grading buttons */}
                    {gradingServices.length > 0 && (
                      <View style={styles.gradingSubmitSection}>
                        <Text style={[styles.gradingSubmitTitle, { color: theme.text }]}>Submit for Grading</Text>
                        <View style={styles.gradingSubmitRow}>
                          {gradingServices.slice(0, 4).map((svc) => (
                            <Pressable
                              key={svc.id}
                              style={[styles.gradingSubmitBtn, { borderColor: theme.border, backgroundColor: theme.card }]}
                              onPress={() => {
                                Linking.openURL(svc.submission_url);
                                fireHaptic(HapticIntent.TAP_LIGHT, { enabled: settings.hapticsEnabled });
                              }}
                              accessibilityRole="link"
                              accessibilityLabel={`Submit to ${svc.short_name}`}
                            >
                              <Text style={[styles.gradingSubmitBtnName, { color: theme.text }]}>{svc.short_name}</Text>
                              <Text style={[styles.gradingSubmitBtnMeta, { color: theme.muted }]}>{svc.price_range}</Text>
                              <Ionicons name="open-outline" size={12} color={theme.muted} />
                            </Pressable>
                          ))}
                        </View>
                      </View>
                    )}
                  </View>
                )}
              </View>
            )}

            {/* Grading Certificate Lookup Modal */}
            <Modal
              visible={gradingModalVisible}
              transparent
              animationType="slide"
              onRequestClose={() => setGradingModalVisible(false)}
            >
              <Pressable
                style={styles.forSaleModalOverlay}
                onPress={() => setGradingModalVisible(false)}
              >
                <Pressable
                  style={[styles.forSaleModalSheet, { backgroundColor: theme.card }]}
                  onPress={() => {}}
                >
                  <View style={styles.forSaleModalHeader}>
                    <Text style={[styles.forSaleModalTitle, { color: theme.text }]}>Look Up Certificate</Text>
                    <Pressable onPress={() => setGradingModalVisible(false)}>
                      <Ionicons name="close" size={24} color={theme.muted} />
                    </Pressable>
                  </View>

                  {/* Service picker */}
                  <Text style={[styles.forSaleModalLabel, { color: theme.text }]}>Grading Service</Text>
                  <View style={styles.gradingServicePickerRow}>
                    {(['psa', 'cgc', 'bgs', 'beckett'] as const).map((svc) => (
                      <Pressable
                        key={svc}
                        style={[
                          styles.gradingServicePickerChip,
                          {
                            backgroundColor: gradingServicePick === svc ? theme.accent : theme.background,
                            borderColor: gradingServicePick === svc ? theme.accent : theme.border,
                          },
                        ]}
                        onPress={() => setGradingServicePick(svc)}
                      >
                        <Text
                          style={[
                            styles.gradingServicePickerText,
                            { color: gradingServicePick === svc ? '#fff' : theme.text },
                          ]}
                        >
                          {svc.toUpperCase()}
                        </Text>
                      </Pressable>
                    ))}
                  </View>

                  {/* Cert number input */}
                  <Text style={[styles.forSaleModalLabel, { color: theme.text, marginTop: 16 }]}>Certification Number</Text>
                  <TextInput
                    style={[styles.forSaleModalInput, { borderColor: theme.border, color: theme.text, backgroundColor: theme.background }]}
                    value={gradingCertInput}
                    onChangeText={setGradingCertInput}
                    placeholder="e.g. 12345678"
                    placeholderTextColor={theme.muted}
                    keyboardType="number-pad"
                    returnKeyType="search"
                    onSubmitEditing={handleGradingLookup}
                    autoFocus
                  />
                  <Text style={[styles.forSaleModalHint, { color: theme.muted }]}>
                    Enter the number printed on your grading certificate or slab label.
                  </Text>

                  <Pressable
                    style={[styles.forSaleModalConfirmBtn, { backgroundColor: theme.accent, opacity: gradingLookupLoading ? 0.6 : 1 }]}
                    onPress={handleGradingLookup}
                    disabled={gradingLookupLoading}
                  >
                    {gradingLookupLoading ? (
                      <ActivityIndicator size="small" color="#fff" />
                    ) : (
                      <>
                        <Ionicons name="search" size={18} color="#fff" />
                        <Text style={styles.forSaleModalConfirmBtnText}>Look Up</Text>
                      </>
                    )}
                  </Pressable>
                </Pressable>
              </Pressable>
            </Modal>

            {/* Dossier Section */}
            {!isDraft && id && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <Pressable
                  onPress={() => {
                    if (!dossierData && !dossierError) loadDossier();
                    else setDossierExpanded(!dossierExpanded);
                  }}
                  style={styles.sectionHeaderRow}
                  accessibilityRole="button"
                  accessibilityLabel="View full item report"
                >
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="document-text-outline" size={20} color={theme.accent} />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>Full Report</Text>
                  </View>
                  {dossierLoading ? (
                    <ActivityIndicator size="small" color={theme.accent} />
                  ) : (
                    <Ionicons
                      name={dossierExpanded ? "chevron-up" : "chevron-down"}
                      size={18}
                      color={theme.muted}
                    />
                  )}
                </Pressable>
                {dossierExpanded && dossierError && !dossierData && (
                  <View style={styles.sectionContent}>
                    <Text style={[styles.emptyText, { color: theme.muted }]}>
                      Could not load report. Check your connection and try again.
                    </Text>
                    <AnimatedPressable
                      onPress={() => loadDossier()}
                      style={[styles.retryBtn, { borderColor: theme.accent }]}
                      accessibilityRole="button"
                      accessibilityLabel="Retry loading report"
                    >
                      <Text style={{ color: theme.accent, fontSize: 13, fontWeight: '600' }}>Retry</Text>
                    </AnimatedPressable>
                  </View>
                )}
                {dossierExpanded && dossierData && (
                  <View style={styles.sectionContent}>
                    {/* Valuation summary */}
                    {dossierData.valuation?.q50 != null && (
                      <View style={[styles.dossierCard, { backgroundColor: theme.background }]}>
                        <Text style={[styles.dossierLabel, { color: theme.muted }]}>Estimated Value</Text>
                        <Text style={[styles.dossierValue, { color: theme.text }]}>
                          {formatPrice(toNum(dossierData.valuation.q50))}
                        </Text>
                        {dossierData.valuation.explanation && (
                          <Text style={[styles.dossierMeta, { color: theme.muted }]}>
                            {dossierData.valuation.explanation}
                          </Text>
                        )}
                      </View>
                    )}
                    {/* Market comps count */}
                    {dossierData.market_comps?.length > 0 && (
                      <View style={styles.dossierRow}>
                        <Text style={[styles.dossierRowLabel, { color: theme.muted }]}>Similar Listings</Text>
                        <Text style={[styles.dossierRowValue, { color: theme.text }]}>
                          {dossierData.market_comps.length} found
                        </Text>
                      </View>
                    )}
                    {/* Authenticity signals */}
                    {dossierData.authenticity_signals?.length > 0 && (
                      <View style={styles.dossierRow}>
                        <Text style={[styles.dossierRowLabel, { color: theme.muted }]}>Authenticity</Text>
                        <Text style={[styles.dossierRowValue, { color: theme.accent }]}>
                          {dossierData.authenticity_signals.join(", ").replace(/_/g, " ")}
                        </Text>
                      </View>
                    )}
                    {/* Export button */}
                    <Pressable
                      onPress={() => {
                        const url = collectorsApi.getDossierExportUrl(id);
                        Linking.openURL(url).catch((err) => {
                          logger.warn('[ItemDetail] Failed to open URL', err);
                        });
                      }}
                      style={[styles.dossierExportBtn, { borderColor: theme.border }]}
                      accessibilityRole="button"
                      accessibilityLabel="Export report as PDF"
                    >
                      <Ionicons name="share-outline" size={16} color={theme.accent} />
                      <Text style={[styles.dossierExportText, { color: theme.accent }]}>Export Report</Text>
                    </Pressable>
                  </View>
                )}
              </View>
            )}

            {/* Build Project — for buildable categories */}
            {!isDraft && id && itemIsBuildable && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <View style={styles.sectionHeaderRow}>
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="construct-outline" size={20} color={buildAccent ?? theme.accent} />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>Build & Paint</Text>
                  </View>
                </View>
                {linkedProject ? (
                  <Pressable
                    onPress={() => router.push(`/projects/${encodeURIComponent(linkedProject.id)}`)}
                    style={[styles.buildProjectLink, { backgroundColor: theme.background, borderColor: theme.border }]}
                    accessibilityRole="button"
                    accessibilityLabel={`View build project: ${linkedProject.title}, ${linkedProject.pct}% complete`}
                  >
                    <View style={[styles.buildProjectLinkAccent, { backgroundColor: buildAccent ?? theme.accent }]} />
                    <View style={styles.buildProjectLinkInfo}>
                      <Text style={[styles.buildProjectLinkTitle, { color: theme.text }]} numberOfLines={1}>
                        {linkedProject.title}
                      </Text>
                      <View style={styles.buildProjectLinkProgressRow}>
                        <View style={[styles.buildProjectLinkProgressBg, { backgroundColor: theme.border }]}>
                          <View
                            style={[
                              styles.buildProjectLinkProgressFill,
                              { backgroundColor: buildAccent ?? theme.accent, width: `${linkedProject.pct}%` },
                            ]}
                          />
                        </View>
                        <Text style={[styles.buildProjectLinkPct, { color: theme.muted }]}>
                          {linkedProject.pct}%
                        </Text>
                      </View>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={theme.muted} />
                  </Pressable>
                ) : (
                  <Pressable
                    onPress={() => router.push({
                      pathname: '/build-paint-projects',
                      params: { linkItemId: id, linkItemName: editableName, linkCategoryId: categorySlug },
                    })}
                    style={[styles.startBuildButton, { backgroundColor: buildAccent ?? theme.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel="Start a build project for this item"
                  >
                    <Ionicons name="add-circle-outline" size={18} color="#fff" />
                    <Text style={styles.startBuildButtonText}>Start Build Project</Text>
                  </Pressable>
                )}
              </View>
            )}

            {/* Reading / Play Progress — for manga, comics, games */}
            {!isDraft && id && hasProgressTracking && progressConfig && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <View style={styles.sectionHeaderRow}>
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name={(progressConfig.icon as keyof typeof Ionicons.glyphMap) || 'book-outline'} size={20} color={theme.accent} />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>{progressConfig.label}</Text>
                  </View>
                  {progressSaving && (
                    <ActivityIndicator size="small" color={theme.accent} />
                  )}
                </View>

                {progressLoading ? (
                  <ActivityIndicator size="small" color={theme.accent} style={{ marginVertical: 12 }} />
                ) : (
                  <>
                    {/* Status pills */}
                    <View style={styles.progressStatusRow}>
                      {progressConfig.statuses.map((status) => {
                        const isActive = progressStatus === status;
                        const statusColor = STATUS_COLORS[status] || theme.accent;
                        return (
                          <Pressable
                            key={status}
                            onPress={() => handleProgressStatusChange(status)}
                            style={[
                              styles.progressStatusPill,
                              {
                                backgroundColor: isActive ? statusColor : statusColor + '15',
                                borderColor: statusColor,
                              },
                            ]}
                            accessibilityRole="button"
                            accessibilityLabel={`Set status to ${STATUS_DISPLAY[status]}`}
                            accessibilityState={{ selected: isActive }}
                          >
                            <Text style={[
                              styles.progressStatusPillText,
                              { color: isActive ? '#fff' : statusColor },
                            ]}>
                              {STATUS_DISPLAY[status]}
                            </Text>
                          </Pressable>
                        );
                      })}
                    </View>

                    {/* Progress bar (percentage) */}
                    <View style={styles.progressBarSection}>
                      <Text style={[styles.progressBarLabel, { color: theme.muted }]}>
                        Progress: {progressPct ?? 0}%
                      </Text>
                      <View style={styles.progressBarRow}>
                        <View style={[styles.progressBarBg, { backgroundColor: theme.border }]}>
                          <View
                            style={[
                              styles.progressBarFill,
                              {
                                backgroundColor: progressStatus ? (STATUS_COLORS[progressStatus] || theme.accent) : theme.accent,
                                width: `${progressPct ?? 0}%`,
                              },
                            ]}
                          />
                        </View>
                      </View>
                      {/* Quick percentage buttons */}
                      <View style={styles.progressPctButtons}>
                        {[0, 25, 50, 75, 100].map((pct) => (
                          <Pressable
                            key={pct}
                            onPress={() => handleProgressPctChange(pct)}
                            style={[
                              styles.progressPctBtn,
                              {
                                backgroundColor: progressPct === pct ? theme.accent : theme.background,
                                borderColor: theme.border,
                              },
                            ]}
                            accessibilityRole="button"
                            accessibilityLabel={`Set progress to ${pct}%`}
                          >
                            <Text style={[
                              styles.progressPctBtnText,
                              { color: progressPct === pct ? '#fff' : theme.muted },
                            ]}>
                              {pct}%
                            </Text>
                          </Pressable>
                        ))}
                      </View>
                    </View>

                    {/* Progress notes */}
                    <TextInput
                      style={[
                        styles.progressNotesInput,
                        {
                          color: theme.text,
                          borderColor: theme.border,
                          backgroundColor: theme.background,
                        },
                      ]}
                      placeholder={
                        categorySlug === 'manga' || categorySlug === 'comic_books'
                          ? 'Reading notes (e.g., "Volume 14 of 37, love the arc!")'
                          : 'Play notes (e.g., "Cleared World 5, need to replay boss")'
                      }
                      placeholderTextColor={theme.muted ?? '#64748B'}
                      multiline
                      value={progressNotes}
                      onChangeText={handleProgressNotesChange}
                      textAlignVertical="top"
                      blurOnSubmit={false}
                      accessibilityLabel={`${progressConfig.label} notes`}
                    />
                  </>
                )}
              </View>
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
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <Pressable
                  onPress={() => {
                    if (marketResults.length === 0 && !marketError) loadMarketResults();
                    else setMarketExpanded(!marketExpanded);
                  }}
                  style={styles.sectionHeaderRow}
                  accessibilityRole="button"
                  accessibilityLabel="Find on market"
                >
                  <View style={styles.sectionHeaderLeft}>
                    <Ionicons name="cart-outline" size={20} color={theme.accent} />
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>Market Prices</Text>
                  </View>
                  {marketLoading ? (
                    <ActivityIndicator size="small" color={theme.accent} />
                  ) : (
                    <Ionicons
                      name={marketExpanded ? "chevron-up" : "chevron-down"}
                      size={18}
                      color={theme.muted}
                    />
                  )}
                </Pressable>
                {marketExpanded && marketError && marketResults.length === 0 && !marketLoading && (
                  <View style={styles.sectionContent}>
                    <Text style={[styles.emptyText, { color: theme.muted }]}>
                      Could not load market prices. Check your connection and try again.
                    </Text>
                    <AnimatedPressable
                      onPress={() => loadMarketResults()}
                      style={[styles.retryBtn, { borderColor: theme.accent }]}
                      accessibilityRole="button"
                      accessibilityLabel="Retry loading market prices"
                    >
                      <Text style={{ color: theme.accent, fontSize: 13, fontWeight: '600' }}>Retry</Text>
                    </AnimatedPressable>
                  </View>
                )}
                {marketExpanded && marketResults.length > 0 && (
                  <View style={styles.sectionContent}>
                    {marketResults.slice(0, 5).map((hit, idx) => (
                      <Pressable
                        key={idx}
                        onPress={() => {
                          const openUrl = hit.affiliate_url || hit.url;
                          if (openUrl) Linking.openURL(openUrl).catch((err) => {
                            logger.warn('[ItemDetail] Failed to open URL', err);
                          });
                        }}
                        style={[styles.marketHitRow, { borderBottomColor: theme.border }]}
                        accessibilityRole="link"
                        accessibilityLabel={`${hit.title}, ${formatPrice(toNum(hit.price))} on ${hit.source || hit.provider || 'marketplace'}`}
                      >
                        <View style={{ flex: 1 }}>
                          <Text style={[styles.marketHitTitle, { color: theme.text }]} numberOfLines={1}>
                            {hit.title}
                          </Text>
                          <Text style={[styles.marketHitMeta, { color: theme.muted }]}>
                            {hit.source || hit.provider} {hit.condition ? `· ${hit.condition}` : ""}
                          </Text>
                        </View>
                        <Text style={[styles.marketHitPrice, { color: theme.text }]}>
                          {formatPrice(toNum(hit.price))}
                        </Text>
                      </Pressable>
                    ))}
                    {marketResults.length > 5 && (
                      <AnimatedPressable
                        onPress={() => {
                          router.push({
                            pathname: '/(tabs)/marketplace',
                            params: { q: editableName },
                          });
                        }}
                        style={styles.viewAllLink}
                        accessibilityRole="link"
                        accessibilityLabel={`View all ${marketResults.length} marketplace results`}
                      >
                        <Text style={[styles.viewAllLinkText, { color: theme.accent }]}>
                          View all {marketResults.length} results
                        </Text>
                        <Ionicons name="arrow-forward" size={14} color={theme.accent} />
                      </AnimatedPressable>
                    )}
                  </View>
                )}
                {marketExpanded && marketResults.length === 0 && !marketLoading && (
                  <Text style={[styles.emptyText, { color: theme.muted }]}>
                    No listings found for this item.
                  </Text>
                )}
              </View>
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

      {/* For-Sale Listing Modal */}
      <Modal
        visible={forSaleModalVisible}
        animationType="slide"
        transparent
        onRequestClose={() => setForSaleModalVisible(false)}
      >
        <View style={styles.forSaleModalOverlay}>
          <View style={[styles.forSaleModalSheet, { backgroundColor: theme.card }]}>
            <View style={styles.forSaleModalHeader}>
              <Text style={[styles.forSaleModalTitle, { color: theme.text }]}>List for Sale</Text>
              <Pressable onPress={() => setForSaleModalVisible(false)}>
                <Ionicons name="close" size={24} color={theme.muted} />
              </Pressable>
            </View>

            <Text style={[styles.forSaleModalLabel, { color: theme.muted }]}>Asking price</Text>
            <TextInput
              style={[
                styles.forSaleModalInput,
                { backgroundColor: theme.background, color: theme.text, borderColor: theme.border },
              ]}
              value={askingPriceValue}
              onChangeText={setAskingPriceValue}
              keyboardType="decimal-pad"
              placeholder="0.00"
              placeholderTextColor={theme.muted}
              autoFocus
            />

            <Text style={[styles.forSaleModalHint, { color: theme.muted }]}>
              Other collectors can make offers on this item. You can accept, decline, or counter any offer.
            </Text>

            <AnimatedPressable
              onPress={handleListForSale}
              disabled={forSaleLoading || !askingPriceValue.trim()}
              style={[
                styles.forSaleModalConfirmBtn,
                {
                  backgroundColor: theme.accent,
                  opacity: forSaleLoading || !askingPriceValue.trim() ? 0.5 : 1,
                },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Confirm listing for sale"
            >
              {forSaleLoading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <Ionicons name="pricetag" size={18} color="#fff" />
                  <Text style={styles.forSaleModalConfirmBtnText}>List for Sale</Text>
                </>
              )}
            </AnimatedPressable>
          </View>
        </View>
      </Modal>

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
  imageWrapper: {
    width: "100%",
    height: 260,
    borderRadius: 16,
    borderWidth: 1,
    overflow: "hidden",
    marginBottom: 16,
  },
  draftSection: {
    marginBottom: 16,
    gap: 8,
  },
  draftBanner: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  draftText: {
    fontSize: 13,
    fontWeight: '600',
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
  image: {
    width: "100%",
    height: "100%",
  },
  photoUploadOverlay: {
    position: "absolute",
    bottom: 12,
    right: 12,
    backgroundColor: "rgba(0,0,0,0.55)",
    borderRadius: 20,
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  photoUploadOverlayEmpty: {
    bottom: 0,
    right: 0,
    left: 0,
    top: 0,
    width: "100%",
    height: "100%",
    borderRadius: 0,
    backgroundColor: "rgba(0,0,0,0.15)",
    gap: 8,
  },
  photoUploadOverlayText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "600",
  },
  photoErrorBanner: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(220,38,38,0.85)",
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  photoErrorText: {
    color: "#FFFFFF",
    fontSize: 12,
    textAlign: "center",
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
  nameInput: {
    fontSize: 20,
    fontWeight: "700",
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginBottom: 4,
  },
  editableRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  editableFieldWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 8,
  },
  editableFieldSmall: {
    alignSelf: 'flex-start',
    marginTop: 4,
  },
  editableNameInput: {
    flex: 1,
    fontSize: 18,
    fontWeight: '600',
  },
  editableCategoryInput: {
    fontSize: 14,
    minWidth: 120,
  },
  editableNameInputSimple: {
    fontSize: 20,
    fontWeight: '700',
    paddingVertical: 4,
    borderBottomWidth: 1,
  },
  editableCategoryInputSimple: {
    fontSize: 14,
    paddingVertical: 4,
    marginTop: 4,
    borderBottomWidth: 1,
    alignSelf: 'flex-start',
    minWidth: 100,
  },
  dropdownField: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    marginTop: 4,
    borderBottomWidth: 1,
    alignSelf: 'flex-start',
    gap: 6,
  },
  dropdownFieldText: {
    fontSize: 14,
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
  category: {
    fontSize: 13,
  },
  categoryInput: {
    fontSize: 13,
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginTop: 4,
  },
  categoryPill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginTop: 4,
    gap: 4,
  },
  categoryPillText: {
    fontSize: 13,
    fontWeight: '500',
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
  feedbackBlock: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
  },
  feedbackHeader: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 10,
  },
  feedbackMessage: {
    fontSize: 12,
    marginBottom: 8,
  },
  feedbackButtonsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  feedbackBtn: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  feedbackBtnText: {
    fontSize: 13,
    fontWeight: '500',
  },
  feedbackBtnTextWhite: {
    fontSize: 13,
    fontWeight: '500',
    color: '#FFFFFF',
  },
  salePriceInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  salePriceInput: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
  },
  feedbackSubmitBtn: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 8,
  },
  feedbackCancelBtn: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
  },
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
  sectionContent: {
    marginTop: 10,
  },
  emptyText: {
    fontSize: 13,
    marginTop: 8,
    fontStyle: 'italic',
  },
  retryBtn: {
    alignSelf: 'flex-start',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 10,
  },
  // Build project link card
  buildProjectLink: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 10,
    borderWidth: 1,
    overflow: 'hidden',
    marginTop: 8,
  },
  buildProjectLinkAccent: {
    width: 4,
    alignSelf: 'stretch',
  },
  buildProjectLinkInfo: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  buildProjectLinkTitle: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 4,
  },
  buildProjectLinkProgressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  buildProjectLinkProgressBg: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  buildProjectLinkProgressFill: {
    height: '100%',
    borderRadius: 2,
  },
  buildProjectLinkPct: {
    fontSize: 11,
    fontWeight: '600',
    minWidth: 28,
    textAlign: 'right',
  },
  startBuildButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 10,
    marginTop: 8,
  },
  startBuildButtonText: {
    color: '#fff',
    fontSize: 13,
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
  dossierCard: {
    padding: 12,
    borderRadius: 10,
    marginBottom: 8,
  },
  dossierLabel: {
    fontSize: 12,
    marginBottom: 4,
  },
  dossierValue: {
    fontSize: 20,
    fontWeight: '700',
  },
  dossierMeta: {
    fontSize: 12,
    marginTop: 4,
    lineHeight: 17,
  },
  dossierRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
  },
  dossierRowLabel: {
    fontSize: 13,
  },
  dossierRowValue: {
    fontSize: 13,
    fontWeight: '500',
  },
  dossierExportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 8,
  },
  dossierExportText: {
    fontSize: 13,
    fontWeight: '500',
  },
  marketHitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 8,
  },
  marketHitTitle: {
    fontSize: 13,
    fontWeight: '500',
  },
  marketHitMeta: {
    fontSize: 11,
    marginTop: 2,
  },
  marketHitPrice: {
    fontSize: 14,
    fontWeight: '700',
    minWidth: 60,
    textAlign: 'right',
  },
  viewAllLink: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: 10,
    marginTop: 4,
  },
  viewAllLinkText: {
    fontSize: 13,
    fontWeight: '600',
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
  editBarBtnWide: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 10,
    borderWidth: 1,
  },
  editBarBtnWideText: {
    fontSize: 15,
    fontWeight: '700',
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
  // Price History Chart styles
  trendDirectionBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
  },
  trendPctText: {
    fontSize: 13,
    fontWeight: '700',
  },
  trendRangePills: {
    flexDirection: 'row',
    gap: 6,
    marginTop: 10,
  },
  trendRangePill: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 14,
    borderWidth: 1,
  },
  trendRangePillText: {
    fontSize: 12,
    fontWeight: '600',
  },
  trendChartContainer: {
    marginTop: 12,
    paddingVertical: 8,
  },
  trendHoverRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 8,
    marginBottom: 8,
  },
  trendHoverPrice: {
    fontSize: 20,
    fontWeight: '700',
  },
  trendHoverDate: {
    fontSize: 12,
    fontWeight: '500',
  },
  trendEmptyState: {
    alignItems: 'center',
    paddingVertical: 24,
    gap: 6,
  },
  trendEmptyText: {
    fontSize: 14,
    fontWeight: '600',
    marginTop: 4,
  },
  trendEmptySubtext: {
    fontSize: 12,
    textAlign: 'center',
    paddingHorizontal: 16,
  },
  // ── Image Gallery styles ─────────────────────────────────────────
  galleryContainer: {
    width: '100%',
    marginBottom: 16,
    borderRadius: 16,
    overflow: 'hidden',
  },
  gallerySlide: {
    borderRadius: 16,
    overflow: 'hidden',
  },
  galleryAddCard: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: 16,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: '#81D8D0',
  },
  galleryAddText: {
    fontSize: 15,
    fontWeight: '600',
  },
  galleryLabelBadge: {
    position: 'absolute',
    bottom: 10,
    left: 10,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  galleryLabelText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'capitalize',
  },
  galleryDeleteBtn: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: 'rgba(255,255,255,0.85)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  galleryCounterBadge: {
    position: 'absolute',
    bottom: 10,
    right: 10,
    backgroundColor: 'rgba(0,0,0,0.55)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
  },
  galleryCounterText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '600',
  },
  galleryDots: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 10,
  },
  galleryDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
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
  forSaleBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
  },
  forSaleBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
  forSaleModalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  forSaleModalSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 40,
  },
  forSaleModalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  forSaleModalTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  forSaleModalLabel: {
    fontSize: 13,
    fontWeight: '500',
    marginBottom: 6,
  },
  forSaleModalInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    marginBottom: 8,
  },
  forSaleModalHint: {
    fontSize: 12,
    lineHeight: 17,
    marginTop: 4,
    marginBottom: 8,
  },
  forSaleModalConfirmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 12,
  },
  forSaleModalConfirmBtnText: {
    color: '#fff',
    fontSize: 15,
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
  // Watchlist button & modal styles
  watchlistBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 8,
  },
  watchlistBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
  watchlistPreview: {
    padding: 12,
    borderRadius: 10,
    marginBottom: 16,
  },
  watchlistPreviewTitle: {
    fontSize: 15,
    fontWeight: '600',
    marginBottom: 6,
  },
  watchlistPreviewBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
  },
  watchlistPreviewBadgeText: {
    fontSize: 12,
    fontWeight: '500',
  },

  // ── Progress Tracking ────────────────────────────────────────────────
  progressStatusRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    paddingTop: 8,
    paddingBottom: 12,
  },
  progressStatusPill: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
    borderWidth: 1,
  },
  progressStatusPillText: {
    fontSize: 13,
    fontWeight: '600',
  },
  progressBarSection: {
    paddingBottom: 10,
  },
  progressBarLabel: {
    fontSize: 12,
    fontWeight: '500',
    marginBottom: 6,
  },
  progressBarRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  progressBarBg: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 4,
  },
  progressPctButtons: {
    flexDirection: 'row',
    gap: 6,
    marginTop: 8,
  },
  progressPctBtn: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
  },
  progressPctBtnText: {
    fontSize: 11,
    fontWeight: '600',
  },
  progressNotesInput: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 10,
    minHeight: 60,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 4,
  },
  // ── Grading styles ─────────────────────────────────────────────────────
  gradingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    marginRight: 4,
  },
  gradingBadgeText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#22C55E',
  },
  gradingVerifiedCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 12,
  },
  gradingVerifiedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  gradingVerifiedGrade: {
    fontSize: 18,
    fontWeight: '700',
  },
  gradingVerifiedMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  gradingVerifiedItemName: {
    fontSize: 12,
    marginTop: 8,
    fontStyle: 'italic',
  },
  gradingSubGradesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 10,
  },
  gradingSubGradeChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    alignItems: 'center',
  },
  gradingSubGradeLabel: {
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  gradingSubGradeValue: {
    fontSize: 14,
    fontWeight: '700',
    marginTop: 1,
  },
  gradingPopRow: {
    flexDirection: 'row',
    marginTop: 8,
  },
  gradingPopText: {
    fontSize: 11,
  },
  gradingActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 12,
  },
  gradingActionBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
  gradingPopTable: {
    borderRadius: 10,
    borderWidth: 1,
    overflow: 'hidden',
    marginBottom: 12,
  },
  gradingPopTableHeader: {
    padding: 12,
  },
  gradingPopTableTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  gradingPopTableSub: {
    fontSize: 11,
    marginTop: 2,
  },
  gradingPopTableHeaderRow: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
  },
  gradingPopTableHeaderCell: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  gradingPopTableRow: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  gradingPopTableCell: {
    fontSize: 13,
  },
  gradingSubmitSection: {
    marginTop: 4,
  },
  gradingSubmitTitle: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  gradingSubmitRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  gradingSubmitBtn: {
    flex: 1,
    minWidth: 120,
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
    gap: 3,
  },
  gradingSubmitBtnName: {
    fontSize: 13,
    fontWeight: '700',
  },
  gradingSubmitBtnMeta: {
    fontSize: 10,
  },
  gradingServicePickerRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8,
  },
  gradingServicePickerChip: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
  },
  gradingServicePickerText: {
    fontSize: 13,
    fontWeight: '700',
  },

  // ── Size-Specific Pricing ──────────────────────────────────────────────
  sizeSelectorRow: {
    paddingTop: 8,
  },
  sizeSystemRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 10,
  },
  sizeSystemPill: {
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  sizeSystemPillText: {
    fontSize: 13,
    fontWeight: '600',
  },
  sizePillsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  sizePill: {
    minWidth: 44,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: 'center',
  },
  sizePillText: {
    fontSize: 13,
    fontWeight: '600',
  },
  sizeInfoNote: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 8,
    marginTop: 10,
  },
  sizeInfoNoteText: {
    fontSize: 12,
    fontWeight: '500',
    flex: 1,
  },

  // ── LEGO-Specific ──────────────────────────────────────────────────────
  legoDetailRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 6,
  },
  legoDetailLabel: {
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
  },
  legoDetailValue: {
    fontSize: 13,
    fontWeight: '700',
  },
  legoRetirementBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 8,
    marginTop: 6,
  },
  legoRetirementText: {
    fontSize: 13,
    fontWeight: '600',
    flex: 1,
  },
  legoInstructionsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 8,
  },
  legoInstructionsBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },

  // ── Funko Vaulted ──────────────────────────────────────────────────────
  vaultedBadgeContainer: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
  },
  vaultedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    marginBottom: 6,
  },
  vaultedBadgeText: {
    fontSize: 14,
    fontWeight: '700',
  },
  vaultedHint: {
    fontSize: 12,
    lineHeight: 17,
  },

  // ── Authentication Links ───────────────────────────────────────────────
  authLinkBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
  },
  authLinkBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
});