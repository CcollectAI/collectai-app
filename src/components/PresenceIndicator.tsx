/**
 * PresenceIndicator — Shows a green/gray dot indicating if a user is online.
 * Optionally shows a text label ("Online", "5m ago", etc.).
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { dataProvider } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import type { UserPresence } from '@/data/types';
import { timeAgo } from '@/lib/timeAgo';

type Props = {
  userId: string;
  size?: number;
  showLabel?: boolean;
};

function formatLastSeen(dateStr: string): string {
  return timeAgo(dateStr);
}

export function PresenceIndicator({ userId, size = 10, showLabel = false }: Props) {
  const { colors } = useAppTheme();
  const [presence, setPresence] = useState<UserPresence | null>(null);

  useEffect(() => {
    let cancelled = false;
    dataProvider.getUserPresence(userId).then((p) => {
      if (!cancelled) setPresence(p);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [userId]);

  const isOnline = presence?.isOnline ?? false;

  return (
    <View style={styles.container}>
      <View
        style={[
          styles.dot,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            backgroundColor: isOnline ? '#22C55E' : colors.muted,
          },
        ]}
      />
      {showLabel && (
        <Text style={[styles.label, { color: colors.muted }]}>
          {isOnline ? 'Online' : presence?.lastSeenAt ? formatLastSeen(presence.lastSeenAt) : 'Offline'}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  dot: {},
  label: {
    fontSize: 11,
    fontWeight: '500',
  },
});
