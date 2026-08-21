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
  View, Text, SectionList, StyleSheet, RefreshControl, Alert, Animated,
  Linking, TextInput, ScrollView, ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';

import ScreenHeader from '@/components/ScreenHeader';
import { BottomSheetModal } from '@/components/BottomSheetModal';
import { OfferAmountSheet } from '@/components/p2p/OfferAmountSheet';
import { QuickNavBar } from '@/components/QuickNavBar';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { EmptyState } from '@/components/EmptyState';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { SwipeableRow } from '@/components/SwipeableRow';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useTabBarInset } from '@/hooks/useTabBarInset';
import { useAsync } from '@/hooks/useAsync';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { showActionSheet } from '@/hooks/useActionSheetPicker';
import { formatPrice } from '@/lib/format';
import { collectorsApi } from '@/api/collectorsApi';
import { offerNeedsMyAction, type P2POffer, type P2PCarrier } from '@/api/p2pApi';
import { timeAgo } from '@/lib/timeAgo';
import { groupCompetingOffers } from '@/lib/offerGrouping';
import { radius, text as textToken, fontWeight, shadow } from '@/theme/tokens';
import logger from '@/utils/logger';

type Role = 'all' | 'buying' | 'selling';

/**
 * When a bid waiting on YOU starts being called out as old.
 *
 * Three days, not one: a hobby marketplace is not a trading desk, and a bid
 * that arrived on Friday should not be shamed on Saturday. Not a deadline —
 * nothing expires — just the point at which "somebody is still waiting" is
 * worth saying out loud.
 */
const STALE_AFTER_DAYS = 3;

/**
 * How many times one offer may be countered. MUST match `MAX_COUNTERS` in
 * server/app/features/p2p_offers_router.py — the server is the enforcer and
 * returns 409 `COUNTER_LIMIT`; this only decides whether to render a button
 * that is going to be refused. A client that offers a control the server will
 * reject is the dead-button failure Stage 1 bug 0 was fixed to avoid.
 */
const MAX_COUNTERS = 5;

/**
 * Status → what it means TO YOU. Keys mirror p2p_offers_status_check.
 *
 * Every label is written from the reader's side of the trade, because the same
 * status means opposite things to the two people looking at it: `countered` is
 * "your call" to one of them and "waiting on them" to the other, and a single
 * neutral word ("Countered") made the member work that out from the role pill.
 * Reported as *"'countered, 1 counter' is just not very easy to follow"*.
 *
 * The spec's original wording is in docs/P2P_MARKETPLACE_SPEC.md §1d-bis; that
 * table has been updated alongside this, so the doc and the screen still agree.
 */
function statusLabel(status: string, iAmBuyer: boolean, iWithdrew?: boolean | null): string {
  switch (status) {
    case 'pending':
      return iAmBuyer ? 'Waiting for the seller to reply' : 'Waiting for your reply';
    case 'countered':
      // The counter always travels toward the other party, so whoever is NOT
      // the one who sent it is the one who has to answer.
      return iAmBuyer ? 'Seller countered — your call' : 'You countered — waiting on the buyer';
    case 'accepted':
      // "Agreed — arrange the exchange" left both sides asking what "arrange"
      // meant. Sparrow handles neither payment nor delivery (§5a), so the
      // honest version of this status is the instruction itself.
      return iAmBuyer
        ? 'Agreed — pay the seller and share your address'
        : 'Agreed — take payment, then send the item';
    case 'shipped':
      return iAmBuyer ? 'On its way — confirm when it arrives' : 'You marked it sent';
    case 'completed':
      return 'Trade complete';
    case 'declined':
      return iAmBuyer ? 'Seller declined' : 'You declined';
    case 'cancelled':
      // EITHER side may withdraw — a seller can retract a counter — so the
      // actor cannot be inferred from your role. `i_withdrew` is server-derived
      // from `withdrawn_by`; when it is absent (an older build) say only what
      // is certainly true rather than guessing an actor.
      // `== null`, NOT `=== undefined`. The server sends JSON `null` for "no
      // one is recorded as having walked", which arrives as `null` and is
      // falsy — so a `=== undefined` check fell straight through to the else
      // and asserted "the other side withdrew" on precisely the unknown case
      // this branch exists to protect.
      if (iWithdrew == null) return 'Withdrawn';
      return iWithdrew ? 'You withdrew this' : 'The other side withdrew';
    case 'expired':
      return 'Expired';
    default:
      return status;
  }
}

function OffersScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const bottomInset = useTabBarInset();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  /**
   * The offer a push was about.
   *
   * Every trade notification deep-links to `/offers?offerId=<id>` rather than
   * to this screen bare — being told "rate your trade" and handed a list of
   * six is a search task, not a link. The param is READ here and used twice
   * below: the card is highlighted, and if the push was the rating ask, the
   * rating prompt opens on arrival.
   *
   * `npm run check:params` compares a push target against the params the
   * destination FILE declares, so this line is what makes that contract
   * checkable — a param nothing reads is silently dropped and legal TS
   * (learning_route_params_are_an_unchecked_contract).
   */
  const { offerId: deepLinkOfferId, action: deepLinkAction } =
    useLocalSearchParams<{ offerId?: string; action?: string }>();

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
    async () => {
      const res = await collectorsApi.p2pListOffers(role);
      return { offers: res?.offers ?? [], total: res?.total };
    },
    [role],
  );
  // Ordered, not raw. `/listings` badges the same count on its "Open bids" pill
  // and this is the screen that pill opens — it used to hand over an undifferentiated list, so
  // the user was told a number and then had to read every card's status line to
  // find which ones it meant. `offerNeedsMyAction` is the SAME helper the badge
  // counts with (src/api/p2pApi.ts), deliberately, so the two cannot disagree
  // about what "needs you" means.
  //
  // Four ranks: your move → live trade → waiting on them → finished. Newest
  // first inside a rank; a null `created_at` sorts last rather than throwing
  // the order away.
  const offers = useMemo(() => {
    const rank = (o: P2POffer) => {
      if (offerNeedsMyAction(o)) return 0;
      if (o.status === 'accepted' || o.status === 'shipped') return 1;
      if (o.status === 'pending' || o.status === 'countered') return 2;
      return 3;
    };
    // Last ACTIVITY, matching the date the card prints. Sorting on
    // `created_at` while displaying `updated_at` puts a card dated "2 hours
    // ago" underneath one dated "3 weeks ago" and looks like a broken sort.
    const at = (o: P2POffer) =>
      (o.updated_at || o.created_at) ? Date.parse((o.updated_at || o.created_at)!) : 0;
    return [...(data?.offers ?? [])].sort((a, b) => rank(a) - rank(b) || at(b) - at(a));
  }, [data]);

  /**
   * How many offers the server holds that this page could not show.
   *
   * The client used to send no limit at all, so the server applied its own
   * default of 50 and returned the 50 NEWEST — and said nothing. A truncation
   * that reads as completeness is the worst kind: "needs you" includes
   * ungraded completed trades, which are old by construction, so the row most
   * likely to fall off the bottom is one that still wants something from you.
   * The request now asks for the server's ceiling and the screen states the
   * shortfall rather than implying there isn't one.
   */
  const hiddenCount = useMemo(() => {
    const total = data?.total;
    if (typeof total !== 'number') return 0;   // older server build: claim nothing
    return Math.max(0, total - offers.length);
  }, [data, offers.length]);

  const needsAction = useMemo(
    () => offers.reduce((n, o) => (offerNeedsMyAction(o) ? n + 1 : n), 0),
    [offers],
  );

  /**
   * Three sections instead of one flat list.
   *
   * The ranking has been correct since 2026-08-13 — your move first, then live
   * trades, then finished — but it was INVISIBLE: five cards in a row with no
   * boundary between "act on this now" and "this ended a week ago". Testers
   * read it as an undifferentiated list, which is exactly what it looked like.
   *
   * Material's rule for lists is to organise by priority and label the groups;
   * Kalshi's blotter does the same thing for resting orders. The headers do the
   * work the sort order alone could not.
   */
  const { sections, groupMeta } = useMemo(() => {
    const mine: P2POffer[] = [];
    const live: P2POffer[] = [];
    const done: P2POffer[] = [];
    for (const o of offers) {
      if (offerNeedsMyAction(o)) mine.push(o);
      else if (o.status === 'accepted' || o.status === 'shipped'
               || o.status === 'pending' || o.status === 'countered') live.push(o);
      else done.push(o);
    }
    // Competing bids, side by side. The spec names this as a gap: two bids on
    // the same item could sit ten cards apart with unrelated trades between
    // them, and choosing between them is the commonest thing a seller does.
    //
    // Grouped INSIDE each section, never as a section of its own — the three
    // sections are a PRIORITY order, and a listing-scoped section would outrank
    // it, sinking a member's own move below a listing nobody is asking about.
    //
    // The count and spread describe the LISTING, so both calls are handed the
    // same population: every offer still in play. A seller who counters one of
    // three bids splits that listing across two sections, and a per-section
    // count would tell them "2 bids" while three were live.
    // `done` is excluded on purpose — a declined or expired bid is not
    // something the seller is still choosing between.
    const active = [...mine, ...live];
    const groupedMine = groupCompetingOffers(mine, active);
    const groupedLive = groupCompetingOffers(live, active);
    const groupMeta = new Map([...groupedMine.meta, ...groupedLive.meta]);

    return {
      sections: [
        { key: 'mine', title: 'Needs you', data: groupedMine.ordered },
        { key: 'live', title: 'Waiting on them', data: groupedLive.ordered },
        // Closed is history: grouping it would imply a choice that is over.
        { key: 'done', title: 'Closed', data: done },
      ].filter((sec) => sec.data.length > 0),
      groupMeta,
    };
  }, [offers]);

  /**
   * Which listing groups are open. Key is `${section}::${listing_id}`, not the
   * listing alone: a listing can appear in TWO sections at once (counter one
   * of three bids and it splits across "Needs you" and "Waiting on them"), and
   * a listing-keyed set would open both at once from one tap.
   *
   * Collapsed is the DEFAULT. Reported 2026-08-20: *"if you have 10 items for
   * sale and 5 bids, you would need to scroll through 50 listings"* — and the
   * grouping shipped on 2026-08-19 only put competing bids next to each other,
   * which fixes comparison and does nothing for volume.
   */
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());
  const toggleGroup = useCallback((key: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, [settings.hapticsEnabled]);

  /**
   * A pushed trade must never arrive collapsed.
   *
   * `deepLinkOfferId` highlights the card a notification points at. If that
   * bid is not the head of its group, collapsing would hide the very card the
   * member tapped a push to see — the screen would look like it had ignored
   * them. Opening the group is enough; the highlight then does its job.
   */
  useEffect(() => {
    if (!deepLinkOfferId) return;
    const target = offers.find((o) => o.id === deepLinkOfferId);
    if (!target) return;
    setOpenGroups((prev) => {
      const next = new Set(prev);
      next.add(`mine::${target.listing_id}`);
      next.add(`live::${target.listing_id}`);
      return next;
    });
  }, [deepLinkOfferId, offers]);

  /**
   * Collapse each listing's competing bids to ONE row until it is opened.
   *
   * All four load-bearing rules from docs/P2P_MARKETPLACE_SPEC.md survive:
   *   1. grouping stays INSIDE a section — this only removes rows from a
   *      section, it never moves one between sections;
   *   2. the group still sits at the position of its FIRST member, because the
   *      row it collapses to IS that member's position;
   *   3. the row carries count and spread — plus the listing title, which is
   *      identity rather than comparison data, and is no longer readable off
   *      the card underneath once the card is hidden;
   *   4. count and spread still come from `groupMeta`, computed over every
   *      ACTIVE offer, so a listing split across two sections reports the whole
   *      listing in both.
   *
   * `done` is never collapsed: the spec's reason for not grouping history is
   * that it would imply a choice that is over, and hiding it behind a
   * disclosure would say the same thing louder.
   */
  const { displaySections, groupHeadIds, sectionCounts } = useMemo(() => {
    const headIds = new Set<string>();
    const counts = new Map<string, number>();
    const out = sections.map((sec) => {
      // `total` is the number of TRADES, which is what the section header
      // states. Counting the rendered rows would say "Waiting on them · 2"
      // over five bids the moment two of them collapsed into one row — a
      // count describing the slice while reading as a fact about the whole
      // ([[learning_aggregate_over_the_wrong_population]]).
      const total = sec.data.length;
      if (sec.key === 'done') return { ...sec, total };
      const byListing = new Map<string, P2POffer[]>();
      for (const o of sec.data) {
        const arr = byListing.get(o.listing_id);
        if (arr) arr.push(o);
        else byListing.set(o.listing_id, [o]);
      }
      const data: P2POffer[] = [];
      for (const o of sec.data) {
        const arr = byListing.get(o.listing_id)!;
        const key = `${sec.key}::${o.listing_id}`;
        counts.set(key, arr.length);
        if (arr.length < 2) { data.push(o); continue; }
        const isHead = arr[0].id === o.id;
        if (isHead) headIds.add(o.id);
        // Collapsed: only the head survives, and it renders as the group row.
        if (isHead || openGroups.has(key)) data.push(o);
      }
      return { ...sec, data, total };
    });
    return { displaySections: out, groupHeadIds: headIds, sectionCounts: counts };
  }, [sections, openGroups]);

  /** What is actually at stake, the way a blotter opens with a total. */
  const committed = useMemo(
    () => offers
      .filter((o) => o.status === 'accepted' || o.status === 'shipped')
      .reduce((sum, o) => sum + (o.amount || 0), 0),
    [offers],
  );

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
        // Resync even on failure. A client-side timeout does NOT mean the write
        // failed: POST /confirm took 26.5s server-side and returned 200 while
        // this screen had already given up, kept rendering the trade as live,
        // and let the buyer open the address form on a trade that had in fact
        // completed — which the server then refused with a 409 the member had
        // no way to make sense of. After an error we know the least about the
        // server's state, which is exactly when to go and ask.
        retry();
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

  // Settling up, once a trade is live. Buyer sees payment rails, seller sees
  // where to book the parcel — Sparrow links out to both and participates in
  // neither (docs/P2P_MARKETPLACE_SPEC.md §5a).
  // `settleFor` / <SettleUpSheet> were removed 2026-08-19 with the "Book
  // shipping" button that was their only opener. A sheet nothing can open is
  // the dead-path class this repo keeps finding — and it was created in the
  // same edit that removed the button, which is exactly how they appear.
  // Settling now happens on `/offer/[offerId]` step 2, which has its own.

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
      // 'all', deliberately: this is the picker for recording a code the
      // seller is already holding. A member in the Netherlands may well have
      // shipped with a carrier outside their region, and filtering here would
      // leave them unable to enter the tracking they have in their hand. The
      // BOOKING list is the one that filters, because that is a choice being
      // made rather than a fact being recorded.
      .p2pListCarriers('all')
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

  /**
   * Arriving from the "how did it go?" push opens the rating prompt.
   *
   * Guarded by a REF, not by state: an effect that writes a state it also
   * lists as a dep tears itself down mid-flight, which is the class
   * `npm run check:effects` exists for. The ref is invisible to the dep array,
   * so this fires exactly once per offer id even though `offers` changes
   * identity on every refetch.
   *
   * Silent when the offer is already graded or not gradable — the deep link
   * still highlights the card, which is the honest outcome for "you already
   * did this".
   */
  const gradePromptedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!deepLinkOfferId || loading) return;
    if (gradePromptedRef.current === deepLinkOfferId) return;
    const target = offers.find((o) => o.id === deepLinkOfferId);
    if (!target) return;
    gradePromptedRef.current = deepLinkOfferId;
    // `action=track` comes from the trade screen (`/offer/[offerId]`), whose
    // "Add tracking" step lives here because this screen owns the carrier
    // sheet. Without it that step dropped the member on a highlighted card and
    // left them to find the button — a seam in the one flow built to remove
    // seams. The grade prompt has auto-opened on arrival since 2026-08-18;
    // this is the same courtesy for the other borrowed step.
    if (deepLinkAction === 'track' && target.can_add_tracking) {
      openTracking(target);
      return;
    }
    if (target.can_grade && !target.already_graded) onGrade(target);
  }, [deepLinkOfferId, deepLinkAction, loading, offers, onGrade, openTracking]);

  /**
   * Decline, confirmed — used by BOTH the button and the swipe gesture.
   *
   * One function, deliberately. A gesture that ran its own copy of the confirm
   * is how the two drift, and the copy that drifts is always the one nobody
   * looks at (learning_duplicate_impl_silently_drops_the_fix). Declining cannot
   * be undone on that offer: the buyer has to make a new one.
   */
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
          onPress: () => act(() => collectorsApi.p2pRespondToOffer(o.id, 'decline'), o.id, 'Declined'),
        },
      ],
    );
  }, [act, settings.hapticsEnabled]);

  /**
   * Accept, behind a confirm — which is what makes it safe to put on a swipe.
   *
   * The rule this screen was written to (and which stays true): **a gesture
   * must not be able to sell something.** eBay's own API lets you decline many
   * offers in one call and never accept many, because a decline is a sweep and
   * an accept is a commitment.
   *
   * The swipe therefore does not accept. It REVEALS an Accept action whose tap
   * opens this alert, and the trade is only agreed on the alert's second tap —
   * the same two-step the Decline gesture already had. One accidental swipe
   * still cannot sell a €850 item.
   */
  const confirmAccept = useCallback((o: P2POffer, amountLabel: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    Alert.alert(
      `Accept ${amountLabel}?`,
      // What accept ACTUALLY does, checked against p2p_offers_router: it sets
      // the offer to accepted and stamps `reserved_offer_id` on the listing.
      // It does NOT decline the other bids — the spec is explicit that accept
      // is "agreement, not a lock" and the listing stays live and browsable;
      // the other offers are declined at COMPLETION, by
      // `_settle_completed_trade`. The first draft of this alert said they were
      // declined immediately, which would have been the app describing a
      // consequence that does not happen.
      'This agrees the trade at that price and reserves the listing for this buyer. Other bids stay open until the trade is completed.',
      [
        { text: 'Not yet', style: 'cancel' },
        {
          text: 'Accept',
          onPress: () => act(() => collectorsApi.p2pRespondToOffer(o.id, 'accept'), o.id, 'Offer accepted'),
        },
      ],
    );
  }, [act, settings.hapticsEnabled]);

  /**
   * Take your own offer off the table. The button calls this "Delete" because
   * that is what the member is doing; the wire action stays `withdraw` and the
   * row still reads "Withdrawn", since `'withdrawn'` is not a legal
   * `p2p_offers` status (spec §1d) and the server writes cancelled +
   * withdrawn_by.
   *
   * Confirmed because it is destructive and now reachable by a gesture
   * (docs/gesture-navigation.md: "always show an alert before delete").
   */
  const confirmWithdraw = useCallback((o: P2POffer) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    Alert.alert(
      'Delete this offer?',
      'It comes off the table and the other side is told. You can send a new one.',
      [
        { text: 'Keep it', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => act(() => collectorsApi.p2pRespondToOffer(o.id, 'withdraw'), o.id, 'Deleted'),
        },
      ],
    );
  }, [act, settings.hapticsEnabled]);

  const renderOffer = useCallback(({ item: o, section }: { item: P2POffer; section: { key: string } }) => {
    // Group state for this card, in THIS section.
    const groupKey = `${section.key}::${o.listing_id}`;
    const inSection = sectionCounts.get(groupKey) ?? 1;
    const isGroupHead = groupHeadIds.has(o.id);
    const groupOpen = openGroups.has(groupKey);
    const busy = busyId === o.id;
    const isSeller = !o.i_am_buyer;
    const open = o.status === 'pending' || o.status === 'countered';
    const live = o.status === 'accepted' || o.status === 'shipped';
    const mine = offerNeedsMyAction(o);
    // Declined, withdrawn, expired, and completed-and-graded are all read-only
    // history. They stay in the list — a trade you can no longer act on is
    // still a trade you may want to look up — but they must not carry the same
    // weight as a live negotiation, or a screen of six dead offers and one open
    // one looks like seven equally urgent things.
    // `mine` wins: a completed trade you have not graded is terminal by status
    // but still needs you, and dimming it while stamping YOUR MOVE on it says
    // both things at once.
    const done = !open && !live && !mine;
    // The seller accepted a DIFFERENT bid on this listing. §1d keeps this one
    // alive on purpose — accept is an agreement, not a lock, and if the
    // accepted buyer ghosts this is the fallback. So it recedes and says why;
    // it does not disappear and every control below stays exactly where it is.
    const onHold = o.superseded === true;

    const group = groupMeta.get(o.id);

    /**
     * ALL is for SCANNING; Buying and Selling are for DOING.
     *
     * Requested 2026-08-19: *"can the all tab have a compressed version
     * without all the functionalities?"* — and it is the right split. "All" is
     * where you look to see what is going on across both sides of every trade,
     * and a card carrying four buttons, two confirm ticks and a tracking block
     * makes that a wall. Two cards fit on a screen; you cannot scan two cards.
     *
     * So in ALL the card keeps everything that helps you JUDGE — thumbnail,
     * title, amount, percentage of asking, YOUR MOVE, role, status, age, the
     * competing-bids banner — and drops everything that ACTS. The whole card
     * already opens `/offer/[offerId]`, which owns every one of those actions
     * in order, so nothing is unreachable: it is one tap further away, on a
     * screen built to do it.
     *
     * Buying and Selling keep the inline controls, because there you have
     * already narrowed to one side and are working through them.
     */
    const compact = role === 'all';

    // ── Finished trades are a REFERENCE ROW, not a card ────────────────────
    // A closed offer rendered the full card: thumbnail, title, amount, the
    // percentage of asking, two pills, status, the quoted message, and the
    // tracking block — all of it de-emphasised, none of it actionable. Five
    // rows of history for something nobody can act on, sitting at the same
    // physical size as a live negotiation.
    //
    // docs/ui-playbook.md, "a list card is a reference row, not a call to
    // action": the watchlist card lost two full-width buttons and an "Added
    // <date>" line, and four cards fit where two and a half did. Same move.
    // The card is kept for anything still in play; history collapses to one
    // line and still opens the listing.
    if (done) {
      return (
        <AnimatedPressable
          onPress={() => router.push({ pathname: '/listing/[id]', params: { id: o.listing_id } } as unknown as Href)}
          accessibilityRole="button"
          accessibilityLabel={[
            o.listing_title || 'Listing',
            formatPrice(o.amount, settings.currency, settings.numberLocale),
            statusLabel(o.status, o.i_am_buyer, o.i_withdrew),
            'Opens the listing',
          ].join('. ')}
          style={[
            styles.historyRow,
            { borderColor: colors.border },
            // The deep link exists so a push lands you on THE trade rather
            // than on a list of six. Once you have rated it the card collapses
            // to this row — and without this, the one thing the push was about
            // arrived looking like every other line of history.
            o.id === deepLinkOfferId && {
              backgroundColor: colors.accent + '12',
              borderRadius: radius.sm,
            },
          ]}
        >
          {o.listing_image_url ? (
            <Image source={{ uri: o.listing_image_url }} style={styles.historyThumb} contentFit="cover" transition={120} />
          ) : (
            <View style={[styles.historyThumb, styles.thumbEmpty, { backgroundColor: colors.accent + '12' }]}>
              <Ionicons name="pricetag-outline" size={13} color={colors.muted} />
            </View>
          )}
          <View style={styles.historyBody}>
            <Text style={[styles.historyTitle, { color: colors.text }]} numberOfLines={1}>
              {o.listing_title || 'Listing'}
            </Text>
            <Text style={[styles.historyMeta, { color: colors.muted }]} numberOfLines={1}>
              {statusLabel(o.status, o.i_am_buyer, o.i_withdrew)}
              {o.updated_at || o.created_at
                ? ` · ${timeAgo(o.updated_at || o.created_at!)}`
                : ''}
              {/* The one fact worth keeping from the old card's dimmed body:
                  whether you still owe the other side a rating is settled by
                  `mine`, so a row that reaches here has nothing outstanding —
                  but "you rated them" is a thing people look for afterwards. */}
              {o.already_graded ? (o.i_am_buyer ? ' · you rated the seller' : ' · you rated the buyer') : ''}
            </Text>
          </View>
          <Text style={[styles.historyAmount, { color: colors.muted }]}>
            {formatPrice(o.amount, settings.currency, settings.numberLocale)}
          </Text>
        </AnimatedPressable>
      );
    }

    // `p2p_offers.expires_at` exists, is NULL on every row and is written by
    // nothing — the spec records this as an open gap. So a bid rests until
    // somebody acts, and "Needs you" never drains on its own.
    //
    // The honest pressure is the age we ALREADY hold, escalated. A countdown
    // would be a deadline we do not enforce, which is the pattern the FTC
    // named in its 2022 dark-patterns report: a timer on a fake deadline. This
    // says only what is true — that somebody has been waiting this long.
    //
    // NOT gated on `mine`. The first version was, which excluded the exact
    // case this is for: a buyer whose bid has sat with a seller for three
    // weeks is not the one who has to move, and is the person most in the
    // dark. Terminal offers cannot reach here — they returned above — so this
    // is "anything still in play that nobody has touched".
    const stale = !onHold && (() => {
      const t = o.updated_at || o.created_at;
      if (!t) return false;
      const days = (Date.now() - Date.parse(t)) / 86_400_000;
      return Number.isFinite(days) && days >= STALE_AFTER_DAYS;
    })();

    /**
     * THE COLLAPSED GROUP ROW.
     *
     * One line per listing instead of one card per bid: "Charizard · 5 bids ·
     * €28 – €41". Ten listings with five bids each go from 50 cards to 10
     * rows, and opening one shows only that listing's bids.
     *
     * The row is the HEAD card's position, so the section's priority order is
     * untouched. Tapping toggles; it never navigates — a disclosure that also
     * navigated would make "see the other bids" and "open this trade" the same
     * gesture, and the whole point is choosing between them first.
     */
    const groupRow = isGroupHead ? (
      <AnimatedPressable
        onPress={() => toggleGroup(groupKey)}
        style={[styles.groupRow, { backgroundColor: colors.card, borderColor: colors.border }]}
        accessibilityRole="button"
        accessibilityState={{ expanded: groupOpen }}
        accessibilityLabel={
          `${o.listing_title || 'Listing'}. ${group?.size ?? inSection} bids, ` +
          `${formatPrice(group?.low ?? o.amount, settings.currency, settings.numberLocale)} to ` +
          `${formatPrice(group?.high ?? o.amount, settings.currency, settings.numberLocale)}.`
        }
        accessibilityHint={groupOpen ? 'Double tap to collapse these bids' : 'Double tap to see these bids'}
      >
        <Ionicons name="layers-outline" size={16} color={colors.accent} />
        <View style={styles.groupRowMain}>
          <Text style={[styles.groupRowTitle, { color: colors.text }]} numberOfLines={1}>
            {o.listing_title || 'Listing'}
          </Text>
          {/* Count and spread, from `groupMeta` — the LISTING's numbers, not
              this section's. `inSection` is only the fallback for a listing
              whose meta is missing, which cannot happen while grouping runs. */}
          <Text style={[styles.groupRowMeta, { color: colors.muted }]} numberOfLines={1}>
            {group?.size ?? inSection} bids · {formatPrice(group?.low ?? o.amount, settings.currency, settings.numberLocale)}
            {(group?.low ?? o.amount) === (group?.high ?? o.amount)
              ? ''
              : ` – ${formatPrice(group?.high ?? o.amount, settings.currency, settings.numberLocale)}`}
          </Text>
        </View>
        <Ionicons name={groupOpen ? 'chevron-up' : 'chevron-down'} size={18} color={colors.muted} />
      </AnimatedPressable>
    ) : null;

    // Collapsed: the row IS the group. The member cards are not rendered at
    // all rather than rendered and hidden — a zero-height card still costs the
    // list a cell.
    if (isGroupHead && !groupOpen) return groupRow;

    return (
      <>
      {groupRow}
      {/* Competing bids, announced once above the group. Count and spread are
          all a seller HAS at this point — the spec records that comparing on
          distance is impossible by construction, since addresses are only
          collectable after `accepted`.

          The seller framing is safe: a buyer sees only their OWN offers, and
          the server allows one open offer per buyer per listing (409 "You
          already have an open offer on this listing"), so a group can only
          ever be bids a seller is choosing between. All bids on one listing
          share its currency, so the spread is a real range. */}
      {/* The banner survives ONLY where there is no group row: a listing whose
          other bids sit in a different section has one card here, so nothing
          above it would otherwise say what it is one of (spec rule 4). Where
          the row exists it already carries the same two numbers. */}
      {group?.isFirst && inSection < 2 ? (
        <View style={styles.groupHeader}>
          <Ionicons name="layers-outline" size={13} color={colors.accent} />
          <Text style={[styles.groupHeaderText, { color: colors.accent }]}>
            {group.size} bids on this listing · {formatPrice(group.low, settings.currency, settings.numberLocale)}
            {group.low === group.high
              ? ''
              : ` – ${formatPrice(group.high, settings.currency, settings.numberLocale)}`}
          </Text>
        </View>
      ) : null}
      {/* The whole card opens the listing, which is what the "View listing" link
          at the bottom used to do from its own dedicated row — a full row of
          vertical space spent on a link that duplicated the obvious gesture.
          Action buttons are nested Pressables and still win their own taps. */}
      {/* Swipe left to decline — for the seller sweeping a stack of bids, which
          is the case the whole grouping change above exists to serve. Right
          side only, and DECLINE only: eBay's own API allows declining many
          offers in one call and never accepting many, because a decline is a
          sweep and an accept is a commitment. A gesture must not be able to
          sell something.

          docs/gesture-navigation.md: destructive actions confirm (it shares
          `confirmDecline` with the button), and every gesture needs a
          non-gesture equivalent — the Decline button is still right there,
          which is also what iOS HIG asks for. Only offered where the button
          is: an open offer the seller may answer. */}
      <SwipeableRow
        // LEFT swipe -> Accept (2026-08-20, requested). The "decline only"
        // rule above is about COMMITMENT, not about which side the action sits
        // on: `confirmAccept` puts an alert between the gesture and the trade,
        // so the swipe still cannot sell anything on its own. Seller + open
        // only, exactly where the Accept button is.
        leftActions={isSeller && open && !busy ? [{
          key: 'accept',
          label: 'Accept',
          icon: 'checkmark-circle-outline',
          color: colors.success,
          onPress: () => confirmAccept(o, formatPrice(o.amount, settings.currency, settings.numberLocale)),
        }] : []}
        // RIGHT swipe -> Decline (seller, open) and Delete (either side, while
        // the offer is still on the table). Both confirm; Delete is the
        // `withdraw` action, and the gesture doc requires an alert before a
        // destructive one.
        rightActions={[
          ...(isSeller && open && !busy ? [{
            key: 'decline',
            label: 'Decline',
            icon: 'close-circle-outline' as const,
            color: colors.danger,
            onPress: () => confirmDecline(o),
          }] : []),
          ...((open || live) && !busy ? [{
            key: 'withdraw',
            label: 'Delete',
            icon: 'trash-outline' as const,
            color: colors.muted,
            onPress: () => confirmWithdraw(o),
          }] : []),
        ]}
        // Enabled whenever ANY action is offered — it used to be gated on
        // `isSeller && open`, which left a buyer unable to swipe at all even
        // though Delete applies to them too.
        disabled={busy || !(open || live)}
        enableHaptics={settings.hapticsEnabled}
      >
      <AnimatedPressable
        // Opens the TRADE, not the listing (2026-08-19). It used to push
        // `/listing/[id]`, which answers "what is this item" when the question
        // a member has on this screen is "what do I do about this trade" —
        // reported as "this is not what you need to edit/manage".
        // `/offer/[offerId]` owns the whole flow in order; the listing is a
        // link at the bottom of it.
        onPress={() => router.push(`/offer/${encodeURIComponent(o.id)}` as Href)}
        accessibilityRole="button"
        /* The two facts that decide whether this card matters — does it need
           me, and what state is it in — were BOTH absent from the label. A
           screen-reader user heard the price of every trade and could not tell
           which one was waiting on them, on a screen whose entire job is
           answering that. */
        accessibilityLabel={[
          mine ? 'Needs you.' : null,
          onHold ? 'On hold, another bid was accepted.' : null,
          stale ? 'Still waiting.' : null,
          o.listing_title || 'Listing',
          formatPrice(o.amount, settings.currency, settings.numberLocale),
          statusLabel(o.status, o.i_am_buyer, o.i_withdrew),
          group && group.size > 1 ? `One of ${group.size} bids on this listing.` : null,
          // The card has pushed `/offer/[offerId]` since 2026-08-19 — the
          // TRADE, not the listing — and the label kept promising the listing.
          // Read off the live accessibility tree on the sim 2026-08-20. A
          // screen-reader user was told the wrong destination on every card on
          // the screen whose whole job is managing trades.
          'Opens this trade',
        ].filter(Boolean).join('. ')}
        // Left edge stripe carries the role at a glance while scanning, so you
        // do not have to read the pill on every card. Same two semantic colours
        // as the pill — the treatment reads as one system, not two signals.
        style={[
        styles.card,
        {
          backgroundColor: colors.card,
          borderColor: colors.border,
          borderLeftWidth: 3,
          borderLeftColor: o.i_am_buyer ? colors.info : colors.success,
        },
        // Emphasis by shadow and opacity, not by colour: the stripe still has
        // to read as the same role token, and dropping the card's elevation is
        // what actually makes the live ones sit forward.
        // `done && styles.cardDone` was here. Terminal offers no longer reach
        // this card at all — they render as history rows above — so the style
        // and its condition both went with them.
        //
        // A bid on hold recedes for a RELATED but different reason: it is not
        // what you should be reading right now. It is not finished, every
        // button is still there, so this is opacity alone and it keeps its
        // elevation and its role stripe.
        onHold && styles.cardOnHold,
        mine && {
          borderColor: colors.accent,
          // Re-asserted: `borderColor` sets all four edges, and losing the left
          // one here would erase the buying/selling signal on exactly the cards
          // a user looks at hardest.
          borderLeftColor: o.i_am_buyer ? colors.info : colors.success,
          ...shadow.card,
        },
        // Arrived from a push about THIS trade. Last in the array so it wins
        // over `done`'s dimming — a closed trade you were just asked to rate
        // is the one card on screen you were sent here for. Same re-assertion
        // of the left edge, for the same reason.
        o.id === deepLinkOfferId && {
          borderColor: colors.accent,
          borderWidth: 2,
          borderLeftColor: o.i_am_buyer ? colors.info : colors.success,
          opacity: 1,
          ...shadow.card,
        },
      ]}>
        <View style={styles.rowTop}>
          {/* Supporting visual FIRST. A stacked list of pure text is what made
              this read as a spreadsheet; a thumbnail is what makes it scannable
              (Mobbin / Eleken on stacked lists). Falls back to a tinted glyph
              rather than a blank box — an empty square reads as a broken image. */}
          {o.listing_image_url ? (
            <Image source={{ uri: o.listing_image_url }} style={styles.thumb} contentFit="cover" transition={120} />
          ) : (
            <View style={[styles.thumb, styles.thumbEmpty, { backgroundColor: colors.accent + '12' }]}>
              <Ionicons name="pricetag-outline" size={18} color={colors.muted} />
            </View>
          )}
          <Text style={[styles.title, { color: colors.text }]} numberOfLines={2}>
            {o.listing_title || 'Listing'}
          </Text>
          {/* Amount and its percentage STACK. They used to sit beside the title
              as two more siblings in this row, and "+5% of EUR 37 asking" is
              long enough that the title lost half its width to it — every card
              read "LEGO Ferguson…", "He's Got A Swor…". A column caps the right
              side and lets the title have two full lines. */}
          <View style={styles.amountCol}>
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
          {/* Leads the row when it applies. The accent is the same one the
              action buttons use — "this is yours to move" and "this is the
              button that moves it" being one colour is the point. */}
          {mine ? (
            <View style={[styles.movePill, { backgroundColor: colors.accent }]}>
              <Text style={[styles.movePillText, { color: colors.accentText }]}>YOUR MOVE</Text>
            </View>
          ) : null}
          {/* Takes the slot YOUR MOVE used to occupy on exactly these cards,
              and says the thing the member would otherwise have to work out:
              the item is promised, but this bid is still yours to fall back
              on. Muted fill, not danger — nothing has gone wrong here. */}
          {onHold ? (
            <View style={[styles.holdPill, { backgroundColor: colors.border }]}>
              <Text style={[styles.holdPillText, { color: colors.muted }]}>
                {o.i_am_buyer ? 'ANOTHER BID ACCEPTED' : 'YOU ACCEPTED ANOTHER BID'}
              </Text>
            </View>
          ) : null}
          <View style={[
            styles.rolePill,
            { backgroundColor: o.i_am_buyer ? colors.infoBg : colors.successBg },
          ]}>
            <Text style={[
              styles.rolePillText,
              { color: o.i_am_buyer ? colors.info : colors.success },
            ]}>
              {/* "Buying" alone reads as a category, not as a fact about you —
                  *"i don't get 'buying', is this the user is buying?"*. The
                  pronoun is the whole fix. */}
              {o.i_am_buyer ? 'You buy' : 'You sell'}
            </Text>
          </View>
          <Text style={[styles.status, { color: colors.muted }]}>
            {statusLabel(o.status, o.i_am_buyer, o.i_withdrew)}
            {/* Only from the SECOND counter on. At one, the status line already
                says a counter happened, and "Countered · 1 counter" said it
                twice. Past one, the number is the new information: how far this
                haggle has actually gone. */}
            {o.counter_count > 1 ? ` · ${o.counter_count} rounds` : ''}
            {/* An offer with no age can't be judged: "Awaiting seller" reads
                very differently at two hours than at three weeks, and the
                server has sent `created_at` all along without anything
                rendering it. Guarded — the field is nullable. */}
            {/* LAST ACTIVITY, not when it opened. `created_at` made a haggle
                opened three weeks ago and countered yesterday read "3 weeks
                ago" — backwards for the judgement this line exists to support.
                Falls back to created_at for an older server build, which is
                the previous behaviour rather than a blank. */}
            {o.updated_at || o.created_at
              ? ` · ${timeAgo(o.updated_at || o.created_at!)}`
              : ''}
          </Text>
          {stale ? (
            <View style={styles.staleTag}>
              <Ionicons name="hourglass-outline" size={11} color={colors.warning} />
              <Text style={[styles.staleText, { color: colors.warning }]}>Still waiting</Text>
            </View>
          ) : null}
        </View>

        {o.message ? (
          <Text style={[styles.message, { color: colors.muted }]} numberOfLines={3}>“{o.message}”</Text>
        ) : null}

        {/* Two-sided completion, made legible. A seller who has confirmed but
            is waiting on the buyer should SEE that, not wonder if it worked. */}
        {live && !compact ? (
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
        {o.tracking_code && !compact ? (
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

        {compact ? (
          // One quiet line instead of a row of buttons: the card is still
          // tappable, and saying where the controls went beats a card that
          // simply looks like it lost them.
          <Text style={[styles.compactHint, { color: colors.muted }]}>
            Tap to manage this trade
          </Text>
        ) : (
        <View style={styles.actions}>
          {/* Every action here is a round trip plus a refetch of the whole
              list. Until now the only feedback was `disabled` dimming each
              button to 50%, which reads as "these went dead", not as "this is
              working" — the two look identical and one of them is alarming.
              The awaits are bounded by httpClient's request timeout, so this
              spinner cannot outlive the call (docs/ui-playbook.md, "any await
              between a spinner going up and coming down must be bounded"). */}
          {busy ? (
            <View style={styles.working}>
              <ActivityIndicator size="small" color={colors.accent} />
              <Text style={[styles.workingText, { color: colors.muted }]}>Working…</Text>
            </View>
          ) : null}

          {/* The buyer answers a counter. A counter replaces `amount` with the
              seller's figure, so what the buyer is looking at is the seller's
              offer — and `offerNeedsMyAction` has always agreed, stamping YOUR
              MOVE on this exact card. It just had no button under it. */}
          {o.i_am_buyer && o.status === 'countered' ? (
            <>
              <AnimatedPressable
                onPress={() => act(
                  () => collectorsApi.p2pRespondToOffer(o.id, 'accept'),
                  o.id,
                  'Bid accepted',
                )}
                disabled={busy}
                style={[styles.btn, { backgroundColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel="Accept this bid"
              >
                <Text style={[styles.btnText, { color: colors.accentText }]}>Accept bid</Text>
              </AnimatedPressable>
              {/* Confirmed, like the seller's Decline: this ends the
                  negotiation and the buyer has to start a new offer. */}
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  Alert.alert(
                    'Turn down this counter?',
                    'The seller will be told. You can make a new offer, but this one is gone.',
                    [
                      { text: 'Keep it', style: 'cancel' },
                      {
                        text: 'Turn it down',
                        style: 'destructive',
                        onPress: () => act(
                          () => collectorsApi.p2pRespondToOffer(o.id, 'decline'),
                          o.id,
                          'Counter turned down',
                        ),
                      },
                    ],
                  );
                }}
                disabled={busy}
                style={[styles.btn, styles.btnQuiet]}
                accessibilityRole="button"
                accessibilityLabel="Turn down the seller's counter"
              >
                <Text style={[styles.btnText, { color: colors.danger }]}>Turn it down</Text>
              </AnimatedPressable>
            </>
          ) : null}

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
              {/* Gone at the cap rather than rendered and refused. The server
                  returns 409 COUNTER_LIMIT, so leaving the button here would
                  be a control whose only outcome is an error toast — the
                  dead-button failure Stage 1 bug 0 was fixed to avoid. Accept
                  and Decline stay, so a capped haggle is never stranded. */}
              {o.counter_count < MAX_COUNTERS ? (
                <AnimatedPressable
                  onPress={() => onCounter(o)}
                  disabled={busy}
                  style={[styles.btn, styles.btnGhost, { borderColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Counter this offer"
                >
                  <Text style={[styles.btnText, { color: colors.accent }]}>Counter</Text>
                </AnimatedPressable>
              ) : null}
              {/* Tertiary, and CONFIRMED. Declining cannot be undone on that
                  offer — the buyer has to make a new one — and it sat here as
                  a same-size button beside Accept, one mis-tap from killing a
                  sale. docs/ui-playbook.md: confirm destructive actions. */}
              <AnimatedPressable
                onPress={() => confirmDecline(o)}
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

          {/* "Add tracking" and "Book shipping" / "How to pay" WERE here.
              Removed 2026-08-19 after seeing it on a device: a live trade put
              FOUR buttons in this row — Mark sent · Add tracking · Book
              shipping · Delete — and the row is `flexWrap: 'nowrap'` with
              shrinking buttons on purpose (playbook, 2026-08-15), so the last
              label squeezed until the WORD broke and it rendered as "Del ete".
              Shrinking is the right rule for three buttons and the wrong one
              for four; the fix is fewer buttons, not a wrapping row.

              They are not lost: both are steps 2 and 3 of `/offer/[offerId]`,
              which the whole card now opens, and which shows them in the order
              they happen. This card keeps the PRIMARY move only — which is
              what a list row is for. */}

          {/* `open || live`, not `live`. Gated on `live` alone this never
              appeared on a pending offer — the exact state 4 of 5 rows sit in —
              so a buyer had no way to retract a bid the seller had not
              answered. An order you cannot cancel is not an order, it is a
              trap. Server widened to match (p2p_offers_router). */}
          {open || live ? (
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

          {/* "Rate the seller" / "Rate the buyer", not "Grade trade". You are
              not scoring the transaction, you are scoring the person on the
              other side of it — and which person that is depends on which side
              you were on. "Grade" also collides with condition grading, which
              is a different thing this app does to cards. */}
          {o.can_grade && !o.already_graded ? (
            <AnimatedPressable
              onPress={() => onGrade(o)}
              disabled={busy}
              style={[styles.btn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel={o.i_am_buyer ? 'Rate the seller' : 'Rate the buyer'}
            >
              <Text style={[styles.btnText, { color: colors.accentText }]}>
                {o.i_am_buyer ? 'Rate the seller' : 'Rate the buyer'}
              </Text>
            </AnimatedPressable>
          ) : null}

          {/* "You rated the seller" moved to the history row. `already_graded`
              implies a COMPLETED trade, which is terminal and not `mine`, so
              it now always returns above — leaving the block here would be a
              dead path surviving a cleanup. */}
        </View>
        )}

        {/* Why the Counter button is not there. AFTER the actions row, not
            inside it: that row is `flexWrap: 'nowrap'` on purpose (playbook,
            2026-08-15), so a sentence in it would squeeze Accept and Decline
            rather than wrap. Without this the button simply vanishes at the
            cap, which reads as a bug rather than as a rule. */}
        {isSeller && open && !compact && o.counter_count >= MAX_COUNTERS ? (
          <Text style={[styles.capNote, { color: colors.muted }]}>
            Countered {MAX_COUNTERS} times — accept it or decline it
          </Text>
        ) : null}

      </AnimatedPressable>
      </SwipeableRow>
      </>
    );
    // `settings.hapticsEnabled` is in here because the Decline confirmation
    // fires a haptic directly. Without it a member who turns haptics off keeps
    // feeling that one tap until something else re-renders the row.
    // `role` IS a dependency: it decides `compact`, so leaving it out would
    // keep rendering the compressed card after a switch to Buying/Selling.
    // The four group values are dependencies for the same reason `role` is:
    // they decide what this function RENDERS. `openGroups` in particular —
    // leave it out and the callback closes over the set as it was on mount, so
    // tapping a group row updates the state, the list re-renders from a stale
    // renderer, and the group appears not to open at all.
  }, [act, busyId, colors, confirmDecline, confirmAccept, confirmWithdraw, deepLinkOfferId, groupMeta, onCounter, onGrade,
      openTracking, role, router, groupHeadIds, openGroups, sectionCounts, toggleGroup,
      settings.currency, settings.numberLocale, settings.hapticsEnabled]);

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScreenHeader title="Open bids" />

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

      {/* Reconciles with the marketplace badge. Tapping "3" and landing on a
          screen that never says three again is what made the badge feel
          untrustworthy; this is the same count, from the same helper. */}
      {/* Opens with what is at stake, the way a blotter does — Kalshi's
          portfolio leads with committed value rather than with rows. */}
      {!loading && !error && offers.length > 0 ? (
        <View style={styles.summary}>
          {/* "2 needs you" was a number agreeing with nothing — reported as
              making no sense, and it doesn't: the noun it counts was missing.
              Name it, and make the verb agree. */}
          {needsAction > 0 ? (
            <Text style={[styles.summaryStrong, { color: colors.accent }]}>
              {needsAction === 1 ? '1 bid needs you' : `${needsAction} bids need you`}
            </Text>
          ) : null}
          {needsAction > 0 && committed > 0 ? (
            <Text style={[styles.summaryText, { color: colors.muted }]}>·</Text>
          ) : null}
          {committed > 0 ? (
            <Text style={[styles.summaryText, { color: colors.muted }]}>
              {formatPrice(committed, settings.currency, settings.numberLocale)} committed
            </Text>
          ) : null}
        </View>
      ) : null}

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
        <SectionList
          sections={displaySections}
          keyExtractor={(o) => o.id}
          renderItem={renderOffer}
          stickySectionHeadersEnabled={false}
          // The first section carries no header. "NEEDS YOU · 2" sat one line
          // under "2 bids need you" and repeated it in a quieter voice — the
          // summary IS this group's heading, and the cards below it are the
          // only ones stamped YOUR MOVE. The later groups still need naming,
          // because nothing above them says what they are.
          renderSectionHeader={({ section }) => (
            section.key === 'mine' ? null : (
              <Text style={[styles.sectionHeader, { color: colors.muted }]}>
                {section.title} · {section.total ?? section.data.length}
              </Text>
            )
          )}
          contentContainerStyle={[styles.list, { paddingBottom: bottomInset }]}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.accent} />}
          // Stated at the bottom, not the top: a banner above the list would
          // be a warning about something the reader has not looked at yet.
          // Rendered only when the server actually sent a total AND it exceeds
          // what arrived — an older build sends nothing and this claims
          // nothing, rather than treating a missing number as zero.
          ListFooterComponent={
            hiddenCount > 0 ? (
              <View style={styles.truncation}>
                <Ionicons name="information-circle-outline" size={14} color={colors.muted} />
                <Text style={[styles.truncationText, { color: colors.muted }]}>
                  Showing your {offers.length} most recent
                  {hiddenCount === 1 ? ' — 1 older trade isn\u2019t listed'
                                     : ` — ${hiddenCount} older trades aren\u2019t listed`}
                </Text>
              </View>
            ) : null
          }
          ListEmptyComponent={
            <EmptyState
              icon="swap-horizontal-outline"
              title={role === 'selling' ? 'No bids received yet' : 'No open bids yet'}
              subtitle={
                role === 'selling'
                  ? 'When someone bids on your listings, it appears here.'
                  : 'Find something on the marketplace and place a bid.'
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
  // Sits directly above the first card of a group and shares its gutter, so
  // the banner reads as a lid on those cards rather than as a row of its own.
  groupRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 12,
    paddingVertical: 12,
    marginTop: 10,
  },
  groupRowMain: { flex: 1, gap: 2 },
  groupRowTitle: { fontSize: textToken.md, fontWeight: fontWeight.semibold },
  groupRowMeta: { fontSize: textToken.sm, lineHeight: 17 },
  groupHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
    marginBottom: -2,
    paddingHorizontal: 4,
  },
  // `sm`, not `xs`. docs/ui-playbook.md, "Type scale": xs is 10pt, below
  // Apple's ~11pt floor, and BANNED for anything a user reads — this screen is
  // the one that got reported as "very small letters" in the first place. sm
  // is also what movePillText and rolePillText use, so the banner sits at the
  // same caption level as the pills below it instead of inventing a level.
  groupHeaderText: {
    fontSize: textToken.sm, fontWeight: fontWeight.bold, lineHeight: 17, flexShrink: 1,
  },
  card: {
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.lg,
    padding: 14, marginBottom: 10, gap: 8,
    ...shadow.card,
  },
  // History, not a live negotiation: flat, and one step back. Kept above 0.6
  // so the text stays legible against the card — this is de-emphasis, not a
  // disabled state, and the card is still readable and still scrolls.
  // Opacity ONLY, and no `cardDone` beside it any more: terminal offers render
  // as history rows and never reach the card. A bid on hold IS still live and
  // still answerable, so it keeps its elevation and its role stripe and only
  // stops competing for attention.
  cardOnHold: { opacity: 0.72 },
  holdPill: {
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill,
  },
  // Matches rolePillText exactly — it stands in the same row and takes the
  // slot YOUR MOVE would have occupied, so a different size would read as a
  // different KIND of thing.
  holdPillText: {
    fontSize: textToken.sm, fontWeight: fontWeight.bold, letterSpacing: 0.3,
  },
  staleTag: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  staleText: { fontSize: textToken.sm, fontWeight: fontWeight.semibold },
  // Its OWN line, not a cell in the actions row. That row is
  // `flexWrap: 'nowrap'` on purpose (playbook, 2026-08-15: a wrapped third
  // button reads as a separate decision), so a sentence dropped into it would
  // squeeze Accept and Decline instead of wrapping — the row shrinks, and the
  // row is made of touch targets.
  capNote: { fontSize: textToken.sm, lineHeight: 17, textAlign: 'right', marginTop: 2 },
  compactHint: { fontSize: textToken.sm, lineHeight: 17, marginTop: 2 },
  // One line, hairline-separated rather than carded: history is a reference
  // list, and giving it borders and shadows makes it compete with the
  // negotiations above it for exactly the attention it does not want.
  historyRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 9, paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  historyThumb: { width: 32, height: 32, borderRadius: radius.xs },
  historyBody: { flex: 1, gap: 1 },
  // Three levels inside one row, per the playbook's lead/body/caption table:
  // the title leads at `md`, the meta recedes to `sm`, and neither touches the
  // banned `xs`. The amount matches the title so the row reads left-to-right
  // as one statement rather than as a title with a footnote.
  historyTitle: { fontSize: textToken.md, fontWeight: fontWeight.semibold },
  historyMeta: { fontSize: textToken.sm, lineHeight: 17 },
  historyAmount: { fontSize: textToken.md, fontWeight: fontWeight.semibold },
  // Sits at the END of the list, where a reader arrives having seen everything
  // this page holds — which is the only honest moment to say there is more.
  truncation: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingTop: 14, paddingHorizontal: 16,
  },
  truncationText: { fontSize: textToken.sm, lineHeight: 17, textAlign: 'center', flexShrink: 1 },
  needsLine: {
    fontSize: textToken.md, fontWeight: fontWeight.bold,
    paddingHorizontal: 16, paddingBottom: 8, marginTop: -4,
  },
  rowTop: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  thumb: { width: 44, height: 44, borderRadius: radius.sm },
  thumbEmpty: { alignItems: 'center', justifyContent: 'center' },
  // Section headers do the work the sort order could not.
  sectionHeader: {
    fontSize: textToken.sm, fontWeight: fontWeight.extrabold,
    letterSpacing: 0.6, textTransform: 'uppercase',
    paddingHorizontal: 2, paddingTop: 14, paddingBottom: 6,
  },
  summary: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 16, paddingBottom: 8,
  },
  summaryText: { fontSize: textToken.md },
  summaryStrong: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  // Caps the right side so the title keeps its width. `flexShrink: 0` because
  // a price must never wrap or ellipsize — the one number on the card that has
  // to be read exactly.
  // 38%, down from 46%: the row gained a 44pt thumbnail, and at the old cap a
  // two-line title like "He's Got A Sword! [1] (Cold Foil)" was left about
  // 140pt to wrap in. The delta line under the amount is the flexible part —
  // it can wrap; the price itself still cannot (flexShrink: 0).
  amountCol: { alignItems: 'flex-end', flexShrink: 0, maxWidth: '38%' },
  title: { flex: 1, fontSize: textToken.lg, fontWeight: fontWeight.semibold, lineHeight: 22 },
  // `lg`, not `xl` (2026-08-11). At 20/extrabold the figure dominated the card
  // — reported as "the numbers are too big" — and with the percentage line now
  // sitting under it the amount no longer has to carry the comparison alone.
  // Still the lead: nothing else on the card is 16/extrabold.
  amount: { fontSize: textToken.lg, fontWeight: fontWeight.extrabold, letterSpacing: -0.2 },
  // Caption level: it qualifies the amount above it, it does not compete.
  amountDelta: { fontSize: textToken.sm, marginTop: 1, textAlign: 'right' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  // A pill is a LABEL beside body text, not body text. At md/bold it was the
  // same size as the status it sits next to and competed with the title; `pill`
  // radius matches the segmented control at the top of the same screen, where
  // `radius.xs` (6) read as a stray rounded rectangle.
  rolePill: { paddingHorizontal: 9, paddingVertical: 3, borderRadius: radius.pill },
  // Filled where the role pill is tinted — it has to out-rank the role, which
  // is context, not a call to act.
  movePill: { paddingHorizontal: 9, paddingVertical: 3, borderRadius: radius.pill },
  movePillText: { fontSize: textToken.sm, fontWeight: fontWeight.extrabold, letterSpacing: 0.4 },
  rolePillText: { fontSize: textToken.sm, fontWeight: fontWeight.bold, letterSpacing: 0.3 },
  status: { fontSize: textToken.md, fontWeight: fontWeight.medium, flexShrink: 1 },
  message: { fontSize: textToken.md, fontStyle: 'italic', lineHeight: 20 },
  confirmRow: { flexDirection: 'row', alignItems: 'center', gap: 5, flexWrap: 'wrap' },
  confirmText: { fontSize: textToken.sm, lineHeight: 17, marginRight: 8 },
  // Right-aligned and divided off the body. Actions floating left under a
  // paragraph read as more content; on the right of a ruled row they read as
  // the decision. Empty rows collapse — `gap` on an empty View adds nothing.
  // ONE row. `flexWrap: 'wrap'` let a third button drop onto its own line —
  // reported on a countered bid, where Accept / Turn it down / Delete rendered
  // as two rows with Delete stranded underneath, which reads as a separate
  // decision rather than the third option in a set.
  //
  // The buttons shrink instead: `flexShrink` on `btn` plus tighter horizontal
  // padding keeps all three on the line at the widest label we ship, and
  // `minHeight: 38` is untouched so the touch targets do not shrink with them.
  actions: {
    flexDirection: 'row', flexWrap: 'nowrap', gap: 8,
    justifyContent: 'flex-end', alignItems: 'center',
    marginTop: 2,
  },
  // Left of the right-aligned buttons, so it explains the dimming beside it.
  working: { flexDirection: 'row', alignItems: 'center', gap: 7, marginRight: 'auto' },
  workingText: { fontSize: textToken.sm },
  btn: {
    minHeight: 38, justifyContent: 'center', alignItems: 'center',
    paddingHorizontal: 12, paddingVertical: 9, borderRadius: radius.md,
    flexShrink: 1,
  },
  btnGhost: { borderWidth: 1, backgroundColor: 'transparent' },
  // No border and no fill: the third action should read as the way out, not as
  // a third equal choice. Accept fills, Counter outlines, Decline recedes.
  btnQuiet: { backgroundColor: 'transparent' },
  btnText: { fontSize: textToken.md, fontWeight: fontWeight.bold, textAlign: 'center' },
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
});
