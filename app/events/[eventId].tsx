import React, { useMemo, useState, useEffect } from 'react';
import { View, Text, ScrollView, TouchableOpacity, Linking } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { EVENTS, CollectorsEvent, EventKind } from '@/data/events';
import { getCategoryById } from '@/data/categories';
import { getUserById } from '@/data/users';
import { dataProvider, type PublicUserProfile } from '@/data';
import { PublicUserProfileCard } from '@/components/PublicUserProfileCard';

const BG = '#0f172a';
const CARD = '#020617';
const BORDER = '#1f2933';
const TEXT = '#e5e7eb';
const MUTED = '#9ca3af';
const PRIMARY = '#0ea5e9';

const kindLabel: Record<EventKind, string> = {
  collection_drop: 'Collection drop',
  meetup: 'Meetup',
  stream: 'Twitch stream',
};

const AvatarSmall: React.FC<{ name: string; color: string }> = ({ name, color }) => {
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
        width: 28,
        height: 28,
        borderRadius: 14,
        backgroundColor: color,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 8,
      }}
    >
      <Text
        style={{
          fontSize: 11,
          fontWeight: '700',
          color: '#ffffff',
        }}
      >
        {initials}
      </Text>
    </View>
  );
};

const EventDetailScreen: React.FC = () => {
  const { eventId } = useLocalSearchParams<{ eventId?: string }>();
  const router = useRouter();

  const event: CollectorsEvent | undefined = useMemo(
    () => EVENTS.find((e) => e.id === eventId),
    [eventId],
  );

  if (!event) {
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
          Event not found
        </Text>
        <Text
          style={{
            fontSize: 13,
            color: MUTED,
            textAlign: 'center',
          }}
        >
          This event doesn&apos;t exist yet. Try opening it from the Events
          tab again.
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

  const relatedCategory = event.categoryId
    ? getCategoryById(event.categoryId)
    : undefined;
  const attendeeUsers = event.attendeeIds
    .map((id) => getUserById(id))
    .filter((u): u is NonNullable<ReturnType<typeof getUserById>> => Boolean(u));

  // Fetch host profile via DataProvider (public view only)
  const [hostProfile, setHostProfile] = useState<PublicUserProfile | null>(null);
  const [hostProfileLoading, setHostProfileLoading] = useState(false);

  useEffect(() => {
    if (event?.hostUserId) {
      setHostProfileLoading(true);
      dataProvider.getPublicUserProfile(event.hostUserId)
        .then(setHostProfile)
        .catch(() => setHostProfile(null))
        .finally(() => setHostProfileLoading(false));
    }
  }, [event?.hostUserId]);

  const [alertsOn, setAlertsOn] = useState(false);
  const [followingStream, setFollowingStream] = useState(false);
  const [going, setGoing] = useState(false);

  const openExternal = () => {
    if (!event.onlineUrl) return;
    Linking.openURL(event.onlineUrl).catch((err) =>
      console.log('[EventDetail] failed to open url', err),
    );
  };

  const isStream = event.kind === 'stream';
  const isDrop = event.kind === 'collection_drop';
  const isMeetup = event.kind === 'meetup';

  const handleAskToConnect = (userId: string) => {
    router.push({
      pathname: '/chat/new',
      params: {
        toUserId: userId,
        contextEventId: event.id,
      },
    });
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: BG }}
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
        }}
      >
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'space-between',
            marginBottom: 10,
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
              name="calendar-outline"
              size={14}
              color={MUTED}
              style={{ marginRight: 6 }}
            />
            <Text
              style={{
                fontSize: 11,
                color: MUTED,
              }}
            >
              {kindLabel[event.kind]}
            </Text>
          </View>
        </View>

        <Text
          style={{
            fontSize: 20,
            fontWeight: '700',
            color: TEXT,
          }}
        >
          {event.title}
        </Text>

        <Text
          style={{
            marginTop: 6,
            fontSize: 13,
            color: MUTED,
          }}
        >
          {event.date}
          {event.time ? ` • ${event.time}` : ''}
        </Text>

        {event.location && (
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
            {event.location}
          </Text>
        )}
      </View>

      {/* Description */}
      <View
        style={{
          borderRadius: 16,
          borderWidth: 1,
          borderColor: BORDER,
          backgroundColor: CARD,
          padding: 12,
          marginBottom: 12,
        }}
      >
        <Text
          style={{
            fontSize: 13,
            color: TEXT,
          }}
        >
          {event.description}
        </Text>
      </View>

      {/* Primary external action */}
      {event.onlineUrl && (
        <TouchableOpacity
          onPress={openExternal}
          style={{
            alignSelf: 'flex-start',
            paddingHorizontal: 16,
            paddingVertical: 10,
            borderRadius: 999,
            backgroundColor: PRIMARY,
            flexDirection: 'row',
            alignItems: 'center',
            marginBottom: 12,
          }}
        >
          <Ionicons
            name={isStream ? 'logo-twitch' : 'open-outline'}
            size={16}
            color="#ffffff"
            style={{ marginRight: 6 }}
          />
          <Text
            style={{
              fontSize: 13,
              fontWeight: '600',
              color: '#ffffff',
            }}
          >
            {isStream
              ? 'Open stream'
              : isDrop
              ? 'Open drop page'
              : 'Open link'}
          </Text>
        </TouchableOpacity>
      )}

      {/* Participation controls */}
      <View
        style={{
          marginBottom: 16,
          flexDirection: 'row',
          flexWrap: 'wrap',
        }}
      >
        {isDrop && (
          <TouchableOpacity
            onPress={() => {
              setAlertsOn(!alertsOn);
              console.log('[EventDetail] toggle drop alerts', event.id, !alertsOn);
            }}
            style={{
              paddingHorizontal: 14,
              paddingVertical: 8,
              borderRadius: 999,
              borderWidth: 1,
              borderColor: alertsOn ? PRIMARY : BORDER,
              backgroundColor: alertsOn ? '#022c22' : CARD,
              flexDirection: 'row',
              alignItems: 'center',
              marginRight: 8,
              marginBottom: 8,
            }}
          >
            <Ionicons
              name={alertsOn ? 'notifications' : 'notifications-outline'}
              size={16}
              color={alertsOn ? PRIMARY : MUTED}
              style={{ marginRight: 6 }}
            />
            <Text
              style={{
                fontSize: 12,
                fontWeight: '500',
                color: alertsOn ? PRIMARY : MUTED,
              }}
            >
              {alertsOn ? 'Alerts on for this drop' : 'Alert me for this drop'}
            </Text>
          </TouchableOpacity>
        )}

        {isStream && (
          <TouchableOpacity
            onPress={() => {
              setFollowingStream(!followingStream);
              console.log('[EventDetail] toggle stream follow', event.id, !followingStream);
            }}
            style={{
              paddingHorizontal: 14,
              paddingVertical: 8,
              borderRadius: 999,
              borderWidth: 1,
              borderColor: followingStream ? PRIMARY : BORDER,
              backgroundColor: followingStream ? '#022c22' : CARD,
              flexDirection: 'row',
              alignItems: 'center',
              marginRight: 8,
              marginBottom: 8,
            }}
          >
            <Ionicons
              name={followingStream ? 'checkmark-circle' : 'add-circle-outline'}
              size={16}
              color={followingStream ? PRIMARY : MUTED}
              style={{ marginRight: 6 }}
            />
            <Text
              style={{
                fontSize: 12,
                fontWeight: '500',
                color: followingStream ? PRIMARY : MUTED,
              }}
            >
              {followingStream ? 'Following this stream' : 'Follow this stream'}
            </Text>
          </TouchableOpacity>
        )}

        {isMeetup && (
          <TouchableOpacity
            onPress={() => {
              setGoing(!going);
              console.log('[EventDetail] toggle meetup going', event.id, !going);
            }}
            style={{
              paddingHorizontal: 14,
              paddingVertical: 8,
              borderRadius: 999,
              borderWidth: 1,
              borderColor: going ? PRIMARY : BORDER,
              backgroundColor: going ? '#022c22' : CARD,
              flexDirection: 'row',
              alignItems: 'center',
              marginRight: 8,
              marginBottom: 8,
            }}
          >
            <Ionicons
              name={going ? 'checkmark' : 'walk-outline'}
              size={16}
              color={going ? PRIMARY : MUTED}
              style={{ marginRight: 6 }}
            />
            <Text
              style={{
                fontSize: 12,
                fontWeight: '500',
                color: going ? PRIMARY : MUTED,
              }}
            >
              {going ? 'You are going' : 'I’m going to this meetup'}
            </Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Related category */}
      {relatedCategory && (
        <View
          style={{
            marginBottom: 14,
          }}
        >
          <Text
            style={{
              fontSize: 13,
              fontWeight: '700',
              color: TEXT,
              marginBottom: 4,
            }}
          >
            Related category
          </Text>

          <TouchableOpacity
            onPress={() =>
              router.push(`/categories/${encodeURIComponent(relatedCategory.id)}`)
            }
            style={{
              borderRadius: 16,
              borderWidth: 1,
              borderColor: BORDER,
              backgroundColor: CARD,
              padding: 10,
              marginBottom: 8,
            }}
          >
            <Text
              style={{
                fontSize: 13,
                fontWeight: '600',
                color: TEXT,
              }}
            >
              {relatedCategory.name}
            </Text>
            <Text
              style={{
                marginTop: 2,
                fontSize: 11,
                color: MUTED,
              }}
              numberOfLines={2}
            >
              {relatedCategory.tagline}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() =>
              router.push(`/chat/category/${encodeURIComponent(relatedCategory.id)}`)
            }
            style={{
              alignSelf: 'flex-start',
              paddingHorizontal: 14,
              paddingVertical: 8,
              borderRadius: 999,
              borderWidth: 1,
              borderColor: BORDER,
              flexDirection: 'row',
              alignItems: 'center',
            }}
          >
            <Ionicons
              name="chatbubbles-outline"
              size={14}
              color={PRIMARY}
              style={{ marginRight: 6 }}
            />
            <Text
              style={{
                fontSize: 12,
                fontWeight: '500',
                color: PRIMARY,
              }}
            >
              Open category chat
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Host collector — uses dataProvider.getPublicUserProfile (public view only) */}
      {(hostProfile || hostProfileLoading) && (
        <View
          style={{
            marginBottom: 14,
          }}
        >
          <Text
            style={{
              fontSize: 13,
              fontWeight: '700',
              color: TEXT,
              marginBottom: 4,
            }}
          >
            Host collector
          </Text>
          <PublicUserProfileCard
            profile={hostProfile}
            loading={hostProfileLoading}
            onPress={hostProfile ? () => router.push(`/users/${encodeURIComponent(hostProfile.id)}`) : undefined}
          />
        </View>
      )}

      {/* Collectors attending */}
      <View
        style={{
          marginTop: 4,
        }}
      >
        <Text
          style={{
            fontSize: 13,
            fontWeight: '700',
            color: TEXT,
            marginBottom: 4,
          }}
        >
          Collectors attending / following
        </Text>
        {attendeeUsers.length === 0 ? (
          <Text
            style={{
              fontSize: 12,
              color: MUTED,
            }}
          >
            No collectors are marked as attending yet. You can be the first.
          </Text>
        ) : (
          <View
            style={{
              borderRadius: 16,
              borderWidth: 1,
              borderColor: BORDER,
              backgroundColor: CARD,
              padding: 10,
            }}
          >
            {attendeeUsers.map((u) => (
              <View
                key={u.id}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  marginBottom: 8,
                }}
              >
                <TouchableOpacity
                  onPress={() =>
                    router.push(`/users/${encodeURIComponent(u.id)}`)
                  }
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    flex: 1,
                  }}
                >
                  <AvatarSmall
                    name={u.displayName}
                    color={u.avatarColor}
                  />
                  <View style={{ flex: 1 }}>
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
                </TouchableOpacity>

                <TouchableOpacity
                  onPress={() => handleAskToConnect(u.id)}
                  style={{
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
                    name="chatbubble-ellipses-outline"
                    size={14}
                    color={PRIMARY}
                    style={{ marginRight: 4 }}
                  />
                  <Text
                    style={{
                      fontSize: 11,
                      fontWeight: '500',
                      color: PRIMARY,
                    }}
                  >
                    Ask to connect
                  </Text>
                </TouchableOpacity>
              </View>
            ))}

            <Text
              style={{
                fontSize: 11,
                color: MUTED,
                marginTop: 4,
              }}
            >
              {attendeeUsers.length === 1
                ? '1 collector is attending/following this event.'
                : `${attendeeUsers.length} collectors are attending/following this event.`}
            </Text>
          </View>
        )}
      </View>
    </ScrollView>
  );
};

export default EventDetailScreen;
