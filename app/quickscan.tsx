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
import { ScanResultCard } from '@/components/ScanResultCard';
import { MultiItemOverlay } from '@/components/MultiItemOverlay';
import { ComparisonCard } from '@/components/ComparisonCard';
import { classifyOnDevice, buildCategoryDistribution } from '@/lib/edgeClassifier';
import type { EdgeClassification } from '@/lib/edgeClassifier';
import { multiDetect, collectorsApi } from '@/api/collectorsApi';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import type { QuickScanResult, CatalogAlternative, DetectedMultiItem } from '@/data/types';
import logger from '@/utils/logger';
import { track } from '@/analytics/track';

import {
  AnalyzingScreen,
  BatchSummaryScreen,
  CameraViewfinder,
  PermissionScreen,
} from '@/components/quickscan';
import type { BatchScannedItem } from '@/components/quickscan';

const TIFFANY = '#81D8D0';

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

  // Edge classification / viewfinder hint state
  const [edgeHint, setEdgeHint] = useState<EdgeClassification | null>(null);
  const [userCategoryDist, setUserCategoryDist] = useState<Record<string, number> | null>(null);

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
        prev < 2 ? prev + 1 : prev,
      );
    }, 1500);
    return () => clearInterval(interval);
  }, [phase]);

  // Track when camera permission is first granted
  useEffect(() => {
    if (permission?.granted) {
      track({ name: 'quickscan_started' });
    }
  }, [permission?.granted]);

  // Load user's category distribution once for edge classification
  useEffect(() => {
    if (!featureFlags.FEATURE_EDGE_CLASSIFICATION) return;
    dataProvider.listItems({ limit: 500, offset: 0 })
      .then((items) => {
        if (items?.length) {
          setUserCategoryDist(buildCategoryDistribution(items));
        }
      })
      .catch(() => {/* best-effort */});
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
          if (hint.confidence >= 0.15) {
            setEdgeHint(hint);
          }
        }
      } catch {
        // Silent — frame capture may fail during transitions
      }
    }, 2500);

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
        quality: 0.8,
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
        setScanResult(response as any);
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
        quality: 0.8,
      });

      if (!photo?.uri) {
        showToast({ message: 'Failed to capture image.', type: 'error' });
        return;
      }

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
          const result = await multiDetect(photo.uri);
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
        const sr = await dataProvider.quickscanSingle(photo.uri);
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
      const sr = await dataProvider.quickscanSingle(photo.uri);

      // Fire haptic based on confidence (always fire success on scan result)
      const intent = confidenceToIntent(sr.prediction.confidence);
      fireHaptic(intent, { enabled: settings.hapticsEnabled });

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
    track({
      name: 'quickscan_result_accepted',
      properties: {
        category: scanResult?.attributes?.category,
        confidence: scanResult?.prediction?.confidence
          ? Math.round(scanResult.prediction.confidence * 100)
          : undefined,
      },
    });
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
        <ActivityIndicator size="large" color={TIFFANY} />
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
        onProcessSelected={() => {/* TODO: process single item */}}
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
        <AnimatedPressable
          style={[styles.galleryBtn, { backgroundColor: 'rgba(0,0,0,0.6)' }]}
          onPress={handleScreenshotScan}
          accessibilityRole="button"
          accessibilityLabel="Scan from gallery or screenshot"
        >
          <Ionicons name="image-outline" size={22} color="#FFFFFF" />
        </AnimatedPressable>
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
    bottom: 120,
    left: 24,
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
  },
});
