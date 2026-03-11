/**
 * Branded analysis screen shown while AI processes the captured image.
 * Displays captured photo with animated scan line + step progress indicators.
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Image,
  Animated,
  ActivityIndicator,
  StatusBar,
  Dimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { featureFlags } from '@/config/featureFlags';
import type { EdgeClassification } from '@/lib/edgeClassifier';
import { BRAND_COLORS } from '@/constants/colors';

const TIFFANY = BRAND_COLORS.tiffany;
const { width: SCREEN_WIDTH } = Dimensions.get('window');

type AnalysisStep = {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
};

const ANALYSIS_STEPS: AnalysisStep[] = [
  { icon: 'sparkles', label: 'Identifying your item...' },
  { icon: 'trending-up', label: 'Checking marketplace prices...' },
  { icon: 'calculator', label: 'Calculating valuation...' },
];

interface AnalyzingScreenProps {
  capturedUri: string;
  analysisStepIndex: number;
  scanLineAnim: Animated.Value;
  edgeHint: EdgeClassification | null;
  colors: {
    background: string;
    text: string;
    muted: string;
  };
}

function AnalyzingScreenInner({
  capturedUri,
  analysisStepIndex,
  scanLineAnim,
  edgeHint,
  colors,
}: AnalyzingScreenProps) {
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

      {/* F3: Edge classification category pill */}
      {featureFlags.FEATURE_EDGE_CLASSIFICATION && edgeHint && edgeHint.confidence >= 0.15 && (
        <View style={styles.edgeHintPill}>
          <Ionicons name="sparkles" size={14} color={TIFFANY} />
          <Text style={[styles.edgeHintText, { color: colors.text }]}>
            Looks like: {edgeHint.category.replace(/_/g, ' ')}
          </Text>
        </View>
      )}

      {/* Bottom hint */}
      <View style={styles.analysisBottomHint}>
        <Text style={[styles.analysisHintText, { color: colors.muted }]}>
          Hold tight -- this usually takes a few seconds
        </Text>
      </View>
    </View>
  );
}

export const AnalyzingScreen = React.memo(AnalyzingScreenInner);

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
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
  edgeHintPill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'center',
    gap: 6,
    marginTop: 16,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: 'rgba(129,216,208,0.12)',
  },
  edgeHintText: {
    fontSize: 13,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
});
