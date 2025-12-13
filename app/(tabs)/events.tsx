import React, { useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { EVENTS, CollectorsEvent } from '@/data/events';

const DARK = {
  BG: '#0f172a',
  CARD: '#020617',
  BORDER: '#1f2933',
  TEXT: '#e5e7eb',
  MUTED: '#9ca3af',
  PRIMARY: '#0ea5e9',
};

const LIGHT = {
  BG: '#f4f4f5',
  CARD: '#ffffff',
  BORDER: '#e5e7eb',
  TEXT: '#0f172a',
  MUTED: '#6b7280',
  PRIMARY: '#0ea5e9',
};

const kindLabel: Record<CollectorsEvent['kind'], string> = {
  collection_drop: 'Collection drop',
  meetup: 'Meetup',
  stream: 'Twitch stream',
};

const kindIcon: Record<CollectorsEvent['kind'], keyof typeof Ionicons.glyphMap> = {
  collection_drop: 'cube-outline',
  meetup: 'people-outline',
  stream: 'logo-twitch',
};

const EventsScreen: React.FC = () => {
  const router = useRouter();
  const [isDark, setIsDark] = useState(true);

  const theme = isDark ? DARK : LIGHT;
  const { BG, CARD, BORDER, TEXT, MUTED, PRIMARY } = theme;

  const sortedEvents = [...EVENTS].sort((a, b) => a.date.localeCompare(b.date));

  console.log('[Events] screen mounted, theme =', isDark ? 'dark' : 'light');

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: BG }}
      contentContainerStyle={{
        paddingTop: 48,
        paddingBottom: 32,
        paddingHorizontal: 16,
      }}
    >
      {/* Header with light/dark toggle */}
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
            Events & Drops
          </Text>
          <Text
            style={{
              marginTop: 4,
              fontSize: 12,
              color: MUTED,
            }}
          >
            Collection drops, local meetups, and Twitch sessions in one timeline.
            Tap a card to see who&apos;s going, follow drops, or join streams.
          </Text>
        </View>

        <TouchableOpacity
          onPress={() => setIsDark((prev) => !prev)}
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
            name={isDark ? 'sunny-outline' : 'moon-outline'}
            size={16}
            color={MUTED}
            style={{ marginRight: 4 }}
          />
          <Text
            style={{
              fontSize: 11,
              color: MUTED,
            }}
          >
            {isDark ? 'Light' : 'Dark'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Events list */}
      {sortedEvents.map((event) => {
        const attendanceLabel =
          event.attendeeIds.length === 0
            ? 'Be the first to join'
            : event.attendeeIds.length === 1
            ? '1 collector attending'
            : `${event.attendeeIds.length} collectors attending`;

        const metaLine = [
          kindLabel[event.kind],
          event.date + (event.time ? ` — ${event.time}` : ''),
        ]
          .filter(Boolean)
          .join(' • ');

        return (
          <TouchableOpacity
            key={event.id}
            activeOpacity={0.9}
            onPress={() =>
              router.push(`/events/${encodeURIComponent(event.id)}`)
            }
            style={{
              borderRadius: 16,
              borderWidth: 1,
              borderColor: BORDER,
              backgroundColor: CARD,
              padding: 10,
              marginBottom: 10,
              flexDirection: 'row',
              alignItems: 'center',
            }}
          >
            {/* Icon bubble */}
            <View
              style={{
                width: 40,
                height: 40,
                borderRadius: 20,
                backgroundColor: PRIMARY,
                alignItems: 'center',
                justifyContent: 'center',
                marginRight: 10,
              }}
            >
              <Ionicons
                name={kindIcon[event.kind]}
                size={20}
                color="#ffffff"
              />
            </View>

            {/* Info */}
            <View style={{ flex: 1, paddingRight: 8 }}>
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: TEXT,
                }}
                numberOfLines={1}
              >
                {event.title}
              </Text>
              <Text
                style={{
                  marginTop: 2,
                  fontSize: 11,
                  color: MUTED,
                }}
                numberOfLines={1}
              >
                {metaLine}
              </Text>
              {event.location && (
                <Text
                  style={{
                    marginTop: 2,
                    fontSize: 11,
                    color: MUTED,
                  }}
                  numberOfLines={1}
                >
                  {event.location}
                </Text>
              )}
              <Text
                style={{
                  marginTop: 2,
                  fontSize: 11,
                  color: MUTED,
                }}
                numberOfLines={1}
              >
                {attendanceLabel}
              </Text>
            </View>

            <Ionicons
              name="chevron-forward"
              size={18}
              color={MUTED}
            />
          </TouchableOpacity>
        );
      })}
    
        {/* Meetups: attendees (opt-in) */}
        <View style={{ marginTop: 14 }}>
          <Text style={{ fontSize: 14, fontWeight: "900", color: "#0b1f3a", marginBottom: 8 }}>
            Attendees
          </Text>

          <View style={{ flexDirection: "row", gap: 10, flexWrap: "wrap" }}>
            {MEETUP_ATTENDEES__MOCK.filter(a => a.optedIn).map((a) => (
              <Pressable
                key={a.id}
                onPress={() =>
                  router.push({
                    pathname: "/users/[id]",
                    params: {
                      id: a.id,
                      name: a.name,
                      handle: a.handle,
                      city: a.city,
                      bio: a.bio,
                    },
                  })
                }
                hitSlop={10}
                style={{ alignItems: "center" }}
              >
                <AvatarBubble label={a.name} />
              </Pressable>
            ))}
          </View>
        </View>

      </ScrollView>
  );
};

export default EventsScreen;



// --- Meetups Attendees (opt-in) ---
// Replace with real attendee data later.
const MEETUP_ATTENDEES__MOCK = [
  { id: "u1", name: "Mina", handle: "@mina.cards", city: "Amsterdam", bio: "Pokémon + Lorcana. Meetups & trades.", optedIn: true },
  { id: "u2", name: "Jay", handle: "@jay.collects", city: "Utrecht", bio: "Funko + Diecast. Looking for swaps.", optedIn: true },
  { id: "u3", name: "Sofia", handle: "@sofia.tcgs", city: "Rotterdam", bio: "MTG sealed. Casual meetups.", optedIn: false },
];

function AvatarBubble({ label }: { label: string }) {
  const ch = (label?.trim()?.[0] ?? "C").toUpperCase();
  return (
    <View
      style={{
        width: 34,
        height: 34,
        borderRadius: 17,
        backgroundColor: "rgba(20,184,166,0.18)",
        alignItems: "center",
        justifyContent: "center",
        borderWidth: 1,
        borderColor: "rgba(11,31,58,0.08)",
      }}
    >
      <Text style={{ fontWeight: "900", color: "#0b1f3a" }}>{ch}</Text>
    </View>
  );
}
