/**
 * QuickScan capture screen.
 * Custom branded camera viewfinder -> branded AI analysis screen -> navigates to item card in draft mode.
 * Supports batch mode for scanning multiple items in sequence.
 */
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import React, { useCallback, useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Image,
  Animated,
  Dimensions,
  StatusBar,
  ScrollView,
  FlatList,
} from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider } from '@/data';
import { featureFlags } from '@/config/featureFlags';
import { fireHaptic, HapticIntent, confidenceToIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { isDeviceOnline } from '@/hooks/useNetworkStatus';
import { useToast } from '@/components/Toast';
import { AnimatedPressable } from '@/motion';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import type { QuickScanResult, CatalogAlternative } from '@/data/types';
import logger from '@/utils/logger';

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';
const FRAME_SIZE = 260;
const CORNER_LENGTH = 36;
const CORNER_THICKNESS = 4;
const CORNER_RADIUS = 16;
const { width: SCREEN_WIDTH } = Dimensions.get('window');

type ScanPhase = 'camera' | 'analyzing' | 'result' | 'done' | 'batch_result' | 'batch_summary';

/** Analysis step for the branded loading screen */
type AnalysisStep = {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
};

/** A scanned item kept in batch session memory */
type BatchScannedItem = {
  id: string;
  name: string;
  category: string;
  condition: string;
  estimatedMid: number;
  estimatedLow: number;
  estimatedHigh: number;
  confidence: number;
  imageUri: string;
  saved: boolean;
};

const ANALYSIS_STEPS: AnalysisStep[] = [
  { icon: 'sparkles', label: 'Identifying your item...' },
  { icon: 'trending-up', label: 'Checking marketplace prices...' },
  { icon: 'calculator', label: 'Calculating valuation...' },
];

function QuickScanScreen() {
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const { settings } = useSettings();
  const cameraRef = useRef<CameraView>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [phase, setPhase] = useState<ScanPhase>('camera');
  const [capturedUri, setCapturedUri] = useState<string | null>(null);
  const [analysisStepIndex, setAnalysisStepIndex] = useState(0);

  // Batch mode state
  const [batchMode, setBatchMode] = useState(false);
  const [batchItems, setBatchItems] = useState<BatchScannedItem[]>([]);
  const [currentBatchResult, setCurrentBatchResult] = useState<BatchScannedItem | null>(null);
  const [savingBatchItem, setSavingBatchItem] = useState(false);

  // Result screen state (intermediate screen with alternatives)
  const [scanResult, setScanResult] = useState<QuickScanResult | null>(null);

  // Slide-up animation for batch result overlay
  const batchOverlayAnim = useRef(new Animated.Value(0)).current;

  // Scanning line animation for analysis screen
  const scanLineAnim = useRef(new Animated.Value(0)).current;

  // Animate batch result overlay in
  useEffect(() => {
    if (phase === 'batch_result') {
      Animated.spring(batchOverlayAnim, {
        toValue: 1,
        useNativeDriver: true,
        tension: 50,
        friction: 9,
      }).start();
    } else {
      batchOverlayAnim.setValue(0);
    }
  }, [phase, batchOverlayAnim]);

  // Start scanning line animation when analyzing
  useEffect(() => {
    if (phase !== 'analyzing') return;
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(scanLineAnim, {
          toValue: 1,
          duration: 1800,
          useNativeDriver: true,
        }),
        Animated.timing(scanLineAnim, {
          toValue: 0,
          duration: 1800,
          useNativeDriver: true,
        }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [phase, scanLineAnim]);

  // Cycle through analysis steps
  useEffect(() => {
    if (phase !== 'analyzing') return;
    const interval = setInterval(() => {
      setAnalysisStepIndex((prev) =>
        prev < ANALYSIS_STEPS.length - 1 ? prev + 1 : prev,
      );
    }, 1500);
    return () => clearInterval(interval);
  }, [phase]);

  const resetCamera = useCallback(() => {
    setPhase('camera');
    setCapturedUri(null);
    setCurrentBatchResult(null);
    setScanResult(null);
    setAnalysisStepIndex(0);
  }, []);

  const handleSaveBatchItem = useCallback(async () => {
    if (!currentBatchResult || savingBatchItem) return;
    setSavingBatchItem(true);

    try {
      await dataProvider.persistQuickscanDraft({
        photoUri: currentBatchResult.imageUri,
        categoryId: currentBatchResult.category,
        title: currentBatchResult.name,
        attributes: {
          condition: currentBatchResult.condition,
          estimatedLow: currentBatchResult.estimatedLow,
          estimatedMid: currentBatchResult.estimatedMid,
          estimatedHigh: currentBatchResult.estimatedHigh,
          confidence: currentBatchResult.confidence,
        },
      });

      const savedItem = { ...currentBatchResult, saved: true };
      setBatchItems((prev) => [...prev, savedItem]);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Item saved to collection!', type: 'success' });
      resetCamera();
    } catch (err: unknown) {
      logger.warn('[QuickScan] batch save error:', err);
      showToast({
        message: (err as Error)?.message ?? 'Failed to save item.',
        type: 'error',
      });
    } finally {
      setSavingBatchItem(false);
    }
  }, [currentBatchResult, savingBatchItem, settings.hapticsEnabled, showToast, resetCamera]);

  const handleDiscardBatchItem = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    resetCamera();
  }, [settings.hapticsEnabled, resetCamera]);

  const handleCapture = useCallback(async () => {
    if (!cameraRef.current) return;

    // Network pre-check before attempting capture + upload
    const online = await isDeviceOnline();
    if (!online) {
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'No internet connection. Please check your network and try again.', type: 'error' });
      return;
    }

    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });

    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.8,
      });

      if (!photo?.uri) {
        showToast({ message: 'Failed to capture image.', type: 'error' });
        return;
      }

      setCapturedUri(photo.uri);
      setPhase('analyzing');
      setAnalysisStepIndex(0);

      // Run AI analysis
      const sr = await dataProvider.quickscanSingle(photo.uri);

      // Fire haptic based on confidence
      if (featureFlags.FEATURE_HAPTICS_MICRO_ANIMATIONS) {
        const intent = confidenceToIntent(sr.prediction.confidence);
        fireHaptic(intent);
      }

      if (batchMode) {
        // In batch mode: show compact overlay result card (no intermediate screen)
        const item: BatchScannedItem = {
          id: `batch-${Date.now()}`,
          name: sr.prediction.name,
          category: sr.attributes.category,
          condition: sr.attributes.conditionGuess ?? 'Not graded',
          estimatedMid: sr.prediction.estimatedMid,
          estimatedLow: sr.prediction.estimatedLow,
          estimatedHigh: sr.prediction.estimatedHigh,
          confidence: sr.prediction.confidence,
          imageUri: photo.uri,
          saved: false,
        };
        setCurrentBatchResult(item);
        setPhase('batch_result');
      } else {
        // Standard mode: show intermediate result screen with alternatives
        setScanResult(sr);
        setPhase('result');
      }
    } catch (err: unknown) {
      logger.warn('[QuickScan] error:', err);
      if (featureFlags.FEATURE_HAPTICS_MICRO_ANIMATIONS) {
        fireHaptic(HapticIntent.ALERT_TRIGGERED);
      }
      showToast({
        message: (err as Error)?.message ?? 'Unable to analyze image. Please try again.',
        type: 'error',
      });
      // Go back to camera on error
      setPhase('camera');
      setCapturedUri(null);
    }
  }, [settings.hapticsEnabled, showToast, batchMode]);

  // Handle selecting an alternative from the "Did you mean?" list
  const handleSelectAlternative = useCallback((alt: CatalogAlternative) => {
    if (!scanResult) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setScanResult({
      ...scanResult,
      prediction: {
        ...scanResult.prediction,
        name: alt.title ?? scanResult.prediction.name,
      },
      attributes: {
        ...scanResult.attributes,
        category: alt.category ?? scanResult.attributes.category,
        rarityScore: null,
      },
      catalogMatchId: alt.catalogItemId,
      catalogMatchKey: alt.itemKey,
    });
  }, [scanResult, settings.hapticsEnabled]);

  // Handle "Add to Collection" from the result screen
  const handleConfirmResult = useCallback(() => {
    if (!scanResult || !capturedUri) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setPhase('done');

    // Build notes from extracted details
    const details = scanResult.attributes.extractedDetails;
    const notesParts: string[] = [];
    if (details) {
      for (const [k, v] of Object.entries(details)) {
        if (v !== null && v !== undefined && v !== '') {
          const label = k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
          notesParts.push(`${label}: ${String(v)}`);
        }
      }
    }

    router.replace({
      pathname: '/item/[id]',
      params: {
        id: 'draft',
        draft: '1',
        name: scanResult.prediction.name,
        category: scanResult.attributes.category,
        condition: scanResult.attributes.conditionGuess ?? 'Not graded',
        value: String(scanResult.prediction.estimatedMid),
        q10: String(scanResult.prediction.estimatedLow),
        q50: String(scanResult.prediction.estimatedMid),
        q90: String(scanResult.prediction.estimatedHigh),
        confidence: String(Math.round(scanResult.prediction.confidence * 100)),
        imageUri: capturedUri,
        notes: notesParts.join('\n'),
        ...(scanResult.catalogMatchKey ? { catalogKey: scanResult.catalogMatchKey } : {}),
      },
    });
  }, [scanResult, capturedUri, settings.hapticsEnabled]);

  const handleCancel = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // If in batch mode with scanned items, show summary
    if (batchMode && batchItems.length > 0) {
      setPhase('batch_summary');
      return;
    }
    router.back();
  }, [settings.hapticsEnabled, batchMode, batchItems.length]);

  const handleBatchDone = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setPhase('batch_summary');
  }, [settings.hapticsEnabled]);

  const handleFinishBatch = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.back();
  }, [settings.hapticsEnabled]);

  const toggleBatchMode = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setBatchMode((prev) => !prev);
    if (batchMode) {
      // Turning off batch mode -- if items were scanned, show summary
      if (batchItems.length > 0) {
        setPhase('batch_summary');
      }
    }
  }, [settings.hapticsEnabled, batchMode, batchItems.length]);

  const savedBatchCount = batchItems.filter((i) => i.saved).length;
  const totalBatchValue = batchItems
    .filter((i) => i.saved)
    .reduce((sum, i) => sum + i.estimatedMid, 0);

  // Permission loading
  if (!permission) {
    return (
      <View style={[styles.container, { backgroundColor: '#000' }]}>
        <ActivityIndicator size="large" color={TIFFANY} />
      </View>
    );
  }

  // Permission denied
  if (!permission.granted) {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.permissionContainer}>
          <Ionicons name="camera-outline" size={64} color={colors.muted} />
          <Text style={[styles.permissionTitle, { color: colors.text }]}>
            Camera Permission Required
          </Text>
          <Text style={[styles.permissionText, { color: colors.muted }]}>
            We need camera access to scan your collectibles with AI.
          </Text>
          <AnimatedPressable
            style={[styles.permissionButton, { backgroundColor: TIFFANY }]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              requestPermission();
            }}
            accessibilityRole="button"
            accessibilityLabel="Grant camera permission"
          >
            <Text style={styles.permissionButtonText}>Grant Permission</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={styles.backBtn}
            onPress={handleCancel}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Text style={[styles.backBtnText, { color: colors.muted }]}>Go Back</Text>
          </AnimatedPressable>
        </View>
      </View>
    );
  }

  // ---- Result Screen (intermediate screen with alternatives) ----
  if (phase === 'result' && scanResult && capturedUri) {
    const fc = scanResult.fieldConfidence;
    const alts = scanResult.alternatives ?? [];
    const priceBandLow = scanResult.prediction.estimatedLow;
    const priceBandMid = scanResult.prediction.estimatedMid;
    const priceBandHigh = scanResult.prediction.estimatedHigh;
    const extracted = scanResult.attributes.extractedDetails;

    // Confidence ring SVG helper
    const RING_SIZE = 56;
    const RING_STROKE = 4;
    const RING_RADIUS = (RING_SIZE - RING_STROKE) / 2;
    const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;
    const ConfidenceRing = ({ value, label }: { value: number; label: string }) => {
      const pct = Math.round(value * 100);
      const strokeDash = RING_CIRCUMFERENCE * value;
      const ringColor = value >= 0.75 ? '#22C55E' : value >= 0.5 ? '#F59E0B' : '#EF4444';
      return (
        <View style={resultStyles.ringItem}>
          <View style={resultStyles.ringContainer}>
            <Svg width={RING_SIZE} height={RING_SIZE}>
              <Circle
                cx={RING_SIZE / 2}
                cy={RING_SIZE / 2}
                r={RING_RADIUS}
                stroke={colors.border}
                strokeWidth={RING_STROKE}
                fill="none"
              />
              <Circle
                cx={RING_SIZE / 2}
                cy={RING_SIZE / 2}
                r={RING_RADIUS}
                stroke={ringColor}
                strokeWidth={RING_STROKE}
                fill="none"
                strokeDasharray={`${strokeDash} ${RING_CIRCUMFERENCE}`}
                strokeDashoffset={RING_CIRCUMFERENCE * 0.25}
                strokeLinecap="round"
                rotation={-90}
                origin={`${RING_SIZE / 2}, ${RING_SIZE / 2}`}
              />
            </Svg>
            <Text style={[resultStyles.ringPct, { color: ringColor }]}>{pct}%</Text>
          </View>
          <Text style={[resultStyles.ringLabel, { color: colors.muted }]}>{label}</Text>
        </View>
      );
    };

    // Pretty-print attribute key
    const formatKey = (k: string) =>
      k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

    // Filter extracted details to show only meaningful ones
    const detailEntries = extracted
      ? Object.entries(extracted).filter(
          ([, v]) => v !== null && v !== undefined && v !== '' && v !== false,
        )
      : [];

    // Price band width percentages for bar
    const priceMax = priceBandHigh > 0 ? priceBandHigh : priceBandMid * 1.5 || 1;
    const lowPct = priceBandLow > 0 ? Math.round((priceBandLow / priceMax) * 100) : 0;
    const midPct = priceBandMid > 0 ? Math.round((priceBandMid / priceMax) * 100) : 0;

    // Overall confidence for status badge
    const overallConf = fc
      ? Math.round(((fc.name + fc.category + fc.condition) / 3) * 100)
      : Math.round(scanResult.prediction.confidence * 100);
    const confLabel = overallConf >= 75 ? 'High Confidence' : overallConf >= 50 ? 'Moderate' : 'Low Confidence';
    const confBadgeColor = overallConf >= 75 ? '#22C55E' : overallConf >= 50 ? '#F59E0B' : '#EF4444';

    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <StatusBar barStyle="light-content" />
        <ScrollView contentContainerStyle={resultStyles.scrollContent} bounces={false}>
          {/* Hero image with overlay */}
          <View style={resultStyles.heroContainer}>
            <Image
              source={{ uri: capturedUri }}
              style={resultStyles.heroImage}
              resizeMode="cover"
            />
            <View style={resultStyles.heroOverlay} />
            {/* Confidence badge on hero */}
            <View style={[resultStyles.heroBadge, { backgroundColor: confBadgeColor + '20', borderColor: confBadgeColor + '40' }]}>
              <View style={[resultStyles.heroBadgeDot, { backgroundColor: confBadgeColor }]} />
              <Text style={[resultStyles.heroBadgeText, { color: confBadgeColor }]}>{confLabel}</Text>
            </View>
            {/* Retake button on hero */}
            <AnimatedPressable
              style={resultStyles.heroRetake}
              onPress={resetCamera}
              accessibilityRole="button"
              accessibilityLabel="Retake photo"
            >
              <Ionicons name="camera-reverse-outline" size={22} color="#FFFFFF" />
            </AnimatedPressable>
          </View>

          {/* Item identification card — overlaps hero */}
          <View style={[resultStyles.idCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[resultStyles.idName, { color: colors.text }]} numberOfLines={3}>
              {scanResult.prediction.name || 'Unknown Item'}
            </Text>
            <View style={resultStyles.idMeta}>
              <View style={[resultStyles.categoryChip, { backgroundColor: TIFFANY + '18' }]}>
                <Ionicons name="pricetag" size={12} color={TIFFANY_DARK} />
                <Text style={[resultStyles.categoryChipText, { color: TIFFANY_DARK }]}>
                  {scanResult.attributes.category.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </Text>
              </View>
              {scanResult.attributes.conditionGuess && (
                <View style={[resultStyles.conditionChip, { backgroundColor: colors.border + '80' }]}>
                  <Ionicons name="shield-checkmark" size={12} color={colors.muted} />
                  <Text style={[resultStyles.conditionChipText, { color: colors.text }]}>
                    {scanResult.attributes.conditionGuess.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </Text>
                </View>
              )}
            </View>
          </View>

          {/* Price band section */}
          {priceBandMid > 0 && (
            <View style={[resultStyles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={resultStyles.sectionHeader}>
                <Ionicons name="analytics-outline" size={18} color={TIFFANY_DARK} />
                <Text style={[resultStyles.sectionTitle, { color: colors.text }]}>Estimated Value</Text>
              </View>
              <Text style={[resultStyles.priceHero, { color: colors.text }]}>
                {formatPrice(priceBandMid, settings.currency)}
              </Text>
              {/* Price band bar */}
              {priceBandLow > 0 && priceBandHigh > 0 && (
                <View style={resultStyles.priceBandContainer}>
                  <View style={[resultStyles.priceBandTrack, { backgroundColor: colors.border + '60' }]}>
                    <View style={[resultStyles.priceBandFill, { left: `${lowPct}%`, width: `${midPct - lowPct}%` }]} />
                    <View style={[resultStyles.priceBandMarker, { left: `${midPct}%` }]} />
                  </View>
                  <View style={resultStyles.priceBandLabels}>
                    <Text style={[resultStyles.priceBandLabel, { color: colors.muted }]}>
                      {formatPrice(priceBandLow, settings.currency)}
                    </Text>
                    <Text style={[resultStyles.priceBandLabel, { color: colors.muted }]}>
                      {formatPrice(priceBandHigh, settings.currency)}
                    </Text>
                  </View>
                </View>
              )}
            </View>
          )}

          {/* Confidence rings */}
          {fc && (
            <View style={[resultStyles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={resultStyles.sectionHeader}>
                <Ionicons name="checkmark-done-circle-outline" size={18} color={TIFFANY_DARK} />
                <Text style={[resultStyles.sectionTitle, { color: colors.text }]}>AI Confidence</Text>
              </View>
              <View style={resultStyles.ringsRow}>
                <ConfidenceRing value={fc.name} label="Name" />
                <ConfidenceRing value={fc.category} label="Category" />
                <ConfidenceRing value={fc.condition} label="Condition" />
              </View>
            </View>
          )}

          {/* Extracted details */}
          {detailEntries.length > 0 && (
            <View style={[resultStyles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={resultStyles.sectionHeader}>
                <Ionicons name="list-outline" size={18} color={TIFFANY_DARK} />
                <Text style={[resultStyles.sectionTitle, { color: colors.text }]}>Detected Details</Text>
              </View>
              <View style={resultStyles.detailsGrid}>
                {detailEntries.map(([key, val]) => (
                  <View key={key} style={resultStyles.detailRow}>
                    <Text style={[resultStyles.detailKey, { color: colors.muted }]}>{formatKey(key)}</Text>
                    <Text style={[resultStyles.detailVal, { color: colors.text }]} numberOfLines={1}>
                      {typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val)}
                    </Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {/* "Did you mean?" alternatives */}
          {alts.length > 0 && (
            <View style={resultStyles.altSection}>
              <View style={resultStyles.sectionHeader}>
                <Ionicons name="swap-horizontal-outline" size={18} color={TIFFANY_DARK} />
                <Text style={[resultStyles.sectionTitle, { color: colors.text }]}>Did you mean?</Text>
              </View>
              {alts.map((alt, idx) => {
                const isSelected = alt.catalogItemId === scanResult.catalogMatchId;
                return (
                  <AnimatedPressable
                    key={alt.catalogItemId ?? `alt-${idx}`}
                    style={[
                      resultStyles.altCard,
                      {
                        backgroundColor: colors.card,
                        borderColor: isSelected ? TIFFANY : colors.border,
                        borderWidth: isSelected ? 2 : 1,
                      },
                    ]}
                    onPress={() => handleSelectAlternative(alt)}
                    accessibilityRole="button"
                    accessibilityLabel={`Select ${alt.title ?? 'alternative'}`}
                  >
                    {isSelected && (
                      <View style={[resultStyles.altSelectedBadge, { backgroundColor: TIFFANY }]}>
                        <Ionicons name="checkmark" size={10} color="#FFFFFF" />
                      </View>
                    )}
                    {alt.imageUrl ? (
                      <Image source={{ uri: alt.imageUrl }} style={resultStyles.altImage} resizeMode="cover" />
                    ) : (
                      <View style={[resultStyles.altImage, { backgroundColor: colors.border }]}>
                        <Ionicons name="image-outline" size={20} color={colors.muted} />
                      </View>
                    )}
                    <View style={resultStyles.altInfo}>
                      <Text style={[resultStyles.altTitle, { color: colors.text }]} numberOfLines={2}>
                        {alt.title ?? 'Unknown'}
                      </Text>
                      <View style={resultStyles.altMeta}>
                        {alt.brand && (
                          <Text style={[resultStyles.altBrand, { color: colors.muted }]} numberOfLines={1}>
                            {alt.brand}
                          </Text>
                        )}
                        {alt.rarity && (
                          <View style={[resultStyles.altRarityBadge, { backgroundColor: TIFFANY + '15' }]}>
                            <Text style={[resultStyles.altRarity, { color: TIFFANY_DARK }]} numberOfLines={1}>
                              {alt.rarity}
                            </Text>
                          </View>
                        )}
                        {alt.setCode && (
                          <Text style={[resultStyles.altSetCode, { color: colors.muted }]} numberOfLines={1}>
                            {alt.setCode}
                          </Text>
                        )}
                      </View>
                    </View>
                    <View style={[resultStyles.altScoreBadge, { backgroundColor: TIFFANY + '12' }]}>
                      <Text style={[resultStyles.altScoreText, { color: TIFFANY_DARK }]}>
                        {Math.round(alt.matchScore * 100)}%
                      </Text>
                    </View>
                  </AnimatedPressable>
                );
              })}
            </View>
          )}
        </ScrollView>

        {/* Bottom action bar */}
        <View style={[resultStyles.bottomBar, { backgroundColor: colors.background, borderTopColor: colors.border }]}>
          <AnimatedPressable
            style={[resultStyles.addBtn, { backgroundColor: TIFFANY }]}
            onPress={handleConfirmResult}
            accessibilityRole="button"
            accessibilityLabel="Add to collection"
          >
            <Ionicons name="add-circle" size={22} color="#FFFFFF" />
            <Text style={resultStyles.addBtnText}>Add to Collection</Text>
          </AnimatedPressable>
        </View>
      </View>
    );
  }

  // ---- Batch Summary Screen ----
  if (phase === 'batch_summary') {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <StatusBar barStyle="dark-content" />
        <View style={styles.summaryHeader}>
          <Ionicons name="checkmark-circle" size={56} color={TIFFANY} />
          <Text style={[styles.summaryTitle, { color: colors.text }]}>
            Batch Scan Complete
          </Text>
          <Text style={[styles.summarySubtitle, { color: colors.muted }]}>
            You scanned {savedBatchCount} item{savedBatchCount !== 1 ? 's' : ''}
          </Text>
          {savedBatchCount > 0 && (
            <View style={[styles.summaryValueBadge, { backgroundColor: TIFFANY + '18' }]}>
              <Text style={[styles.summaryValueLabel, { color: TIFFANY_DARK }]}>
                Total estimated value
              </Text>
              <Text style={[styles.summaryValueAmount, { color: TIFFANY_DARK }]}>
                {formatPrice(totalBatchValue, settings.currency)}
              </Text>
            </View>
          )}
        </View>

        <FlatList
          data={batchItems.filter((i) => i.saved)}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.summaryList}
          renderItem={({ item }) => (
            <View style={[styles.summaryItemCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Image
                source={{ uri: item.imageUri }}
                style={styles.summaryItemImage}
                resizeMode="cover"
              />
              <View style={styles.summaryItemInfo}>
                <Text style={[styles.summaryItemName, { color: colors.text }]} numberOfLines={1}>
                  {item.name}
                </Text>
                <Text style={[styles.summaryItemCategory, { color: colors.muted }]} numberOfLines={1}>
                  {item.category} -- {item.condition}
                </Text>
              </View>
              <Text style={[styles.summaryItemPrice, { color: TIFFANY_DARK }]}>
                {formatPrice(item.estimatedMid, settings.currency)}
              </Text>
            </View>
          )}
          ListEmptyComponent={
            <View style={styles.summaryEmpty}>
              <Text style={[styles.summaryEmptyText, { color: colors.muted }]}>
                No items were saved during this session.
              </Text>
            </View>
          }
        />

        <View style={styles.summaryBottomBar}>
          <AnimatedPressable
            style={[styles.summaryDoneBtn, { backgroundColor: TIFFANY }]}
            onPress={handleFinishBatch}
            accessibilityRole="button"
            accessibilityLabel="Done, go back"
          >
            <Text style={styles.summaryDoneBtnText}>Done</Text>
          </AnimatedPressable>
        </View>
      </View>
    );
  }

  // ---- Branded Analysis Screen ----
  if (phase === 'analyzing' && capturedUri) {
    const currentStep = ANALYSIS_STEPS[analysisStepIndex];
    const imageHeight = SCREEN_WIDTH * 0.75;
    const scanLineTranslate = scanLineAnim.interpolate({
      inputRange: [0, 1],
      outputRange: [0, imageHeight - 4],
    });

    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <StatusBar barStyle="light-content" />

        {/* Captured image with scan line */}
        <View style={[styles.analysisImageContainer, { height: imageHeight }]}>
          <Image
            source={{ uri: capturedUri }}
            style={styles.analysisImage}
            resizeMode="cover"
          />
          {/* Dark tint overlay */}
          <View style={styles.analysisImageOverlay} />
          {/* Animated scan line */}
          <Animated.View
            style={[
              styles.scanLine,
              { transform: [{ translateY: scanLineTranslate }] },
            ]}
          />
          {/* Corner brackets on the image */}
          <View style={styles.analysisFrameCorners}>
            <View style={[styles.aCorner, styles.aCornerTL]} />
            <View style={[styles.aCorner, styles.aCornerTR]} />
            <View style={[styles.aCorner, styles.aCornerBL]} />
            <View style={[styles.aCorner, styles.aCornerBR]} />
          </View>
        </View>

        {/* Step progress */}
        <View style={styles.analysisStepsContainer}>
          {ANALYSIS_STEPS.map((step, idx) => {
            const isActive = idx === analysisStepIndex;
            const isDone = idx < analysisStepIndex;
            const iconColor = isDone
              ? TIFFANY
              : isActive
                ? TIFFANY
                : colors.muted + '60';
            const textColor = isDone
              ? TIFFANY
              : isActive
                ? colors.text
                : colors.muted + '60';

            return (
              <View key={idx} style={styles.analysisStepRow}>
                {isDone ? (
                  <Ionicons name="checkmark-circle" size={22} color={TIFFANY} />
                ) : (
                  <Ionicons name={step.icon} size={22} color={iconColor} />
                )}
                <Text style={[styles.analysisStepText, { color: textColor }]}>
                  {step.label}
                </Text>
                {isActive && !isDone && (
                  <ActivityIndicator
                    size="small"
                    color={TIFFANY}
                    style={{ marginLeft: 8 }}
                  />
                )}
              </View>
            );
          })}
        </View>

        {/* Bottom hint */}
        <View style={styles.analysisBottomHint}>
          <Text style={[styles.analysisHintText, { color: colors.muted }]}>
            Hold tight -- this usually takes a few seconds
          </Text>
        </View>
      </View>
    );
  }

  // ---- Camera Viewfinder (also serves as background for batch_result overlay) ----
  return (
    <View style={styles.cameraRoot}>
      <StatusBar barStyle="light-content" />
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        facing="back"
      >
        {/* Semi-transparent overlay with cutout */}
        <View style={styles.overlay}>
          {/* Top bar */}
          <SafeAreaView style={styles.topBar} edges={['top']}>
            <AnimatedPressable
              onPress={handleCancel}
              style={styles.cancelBtn}
              accessibilityRole="button"
              accessibilityLabel="Cancel and go back"
            >
              <Ionicons name="close" size={28} color="#FFFFFF" />
            </AnimatedPressable>
            <Text style={styles.topBarTitle}>QuickScan</Text>

            {/* Batch mode toggle pill */}
            <AnimatedPressable
              onPress={toggleBatchMode}
              style={[
                styles.batchPill,
                batchMode
                  ? { backgroundColor: TIFFANY }
                  : { backgroundColor: 'rgba(255,255,255,0.2)' },
              ]}
              accessibilityRole="switch"
              accessibilityLabel={`Batch mode ${batchMode ? 'on' : 'off'}`}
              accessibilityState={{ checked: batchMode }}
            >
              <Ionicons
                name="layers-outline"
                size={16}
                color={batchMode ? '#FFFFFF' : 'rgba(255,255,255,0.8)'}
              />
              <Text
                style={[
                  styles.batchPillText,
                  { color: batchMode ? '#FFFFFF' : 'rgba(255,255,255,0.8)' },
                ]}
              >
                Batch
              </Text>
            </AnimatedPressable>
          </SafeAreaView>

          {/* Batch counter badge */}
          {batchMode && savedBatchCount > 0 && (
            <View style={styles.batchCounterRow}>
              <View style={[styles.batchCounterBadge, { backgroundColor: TIFFANY }]}>
                <Ionicons name="checkmark-circle" size={14} color="#FFFFFF" />
                <Text style={styles.batchCounterText}>
                  {savedBatchCount} item{savedBatchCount !== 1 ? 's' : ''} scanned
                </Text>
              </View>
            </View>
          )}

          {/* Center area: dark edges + clear frame */}
          <View style={styles.centerRow}>
            <View style={styles.overlayFill} />
            <View style={styles.frameCutout}>
              {/* Corner brackets */}
              <View style={[styles.corner, styles.cornerTL]} />
              <View style={[styles.corner, styles.cornerTR]} />
              <View style={[styles.corner, styles.cornerBL]} />
              <View style={[styles.corner, styles.cornerBR]} />
            </View>
            <View style={styles.overlayFill} />
          </View>

          {/* Hint text below frame */}
          <View style={styles.hintArea}>
            <Text style={styles.hintText}>
              {batchMode ? 'Batch mode -- scan multiple items' : 'Point at your collectible'}
            </Text>
          </View>

          {/* Bottom: capture button + batch done */}
          <View style={styles.bottomBar}>
            {batchMode && savedBatchCount > 0 && phase === 'camera' && (
              <AnimatedPressable
                onPress={handleBatchDone}
                style={[styles.batchDoneBtn, { backgroundColor: 'rgba(255,255,255,0.2)' }]}
                accessibilityRole="button"
                accessibilityLabel="Finish batch scanning"
              >
                <Text style={styles.batchDoneBtnText}>
                  Done ({savedBatchCount})
                </Text>
              </AnimatedPressable>
            )}
            <AnimatedPressable
              onPress={phase === 'camera' ? handleCapture : undefined}
              style={[
                styles.captureBtn,
                phase !== 'camera' && { opacity: 0.5 },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Take photo"
              disabled={phase !== 'camera'}
            >
              <View style={styles.captureBtnInner}>
                <Ionicons name="camera" size={32} color="#FFFFFF" />
              </View>
            </AnimatedPressable>
          </View>

          {/* Batch result overlay card -- slides up from bottom */}
          {phase === 'batch_result' && currentBatchResult && (
            <Animated.View
              style={[
                styles.batchOverlay,
                {
                  transform: [
                    {
                      translateY: batchOverlayAnim.interpolate({
                        inputRange: [0, 1],
                        outputRange: [250, 0],
                      }),
                    },
                  ],
                  opacity: batchOverlayAnim,
                },
              ]}
            >
              <View style={[styles.batchOverlayCard, { backgroundColor: colors.card }]}>
                <View style={styles.batchOverlayHandle} />
                <View style={styles.batchOverlayContent}>
                  <Image
                    source={{ uri: currentBatchResult.imageUri }}
                    style={styles.batchOverlayImage}
                    resizeMode="cover"
                  />
                  <View style={styles.batchOverlayInfo}>
                    <Text
                      style={[styles.batchOverlayName, { color: colors.text }]}
                      numberOfLines={2}
                    >
                      {currentBatchResult.name}
                    </Text>
                    <Text
                      style={[styles.batchOverlayCategory, { color: colors.muted }]}
                      numberOfLines={1}
                    >
                      {currentBatchResult.category} -- {currentBatchResult.condition}
                    </Text>
                    <Text style={[styles.batchOverlayPrice, { color: TIFFANY_DARK }]}>
                      {formatPrice(currentBatchResult.estimatedMid, settings.currency)}
                    </Text>
                  </View>
                </View>

                <View style={styles.batchOverlayButtons}>
                  <AnimatedPressable
                    onPress={handleDiscardBatchItem}
                    style={[styles.batchOverlayBtn, styles.batchDiscardBtn, { borderColor: colors.border }]}
                    accessibilityRole="button"
                    accessibilityLabel="Discard this item"
                  >
                    <Ionicons name="close-circle-outline" size={20} color={colors.muted} />
                    <Text style={[styles.batchOverlayBtnText, { color: colors.muted }]}>
                      Discard
                    </Text>
                  </AnimatedPressable>

                  <AnimatedPressable
                    onPress={handleSaveBatchItem}
                    style={[styles.batchOverlayBtn, styles.batchSaveBtn, { backgroundColor: TIFFANY }]}
                    accessibilityRole="button"
                    accessibilityLabel="Save item and scan next"
                    disabled={savingBatchItem}
                  >
                    {savingBatchItem ? (
                      <ActivityIndicator size="small" color="#FFFFFF" />
                    ) : (
                      <>
                        <Ionicons name="checkmark-circle-outline" size={20} color="#FFFFFF" />
                        <Text style={[styles.batchOverlayBtnText, { color: '#FFFFFF' }]}>
                          Save & Next
                        </Text>
                      </>
                    )}
                  </AnimatedPressable>
                </View>
              </View>
            </Animated.View>
          )}
        </View>
      </CameraView>
    </View>
  );
}

export default function QuickScanScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Quick Scan">
      <QuickScanScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  // ---- Permission Screen ----
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  permissionTitle: {
    fontSize: 20,
    fontWeight: '600',
    marginTop: 16,
    marginBottom: 8,
  },
  permissionText: {
    fontSize: 15,
    textAlign: 'center',
    marginBottom: 24,
  },
  permissionButton: {
    paddingHorizontal: 28,
    paddingVertical: 16,
    borderRadius: 12,
  },
  permissionButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  backBtn: {
    marginTop: 16,
    padding: 8,
  },
  backBtnText: {
    fontSize: 15,
  },

  // ---- Camera Viewfinder ----
  cameraRoot: {
    flex: 1,
    backgroundColor: '#000',
  },
  overlay: {
    flex: 1,
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
    backgroundColor: 'rgba(0,0,0,0.45)',
  },
  cancelBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(0,0,0,0.4)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  topBarTitle: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 0.3,
  },

  // ---- Batch Mode Toggle ----
  batchPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 20,
  },
  batchPillText: {
    fontSize: 13,
    fontWeight: '600',
  },

  // ---- Batch Counter Badge ----
  batchCounterRow: {
    alignItems: 'center',
    paddingVertical: 6,
    backgroundColor: 'rgba(0,0,0,0.45)',
  },
  batchCounterBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 14,
  },
  batchCounterText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },

  centerRow: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  overlayFill: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
  },
  frameCutout: {
    width: FRAME_SIZE,
    height: FRAME_SIZE,
    borderRadius: CORNER_RADIUS,
    position: 'relative',
    // Transparent center -- the camera shows through here
  },
  corner: {
    position: 'absolute',
    width: CORNER_LENGTH,
    height: CORNER_LENGTH,
    borderColor: TIFFANY,
  },
  cornerTL: {
    top: 0,
    left: 0,
    borderTopWidth: CORNER_THICKNESS,
    borderLeftWidth: CORNER_THICKNESS,
    borderTopLeftRadius: CORNER_RADIUS,
  },
  cornerTR: {
    top: 0,
    right: 0,
    borderTopWidth: CORNER_THICKNESS,
    borderRightWidth: CORNER_THICKNESS,
    borderTopRightRadius: CORNER_RADIUS,
  },
  cornerBL: {
    bottom: 0,
    left: 0,
    borderBottomWidth: CORNER_THICKNESS,
    borderLeftWidth: CORNER_THICKNESS,
    borderBottomLeftRadius: CORNER_RADIUS,
  },
  cornerBR: {
    bottom: 0,
    right: 0,
    borderBottomWidth: CORNER_THICKNESS,
    borderRightWidth: CORNER_THICKNESS,
    borderBottomRightRadius: CORNER_RADIUS,
  },
  hintArea: {
    alignItems: 'center',
    paddingVertical: 20,
    backgroundColor: 'rgba(0,0,0,0.55)',
  },
  hintText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '500',
    opacity: 0.9,
  },
  bottomBar: {
    alignItems: 'center',
    paddingBottom: 48,
    paddingTop: 16,
    backgroundColor: 'rgba(0,0,0,0.55)',
  },
  captureBtn: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: TIFFANY,
    alignItems: 'center',
    justifyContent: 'center',
    // Outer ring effect
    borderWidth: 4,
    borderColor: 'rgba(255,255,255,0.3)',
  },
  captureBtnInner: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: TIFFANY,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // ---- Batch Done Button ----
  batchDoneBtn: {
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 20,
    marginBottom: 12,
  },
  batchDoneBtnText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },

  // ---- Batch Result Overlay ----
  batchOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
  },
  batchOverlayCard: {
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 12,
    paddingBottom: 36,
    paddingHorizontal: 20,
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -4 },
    elevation: 8,
  },
  batchOverlayHandle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: 'rgba(0,0,0,0.15)',
    alignSelf: 'center',
    marginBottom: 16,
  },
  batchOverlayContent: {
    flexDirection: 'row',
    gap: 14,
    marginBottom: 16,
  },
  batchOverlayImage: {
    width: 72,
    height: 72,
    borderRadius: 12,
    backgroundColor: '#E2E8F0',
  },
  batchOverlayInfo: {
    flex: 1,
    justifyContent: 'center',
    gap: 3,
  },
  batchOverlayName: {
    fontSize: 16,
    fontWeight: '600',
  },
  batchOverlayCategory: {
    fontSize: 13,
    fontWeight: '400',
  },
  batchOverlayPrice: {
    fontSize: 18,
    fontWeight: '700',
    marginTop: 2,
  },
  batchOverlayButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  batchOverlayBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 14,
    borderRadius: 14,
  },
  batchDiscardBtn: {
    borderWidth: 1,
  },
  batchSaveBtn: {
    // backgroundColor set inline
  },
  batchOverlayBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },

  // ---- Batch Summary Screen ----
  summaryHeader: {
    alignItems: 'center',
    paddingTop: 40,
    paddingBottom: 24,
    paddingHorizontal: 24,
    gap: 8,
  },
  summaryTitle: {
    fontSize: 24,
    fontWeight: '700',
    marginTop: 12,
  },
  summarySubtitle: {
    fontSize: 16,
    fontWeight: '400',
  },
  summaryValueBadge: {
    marginTop: 12,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 16,
    alignItems: 'center',
    gap: 4,
  },
  summaryValueLabel: {
    fontSize: 13,
    fontWeight: '500',
  },
  summaryValueAmount: {
    fontSize: 28,
    fontWeight: '700',
  },
  summaryList: {
    paddingHorizontal: 20,
    paddingBottom: 100,
    gap: 10,
  },
  summaryItemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 14,
    borderWidth: 1,
    gap: 12,
  },
  summaryItemImage: {
    width: 48,
    height: 48,
    borderRadius: 10,
    backgroundColor: '#E2E8F0',
  },
  summaryItemInfo: {
    flex: 1,
    gap: 2,
  },
  summaryItemName: {
    fontSize: 15,
    fontWeight: '600',
  },
  summaryItemCategory: {
    fontSize: 13,
    fontWeight: '400',
  },
  summaryItemPrice: {
    fontSize: 16,
    fontWeight: '700',
  },
  summaryEmpty: {
    alignItems: 'center',
    paddingTop: 40,
  },
  summaryEmptyText: {
    fontSize: 15,
    fontWeight: '400',
  },
  summaryBottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: 20,
    paddingBottom: 40,
    paddingTop: 16,
  },
  summaryDoneBtn: {
    alignItems: 'center',
    paddingVertical: 16,
    borderRadius: 14,
  },
  summaryDoneBtnText: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
  },

  // ---- Branded Analysis Screen ----
  analysisImageContainer: {
    width: '100%',
    overflow: 'hidden',
    position: 'relative',
  },
  analysisImage: {
    width: '100%',
    height: '100%',
  },
  analysisImageOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.2)',
  },
  scanLine: {
    position: 'absolute',
    left: 16,
    right: 16,
    height: 3,
    backgroundColor: TIFFANY,
    borderRadius: 2,
    shadowColor: TIFFANY,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 8,
    elevation: 4,
  },
  analysisFrameCorners: {
    position: 'absolute',
    top: 20,
    left: 20,
    right: 20,
    bottom: 20,
  },
  aCorner: {
    position: 'absolute',
    width: 28,
    height: 28,
    borderColor: TIFFANY,
  },
  aCornerTL: {
    top: 0,
    left: 0,
    borderTopWidth: 3,
    borderLeftWidth: 3,
    borderTopLeftRadius: 10,
  },
  aCornerTR: {
    top: 0,
    right: 0,
    borderTopWidth: 3,
    borderRightWidth: 3,
    borderTopRightRadius: 10,
  },
  aCornerBL: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
    borderBottomLeftRadius: 10,
  },
  aCornerBR: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 3,
    borderRightWidth: 3,
    borderBottomRightRadius: 10,
  },
  analysisStepsContainer: {
    paddingHorizontal: 32,
    paddingTop: 36,
    gap: 20,
  },
  analysisStepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  analysisStepText: {
    fontSize: 16,
    fontWeight: '500',
    flex: 1,
  },
  analysisBottomHint: {
    flex: 1,
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingBottom: 48,
  },
  analysisHintText: {
    fontSize: 13,
    fontWeight: '400',
  },
});

