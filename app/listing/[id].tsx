/**
 * Listing detail — one member listing.
 *
 * This is the destination of `https://sparrowcollect.com/l/<id>`, the URL the
 * P2P supply hook writes into `market_hits.url`. Without this screen a Target
 * Hit on a member listing opened a URL nothing served — the dead-button
 * failure the snipe query was specifically fixed to avoid, reintroduced from
 * our own side. See docs/P2P_MARKETPLACE_SPEC.md.
 *
 * Stage 1 has no checkout by design. The action is "Message seller", which
 * hands off to the existing chat. Sparrow never touches funds, and the screen
 * says so plainly rather than implying protection we do not provide — an
 * implied guarantee is the fastest way to inherit liability we deliberately
 * scoped out.
 */
import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, Animated, Alert } from 'react-native';
import { useToast } from '@/components/Toast';
import { Image } from 'expo-image';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import ScreenHeader from '@/components/ScreenHeader';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { EmptyState } from '@/components/EmptyState';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useAsync } from '@/hooks/useAsync';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import { collectorsApi } from '@/api/collectorsApi';
import { CATEGORY_SLUG_TO_NAME } from '@/constants/categories';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';
import logger from '@/utils/logger';

function ListingDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const { data: listing, loading, error, retry } = useAsync(
    async () => (id ? collectorsApi.getP2PListing(id) : null),
    [id],
  );

  const handleMessage = useCallback(() => {
    if (!listing) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // toUserId is REQUIRED — chat/new calls dataProvider.requestDm(toUserId,…)
    // and without it the send fails. Passing the title too so the seller sees
    // what is being asked about instead of a bare "hi" from a stranger.
    // Stage 1 deliberately stops here: no offers, no checkout.
    router.push({
      pathname: '/chat/new',
      params: { toUserId: listing.user_id, contextListingTitle: listing.title },
    });
  }, [listing, router, settings.hapticsEnabled]);

  const [reported, setReported] = useState(false);
  const [offered, setOffered] = useState(false);
  const { showToast } = useToast();

  // Offer ladder rather than a free-text input: one number, three taps, no
  // modal. A keyboard for a single figure is friction at exactly the moment
  // intent is highest.
  const handleOffer = useCallback(() => {
    if (!listing) return;
    const steps = [0.9, 0.8, 0.7].map((f) => Math.round(listing.price * f * 100) / 100);
    Alert.alert(
      'Make an offer',
      `Asking ${formatPrice(listing.price, settings.currency, settings.numberLocale)}. Offer:`,
      [
        ...steps.map((amt) => ({
          text: formatPrice(amt, settings.currency, settings.numberLocale),
          onPress: async () => {
            try {
              await collectorsApi.p2pCreateOffer({
                listing_id: listing.id, amount: amt, currency: listing.currency,
              });
              fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
              setOffered(true);
              showToast({ message: 'Offer sent — the seller will be notified', type: 'success' });
            } catch (e: unknown) {
              logger.error('[listing] offer failed:', e);
              showToast({ message: (e as Error)?.message || 'Could not send the offer', type: 'error' });
            }
          },
        })),
        { text: 'Cancel', style: 'cancel' as const },
      ],
    );
  }, [listing, settings, showToast]);

  // DSA notice-and-action. The micro-enterprise exemption does NOT cover this
  // obligation, so a report path ships in Stage 1 rather than later. Reasons
  // are fixed options, not free text: a structured reason is what makes
  // triage and a statement-of-reasons possible, and it stops the field being
  // used as an abuse channel against the seller.
  const handleReport = useCallback(() => {
    if (!listing) return;
    const reasons = [
      'Counterfeit or replica',
      'Prohibited item',
      'Misleading description',
      'Suspected scam',
    ];
    Alert.alert(
      'Report this listing',
      'Tell us what is wrong. We review reports and act on them.',
      [
        ...reasons.map((reason) => ({
          text: reason,
          onPress: async () => {
            try {
              await collectorsApi.reportListing(listing.id, reason);
              setReported(true);
            } catch (e) {
              logger.error('[listing] report failed:', e);
            }
          },
        })),
        { text: 'Cancel', style: 'cancel' as const },
      ],
    );
  }, [listing]);

  const handleDelist = useCallback(async () => {
    if (!listing) return;
    try {
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      await collectorsApi.delistListing(listing.id, 'sold');
      retry();
    } catch (e) {
      logger.error('[listing] delist failed:', e);
    }
  }, [listing, retry, settings.hapticsEnabled]);

  if (loading) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <ScreenHeader title="Listing" />
        <View style={styles.center}>
          <Text style={[styles.muted, { color: colors.muted }]}>Loading…</Text>
        </View>
      </View>
    );
  }

  if (error || !listing) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <ScreenHeader title="Listing" />
        <EmptyState
          icon="pricetag-outline"
          title="Listing unavailable"
          subtitle="It may have been removed by the seller."
          colors={colors}
          action={
            <AnimatedPressable
              onPress={retry}
              style={[styles.primaryBtn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Try again"
            >
              <Text style={[styles.primaryBtnText, { color: colors.accentText }]}>Try again</Text>
            </AnimatedPressable>
          }
        />
      </View>
    );
  }

  // A sold listing resolves 200 with status 'sold' rather than 404, so the
  // buyer learns the item went instead of seeing an error. Surface that
  // clearly — a Target Hit that lands here should explain itself.
  const isGone = listing.status !== 'active';

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScreenHeader title="Listing" />
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Animated.View style={animatedStyle}>
          {listing.image_url ? (
            <View>
              <Image source={{ uri: listing.image_url }} style={styles.hero} contentFit="cover" transition={150} />
              {/* The grid (app/listings.tsx) labelled this and the DETAIL screen
                  did not — the wrong way round. This is where a buyer studies
                  the item before messaging or making an offer, so an unlabelled
                  stock photo here is the one that actually misleads. Per
                  ListingOut.image_is_catalog: "a stock photo passed off as the
                  actual item hides condition, which is the one thing a
                  second-hand buyer needs to see". Found by walking a listing
                  whose seller had no photo of their own. */}
              {listing.image_is_catalog ? (
                <View style={[styles.stockTag, { backgroundColor: colors.background + 'E6' }]}>
                  <Text style={[styles.stockTagText, { color: colors.muted }]}>
                    Catalog photo — not the seller&apos;s item
                  </Text>
                </View>
              ) : null}
            </View>
          ) : (
            <View style={[styles.hero, styles.heroEmpty, { backgroundColor: colors.accent + '12' }]}>
              <Ionicons name="image-outline" size={40} color={colors.muted} />
            </View>
          )}

          {isGone ? (
            <View style={[styles.banner, { backgroundColor: colors.muted + '1E' }]}>
              <Ionicons name="checkmark-done-outline" size={16} color={colors.muted} />
              <Text style={[styles.bannerText, { color: colors.muted }]}>
                This listing is no longer available ({listing.status}).
              </Text>
            </View>
          ) : null}

          <Text style={[styles.title, { color: colors.text }]}>{listing.title}</Text>
          <Text style={[styles.price, { color: colors.text }]}>
            {formatPrice(listing.price, settings.currency, settings.numberLocale)}
          </Text>
          {/* All-in price. `shipping_cost` is NULLABLE and null means "the
              seller didn't say", which is NOT zero — rendering it as "free
              shipping" would be the unknown-as-zero class the silent-failure
              checker exists for. Three distinct states, one of which is
              silence. Estimates are already disclaimed in app/legal/terms.tsx. */}
          {listing.shipping_cost != null ? (
            <Text style={[styles.allIn, { color: colors.muted }]}>
              {listing.shipping_cost > 0
                ? // ONE derived number, not price + shipping + total.
                  // `formatPrice` renders 0 decimals for every currency by
                  // design (src/lib/format.ts), so three independently rounded
                  // figures can visibly fail to add up: €42.50 + €6.50 renders
                  // as "43 €" + "7 € shipping" = "49 € total", and 43 + 7 ≠ 49.
                  // Caught by walking the simulator, not by any test — the
                  // arithmetic is only wrong once it is rounded for display.
                  // The total is the number the buyer actually pays, so it is
                  // the one worth showing. The exact shipping figure is
                  // deliberately NOT rendered alongside it: any second money
                  // number here re-creates the sum the reader will check.
                  `${formatPrice(listing.price + listing.shipping_cost, settings.currency, settings.numberLocale)} total incl. shipping`
                : 'Free shipping'}
            </Text>
          ) : (
            <Text style={[styles.allIn, { color: colors.muted }]}>
              Shipping not stated — ask the seller
            </Text>
          )}

          <View style={styles.metaRow}>
            {listing.condition_label ? (
              <View style={[styles.pill, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <Text style={[styles.pillText, { color: colors.text }]}>{listing.condition_label}</Text>
              </View>
            ) : null}
            {listing.category ? (
              <View style={[styles.pill, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <Text style={[styles.pillText, { color: colors.text }]}>
                  {CATEGORY_SLUG_TO_NAME[listing.category] ?? listing.category}
                </Text>
              </View>
            ) : null}
            {listing.ships_from ? (
              <View style={[styles.pill, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <Ionicons name="location-outline" size={12} color={colors.muted} />
                <Text style={[styles.pillText, { color: colors.text }]}>{listing.ships_from}</Text>
              </View>
            ) : null}
          </View>

          {listing.description ? (
            <Text style={[styles.body, { color: colors.text }]}>{listing.description}</Text>
          ) : null}

          {/* Only the seller, and only when it matters. A listing with no
              canonical identity is skipped by the publish supply hook, so it
              never becomes a buyable market_hits row and can never fire a
              Target Hit — it is findable by browsing and invisible to everyone
              watching for exactly this item. That was silent until 2026-08-07;
              the seller had no way to know their listing reached nobody.
              Deliberately not shown to buyers: it says nothing about the item. */}
          {listing.is_mine && !listing.reaches_target_hit && !isGone ? (
            <View style={[styles.notice, { borderColor: colors.border }]}>
              <Ionicons name="notifications-off-outline" size={16} color={colors.muted} />
              <View style={{ flex: 1 }}>
                <Text style={[styles.noticeText, { color: colors.muted }]}>
                  This listing won&apos;t alert members watching for this item — it
                  isn&apos;t matched to a catalogue entry. It still shows in browse
                  and search.
                </Text>
                <Text style={[styles.noticeText, { color: colors.muted, marginTop: 4 }]}>
                  Match the item in your collection to a catalogue entry, then
                  relist, and everyone watching it gets a Target Hit.
                </Text>
              </View>
            </View>
          ) : null}

          {listing.watchers > 0 ? (
            <View style={[styles.demandRow, { backgroundColor: colors.accent + '12' }]}>
              <Ionicons name="eye-outline" size={14} color={colors.accent} />
              <Text style={[styles.demandText, { color: colors.text }]}>
                {listing.watchers} other member{listing.watchers === 1 ? '' : 's'} watching this item
              </Text>
            </View>
          ) : null}

          {/* Seller credibility. A buyer is about to message a stranger about
              a potentially expensive item; these are the only honest signals
              we have without transaction history. Every field degrades: a
              profile with no display name and no items still renders. */}
          <View style={[styles.seller, { borderColor: colors.border }]}>
            <View style={[styles.sellerAvatar, { backgroundColor: colors.accent + '18' }]}>
              <Ionicons name="person-outline" size={16} color={colors.accent} />
            </View>
            <View style={styles.sellerText}>
              {/* Name and reputation on one line, so the credibility signal is
                  read WITH the identity rather than as a separate stat. */}
              <View style={styles.sellerNameRow}>
                <Text style={[styles.sellerName, { color: colors.text }]} numberOfLines={1}>
                  {listing.seller_name || 'Sparrow member'}
                  {listing.is_mine ? ' (you)' : ''}
                </Text>
                {/* Gated on having completed a trade. A "no rating yet" badge on
                    every listing in a young marketplace reads as a warning and
                    is worse than absence — below the gate the tenure and
                    collection line underneath is the honest signal, and it
                    already renders. */}
                {listing.seller_completed_trades > 0 ? (
                  <View style={[styles.repPill, { backgroundColor: colors.accent + '18' }]}>
                    <Ionicons
                      name="checkmark-circle"
                      size={12}
                      color={colors.accent}
                    />
                    <Text style={[styles.repPillText, { color: colors.accent }]}>
                      {/* Percentage only once the server says the sample is big
                          enough (seller_positive_pct is null until then). The
                          trade count leads because it is a fact at n=1, whereas
                          "100% positive" off one grade is not credibility. */}
                      {listing.seller_positive_pct !== null
                        ? `${listing.seller_positive_pct}% positive · ${listing.seller_completed_trades} trade${listing.seller_completed_trades === 1 ? '' : 's'}`
                        : `${listing.seller_completed_trades} completed trade${listing.seller_completed_trades === 1 ? '' : 's'}`}
                    </Text>
                  </View>
                ) : null}
              </View>
              <Text style={[styles.sellerMeta, { color: colors.muted }]}>
                {[
                  listing.seller_since
                    ? `Member since ${new Date(listing.seller_since).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}`
                    : null,
                  listing.seller_collection_size > 0
                    ? `${listing.seller_collection_size} item${listing.seller_collection_size === 1 ? '' : 's'} tracked`
                    : null,
                  listing.seller_active_listings > 1
                    ? `${listing.seller_active_listings} listings`
                    : null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </Text>
            </View>
          </View>

          {/* Stage 1 has no payment protection. Say so rather than let the
              buyer assume it — an implied guarantee is exactly the liability
              this stage is scoped to avoid. */}
          <View style={[styles.notice, { borderColor: colors.border }]}>
            <Ionicons name="information-circle-outline" size={16} color={colors.muted} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.noticeText, { color: colors.muted }]}>
                Sparrow doesn&apos;t handle payment or delivery. You arrange those
                directly with the seller, and there is no buyer protection.
              </Text>
              <AnimatedPressable
                onPress={() => router.push('/legal/marketplace-terms' as Href)}
                accessibilityRole="link"
                accessibilityLabel="Read the marketplace terms"
              >
                <Text style={[styles.noticeLink, { color: colors.accent }]}>Marketplace terms</Text>
              </AnimatedPressable>
            </View>
          </View>

          {listing.is_mine ? (
            !isGone ? (
              <AnimatedPressable
                onPress={handleDelist}
                style={[styles.primaryBtn, { backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1 }]}
                accessibilityRole="button"
                accessibilityLabel="Mark as sold"
              >
                <Text style={[styles.primaryBtnText, { color: colors.text }]}>Mark as sold</Text>
              </AnimatedPressable>
            ) : null
          ) : !isGone ? (
            <>
              <AnimatedPressable
                onPress={handleOffer}
                disabled={offered}
                style={[styles.primaryBtn, { backgroundColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel={offered ? 'Offer sent' : 'Make an offer'}
              >
                <Ionicons name="pricetag-outline" size={16} color={colors.accentText} />
                <Text style={[styles.primaryBtnText, { color: colors.accentText }]}>
                  {offered ? 'Offer sent' : 'Make an offer'}
                </Text>
              </AnimatedPressable>
              <AnimatedPressable
                onPress={handleMessage}
              style={[styles.primaryBtn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Message the seller"
            >
              <Ionicons name="chatbubble-outline" size={16} color={colors.accentText} />
                <Text style={[styles.primaryBtnText, { color: colors.text }]}>Message seller</Text>
              </AnimatedPressable>
            </>
          ) : null}
          {/* Report — not for your own listing. Placed last: it must be
              findable without competing with the primary action. */}
          {!listing.is_mine ? (
            <AnimatedPressable
              onPress={handleReport}
              disabled={reported}
              style={styles.reportRow}
              accessibilityRole="button"
              accessibilityLabel={reported ? 'Listing reported' : 'Report this listing'}
            >
              <Ionicons
                name={reported ? 'checkmark-circle-outline' : 'flag-outline'}
                size={14}
                color={colors.muted}
              />
              <Text style={[styles.reportText, { color: colors.muted }]}>
                {reported ? 'Reported — thank you' : 'Report this listing'}
              </Text>
            </AnimatedPressable>
          ) : null}
        </Animated.View>
      </ScrollView>
    </View>
  );
}

export default function ListingDetailScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Listing Detail">
      <ListingDetailScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  muted: { fontSize: textToken.md },
  content: { padding: 16, paddingBottom: 48, gap: 10 },
  hero: { width: '100%', aspectRatio: 1, borderRadius: radius.md },
  // Same treatment as the grid tile in app/listings.tsx, sized up for a
  // full-width hero so it is legible rather than decorative.
  stockTag: {
    position: 'absolute', left: 10, bottom: 10,
    paddingHorizontal: 8, paddingVertical: 4, borderRadius: radius.xs,
  },
  stockTagText: { fontSize: 11, fontWeight: fontWeight.semibold },
  heroEmpty: { alignItems: 'center', justifyContent: 'center' },
  banner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    padding: 10, borderRadius: radius.sm, marginTop: 10,
  },
  bannerText: { fontSize: textToken.sm, flex: 1 },
  title: { fontSize: textToken.xl, fontWeight: fontWeight.bold, marginTop: 12 },
  price: { fontSize: textToken.xl, fontWeight: fontWeight.extrabold },
  allIn: { fontSize: textToken.xs, marginTop: 2 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 4 },
  pill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    borderWidth: 1, borderRadius: radius.sm,
    paddingHorizontal: 10, paddingVertical: 5,
  },
  pillText: { fontSize: textToken.xs },
  body: { fontSize: textToken.md, lineHeight: 21, marginTop: 6 },
  demandRow: {
    flexDirection: 'row', alignItems: 'center', gap: 7,
    paddingHorizontal: 10, paddingVertical: 8,
    borderRadius: radius.sm, marginTop: 12,
  },
  demandText: { fontSize: textToken.xs, fontWeight: fontWeight.semibold },
  secondaryBtn: { backgroundColor: 'transparent', borderWidth: 1 },
  seller: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm,
    padding: 11, marginTop: 14,
  },
  sellerAvatar: {
    width: 34, height: 34, borderRadius: 17,
    alignItems: 'center', justifyContent: 'center',
  },
  sellerText: { flex: 1, gap: 2 },
  // Name + reputation share a row. `flexWrap` so a long display name and a long
  // pill drop to a second line instead of the pill being squeezed to nothing,
  // and the name gets flexShrink so it truncates before the pill does — the
  // reputation is the part a buyer cannot infer from anywhere else on screen.
  sellerNameRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6 },
  sellerName: { fontSize: textToken.md, fontWeight: fontWeight.semibold, flexShrink: 1 },
  repPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill,
  },
  repPillText: { fontSize: 11, fontWeight: fontWeight.bold },
  sellerMeta: { fontSize: textToken.xs, lineHeight: 16 },
  notice: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm,
    padding: 10, marginTop: 12,
  },
  noticeText: { fontSize: textToken.xs, lineHeight: 17 },
  noticeLink: { fontSize: textToken.xs, fontWeight: fontWeight.bold, marginTop: 5 },
  reportRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, marginTop: 22, paddingVertical: 10,
  },
  reportText: { fontSize: textToken.xs },
  primaryBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    marginTop: 16, paddingVertical: 13, borderRadius: radius.md,
  },
  primaryBtnText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
});
