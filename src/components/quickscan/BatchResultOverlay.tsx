/**
 * Slide-up overlay card showing batch scan result with Save/Discard actions.
 * Appears at the bottom of the camera viewfinder after scanning in batch mode.
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Image,
  Animated,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';
import type { CurrencyCode } from '@/data/types';
import type { BatchScannedItem } from './BatchSummaryScreen';
import { BRAND_COLORS } from '@/constants/colors';

const TIFFANY = BRAND_COLORS.tiffany;
const TIFFANY_DARK = BRAND_COLORS.tiffanyDark;

interface BatchResultOverlayProps {
  currentBatchResult: BatchScannedItem;
  batchOverlayAnim: Animated.Value;
  savingBatchItem: boolean;
  currency: CurrencyCode;
  onDiscard: () => void;
  onSave: () => void;
  colors: {
    card: string;
    text: string;
    muted: string;
    border: string;
  };
}

function BatchResultOverlayInner({
  currentBatchResult,
  batchOverlayAnim,
  savingBatchItem,
  currency,
  onDiscard,
  onSave,
  colors,
}: BatchResultOverlayProps) {
  return (
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
            style={[styles.batchOverlayImage, { backgroundColor: colors.border }]}
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
              {formatPrice(currentBatchResult.estimatedMid, currency)}
            </Text>
          </View>
        </View>

        <View style={styles.batchOverlayButtons}>
          <AnimatedPressable
            onPress={onDiscard}
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
            onPress={onSave}
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
  );
}

export const BatchResultOverlay = React.memo(BatchResultOverlayInner);

const styles = StyleSheet.create({
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
});
