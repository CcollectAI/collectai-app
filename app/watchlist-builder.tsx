import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  Share,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Stack } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';
import { useSession } from '@/hooks/useSession';
import {
  fetchWatchlistForUser,
  upsertWatchlistItem,
  deleteWatchlistItem,
  type WatchlistItem,
  type WatchlistPriority,
} from '@/services/watchlistAndAlerts';

type SortMode = 'added' | 'rank' | 'priority';

const PRIORITY_OPTIONS: WatchlistPriority[] = [
  'high',
  'medium',
  'low',
];

export default function WatchlistBuilderScreen() {
  const { colors, spacing, radii } = useAppTheme();
  const { user } = useSession();

  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [sortMode, setSortMode] = useState<SortMode>('added');
  const [error, setError] = useState<string | null>(null);

  const [newTitle, setNewTitle] = useState('');
  const [newPriority, setNewPriority] =
    useState<WatchlistPriority>('high');
  const [newRank, setNewRank] = useState<string>('1');
  const [saving, setSaving] = useState(false);

  const userId = user?.id ?? '';

  const loadWatchlist = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWatchlistForUser(userId);
      setItems(data);
    } catch (err: any) {
      console.warn('[watchlist-builder] load error', err);
      setError(
        err?.message ?? 'Unable to load your watchlist right now.',
      );
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadWatchlist();
  }, [loadWatchlist]);

  const sortedItems = useMemo(() => {
    const copy = [...items];
    if (sortMode === 'rank') {
      return copy.sort((a, b) => {
        const ra = a.rank ?? 9999;
        const rb = b.rank ?? 9999;
        if (ra === rb) {
          return a.created_at.localeCompare(b.created_at);
        }
        return ra - rb;
      });
    }
    if (sortMode === 'priority') {
      const order: Record<WatchlistPriority, number> = {
        high: 0,
        medium: 1,
        low: 2,
      };
      return copy.sort((a, b) => {
        const pa =
          order[(a.priority ?? 'medium') as WatchlistPriority] ?? 1;
        const pb =
          order[(b.priority ?? 'medium') as WatchlistPriority] ?? 1;
        if (pa === pb) {
          return a.created_at.localeCompare(b.created_at);
        }
        return pa - pb;
      });
    }
    return copy.sort((a, b) =>
      a.created_at.localeCompare(b.created_at),
    );
  }, [items, sortMode]);

  const topFive = useMemo(
    () =>
      sortedItems
        .filter((it) => typeof it.rank === 'number')
        .sort(
          (a, b) =>
            (a.rank ?? 9999) - (b.rank ?? 9999),
        )
        .slice(0, 5),
    [sortedItems],
  );

  const handleSaveNew = useCallback(async () => {
    if (!userId) {
      Alert.alert(
        'Not signed in',
        'You need to be signed in to save a watchlist.',
      );
      return;
    }
    const title = newTitle.trim();
    if (!title) {
      Alert.alert(
        'Missing title',
        'Add a short title for this watchlist entry (e.g. PSA 9 Charizard).',
      );
      return;
    }

    let rank: number | null = null;
    if (newRank.trim().length) {
      const parsed = Number(newRank.trim());
      if (!Number.isFinite(parsed) || parsed <= 0) {
        Alert.alert(
          'Invalid rank',
          'Rank should be a positive number (1 = top priority).',
        );
        return;
      }
      rank = parsed;
    }

    setSaving(true);
    try {
      const created = await upsertWatchlistItem({
        user_id: userId,
        title,
        rank,
        priority: newPriority,
        owned: false,
        currency: 'EUR',
      });
      if (!created) {
        Alert.alert(
          'Save failed',
          'Could not save this entry. Please try again.',
        );
        return;
      }
      setNewTitle('');
      setNewRank(
        typeof created.rank === 'number'
          ? String(created.rank + 1)
          : '',
      );
      await loadWatchlist();
    } catch (err: any) {
      console.warn('[watchlist-builder] save error', err);
      Alert.alert(
        'Save error',
        err?.message ?? 'Unable to save this entry.',
      );
    } finally {
      setSaving(false);
    }
  }, [loadWatchlist, newPriority, newRank, newTitle, userId]);

  const handleDelete = useCallback(
    async (id: string) => {
      const ok = await deleteWatchlistItem(id);
      if (!ok) {
        Alert.alert(
          'Delete failed',
          'Could not delete this watchlist entry.',
        );
        return;
      }
      await loadWatchlist();
    },
    [loadWatchlist],
  );

  const handleShare = useCallback(async () => {
    if (!sortedItems.length) {
      Alert.alert(
        'Nothing to share yet',
        'Add at least one item to your watchlist before sharing.',
      );
      return;
    }

    const lines: string[] = [];
    lines.push('My collector watchlist:');

    const listForShare = sortedItems.slice(0, 20);

    listForShare.forEach((item, index) => {
      const rankDisplay =
        typeof item.rank === 'number'
          ? item.rank
          : index + 1;
      const priorityLabel =
        item.priority === 'high'
          ? 'HIGH'
          : item.priority === 'low'
          ? 'LOW'
          : 'MED';
      lines.push(
        `${rankDisplay}. ${item.title} [${priorityLabel}]`,
      );
    });

    const message = lines.join('\n');

    try {
      await Share.share({
        message,
      });
    } catch (err: any) {
      console.warn('[watchlist-builder] share error', err);
      Alert.alert(
        'Share error',
        err?.message ?? 'Unable to open the share sheet.',
      );
    }
  }, [sortedItems]);

  const renderSortButton = (
    mode: SortMode,
    label: string,
  ) => {
    const active = sortMode === mode;
    return (
      <TouchableOpacity
        onPress={() => setSortMode(mode)}
        style={{
          paddingHorizontal: spacing.sm,
          paddingVertical: spacing.xs,
          borderRadius: radii.full,
          borderWidth: 1,
          borderColor: active ? colors.primary : colors.border,
          backgroundColor: active
            ? colors.primarySoft ?? '#e0f2fe'
            : colors.card,
          marginRight: spacing.xs,
        }}
      >
        <Text
          style={{
            fontSize: 12,
            fontWeight: active ? '600' : '400',
            color: active ? colors.primary : colors.text,
          }}
        >
          {label}
        </Text>
      </TouchableOpacity>
    );
  };

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Watchlist',
          headerRight: () => (
            <TouchableOpacity
              onPress={handleShare}
              style={{ paddingHorizontal: spacing.md }}
            >
              <Text
                style={{
                  fontSize: 13,
                  fontWeight: '600',
                  color: colors.primary,
                }}
              >
                Share
              </Text>
            </TouchableOpacity>
          ),
        }}
      />
      <ScrollView
        style={{
          flex: 1,
          backgroundColor: colors.background,
        }}
        contentContainerStyle={{
          padding: spacing.lg,
          paddingBottom: spacing.xl * 2,
        }}
      >
        {/* Intro */}
        <View
          style={{
            marginBottom: spacing.md,
          }}
        >
          <Text
            style={{
              fontSize: 18,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.xs,
            }}
          >
            Investor watchlist
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            Track items you care about most — owned or not. Rank your
            top 5, set a priority, and share your list with friends or
            future you.
          </Text>
        </View>

        {/* New entry card */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
            marginBottom: spacing.md,
          }}
        >
          <Text
            style={{
              fontSize: 15,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.sm,
            }}
          >
            Add to watchlist
          </Text>

          <View style={{ marginBottom: spacing.sm }}>
            <Text
              style={{
                fontSize: 12,
                color: colors.mutedText,
                marginBottom: 4,
              }}
            >
              Title
            </Text>
            <TextInput
              value={newTitle}
              onChangeText={setNewTitle}
              placeholder="e.g. PSA 9 Charizard Base, sealed LEGO UCS Falcon"
              placeholderTextColor={colors.mutedText}
              style={{
                borderRadius: radii.md,
                borderWidth: 1,
                borderColor: colors.border,
                paddingHorizontal: spacing.sm,
                paddingVertical: spacing.xs,
                fontSize: 14,
                color: colors.text,
              }}
            />
          </View>

          <View
            style={{
              flexDirection: 'row',
              marginBottom: spacing.sm,
            }}
          >
            <View style={{ flex: 1, marginRight: spacing.sm }}>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginBottom: 4,
                }}
              >
                Rank (1 = top)
              </Text>
              <TextInput
                value={newRank}
                onChangeText={setNewRank}
                keyboardType="number-pad"
                placeholder="1"
                placeholderTextColor={colors.mutedText}
                style={{
                  borderRadius: radii.md,
                  borderWidth: 1,
                  borderColor: colors.border,
                  paddingHorizontal: spacing.sm,
                  paddingVertical: spacing.xs,
                  fontSize: 14,
                  color: colors.text,
                }}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginBottom: 4,
                }}
              >
                Priority
              </Text>
              <View style={{ flexDirection: 'row' }}>
                {PRIORITY_OPTIONS.map((p) => {
                  const active = newPriority === p;
                  const label =
                    p === 'high' ? 'High' : p === 'low' ? 'Low' : 'Medium';
                  return (
                    <TouchableOpacity
                      key={p}
                      onPress={() =>
                        setNewPriority(p as WatchlistPriority)
                      }
                      style={{
                        paddingHorizontal: spacing.sm,
                        paddingVertical: spacing.xs,
                        borderRadius: radii.full,
                        borderWidth: 1,
                        borderColor: active
                          ? colors.primary
                          : colors.border,
                        backgroundColor: active
                          ? colors.primarySoft ?? '#e0f2fe'
                          : colors.card,
                        marginRight: spacing.xs,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 12,
                          fontWeight: active ? '600' : '400',
                          color: active
                            ? colors.primary
                            : colors.text,
                        }}
                      >
                        {label}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>
          </View>

          <TouchableOpacity
            onPress={handleSaveNew}
            disabled={saving}
            style={{
              marginTop: spacing.sm,
              borderRadius: radii.full,
              backgroundColor: colors.primary,
              paddingVertical: spacing.sm,
              alignItems: 'center',
              opacity: saving ? 0.7 : 1,
            }}
          >
            {saving ? (
              <ActivityIndicator size="small" color={colors.onPrimary} />
            ) : (
              <Text
                style={{
                  color: colors.onPrimary,
                  fontWeight: '600',
                  fontSize: 14,
                }}
              >
                Add to watchlist
              </Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Sort + top 5 highlight */}
        <View
          style={{
            marginBottom: spacing.md,
          }}
        >
          <View
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
              marginBottom: spacing.xs,
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: colors.text,
              }}
            >
              Your list
            </Text>
            <View style={{ flexDirection: 'row' }}>
              {renderSortButton('added', 'Added date')}
              {renderSortButton('rank', 'Rank')}
              {renderSortButton('priority', 'Priority')}
            </View>
          </View>
          {loading && (
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
              }}
            >
              <ActivityIndicator size="small" />
              <Text
                style={{
                  marginLeft: spacing.xs,
                  fontSize: 12,
                  color: colors.mutedText,
                }}
              >
                Loading…
              </Text>
            </View>
          )}
          {error && (
            <Text
              style={{
                fontSize: 12,
                color: colors.error ?? '#B00020',
              }}
            >
              {error}
            </Text>
          )}
          {!loading && !sortedItems.length && !error && (
            <Text
              style={{
                fontSize: 12,
                color: colors.mutedText,
              }}
            >
              No items yet. Add a few targets above — think of this as
              your top 5–20 focus list as a collector-investor.
            </Text>
          )}

          {topFive.length > 0 && (
            <View
              style={{
                marginTop: spacing.sm,
                marginBottom: spacing.xs,
                padding: spacing.sm,
                borderRadius: radii.md,
                backgroundColor:
                  colors.primarySoft ?? '#e0f2fe',
              }}
            >
              <Text
                style={{
                  fontSize: 12,
                  fontWeight: '600',
                  color: colors.primary,
                  marginBottom: 2,
                }}
              >
                Top 5 focus picks
              </Text>
              <Text
                style={{
                  fontSize: 11,
                  color: colors.mutedText,
                }}
              >
                These are the highest-ranked entries (rank 1–5). You
                can reorder priorities by editing their rank.
              </Text>
            </View>
          )}
        </View>

        {/* Full list */}
        {sortedItems.map((item, index) => {
          const rankDisplay =
            typeof item.rank === 'number'
              ? item.rank
              : index + 1;
          const priorityLabel =
            item.priority === 'high'
              ? 'High'
              : item.priority === 'low'
              ? 'Low'
              : 'Medium';
          const priorityColor =
            item.priority === 'high'
              ? colors.error ?? '#B00020'
              : item.priority === 'low'
              ? colors.mutedText
              : colors.warning ?? '#C77C00';

          return (
            <View
              key={item.id}
              style={{
                borderRadius: radii.md,
                backgroundColor: colors.card,
                padding: spacing.sm,
                marginBottom: spacing.xs,
                flexDirection: 'row',
                alignItems: 'center',
              }}
            >
              <View style={{ marginRight: spacing.sm }}>
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: '700',
                    color: colors.text,
                  }}
                >
                  {rankDisplay}.
                </Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: '600',
                    color: colors.text,
                  }}
                  numberOfLines={1}
                >
                  {item.title}
                </Text>
                <Text
                  style={{
                    fontSize: 11,
                    color: colors.mutedText,
                    marginTop: 2,
                  }}
                  numberOfLines={1}
                >
                  Priority:{' '}
                  <Text style={{ color: priorityColor }}>
                    {priorityLabel}
                  </Text>
                  {item.owned ? ' · Owned' : ' · Not owned'}
                </Text>
              </View>
              <TouchableOpacity
                onPress={() =>
                  Alert.alert(
                    'Remove entry',
                    'Remove this from your watchlist?',
                    [
                      { text: 'Cancel', style: 'cancel' },
                      {
                        text: 'Remove',
                        style: 'destructive',
                        onPress: () => handleDelete(item.id),
                      },
                    ],
                  )
                }
                style={{
                  paddingHorizontal: spacing.sm,
                  paddingVertical: spacing.xs,
                }}
              >
                <Text
                  style={{
                    fontSize: 12,
                    color: colors.mutedText,
                  }}
                >
                  Remove
                </Text>
              </TouchableOpacity>
            </View>
          );
        })}
      </ScrollView>
    </>
  );
}
