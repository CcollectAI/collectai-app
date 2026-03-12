/**
 * ScanResultCard Component
 * Displays the QuickScan result screen: hero image, item identification card,
 * estimated value, AI confidence rings, extracted details, "Did you mean?"
 * catalog alternatives, and action buttons (retake / add to collection).
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Image,
  ScrollView,
  StatusBar,
  Dimensions,
  TextInput,
  Alert,
} from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';
import { featureFlags } from '@/config/featureFlags';
import { SocialProofSection } from '@/components/SocialProofSection';
import { ConditionGradeSection } from '@/components/ConditionGradeSection';
import { submitScanFeedback } from '@/api/collectorsApi';
import type { QuickScanResult, CatalogAlternative, CurrencyCode } from '@/data/types';

const TIFFANY = '#81D8D0'; // fallback for StyleSheet only
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

  // Scan feedback state (F9)
  const [editingField, setEditingField] = useState<'name' | 'category' | 'condition' | null>(null);
  const [editValue, setEditValue] = useState('');
  const [feedbackSent, setFeedbackSent] = useState(false);

  const handleStartEdit = useCallback((field: 'name' | 'category' | 'condition', current: string) => {
    if (!featureFlags.FEATURE_SCAN_FEEDBACK || !scanResult.scanSessionId) return;
    setEditingField(field);
    setEditValue(current);
  }, [scanResult.scanSessionId]);

  const handleSubmitFeedback = useCallback(async () => {
    if (!editingField || !scanResult.scanSessionId) return;
    try {
      const feedback: { scanSessionId: string; correctedName?: string; correctedCategory?: string; correctedCondition?: string } = { scanSessionId: scanResult.scanSessionId };
      if (editingField === 'name') feedback.correctedName = editValue;
      else if (editingField === 'category') feedback.correctedCategory = editValue;
      else if (editingField === 'condition') feedback.correctedCondition = editValue;
      await submitScanFeedback(feedback);
      setFeedbackSent(true);
      setEditingField(null);
      Alert.alert('Thanks!', 'Your correction helps improve future scans.');
    } catch {
      Alert.alert('Error', 'Could not submit feedback. Please try again.');
    }
  }, [editingField, editValue, scanResult.scanSessionId]);

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
              { backgroundColor: '#FFFFFFEE', borderColor: confBadgeColor + '60' },
            ]}
            accessibilityLabel={`${confLabel}: ${overallConf} percent`}
            accessibilityRole="text"
          >
            <View style={[styles.heroBadgeDot, { backgroundColor: confBadgeColor }]} />
            <Text style={[styles.heroBadgeText, { color: confBadgeColor }]}>{confLabel} · {overallConf}%</Text>
          </View>
          {/* Retake button on hero */}
          <AnimatedPressable
            style={styles.heroRetake}
            onPress={onRetake}
            accessibilityRole="button"
            accessibilityLabel="Retake photo"
          >
            <Ionicons name="camera-reverse-outline" size={22} color="#FFFFFF" />
          </AnimatedPressable>
        </View>

        {/* Item identification card -- overlaps hero */}
        <View style={[styles.idCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {editingField === 'name' ? (
            <View style={styles.feedbackEditRow}>
              <TextInput
                style={[styles.feedbackInput, { color: colors.text, borderColor: colors.brand.base }]}
                value={editValue}
                onChangeText={setEditValue}
                autoFocus
                returnKeyType="done"
                onSubmitEditing={handleSubmitFeedback}
                accessibilityLabel="Edit item name"
              />
              <AnimatedPressable onPress={handleSubmitFeedback} style={[styles.feedbackSubmitBtn, { backgroundColor: colors.brand.base }]} accessibilityRole="button" accessibilityLabel="Submit correction">
                <Ionicons name="checkmark" size={16} color="#FFF" />
              </AnimatedPressable>
              <AnimatedPressable onPress={() => setEditingField(null)} style={styles.feedbackCancelBtn} accessibilityRole="button" accessibilityLabel="Cancel editing">
                <Ionicons name="close" size={16} color={colors.muted} />
              </AnimatedPressable>
            </View>
          ) : (
            <AnimatedPressable
              onPress={() => handleStartEdit('name', scanResult.prediction.name || '')}
              accessibilityRole="button"
              accessibilityLabel={`Item name: ${scanResult.prediction.name || 'Unknown Item'}. ${featureFlags.FEATURE_SCAN_FEEDBACK ? 'Tap to correct' : ''}`}
              accessibilityHint={featureFlags.FEATURE_SCAN_FEEDBACK ? 'Tap to correct' : undefined}
            >
              <Text style={[styles.idName, { color: colors.text }]} numberOfLines={3}>
                {scanResult.prediction.name || 'Unknown Item'}
              </Text>
            </AnimatedPressable>
          )}
          <View style={styles.idMeta}>
            {editingField === 'category' ? (
              <View style={styles.feedbackEditRow}>
                <TextInput
                  style={[styles.feedbackInput, styles.feedbackInputSmall, { color: colors.text, borderColor: colors.brand.base }]}
                  value={editValue}
                  onChangeText={setEditValue}
                  autoFocus
                  returnKeyType="done"
                  onSubmitEditing={handleSubmitFeedback}
                  accessibilityLabel="Edit category value"
                />
                <AnimatedPressable onPress={handleSubmitFeedback} style={[styles.feedbackSubmitBtn, { backgroundColor: colors.brand.base }]} accessibilityRole="button" accessibilityLabel="Submit category correction">
                  <Ionicons name="checkmark" size={14} color="#FFF" />
                </AnimatedPressable>
                <AnimatedPressable onPress={() => setEditingField(null)} style={styles.feedbackCancelBtn} accessibilityRole="button" accessibilityLabel="Cancel editing">
                  <Ionicons name="close" size={14} color={colors.muted} />
                </AnimatedPressable>
              </View>
            ) : (
              <AnimatedPressable
                onPress={() => handleStartEdit('category', scanResult.attributes.category)}
                accessibilityRole="button"
                accessibilityLabel={`Category: ${scanResult.attributes.category.replace(/_/g, ' ')}`}
                style={[styles.categoryChip, { backgroundColor: colors.brand.base + '18' }]}
              >
                <Ionicons name="pricetag" size={12} color={colors.brand.dark} />
                <Text style={[styles.categoryChipText, { color: colors.brand.dark }]}>
                  {scanResult.attributes.category
                    .replace(/_/g, ' ')
                    .replace(/\b\w/g, (c) => c.toUpperCase())}
                </Text>
                {featureFlags.FEATURE_SCAN_FEEDBACK && <Ionicons name="pencil" size={10} color={colors.brand.dark} style={{ marginLeft: 4 }} />}
              </AnimatedPressable>
            )}
            {!!scanResult.attributes.conditionGuess && editingField !== 'condition' && (
              <AnimatedPressable
                onPress={() => handleStartEdit('condition', scanResult.attributes.conditionGuess || '')}
                style={[styles.conditionChip, { backgroundColor: colors.border + '80' }]}
                accessibilityRole="button"
                accessibilityLabel={`Condition: ${scanResult.attributes.conditionGuess?.replace(/_/g, ' ') ?? 'unknown'}`}
              >
                <Ionicons name="shield-checkmark" size={12} color={colors.muted} />
                <Text style={[styles.conditionChipText, { color: colors.text }]}>
                  {scanResult.attributes.conditionGuess
                    .replace(/_/g, ' ')
                    .replace(/\b\w/g, (c) => c.toUpperCase())}
                </Text>
                {featureFlags.FEATURE_SCAN_FEEDBACK && <Ionicons name="pencil" size={10} color={colors.muted} style={{ marginLeft: 4 }} />}
              </AnimatedPressable>
            )}
            {editingField === 'condition' && (
              <View style={styles.feedbackEditRow}>
                <TextInput
                  style={[styles.feedbackInput, styles.feedbackInputSmall, { color: colors.text, borderColor: colors.brand.base }]}
                  value={editValue}
                  onChangeText={setEditValue}
                  autoFocus
                  returnKeyType="done"
                  onSubmitEditing={handleSubmitFeedback}
                  accessibilityLabel="Edit condition value"
                />
                <AnimatedPressable onPress={handleSubmitFeedback} style={[styles.feedbackSubmitBtn, { backgroundColor: colors.brand.base }]} accessibilityRole="button" accessibilityLabel="Submit condition correction">
                  <Ionicons name="checkmark" size={14} color="#FFF" />
                </AnimatedPressable>
                <AnimatedPressable onPress={() => setEditingField(null)} style={styles.feedbackCancelBtn} accessibilityRole="button" accessibilityLabel="Cancel editing">
                  <Ionicons name="close" size={14} color={colors.muted} />
                </AnimatedPressable>
              </View>
            )}
          </View>
          {featureFlags.FEATURE_SCAN_FEEDBACK && !feedbackSent && scanResult.scanSessionId && (
            <Text style={[styles.feedbackHint, { color: colors.muted }]}>
              Tap name, category, or condition to correct
            </Text>
          )}
          {feedbackSent && (
            <View style={styles.feedbackSentBadge}>
              <Ionicons name="checkmark-circle" size={14} color="#22C55E" />
              <Text style={{ color: colors.success, fontSize: 11, marginLeft: 4 }}>Correction submitted</Text>
            </View>
          )}
        </View>

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
        {featureFlags.FEATURE_SOCIAL_PROOF && scanResult.socialProof && (
          <SocialProofSection socialProof={scanResult.socialProof} currency={currency} />
        )}

        {/* Condition grading */}
        {featureFlags.FEATURE_CONDITION_GRADING && (
          <ConditionGradeSection
            defects={scanResult.defectAnnotations ?? []}
            grade={scanResult.suggestedGrade ?? null}
          />
        )}

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
                  {!!alt.imageUrl ? (
                    <Image source={{ uri: alt.imageUrl }} style={styles.altImage} resizeMode="cover" accessibilityLabel={`Image of ${alt.title ?? 'alternative'}`} />
                  ) : (
                    <View style={[styles.altImage, { backgroundColor: colors.border }]}>
                      <Ionicons name="image-outline" size={20} color={colors.muted} />
                    </View>
                  )}
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
  heroRetake: {
    position: 'absolute',
    bottom: 14,
    right: 16,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  // ID Card (below hero)
  idCard: {
    marginTop: 12,
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
  // Feedback (F9)
  feedbackEditRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  feedbackInput: {
    flex: 1,
    borderWidth: 1.5,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    fontSize: 14,
    fontWeight: '600',
  },
  feedbackInputSmall: {
    fontSize: 12,
    paddingVertical: 4,
  },
  feedbackSubmitBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  feedbackCancelBtn: {
    width: 28,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  feedbackHint: {
    fontSize: 11,
    marginTop: 8,
    fontStyle: 'italic',
  },
  feedbackSentBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
});

export const ScanResultCard = React.memo(ScanResultCardInner);
export default ScanResultCard;
