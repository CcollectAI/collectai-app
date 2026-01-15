import React, { useMemo } from 'react';
import { View, Text, ScrollView, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { USER_PROFILES } from '@/data/users';

const BG = '#0f172a';
const CARD = '#020617';
const BORDER = '#1f2933';
const TEXT = '#e5e7eb';
const MUTED = '#9ca3af';
const PRIMARY = '#0ea5e9';

const formatCurrency = (value: number | undefined | null): string => {
  if (!value || !Number.isFinite(value)) return '€0';
  try {
    return `€${value.toLocaleString('en-US', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })}`;
  } catch {
    return `€${value}`;
  }
};

const AvatarCircle: React.FC<{ name: string; color: string }> = ({ name, color }) => {
  const initials =
    name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || '?';
  return (
    <View
      style={{
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: color,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Text
        style={{
          fontSize: 14,
          fontWeight: '700',
          color: '#ffffff',
        }}
      >
        {initials}
      </Text>
    </View>
  );
};

const LeaderboardScreen: React.FC = () => {
  const router = useRouter();

  const rankedUsers = useMemo(
    () =>
      [...USER_PROFILES].sort(
        (a, b) =>
          b.stats.totalEstimatedValueEur - a.stats.totalEstimatedValueEur,
      ),
    [],
  );

  return (
    <ScrollView
      style={{
        flex: 1,
        backgroundColor: BG,
      }}
      contentContainerStyle={{
        paddingTop: 48,
        paddingBottom: 32,
        paddingHorizontal: 16,
      }}
    >
      {/* Header */}
      <View
        style={{
          marginBottom: 16,
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <View style={{ flex: 1, paddingRight: 8 }}>
          <Text
            style={{
              fontSize: 20,
              fontWeight: '700',
              color: TEXT,
            }}
          >
            Collector Leaderboard
          </Text>
          <Text
            style={{
              marginTop: 4,
              fontSize: 12,
              color: MUTED,
            }}
          >
            Ranked by estimated portfolio value. Tap a row to view a full
            collector profile.
          </Text>
        </View>
        <TouchableOpacity
          onPress={() => router.back()}
          style={{
            paddingHorizontal: 10,
            paddingVertical: 6,
            borderRadius: 999,
            borderWidth: 1,
            borderColor: BORDER,
          }}
        >
          <Text
            style={{
              fontSize: 11,
              color: MUTED,
            }}
          >
            Back
          </Text>
        </TouchableOpacity>
      </View>

      {/* Leaderboard list */}
      {rankedUsers.map((user, index) => (
        <TouchableOpacity
          key={user.id}
          activeOpacity={0.9}
          onPress={() => router.push(`/users/${encodeURIComponent(user.id)}`)}
          style={{
            borderRadius: 16,
            borderWidth: 1,
            borderColor: BORDER,
            backgroundColor: CARD,
            padding: 10,
            marginBottom: 8,
            flexDirection: 'row',
            alignItems: 'center',
          }}
        >
          {/* Rank */}
          <View
            style={{
              width: 30,
              alignItems: 'center',
              marginRight: 8,
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '700',
                color:
                  index === 0
                    ? '#eab308'
                    : index === 1
                    ? '#9ca3af'
                    : index === 2
                    ? '#b45309'
                    : MUTED,
              }}
            >
              #{index + 1}
            </Text>
            {index < 3 && (
              <Ionicons
                name="trophy-outline"
                size={14}
                color={
                  index === 0
                    ? '#eab308'
                    : index === 1
                    ? '#9ca3af'
                    : '#b45309'
                }
              />
            )}
          </View>

          {/* Avatar + main info */}
          <AvatarCircle name={user.displayName} color={user.avatarColor} />
          <View style={{ marginLeft: 10, flex: 1 }}>
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: TEXT,
              }}
            >
              {user.displayName}
            </Text>
            <Text
              style={{
                fontSize: 11,
                color: MUTED,
              }}
            >
              @{user.handle}
            </Text>
            <Text
              style={{
                marginTop: 2,
                fontSize: 11,
                color: MUTED,
              }}
              numberOfLines={1}
            >
              {user.stats.totalItems} items • {user.stats.totalCategories}{' '}
              categories
            </Text>
          </View>

          {/* Value + key score */}
          <View
            style={{
              alignItems: 'flex-end',
            }}
          >
            <Text
              style={{
                fontSize: 13,
                fontWeight: '700',
                color: TEXT,
              }}
            >
              {formatCurrency(user.stats.totalEstimatedValueEur)}
            </Text>
            <Text
              style={{
                marginTop: 2,
                fontSize: 11,
                color: MUTED,
              }}
            >
              Rarity {user.stats.rarityScore}
            </Text>
          </View>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
};

export default LeaderboardScreen;
