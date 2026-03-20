/**
 * ShareCard — A branded, screenshot-worthy card for sharing scan results.
 * Designed to look great when shared to Instagram Stories, TikTok, or group chats.
 * Rendered off-screen and captured via ViewShot for image sharing.
 *
 * Visual hierarchy:
 *   1. Tiffany brand bar with logo + confidence
 *   2. Hero item photo with category pill + condition badge
 *   3. Item name (large, bold)
 *   4. Price hero with glow accent
 *   5. Price range bar (low–high)
 *   6. Subtle footer watermark
 */

import React from 'react';
import { View, Text, Image, StyleSheet, Dimensions } from 'react-native';
import { BRAND_COLORS } from '@/constants/colors';
import { fonts } from '@/theme/tokens';
import { formatPrice } from '@/lib/format';
import type { CurrencyCode } from '@/data/types';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const CARD_WIDTH = SCREEN_WIDTH - 48;
const TIFFANY = BRAND_COLORS.tiffany;
const TIFFANY_DARK = BRAND_COLORS.tiffanyDark;

export type ShareCardProps = {
  itemName: string;
  category: string;
  condition: string;
  priceMid: number;
  priceLow: number;
  priceHigh: number;
  currency: CurrencyCode;
  imageUri: string;
  confidence: number;
};

