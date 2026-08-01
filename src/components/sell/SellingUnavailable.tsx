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
import { Stack } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { EmptyState } from '@/components/EmptyState';
import { QuickNavBar } from '@/components/QuickNavBar';

export function SellingUnavailable({ title = 'Selling' }: { title?: string }) {
  const { colors } = useAppTheme();
  return (
    <View style={{ flex: 1, backgroundColor: colors.background }}>
      <Stack.Screen options={{ title }} />
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
