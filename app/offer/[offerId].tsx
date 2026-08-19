/**
 * Trade screen — one offer, and every step of finishing it, in order.
 *
 * WHY THIS EXISTS
 * Reported 2026-08-19: *"if you press on the bids/offers then it goes straight
 * to the item listing. this is not what you need to edit/manage… it needs to be
 * one seamless flow."* Exactly right. Every capability existed — respond,
 * settle up, address, carriage, tracking, two-sided confirm, rating — but they
 * were buttons and sheets scattered across a list card, in no stated order,
 * and tapping the card navigated AWAY to the listing. Nothing owned a trade.
 *
 * This screen owns it. The list becomes a way in; the listing becomes a link
 * out at the bottom.
 *
 * ⚠️ THE STATE MACHINE IS STILL THE SERVER'S.
 * `can_confirm`, `can_grade`, `already_graded`, `can_add_tracking` and
 * `superseded` are computed in `p2p_offers_router.py` and rendered here as
 * given — the same rule `app/offers.tsx` opens with. That is what makes it safe
 * for both screens to carry actions: they are two VIEWS of one machine, not two
 * machines. The step ladder below derives only PRESENTATION (done / now /
 * later) from those flags, and never decides what is legal.
 *
 * WHY A LADDER RATHER THAN A PILE OF BUTTONS
 * The trade is genuinely sequential — you cannot ship before it is accepted or
 * rate before it completes — and the old card showed whichever buttons happened
 * to be legal with no indication of what came next. Naming all five steps and
 * marking where you are turns "what do I do now" into a glance. Steps behind
 * you stay visible and ticked, because "did I already confirm?" is a real
 * question a member asks.
 *
 * ⚠️ PUSHES STILL DEEP-LINK TO `/offers?offerId=…`, NOT HERE.
 * §5e's deploy-order trap: the server ships in minutes and an app build takes a
 * day, so repointing `_notify_trade` before the build carrying this route is
 * live would land every trade push on a route that does not exist. The list
 * still highlights the pushed card. Repoint in the deploy AFTER this ships.
 */
import React, { useCallback, useMemo, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Image, Alert, ActivityIndicator, Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { AnimatedPressable, useEnterReveal } from '@/motion';
import { QuickNavBar } from '@/components/QuickNavBar';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { OfferAmountSheet } from '@/components/p2p/OfferAmountSheet';
import { SettleUpSheet } from '@/components/p2p/SettleUpSheet';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useAsync } from '@/hooks/useAsync';
import { useToast } from '@/components/Toast';
import { fireHaptic, HapticIntent } from '@/haptics';
import { formatPrice } from '@/lib/format';
import { timeAgo } from '@/lib/timeAgo';
import { collectorsApi } from '@/api/collectorsApi';
import { offerNeedsMyAction, type P2POffer } from '@/api/p2pApi';
import { radius, text as textToken, fontWeight, shadow } from '@/theme/tokens';
import logger from '@/utils/logger';

/** Must match `MAX_COUNTERS` in the server router — see app/offers.tsx. */
const MAX_COUNTERS = 5;

type StepState = 'done' | 'now' | 'later';