// ---- Result Screen Styles (Pro-Grade) ----
const resultStyles = StyleSheet.create({
  scrollContent: {
    paddingBottom: 100,
  },
  // Hero image
  heroContainer: {
    width: '100%',
    height: SCREEN_WIDTH * 0.85,
    position: 'relative',
  },
  heroImage: {
    width: '100%',
    height: '100%',
  },
  heroOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.15)',
  },
  heroBadge: {
    position: 'absolute',
    top: 56,
    left: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
  },
  heroBadgeDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  heroBadgeText: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  heroRetake: {
    position: 'absolute',
    top: 54,
    right: 16,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  // ID Card (overlaps hero)
  idCard: {
    marginTop: -32,
    marginHorizontal: 16,
    padding: 20,
    borderRadius: 20,
    borderWidth: 1,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  idName: {
    fontSize: 22,
    fontWeight: '800',
    lineHeight: 28,
    letterSpacing: -0.3,
  },
  idMeta: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  categoryChipText: {
    fontSize: 12,
    fontWeight: '600',
  },
  conditionChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  conditionChipText: {
    fontSize: 12,
    fontWeight: '600',
  },
  // Section card (reused for price, confidence, details)
  section: {
    marginTop: 12,
    marginHorizontal: 16,
    padding: 18,
    borderRadius: 16,
    borderWidth: 1,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 14,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  // Price
  priceHero: {
    fontSize: 32,
    fontWeight: '800',
    letterSpacing: -0.5,
    marginBottom: 12,
  },
  priceBandContainer: {
    gap: 6,
  },
  priceBandTrack: {
    height: 6,
    borderRadius: 3,
    position: 'relative',
    overflow: 'hidden',
  },
  priceBandFill: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    backgroundColor: TIFFANY,
    borderRadius: 3,
    opacity: 0.5,
  },
  priceBandMarker: {
    position: 'absolute',
    top: -3,
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: TIFFANY,
    marginLeft: -6,
    borderWidth: 2,
    borderColor: '#FFFFFF',
    shadowColor: TIFFANY,
    shadowOpacity: 0.4,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 0 },
    elevation: 3,
  },
  priceBandLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  priceBandLabel: {
    fontSize: 12,
    fontWeight: '500',
  },
  // Confidence rings
  ringsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  ringItem: {
    alignItems: 'center',
    gap: 6,
  },
  ringContainer: {
    width: 56,
    height: 56,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ringPct: {
    position: 'absolute',
    fontSize: 13,
    fontWeight: '800',
  },
  ringLabel: {
    fontSize: 12,
    fontWeight: '500',
    letterSpacing: 0.2,
  },
  // Extracted details grid
  detailsGrid: {
    gap: 0,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(128,128,128,0.15)',
  },
  detailKey: {
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
  },
  detailVal: {
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'right',
    flex: 1,
  },
  // Alternatives
  altSection: {
    marginTop: 12,
    marginHorizontal: 16,
    gap: 10,
  },
  altCard: {
    flexDirection: 'row',
    padding: 12,
    borderRadius: 14,
    gap: 12,
    alignItems: 'center',
    position: 'relative',
  },
  altSelectedBadge: {
    position: 'absolute',
    top: -4,
    right: -4,
    width: 20,
    height: 20,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1,
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  altImage: {
    width: 52,
    height: 52,
    borderRadius: 10,
    backgroundColor: '#E2E8F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  altInfo: {
    flex: 1,
    gap: 4,
  },
  altTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  altMeta: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    alignItems: 'center',
  },
  altBrand: {
    fontSize: 12,
    fontWeight: '400',
  },
  altRarityBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  altRarity: {
    fontSize: 11,
    fontWeight: '600',
  },
  altSetCode: {
    fontSize: 11,
    fontWeight: '500',
    fontStyle: 'italic',
  },
  altScoreBadge: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 10,
  },
  altScoreText: {
    fontSize: 13,
    fontWeight: '700',
  },
  // Bottom bar
  bottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: 20,
    paddingBottom: 40,
    paddingTop: 14,
    borderTopWidth: 1,
  },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    borderRadius: 16,
    shadowColor: TIFFANY,
    shadowOpacity: 0.35,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 4,
  },
  addBtnText: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
});
