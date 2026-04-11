/**
 * ScanResultCard Component
 * Displays the QuickScan result screen: hero image, item identification card,
 * estimated value, AI confidence rings, extracted details, "Did you mean?"
 * catalog alternatives, and action buttons (retake / add to collection).
 */

import React, { useRef, useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Image,
  ScrollView,
  StatusBar,
  Dimensions,
  Share,
  Alert,
  Platform,
} from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import ViewShot from 'react-native-view-shot';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';
import { featureFlags } from '@/config/featureFlags';
import { fireHaptic, HapticIntent } from '@/haptics';
import { track } from '@/analytics/track';
import { CatalogImage } from '@/components/CatalogImage';
import { ScanFeedbackPanel } from '@/components/quickscan/ScanFeedbackPanel';
import { ScanSocialProof } from '@/components/quickscan/ScanSocialProof';
import { ConditionGradeSelector } from '@/components/quickscan/ConditionGradeSelector';
import { ShareCard } from '@/components/quickscan/ShareCard';
import type { QuickScanResult, CatalogAlternative, CurrencyCode } from '@/data/types';
import logger from '@/utils/logger';

import { BRAND_COLORS } from '@/constants/colors';
const TIFFANY = BRAND_COLORS.tiffany; // StyleSheet can't use hooks
const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Confidence ring SVG constants
const RING_SIZE = 56;
const RING_STROKE = 4;
const RING_RADIUS = (RING_SIZE - RING_STROKE) / 2;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type ScanResultCardProps = {
  /** The full scan result from the AI pipeline */
  scanResult: QuickScanResult;
  /** URI of the captured photo */
  capturedUri: string;
  /** User's preferred currency for price display */
  currency: CurrencyCode;
  /** Called when the user taps "Retake" */
  onRetake: () => void;
  /** Called when the user selects a catalog alternative */
  onSelectAlternative: (alt: CatalogAlternative) => void;
  /** Called when the user taps "Add to Collection" */
  onConfirm: () => void;
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ConfidenceRing({
  value,
  label,
  borderColor,
}: {
  value: number;
  label: string;
  borderColor: string;
}) {
  const { colors } = useAppTheme();
  const pct = Math.round(value * 100);
  const strokeDash = RING_CIRCUMFERENCE * value;
  const ringColor = value >= 0.75 ? colors.success : value >= 0.5 ? colors.warning : colors.error;

  return (
    <View
      style={styles.ringItem}
      accessibilityLabel={`${label} confidence: ${pct} percent`}
      accessibilityRole="text"
    >
      <View style={styles.ringContainer}>
        <Svg width={RING_SIZE} height={RING_SIZE}>
          <Circle
            cx={RING_SIZE / 2}
            cy={RING_SIZE / 2}
            r={RING_RADIUS}
            stroke={borderColor}
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
        <Text style={[styles.ringPct, { color: ringColor }]}>{pct}%</Text>
      </View>
      <Text style={[styles.ringLabel, { color: colors.muted }]}>{label}</Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Pretty-print an attribute key (snake_case -> Title Case) */
function formatKey(k: string): string {
  return k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

function ScanResultCardInner({
  scanResult,
  capturedUri,
  currency,
  onRetake,
  onSelectAlternative,
  onConfirm,
}: ScanResultCardProps) {
  const { colors } = useAppTheme();
  const shareCardRef = useRef<ViewShot>(null);
  const [isSharing, setIsSharing] = useState(false);
  const [showCorrection, setShowCorrection] = useState(false);

  const handleShare = useCallback(async () => {
    if (isSharing) return;
    setIsSharing(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);

    try {
      // Try image share first via ViewShot
      if (shareCardRef.current?.capture) {
        const uri = await shareCardRef.current.capture();
        const Sharing = await import('expo-sharing');
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(uri, {
            mimeType: 'image/png',
            dialogTitle: 'Share scan result',
            UTI: 'public.png',
          });
          track({ name: 'scan_result_shared', properties: { method: 'image', category: scanResult.attributes.category } });
          setIsSharing(false);
          return;
        }
      }
      // Fallback: text share
      const name = scanResult.prediction.name || 'Unknown Item';
      const price = scanResult.prediction.estimatedMid;
      const priceStr = price > 0 ? ` — valued at ${formatPrice(price, currency)}` : '';
      await Share.share({
        message: `${name}${priceStr}\n\nScanned with CollectAI`,
      });
      track({ name: 'scan_result_shared', properties: { method: 'text', category: scanResult.attributes.category } });
    } catch (e) {
      logger.warn('Share failed', e);
    } finally {
      setIsSharing(false);
    }
  }, [isSharing, scanResult, currency]);

  const fc = scanResult.fieldConfidence;
  const alts = scanResult.alternatives ?? [];
  const priceBandLow = scanResult.prediction.estimatedLow;
  const priceBandMid = scanResult.prediction.estimatedMid;
  const priceBandHigh = scanResult.prediction.estimatedHigh;
  const extracted = scanResult.attributes.extractedDetails;

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
  const confLabel =
    overallConf >= 75 ? 'High Confidence' : overallConf >= 50 ? 'Moderate' : 'Low Confidence';
  const confBadgeColor = overallConf >= 75 ? colors.success : overallConf >= 50 ? colors.warning : colors.error;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={styles.scrollContent} bounces={false}>
        {/* Hero image with overlay */}
        <View style={styles.heroContainer}>
          <Image
            source={{ uri: capturedUri }}
            style={styles.heroImage}
            resizeMode="cover"
            accessibilityLabel="Scanned item photo"
          />
          <View style={styles.heroOverlay} />
          {/* Confidence badge on hero */}
          <View
            style={[
              styles.heroBadge,
              { backgroundColor: colors.card + 'EE', borderColor: confBadgeColor + '60' },
            ]}
            accessibilityLabel={`${confLabel}: ${overallConf} percent`}
            accessibilityRole="text"
          >
            <View style={[styles.heroBadgeDot, { backgroundColor: confBadgeColor }]} />
            <Text style={[styles.heroBadgeText, { color: confBadgeColor }]}>{confLabel} · {overallConf}%</Text>
          </View>
          {/* Action buttons on hero */}
          <View style={styles.heroActions}>
            <AnimatedPressable
              style={styles.heroActionBtn}
              onPress={handleShare}
              accessibilityRole="button"
              accessibilityLabel="Share scan result"
            >
              <Ionicons name="share-outline" size={20} color="#FFFFFF" />
            </AnimatedPressable>
            <AnimatedPressable
              style={styles.heroActionBtn}
              onPress={onRetake}
              accessibilityRole="button"
              accessibilityLabel="Retake photo"
            >
              <Ionicons name="camera-reverse-outline" size={22} color="#FFFFFF" />
            </AnimatedPressable>
          </View>
        </View>

        {/* "Is this correct?" confirmation card */}
        {featureFlags.FEATURE_SCAN_FEEDBACK && !showCorrection && (
          <View
            style={{
              backgroundColor: colors.brand.base + '10',
              borderRadius: 16,
              padding: 16,
              marginBottom: 12,
              borderWidth: 1,
              borderColor: colors.brand.base,
              marginTop: 12,
              marginHorizontal: 16,
            }}
          >
            <Text
              style={{ fontSize: 15, fontWeight: '600', color: colors.muted, marginBottom: 8 }}
            >
              Is this correct?
            </Text>
            <Text
              style={{ fontSize: 18, fontWeight: '700', color: colors.text, marginBottom: 6 }}
              numberOfLines={2}
            >
              {scanResult.prediction.name || 'Unknown Item'}
            </Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              <View
                style={{
                  backgroundColor: colors.brand.base + '18',
                  paddingHorizontal: 10,
                  paddingVertical: 4,
                  borderRadius: 8,
                }}
              >
                <Text style={{ fontSize: 12, fontWeight: '600', color: colors.brand.dark }}>
                  {formatKey(scanResult.attributes.category)}
                </Text>
              </View>
              <Text style={{ fontSize: 13, fontWeight: '600', color: colors.muted }}>
                {overallConf}% confidence
              </Text>
            </View>
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <AnimatedPressable
                style={{
                  flex: 1,
                  backgroundColor: TIFFANY,
                  paddingVertical: 12,
                  borderRadius: 12,
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexDirection: 'row',
                  gap: 6,
                }}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                  track({ name: 'quickscan_result_accepted', properties: { category: scanResult.attributes.category, confidence: overallConf } });
                  setShowCorrection(false);
                }}
                accessibilityRole="button"
                accessibilityLabel="Confirm identification is correct"
              >
                <Ionicons name="checkmark-circle" size={18} color={colors.accentText} />
                <Text style={{ color: colors.accentText, fontSize: 14, fontWeight: '700' }}>
                  Yes, this is correct
                </Text>
              </AnimatedPressable>
              <AnimatedPressable
                style={{
                  flex: 1,
                  backgroundColor: 'transparent',
                  paddingVertical: 12,
                  borderRadius: 12,
                  borderWidth: 1.5,
                  borderColor: colors.border,
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexDirection: 'row',
                  gap: 6,
                }}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                  setShowCorrection(true);
                }}
                accessibilityRole="button"
                accessibilityLabel="Open correction form"
              >
                <Ionicons name="create-outline" size={16} color={colors.muted} />
                <Text style={{ color: colors.muted, fontSize: 14, fontWeight: '600' }}>
                  No, let me correct
                </Text>
              </AnimatedPressable>
            </View>
          </View>
        )}

        {/* Item identification card with inline feedback (shown when user taps "No, let me correct") */}
        {showCorrection && (
          <ScanFeedbackPanel
            name={scanResult.prediction.name || ''}
            category={scanResult.attributes.category}
            conditionGuess={scanResult.attributes.conditionGuess}
            scanSessionId={scanResult.scanSessionId}
            feedbackEnabled={!!featureFlags.FEATURE_SCAN_FEEDBACK}
          />
        )}

        {/* Price band section */}
        {priceBandMid > 0 && (
          <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.sectionHeader}>
              <Ionicons name="analytics-outline" size={18} color={colors.brand.dark} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Estimated Value</Text>
            </View>
            <Text style={[styles.priceHero, { color: colors.text }]}>
              {formatPrice(priceBandMid, currency)}
            </Text>
            {/* Price band bar */}
            {priceBandLow > 0 && priceBandHigh > 0 && (
              <View style={styles.priceBandContainer}>
                <View style={[styles.priceBandTrack, { backgroundColor: colors.border + '60' }]}>
                  <View
                    style={[styles.priceBandFill, { left: `${lowPct}%`, width: `${midPct - lowPct}%` }]}
                  />
                  <View style={[styles.priceBandMarker, { left: `${midPct}%` }]} />
                </View>
                <View style={styles.priceBandLabels}>
                  <Text style={[styles.priceBandLabel, { color: colors.muted }]}>
                    {formatPrice(priceBandLow, currency)}
                  </Text>
                  <Text style={[styles.priceBandLabel, { color: colors.muted }]}>
                    {formatPrice(priceBandHigh, currency)}
                  </Text>
                </View>
              </View>
            )}
          </View>
        )}

        {/* Duplicate/variant banner */}
        {featureFlags.FEATURE_DUPLICATE_DETECTION && scanResult.duplicateInfo?.ownedCount ? (
          <View style={[styles.section, { backgroundColor: colors.warning + '15', borderColor: colors.warning + '40' }]}>
            <View style={styles.sectionHeader}>
              <Ionicons name="warning-outline" size={18} color={colors.warning} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                You already have this!
              </Text>
            </View>
            <Text style={{ color: colors.text, fontSize: 13 }}>
              You own {scanResult.duplicateInfo.ownedCount} matching item(s) in your collection.
            </Text>
            {scanResult.duplicateInfo.setCompletion && (
              <Text style={{ color: colors.muted, fontSize: 12, marginTop: 4 }}>
                Set completion: {scanResult.duplicateInfo.setCompletion.pct}% ({scanResult.duplicateInfo.setCompletion.owned}/{scanResult.duplicateInfo.setCompletion.total})
              </Text>
            )}
          </View>
        ) : featureFlags.FEATURE_DUPLICATE_DETECTION && scanResult.duplicateInfo?.isVariant ? (
          <View style={[styles.section, { backgroundColor: colors.info + '15', borderColor: colors.info + '40' }]}>
            <View style={styles.sectionHeader}>
              <Ionicons name="git-branch-outline" size={18} color={colors.info} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                Variant of {scanResult.duplicateInfo.variantOf}
              </Text>
            </View>
          </View>
        ) : null}

        {/* Social proof */}
        <ScanSocialProof socialProof={scanResult.socialProof} currency={currency} />

        {/* Condition grading */}
        <ConditionGradeSelector
          defects={scanResult.defectAnnotations ?? []}
          grade={scanResult.suggestedGrade ?? null}
        />

        {/* Confidence rings */}
        {!!fc && (
          <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.sectionHeader}>
              <Ionicons name="checkmark-done-circle-outline" size={18} color={colors.brand.dark} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>AI Confidence</Text>
            </View>
            <View style={styles.ringsRow}>
              <ConfidenceRing value={fc.name} label="Name" borderColor={colors.border} />
              <ConfidenceRing value={fc.category} label="Category" borderColor={colors.border} />
              <ConfidenceRing value={fc.condition} label="Condition" borderColor={colors.border} />
            </View>
          </View>
        )}

        {/* Extracted details */}
        {detailEntries.length > 0 && (
          <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.sectionHeader}>
              <Ionicons name="list-outline" size={18} color={colors.brand.dark} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Detected Details</Text>
            </View>
            <View style={styles.detailsGrid}>
              {detailEntries.map(([key, val]) => (
                <View key={key} style={styles.detailRow}>
                  <Text style={[styles.detailKey, { color: colors.muted }]}>{formatKey(key)}</Text>
                  <Text style={[styles.detailVal, { color: colors.text }]} numberOfLines={1}>
                    {typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val)}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* "Did you mean?" alternatives */}
        {alts.length > 0 && (
          <View style={styles.altSection}>
            <View style={styles.sectionHeader}>
              <Ionicons name="swap-horizontal-outline" size={18} color={colors.brand.dark} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Did you mean?</Text>
            </View>
            {alts.map((alt, idx) => {
              const isSelected = alt.catalogItemId === scanResult.catalogMatchId;
              return (
                <AnimatedPressable
                  key={alt.catalogItemId ?? `alt-${idx}`}
                  style={[
                    styles.altCard,
                    {
                      backgroundColor: colors.card,
                      borderColor: isSelected ? colors.brand.base : colors.border,
                      borderWidth: isSelected ? 2 : 1,
                    },
                  ]}
                  onPress={() => onSelectAlternative(alt)}
                  accessibilityRole="button"
                  accessibilityLabel={`Select ${alt.title ?? 'alternative'}`}
                >
                  {!!isSelected && (
                    <View style={[styles.altSelectedBadge, { backgroundColor: colors.brand.base }]}>
                      <Ionicons name="checkmark" size={10} color="#FFFFFF" />
                    </View>
                  )}
                  <CatalogImage
                    uri={alt.imageUrl}
                    style={styles.altImage}
                    fallbackIcon="image-outline"
                    accessibilityLabel={`Image of ${alt.title ?? 'alternative'}`}
                  />
                  <View style={styles.altInfo}>
                    <Text style={[styles.altTitle, { color: colors.text }]} numberOfLines={2}>
                      {alt.title ?? 'Unknown'}
                    </Text>
                    <View style={styles.altMeta}>
                      {!!alt.brand && (
                        <Text style={[styles.altBrand, { color: colors.muted }]} numberOfLines={1}>
                          {alt.brand}
                        </Text>
                      )}
                      {!!alt.rarity && (
                        <View style={[styles.altRarityBadge, { backgroundColor: colors.brand.base + '15' }]}>
                          <Text style={[styles.altRarity, { color: colors.brand.dark }]} numberOfLines={1}>
                            {alt.rarity}
                          </Text>
                        </View>
                      )}
                      {!!alt.setCode && (
                        <Text style={[styles.altSetCode, { color: colors.muted }]} numberOfLines={1}>
                          {alt.setCode}
                        </Text>
                      )}
                    </View>
                  </View>
                  <View style={[styles.altScoreBadge, { backgroundColor: colors.brand.base + '12' }]}>
                    <Text style={[styles.altScoreText, { color: colors.brand.dark }]}>
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
      <View
        style={[styles.bottomBar, { backgroundColor: colors.background, borderTopColor: colors.border }]}
      >
        <View style={styles.bottomBarRow}>
          <AnimatedPressable
            style={[styles.shareBtn, { borderColor: colors.border }]}
            onPress={handleShare}
            accessibilityRole="button"
            accessibilityLabel="Share scan result"
          >
            <Ionicons name="share-outline" size={20} color={colors.brand.dark} />
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.addBtn, { backgroundColor: colors.brand.base }]}
            onPress={onConfirm}
            accessibilityRole="button"
            accessibilityLabel="Add to collection"
          >
            <Ionicons name="add-circle" size={22} color="#FFFFFF" />
            <Text style={styles.addBtnText}>Add to Collection</Text>
          </AnimatedPressable>
        </View>
      </View>

      {/* Off-screen share card for ViewShot capture */}
      <View style={styles.offScreen} pointerEvents="none">
        <ViewShot ref={shareCardRef} options={{ format: 'png', quality: 1 }}>
          <ShareCard
            itemName={scanResult.prediction.name || 'Unknown Item'}
            category={scanResult.attributes.category}
            condition={scanResult.attributes.conditionGuess ?? ''}
            priceMid={priceBandMid}
            priceLow={priceBandLow}
            priceHigh={priceBandHigh}
            currency={currency}
            imageUri={capturedUri}
            confidence={
              fc ? (fc.name + fc.category + fc.condition) / 3 : scanResult.prediction.confidence
            }
          />
        </ViewShot>
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 100,
  },
  // Hero image
  heroContainer: {
    width: '100%',
    height: SCREEN_WIDTH * 0.75,
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
    bottom: 14,
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
  heroActions: {
    position: 'absolute',
    bottom: 14,
    right: 16,
    flexDirection: 'row',
    gap: 8,
  },
  heroActionBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
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
    borderColor: '#FFFFFF', // Marker on colored band — always white
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
    borderColor: '#FFFFFF', // Badge border on image — always white
  },
  altImage: {
    width: 52,
    height: 52,
    borderRadius: 10,
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
  bottomBarRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  shareBtn: {
    width: 52,
    height: 52,
    borderRadius: 16,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addBtn: {
    flex: 1,
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
    color: '#FFFFFF', // CTA button text on brand background — always white
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  // Off-screen container for share card capture
  offScreen: {
    position: 'absolute',
    left: -9999,
    top: -9999,
  },
});

export const ScanResultCard = React.memo(ScanResultCardInner);
export default ScanResultCard;
