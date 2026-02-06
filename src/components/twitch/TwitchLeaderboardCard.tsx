import React from 'react';
import { View, Text, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/theme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';

type TwitchCategory = 'tcg' | 'painting' | 'gunpla' | 'designer_toys';

type TwitchStreamer = {
  id: string;
  handle: string;
  displayName: string;
  category: TwitchCategory;
  viewers: number;
  isLive: boolean;
  completionScore: number; // 0–100
  rarityScore: number; // 0–100
  tier: 'Diamond' | 'Gold' | 'Silver';
  sampleItem: string; // Example item relevant to the stream
  note: string; // Why this matters for collectors
};

const MOCK_STREAMERS: TwitchStreamer[] = [
  {
    id: 's1',
    handle: 'cardboard_quarterly',
    displayName: 'Cardboard Quarterly',
    category: 'tcg',
    viewers: 780,
    isLive: true,
    completionScore: 92,
    rarityScore: 88,
    tier: 'Diamond',
    sampleItem: 'PSA 10 Lugia alt art',
    note: 'Weekly live auctions for grail-level Pokémon/MTG cards with real-time price discovery.',
  },
  {
    id: 's2',
    handle: 'mini_martian',
    displayName: 'Mini Martian',
    category: 'painting',
    viewers: 340,
    isLive: true,
    completionScore: 86,
    rarityScore: 75,
    tier: 'Gold',
    sampleItem: 'Warhammer Nurgle plague marines',
    note: 'High-signal painting techniques that increase resale value and desirability.',
  },
  {
    id: 's3',
    handle: 'runner_snaps',
    displayName: 'Runner Snaps',
    category: 'gunpla',
    viewers: 210,
    isLive: false,
    completionScore: 74,
    rarityScore: 80,
    tier: 'Gold',
    sampleItem: 'MGEX Strike Freedom custom',
    note: 'Deep dives on custom builds that become one-of-one collectibles.',
  },
  {
    id: 's4',
    handle: 'vinylvault_live',
    displayName: 'Vinyl Vault Live',
    category: 'designer_toys',
    viewers: 120,
    isLive: true,
    completionScore: 68,
    rarityScore: 90,
    tier: 'Silver',
    sampleItem: 'Limited-run sofubi collabs',
    note: 'Drops and preorders for small-batch designer toys with thin supply.',
  },
];

const categoryLabel: Record<TwitchCategory, string> = {
  tcg: 'TCG & Breaks',
  painting: 'Mini Painting',
  gunpla: 'Gunpla Builds',
  designer_toys: 'Designer Toys',
};

const categoryChipColor: Record<TwitchCategory, string> = {
  tcg: '#22c55e',
  painting: '#60a5fa',
  gunpla: '#f97316',
  designer_toys: '#a855f7',
};

const tierColor: Record<TwitchStreamer['tier'], string> = {
  Diamond: '#0ea5e9',
  Gold: '#eab308',
  Silver: '#9ca3af',
};

const formatViewers = (n: number) =>
  n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);

