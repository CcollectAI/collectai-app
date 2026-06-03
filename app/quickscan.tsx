/**
 * QuickScan capture screen.
 * Custom branded camera viewfinder -> branded AI analysis screen -> navigates to item card in draft mode.
 * Supports batch mode for scanning multiple items in sequence.
 */
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import React, { useCallback, useState, useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  ActivityIndicator,
  Animated,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { router } from 'expo-router';
import { dataProvider } from '@/data';
import { featureFlags } from '@/config/featureFlags';
import { fireHaptic, HapticIntent, confidenceToIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { isDeviceOnline } from '@/hooks/useNetworkStatus';
import { useToast } from '@/components/Toast';
import { useSettings } from '@/lib/settings';
import { useTranslation } from 'react-i18next';
import { ScanResultCard } from '@/components/ScanResultCard';
import { MultiItemOverlay } from '@/components/MultiItemOverlay';
import { ComparisonCard } from '@/components/ComparisonCard';
import { classifyOnDevice, buildCategoryDistribution } from '@/lib/edgeClassifier';
import type { EdgeClassification } from '@/lib/edgeClassifier';
import { multiDetect, collectorsApi } from '@/api/collectorsApi';
import * as ImagePicker from 'expo-image-picker';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as FileSystem from 'expo-file-system';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import type { QuickScanResult, CatalogAlternative, DetectedMultiItem } from '@/data/types';
import logger from '@/utils/logger';
import { prepareImageForUpload } from '@/lib/prepareImageForUpload';
import { track } from '@/analytics/track';
import { useInterstitial } from '@/ads';
import { radius } from '@/theme/tokens';

import {
  AnalyzingScreen,
  BatchSummaryScreen,
  CameraViewfinder,
  PermissionScreen,
} from '@/components/quickscan';
import type { BatchScannedItem } from '@/components/quickscan';

// TIFFANY removed — use colors.accent from theme instead

const SCAN_LINE_DURATION = 1800;
const ANALYSIS_STEP_INTERVAL = 1500;
const EDGE_HINT_THRESHOLD = 0.15;
const VIEWFINDER_HINT_INTERVAL = 2500;
const PHOTO_QUALITY = 0.8;

type ScanPhase =
  | 'camera'
  | 'analyzing'
  | 'result'
  | 'done'
  | 'batch_result'
  | 'batch_summary'
  | 'multi_detect'
  | 'multi_result'
  | 'comparison_first'
  | 'comparison_second'
  | 'comparison_result';

function QuickScanScreen() {
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const { settings } = useSettings();
  const { t } = useTranslation();
  const { recordAction: recordAdAction, tryShow: tryShowAd } = useInterstitial('scan_interstitial');
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

  // Multi-detect state
  const [multiMode, setMultiMode] = useState(false);
  const [detectedMultiItems, setDetectedMultiItems] = useState<DetectedMultiItem[]>([]);
  const [multiSelectedIndex, setMultiSelectedIndex] = useState<number | null>(null);

  // Comparison mode state
  const [compareMode, setCompareMode] = useState(false);
  const [comparisonA, setComparisonA] = useState<{ result: QuickScanResult; uri: string } | null>(null);
  const [comparisonB, setComparisonB] = useState<{ result: QuickScanResult; uri: string } | null>(null);

  // Flash/torch toggle
  const [torchEnabled, setTorchEnabled] = useState(false);

  // Edge classification / viewfinder hint state
  const [edgeHint, setEdgeHint] = useState<EdgeClassification | null>(null);
  const [userCategoryDist, setUserCategoryDist] = useState<Record<string, number> | null>(null);

  // Result screen state (intermediate screen with alternatives)
  const [scanResult, setScanResult] = useState<QuickScanResult | null>(null);

  // Session scan counter for savings toast
  const sessionScanCount = useRef(0);

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
          duration: SCAN_LINE_DURATION,
          useNativeDriver: true,
        }),
        Animated.timing(scanLineAnim, {
          toValue: 0,
          duration: SCAN_LINE_DURATION,
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
        prev < 2 ? prev + 1 : prev,
      );
    }, ANALYSIS_STEP_INTERVAL);
    return () => clearInterval(interval);
  }, [phase]);

  // Track when camera permission is first granted (fires once when granted becomes true)
  const permissionTrackedRef = useRef(false);
  useEffect(() => {
    if (permission?.granted && !permissionTrackedRef.current) {
      permissionTrackedRef.current = true;
      track({ name: 'quickscan_started' });
    }
  }, [permission?.granted]);

  // M9: Load user's category distribution once for edge classification (with cancellation).
  // Includes the followed-category onboarding picks as a synthetic prior so
  // brand-new users (empty collection) still get a useful classifier hint.
  useEffect(() => {
    if (!featureFlags.FEATURE_EDGE_CLASSIFICATION) return;
    let cancelled = false;
    Promise.all([
      dataProvider.listItems({ limit: 500, offset: 0 }).catch(() => []),
      AsyncStorage.getItem('@sparrowcollect/followed_categories').catch(() => null),
    ])
      .then(([items, followedRaw]) => {
        if (cancelled) return;
        let followed: string[] | undefined;
        if (typeof followedRaw === 'string') {
          try {
            const parsed = JSON.parse(followedRaw);
            if (Array.isArray(parsed)) followed = parsed;
          } catch {/* ignore */}
        }
        const list = items ?? [];
        if (list.length === 0 && !followed?.length) return;
        setUserCategoryDist(buildCategoryDistribution(list, followed));
      });
    return () => { cancelled = true; };
  }, []);

  // F5: Live viewfinder hints — periodic frame capture in camera phase
  useEffect(() => {
    if (!featureFlags.FEATURE_VIEWFINDER_HINTS || phase !== 'camera' || !cameraRef.current) return;

    const interval = setInterval(async () => {
      if (!cameraRef.current || phase !== 'camera') return;
      try {
        const frame = await cameraRef.current.takePictureAsync({ quality: 0.1 });
        if (frame?.width && frame?.height) {
          const hint = classifyOnDevice(
            { width: frame.width, height: frame.height },
            userCategoryDist,
          );
          if (hint.confidence >= EDGE_HINT_THRESHOLD) {
            setEdgeHint(hint);
          }
        }
      } catch {
        // Silent — frame capture may fail during transitions
      }
    }, VIEWFINDER_HINT_INTERVAL);

    return () => clearInterval(interval);
  }, [phase, userCategoryDist]);

  const resetCamera = useCallback(() => {
    setPhase('camera');
    setCapturedUri(null);
    setCurrentBatchResult(null);
    setScanResult(null);
    setEdgeHint(null);
    setAnalysisStepIndex(0);
  }, []);

  const handleScreenshotScan = useCallback(async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: PHOTO_QUALITY,
        base64: true,
      });

      if (result.canceled || !result.assets?.[0]) return;

      const asset = result.assets[0];
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });

      // If base64 not available, read from URI
      let base64 = asset.base64;
      if (!base64 && asset.uri) {
        base64 = await FileSystem.readAsStringAsync(asset.uri, { encoding: 'base64' });
      }

      if (!base64) {
        showToast({ message: 'Could not read image', type: 'error' });
        return;
      }

      setPhase('analyzing');
      setCapturedUri(asset.uri);
      setAnalysisStepIndex(0);

      const response = await collectorsApi.analyzeScreenshot({ image_base64: base64, source: 'gallery' });

      // The response should be similar to intake result — set it as scan result
      if (response) {
        setScanResult(response as QuickScanResult);
        setPhase('result');
      } else {
        showToast({ message: 'Could not identify items in screenshot', type: 'info' });
        setPhase('camera');
      }
    } catch (err) {
      logger.warn('[QuickScan] Screenshot analysis failed:', err);
      showToast({ message: 'Screenshot analysis failed', type: 'error' });
      setPhase('camera');
    }
  }, [showToast, settings.hapticsEnabled]);

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
        quality: PHOTO_QUALITY,
      });

      if (!photo?.uri) {
        showToast({ message: 'Failed to capture image.', type: 'error' });
        return;
      }

      // S2: downscale to ~1568px before any upload — cuts payload ~5–10x,
      // reducing latency, mobile upload failures, and OpenAI token cost.
      // Falls back to the original URI on any failure. Display keeps the
      // original photo for a crisp preview.
      const uploadUri = await prepareImageForUpload(photo.uri);

      setCapturedUri(photo.uri);
      setAnalysisStepIndex(0);
      track({ name: 'quickscan_photo_taken' });

      // F3: On-device edge classification — show instant hint during analyzing
      if (featureFlags.FEATURE_EDGE_CLASSIFICATION && photo.width && photo.height) {
        const hint = classifyOnDevice(
          { width: photo.width, height: photo.height },
          userCategoryDist,
        );
        setEdgeHint(hint);
        track({ name: 'edge_classification_used', properties: { category: hint.category, method: hint.method } });
      }

      // F1: Multi-item detection mode
      if (multiMode && featureFlags.FEATURE_MULTI_ITEM_SCAN) {
        setPhase('multi_detect');
        try {
          const result = await multiDetect(uploadUri);
          if (result.items.length > 0) {
            setDetectedMultiItems(result.items.map((it) => ({
              itemIndex: it.itemIndex,
              boundingBox: it.boundingBox,
              categoryHint: it.categoryHint ?? null,
              suggestedName: it.suggestedName ?? null,
              confidence: it.confidence,
            })));
            track({ name: 'multi_item_detected', properties: { item_count: result.items.length } });
            setPhase('multi_result');
          } else {
            showToast({ message: 'No items detected. Try again.', type: 'info' });
            setPhase('camera');
            setCapturedUri(null);
          }
        } catch (err: unknown) {
          logger.warn('[QuickScan] multi-detect error:', err);
          showToast({ message: 'Multi-detect failed. Try standard mode.', type: 'error' });
          setPhase('camera');
          setCapturedUri(null);
        }
        return;
      }

      // F8: Comparison mode — first or second capture
      if (compareMode && featureFlags.FEATURE_COMPARISON_SCAN) {
        setPhase('analyzing');
        const sr = await dataProvider.quickscanSingle(uploadUri);
        if (!comparisonA) {
          setComparisonA({ result: sr, uri: photo.uri });
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          showToast({ message: 'Item A captured! Now scan item B.', type: 'success' });
          setPhase('comparison_second');
          setCapturedUri(null);
        } else {
          setComparisonB({ result: sr, uri: photo.uri });
          track({ name: 'comparison_scan_completed', properties: {} });
          setPhase('comparison_result');
        }
        return;
      }

      setPhase('analyzing');

      // Run AI analysis
      const sr = await dataProvider.quickscanSingle(uploadUri);

      // R48.4 — Low-confidence fallback: if the AI can't identify the item,
      // offer "Add Manually" instead of showing a garbage guess.
      const LOW_CONFIDENCE_THRESHOLD = 0.3;
      if (sr.prediction.confidence < LOW_CONFIDENCE_THRESHOLD) {
        fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
        showToast({
          message: "Couldn't identify this item",
          type: 'info',
          duration: 4000,
        });
        // Navigate to manual-add with the captured photo pre-attached
        router.push({
          pathname: '/add-manual',
          params: { imageUri: photo.uri },
        });
        setPhase('camera');
        setCapturedUri(null);
        return;
      }

      // Fire haptic based on confidence (always fire success on scan result)
      const intent = confidenceToIntent(sr.prediction.confidence);
      fireHaptic(intent, { enabled: settings.hapticsEnabled });

      // Track scan count and show savings toast on milestones
      sessionScanCount.current += 1;
      const count = sessionScanCount.current;
      if (count === 1) {
        showToast({ message: 'Saved ~15 min of manual research', type: 'success', duration: 3000 });
      } else if (count % 5 === 0) {
        const minsSaved = count * 15;
        showToast({ message: `${count} scans — ~${minsSaved} min saved so far`, type: 'success', duration: 3000 });
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
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
      showToast({
        message: (err as Error)?.message ?? 'Unable to analyze image. Please try again.',
        type: 'error',
      });
      // Go back to camera on error
      setPhase('camera');
      setCapturedUri(null);
    }
  }, [settings.hapticsEnabled, showToast, batchMode, multiMode, compareMode, comparisonA, userCategoryDist, edgeHint]);

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
    track({
      name: 'quickscan_result_accepted',
      properties: {
        category: scanResult?.attributes?.category,
        confidence: scanResult?.prediction?.confidence
          ? Math.round(scanResult.prediction.confidence * 100)
          : undefined,
      },
    });
    // Record action toward interstitial throttle (no-op when ads disabled)
    recordAdAction();
    // Fire-and-forget interstitial attempt (throttled, no-op when ads disabled)
    void tryShowAd();
    setPhase('done');

    // Pass extracted details as structured JSON so they can be persisted
    // to items.attributes_json (not flattened into free-text notes).
    const details = scanResult.attributes.extractedDetails;
    const attributesJson = details ? JSON.stringify(details) : '';

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
        attributesJson,
        ...(scanResult.catalogMatchKey ? { catalogKey: scanResult.catalogMatchKey } : {}),
      },
    });
  }, [scanResult, capturedUri, settings.hapticsEnabled, recordAdAction, tryShowAd]);

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
    setMultiMode(false);
    setCompareMode(false);
    if (batchMode) {
      // Turning off batch mode -- if items were scanned, show summary
      if (batchItems.length > 0) {
        setPhase('batch_summary');
      }
    }
  }, [settings.hapticsEnabled, batchMode, batchItems.length]);

  const toggleMultiMode = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setMultiMode((prev) => !prev);
    setBatchMode(false);
    setCompareMode(false);
  }, [settings.hapticsEnabled]);

  const toggleCompareMode = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setCompareMode((prev) => !prev);
    setBatchMode(false);
    setMultiMode(false);
    setComparisonA(null);
    setComparisonB(null);
  }, [settings.hapticsEnabled]);

  // Multi-detect: process all items sequentially
  const handleProcessAllMulti = useCallback(async () => {
    if (!capturedUri || detectedMultiItems.length === 0) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // Navigate to batch summary with detected items as a starting point
    showToast({ message: `Processing ${detectedMultiItems.length} items...`, type: 'info' });
    // For now, save the first item and reset
    resetCamera();
  }, [capturedUri, detectedMultiItems, settings.hapticsEnabled, showToast, resetCamera]);

  // Comparison: keep item A, B, or both
  const handleKeepCompA = useCallback(() => {
    if (!comparisonA) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setScanResult(comparisonA.result);
    setCapturedUri(comparisonA.uri);
    setPhase('result');
    setComparisonA(null);
    setComparisonB(null);
  }, [comparisonA, settings.hapticsEnabled]);

  const handleKeepCompB = useCallback(() => {
    if (!comparisonB) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setScanResult(comparisonB.result);
    setCapturedUri(comparisonB.uri);
    setPhase('result');
    setComparisonA(null);
    setComparisonB(null);
  }, [comparisonB, settings.hapticsEnabled]);

  const handleKeepBoth = useCallback(() => {
    if (!comparisonA) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    // Show item A first, user can go back for B
    setScanResult(comparisonA.result);
    setCapturedUri(comparisonA.uri);
    setPhase('result');
    setComparisonA(null);
    setComparisonB(null);
  }, [comparisonA, settings.hapticsEnabled]);

  const handleCompRetake = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setComparisonA(null);
    setComparisonB(null);
    resetCamera();
  }, [settings.hapticsEnabled, resetCamera]);

  const savedBatchCount = batchItems.filter((i) => i.saved).length;
  const totalBatchValue = batchItems
    .filter((i) => i.saved)
    .reduce((sum, i) => sum + i.estimatedMid, 0);

  // Permission loading
  if (!permission) {
    return (
      <View style={[styles.container, { backgroundColor: '#000' }]}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  // Permission denied
  if (!permission.granted) {
    return (
      <PermissionScreen
        onGrant={requestPermission}
        onCancel={handleCancel}
        hapticsEnabled={settings.hapticsEnabled}
        colors={colors}
      />
    );
  }

  // ---- Multi-detect Result Screen ----
  if (phase === 'multi_result' && capturedUri && detectedMultiItems.length > 0) {
    return (
      <MultiItemOverlay
        imageUri={capturedUri}
        detectedItems={detectedMultiItems}
        selectedIndex={multiSelectedIndex}
        onSelectItem={setMultiSelectedIndex}
        onProcessAll={handleProcessAllMulti}
        onProcessSelected={() => {
          if (multiSelectedIndex == null || !detectedMultiItems[multiSelectedIndex]) return;
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          const item = detectedMultiItems[multiSelectedIndex];
          showToast({ message: `Processing "${item.suggestedName || 'item'}"...`, type: 'info' });
          resetCamera();
        }}
      />
    );
  }

  // ---- Comparison Result Screen ----
  if (phase === 'comparison_result' && comparisonA && comparisonB) {
    return (
      <ComparisonCard
        itemA={comparisonA.result}
        itemB={comparisonB.result}
        imageUriA={comparisonA.uri}
        imageUriB={comparisonB.uri}
        currency={settings.currency}
        onKeepA={handleKeepCompA}
        onKeepB={handleKeepCompB}
        onKeepBoth={handleKeepBoth}
        onRetake={handleCompRetake}
      />
    );
  }

  // ---- Result Screen (intermediate screen with alternatives) ----
  if (phase === 'result' && scanResult && capturedUri) {
    return (
      <ScanResultCard
        scanResult={scanResult}
        capturedUri={capturedUri}
        currency={settings.currency}
        onRetake={resetCamera}
        onSelectAlternative={handleSelectAlternative}
        onConfirm={handleConfirmResult}
      />
    );
  }

  // ---- Batch Summary Screen ----
  if (phase === 'batch_summary') {
    return (
      <BatchSummaryScreen
        batchItems={batchItems}
        savedBatchCount={savedBatchCount}
        totalBatchValue={totalBatchValue}
        currency={settings.currency}
        onFinish={handleFinishBatch}
        colors={colors}
      />
    );
  }

  // ---- Branded Analysis Screen ----
  if ((phase === 'analyzing' || phase === 'multi_detect') && capturedUri) {
    return (
      <AnalyzingScreen
        capturedUri={capturedUri}
        analysisStepIndex={analysisStepIndex}
        scanLineAnim={scanLineAnim}
        edgeHint={edgeHint}
        colors={colors}
      />
    );
  }

  // ---- Camera Viewfinder (also serves as background for batch_result overlay) ----
  return (
    <View style={styles.container}>
      <CameraViewfinder
        cameraRef={cameraRef}
        phase={phase}
        batchMode={batchMode}
        multiMode={multiMode}
        compareMode={compareMode}
        savedBatchCount={savedBatchCount}
        edgeHint={edgeHint}
        comparisonA={comparisonA}
        currentBatchResult={currentBatchResult}
        batchOverlayAnim={batchOverlayAnim}
        savingBatchItem={savingBatchItem}
        currency={settings.currency}
        enableTorch={torchEnabled}
        onCancel={handleCancel}
        onCapture={handleCapture}
        onBatchDone={handleBatchDone}
        onToggleBatch={toggleBatchMode}
        onToggleMulti={toggleMultiMode}
        onToggleCompare={toggleCompareMode}
        onDiscardBatchItem={handleDiscardBatchItem}
        onSaveBatchItem={handleSaveBatchItem}
        colors={colors}
      />
      {phase === 'camera' && (
        <>
          <AnimatedPressable
            testID="gallery-scan-btn"
            style={[styles.galleryBtn, { backgroundColor: 'rgba(0,0,0,0.6)' }]}
            onPress={handleScreenshotScan}
            accessibilityRole="button"
            accessibilityLabel={t('quickscan_screen.gallery_a11y')}
          >
            <Ionicons name="image-outline" size={22} color={colors.accentText} />
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.flashBtn, { backgroundColor: torchEnabled ? colors.accent : 'rgba(0,0,0,0.6)' }]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              setTorchEnabled((prev) => !prev);
            }}
            accessibilityRole="switch"
            accessibilityLabel={`Flash ${torchEnabled ? 'on' : 'off'}`}
            accessibilityState={{ checked: torchEnabled }}
          >
            <Ionicons name={torchEnabled ? 'flash' : 'flash-outline'} size={22} color="#FFFFFF" />
          </AnimatedPressable>
        </>
      )}
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
  galleryBtn: {
    position: 'absolute',
    bottom: 56,
    left: 32,
    width: 48,
    height: 48,
    borderRadius: radius.xl,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.25)',
  },
  flashBtn: {
    position: 'absolute',
    bottom: 56,
    right: 32,
    width: 48,
    height: 48,
    borderRadius: radius.xl,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.25)',
  },
});
