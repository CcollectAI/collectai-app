import React from 'react';
import { View, Text } from 'react-native';
import type { Tier, CollectionStatusScore } from '@/utils/statusScoring';

interface StatusBadgeProps {
  tier: Tier;
  compact?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  tier,
  compact = false,
}) => {
  const label = tier.toUpperCase();
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
        borderColor:
          tier === 'Diamond'
            ? '#00bcd4'
            : tier === 'Gold'
            ? '#c9a800'
            : '#9e9e9e',
      }}
    >
      <Text
        style={{
          fontSize: compact ? 10 : 12,
          fontWeight,
          color:
            tier === 'Diamond'
              ? '#00bcd4'
              : tier === 'Gold'
              ? '#c9a800'
              : '#616161',
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
          color: '#424242',
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
            color: '#212121',
          }}
        >
          {score.key}
        </Text>
        <Text
          style={{
            fontSize: 11,
            color: '#757575',
          }}
        >
          {score.category} · {score.ownedCount}/{score.expectedCount} items
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
            color: '#424242',
          }}
        >
          {score.points.toFixed(0)} pts
        </Text>
        <Text
          style={{
            fontSize: 10,
            color: '#9e9e9e',
          }}
        >
          R {Math.round(score.rarityScore * 100)} · C{' '}
          {Math.round(score.completenessRatio * 100)}
        </Text>
      </View>
    </View>
  );
};
