import React, { useMemo } from 'react';
import { View, Text } from 'react-native';
import {
  CollectionStatusInput,
  CollectionStatusScore,
} from '@/utils/statusScoring';
import { useCollectionStatus } from '@/hooks/useCollectionStatus';
import { LeaderboardRow } from '@/components/StatusBadge';

interface Props {
  items: CollectionStatusInput[];
}

export const SearchStatusPanel: React.FC<Props> = ({ items }) => {
  const { scores, tier } = useCollectionStatus(items);

  const nearComplete: CollectionStatusScore[] = useMemo(
    () =>
      scores
        .filter(
          (s) =>
            s.completenessRatio >= 0.4 &&
            s.completenessRatio < 0.95 &&
            s.expectedCount > 0,
        )
        .sort(
          (a, b) =>
            b.completenessRatio - a.completenessRatio ||
            b.valueTotal - a.valueTotal,
        )
        .slice(0, 5),
    [scores],
  );

  const leaderboardTop = scores.slice(0, 5);

  return (
    <View style={{ marginHorizontal: 16, marginVertical: 8 }}>
      {/* Leaders & sets card */}
      <View
        style={{
          padding: 12,
          borderRadius: 12,
          backgroundColor: '#ffffff',
          marginBottom: 10,
        }}
      >
        <Text
          style={{
            fontSize: 14,
            fontWeight: '700',
            color: '#0f172a',
            marginBottom: 6,
          }}
        >
          Leaders & sets
        </Text>
        {leaderboardTop.length === 0 ? (
          <Text
            style={{
              fontSize: 11,
              color: '#6b7280',
            }}
          >
            Add items to build up your leaderboard and see which sets you are
            closest to completing.
          </Text>
        ) : (
          <>
            <Text
              style={{
                fontSize: 11,
                color: '#6b7280',
                marginBottom: 4,
              }}
            >
              Your tier: {tier} · Local top collections
            </Text>
            {leaderboardTop.map((s, idx) => (
              <LeaderboardRow
                key={s.key}
                rank={idx + 1}
                score={s}
              />
            ))}
          </>
        )}
      </View>

      {/* Sets to complete card */}
      <View
        style={{
          padding: 12,
          borderRadius: 12,
          backgroundColor: '#ffffff',
          marginBottom: 10,
        }}
      >
        <Text
          style={{
            fontSize: 14,
            fontWeight: '700',
            color: '#0f172a',
            marginBottom: 6,
          }}
        >
          Sets to complete
        </Text>
        {nearComplete.length === 0 ? (
          <Text
            style={{
              fontSize: 11,
              color: '#6b7280',
            }}
          >
            No sets are near completion yet. Once you are 40–95% complete on a
            set, it will show up here.
          </Text>
        ) : (
          nearComplete.map((s) => {
            const missing = Math.max(
              0,
              s.expectedCount - s.ownedCount,
            );
            return (
              <View key={s.key} style={{ marginBottom: 6 }}>
                <Text
                  style={{
                    fontSize: 13,
                    fontWeight: '600',
                    color: '#111827',
                  }}
                >
                  {s.key}
                </Text>
                <Text
                  style={{
                    fontSize: 11,
                    color: '#6b7280',
                  }}
                >
                  {s.category} · {s.ownedCount}/{s.expectedCount} · Missing{' '}
                  {missing}
                </Text>
              </View>
            );
          })
        )}
      </View>

      {/* Fraud Watch placeholder card (data will come from backend later) */}
      <View
        style={{
          padding: 12,
          borderRadius: 12,
          backgroundColor: '#f9fafb',
        }}
      >
        <Text
          style={{
            fontSize: 14,
            fontWeight: '700',
            color: '#0f172a',
            marginBottom: 6,
          }}
        >
          Fraud Watch (coming from scans)
        </Text>
        <Text
          style={{
            fontSize: 11,
            color: '#6b7280',
          }}
        >
          As you and other users run anti-fraud scans during purchases, this
          section will surface high-risk sets, items, and patterns to watch
          out for.
        </Text>
      </View>
    </View>
  );
};

export default SearchStatusPanel;
