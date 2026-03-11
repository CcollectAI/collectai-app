/**
 * Camera viewfinder overlay with mode toggles, frame corners, hint text,
 * capture button, and batch counter/done controls.
 * Also renders the BatchResultOverlay when in batch_result phase.
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CameraView } from 'expo-camera';
import { Ionicons } from '@expo/vector-icons';
import { featureFlags } from '@/config/featureFlags';
import { AnimatedPressable } from '@/motion';
import type { EdgeClassification } from '@/lib/edgeClassifier';
import type { CurrencyCode } from '@/data/types';
import { BatchResultOverlay } from './BatchResultOverlay';
import type { BatchScannedItem } from './BatchSummaryScreen';

const TIFFANY = '#81D8D0';
const FRAME_SIZE = 260;
const CORNER_LENGTH = 36;
const CORNER_THICKNESS = 4;
const CORNER_RADIUS = 16;

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

interface CameraViewfinderProps {
  cameraRef: React.RefObject<CameraView | null>;
  phase: ScanPhase;
  batchMode: boolean;
  multiMode: boolean;
  compareMode: boolean;
  savedBatchCount: number;
  edgeHint: EdgeClassification | null;
  comparisonA: unknown | null;
  currentBatchResult: BatchScannedItem | null;
  batchOverlayAnim: Animated.Value;
  savingBatchItem: boolean;
  currency: CurrencyCode;
  onCancel: () => void;
  onCapture: () => void;
  onBatchDone: () => void;
  onToggleBatch: () => void;
  onToggleMulti: () => void;
  onToggleCompare: () => void;
  onDiscardBatchItem: () => void;
  onSaveBatchItem: () => void;
  colors: {
    card: string;
    text: string;
    muted: string;
    border: string;
  };
}

function CameraViewfinderInner({
  cameraRef,
  phase,
  batchMode,
  multiMode,
  compareMode,
  savedBatchCount,
  edgeHint,
  comparisonA,
  currentBatchResult,
  batchOverlayAnim,
  savingBatchItem,
  currency,
  onCancel,
  onCapture,
  onBatchDone,
  onToggleBatch,
  onToggleMulti,
  onToggleCompare,
  onDiscardBatchItem,
  onSaveBatchItem,
  colors,
}: CameraViewfinderProps) {
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
              onPress={onCancel}
              style={styles.cancelBtn}
              accessibilityRole="button"
              accessibilityLabel="Cancel and go back"
            >
              <Ionicons name="close" size={28} color="#FFFFFF" />
            </AnimatedPressable>
            <Text style={styles.topBarTitle}>QuickScan</Text>

            {/* Mode toggle pills */}
            <View style={styles.modePills}>
              <AnimatedPressable
                onPress={onToggleBatch}
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

              {featureFlags.FEATURE_MULTI_ITEM_SCAN && (
                <AnimatedPressable
                  onPress={onToggleMulti}
                  style={[
                    styles.batchPill,
                    multiMode
                      ? { backgroundColor: TIFFANY }
                      : { backgroundColor: 'rgba(255,255,255,0.2)' },
                  ]}
                  accessibilityRole="switch"
                  accessibilityLabel={`Multi mode ${multiMode ? 'on' : 'off'}`}
                  accessibilityState={{ checked: multiMode }}
                >
                  <Ionicons
                    name="grid-outline"
                    size={16}
                    color={multiMode ? '#FFFFFF' : 'rgba(255,255,255,0.8)'}
                  />
                  <Text
                    style={[
                      styles.batchPillText,
                      { color: multiMode ? '#FFFFFF' : 'rgba(255,255,255,0.8)' },
                    ]}
                  >
                    Multi
                  </Text>
                </AnimatedPressable>
              )}

              {featureFlags.FEATURE_COMPARISON_SCAN && (
                <AnimatedPressable
                  onPress={onToggleCompare}
                  style={[
                    styles.batchPill,
                    compareMode
                      ? { backgroundColor: '#8B5CF6' }
                      : { backgroundColor: 'rgba(255,255,255,0.2)' },
                  ]}
                  accessibilityRole="switch"
                  accessibilityLabel={`Compare mode ${compareMode ? 'on' : 'off'}`}
                  accessibilityState={{ checked: compareMode }}
                >
                  <Ionicons
                    name="git-compare-outline"
                    size={16}
                    color={compareMode ? '#FFFFFF' : 'rgba(255,255,255,0.8)'}
                  />
                  <Text
                    style={[
                      styles.batchPillText,
                      { color: compareMode ? '#FFFFFF' : 'rgba(255,255,255,0.8)' },
                    ]}
                  >
                    Compare
                  </Text>
                </AnimatedPressable>
              )}
            </View>
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

          {/* F5: Viewfinder hint floating pill */}
          {featureFlags.FEATURE_VIEWFINDER_HINTS && edgeHint && edgeHint.confidence >= 0.15 && phase === 'camera' && (
            <View style={styles.viewfinderHintRow}>
              <View style={styles.viewfinderHintPill}>
                <Ionicons name="sparkles" size={13} color={TIFFANY} />
                <Text style={styles.viewfinderHintText}>
                  Looks like: {edgeHint.category.replace(/_/g, ' ')}
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
              {batchMode
                ? 'Batch mode -- scan multiple items'
                : multiMode
                  ? 'Multi mode -- point at a shelf or group'
                  : compareMode
                    ? comparisonA
                      ? 'Now scan item B for comparison'
                      : 'Compare mode -- scan item A first'
                    : 'Point at your collectible'}
            </Text>
          </View>

          {/* Bottom: capture button + batch done */}
          <View style={styles.bottomBar}>
            {batchMode && savedBatchCount > 0 && phase === 'camera' && (
              <AnimatedPressable
                onPress={onBatchDone}
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
              onPress={phase === 'camera' || phase === 'comparison_second' ? onCapture : undefined}
              style={[
                styles.captureBtn,
                phase !== 'camera' && phase !== 'comparison_second' && { opacity: 0.5 },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Take photo"
              disabled={phase !== 'camera' && phase !== 'comparison_second'}
              testID="capture-button"
            >
              <View style={styles.captureBtnInner}>
                <Ionicons name="camera" size={32} color="#FFFFFF" />
              </View>
            </AnimatedPressable>
          </View>

          {/* Batch result overlay card -- slides up from bottom */}
          {phase === 'batch_result' && currentBatchResult && (
            <BatchResultOverlay
              currentBatchResult={currentBatchResult}
              batchOverlayAnim={batchOverlayAnim}
              savingBatchItem={savingBatchItem}
              currency={currency}
              onDiscard={onDiscardBatchItem}
              onSave={onSaveBatchItem}
              colors={colors}
            />
          )}
        </View>
      </CameraView>
    </View>
  );
}

export const CameraViewfinder = React.memo(CameraViewfinderInner);

const styles = StyleSheet.create({
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
  modePills: {
    flexDirection: 'row',
    gap: 6,
  },
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
  viewfinderHintRow: {
    alignItems: 'center',
    paddingVertical: 6,
    backgroundColor: 'rgba(0,0,0,0.45)',
  },
  viewfinderHintPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 14,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  viewfinderHintText: {
    color: 'rgba(255,255,255,0.9)',
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
});
