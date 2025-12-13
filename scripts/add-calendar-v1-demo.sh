#!/usr/bin/env bash
set -euo pipefail

FILE="app/calendar-v1-demo.tsx"
cp "$FILE" "$FILE.bak-$(date +%s)" 2>/dev/null || true

cat > "$FILE" <<'TS'
import React, { useState } from 'react';
import { ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { Stack } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';

type EventType = 'Convention' | 'Card show' | 'Drop' | 'Release';

type CalendarEvent = {
  id: string;
  title: string;
  date: string; // ISO or human
  type: EventType;
  location?: string;
  note?: string;
  source?: string;
};

type TabKey = 'MY' | 'DROPS';

const MY_EVENTS: CalendarEvent[] = [
  {
    id: 'me1',
    title: 'Local TCG meetup',
    date: '2025-02-18',
    type: 'Card show',
    location: 'Utrecht card shop',
    note: 'Bring Lugia binder and a few slab trades.',
  },
  {
    id: 'me2',
    title: 'Gunpla build night',
    date: '2025-03-02',
    type: 'Convention',
    location: 'Friend\'s place',
    note: 'Continue airbrushing HG kit and panel lining.',
  },
  {
    id: 'me3',
    title: 'Vintage trade session',
    date: '2025-03-21',
    type: 'Card show',
    location: 'Amsterdam collector meetup',
    note: 'Focus on Neo Genesis and Expedition trades.',
  },
];

const MAJOR_DROPS: CalendarEvent[] = [
  {
    id: 'md1',
    title: 'Pokémon – special set release',
    date: '2025-04-05',
    type: 'Release',
    location: 'Global / online',
    note: 'High demand set, likely scalping window in first week.',
    source: 'Official Pokémon announcements',
  },
  {
    id: 'md2',
    title: 'Warhammer army starter reprint',
    date: '2025-05-10',
    type: 'Drop',
    location: 'GW stores & FLGS',
    note: 'Opportunity to pick up starter box below secondary prices.',
    source: 'GW community site (demo)',
  },
  {
    id: 'md3',
    title: 'Designer toy collaboration drop',
    date: '2025-06-01',
    type: 'Drop',
    location: 'Online only',
    note: 'Limited run; track floor price vs retail.',
    source: 'Brand newsletter (demo)',
  },
];

function formatDateHuman(date: string): string {
  // Very simple display; real impl would parse
  if (date.length === 10 && date[4] === '-' && date[7] === '-') {
    const [y, m, d] = date.split('-');
    return `${d}.${m}.${y.slice(2)}`;
  }
  return date;
}

function eventTypeColor(type: EventType, colors: any): string {
  switch (type) {
    case 'Convention':
      return colors.primary;
    case 'Card show':
      return colors.success ?? '#16a34a';
    case 'Drop':
      return colors.error ?? '#B00020';
    case 'Release':
      return colors.text;
    default:
      return colors.mutedText;
  }
}

export default function CalendarV1DemoScreen() {
  const { colors, spacing, radii } = useAppTheme();
  const [tab, setTab] = useState<TabKey>('MY');

  const activeEvents = tab === 'MY' ? MY_EVENTS : MAJOR_DROPS;

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Calendar (v1 demo)',
        }}
      />
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{
          paddingTop: spacing.lg * 1.5,
          paddingHorizontal: spacing.lg,
          paddingBottom: spacing.xl * 2,
          gap: spacing.md,
        }}
      >
        {/* Intro */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
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
            Events & drops
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            Keep track of your own events and major set drops in one place.
            Only your own events will trigger reminders later; big drops are
            shown for planning.
          </Text>
        </View>

        {/* Segmented control: My events / Major drops */}
        <View
          style={{
            flexDirection: 'row',
            borderRadius: 999,
            backgroundColor: colors.card,
            padding: 4,
          }}
        >
          {[
            { key: 'MY' as TabKey, label: 'My events' },
            { key: 'DROPS' as TabKey, label: 'Major drops' },
          ].map((seg) => {
            const active = seg.key === tab;
            return (
              <TouchableOpacity
                key={seg.key}
                onPress={() => setTab(seg.key)}
                activeOpacity={0.85}
                style={{
                  flex: 1,
                  paddingVertical: 8,
                  borderRadius: 999,
                  alignItems: 'center',
                  backgroundColor: active ? colors.primary : 'transparent',
                }}
              >
                <Text
                  style={{
                    fontSize: 13,
                    fontWeight: '600',
                    color: active ? colors.onPrimary : colors.text,
                  }}
                >
                  {seg.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Events list */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
          }}
        >
          <Text
            style={{
              fontSize: 16,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.sm,
            }}
          >
            {tab === 'MY' ? 'Your upcoming events' : 'Notable drops & releases'}
          </Text>

          {activeEvents.length === 0 ? (
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
              }}
            >
              No events yet. Later you&apos;ll be able to add your own shows,
              drops and conventions here.
            </Text>
          ) : (
            <View style={{ gap: spacing.sm }}>
              {activeEvents.map((ev) => (
                <View
                  key={ev.id}
                  style={{
                    borderRadius: 8,
                    borderWidth: 1,
                    borderColor: colors.border,
                    padding: spacing.sm,
                  }}
                >
                  <View
                    style={{
                      flexDirection: 'row',
                      justifyContent: 'space-between',
                      marginBottom: 2,
                    }}
                  >
                    <Text
                      style={{
                        flex: 1,
                        fontSize: 14,
                        fontWeight: '600',
                        color: colors.text,
                      }}
                      numberOfLines={2}
                    >
                      {ev.title}
                    </Text>
                    <Text
                      style={{
                        fontSize: 12,
                        color: colors.mutedText,
                        marginLeft: spacing.sm,
                      }}
                    >
                      {formatDateHuman(ev.date)}
                    </Text>
                  </View>

                  {ev.location ? (
                    <Text
                      style={{
                        fontSize: 12,
                        color: colors.mutedText,
                        marginBottom: 2,
                      }}
                    >
                      {ev.location}
                    </Text>
                  ) : null}

                  {ev.note ? (
                    <Text
                      style={{
                        fontSize: 12,
                        color: colors.mutedText,
                        marginBottom: 4,
                      }}
                      numberOfLines={3}
                    >
                      {ev.note}
                    </Text>
                  ) : null}

                  <View
                    style={{
                      flexDirection: 'row',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginTop: 2,
                    }}
                  >
                    <View
                      style={{
                        paddingHorizontal: spacing.sm,
                        paddingVertical: 3,
                        borderRadius: 999,
                        backgroundColor: colors.surface,
                      }}
                    >
                      <Text
                        style={{
                          fontSize: 11,
                          fontWeight: '600',
                          color: eventTypeColor(ev.type, colors),
                        }}
                      >
                        {ev.type}
                      </Text>
                    </View>
                    {ev.source ? (
                      <Text
                        style={{
                          fontSize: 11,
                          color: colors.mutedText,
                        }}
                        numberOfLines={1}
                      >
                        Source: {ev.source}
                      </Text>
                    ) : null}
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>
      </ScrollView>
    </>
  );
}
TS

echo "Created app/calendar-v1-demo.tsx (Calendar v1 demo)."
