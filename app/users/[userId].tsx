import React, { useMemo } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import {
  getUserById,
  getSimilarUsers,
  UserProfile,
} from '@/data/users';

const BG = '#0f172a';
const CARD = '#020617';
const BORDER = '#1f2933';
const TEXT = '#e5e7eb';
const MUTED = '#9ca3af';

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

const StatChip: React.FC<{ label: string; value: string }> = ({ label, value }) => {
  return (
    <View
      style={{
        paddingHorizontal: 10,
        paddingVertical: 8,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: BORDER,
        backgroundColor: CARD,
        minWidth: 90,
      }}
    >
      <Text
        style={{
          fontSize: 11,
          color: MUTED,
        }}
      >
        {label}
      </Text>
      <Text
        style={{
          marginTop: 2,
          fontSize: 14,
          fontWeight: '600',
          color: TEXT,
        }}
      >
        {value}
      </Text>
    </View>
  );
};

const ScorePill: React.FC<{ label: string; value: number }> = ({ label, value }) => {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <View
      style={{
        paddingHorizontal: 10,
        paddingVertical: 6,
        borderRadius: 999,
        borderWidth: 1,
        borderColor: BORDER,
        flexDirection: 'row',
        alignItems: 'center',
        marginRight: 8,
      }}
    >
      <View
        style={{
          width: 6,
          height: 6,
          borderRadius: 3,
          marginRight: 6,
          backgroundColor:
            clamped >= 80 ? '#22c55e' : clamped >= 60 ? '#eab308' : '#64748b',
        }}
      />
      <Text
        style={{
          fontSize: 11,
          color: MUTED,
          marginRight: 4,
        }}
      >
        {label}
      </Text>
      <Text
        style={{
          fontSize: 12,
          fontWeight: '600',
          color: TEXT,
        }}
      >
        {clamped}
      </Text>
    </View>
  );
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
        width: 52,
        height: 52,
        borderRadius: 26,
        backgroundColor: color,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Text
        style={{
          fontSize: 18,
          fontWeight: '700',
          color: '#ffffff',
        }}
      >
        {initials}
      </Text>
    </View>
  );
};

