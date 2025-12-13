import React, { useMemo } from 'react';
import { View, Text } from 'react-native';
import {
  CollectionStatusInput,
  CollectionStatusScore,
  computeCollectionStatusScores,
} from '@/utils/statusScoring';
import { StatusBadge } from '@/components/StatusBadge';

interface Props {
  /** All items belonging to the same logical collection as the detail item. */
  collectionItems: CollectionStatusInput[];
  /** Optional: the specific item being viewed (for highlighting). */
  currentItemId?: string | number | null;
}

/**
 * Computes the single CollectionStatusScore for the given collection key.
 */
function getCollectionScore(
  items: CollectionStatusInput[],
): CollectionStatusScore | null {
  const scores = computeCollectionStatusScores(items);
  if (!scores.length) return null;
  // assuming a single collection; take the first score
  return scores[0];
}

export const ItemStatusInspector: React.FC<Props> = ({
  collectionItems,
  currentItemId,
}) => {
  const score = useMemo(
    () => getCollectionScore(collectionItems),
    [collectionItems],
  );

  const currentIndex = useMemo(() => {
    if (currentItemId == null) return null;
    const idx = collectionItems.findIndex(
      (it) => it.id === currentItemId,
    );
    return idx >= 0 ? idx : null;
  }, [collectionItems, currentItemId]);

  if (!score) {
    return (
      <View
        style={{
          marginTop: 12,
          padding: 12,
          borderRadius: 12,
          backgroundColor: '#f3f4f6',
        }}
      >
        <Text
          style={{
            fontSize: 13,
            fontWeight: '600',
            marginBottom: 4,
          }}
        >
          Collection status
        </Text>
        <Text
          style={{
            fontSize: 11,
            color: '#4b5563',
          }}
        >
          Not enough data yet to compute status for this collection.
        </Text>
      </View>
    );
  }

  const completenessPct = Math.round(score.completenessRatio * 100);
  const rarityPct = Math.round(score.rarityScore * 100);
  const missing = Math.max(0, score.expectedCount - score.ownedCount);

  return (
    <View
      style={{
        marginTop: 12,
        padding: 12,
        borderRadius: 12,
        backgroundColor: '#ffffff',
      }}
    >
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          marginBottom: 4,
        }}
      >
        <Text
          style={{
            flex: 1,
            fontSize: 13,
            fontWeight: '700',
            color: '#0f172a',
          }}
        >
          Collection status
        </Text>
        <StatusBadge tier={score.tier} />
      </View>

      <Text
        style={{
          fontSize: 11,
          color: '#6b7280',
          marginBottom: 6,
        }}
      >
        {score.key} · {score.category}
      </Text>

      <View
        style={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          marginBottom: 4,
        }}
      >
        <View style={{ flex: 1, marginRight: 8 }}>
          <Text
            style={{
              fontSize: 11,
              fontWeight: '600',
              color: '#111827',
            }}
          >
            Completeness
          </Text>
          <Text
            style={{
              fontSize: 11,
              color: '#6b7280',
            }}
          >
            {score.ownedCount}/{score.expectedCount} items ·{' '}
            {completenessPct}%
          </Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text
            style={{
              fontSize: 11,
              fontWeight: '600',
              color: '#111827',
            }}
          >
            Rarity impact
          </Text>
          <Text
            style={{
              fontSize: 11,
              color: '#6b7280',
            }}
          >
            Rarity score {rarityPct}/100
          </Text>
        </View>
      </View>

      <Text
        style={{
          fontSize: 11,
          color: '#4b5563',
          marginTop: 2,
        }}
      >
        Missing items: {missing}. Completing this set increases your points
        and strengthens your tier.
      </Text>

      {currentIndex != null && (
        <Text
          style={{
            fontSize: 11,
            color: '#9ca3af',
            marginTop: 2,
          }}
        >
          This item is #{currentIndex + 1} in your tracked items for this
          collection.
        </Text>
      )}
    </View>
  );
};

export default ItemStatusInspector;
