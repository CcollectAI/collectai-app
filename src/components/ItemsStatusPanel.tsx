import React, { useMemo } from 'react';
import { View, Text } from 'react-native';
import {
  CollectionStatusInput,
  computeCollectionStatusScores,
  computeOverallTier,
} from '@/utils/statusScoring';
import { LeaderboardRow, StatusBadge } from '@/components/StatusBadge';
import { useAppTheme } from '@/hooks/useAppTheme';

interface Props {
  items: CollectionStatusInput[];
}

export const ItemsStatusPanel: React.FC<Props> = ({ items }) => {
  const scores = useMemo(
    () => computeCollectionStatusScores(items),
    [items],
  );

  const { tier, avgPoints } = useMemo(
    () => computeOverallTier(scores),
    [scores],
  );

  const { colors } = useAppTheme();

  if (!items.length) {
    return (
      <View
        style={{
          marginHorizontal: 16,
          marginVertical: 8,
          padding: 12,
          borderRadius: 12,
          backgroundColor: colors.brand.lighter,
        }}
      >
        <Text
          style={{
            fontSize: 13,
            fontWeight: '600',
            marginBottom: 4,
            color: colors.text,
          }}
        >
          Status & leaderboard
        </Text>
        <Text
          style={{
            fontSize: 11,
            color: colors.text,
          }}
        >
          Start adding items to see your collection status, tiers, and
          leaderboard position.
        </Text>
      </View>
    );
  }

  const top = scores.slice(0, 5);

  return (
    <View style={{ marginHorizontal: 16, marginVertical: 8 }}>
      {/* Self status card */}
      <View
        style={{
          marginBottom: 10,
          padding: 12,
          borderRadius: 12,
          backgroundColor: colors.card,
        }}
      >
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            marginBottom: 6,
          }}
        >
          <Text
            style={{
              flex: 1,
              fontSize: 14,
              fontWeight: '700',
              color: colors.text,
            }}
          >
            Your collector status
          </Text>
          <StatusBadge tier={tier} />
        </View>
        <Text
          style={{
            fontSize: 11,
            color: colors.muted,
          }}
        >
          Avg points across your collections:{' '}
          {avgPoints.toFixed(0)} pts
        </Text>
        {scores.length > 1 && (
          <Text
            style={{
              marginTop: 2,
              fontSize: 11,
              color: colors.muted,
            }}
          >
            Based on completeness (sets finished) and rarity of items
            you own.
          </Text>
        )}
      </View>

      {/* Leaderboard card */}
      <View
        style={{
          padding: 12,
          borderRadius: 12,
          backgroundColor: colors.card,
        }}
      >
        <Text
          style={{
            fontSize: 14,
            fontWeight: '700',
            marginBottom: 6,
            color: colors.text,
          }}
        >
          Top collections (local)
        </Text>
        {top.map((score, idx) => (
          <LeaderboardRow
            key={score.key}
            rank={idx + 1}
            score={score}
          />
        ))}
        {scores.length > 5 && (
          <Text
            style={{
              marginTop: 4,
              fontSize: 11,
              color: colors.muted,
            }}
          >
            Showing top {top.length} of {scores.length} collections
            on this device.
          </Text>
        )}
      </View>
    </View>
  );
};

export default ItemsStatusPanel;
