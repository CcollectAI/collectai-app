/**
 * "3 bids need you →" — one line on Home, and only when it is true.
 *
 * WHY IT EXISTS
 * `countOffersNeedingAction` had exactly ONE caller: the badge on
 * `app/listings.tsx`. So a bid waiting on an answer was visible only if you
 * opened the Marketplace tab, or if a push notification arrived and was not
 * muted. Home is the screen people actually open, and a bid is the single most
 * time-sensitive thing in the app — money on the table, with another person
 * waiting at the other end.
 *
 * WHY IT IS A ROW AND NOT A CARD
 * Home has twice shed accreted cards on purpose: the Deal Agent card moved to
 * the Watchlist tab on 2026-08-11 to sit with the list it acts on, and the
 * "Extended Portfolio Insights" CTA was deleted so there is ONE route to
 * Analytics. Adding a permanent marketplace card back would reverse both
 * decisions. This renders `null` — no box, no border, no empty state — unless
 * something is genuinely waiting, so on the normal day Home is unchanged.
 *
 * AND WHY IT IS AT THE TOP
 * The obvious place was the bottom, under set progress and the ad slot. That is
 * the part of Home nobody scrolls to, and putting the most time-sensitive thing
 * in the app where it will not be read is worse than not adding it.
 *
 * THE COUNT MUST BE THE SAME COUNT (docs/ui-playbook.md, "a count in a badge is
 * a promise the destination has to keep"). It uses `countOffersNeedingAction`,
 * the exported helper — not a re-implementation — so this row, the marketplace
 * badge and the offers screen's own summary line cannot disagree about what
 * "needs you" means. The destination restates the number on arrival.
 */
import React, { useCallback, useState } from 'react';
import { Text, StyleSheet } from 'react-native';
import { useFocusEffect, useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { collectorsApi } from '@/api/collectorsApi';
import { countOffersNeedingAction } from '@/api/p2pApi';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';
import logger from '@/utils/logger';

export function OpenBidsRow() {
  const { colors } = useAppTheme();
  const router = useRouter();
  const [count, setCount] = useState(0);

  /**
   * `useFocusEffect`, NOT `useEffect`. Home is a tab and stays mounted, so a
   * mount-only fetch would count once and never again — you would tap the row,
   * answer all three bids, come back, and Home would still be advertising work
   * you had already done.
   *
   * `app/listings.tsx` had already learnt this for the same number ("the badge
   * is the reason to walk into /offers, so it has to be right when you walk
   * BACK out"), and the first version of this row reintroduced it a screen
   * over — which is why it is written out here rather than left implicit.
   *
   * Deliberately NOT wired into Home's pull-to-refresh: that would make the
   * offers list a dependency of the portfolio refresh, and a slow marketplace
   * call would hold up the numbers this screen actually exists for.
   */
  useFocusEffect(useCallback(() => {
    let cancelled = false;
    collectorsApi.p2pListOffers('all')
      .then((res) => {
        if (!cancelled) setCount(countOffersNeedingAction(res?.offers ?? []));
      })
      // Silent by design, and the only honest failure: a request that did not
      // come back cannot tell us there are zero bids, and zero is what this row
      // renders as nothing. `logger.error`, not warn — release builds strip
      // info/warn, so a warn here leaves nothing to find on the builds where
      // it matters (learning_prod_logger_strips_info_warn).
      .catch((e) => logger.error('[home] open bids count failed:', e));
    return () => { cancelled = true; };
  }, []));

  if (count < 1) return null;

  const label = count === 1 ? '1 bid needs you' : `${count} bids need you`;

  return (
    <AnimatedPressable
      onPress={() => router.push('/offers' as Href)}
      accessibilityRole="button"
      accessibilityLabel={`${label}. Opens your offers`}
      style={[styles.row, { backgroundColor: colors.accent + '14', borderColor: colors.accent + '33' }]}
    >
      <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
      <Text style={[styles.text, { color: colors.accent }]}>{label}</Text>
      <Ionicons name="chevron-forward" size={16} color={colors.accent} />
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
  },
  // `md`, not `sm`. docs/ui-playbook.md's type table puts BODY at md — status,
  // prose, button labels — and sm is the caption level for pills and passive
  // notes. This is neither: it is the one thing on Home asking to be acted on,
  // and a 12pt call to action next to 14pt body copy recedes below the thing
  // it is meant to outrank.
  //
  // `flex: 1` so the chevron is pinned right and the label takes the slack —
  // otherwise a one-bid label leaves the arrow floating mid-row.
  text: { flex: 1, fontSize: textToken.md, lineHeight: 19, fontWeight: fontWeight.semibold },
});