const TwitchLeaderboardCard: React.FC = () => {
  const theme = useAppTheme();
  const router = useRouter();
  const { settings } = useSettings();

  return (
    <View
      style={{
        borderRadius: 16,
        borderWidth: 1,
        borderColor: theme.colors.border,
        backgroundColor: theme.colors.card,
        padding: 12,
        marginTop: 16,
      }}
    >
      <View
        style={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 8,
        }}
      >
        <View style={{ flex: 1, paddingRight: 8 }}>
          <Text
            style={{
              fontSize: 16,
              fontWeight: '700',
              color: theme.colors.text,
            }}
          >
            Twitch Hobby Leaderboard
          </Text>
          <Text
            style={{
              marginTop: 4,
              fontSize: 12,
              color: theme.colors.mutedText,
            }}
          >
            Streams ranked by completion & rarity scores — great sources of comp prices,
            build inspiration, and future watchlist ideas.
          </Text>
        </View>
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push('/analytics-metrics-debug');
          }}
          style={{
            paddingHorizontal: 10,
            paddingVertical: 6,
            borderRadius: 999,
            backgroundColor: theme.colors.primary,
          }}
        >
          <Text
            style={{
              fontSize: 11,
              fontWeight: '600',
              color: theme.colors.onPrimary,
            }}
          >
            View metrics
          </Text>
        </AnimatedPressable>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingVertical: 4 }}
      >
        {MOCK_STREAMERS.map((s) => (
          <View
            key={s.id}
            style={{
              width: 260,
              marginRight: 10,
              borderRadius: 14,
              padding: 10,
              backgroundColor: theme.colors.background,
              borderWidth: 1,
              borderColor: theme.colors.border,
            }}
          >
            {/* Header row: name + tier + live badge */}
            <View
              style={{
                flexDirection: 'row',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <View style={{ flex: 1, paddingRight: 4 }}>
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: '600',
                    color: theme.colors.text,
                  }}
                  numberOfLines={1}
                >
                  {s.displayName}
                </Text>
                <Text
                  style={{
                    fontSize: 11,
                    color: theme.colors.mutedText,
                  }}
                >
                  @{s.handle}
                </Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <View
                  style={{
                    paddingHorizontal: 8,
                    paddingVertical: 3,
                    borderRadius: 999,
                    backgroundColor: '#0f172a',
                  }}
                >
                  <Text
                    style={{
                      fontSize: 10,
                      fontWeight: '600',
                      color: tierColor[s.tier],
                    }}
                  >
                    {s.tier} tier
                  </Text>
                </View>
                <View
                  style={{
                    marginTop: 4,
                    flexDirection: 'row',
                    alignItems: 'center',
                  }}
                >
                  <View
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: 3,
                      marginRight: 4,
                      backgroundColor: s.isLive ? '#ef4444' : '#9ca3af',
                    }}
                  />
                  <Text
                    style={{
                      fontSize: 11,
                      color: theme.colors.mutedText,
                    }}
                  >
                    {s.isLive ? 'Live now' : 'Offline'}
                  </Text>
                </View>
              </View>
            </View>

            {/* Category + viewers */}
            <View
              style={{
                marginTop: 6,
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <View
                style={{
                  paddingHorizontal: 8,
                  paddingVertical: 3,
                  borderRadius: 999,
                  backgroundColor: categoryChipColor[s.category],
                }}
              >
                <Text
                  style={{
                    fontSize: 10,
                    fontWeight: '600',
                    color: '#ffffff',
                  }}
                >
                  {categoryLabel[s.category]}
                </Text>
              </View>
              <Text
                style={{
                  fontSize: 11,
                  color: theme.colors.mutedText,
                }}
              >
                {formatViewers(s.viewers)} viewers
              </Text>
            </View>

            {/* Scores row */}
            <View
              style={{
                marginTop: 6,
                flexDirection: 'row',
                justifyContent: 'space-between',
              }}
            >
              <View>
                <Text
                  style={{
                    fontSize: 11,
                    color: theme.colors.mutedText,
                  }}
                >
                  Completion score
                </Text>
                <Text
                  style={{
                    fontSize: 13,
                    fontWeight: '600',
                    color: theme.colors.text,
                  }}
                >
                  {s.completionScore} / 100
                </Text>
              </View>
              <View>
                <Text
                  style={{
                    fontSize: 11,
                    color: theme.colors.mutedText,
                  }}
                >
                  Rarity signal
                </Text>
                <Text
                  style={{
                    fontSize: 13,
                    fontWeight: '600',
                    color: theme.colors.text,
                  }}
                >
                  {s.rarityScore} / 100
                </Text>
              </View>
            </View>

            {/* Collector tie-in */}
            <View style={{ marginTop: 6 }}>
              <Text
                style={{
                  fontSize: 11,
                  fontWeight: '600',
                  color: theme.colors.text,
                }}
              >
                Collector hook
              </Text>
              <Text
                style={{
                  marginTop: 2,
                  fontSize: 11,
                  color: theme.colors.mutedText,
                }}
                numberOfLines={3}
              >
                {s.note}
              </Text>
              <Text
                style={{
                  marginTop: 2,
                  fontSize: 11,
                  color: theme.colors.mutedText,
                  fontStyle: 'italic',
                }}
              >
                Example item: {s.sampleItem}
              </Text>
            </View>

            {/* Actions */}
            <View
              style={{
                marginTop: 8,
                flexDirection: 'row',
                justifyContent: 'space-between',
              }}
            >
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  // Future: open Twitch URL or deep link
                  console.log('[Twitch] open stream', s.handle);
                }}
                style={{
                  flex: 1,
                  marginRight: 6,
                  paddingVertical: 7,
                  borderRadius: 999,
                  backgroundColor: theme.colors.primary,
                  alignItems: 'center',
                }}
              >
                <Text
                  style={{
                    fontSize: 11,
                    fontWeight: '600',
                    color: theme.colors.onPrimary,
                  }}
                >
                  Open on Twitch
                </Text>
              </AnimatedPressable>

              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  // Future: create event or watchlist suggestion
                  console.log('[Twitch] suggest event/watchlist for', s.handle);
                  router.push('/calendar'); // or an events route if you prefer
                }}
                style={{
                  flex: 1,
                  marginLeft: 6,
                  paddingVertical: 7,
                  borderRadius: 999,
                  borderWidth: 1,
                  borderColor: theme.colors.border,
                  alignItems: 'center',
                }}
              >
                <Text
                  style={{
                    fontSize: 11,
                    fontWeight: '600',
                    color: theme.colors.text,
                  }}
                >
                  Link to Events & Drops
                </Text>
              </AnimatedPressable>
            </View>
          </View>
        ))}
      </ScrollView>
    </View>
  );
};

export default TwitchLeaderboardCard;
