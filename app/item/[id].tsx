import React, { useState, useRef, useMemo, useEffect } from "react";
import { router } from 'expo-router';
import {
  SafeAreaView,
  ScrollView,
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
import { formatPrice, formatNumber } from "@/lib/format";

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

export default function ItemDetailScreen() {
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

  // Photo upload
  const { user } = useAuthContext();
  const {
    pickAndUpload,
    uploading: photoUploading,
    error: photoError,
    photoUrl: userPhotoUrl,
  } = usePhotoUpload(id || "draft");
  const [userPhoto, setUserPhoto] = useState<string | null>(null);

  // Resolved display image: user photo > imageUri (catalog) > placeholder
  const displayImageUri = userPhoto || userPhotoUrl || imageUri;

  const handlePhotoUpload = async (source: "camera" | "gallery") => {
    const url = await pickAndUpload(source);
    if (url) {
      setUserPhoto(url);
    }
  };

  const showPhotoSourcePicker = () => {
    if (Platform.OS === "ios") {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ["Cancel", "Take Photo", "Choose from Library"],
          cancelButtonIndex: 0,
          title: "Add Your Photo",
        },
        (buttonIndex) => {
          if (buttonIndex === 1) handlePhotoUpload("camera");
          if (buttonIndex === 2) handlePhotoUpload("gallery");
        },
      );
    } else {
      Alert.alert("Add Your Photo", "Choose a source", [
        { text: "Take Photo", onPress: () => handlePhotoUpload("camera") },
        {
          text: "Choose from Library",
          onPress: () => handlePhotoUpload("gallery"),
        },
        { text: "Cancel", style: "cancel" },
      ]);
    }
  };

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

  // Marketplace state
  const [marketResults, setMarketResults] = useState<MarketHit[]>([]);
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketExpanded, setMarketExpanded] = useState(false);
  const [marketScannedAt, setMarketScannedAt] = useState<string | null>(null);

  // AI Intelligence refresh state
  const [aiRefreshing, setAiRefreshing] = useState(false);

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
          onPress: () => setEditableCategory(opt),
        })).concat([{ text: 'Cancel', style: 'cancel' }])
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
          }
        }
      );
    } else {
      Alert.alert(
        'Select Collection/Set',
        undefined,
        COLLECTION_OPTIONS.map((opt) => ({
          text: opt,
          onPress: () => setEditableCollection(opt),
        })).concat([{ text: 'Cancel', style: 'cancel' }])
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
          }
        }
      );
    } else {
      Alert.alert(
        'Select Condition/Grade',
        undefined,
        CONDITION_OPTIONS.map((opt) => ({
          text: opt,
          onPress: () => setEditableCondition(opt),
        })).concat([{ text: 'Cancel', style: 'cancel' }])
      );
    }
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

  // Mock fallback data for previewing sections when API is empty
  const MOCK_PROVENANCE_EVENTS = [
    { id: 'mock-1', eventType: 'purchase', timestamp: new Date(Date.now() - 90 * 86400000).toISOString(), note: 'Purchased from local card shop', source: 'manual', metadata: {} },
    { id: 'mock-2', eventType: 'graded', timestamp: new Date(Date.now() - 60 * 86400000).toISOString(), note: 'Sent to PSA for grading — returned PSA 9', source: 'receipt', metadata: {} },
    { id: 'mock-3', eventType: 'added', timestamp: new Date(Date.now() - 30 * 86400000).toISOString(), note: 'Added to CcollectAI collection', source: 'barcode', metadata: {} },
  ];
  const MOCK_AUTH_SIGNALS = ['receipt_on_file', 'professionally_graded'];
  const EMPTY_MARKET_RESULTS: MarketHit[] = [];
  const MOCK_DOSSIER: DossierData = {
    item_id: id || '',
    generated_at: new Date().toISOString(),
    identity: { name: editableName, category: editableCategory },
    valuation: { q50: toNum(editableValue) ?? 35, explanation: 'Based on 24 comparable sales across eBay and TCGPlayer over the last 90 days.' },
    provenance: [],
    price_history: [],
    market_comps: [{ source: 'eBay', price: 42 }, { source: 'TCGPlayer', price: 38 }, { source: 'Cardmarket', price: 35 }],
    photos: [],
    collections: [],
    authenticity_signals: ['receipt_on_file', 'professionally_graded'],
    completeness_score: 0.72,
  };

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
        // Fall back to mock data if API returns empty
        setProvenanceEvents(events.length > 0 ? events : MOCK_PROVENANCE_EVENTS);
        setAuthenticitySignals(data.authenticity_signals?.length ? data.authenticity_signals : MOCK_AUTH_SIGNALS);
      })
      .catch((err) => {
        logger.warn('[ItemDetail] provenance fetch error:', err);
        setProvenanceEvents(MOCK_PROVENANCE_EVENTS);
        setAuthenticitySignals(MOCK_AUTH_SIGNALS);
      })
      .finally(() => setProvenanceLoading(false));
  }, [id, isDraft]);

  // Load dossier on demand
  const loadDossier = async () => {
    if (!id || isDraft || dossierData) return;
    setDossierLoading(true);
    try {
      const data = await collectorsApi.getDossier(id);
      // Use mock if API returns empty/minimal data
      const hasContent = data && (data.valuation?.q50 != null || data.market_comps?.length > 0);
      setDossierData(hasContent ? data : MOCK_DOSSIER);
      setDossierExpanded(true);
    } catch (err) {
      logger.warn('[ItemDetail] dossier fetch error:', err);
      setDossierData(MOCK_DOSSIER);
      setDossierExpanded(true);
    } finally {
      setDossierLoading(false);
    }
  };

  // Load marketplace results on demand
  const loadMarketResults = async () => {
    if (!editableName) return;
    setMarketLoading(true);
    try {
      const data = await collectorsApi.marketplaceSearch(editableName, editableCategory);
      const results = data.results || data.hits || [];
      // Fall back to mock data if API returns empty
      setMarketResults(results.length > 0 ? results : EMPTY_MARKET_RESULTS);
      setMarketScannedAt(new Date().toISOString());
      setMarketExpanded(true);
    } catch (err) {
      logger.warn('[ItemDetail] marketplace search error:', err);
      setMarketResults(EMPTY_MARKET_RESULTS);
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
      currency: 'EUR',
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

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 80 : 0}
    >
      <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.background }]}>
        <Animated.ScrollView
          ref={scrollViewRef}
          style={styles.scroll}
          contentContainerStyle={[
            styles.content,
            { backgroundColor: theme.background },
            { paddingBottom: keyboardVisible ? keyboardHeight + 40 : 100 },
          ]}
          keyboardShouldPersistTaps="handled"
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
          {/* Image — priority: user photo > catalog imageUri > placeholder */}
          <View style={[styles.imageWrapper, { borderColor: theme.border }]}>
            {displayImageUri ? (
              <Image
                source={{ uri: displayImageUri }}
                style={styles.image}
                contentFit="cover"
                cachePolicy="disk"
                transition={200}
              />
            ) : (
              <Image
                source={require("../../assets/placeholder.png")}
                style={styles.image}
                contentFit="cover"
              />
            )}

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

          {/* Details card */}
          <View
            style={[
              styles.card,
              { backgroundColor: theme.card, borderColor: theme.border },
            ]}
          >
            {/* Editable Name (draft mode) */}
            {isDraft ? (
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
              {isDraft ? (
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
              {isDraft ? (
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
              {isDraft ? (
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
                <Text style={[styles.value, { color: theme.text }]}>{editableCondition}</Text>
              )}
            </View>

            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.muted }]}>
                Estimated value
              </Text>
              {isDraft ? (
                <View style={styles.editableValueRow}>
                  <Text style={[styles.currencySymbol, { color: theme.muted }]}>€</Text>
                  <TextInput
                    style={[styles.editableValueInput, { color: theme.text, borderBottomColor: theme.border, fontWeight: '700' }]}
                    value={editableValue}
                    onChangeText={setEditableValue}
                    placeholder="0"
                    placeholderTextColor={theme.muted ?? '#64748B'}
                    keyboardType="decimal-pad"
                    accessibilityLabel="Estimated value in euros"
                  />
                </View>
              ) : (
                <Text style={[styles.valueHighlight, { color: theme.text }]}>
                  {formatPrice(toNum(editableValue))}
                </Text>
              )}
            </View>

            {/* Item Attributes Section — from attributes_json */}
            <ItemAttributesSection
              attributes={itemAttributes}
              taxonomyVersion={taxonomyVersion}
              subtypeId={subtypeId}
              collections={itemCollections}
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

            {/* Dossier Section */}
            {!isDraft && id && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <Pressable
                  onPress={() => {
                    if (!dossierData) loadDossier();
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

            {/* Marketplace Section */}
            {!isDraft && id && (
              <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
                <Pressable
                  onPress={() => {
                    if (marketResults.length === 0) loadMarketResults();
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

          </View>
        </Animated.ScrollView>

        {/* Sticky Save Button — appears on scroll, hidden when keyboard is open */}
        {showStickyButton && !keyboardVisible && (
          <View style={[styles.stickyButtonContainer, { backgroundColor: theme.card, borderTopColor: theme.border }]}>
            {isDraft ? (
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
            ) : (
              <Pressable
                onPress={onSaveNotes}
                disabled={savingNotes}
                style={[
                  styles.stickyButton,
                  { backgroundColor: theme.accent, opacity: savingNotes ? 0.7 : 1 },
                ]}
                accessibilityRole="button"
                accessibilityLabel="Save changes"
              >
                {savingNotes ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <>
                    <Ionicons name="save-outline" size={18} color="#FFFFFF" />
                    <Text style={styles.stickyButtonText}>Save Changes</Text>
                  </>
                )}
              </Pressable>
            )}
          </View>
        )}
      </SafeAreaView>

      {/* Price Explanation Bottom Sheet */}
      {featureFlags.FEATURE_EXPLAINABLE_AI_INTERFACES && priceEstimate && (
        <PriceExplanationSheet
          visible={showPriceExplanation}
          onClose={() => setShowPriceExplanation(false)}
          explanation={priceExplanationData}
          priceBand={priceEstimate.priceBand}
          currency={priceEstimate.currency}
        />
      )}
    </KeyboardAvoidingView>
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
    gap: 12,
  },
  name: {
    fontSize: 20,
    fontWeight: "700",
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
    fontSize: 16,
    fontWeight: "700",
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
});