function TradeScreen() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const router = useRouter();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { offerId } = useLocalSearchParams<{ offerId?: string }>();

  const [busy, setBusy] = useState(false);
  const [counterOpen, setCounterOpen] = useState(false);
  const [settleOpen, setSettleOpen] = useState(false);

  const { data: offer, loading, error, retry } = useAsync(
    async () => (offerId ? await collectorsApi.p2pGetOffer(String(offerId)) : null),
    [offerId],
  );

  /**
   * Run an action, then RELOAD from the server.
   *
   * Never patches the offer locally from the response: `can_confirm` and
   * friends are server-computed, and a locally-merged object would be the
   * moment this screen started deciding what is legal.
   */
  const act = useCallback(async (fn: () => Promise<unknown>, successMsg?: string) => {
    setBusy(true);
    try {
      await fn();
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      if (successMsg) showToast({ message: successMsg, type: 'success' });
      await retry();
    } catch (e: unknown) {
      // Surface the server's sentence: 409s here are meaningful states
      // ("This offer has been countered 5 times", "Offer is already declined"),
      // not noise, and a generic message would hide the reason.
      logger.error('[trade] action failed:', e);
      showToast({ message: (e as Error)?.message || 'That didn’t work', type: 'error' });
    } finally {
      setBusy(false);
    }
  }, [retry, settings.hapticsEnabled, showToast]);

  const confirmDecline = useCallback((o: P2POffer) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    Alert.alert(
      'Decline this offer?',
      'The buyer will be told. They can send a new offer, but this one is gone.',
      [
        { text: 'Keep it', style: 'cancel' },
        {
          text: 'Decline',
          style: 'destructive',
          onPress: () => act(() => collectorsApi.p2pRespondToOffer(o.id, 'decline'), 'Declined'),
        },
      ],
    );
  }, [act, settings.hapticsEnabled]);

  /**
   * The five steps, and where the trade is.
   *
   * PRESENTATION ONLY — every `now` is gated on a server flag, never on a rule
   * re-derived here.
   */
  const steps = useMemo(() => {
    if (!offer) return [];
    const open = offer.status === 'pending' || offer.status === 'countered';
    const live = offer.status === 'accepted' || offer.status === 'shipped';
    const done = offer.status === 'completed';
    const dead = !open && !live && !done;   // declined / cancelled / expired
    const mine = offerNeedsMyAction(offer);

    const state = (isDone: boolean, isNow: boolean): StepState =>
      isDone ? 'done' : isNow ? 'now' : 'later';

    return [
      {
        key: 'respond',
        title: 'Respond',
        // A dead trade never got past step 1, and marking it "done" would read
        // as progress. It is shown as the step that ended.
        state: state(live || done, open && mine && !offer.superseded),
        detail: dead
          ? 'This trade ended here.'
          : open
            ? (mine ? 'Your call.' : 'Waiting on them.')
            : 'Agreed.',
      },
      {
        key: 'settle',
        title: offer.i_am_buyer ? 'Pay the seller' : 'Book the parcel',
        state: state(done || offer.status === 'shipped', live),
        detail: offer.i_am_buyer
          ? 'Pay in your own app, and give the seller a delivery address.'
          : 'Book carriage in your own name and see where it goes.',
      },
      {
        key: 'ship',
        title: 'Add tracking',
        state: state(!!offer.tracking_code, !!offer.can_add_tracking && !offer.tracking_code),
        detail: offer.tracking_code
          ? `${offer.tracking_carrier_label ?? 'Carrier'} · ${offer.tracking_code}`
          : offer.i_am_buyer
            ? 'The seller adds this so you can follow the parcel.'
            : 'Optional. It does not complete the trade.',
      },
      {
        key: 'confirm',
        title: offer.i_am_buyer ? 'Confirm you received it' : 'Confirm you sent it',
        state: state(
          offer.i_am_buyer ? !!offer.buyer_confirmed_at : !!offer.seller_confirmed_at,
          !!offer.can_confirm,
        ),
        detail: 'Both sides confirm. That is what completes the trade.',
      },
      {
        key: 'rate',
        title: offer.i_am_buyer ? 'Rate the seller' : 'Rate the buyer',
        state: state(!!offer.already_graded, !!offer.can_grade && !offer.already_graded),
        detail: offer.already_graded
          ? 'Thanks — your rating is on their profile.'
          : 'Unlocks once you have both confirmed.',
      },
    ];
  }, [offer]);

  const openListing = useCallback(() => {
    if (!offer) return;
    router.push({ pathname: '/listing/[id]', params: { id: offer.listing_id } } as unknown as Href);
  }, [offer, router]);

  // ── states ───────────────────────────────────────────────────────────────
  if (loading && !offer) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.centered}>
          <ActivityIndicator color={colors.accent} />
          <Text style={[styles.muted, { color: colors.muted }]}>Loading this trade…</Text>
        </View>
        <QuickNavBar />
      </SafeAreaView>
    );
  }

  // A failed load and a missing trade are DIFFERENT facts and must not render
  // as each other: one deserves a retry, the other does not.
  if (error || !offer) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={44} color={colors.muted} />
          <Text style={[styles.errTitle, { color: colors.text }]}>
            {error ? 'Couldn’t load this trade' : 'Trade not found'}
          </Text>
          <Text style={[styles.muted, { color: colors.muted }]}>
            {error
              ? 'Check your connection and try again.'
              : 'It may have been removed, or it is not yours.'}
          </Text>
          {error ? (
            <AnimatedPressable
              onPress={retry}
              style={[styles.btn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Try again"
            >
              <Text style={[styles.btnText, { color: colors.accentText }]}>Try again</Text>
            </AnimatedPressable>
          ) : null}
        </View>
        <QuickNavBar />
      </SafeAreaView>
    );
  }

  const open = offer.status === 'pending' || offer.status === 'countered';
  const isSeller = !offer.i_am_buyer;
  const pct = typeof offer.listing_price === 'number' && offer.listing_price > 0
    ? Math.round(((offer.amount - offer.listing_price) / offer.listing_price) * 100)
    : null;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>

          {/* WHAT is being traded, and for how much. */}
          <View style={[styles.head, { backgroundColor: colors.card, borderColor: colors.border }]}>
            {offer.listing_image_url ? (
              <Image source={{ uri: offer.listing_image_url }} style={styles.thumb} />
            ) : (
              <View style={[styles.thumb, styles.thumbEmpty, { backgroundColor: colors.accent + '12' }]}>
                <Ionicons name="pricetag-outline" size={22} color={colors.muted} />
              </View>
            )}
            <View style={{ flex: 1, gap: 3 }}>
              <Text style={[styles.title, { color: colors.text }]} numberOfLines={2}>
                {offer.listing_title || 'Listing'}
              </Text>
              <Text style={[styles.amount, { color: colors.text }]}>
                {formatPrice(offer.amount, settings.currency, settings.numberLocale)}
                {/* Only against a stated asking price — a bare percentage off
                    an unstated basis is a number nobody can check. */}
                {pct !== null ? (
                  <Text style={[styles.amountSub, { color: colors.muted }]}>
                    {'  '}{pct > 0 ? '+' : ''}{pct}% of asking
                  </Text>
                ) : null}
              </Text>
              <View style={styles.metaRow}>
                <View style={[
                  styles.rolePill,
                  { backgroundColor: offer.i_am_buyer ? colors.infoBg : colors.successBg },
                ]}>
                  <Text style={[
                    styles.rolePillText,
                    { color: offer.i_am_buyer ? colors.info : colors.success },
                  ]}>
                    {offer.i_am_buyer ? 'You buy' : 'You sell'}
                  </Text>
                </View>
                <Text style={[styles.meta, { color: colors.muted }]}>
                  {offer.counter_count > 1 ? `${offer.counter_count} rounds · ` : ''}
                  {offer.updated_at || offer.created_at
                    ? timeAgo((offer.updated_at || offer.created_at)!)
                    : ''}
                </Text>
              </View>
            </View>
          </View>

          {/* The rival-bid case, stated once at the top: §1d keeps these alive
              on purpose, so the controls below stay usable. */}
          {offer.superseded ? (
            <View style={[styles.notice, { backgroundColor: colors.border + '55' }]}>
              <Ionicons name="information-circle-outline" size={15} color={colors.muted} />
              <Text style={[styles.noticeText, { color: colors.muted }]}>
                {offer.i_am_buyer
                  ? 'The seller accepted a different bid. Yours is still open if that falls through.'
                  : 'You accepted another bid on this listing. This one is still here as a fallback.'}
              </Text>
            </View>
          ) : null}

          {offer.message ? (
            <Text style={[styles.quote, { color: colors.muted }]}>“{offer.message}”</Text>
          ) : null}

          {/* ── THE LADDER ───────────────────────────────────────────────── */}
          {steps.map((s, i) => (
            <View
              key={s.key}
              style={[
                styles.step,
                { borderColor: s.state === 'now' ? colors.accent : colors.border },
                s.state === 'now' && { backgroundColor: colors.card, ...shadow.card },
                s.state === 'later' && styles.stepLater,
              ]}
            >
              <View style={styles.stepHead}>
                <View style={[
                  styles.stepNum,
                  {
                    backgroundColor: s.state === 'done'
                      ? colors.success
                      : s.state === 'now' ? colors.accent : 'transparent',
                    borderColor: s.state === 'later' ? colors.border : 'transparent',
                  },
                ]}>
                  {s.state === 'done' ? (
                    <Ionicons name="checkmark" size={13} color={colors.accentText} />
                  ) : (
                    <Text style={[
                      styles.stepNumText,
                      { color: s.state === 'now' ? colors.accentText : colors.muted },
                    ]}>{i + 1}</Text>
                  )}
                </View>
                <Text style={[styles.stepTitle, { color: colors.text }]}>{s.title}</Text>
              </View>
              <Text style={[styles.stepDetail, { color: colors.muted }]}>{s.detail}</Text>

              {/* Actions belong to the step that owns them, and appear only
                  when the SERVER says they are legal. */}
              {s.key === 'respond' && s.state === 'now' ? (
                <View style={styles.actions}>
                  <AnimatedPressable
                    onPress={() => act(
                      () => collectorsApi.p2pRespondToOffer(offer.id, 'accept'),
                      offer.i_am_buyer ? 'Bid accepted' : 'Offer accepted',
                    )}
                    disabled={busy}
                    style={[styles.btn, { backgroundColor: colors.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel="Accept this offer"
                  >
                    <Text style={[styles.btnText, { color: colors.accentText }]}>Accept</Text>
                  </AnimatedPressable>

                  {/* Countering is the SELLER's move only (§1d-bis: whoever did
                      not set the current number answers it), and it disappears
                      at the cap because the server returns 409 there. */}
                  {isSeller && offer.counter_count < MAX_COUNTERS ? (
                    <AnimatedPressable
                      onPress={() => setCounterOpen(true)}
                      disabled={busy}
                      style={[styles.btn, styles.btnGhost, { borderColor: colors.accent }]}
                      accessibilityRole="button"
                      accessibilityLabel="Counter this offer"
                    >
                      <Text style={[styles.btnText, { color: colors.accent }]}>Counter</Text>
                    </AnimatedPressable>
                  ) : null}

                  <AnimatedPressable
                    onPress={() => confirmDecline(offer)}
                    disabled={busy}
                    style={[styles.btn, styles.btnQuiet]}
                    accessibilityRole="button"
                    accessibilityLabel="Decline this offer"
                  >
                    <Text style={[styles.btnText, { color: colors.danger }]}>Decline</Text>
                  </AnimatedPressable>
                </View>
              ) : null}

              {s.key === 'respond' && isSeller && open && offer.counter_count >= MAX_COUNTERS ? (
                <Text style={[styles.capNote, { color: colors.muted }]}>
                  Countered {MAX_COUNTERS} times — accept it or decline it.
                </Text>
              ) : null}

              {s.key === 'settle' && s.state === 'now' ? (
                <View style={styles.actions}>
                  <AnimatedPressable
                    onPress={() => setSettleOpen(true)}
                    style={[styles.btn, { backgroundColor: colors.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel={offer.i_am_buyer ? 'Pay the seller' : 'Book the parcel'}
                  >
                    <Text style={[styles.btnText, { color: colors.accentText }]}>
                      {offer.i_am_buyer ? 'Pay & send address' : 'Ship it'}
                    </Text>
                  </AnimatedPressable>
                </View>
              ) : null}

              {/* Tracking capture stays on the offers LIST, which owns the
                  carrier sheet. Linking to it beats a second copy of that
                  sheet here — one picker, one place it can go wrong. */}
              {s.key === 'ship' && s.state === 'now' ? (
                <View style={styles.actions}>
                  <AnimatedPressable
                    onPress={() => router.push(`/offers?offerId=${encodeURIComponent(offer.id)}` as Href)}
                    style={[styles.btn, styles.btnGhost, { borderColor: colors.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel="Add tracking for this parcel"
                  >
                    <Text style={[styles.btnText, { color: colors.accent }]}>Add tracking</Text>
                  </AnimatedPressable>
                </View>
              ) : null}

              {s.key === 'confirm' && s.state === 'now' ? (
                <View style={styles.actions}>
                  <AnimatedPressable
                    onPress={() => act(
                      () => collectorsApi.p2pConfirmExchange(offer.id),
                      offer.i_am_buyer ? 'Marked received' : 'Marked sent',
                    )}
                    disabled={busy}
                    style={[styles.btn, { backgroundColor: colors.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel={offer.i_am_buyer ? 'Confirm you received it' : 'Confirm you sent it'}
                  >
                    <Text style={[styles.btnText, { color: colors.accentText }]}>
                      {offer.i_am_buyer ? 'I received it' : 'I sent it'}
                    </Text>
                  </AnimatedPressable>
                </View>
              ) : null}

              {/* Both ticks, on the step that explains them. */}
              {s.key === 'confirm' && (offer.seller_confirmed_at || offer.buyer_confirmed_at) ? (
                <View style={styles.confirmRow}>
                  <Ionicons
                    name={offer.seller_confirmed_at ? 'checkmark-circle' : 'ellipse-outline'}
                    size={14}
                    color={offer.seller_confirmed_at ? colors.accent : colors.muted}
                  />
                  <Text style={[styles.confirmText, { color: colors.muted }]}>Seller sent</Text>
                  <Ionicons
                    name={offer.buyer_confirmed_at ? 'checkmark-circle' : 'ellipse-outline'}
                    size={14}
                    color={offer.buyer_confirmed_at ? colors.accent : colors.muted}
                  />
                  <Text style={[styles.confirmText, { color: colors.muted }]}>Buyer received</Text>
                </View>
              ) : null}

              {s.key === 'rate' && s.state === 'now' ? (
                <View style={styles.actions}>
                  <AnimatedPressable
                    onPress={() => router.push(`/offers?offerId=${encodeURIComponent(offer.id)}` as Href)}
                    style={[styles.btn, { backgroundColor: colors.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel={offer.i_am_buyer ? 'Rate the seller' : 'Rate the buyer'}
                  >
                    <Text style={[styles.btnText, { color: colors.accentText }]}>
                      {offer.i_am_buyer ? 'Rate the seller' : 'Rate the buyer'}
                    </Text>
                  </AnimatedPressable>
                </View>
              ) : null}
            </View>
          ))}

          {busy ? (
            <View style={styles.working}>
              <ActivityIndicator size="small" color={colors.accent} />
              <Text style={[styles.muted, { color: colors.muted }]}>Working…</Text>
            </View>
          ) : null}

          {/* The listing is a link OUT of the trade, not the destination of
              tapping one. This is the swap the whole screen exists for. */}
          <AnimatedPressable
            onPress={openListing}
            style={[styles.listingLink, { borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel="View the listing this trade is for"
          >
            <Ionicons name="open-outline" size={16} color={colors.accent} />
            <Text style={[styles.listingLinkText, { color: colors.accent }]}>View listing</Text>
          </AnimatedPressable>
        </Animated.View>
      </ScrollView>

      {/* Same props the offers list passes — the presets are a percentage of
          the ASKING price, never of the buyer's own offer (§10d), and
          `referenceLabel` says which basis is in use when the listing price is
          missing. */}
      <OfferAmountSheet
        visible={counterOpen}
        onClose={() => setCounterOpen(false)}
        title="Counter offer"
        reference={offer.listing_price ?? offer.amount}
        referenceLabel={offer.listing_price != null ? 'Asking' : 'Their offer'}
        currency={settings.currency}
        numberLocale={settings.numberLocale}
        submitLabel="Send counter"
        busy={busy}
        colors={colors}
        hapticsEnabled={settings.hapticsEnabled}
        onSubmit={async (amount: number) => {
          setCounterOpen(false);
          await act(
            () => collectorsApi.p2pRespondToOffer(offer.id, 'counter', amount),
            'Counter sent',
          );
        }}
      />

      <SettleUpSheet
        visible={settleOpen}
        onClose={() => setSettleOpen(false)}
        mode={offer.i_am_buyer ? 'pay' : 'ship'}
        isBuyer={offer.i_am_buyer}
        amountLabel={formatPrice(offer.amount, settings.currency, settings.numberLocale)}
        offerId={offer.id}
        colors={colors}
      />

      {/* QuickNavBar reserves its own space (normal flex row, not absolute), so
          this needs no inset — see ui-playbook, "The newest screens keep
          shipping without the nav bar". */}
      <QuickNavBar />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: 16, paddingBottom: 24 },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10, padding: 24 },
  errTitle: { fontSize: textToken.lg, fontWeight: fontWeight.bold },
  muted: { fontSize: textToken.md, textAlign: 'center' },

  head: {
    flexDirection: 'row', gap: 12, padding: 12,
    borderRadius: radius.lg, borderWidth: StyleSheet.hairlineWidth,
    ...shadow.card,
  },
  thumb: { width: 64, height: 64, borderRadius: radius.sm },
  thumbEmpty: { alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: textToken.lg, fontWeight: fontWeight.semibold, lineHeight: 22 },
  amount: { fontSize: textToken.xl, fontWeight: fontWeight.bold },
  amountSub: { fontSize: textToken.sm, fontWeight: fontWeight.medium },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  meta: { fontSize: textToken.sm },
  rolePill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill },
  rolePillText: { fontSize: textToken.sm, fontWeight: fontWeight.bold, letterSpacing: 0.3 },

  notice: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 7,
    padding: 10, borderRadius: radius.md, marginTop: 12,
  },
  noticeText: { flex: 1, fontSize: textToken.sm, lineHeight: 17 },
  quote: { fontSize: textToken.md, lineHeight: 20, marginTop: 12, fontStyle: 'italic' },

  step: {
    marginTop: 12, padding: 12,
    borderRadius: radius.lg, borderWidth: StyleSheet.hairlineWidth,
    gap: 6,
  },
  // Steps you cannot reach yet recede but stay READABLE — "what comes next"
  // is the question the ladder exists to answer, so hiding them would defeat
  // it. De-emphasis, not a disabled state.
  stepLater: { opacity: 0.55 },
  stepHead: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  stepNum: {
    width: 21, height: 21, borderRadius: 11, borderWidth: 1,
    alignItems: 'center', justifyContent: 'center',
  },
  stepNumText: { fontSize: textToken.sm, fontWeight: fontWeight.bold },
  stepTitle: { flex: 1, fontSize: textToken.md, fontWeight: fontWeight.semibold },
  stepDetail: { fontSize: textToken.sm, lineHeight: 17 },
  capNote: { fontSize: textToken.sm, lineHeight: 17 },

  // `nowrap` with shrinking buttons — a wrapped third button reads as a
  // separate decision (ui-playbook, 2026-08-15).
  actions: {
    flexDirection: 'row', flexWrap: 'nowrap', gap: 8,
    alignItems: 'center', marginTop: 4,
  },
  btn: {
    flexShrink: 1, minHeight: 40, paddingHorizontal: 14,
    alignItems: 'center', justifyContent: 'center', borderRadius: radius.md,
  },
  btnGhost: { borderWidth: 1 },
  btnQuiet: { paddingHorizontal: 10 },
  btnText: { fontSize: textToken.md, fontWeight: fontWeight.semibold, textAlign: 'center' },

  confirmRow: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginTop: 2 },
  confirmText: { fontSize: textToken.sm, marginRight: 6 },
  working: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12, justifyContent: 'center' },

  listingLink: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7,
    marginTop: 18, paddingVertical: 12,
    borderRadius: radius.md, borderWidth: StyleSheet.hairlineWidth,
  },
  listingLinkText: { fontSize: textToken.md, fontWeight: fontWeight.semibold },
});

export default function TradeScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Trade">
      <TradeScreen />
    </ScreenErrorBoundary>
  );
}
