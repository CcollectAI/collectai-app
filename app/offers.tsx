/**
 * Offers — the Stage 2 negotiation and trust loop.
 *
 * See docs/P2P_MARKETPLACE_SPEC.md. One screen for both sides of every trade,
 * because a member is usually both a buyer and a seller and splitting them
 * into two screens means checking two places for the same conversation.
 *
 * The state machine lives on the SERVER. This screen renders `can_confirm`,
 * `can_grade` and `already_graded` as the API computes them rather than
 * re-deriving the rules — two implementations of one state machine is how
 * they drift apart.
 *
 * Playbook rules this is built around (docs/ui-playbook.md):
 *  - Header outside the list (FlashList hit-area bug) — and it's a FlatList.
 *  - `useTabBarInset` for QuickNavBar clearance.
 *  - No `accessibilityRole="tabbar"` (hard-crashes Android).
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  View, Text, FlatList, StyleSheet, RefreshControl, Alert, Animated,
  Linking, TextInput, ScrollView,
} from 'react-native';
import { useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import ScreenHeader from '@/components/ScreenHeader';
import { BottomSheetModal } from '@/components/BottomSheetModal';
import { OfferAmountSheet } from '@/components/p2p/OfferAmountSheet';
import { QuickNavBar } from '@/components/QuickNavBar';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { EmptyState } from '@/components/EmptyState';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useTabBarInset } from '@/hooks/useTabBarInset';
import { useAsync } from '@/hooks/useAsync';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { showActionSheet } from '@/hooks/useActionSheetPicker';
import { formatPrice } from '@/lib/format';
import { collectorsApi } from '@/api/collectorsApi';
import type { P2POffer, P2PCarrier } from '@/api/p2pApi';
import { radius, text as textToken, fontWeight, shadow } from '@/theme/tokens';
import logger from '@/utils/logger';

type Role = 'all' | 'buying' | 'selling';

/** Status → human label + tone. Keys mirror p2p_offers_status_check. */
const STATUS_LABEL: Record<string, string> = {
  pending: 'Awaiting seller',
  countered: 'Countered',
  accepted: 'Agreed — arrange the exchange',
  declined: 'Declined',
  cancelled: 'Withdrawn',
  expired: 'Expired',
  shipped: 'Sent',
  completed: 'Completed',
};

function OffersScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const bottomInset = useTabBarInset();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const [role, setRole] = useState<Role>('all');
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Tracking capture. The offer being edited drives the sheet; null = closed.
  const [trackingFor, setTrackingFor] = useState<P2POffer | null>(null);
  const [carriers, setCarriers] = useState<P2PCarrier[]>([]);
  const [carriersState, setCarriersState] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle');
  const [carrierKey, setCarrierKey] = useState<string | null>(null);
  const [trackingCode, setTrackingCode] = useState('');
  // "Have we already fetched the carriers this session?" — deliberately a ref,
  // so it is invisible to the fetch effect's dep array. `carrierRetry` is the
  // only thing that may re-trigger that effect, and only the retry button
  // bumps it. See the effect below for what putting this in state cost.
  const carrierFetchRef = useRef(false);
  const [carrierRetry, setCarrierRetry] = useState(0);

  const { data, loading, error, retry } = useAsync(
    async () => (await collectorsApi.p2pListOffers(role))?.offers ?? [],
    [role],
  );
  const offers = useMemo(() => data ?? [], [data]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try { await retry(); } finally { setRefreshing(false); }
  }, [retry]);

  const act = useCallback(
    async (fn: () => Promise<unknown>, offerId: string, successMsg?: string) => {
      setBusyId(offerId);
      try {
        await fn();
        fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
        if (successMsg) showToast({ message: successMsg, type: 'success' });
        await retry();
      } catch (e: unknown) {
        // Surface the server's message: 409s here are meaningful states
        // ("already confirmed", "offer is already declined"), not failures.
        logger.error('[offers] action failed:', e);
        showToast({ message: (e as Error)?.message || 'That didn\'t work', type: 'error' });
      } finally {
        setBusyId(null);
      }
    },
    [retry, showToast, settings.hapticsEnabled],
  );

  // Counter amounts come from `OfferAmountSheet` — signed percentage presets
  // plus a custom field, the same component the buyer's side uses.
  //
  // It was an `Alert.alert` ladder of ×1.1 / ×1.2 / ×1.35 off the BUYER'S offer,
  // labelled with money only: no percentage, and no way to counter with any
  // other figure (Alert.prompt is iOS-only, so a text field was impossible in
  // that container).
  //
  // The reference is now the listing's ASKING price, not the buyer's offer.
  // Against the buyer's own offer a "−5%" preset means "less than they already
  // offered", which no seller would ever send; against asking, both directions
  // are real moves and −5% is exactly the concession a counter usually is. Falls
  // back to the offer amount when `listing_price` is null (a deleted listing
  // row), and the sheet's label says which basis is in use rather than showing
  // an unexplained percentage.
  const [counterFor, setCounterFor] = useState<P2POffer | null>(null);

  const onCounter = useCallback((o: P2POffer) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setCounterFor(o);
  }, [settings.hapticsEnabled]);

  const submitCounter = useCallback(async (amount: number) => {
    if (!counterFor) return;
    const offerId = counterFor.id;
    setCounterFor(null);
    await act(
      () => collectorsApi.p2pRespondToOffer(offerId, 'counter', amount),
      offerId,
      'Counter sent',
    );
  }, [act, counterFor]);

  // Carriers come from the SERVER (`_CARRIER_TRACKING`), not a list hardcoded
  // here — a client copy would let a seller pick a carrier the server cannot
  // resolve, which silently degrades to a code with no link. Fetched when the
  // sheet first opens rather than on mount: most sessions never ship anything.
  // Tri-state, not a bare list. "Empty" and "still loading" render identically
  // if you only track the array, and the playbook's rule is that a user who
  // cannot tell them apart is being lied to (docs/ui-playbook.md, "Empty ≠
  // loading"). The first version showed "Couldn't load carriers" for the whole
  // duration of a perfectly healthy fetch.
  //
  // The re-entry guard is a REF, and `carriersState` is NOT a dependency.
  //
  // It used to be both: the effect read `carriersState !== 'idle'` as its guard
  // and listed it in the dep array. `setCarriersState('loading')` on the line
  // below therefore changed a dependency of the effect that had just set it, so
  // React tore the effect down — running `cancelled = true` — while the request
  // was still in flight. The `.then` and the `.catch` both no-op'd, the sheet
  // sat on "Loading carriers…" forever, and the retry was unreachable because
  // the error branch never rendered. Every seller, every open, since the sheet
  // shipped; the endpoint was healthy the whole time (reported 2026-08-09).
  //
  // Note the old comment's claim that httpClient's REQUEST_TIMEOUT_MS made
  // hanging impossible. It didn't: a timeout bounds the REQUEST, and the
  // request was never the problem — the handler that would act on it had been
  // disarmed. `scripts/check-self-cancelling-effects.mjs` now fails the build
  // on a dependency the effect writes itself.
  useEffect(() => {
    if (!trackingFor || carrierFetchRef.current) return;
    carrierFetchRef.current = true;
    let cancelled = false;
    let settled = false;
    setCarriersState('loading');
    collectorsApi
      .p2pListCarriers()
      .then((list) => {
        settled = true;
        if (cancelled) return;
        setCarriers(list ?? []);
        setCarriersState('ok');
      })
      .catch((e) => {
        settled = true;
        // logger.error, not warn — warn is stripped in release builds, which is
        // exactly where a silent empty picker would be invisible.
        logger.error('[offers] carrier list failed:', e);
        if (!cancelled) setCarriersState('error');
      });
    return () => {
      cancelled = true;
      // Re-arm only if we tore down BEFORE the response settled — closing the
      // sheet mid-flight would otherwise latch 'loading' with the guard held,
      // and reopening would show the same dead spinner the ref exists to
      // prevent. A settled fetch keeps the guard so reopening is instant.
      if (!settled) carrierFetchRef.current = false;
    };
  }, [trackingFor, carrierRetry]);

  /** Label for the chosen carrier. Derived from the SERVER list rather than
   *  stored alongside the key, so a key with no matching row (a carrier retired
   *  server-side) shows the placeholder instead of a stale name. */
  const carrierLabel = useMemo(
    () => carriers.find((c) => c.key === carrierKey)?.label ?? null,
    [carriers, carrierKey],
  );

  const pickCarrier = useCallback(() => {
    if (carriers.length === 0) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // Options are built from the same array the field reads, so the index the
    // sheet returns cannot address a different carrier than the one displayed.
    showActionSheet('Carrier', carriers.map((c) => c.label), (i) => {
      const chosen = carriers[i];
      if (chosen) setCarrierKey(chosen.key);
    });
  }, [carriers, settings.hapticsEnabled]);

  const openTracking = useCallback((o: P2POffer) => {
    setTrackingFor(o);
    setCarrierKey(o.tracking_carrier ?? null);
    setTrackingCode(o.tracking_code ?? '');
  }, []);

  const closeTracking = useCallback(() => setTrackingFor(null), []);

  // ONE definition of "is this saveable", used by the guard, the `disabled`
  // prop and the disabled styling. Three copies of the same predicate is how
  // an enabled-looking button that refuses to do anything gets shipped.
  // Minimum 3 matches TrackingIn.tracking_code's pattern on the server.
  const canSaveTracking = useMemo(
    () => Boolean(trackingFor && carrierKey) && trackingCode.trim().length >= 3,
    [trackingFor, carrierKey, trackingCode],
  );

  const saveTracking = useCallback(async () => {
    if (!trackingFor || !carrierKey || !canSaveTracking) return;
    const offerId = trackingFor.id;
    setTrackingFor(null);
    await act(
      () => collectorsApi.p2pSetOfferTracking(offerId, carrierKey, trackingCode.trim()),
      offerId,
      'Tracking added',
    );
  }, [act, canSaveTracking, carrierKey, trackingCode, trackingFor]);

  const onGrade = useCallback((o: P2POffer) => {
    Alert.alert(
      'How did it go?',
      'Your grade is visible to other members and helps them trade safely.',
      [
        { text: 'Good trade', onPress: () => act(() => collectorsApi.p2pGradeCounterparty(o.id, 'positive'), o.id, 'Thanks — graded') },
        { text: 'Problem', style: 'destructive' as const, onPress: () => act(() => collectorsApi.p2pGradeCounterparty(o.id, 'negative'), o.id, 'Grade recorded') },
        { text: 'Later', style: 'cancel' as const },
      ],
    );
  }, [act]);

  const renderOffer = useCallback(({ item: o }: { item: P2POffer }) => {
    const busy = busyId === o.id;
    const isSeller = !o.i_am_buyer;
    const open = o.status === 'pending' || o.status === 'countered';
    const live = o.status === 'accepted' || o.status === 'shipped';

    // Left edge stripe carries the role at a glance while scanning, so you do
    // not have to read the pill on every card. Same two semantic colours as the
    // pill — the treatment reads as one system, not two signals.
    return (
      <View style={[
        styles.card,
        {
          backgroundColor: colors.card,
          borderColor: colors.border,
          borderLeftWidth: 3,
          borderLeftColor: o.i_am_buyer ? colors.info : colors.success,
        },
      ]}>
        <View style={styles.rowTop}>
          <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
            {o.listing_title || 'Listing'}
          </Text>
          <Text style={[styles.amount, { color: colors.text }]}>
            {formatPrice(o.amount, settings.currency, settings.numberLocale)}
          </Text>
          {/* The offer ALONE does not decide anything — "EUR 380" is only good
              or bad against what you asked. The percentage is the number a
              seller actually judges on, and it is the same reference the
              counter sheet uses (the ASKING price, never the buyer's own
              offer — see docs/P2P_MARKETPLACE_SPEC.md 10d). Rendered only when
              the server sent a listing price; a computed "0%" would be a
              claim we cannot back. */}
          {typeof o.listing_price === 'number' && o.listing_price > 0 ? (
            <Text style={[styles.amountDelta, { color: colors.muted }]}>
              {(() => {
                const pct = Math.round(((o.amount - o.listing_price) / o.listing_price) * 100);
                const sign = pct > 0 ? '+' : '';
                return `${sign}${pct}% of ${formatPrice(o.listing_price, settings.currency, settings.numberLocale)} asking`;
              })()}
            </Text>
          ) : null}
        </View>

        <View style={styles.metaRow}>
          {/* Buy/sell told by COLOUR, not just the word (2026-08-11).
              Both roles used to render `colors.accent + '18'` with accent text —
              identical fill, identical text colour, distinguished only by
              "Buying" / "Selling". In a mixed list that is no distinction at all.
              info = buying, success = selling: both are existing theme tokens
              with proper light/dark/high-contrast variants, so nothing is
              hardcoded, and the brand accent stays reserved for CTAs and confirm
              ticks rather than competing with role. */}
          <View style={[
            styles.rolePill,
            { backgroundColor: o.i_am_buyer ? colors.infoBg : colors.successBg },
          ]}>
            <Text style={[
              styles.rolePillText,
              { color: o.i_am_buyer ? colors.info : colors.success },
            ]}>
              {o.i_am_buyer ? 'Buying' : 'Selling'}
            </Text>
          </View>
          <Text style={[styles.status, { color: colors.muted }]}>
            {STATUS_LABEL[o.status] ?? o.status}
            {o.counter_count > 0 ? ` · ${o.counter_count} counter${o.counter_count === 1 ? '' : 's'}` : ''}
          </Text>
        </View>

        {o.message ? (
          <Text style={[styles.message, { color: colors.muted }]} numberOfLines={3}>“{o.message}”</Text>
        ) : null}

        {/* Two-sided completion, made legible. A seller who has confirmed but
            is waiting on the buyer should SEE that, not wonder if it worked. */}
        {live ? (
          <View style={styles.confirmRow}>
            <Ionicons
              name={o.seller_confirmed_at ? 'checkmark-circle' : 'ellipse-outline'}
              size={14}
              color={o.seller_confirmed_at ? colors.accent : colors.muted}
            />
            <Text style={[styles.confirmText, { color: colors.muted }]}>Seller sent</Text>
            <Ionicons
              name={o.buyer_confirmed_at ? 'checkmark-circle' : 'ellipse-outline'}
              size={14}
              color={o.buyer_confirmed_at ? colors.accent : colors.muted}
            />
            <Text style={[styles.confirmText, { color: colors.muted }]}>Buyer received</Text>
          </View>
        ) : null}

        {/* Shipment visibility. DISPLAY ONLY — this never advances the trade.
            Completion stays the two ticks above, which only a human sets. */}
        {o.tracking_code ? (
          <View style={[styles.tracking, { borderColor: colors.border }]}>
            <Ionicons name="cube-outline" size={14} color={colors.muted} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.trackingLabel, { color: colors.muted }]}>
                {o.tracking_carrier_label ?? 'Carrier'}
              </Text>
              {/* `selectable` rather than a copy button: expo-clipboard is not
                  installed, and a guarded require of a missing package is a
                  silent no-op on BOTH platforms (learning_ios_only_apis_
                  silently_noop_on_android). Selectable text always works. */}
              <Text selectable style={[styles.trackingCode, { color: colors.text }]}>
                {o.tracking_code}
              </Text>
            </View>
            {o.tracking_url ? (
              <AnimatedPressable
                onPress={() => {
                  const url = o.tracking_url;
                  if (!url) return;
                  Linking.openURL(url).catch((e) =>
                    logger.error('[offers] tracking link failed:', e));
                }}
                accessibilityRole="link"
                accessibilityLabel={`Track this parcel with ${o.tracking_carrier_label ?? 'the carrier'}`}
              >
                <Text style={[styles.trackLink, { color: colors.accent }]}>Track</Text>
              </AnimatedPressable>
            ) : (
              // No link rather than a broken one. PostNL and DPD need the
              // recipient's postcode in the URL and we deliberately don't hold
              // it — a 404 button is the dead-button failure Stage 1 bug 0 was
              // fixed to avoid.
              <Text style={[styles.trackHint, { color: colors.muted }]}>
                Search this code{'\n'}on the carrier&apos;s site
              </Text>
            )}
          </View>
        ) : null}

        <View style={styles.actions}>
          {/* Seller decides on an open offer. */}
          {isSeller && open ? (
            <>
              <AnimatedPressable
                onPress={() => act(() => collectorsApi.p2pRespondToOffer(o.id, 'accept'), o.id, 'Offer accepted')}
                disabled={busy}
                style={[styles.btn, { backgroundColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel="Accept this offer"
              >
                <Text style={[styles.btnText, { color: colors.accentText }]}>Accept</Text>
              </AnimatedPressable>
              <AnimatedPressable
                onPress={() => onCounter(o)}
                disabled={busy}
                style={[styles.btn, styles.btnGhost, { borderColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel="Counter this offer"
              >
                <Text style={[styles.btnText, { color: colors.accent }]}>Counter</Text>
              </AnimatedPressable>
              {/* Tertiary, and CONFIRMED. Declining cannot be undone on that
                  offer — the buyer has to make a new one — and it sat here as
                  a same-size button beside Accept, one mis-tap from killing a
                  sale. docs/ui-playbook.md: confirm destructive actions. */}
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  Alert.alert(
                    'Decline this offer?',
                    'The buyer will be told. They can send a new offer, but this one is gone.',
                    [
                      { text: 'Keep it', style: 'cancel' },
                      {
                        text: 'Decline',
                        style: 'destructive',
                        onPress: () => act(() => collectorsApi.p2pRespondToOffer(o.id, 'decline'), o.id, 'Declined'),
                      },
                    ],
                  );
                }}
                disabled={busy}
                style={[styles.btn, styles.btnQuiet]}
                accessibilityRole="button"
                accessibilityLabel="Decline this offer"
              >
                <Text style={[styles.btnText, { color: colors.danger }]}>Decline</Text>
              </AnimatedPressable>
            </>
          ) : null}

          {/* can_confirm / can_grade come from the SERVER — see file header. */}
          {o.can_confirm ? (
            <AnimatedPressable
              onPress={() => act(
                () => collectorsApi.p2pConfirmExchange(o.id),
                o.id,
                o.i_am_buyer ? 'Marked received' : 'Marked sent',
              )}
              disabled={busy}
              style={[styles.btn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel={o.i_am_buyer ? 'Mark as received' : 'Mark as sent'}
            >
              <Text style={[styles.btnText, { color: colors.accentText }]}>
                {o.i_am_buyer ? 'Mark received' : 'Mark sent'}
              </Text>
            </AnimatedPressable>
          ) : null}

          {/* can_add_tracking is server-computed (seller, and trade live). It is
              a hint only — the endpoint enforces both independently. */}
          {o.can_add_tracking ? (
            <AnimatedPressable
              onPress={() => openTracking(o)}
              disabled={busy}
              style={[styles.btn, styles.btnGhost, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel={o.tracking_code ? 'Edit tracking details' : 'Add tracking details'}
            >
              <Text style={[styles.btnText, { color: colors.text }]}>
                {o.tracking_code ? 'Edit tracking' : 'Add tracking'}
              </Text>
            </AnimatedPressable>
          ) : null}

          {live ? (
            <AnimatedPressable
              // Labelled "Delete" because that is what a member is doing —
              // taking their offer off the table. The API action stays
              // `withdraw` and the resulting row still reads "Withdrawn": the
              // server writes cancelled + withdrawn_by, since 'withdrawn' is not
              // a legal p2p_offers status (spec §1d). Renaming the wire format to
              // match a button label would break that constraint.
              onPress={() => act(() => collectorsApi.p2pRespondToOffer(o.id, 'withdraw'), o.id, 'Deleted')}
              disabled={busy}
              style={[styles.btn, styles.btnGhost, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel="Delete this offer"
            >
              <Text style={[styles.btnText, { color: colors.muted }]}>Delete</Text>
            </AnimatedPressable>
          ) : null}

          {o.can_grade && !o.already_graded ? (
            <AnimatedPressable
              onPress={() => onGrade(o)}
              disabled={busy}
              style={[styles.btn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Grade the other member"
            >
              <Text style={[styles.btnText, { color: colors.accentText }]}>Grade trade</Text>
            </AnimatedPressable>
          ) : null}

          {o.already_graded ? (
            <Text style={[styles.graded, { color: colors.muted }]}>You graded this trade</Text>
          ) : null}
        </View>

        <AnimatedPressable
          onPress={() => router.push({ pathname: '/listing/[id]', params: { id: o.listing_id } } as unknown as Href)}
          accessibilityRole="link"
          accessibilityLabel="View the listing"
        >
          <Text style={[styles.viewLink, { color: colors.accent }]}>View listing</Text>
        </AnimatedPressable>
      </View>
    );
  }, [act, busyId, colors, onCounter, onGrade, openTracking, router, settings.currency, settings.numberLocale]);

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScreenHeader title="Offers" />

      <Animated.View style={[styles.segmentWrap, animatedStyle]}>
        <View style={[styles.segment, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {(['all', 'buying', 'selling'] as Role[]).map((r) => {
            const active = role === r;
            return (
              <AnimatedPressable
                key={r}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  setRole(r);
                }}
                style={[
                  styles.segmentBtn,
                  // The chips inherit the same role colours as the cards, so
                  // selecting "Buying" tints the control the same blue the
                  // buying cards carry. "All" stays on the brand accent.
                  active && {
                    backgroundColor:
                      r === 'buying' ? colors.infoBg
                      : r === 'selling' ? colors.successBg
                      : colors.accent + '1E',
                  },
                ]}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                accessibilityLabel={r === 'all' ? 'All offers' : r === 'buying' ? 'Offers I made' : 'Offers I received'}
              >
                <Text style={[
                  styles.segmentText,
                  {
                    color: !active ? colors.muted
                      : r === 'buying' ? colors.info
                      : r === 'selling' ? colors.success
                      : colors.accent,
                  },
                  active && { fontWeight: fontWeight.bold },
                ]}>
                  {r === 'all' ? 'All' : r === 'buying' ? 'Buying' : 'Selling'}
                </Text>
              </AnimatedPressable>
            );
          })}
        </View>
      </Animated.View>

      {loading && !refreshing ? (
        <View style={styles.pad}>
          <Text style={[styles.loadingText, { color: colors.muted }]}>Loading offers…</Text>
        </View>
      ) : error ? (
        <EmptyState
          icon="cloud-offline-outline"
          title="Couldn't load offers"
          subtitle="Check your connection and try again."
          colors={colors}
          action={
            <AnimatedPressable onPress={retry} style={[styles.btn, { backgroundColor: colors.accent }]}
              accessibilityRole="button" accessibilityLabel="Try again">
              <Text style={[styles.btnText, { color: colors.accentText }]}>Try again</Text>
            </AnimatedPressable>
          }
        />
      ) : (
        <FlatList
          data={offers}
          keyExtractor={(o) => o.id}
          renderItem={renderOffer}
          contentContainerStyle={[styles.list, { paddingBottom: bottomInset }]}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.accent} />}
          ListEmptyComponent={
            <EmptyState
              icon="swap-horizontal-outline"
              title={role === 'selling' ? 'No offers received yet' : 'No offers yet'}
              subtitle={
                role === 'selling'
                  ? 'When someone offers on your listings, it appears here.'
                  : 'Find something on the marketplace and make an offer.'
              }
              colors={colors}
              action={
                <AnimatedPressable
                  onPress={() => router.push('/listings' as Href)}
                  style={[styles.btn, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Browse the marketplace"
                >
                  <Text style={[styles.btnText, { color: colors.accentText }]}>Browse marketplace</Text>
                </AnimatedPressable>
              }
            />
          }
        />
      )}

      {/* BottomSheetModal, not Alert.prompt — the latter is iOS-only, and a
          consignment code has to be typed so there is no option ladder that
          would avoid an input. The wrapper already handles onRequestClose
          (Android back) and safe-area-context. */}
      <BottomSheetModal
        visible={trackingFor !== null}
        onClose={closeTracking}
        title={trackingFor?.tracking_code ? 'Edit tracking' : 'Add tracking'}
        colors={colors}
        maxHeight="70%"
      >
        <ScrollView contentContainerStyle={styles.sheet} keyboardShouldPersistTaps="handled">
          <Text style={[styles.sheetHint, { color: colors.muted }]}>
            The buyer sees this so they can follow the parcel. Sparrow doesn&apos;t
            check it and it doesn&apos;t complete the trade — you both still confirm
            by hand.
          </Text>

          {/* A dropdown, not a chip grid — `showActionSheet` is what every other
              picker in the app uses (native ActionSheetIOS on iOS, an Alert on
              Android), so a carrier is chosen the same way a category or a
              condition is in app/sell/new.tsx. The chips also grew with the
              carrier list; a field does not. */}
          <Text style={[styles.sheetLabel, { color: colors.text }]}>Carrier</Text>
          <AnimatedPressable
            onPress={pickCarrier}
            disabled={carriers.length === 0}
            style={[styles.field, { borderColor: colors.border, backgroundColor: colors.card }]}
            accessibilityRole="button"
            accessibilityState={{ disabled: carriers.length === 0 }}
            accessibilityLabel="Choose the carrier"
          >
            <Text style={[styles.fieldText, { color: carrierLabel ? colors.text : colors.muted }]}>
              {carrierLabel ?? (carriers.length === 0 ? 'No carriers available' : 'Choose a carrier')}
            </Text>
            <Ionicons name="chevron-down" size={16} color={colors.muted} />
          </AnimatedPressable>
          {/* Loading and failed are DIFFERENT states and must read differently.
              The retry releases the ref guard and bumps `carrierRetry`, which is
              what re-triggers the effect — an earlier copy said "pull to
              refresh", which refetches the offers list and would never have
              fetched carriers again. */}
          {carriersState === 'loading' ? (
            <Text style={[styles.sheetHint, { color: colors.muted }]}>Loading carriers…</Text>
          ) : carriersState === 'error' || (carriersState === 'ok' && carriers.length === 0) ? (
            // A successful response with an empty list is treated as a failure
            // on purpose. The server always returns _CARRIER_TRACKING, so empty
            // means something upstream broke — and rendering a sheet with no
            // choices and no message is the silent-empty pattern this codebase
            // keeps getting bitten by.
            <View style={styles.carrierError}>
              <Text style={[styles.sheetHint, { color: colors.muted }]}>
                Couldn&apos;t load the carrier list.
              </Text>
              <AnimatedPressable
                onPress={() => {
                  carrierFetchRef.current = false;
                  setCarrierRetry((n) => n + 1);
                }}
                accessibilityRole="button"
                accessibilityLabel="Retry loading carriers"
              >
                <Text style={[styles.trackLink, { color: colors.accent }]}>Try again</Text>
              </AnimatedPressable>
            </View>
          ) : null}

          <Text style={[styles.sheetLabel, { color: colors.text }]}>Tracking code</Text>
          <TextInput
            value={trackingCode}
            // Masked to the charset TrackingIn.tracking_code accepts on the
            // server. Without this a typed '.' or '#' left the Save button
            // enabled and the request came back a 422 whose message names a
            // regex — unactionable for a seller. Masking fails visibly (the
            // character just doesn't appear) instead of failing on submit.
            // Widen the server pattern and this mask must widen with it.
            onChangeText={(t) => setTrackingCode(t.replace(/[^A-Za-z0-9 \-_/]/g, ''))}
            placeholder="e.g. 3STBJG123456789"
            placeholderTextColor={colors.muted}
            autoCapitalize="characters"
            autoCorrect={false}
            maxLength={64}
            style={[styles.input, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
            accessibilityLabel="Tracking code"
          />
          {/* Selected carrier can't produce a code-only link — set expectations
              in the sheet rather than letting the seller discover it after. */}
          {carrierKey && carriers.find((c) => c.key === carrierKey)?.linkable === false ? (
            <Text style={[styles.sheetHint, { color: colors.muted }]}>
              This carrier needs the delivery postcode to open a tracking page,
              which Sparrow doesn&apos;t hold. The buyer will see the code to search
              with instead of a link.
            </Text>
          ) : null}

          {/* `colors.accentText` is ONLY valid on an accent/brand fill. Pairing
              it with the disabled `colors.border` fill is the exact bug the
              playbook documents from app/subscription.tsx — in high-contrast
              dark accentText is #000000, in light it is #ffffff, and neither is
              readable on a border-coloured button. Disabled uses muted-on-card
              instead, matching btnGhost. */}
          <AnimatedPressable
            onPress={saveTracking}
            disabled={!canSaveTracking}
            style={[
              styles.btn,
              styles.sheetSave,
              canSaveTracking
                ? { backgroundColor: colors.accent }
                : { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
            ]}
            accessibilityRole="button"
            accessibilityState={{ disabled: !canSaveTracking }}
            accessibilityLabel="Save tracking details"
          >
            <Text style={[styles.btnText, { color: canSaveTracking ? colors.accentText : colors.muted }]}>
              Save tracking
            </Text>
          </AnimatedPressable>
        </ScrollView>
      </BottomSheetModal>

      {/* Seller side of the negotiation. Same component as the buyer's, so the
          two ladders cannot drift apart. */}
      {counterFor ? (
        <OfferAmountSheet
          visible={counterFor !== null}
          onClose={() => setCounterFor(null)}
          title="Counter offer"
          reference={counterFor.listing_price ?? counterFor.amount}
          referenceLabel={counterFor.listing_price != null ? 'Asking' : 'Their offer'}
          currency={settings.currency}
          numberLocale={settings.numberLocale}
          submitLabel="Send counter"
          busy={busyId === counterFor.id}
          colors={colors}
          hapticsEnabled={settings.hapticsEnabled}
          onSubmit={submitCounter}
        />
      ) : null}

      <QuickNavBar />
    </View>
  );
}

export default function OffersScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Offers">
      <OffersScreen />
    </ScreenErrorBoundary>
  );
}

/*
 * TYPE SCALE (revised 2026-08-11) — three levels, not one.
 *
 * The 2026-08-09 pass fixed "that screen is very small letters" by moving every
 * style one step UP the scale. That cured the unreadability and replaced it with
 * the opposite defect: 12 of 17 text styles landed on `md` (14), so the status
 * line, the role pill, the confirm ticks, the tracking caption, the sheet hints,
 * every button label and the view link all rendered at the same size as the body
 * copy. Nothing receded, so nothing led — a card with no hierarchy reads as
 * unfinished no matter how correct its content is, and next to `/listings`
 * (card title 12, meta 10) and `/listing/[id]` (title 20, body 14, meta 10) the
 * screen visibly did not belong to the same app.
 *
 * The fix is NOT to undo the bump. `xs` (10) stays banned for anything a user
 * reads — that rule was written from Merle's own report and it still holds. The
 * floor here is `sm` (12), and hierarchy is rebuilt by pushing the two things
 * that matter UP rather than pushing everything else down:
 *
 *   lead    lg (16)  the amount (extrabold) · the listing title, the tracking CODE
 *   body    md (14)  status, the buyer's message, buttons, links, sheet copy
 *   caption sm (12)  role pill, confirm ticks, captions, passive notes
 *
 * Two outright bugs went with it:
 *  - `trackHint` was `fontSize: 14` with `lineHeight: 15` on a deliberately
 *    two-line string ("Search this code\non the carrier's site"), so the lines
 *    collided. A lineHeight below its own fontSize is never intentional.
 *  - the carrier field rendered at 14 while the tracking input directly below it
 *    rendered at 16 — two controls in one form, two sizes, for no reason.
 *
 * Every line-height here is >= 1.35x its font size; the tightest sibling
 * (`listing/[id].tsx` body) is 14/21.
 */
const styles = StyleSheet.create({
  safe: { flex: 1 },
  pad: { padding: 16 },
  loadingText: { fontSize: textToken.md },
  segmentWrap: { paddingHorizontal: 16, paddingTop: 8 },
  segment: {
    flexDirection: 'row', borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.pill, padding: 3, marginBottom: 12,
  },
  segmentBtn: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: radius.pill },
  segmentText: { fontSize: textToken.md, fontWeight: fontWeight.semibold },
  list: { paddingHorizontal: 16, paddingTop: 2 },
  // More room and a softer corner: at 14pt padding with 8pt gaps the card read
  // as a dense list row rather than a document about one negotiation. The
  // shadow is the same token the marketplace tiles use, so the two screens
  // belong to each other.
  card: {
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.lg,
    padding: 16, marginBottom: 12, gap: 10,
    ...shadow.card,
  },
  rowTop: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  title: { flex: 1, fontSize: textToken.lg, fontWeight: fontWeight.semibold, lineHeight: 22 },
  // `lg`, not `xl` (2026-08-11). At 20/extrabold the figure dominated the card
  // — reported as "the numbers are too big" — and with the percentage line now
  // sitting under it the amount no longer has to carry the comparison alone.
  // Still the lead: nothing else on the card is 16/extrabold.
  amount: { fontSize: textToken.lg, fontWeight: fontWeight.extrabold, letterSpacing: -0.2 },
  // Caption level: it qualifies the amount above it, it does not compete.
  amountDelta: { fontSize: textToken.sm, marginTop: 1 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  // A pill is a LABEL beside body text, not body text. At md/bold it was the
  // same size as the status it sits next to and competed with the title; `pill`
  // radius matches the segmented control at the top of the same screen, where
  // `radius.xs` (6) read as a stray rounded rectangle.
  rolePill: { paddingHorizontal: 9, paddingVertical: 3, borderRadius: radius.pill },
  rolePillText: { fontSize: textToken.sm, fontWeight: fontWeight.bold, letterSpacing: 0.3 },
  status: { fontSize: textToken.md, fontWeight: fontWeight.medium, flexShrink: 1 },
  message: { fontSize: textToken.md, fontStyle: 'italic', lineHeight: 20 },
  confirmRow: { flexDirection: 'row', alignItems: 'center', gap: 5, flexWrap: 'wrap' },
  confirmText: { fontSize: textToken.sm, lineHeight: 17, marginRight: 8 },
  // Right-aligned and divided off the body. Actions floating left under a
  // paragraph read as more content; on the right of a ruled row they read as
  // the decision. Empty rows collapse — `gap` on an empty View adds nothing.
  actions: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8,
    justifyContent: 'flex-end', alignItems: 'center',
    marginTop: 2,
  },
  btn: { minHeight: 38, justifyContent: 'center', paddingHorizontal: 16, paddingVertical: 9, borderRadius: radius.md },
  btnGhost: { borderWidth: 1, backgroundColor: 'transparent' },
  // No border and no fill: the third action should read as the way out, not as
  // a third equal choice. Accept fills, Counter outlines, Decline recedes.
  btnQuiet: { backgroundColor: 'transparent' },
  btnText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  graded: { fontSize: textToken.sm, paddingVertical: 9 },
  // Tracking — display-only shipment reference on the card.
  tracking: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm,
    paddingHorizontal: 10, paddingVertical: 9, marginTop: 8,
  },
  trackingLabel: { fontSize: textToken.sm, lineHeight: 16 },
  // The code is what a seller reads back and a buyer copies, so it leads its
  // block — it was the same 14 as its own caption.
  trackingCode: { fontSize: textToken.lg, fontWeight: fontWeight.semibold, letterSpacing: 0.4 },
  trackLink: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  trackHint: { fontSize: textToken.sm, textAlign: 'right', lineHeight: 16 },
  // Tracking capture sheet.
  sheet: { padding: 16, paddingBottom: 32, gap: 10 },
  sheetHint: { fontSize: textToken.md, lineHeight: 20 },
  // Field captions, so the field VALUE below leads. Uppercase + tracking is the
  // form-label treatment; at md/semibold the label outweighed its own field.
  sheetLabel: {
    fontSize: textToken.sm, fontWeight: fontWeight.bold,
    textTransform: 'uppercase', letterSpacing: 0.6, marginTop: 8,
  },
  // (carrierWrap/carrierChip/carrierChipText removed with the chip grid)
  field: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    borderWidth: 1, borderRadius: radius.sm,
    paddingHorizontal: 12, paddingVertical: 13,
  },
  // Matches `input` below — one form, one control size.
  fieldText: { fontSize: textToken.lg },
  carrierError: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
  input: {
    borderWidth: 1, borderRadius: radius.sm,
    paddingHorizontal: 12, paddingVertical: 13, fontSize: textToken.lg,
  },
  sheetSave: { marginTop: 8, alignItems: 'center', paddingVertical: 13 },
  viewLink: { fontSize: textToken.md, fontWeight: fontWeight.bold, marginTop: 2 },
});
