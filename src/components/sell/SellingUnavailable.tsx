/**
 * SellingUnavailable — the gate shown in place of every /sell/* screen while
 * `SELLING_ENABLED` is false.
 *
 * Applied in each route's default export (the `*WithBoundary` wrapper) so the
 * real screen never mounts and its data fetches never fire for a feature the
 * user cannot complete.
 *
 * Gating the SCREENS rather than only hiding entry points is deliberate:
 * `/sell/*` is reachable by deep link even with every button hidden — the same
 * shape as the free-tier purchase mandates, which were unreachable in the UI
 * yet reachable via a Universal Link (docs/MONETIZATION.md). The buttons are
 * hidden too, so nobody walks into a wall; this is the backstop.
 */

import React from 'react';
import { View } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { EmptyState } from '@/components/EmptyState';
import { QuickNavBar } from '@/components/QuickNavBar';

/**
 * No `title` prop (2026-09-17). It used to take one and feed it to
 * `Stack.Screen options={{ title }}`, and `app/_layout.tsx`'s icon-only header
 * sets `headerTitle: ''` for these routes — so the string was never drawn
 * anywhere. Two routes passed two different titles ("eBay Defaults", the
 * dashboard's) and rendered byte-identical screens; the screen sweep caught it
 * as SAME_AS_PREVIOUS, which is exactly what a member sees: no way to tell the
 * two apart. The shared message is deliberate, the dead prop was not.
 */
export function SellingUnavailable() {
  const { colors } = useAppTheme();
  return (
    <View style={{ flex: 1, backgroundColor: colors.background }}>
      <EmptyState
        icon="construct-outline"
        title="Selling is coming soon"
        subtitle="Listing your collection across eBay, Mercari and Cardmarket is still being built. We'll turn it on once marketplace accounts can be connected."
        colors={colors}
        style={{ flex: 1 }}
      />
      <QuickNavBar />
    </View>
  );
}
