/**
 * ShareCard — Premium dark-mode share card for scan results.
 *
 * Cal.ai-inspired design: dark gradient background, frosted glass elements,
 * giant price hero, and subtle branding. Designed to look premium when shared
 * to Instagram Stories, TikTok, or group chats.
 *
 * Rendered off-screen and captured via ViewShot for image sharing.
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

// Dark palette
const BG_DARK = '#0F172A';
const BG_MID = '#1E293B';
const GLASS_BG = 'rgba(255,255,255,0.07)';
const GLASS_BORDER = 'rgba(255,255,255,0.12)';
const TEXT_PRIMARY = '#F8FAFC';
const TEXT_SECONDARY = '#94A3B8';
const TEXT_TERTIARY = '#64748B';

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
  const confColor = confPct >= 75 ? '#34D399' : confPct >= 50 ? '#FBBF24' : '#F87171';

  // Price bar percentages
  const priceMax = priceHigh > 0 ? priceHigh : priceMid * 1.5 || 1;
  const lowPct = priceLow > 0 ? Math.round((priceLow / priceMax) * 100) : 0;
  const midPct = priceMid > 0 ? Math.round((priceMid / priceMax) * 100) : 50;

  return (
    <View style={styles.card}>
      {/* ── Tiffany glow accent (top-left) ── */}
      <View style={styles.glowAccent} />

      {/* ── Floating brand badge ── */}
      <View style={styles.brandBadge}>
        <View style={styles.brandDot} />
        <Text style={styles.brandText}>CollectAI</Text>
      </View>

      {/* ── Hero image ── */}
      <View style={styles.imageWrapper}>
        <View style={styles.imageContainer}>
          <Image source={{ uri: imageUri }} style={styles.itemImage} resizeMode="cover" />
        </View>
        {/* Image shadow glow */}
        <View style={styles.imageShadow} />
      </View>

      {/* ── Glass chips (category + condition) ── */}
      <View style={styles.chipsRow}>
        <View style={styles.glassPill}>
          <Text style={styles.glassPillText}>{categoryLabel}</Text>
        </View>
        {condition ? (
          <View style={styles.glassPill}>
            <Text style={styles.glassPillText}>{condition}</Text>
          </View>
        ) : null}
      </View>

      {/* ── Item name ── */}
      <Text style={styles.itemName} numberOfLines={2}>{itemName}</Text>

      {/* ── Price hero ── */}
      <View style={styles.priceSection}>
        <Text style={styles.priceLabel}>ESTIMATED VALUE</Text>
        <Text style={styles.priceHero}>{formatPrice(priceMid, currency)}</Text>
      </View>

      {/* ── Price range bar ── */}
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

      {/* ── Confidence arc ── */}
      <View style={styles.confSection}>
        <View style={[styles.confRing, { borderColor: confColor + '40' }]}>
          <View style={[styles.confArc, { borderTopColor: confColor, borderRightColor: confColor }]} />
          <Text style={[styles.confValue, { color: confColor }]}>{confPct}%</Text>
        </View>
        <Text style={styles.confLabel}>match confidence</Text>
      </View>

      {/* ── Footer ── */}
      <View style={styles.footer}>
        <View style={styles.footerDivider} />
        <View style={styles.footerContent}>
          <Text style={styles.footerBrand}>collectai.app</Text>
          <View style={styles.footerDot} />
          <Text style={styles.footerCta}>Scan any collectible</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: CARD_WIDTH,
    backgroundColor: BG_DARK,
    borderRadius: 28,
    overflow: 'hidden',
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 20,
    position: 'relative',
  },

  // ── Glow accent ──
  glowAccent: {
    position: 'absolute',
    top: -60,
    left: -60,
    width: 180,
    height: 180,
    borderRadius: 90,
    backgroundColor: TIFFANY,
    opacity: 0.08,
  },

  // ── Brand badge ──
  brandBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-end',
    gap: 6,
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    marginBottom: 16,
  },
  brandDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: TIFFANY,
  },
  brandText: {
    fontSize: 13,
    fontWeight: '700',
    fontFamily: fonts.bold,
    color: TEXT_SECONDARY,
    letterSpacing: 0.3,
  },

  // ── Hero image ──
  imageWrapper: {
    alignItems: 'center',
    marginBottom: 20,
    position: 'relative',
  },
  imageContainer: {
    width: CARD_WIDTH - 80,
    height: (CARD_WIDTH - 80) * 0.85,
    borderRadius: 20,
    overflow: 'hidden',
    backgroundColor: BG_MID,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
  },
  itemImage: {
    width: '100%',
    height: '100%',
  },
  imageShadow: {
    position: 'absolute',
    bottom: -8,
    left: 20,
    right: 20,
    height: 16,
    borderRadius: 20,
    backgroundColor: TIFFANY,
    opacity: 0.12,
  },

  // ── Glass chips ──
  chipsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  glassPill: {
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
  },
  glassPillText: {
    fontSize: 12,
    fontWeight: '600',
    fontFamily: fonts.medium,
    color: TEXT_SECONDARY,
    letterSpacing: 0.3,
  },

  // ── Item name ──
  itemName: {
    fontSize: 22,
    fontWeight: '800',
    fontFamily: fonts.bold,
    color: TEXT_PRIMARY,
    letterSpacing: -0.3,
    lineHeight: 28,
    marginBottom: 20,
  },

  // ── Price hero ──
  priceSection: {
    marginBottom: 16,
  },
  priceLabel: {
    fontSize: 11,
    fontWeight: '700',
    fontFamily: fonts.bold,
    color: TEXT_TERTIARY,
    letterSpacing: 1.5,
    marginBottom: 4,
  },
  priceHero: {
    fontSize: 40,
    fontWeight: '900',
    fontFamily: fonts.black,
    color: TIFFANY,
    letterSpacing: -1.5,
  },

  // ── Price band ──
  priceBandSection: {
    marginBottom: 20,
    gap: 6,
  },
  priceBandTrack: {
    height: 4,
    borderRadius: 2,
    backgroundColor: 'rgba(255,255,255,0.08)',
    position: 'relative',
    overflow: 'visible',
  },
  priceBandFill: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    backgroundColor: TIFFANY,
    borderRadius: 2,
    opacity: 0.35,
  },
  priceBandMarker: {
    position: 'absolute',
    top: -4,
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: TIFFANY,
    marginLeft: -6,
    borderWidth: 2,
    borderColor: BG_DARK,
    shadowColor: TIFFANY,
    shadowOpacity: 0.5,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 0 },
    elevation: 4,
  },
  priceBandLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  priceBandLabel: {
    fontSize: 11,
    fontWeight: '500',
    fontFamily: fonts.medium,
    color: TEXT_TERTIARY,
  },

  // ── Confidence section ──
  confSection: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 20,
  },
  confRing: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 3,
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  confArc: {
    position: 'absolute',
    top: -3,
    left: -3,
    right: -3,
    bottom: -3,
    borderRadius: 22,
    borderWidth: 3,
    borderColor: 'transparent',
    transform: [{ rotate: '-45deg' }],
  },
  confValue: {
    fontSize: 14,
    fontWeight: '800',
    fontFamily: fonts.bold,
  },
  confLabel: {
    fontSize: 12,
    fontWeight: '500',
    fontFamily: fonts.medium,
    color: TEXT_TERTIARY,
    letterSpacing: 0.2,
  },

  // ── Footer ──
  footer: {
    marginTop: 4,
  },
  footerDivider: {
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.06)',
    marginBottom: 14,
  },
  footerContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  footerBrand: {
    fontSize: 12,
    fontWeight: '700',
    fontFamily: fonts.bold,
    color: TIFFANY_DARK,
    letterSpacing: 0.3,
  },
  footerDot: {
    width: 3,
    height: 3,
    borderRadius: 1.5,
    backgroundColor: TEXT_TERTIARY,
  },
  footerCta: {
    fontSize: 11,
    fontWeight: '500',
    fontFamily: fonts.medium,
    color: TEXT_TERTIARY,
    letterSpacing: 0.2,
  },
});

export const ShareCard = React.memo(ShareCardInner);
