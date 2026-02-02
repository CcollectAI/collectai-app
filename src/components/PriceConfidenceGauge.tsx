/**
 * PriceConfidenceGauge - Visual gauge showing price prediction confidence.
 * Shows a horizontal bar with color gradient from red (low) to green (high).
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface Props {
  confidence: number; // 0-100 or 0-1
  showLabel?: boolean;
  size?: 'small' | 'medium' | 'large';
  colors?: {
    text?: string;
    muted?: string;
    background?: string;
  };
}

export function PriceConfidenceGauge({
  confidence,
  showLabel = true,
  size = 'medium',
  colors = {},
}: Props) {
  // Normalize to 0-100
  const normalizedConfidence = confidence > 1 ? confidence : confidence * 100;
  const clampedConfidence = Math.max(0, Math.min(100, normalizedConfidence));

  // Determine color based on confidence level
  const getConfidenceColor = (value: number) => {
    if (value >= 80) return '#22c55e'; // Green - High confidence
    if (value >= 60) return '#84cc16'; // Lime - Good confidence
    if (value >= 40) return '#eab308'; // Yellow - Medium confidence
    if (value >= 20) return '#f97316'; // Orange - Low confidence
    return '#ef4444'; // Red - Very low confidence
  };

  const getConfidenceLabel = (value: number) => {
    if (value >= 80) return 'High';
    if (value >= 60) return 'Good';
    if (value >= 40) return 'Medium';
    if (value >= 20) return 'Low';
    return 'Very Low';
  };

  const barHeight = size === 'small' ? 6 : size === 'large' ? 12 : 8;
  const fontSize = size === 'small' ? 11 : size === 'large' ? 14 : 12;
  const confidenceColor = getConfidenceColor(clampedConfidence);

  return (
    <View style={styles.container}>
      {showLabel && (
        <View style={styles.labelRow}>
          <Text style={[styles.label, { color: colors.muted || '#64748b', fontSize }]}>
            Confidence
          </Text>
          <Text style={[styles.value, { color: confidenceColor, fontSize }]}>
            {Math.round(clampedConfidence)}% ({getConfidenceLabel(clampedConfidence)})
          </Text>
        </View>
      )}

      <View style={[styles.barContainer, { height: barHeight, backgroundColor: colors.background || '#e2e8f0' }]}>
        <View
          style={[
            styles.barFill,
            {
              width: `${clampedConfidence}%`,
              backgroundColor: confidenceColor,
              height: barHeight,
            },
          ]}
        />
        {/* Tick marks */}
        <View style={[styles.tick, { left: '25%' }]} />
        <View style={[styles.tick, { left: '50%' }]} />
        <View style={[styles.tick, { left: '75%' }]} />
      </View>

      {!showLabel && (
        <Text style={[styles.inlineValue, { color: colors.text || '#0f172a', fontSize: fontSize - 1 }]}>
          {Math.round(clampedConfidence)}%
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
  labelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  label: {
    fontWeight: '500',
  },
  value: {
    fontWeight: '600',
  },
  barContainer: {
    width: '100%',
    borderRadius: 999,
    overflow: 'hidden',
    position: 'relative',
  },
  barFill: {
    borderRadius: 999,
  },
  tick: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 1,
    backgroundColor: 'rgba(255,255,255,0.4)',
  },
  inlineValue: {
    marginTop: 4,
    textAlign: 'center',
    fontWeight: '500',
  },
});

export default PriceConfidenceGauge;