const UserProfileScreen: React.FC = () => {
  const { userId } = useLocalSearchParams<{ userId?: string }>();
  const router = useRouter();

  const user: UserProfile | undefined = useMemo(
    () => getUserById(userId ?? null),
    [userId],
  );

  if (!user) {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: BG,
          alignItems: 'center',
          justifyContent: 'center',
          paddingHorizontal: 16,
        }}
      >
        <Text
          style={{
            fontSize: 16,
            fontWeight: '600',
            color: TEXT,
            marginBottom: 8,
          }}
        >
          Collector not found
        </Text>
        <Text
          style={{
            fontSize: 13,
            color: MUTED,
            textAlign: 'center',
          }}
        >
          This profile doesn&apos;t exist yet. Try opening from the leaderboard
          or from a different link.
        </Text>
        <TouchableOpacity
          onPress={() => router.back()}
          style={{
            marginTop: 16,
            paddingHorizontal: 16,
            paddingVertical: 10,
            borderRadius: 999,
            borderWidth: 1,
            borderColor: BORDER,
          }}
        >
          <Text
            style={{
              fontSize: 13,
              fontWeight: '500',
              color: TEXT,
            }}
          >
            Go back
          </Text>
        </TouchableOpacity>
      </View>
    );
  }

  const similarUsers = getSimilarUsers(user);

  return (
    <ScrollView
      style={{
        flex: 1,
        backgroundColor: BG,
      }}
      contentContainerStyle={{
        paddingBottom: 32,
      }}
    >
      {/* Header / hero */}
      <View
        style={{
          paddingTop: 48,
          paddingHorizontal: 16,
          paddingBottom: 16,
          borderBottomWidth: 1,
          borderBottomColor: BORDER,
          backgroundColor: CARD,
        }}
      >
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'space-between',
            marginBottom: 12,
          }}
        >
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

          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
            }}
          >
            <Ionicons
              name="trophy-outline"
              size={18}
              color={MUTED}
              style={{ marginRight: 6 }}
            />
            <Text
              style={{
                fontSize: 12,
                color: MUTED,
              }}
            >
              Leaderboard profile
            </Text>
          </View>
        </View>

        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
          }}
        >
          <AvatarCircle name={user.displayName} color={user.avatarColor} />
          <View style={{ marginLeft: 12, flex: 1 }}>
            <Text
              style={{
                fontSize: 18,
                fontWeight: '700',
                color: TEXT,
              }}
            >
              {user.displayName}
            </Text>
            <Text
              style={{
                fontSize: 13,
                color: MUTED,
              }}
            >
              @{user.handle}
            </Text>
            {user.location && (
              <Text
                style={{
                  marginTop: 2,
                  fontSize: 12,
                  color: MUTED,
                }}
              >
                <Ionicons
                  name="location-outline"
                  size={12}
                  color={MUTED}
                />{' '}
                {user.location}
              </Text>
            )}
          </View>
        </View>

        {user.bio && (
          <Text
            style={{
              marginTop: 10,
              fontSize: 12,
              color: MUTED,
            }}
          >
            {user.bio}
          </Text>
        )}
      </View>

      {/* Stats row */}
      <View
        style={{
          paddingHorizontal: 16,
          paddingTop: 12,
        }}
      >
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'space-between',
            marginBottom: 12,
          }}
        >
          <Text
            style={{
              fontSize: 14,
              fontWeight: '700',
              color: TEXT,
            }}
          >
            Collection snapshot
          </Text>
          {user.joinedAt && (
            <Text
              style={{
                fontSize: 11,
                color: MUTED,
              }}
            >
              Joined{' '}
              {new Date(user.joinedAt).toLocaleDateString('en-GB', {
                month: 'short',
                year: 'numeric',
              })}
            </Text>
          )}
        </View>

        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'space-between',
          }}
        >
          <StatChip
            label="Portfolio value"
            value={formatCurrency(user.stats.totalEstimatedValueEur)}
          />
          <StatChip
            label="Items"
            value={user.stats.totalItems.toString()}
          />
          <StatChip
            label="Categories"
            value={user.stats.totalCategories.toString()}
          />
        </View>

        <View
          style={{
            marginTop: 10,
            flexDirection: 'row',
            flexWrap: 'wrap',
          }}
        >
          <ScorePill label="Completion" value={user.stats.completionScore} />
          <ScorePill label="Rarity" value={user.stats.rarityScore} />
          <ScorePill label="Activity" value={user.stats.activityScore} />
        </View>
      </View>

      {/* Collections by category */}
      <View
        style={{
          marginTop: 16,
          paddingHorizontal: 16,
        }}
      >
        <Text
          style={{
            fontSize: 14,
            fontWeight: '700',
            color: TEXT,
            marginBottom: 6,
          }}
        >
          Collections by category
        </Text>
        <Text
          style={{
            fontSize: 12,
            color: MUTED,
            marginBottom: 8,
          }}
        >
          Structured similar to your Items view: each category shows a total and
          links into that slice of the portfolio.
        </Text>

        {user.categories.map((cat) => (
          <View
            key={cat.id}
            style={{
              borderRadius: 16,
              borderWidth: 1,
              borderColor: BORDER,
              backgroundColor: CARD,
              padding: 12,
              marginBottom: 8,
            }}
          >
            <View
              style={{
                flexDirection: 'row',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 6,
              }}
            >
              <View>
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: '600',
                    color: TEXT,
                  }}
                >
                  {cat.name}
                </Text>
                <Text
                  style={{
                    fontSize: 12,
                    color: MUTED,
                  }}
                >
                  {cat.itemCount} items
                </Text>
              </View>
              <Text
                style={{
                  fontSize: 13,
                  fontWeight: '600',
                  color: TEXT,
                }}
              >
                {formatCurrency(cat.totalEstimatedValueEur)}
              </Text>
            </View>

            <TouchableOpacity
              onPress={() => {
                console.log('[UserProfile] open category slice', user.id, cat.id);
              }}
              style={{
                marginTop: 4,
                alignSelf: 'flex-start',
                paddingHorizontal: 10,
                paddingVertical: 6,
                borderRadius: 999,
                borderWidth: 1,
                borderColor: BORDER,
                flexDirection: 'row',
                alignItems: 'center',
              }}
            >
              <Ionicons
                name="albums-outline"
                size={13}
                color={MUTED}
                style={{ marginRight: 6 }}
              />
              <Text
                style={{
                  fontSize: 11,
                  fontWeight: '500',
                  color: MUTED,
                }}
              >
                View items in this category
              </Text>
            </TouchableOpacity>
          </View>
        ))}
      </View>

      {/* Recent pickups */}
      <View
        style={{
          marginTop: 16,
          paddingHorizontal: 16,
        }}
      >
        <Text
          style={{
            fontSize: 14,
            fontWeight: '700',
            color: TEXT,
            marginBottom: 6,
          }}
        >
          Recent pickups
        </Text>
        <Text
          style={{
            fontSize: 12,
            color: MUTED,
            marginBottom: 8,
          }}
        >
          A short stream of the latest items added, useful for leaderboard
          viewers to understand how this collection is evolving.
        </Text>

        {user.recentItems.map((it) => (
          <View
            key={it.id}
            style={{
              borderRadius: 16,
              borderWidth: 1,
              borderColor: BORDER,
              backgroundColor: CARD,
              padding: 10,
              marginBottom: 6,
            }}
          >
            <View
              style={{
                flexDirection: 'row',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <View style={{ flex: 1, paddingRight: 8 }}>
                <Text
                  style={{
                    fontSize: 13,
                    fontWeight: '600',
                    color: TEXT,
                  }}
                  numberOfLines={1}
                >
                  {it.name}
                </Text>
                <Text
                  style={{
                    marginTop: 2,
                    fontSize: 11,
                    color: MUTED,
                  }}
                  numberOfLines={1}
                >
                  {it.category}
                  {it.collectionName ? ` • ${it.collectionName}` : ''}
                </Text>
              </View>
              {it.estimatedValueEur && (
                <Text
                  style={{
                    fontSize: 12,
                    fontWeight: '600',
                    color: TEXT,
                  }}
                >
                  {formatCurrency(it.estimatedValueEur)}
                </Text>
              )}
            </View>
          </View>
        ))}
      </View>

      {/* Similar collectors */}
      {similarUsers.length > 0 && (
        <View
          style={{
            marginTop: 16,
            paddingHorizontal: 16,
          }}
        >
          <Text
            style={{
              fontSize: 14,
              fontWeight: '700',
              color: TEXT,
              marginBottom: 6,
            }}
          >
            Similar collectors
          </Text>
          <Text
            style={{
              fontSize: 12,
              color: MUTED,
              marginBottom: 6,
            }}
          >
            Profiles with similar category focus or portfolio patterns — useful
            for leaderboard discovery.
          </Text>

          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ paddingVertical: 4 }}
          >
            {similarUsers.map((u) => (
              <TouchableOpacity
                key={u.id}
                onPress={() =>
                  router.push(`/users/${encodeURIComponent(u.id)}`)
                }
                style={{
                  width: 190,
                  marginRight: 10,
                  borderRadius: 16,
                  borderWidth: 1,
                  borderColor: BORDER,
                  backgroundColor: CARD,
                  padding: 10,
                }}
              >
                <View
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    marginBottom: 6,
                  }}
                >
                  <AvatarCircle name={u.displayName} color={u.avatarColor} />
                  <View style={{ marginLeft: 8, flex: 1 }}>
                    <Text
                      style={{
                        fontSize: 13,
                        fontWeight: '600',
                        color: TEXT,
                      }}
                      numberOfLines={1}
                    >
                      {u.displayName}
                    </Text>
                    <Text
                      style={{
                        fontSize: 11,
                        color: MUTED,
                      }}
                      numberOfLines={1}
                    >
                      @{u.handle}
                    </Text>
                  </View>
                </View>
                <Text
                  style={{
                    fontSize: 11,
                    color: MUTED,
                    marginBottom: 4,
                  }}
                  numberOfLines={2}
                >
                  {u.bio}
                </Text>
                <Text
                  style={{
                    fontSize: 11,
                    fontWeight: '600',
                    color: TEXT,
                  }}
                >
                  {formatCurrency(u.stats.totalEstimatedValueEur)}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      )}
    </ScrollView>
  );
};

export default UserProfileScreen;
