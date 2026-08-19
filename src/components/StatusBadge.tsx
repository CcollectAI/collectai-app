import React from 'react';
import { View, Text } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import type { Tier, CollectionStatusScore } from '@/utils/statusScoring';

const TIER_COLORS: Record<string, string> = {
  Diamond: '#00bcd4',
  Gold: '#c9a800',
  Silver: '#9e9e9e',
};

interface StatusBadgeProps {
  tier: Tier;
  compact?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  tier,
  compact = false,
}) => {
  const label = tier.toUpperCase();
  const tierColor = TIER_COLORS[tier] ?? '#9e9e9e';
  let borderWidth = 1;
  let fontWeight: '400' | '600' | '700' = '600';

  if (tier === 'Diamond') {
    borderWidth = 2;
    fontWeight = '700';
  }

  return (
    <View
      style={{
        borderWidth,
        borderRadius: 999,
        paddingHorizontal: compact ? 8 : 10,
        paddingVertical: compact ? 2 : 4,
        borderColor: tierColor,
      }}
    >
      <Text
        style={{
          fontSize: compact ? 10 : 12,
          fontWeight,
          color: tierColor,
        }}
      >
        {label}
      </Text>
    </View>
  );
};

interface LeaderboardRowProps {
  rank: number;
  score: CollectionStatusScore;
}

export const LeaderboardRow: React.FC<LeaderboardRowProps> = ({
  rank,
  score,
}) => {
  const { colors } = useAppTheme();

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        paddingVertical: 6,
      }}
    >
      <Text
        style={{
          width: 20,
          fontSize: 12,
          fontWeight: '600',
          color: colors.muted,
        }}
      >
        {rank}.
      </Text>
      <View style={{ flex: 1 }}>
        <Text
          numberOfLines={1}
          style={{
            fontSize: 13,
            fontWeight: '600',
            color: colors.text,
          }}
        >
          {score.key}
        </Text>
        <Text
          style={{
            fontSize: 11,
            color: colors.muted,
          }}
        >
          {/* "12/? items" when we hold no catalogue row for the set. Rendering
              "12/null" or quietly printing "12/12" would both state a set size
              we do not have. */}
          {score.category} · {score.ownedCount}/{score.expectedCount ?? '?'} items
        </Text>
      </View>
      <View style={{ marginHorizontal: 8 }}>
        <StatusBadge tier={score.tier} compact />
      </View>
      <View style={{ alignItems: 'flex-end', minWidth: 60 }}>
        <Text
          style={{
            fontSize: 11,
            fontWeight: '600',
            color: colors.muted,
          }}
        >
          {score.points.toFixed(0)} pts
        </Text>
        <Text
          style={{
            fontSize: 10,
            color: colors.muted,
          }}
        >
          R {Math.round(score.rarityScore * 100)} · C{' '}
          {score.completenessRatio === null
            ? '—'
            : Math.round(score.completenessRatio * 100)}
        </Text>
      </View>
    </View>
  );
};