function ShareCardInner({
  itemName,
  category,
  condition,
  priceMid,
  priceLow,
  priceHigh,
  currency,
  imageUri,
  confidence,
}: ShareCardProps) {
  const confPct = Math.round(confidence * 100);
  const categoryLabel = category.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  const confColor = confPct >= 75 ? '#10B981' : confPct >= 50 ? '#F59E0B' : '#EF4444';

  // Price bar percentages
  const priceMax = priceHigh > 0 ? priceHigh : priceMid * 1.5 || 1;
  const lowPct = priceLow > 0 ? Math.round((priceLow / priceMax) * 100) : 0;
  const midPct = priceMid > 0 ? Math.round((priceMid / priceMax) * 100) : 50;

  return (
    <View style={styles.card}>
      {/* ── Brand header ── */}
      <View style={styles.topBar}>
        <View style={styles.brandRow}>
          <View style={styles.logoCircle}>
            <Text style={styles.logoText}>C</Text>
          </View>
          <Text style={styles.brandName}>CollectAI</Text>
        </View>
        <View style={[styles.confBadge, { borderColor: confColor + '50' }]}>
          <View style={[styles.confDot, { backgroundColor: confColor }]} />
          <Text style={[styles.confText, { color: confColor }]}>{confPct}%</Text>
        </View>
      </View>

      {/* ── Hero image ── */}
      <View style={styles.imageContainer}>
        <Image source={{ uri: imageUri }} style={styles.itemImage} resizeMode="cover" />
        <View style={styles.imageOverlay} />

        {/* Category pill */}
        <View style={styles.categoryPill}>
          <Text style={styles.categoryText}>{categoryLabel}</Text>
        </View>

        {/* Condition badge */}
        {condition ? (
          <View style={styles.conditionBadge}>
            <Text style={styles.conditionText}>{condition}</Text>
          </View>
        ) : null}
      </View>

      {/* ── Item info ── */}
      <View style={styles.infoSection}>
        <Text style={styles.itemName} numberOfLines={2}>{itemName}</Text>

        {/* Price hero with accent line */}
        <View style={styles.priceSection}>
          <View style={styles.priceAccentLine} />
          <View style={styles.priceContent}>
            <Text style={styles.priceLabel}>ESTIMATED VALUE</Text>
            <Text style={styles.priceHero}>{formatPrice(priceMid, currency)}</Text>
          </View>
        </View>

        {/* Price range bar */}
        {priceLow > 0 && priceHigh > 0 && (
          <View style={styles.priceBandSection}>
            <View style={styles.priceBandTrack}>
              <View
                style={[
                  styles.priceBandFill,
                  { left: `${lowPct}%`, width: `${Math.max(midPct - lowPct, 5)}%` },
                ]}
              />
              <View style={[styles.priceBandMarker, { left: `${midPct}%` }]} />
            </View>
            <View style={styles.priceBandLabels}>
              <Text style={styles.priceBandLabel}>{formatPrice(priceLow, currency)}</Text>
              <Text style={styles.priceBandLabel}>{formatPrice(priceHigh, currency)}</Text>
            </View>
          </View>
        )}
      </View>

      {/* ── Footer watermark ── */}
      <View style={styles.footer}>
        <View style={styles.footerLine} />
        <View style={styles.footerContent}>
          <Text style={styles.footerBrand}>CollectAI</Text>
          <Text style={styles.footerSep}>·</Text>
          <Text style={styles.footerCta}>Scan any collectible</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: CARD_WIDTH,
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    overflow: 'hidden',
  },

  // ── Brand header ──
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 18,
    paddingVertical: 12,
    backgroundColor: TIFFANY,
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  logoCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.3)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoText: {
    fontSize: 16,
    fontWeight: '900',
    fontFamily: fonts.black,
    color: '#FFFFFF',
  },
  brandName: {
    fontSize: 18,
    fontWeight: '800',
    fontFamily: fonts.bold,
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
  confBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: 'rgba(255,255,255,0.9)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1.5,
  },
  confDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  confText: {
    fontSize: 13,
    fontWeight: '800',
    fontFamily: fonts.bold,
  },

  // ── Hero image ──
  imageContainer: {
    width: '100%',
    height: CARD_WIDTH * 0.65,
    position: 'relative',
    backgroundColor: '#F1F5F9',
  },
  itemImage: {
    width: '100%',
    height: '100%',
  },
  imageOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.08)',
  },
  categoryPill: {
    position: 'absolute',
    bottom: 12,
    left: 12,
    backgroundColor: 'rgba(0,0,0,0.55)',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 14,
  },
  categoryText: {
    fontSize: 12,
    fontWeight: '700',
    fontFamily: fonts.bold,
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
  conditionBadge: {
    position: 'absolute',
    bottom: 12,
    right: 12,
    backgroundColor: 'rgba(255,255,255,0.92)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
  },
  conditionText: {
    fontSize: 11,
    fontWeight: '700',
    fontFamily: fonts.bold,
    color: '#334155',
    letterSpacing: 0.2,
  },

  // ── Item info ──
  infoSection: {
    paddingHorizontal: 20,
    paddingTop: 18,
    paddingBottom: 4,
  },
  itemName: {
    fontSize: 21,
    fontWeight: '800',
    fontFamily: fonts.bold,
    color: '#0F172A',
    letterSpacing: -0.4,
    lineHeight: 27,
  },
  priceSection: {
    flexDirection: 'row',
    alignItems: 'stretch',
    marginTop: 16,
    gap: 14,
  },
  priceAccentLine: {
    width: 3,
    borderRadius: 2,
    backgroundColor: TIFFANY,
  },
  priceContent: {
    flex: 1,
  },
  priceLabel: {
    fontSize: 10,
    fontWeight: '700',
    fontFamily: fonts.bold,
    color: '#94A3B8',
    letterSpacing: 1.2,
  },
  priceHero: {
    fontSize: 34,
    fontWeight: '900',
    fontFamily: fonts.black,
    color: TIFFANY_DARK,
    marginTop: 2,
    letterSpacing: -1,
  },

  // ── Price band ──
  priceBandSection: {
    marginTop: 14,
    gap: 5,
  },
  priceBandTrack: {
    height: 5,
    borderRadius: 3,
    backgroundColor: '#E2E8F0',
    position: 'relative',
    overflow: 'hidden',
  },
  priceBandFill: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    backgroundColor: TIFFANY,
    borderRadius: 3,
    opacity: 0.45,
  },
  priceBandMarker: {
    position: 'absolute',
    top: -3,
    width: 11,
    height: 11,
    borderRadius: 6,
    backgroundColor: TIFFANY_DARK,
    marginLeft: -5,
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  priceBandLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  priceBandLabel: {
    fontSize: 11,
    fontWeight: '500',
    fontFamily: fonts.medium,
    color: '#94A3B8',
  },

  // ── Footer ──
  footer: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 16,
    marginTop: 8,
  },
  footerLine: {
    height: 1,
    backgroundColor: '#F1F5F9',
    marginBottom: 12,
  },
  footerContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  footerBrand: {
    fontSize: 12,
    fontWeight: '800',
    fontFamily: fonts.bold,
    color: TIFFANY_DARK,
    letterSpacing: 0.2,
  },
  footerSep: {
    fontSize: 12,
    fontFamily: fonts.regular,
    color: '#CBD5E1',
  },
  footerCta: {
    fontSize: 11,
    fontWeight: '500',
    fontFamily: fonts.medium,
    color: '#94A3B8',
    letterSpacing: 0.2,
  },
});

export const ShareCard = React.memo(ShareCardInner);
