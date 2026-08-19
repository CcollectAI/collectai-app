import React, { useMemo } from 'react';
import { View, Text } from 'react-native';
import {
  CollectionStatusInput,
  SizedCollectionScore,
  hasKnownSetSize,
} from '@/utils/statusScoring';
import { useCollectionStatus } from '@/hooks/useCollectionStatus';
import { LeaderboardRow } from '@/components/StatusBadge';
import { useAppTheme } from '@/hooks/useAppTheme';

interface Props {
  items: CollectionStatusInput[];
}

export const SearchStatusPanel: React.FC<Props> = ({ items }) => {
  const { scores, tier } = useCollectionStatus(items);
  const { colors } = useAppTheme();

  // Same 0.4..0.95 band as app/sets-to-complete.tsx — a second copy of that
  // predicate, and it was dead for the same reason: with no catalogue set size
  // every score came back at exactly 1.0 and fell outside the band. Sets whose
  // size we do not know are excluded up front now, rather than being given an
  // invented denominator (see hasKnownSetSize).
  const nearComplete: SizedCollectionScore[] = useMemo(
    () =>
      scores
        .filter(hasKnownSetSize)
        .filter(
          (s) =>
            s.completenessRatio >= 0.4 &&
            s.completenessRatio < 0.95,
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
          backgroundColor: colors.card,
          marginBottom: 10,
        }}
      >
        <Text
          style={{
            fontSize: 14,
            fontWeight: '700',
            color: colors.text,
            marginBottom: 6,
          }}
        >
          Leaders & sets
        </Text>
        {leaderboardTop.length === 0 ? (
          <Text
            style={{
              fontSize: 11,
              color: colors.muted,
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
                color: colors.muted,
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
          backgroundColor: colors.card,
          marginBottom: 10,
        }}
      >
        <Text
          style={{
            fontSize: 14,
            fontWeight: '700',
            color: colors.text,
            marginBottom: 6,
          }}
        >
          Sets to complete
        </Text>
        {nearComplete.length === 0 ? (
          <Text
            style={{
              fontSize: 11,
              color: colors.muted,
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
                    color: colors.text,
                  }}
                >
                  {s.key}
                </Text>
                <Text
                  style={{
                    fontSize: 11,
                    color: colors.muted,
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
          backgroundColor: colors.card,
        }}
      >
        <Text
          style={{
            fontSize: 14,
            fontWeight: '700',
            color: colors.text,
            marginBottom: 6,
          }}
        >
          Fraud Watch (coming from scans)
        </Text>
        <Text
          style={{
            fontSize: 11,
            color: colors.muted,
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
