/**
 * Catalog item "museum" detail screen.
 *
 * READ-ONLY view of a catalog item — "what exists in this category", NOT the
 * user's owned copy. Reached by tapping a catalog item in a category carousel.
 * Deliberately carries NO ownership UI (no purchase price, condition you set,
 * edit/delete) and is keyed by the CATALOG item_key, never a user items row.
 *
 * Gating (verified 2026-06-04): the single `estimated_price` (latest comp,
 * public/free) IS shown. The q10/q50/q90 bands + trend are Pro-gated
 * (`limits.detailed_valuation`) — this screen does NOT fetch or render them for
 * free users; it shows a single locked teaser row instead, so no gated data
 * leaks onto a public catalog screen.
 *
 * "Where to buy" uses the public, affiliate-tagged /marketplace/affiliate-links
 * so every buy tap is monetized.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, Image, StyleSheet, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { useBillingLimits } from '@/hooks/useBillingLimits';
import { fireHaptic, HapticIntent } from '@/haptics';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import { browseCatalogItemsCached } from '@/data/catalogBrowseCache';
import { cleanCatalogItem, cleanCatalogTitle } from '@/lib/catalogPresentation';
import { formatPrice } from '@/lib/format';
import { dataProvider } from '@/data';
import { openAffiliateUrl } from '@/utils/affiliateHelpers';
import { colors as tokens } from '@/theme/tokens';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import logger from '@/utils/logger';
import type { CatalogItemData } from '@/components/CatalogBrowseSection';

type AffiliateLink = { source: string; url: string; affiliate_url: string; label: string };

function CatalogItemMuseumScreen() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { limits } = useBillingLimits();
  const router = useRouter();

  const params = useLocalSearchParams<{
    key?: string; category?: string; title?: string; image_url?: string;
    rarity?: string; set_code?: string; brand?: string; estimated_price?: string;
  }>();

  const title = params.title || 'Catalog item';
  const category = params.category || '';
  const setCode = params.set_code || null;
  const rarity = params.rarity || null;
  const brand = params.brand || null;
  const imageUrl = params.image_url || null;
  const paramPrice = params.estimated_price ? parseFloat(params.estimated_price) : null;

  const [links, setLinks] = useState<AffiliateLink[]>([]);
  const [linksLoading, setLinksLoading] = useState(true);
  const [siblings, setSiblings] = useState<CatalogItemData[]>([]);
  const [adding, setAdding] = useState(false);
  // Price is seeded from the nav param (instant) but falls back to a fetch
  // when the caller didn't pass one — otherwise a priced item shows "No recent
  // sales data" purely because of how it was navigated to (deep link, older
  // build, sibling tap). See the fallback effect below.
  const [estPrice, setEstPrice] = useState<number | null>(paramPrice);

  // Where-to-buy: public affiliate-tagged links (monetized).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await collectorsApi.getAffiliateLinks(title, category, 8, settings.region);
        const data = res as { links?: AffiliateLink[] } | undefined;
        if (!cancelled) setLinks(data?.links ?? []);
      } catch (e) {
        logger.warn('[museum] affiliate links failed:', e);
      } finally {
        if (!cancelled) setLinksLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [title, category, settings.region]);

  // "From this set" — sibling catalog items sharing set_code (catalog-only).
  useEffect(() => {
    if (!setCode || !category) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await browseCatalogItemsCached(category, { limit: 50 });
        const data = res as { items?: CatalogItemData[] } | undefined;
        const sameSet = (data?.items ?? [])
          .filter((it) => it.set_code === setCode && it.item_key !== params.key)
          .slice(0, 10);
        if (!cancelled) setSiblings(sameSet);
      } catch (e) {
        logger.warn('[museum] siblings fetch failed:', e);
      }
    })();
    return () => { cancelled = true; };
  }, [setCode, category, params.key]);

  // Market-value fallback: if we arrived without a price param, fetch the
  // latest comp for this item so a priced item never shows "No recent sales
  // data" just because the entry point omitted estimated_price.
  useEffect(() => {
    if (paramPrice != null || !params.key || !category) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await collectorsApi.getCatalogItemPrice(category, params.key as string);
        if (!cancelled && res?.estimated_price != null) setEstPrice(res.estimated_price);
      } catch (e) {
        logger.warn('[museum] price fallback failed:', e);
      }
    })();
    return () => { cancelled = true; };
  }, [paramPrice, params.key, category]);

  const onAddToWatchlist = useCallback(async () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setAdding(true);
    try {
      // Go through the provider, not collectorsApi directly: the server
      // contract is `name` (NOT `title` — that exact bug was fixed once
      // before in watchlistProvider, 2026-04-30) and the provider also
      // invalidates the cached watchlist.
      await dataProvider.addWatchlistItem({
        title, category, targetPrice: estPrice ?? undefined,
      });
      showToast({ message: `${title} added to watchlist`, type: 'success' });
    } catch (e) {
      // Surface the real failure (status + detail) — a generic message hides
      // whether this is auth, network, or a server error.
      const detail = e instanceof Error && e.message ? ` (${e.message})` : '';
      showToast({ message: `Couldn't add to watchlist — try again${detail}`, type: 'error' });
    } finally {
      setAdding(false);
    }
  }, [title, category, estPrice, settings.hapticsEnabled, showToast]);

  const openLink = useCallback((link: AffiliateLink) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    openAffiliateUrl(link.affiliate_url || link.url);
  }, [settings.hapticsEnabled]);

  const openSibling = useCallback((it: CatalogItemData) => {
    router.push({
      pathname: '/catalog-item/[key]',
      params: {
        key: it.item_key, category: it.category, title: it.title,
        image_url: it.image_url ?? '', rarity: it.rarity ?? '',
        set_code: it.set_code ?? '', brand: it.brand ?? '',
        estimated_price: it.estimated_price != null ? String(it.estimated_price) : '',
      },
    } as unknown as Href);
  }, [router]);

  // Render-time cleanup of scraped fields (jargon, duplicate platform tags,
  // brand-vs-platform mislabel). Does NOT touch stored catalog data.
  const clean = cleanCatalogItem({ title, brand, rarity, setCode });

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.background }} contentContainerStyle={{ paddingBottom: 48 }}>
      {/* Back */}
      <View style={styles.topBar}>
        <AnimatedPressable
          style={[styles.backBtn, { borderColor: colors.border }]}
          onPress={() => router.back()}
          accessibilityRole="button" accessibilityLabel="Go back"
        >
          <Ionicons name="chevron-back" size={20} color={colors.text} />
        </AnimatedPressable>
      </View>

      {/* Hero */}
      {imageUrl ? (
        <Image source={{ uri: imageUrl }} style={styles.hero} resizeMode="contain" accessibilityIgnoresInvertColors />
      ) : (
        <View style={[styles.hero, styles.heroEmpty, { backgroundColor: colors.card }]}>
          <Ionicons name="image-outline" size={48} color={colors.muted} />
          {/* No catalog art yet — user photos will fill these as the database grows. */}
          <Text style={[styles.comingSoon, { color: colors.muted }]}>Image coming soon</Text>
        </View>
      )}

      <View style={styles.body}>
        <Text style={[styles.title, { color: colors.text }]}>{clean.title}</Text>
        {clean.tags.length > 0 && (
          <View style={styles.badgeRow}>
            {clean.tags.map((b) => (
              <View key={b} style={[styles.badge, { backgroundColor: colors.accent + '20' }]}>
                {/* Deep tiffany (mockup --tiffDark): base accent washes out on its own 20% tint */}
                <Text style={[styles.badgeText, { color: tokens.brand.deep }]} numberOfLines={1}>{b}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Market value — FREE estimated price; q-bands/trend are Pro-gated and NOT shown here */}
        <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Text style={[styles.sectionLabel, { color: colors.muted }]}>MARKET VALUE</Text>
          {estPrice != null ? (
            <Text style={[styles.price, { color: colors.text }]}>~{formatPrice(estPrice)}</Text>
          ) : (
            <Text style={[styles.priceMuted, { color: colors.muted }]}>No recent sales data</Text>
          )}
          <Text style={[styles.priceSub, { color: colors.muted }]}>Estimated from the latest marketplace comp</Text>
          {!limits?.advanced_analytics && (
            <AnimatedPressable
              style={[styles.proRow, { borderColor: colors.border }]}
              onPress={() => router.push('/subscription' as Href)}
              accessibilityRole="button" accessibilityLabel="Unlock full market analysis with Pro"
            >
              <Ionicons name="lock-closed" size={14} color={colors.muted} />
              <Text style={[styles.proText, { color: colors.muted }]}>Full price range & 90-day trend — Sparrow Pro</Text>
              <Ionicons name="chevron-forward" size={14} color={colors.muted} />
            </AnimatedPressable>
          )}
        </View>

        {/* Details (from the public catalog fields, cleaned for presentation) */}
        {(clean.platform || clean.brand || clean.setCode || clean.rarity || clean.condition) && (
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.sectionLabel, { color: colors.muted }]}>DETAILS</Text>
            {clean.platform && <Detail label="Platform" value={clean.platform} colors={colors} />}
            {clean.brand && <Detail label="Brand" value={clean.brand} colors={colors} />}
            {clean.setCode && <Detail label="Set" value={clean.setCode} colors={colors} />}
            {clean.condition && <Detail label="Condition" value={clean.condition} colors={colors} />}
            {clean.rarity && <Detail label="Rarity" value={clean.rarity} colors={colors} />}
          </View>
        )}

        {/* From this set */}
        {siblings.length > 0 && (
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.sectionLabel, { color: colors.muted }]}>FROM THIS SET</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
              {siblings.map((it) => (
                <AnimatedPressable key={it.id} style={styles.sibling} onPress={() => openSibling(it)}>
                  {it.image_url ? (
                    <Image source={{ uri: it.image_url }} style={styles.siblingImg} resizeMode="cover" accessibilityIgnoresInvertColors />
                  ) : (
                    <View style={[styles.siblingImg, { backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' }]}>
                      <Ionicons name="cube-outline" size={20} color={colors.muted} />
                    </View>
                  )}
                  <Text style={[styles.siblingName, { color: colors.text }]} numberOfLines={2}>{cleanCatalogTitle(it.title, { brand: it.brand, setCode: it.set_code })}</Text>
                </AnimatedPressable>
              ))}
            </ScrollView>
          </View>
        )}

        {/* Where to buy — affiliate-tagged (monetized) */}
        <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Text style={[styles.sectionLabel, { color: colors.muted }]}>WHERE TO BUY</Text>
          {linksLoading ? (
            <ActivityIndicator color={colors.accent} style={{ marginTop: 12 }} />
          ) : links.length === 0 ? (
            <Text style={[styles.priceSub, { color: colors.muted, marginTop: 8 }]}>No marketplaces available for this item.</Text>
          ) : (
            links.map((link) => (
              <AnimatedPressable
                key={link.source + link.url}
                style={[styles.buyRow, { borderColor: colors.border }]}
                onPress={() => openLink(link)}
                accessibilityRole="button" accessibilityLabel={link.label}
              >
                <Text style={[styles.buyLabel, { color: colors.text }]}>{link.label}</Text>
                <Ionicons name="open-outline" size={16} color={colors.accent} />
              </AnimatedPressable>
            ))
          )}
        </View>

        {/* Primary CTA */}
        <AnimatedPressable
          style={[styles.cta, { backgroundColor: colors.accent, opacity: adding ? 0.6 : 1 }]}
          onPress={onAddToWatchlist} disabled={adding}
          accessibilityRole="button" accessibilityLabel="Add to watchlist"
        >
          <Ionicons name="heart-outline" size={18} color="#fff" />
          <Text style={styles.ctaText}>Add to watchlist</Text>
        </AnimatedPressable>
      </View>
    </ScrollView>
  );
}

function Detail({ label, value, colors }: { label: string; value: string; colors: { text: string; muted: string } }) {
  return (
    <View style={styles.detailRow}>
      <Text style={[styles.detailLabel, { color: colors.muted }]}>{label}</Text>
      <Text style={[styles.detailValue, { color: colors.text }]} numberOfLines={1}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  topBar: { paddingTop: 56, paddingHorizontal: 16, paddingBottom: 4 },
  backBtn: { width: 40, height: 40, borderRadius: 20, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  hero: { width: '100%', height: 280, marginTop: 8 },
  heroEmpty: { alignItems: 'center', justifyContent: 'center' },
  comingSoon: { fontSize: 13, fontWeight: '600', marginTop: 8 },
  body: { padding: 16 },
  title: { fontSize: 22, fontWeight: '800', marginBottom: 8 },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 16 },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },
  badgeText: { fontSize: 12, fontWeight: '600' },
  card: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 14 },
  sectionLabel: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },
  price: { fontSize: 30, fontWeight: '900', marginTop: 6 },
  priceMuted: { fontSize: 18, fontWeight: '600', marginTop: 6 },
  priceSub: { fontSize: 12, marginTop: 2 },
  proRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12, paddingTop: 12, borderTopWidth: 1 },
  proText: { flex: 1, fontSize: 13, fontWeight: '500' },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 10 },
  detailLabel: { fontSize: 13 },
  detailValue: { fontSize: 13, fontWeight: '600', maxWidth: '60%' },
  sibling: { width: 92, marginRight: 12 },
  siblingImg: { width: 92, height: 92, borderRadius: 10 },
  siblingName: { fontSize: 11, marginTop: 6 },
  buyRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth },
  buyLabel: { fontSize: 15, fontWeight: '600' },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 52, borderRadius: 14, marginTop: 6 },
  ctaText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});

export default function CatalogItemMuseumScreenWrapped() {
  return (
    <ScreenErrorBoundary>
      <CatalogItemMuseumScreen />
    </ScreenErrorBoundary>
  );
}
