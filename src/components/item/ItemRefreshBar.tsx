/**
 * ItemRefreshBar — Compact AI action bar showing last analysis time and refresh button.
 */
import React from 'react';
import { View, Text, Pressable, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { timeAgo } from '@/lib/timeAgo';

interface ItemRefreshBarProps {
  predictionAt: string | null | undefined;
  aiRefreshing: boolean;
  onRefresh: () => void;
}

const relativeTime = (iso: string | null | undefined): string => {
  if (!iso) return '';
  return timeAgo(iso);
};

export const ItemRefreshBar = React.memo(function ItemRefreshBar({ predictionAt, aiRefreshing, onRefresh }: ItemRefreshBarProps) {
  const { colors: theme } = useAppTheme();

  return (
    <View style={[styles.refreshBar, { borderTopColor: theme.border }]}>
      <View style={styles.refreshBarLeft}>
        <Ionicons name="sparkles" size={16} color={theme.accent} />
        <Text style={[styles.refreshBarLabel, { color: theme.muted }]}>
          {/* The fallback states the STATUS, not the brand. It read
              'Powered by Sparrow Collect' until 2026-08-30. That is the same
              byline removed from the unpriced valuation block on 08-27 for the
              same reason — "the one row with any emphasis on it was our own
              brand name, on a card that had failed to answer its only
              question" — and it came straight back on the same screen through a
              different component, because the earlier fix edited the block and
              not this bar. Both render when there is no prediction, so the user
              saw the byline in exactly the state it was removed from. */}
          {predictionAt
            ? `Last analyzed ${relativeTime(predictionAt)}`
            : 'Not analyzed yet'}
        </Text>
      </View>
      <Pressable
        onPress={onRefresh}
        disabled={aiRefreshing}
        style={[
          styles.refreshBarBtn,
          { backgroundColor: theme.accent + '14', opacity: aiRefreshing ? 0.7 : 1 },
        ]}
        accessibilityRole="button"
        accessibilityLabel="Refresh all intelligence data"
      >
        {aiRefreshing ? (
          <ActivityIndicator size="small" color={theme.accent} />
        ) : (
          <Ionicons name="refresh-outline" size={14} color={theme.accent} />
        )}
        <Text style={[styles.refreshBarBtnText, { color: theme.accent }]}>
          {aiRefreshing ? 'Updating...' : 'Refresh'}
        </Text>
      </Pressable>
    </View>
  );
});

const styles = StyleSheet.create({
  refreshBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderTopWidth: StyleSheet.hairlineWidth,
    marginTop: 4,
  },
  refreshBarLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flexShrink: 1,
  },
  refreshBarLabel: {
    fontSize: 12,
    fontWeight: '500',
  },
  refreshBarBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
  },
  refreshBarBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
