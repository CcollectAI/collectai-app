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
import React, { useCallback, useMemo, useState } from 'react';
import { View, Text, FlatList, StyleSheet, RefreshControl, Alert, Animated } from 'react-native';
import { useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import ScreenHeader from '@/components/ScreenHeader';
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
import { formatPrice } from '@/lib/format';
import { collectorsApi } from '@/api/collectorsApi';
import type { P2POffer } from '@/api/p2pApi';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';
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

  const onCounter = useCallback((o: P2POffer) => {
    // Alert.prompt is iOS-only; a simple ladder keeps this cross-platform and
    // avoids a modal for a one-number decision.
    const steps = [o.amount * 1.1, o.amount * 1.2, o.amount * 1.35].map((n) => Math.round(n * 100) / 100);
    Alert.alert(
      'Counter offer',
      `They offered ${formatPrice(o.amount, settings.currency)}. Counter with:`,
      [
        ...steps.map((amt) => ({
          text: formatPrice(amt, settings.currency),
          onPress: () => act(() => collectorsApi.p2pRespondToOffer(o.id, 'counter', amt), o.id, 'Counter sent'),
        })),
        { text: 'Cancel', style: 'cancel' as const },
      ],
    );
  }, [act, settings.currency]);

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

    return (
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.rowTop}>
          <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
            {o.listing_title || 'Listing'}
          </Text>
          <Text style={[styles.amount, { color: colors.text }]}>
            {formatPrice(o.amount, settings.currency, settings.numberLocale)}
          </Text>
        </View>

        <View style={styles.metaRow}>
          <View style={[styles.rolePill, { backgroundColor: colors.accent + '18' }]}>
            <Text style={[styles.rolePillText, { color: colors.accent }]}>
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
                style={[styles.btn, styles.btnGhost, { borderColor: colors.border }]}
                accessibilityRole="button"
                accessibilityLabel="Counter this offer"
              >
                <Text style={[styles.btnText, { color: colors.text }]}>Counter</Text>
              </AnimatedPressable>
              <AnimatedPressable
                onPress={() => act(() => collectorsApi.p2pRespondToOffer(o.id, 'decline'), o.id, 'Declined')}
                disabled={busy}
                style={[styles.btn, styles.btnGhost, { borderColor: colors.border }]}
                accessibilityRole="button"
                accessibilityLabel="Decline this offer"
              >
                <Text style={[styles.btnText, { color: colors.muted }]}>Decline</Text>
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

          {live ? (
            <AnimatedPressable
              onPress={() => act(() => collectorsApi.p2pRespondToOffer(o.id, 'withdraw'), o.id, 'Withdrawn')}
              disabled={busy}
              style={[styles.btn, styles.btnGhost, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel="Withdraw from this trade"
            >
              <Text style={[styles.btnText, { color: colors.muted }]}>Withdraw</Text>
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
  }, [act, busyId, colors, onCounter, onGrade, router, settings.currency, settings.numberLocale]);

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
                style={[styles.segmentBtn, active && { backgroundColor: colors.accent + '1E' }]}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                accessibilityLabel={r === 'all' ? 'All offers' : r === 'buying' ? 'Offers I made' : 'Offers I received'}
              >
                <Text style={[
                  styles.segmentText,
                  { color: active ? colors.accent : colors.muted },
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

const styles = StyleSheet.create({
  safe: { flex: 1 },
  pad: { padding: 16 },
  loadingText: { fontSize: textToken.md },
  segmentWrap: { paddingHorizontal: 16, paddingTop: 8 },
  segment: {
    flexDirection: 'row', borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.pill, padding: 3, marginBottom: 10,
  },
  segmentBtn: { flex: 1, alignItems: 'center', paddingVertical: 7, borderRadius: radius.pill },
  segmentText: { fontSize: textToken.sm },
  list: { paddingHorizontal: 16, paddingTop: 2 },
  card: {
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.md,
    padding: 14, marginBottom: 12, gap: 8,
  },
  rowTop: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  title: { flex: 1, fontSize: textToken.md, fontWeight: fontWeight.semibold },
  amount: { fontSize: textToken.lg, fontWeight: fontWeight.extrabold, letterSpacing: -0.3 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  rolePill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.xs },
  rolePillText: { fontSize: textToken.xs, fontWeight: fontWeight.bold },
  status: { fontSize: textToken.xs, flexShrink: 1 },
  message: { fontSize: textToken.sm, fontStyle: 'italic', lineHeight: 18 },
  confirmRow: { flexDirection: 'row', alignItems: 'center', gap: 5, flexWrap: 'wrap' },
  confirmText: { fontSize: textToken.xs, marginRight: 8 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 2 },
  btn: { paddingHorizontal: 14, paddingVertical: 9, borderRadius: radius.sm },
  btnGhost: { borderWidth: 1, backgroundColor: 'transparent' },
  btnText: { fontSize: textToken.sm, fontWeight: fontWeight.bold },
  graded: { fontSize: textToken.xs, paddingVertical: 9 },
  viewLink: { fontSize: textToken.xs, fontWeight: fontWeight.bold, marginTop: 2 },
});
