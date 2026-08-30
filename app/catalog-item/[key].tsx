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
 * (`limits.advanced_analytics`, line 233 — this comment said
 * `limits.detailed_valuation` until 2026-07-28, a key the FE's limits tables
 * do not even define; the code has always read advanced_analytics)
 * — this screen does NOT fetch or render them for
 * free users; it shows a single locked teaser row instead, so no gated data
 * leaks onto a public catalog screen.
 *
 * "Where to buy" uses the public, affiliate-tagged /marketplace/affiliate-links
 * so every buy tap is monetized.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { compNoun } from '@/lib/compProvenance';
import { View, Text, ScrollView, Image, StyleSheet, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { useBillingLimits } from '@/hooks/useBillingLimits';
import { useFavorites } from '@/hooks/useFavorites';
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
import ScreenHeader from '@/components/ScreenHeader';

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

  /**
   * `null` is COULD NOT ASK, `[]` is asked-and-there-are-none. They are
   * different answers and they get different states
   * ([[learning_empty_answer_rendered_as_zero]]).
   *
   * This card used to render a thrown request as "No marketplaces available
   * for this item." — a confident claim about the market made on the strength
   * of a request that never came back. Measured 2026-08-22: the device's own
   * request was in the prod log as
   * `GET /marketplace/affiliate-links?...&category=yugioh` -> **429**, while
   * the same query answered 200 with four marketplaces from the server itself.
   * The links were never missing; the app had spent its per-IP budget.
   */
  const [links, setLinks] = useState<AffiliateLink[] | null>([]);
  const [linksLoading, setLinksLoading] = useState(true);
  // Retry drives the effect through a nonce, so the effect never depends on a
  // value it also writes (scripts/check-self-cancelling-effects.mjs).
  const [linksNonce, setLinksNonce] = useState(0);
  const [siblings, setSiblings] = useState<CatalogItemData[]>([]);
  const [adding, setAdding] = useState(false);
  // Favourites for the CATALOGUE half: keyed by canonical_key (bare), which is
  // what `params.key` already is on this screen.
  const { isFavorite, toggle: toggleFavorite } = useFavorites();
  const favorited = params.key ? isFavorite({ canonical_key: params.key }) : false;
  // Price is seeded from the nav param (instant) but falls back to a fetch
  // when the caller didn't pass one — otherwise a priced item shows "No recent
  // sales data" purely because of how it was navigated to (deep link, older
  // build, sibling tap). See the fallback effect below.
  const [estPrice, setEstPrice] = useState<number | null>(paramPrice);
  // Median over recent comps + how many comps back it — drives the credibility
  // line ("Based on N recent comps"). Fetched on mount; the nav param shows
  // instantly meanwhile.
  const [priceDetail, setPriceDetail] = useState<{ estimated_price: number | null; comps_count: number } | null>(null);

  // Where-to-buy: public affiliate-tagged links (monetized).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // estPrice is the item's own market estimate, and it is what decides
        // whether this is a EUR 45 Casio or a EUR 184,194 Daytona. Without it
        // the server cannot tell them apart and correctly falls back to the
        // general marketplaces for both.
        const res = await collectorsApi.getAffiliateLinks(
          title, category, 8, settings.region, null, undefined, estPrice ?? null,
        );
        const data = res as { links?: AffiliateLink[] } | undefined;
        if (!cancelled) setLinks(data?.links ?? []);
      } catch (e) {
        // logger.error, not warn: release builds strip info/warn, so a warn
        // here is invisible on exactly the builds where this was reported.
        logger.error('[museum] affiliate links failed:', e);
        if (!cancelled) setLinks(null);
      } finally {
        if (!cancelled) setLinksLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // `estPrice` MUST be here. It starts as the route param (often null) and is
    // refined by the price-detail fetch below, so without it in the deps the
    // links are built once with no value and the high-value routing never
    // fires — the Daytona would keep showing eBay because the request went out
    // before its price arrived. Safe to depend on: this effect READS estPrice,
    // it does not write it (the price-detail effect does), so it cannot tear
    // itself down the way scripts/check-self-cancelling-effects.mjs guards
    // against.
  }, [title, category, settings.region, estPrice, linksNonce]);

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
        logger.error('[museum] siblings fetch failed:', e);
      }
    })();
    return () => { cancelled = true; };
  }, [setCode, category, params.key]);

  // Market value: always fetch the detail so we get the comp COUNT (and a
  // robust median) for the credibility line — the nav param only carries a bare
  // latest price. The param still shows instantly; this refines it on arrival.
  useEffect(() => {
    if (!params.key || !category) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await collectorsApi.getCatalogItemPrice(category, params.key as string);
        if (cancelled || !res) return;
        setPriceDetail({ estimated_price: res.estimated_price, comps_count: res.comps_count });
        if (res.estimated_price != null) setEstPrice(res.estimated_price);
      } catch (e) {
        logger.error('[museum] price detail fetch failed:', e);
      }
    })();
    return () => { cancelled = true; };
  }, [params.key, category]);

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
        // Link the row back to the catalog entry it was added from, so the
        // watchlist knows *what* it is watching (was NULL on every row).
        itemId: params.key ?? null,
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
  }, [title, category, estPrice, params.key, settings.hapticsEnabled, showToast]);

  const onToggleFavorite = useCallback(async () => {
    if (!params.key) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      // `category` is the slug this screen already loads with — the same
      // vocabulary market_hits and watchlist_items use.
      const nowFavorite = await toggleFavorite({ canonical_key: params.key }, category);
      showToast({
        message: nowFavorite ? 'Saved to favourites' : 'Removed from favourites',
        type: 'success',
      });
    } catch {
      // useFavorites rolled the optimistic flip back and logged the cause. Say
      // so — a heart that silently snaps back reads as a broken button.
      showToast({ message: "Couldn't save — try again", type: 'error' });
    }
  }, [params.key, category, toggleFavorite, settings.hapticsEnabled, showToast]);

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
      {/* Shared flat header. This screen used to hand-roll a back-only circle,
          which is why the settings icon was missing here while every other
          non-tab screen has it — the exact duplication ScreenHeader was written
          to remove (see its module docstring). */}
      <ScreenHeader />

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
          <Text style={[styles.priceSub, { color: colors.muted }]}>
            {/* "comps" read as completed sales and is not: 99.98% of the
                rows behind these numbers are daily price-index observations
                with no sale timestamp (docs/COLLECTOR_DEMAND.md §1). The noun
                comes from `compNoun` so the item card and this screen cannot
                drift into describing the same rows two ways. This endpoint
                returns only a count -- no `sources` -- so it makes no provider
                or market claim, which is the honest floor. */}
            {estPrice == null
              ? 'Estimated from the latest market observation'
              : (priceDetail && priceDetail.comps_count >= 3)
                ? `Median of ${priceDetail.comps_count} recent ${compNoun(null, priceDetail.comps_count)}`
                : (priceDetail && priceDetail.comps_count > 0)
                  ? `Based on ${priceDetail.comps_count} recent ${compNoun(null, priceDetail.comps_count)}`
                  : 'Estimated from the latest market observation'}
          </Text>
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
          ) : links === null ? (
            <View style={{ marginTop: 8 }}>
              <Text style={[styles.priceSub, { color: colors.muted }]}>Couldn&apos;t load marketplaces.</Text>
              <AnimatedPressable
                onPress={() => { setLinksLoading(true); setLinksNonce((n) => n + 1); }}
                style={[styles.retryBtn, { borderColor: colors.accent }]}
                accessibilityRole="button" accessibilityLabel="Try loading marketplaces again"
              >
                <Text style={[styles.buyLabel, { color: colors.accent }]}>Try again</Text>
                <Ionicons name="refresh" size={16} color={colors.accent} />
              </AnimatedPressable>
            </View>
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

        {/* Primary CTA — WATCH, so it carries the eye.
            It wore a heart until 2026-08-11 while writing a watchlist row,
            which is the same icon this screen now uses for favouriting: one
            glyph meaning two different things on one screen. The heart beside
            it saves; this one sets a target price and can alert.

            The write itself was already correct — `targetPrice: estPrice` and
            `itemId: params.key` — so only the glyph changed. */}
        <View style={styles.ctaRow}>
          <AnimatedPressable
            style={[styles.cta, { backgroundColor: colors.accent, opacity: adding ? 0.6 : 1 }]}
            onPress={onAddToWatchlist} disabled={adding}
            accessibilityRole="button" accessibilityLabel="Add to watchlist"
          >
            <Ionicons name="eye-outline" size={18} color="#fff" />
            <Text style={styles.ctaText}>Add to watchlist</Text>
          </AnimatedPressable>

          {/* Favourite this CATALOGUE entry — keyed by canonical_key, not by a
              listing. Saves; promises nothing. */}
          <AnimatedPressable
            style={[styles.favBtn, { backgroundColor: colors.card, borderColor: colors.border }]}
            onPress={onToggleFavorite}
            accessibilityRole="button"
            accessibilityLabel={favorited ? 'Remove from favourites' : 'Save to favourites'}
            accessibilityState={{ selected: favorited }}
          >
            <Ionicons
              name={favorited ? 'heart' : 'heart-outline'}
              size={20}
              color={favorited ? colors.accent : colors.muted}
            />
          </AnimatedPressable>
        </View>
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
  hero: { width: '100%', height: 280, marginTop: 8 },
  heroEmpty: { alignItems: 'center', justifyContent: 'center' },
  comingSoon: { fontSize: 13, fontWeight: '600', marginTop: 8 },
  body: { padding: 16 },
  title: { fontSize: 24, fontWeight: '800', marginBottom: 8, lineHeight: 30},
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
  // Its OWN style, not a reuse of `buyRow`: that row is a list row carrying
  // only `borderBottomWidth`, so a button borrowing it would have had no
  // visible edge — the outline-button-with-no-borderWidth trap
  // (docs/ui-playbook.md, "What actually catches a UI defect you just wrote").
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 6,
    marginTop: 10,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderRadius: 20,
  },
  ctaRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 6 },
  // flex:1 so the watch CTA keeps the full width it had before the
  // heart joined it, rather than both shrinking to content.
  cta: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 52, borderRadius: 14 },
  favBtn: { width: 52, height: 52, borderRadius: 14, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  ctaText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});

export default function CatalogItemMuseumScreenWrapped() {
  return (
    <ScreenErrorBoundary>
      <CatalogItemMuseumScreen />
    </ScreenErrorBoundary>
  );
}
