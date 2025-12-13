#!/usr/bin/env bash
set -euo pipefail

mkdir -p app

#######################################
# calendar-add-event-demo.tsx
#######################################
FILE1="app/calendar-add-event-demo.tsx"
cp "$FILE1" "$FILE1.bak-$(date +%s)" 2>/dev/null || true

cat > "$FILE1" <<'TS'
import React, { useState } from 'react';
import {
  ScrollView,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Stack, router } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';

type EventType = 'Convention' | 'Card show' | 'Drop' | 'Release';

const EVENT_TYPES: EventType[] = [
  'Convention',
  'Card show',
  'Drop',
  'Release',
];

export default function CalendarAddEventDemoScreen() {
  const { colors, spacing, radii } = useAppTheme();

  const [title, setTitle] = useState('');
  const [date, setDate] = useState('2025-02-18');
  const [type, setType] = useState<EventType>('Card show');
  const [location, setLocation] = useState('Amsterdam');
  const [note, setNote] = useState(
    'This is a demo only — later this will save to your profile and trigger notifications.',
  );

  const handleSave = () => {
    // Demo: just go back to calendar; later this will POST to backend
    try {
      router.push('/calendar-v1-demo');
    } catch {
      // no-op
    }
  };

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Add event (demo)',
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
            New event
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            This is a front-end demo. Eventually, these events will live
            on your account and can send reminders before the date.
          </Text>
        </View>

        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
            gap: spacing.sm,
          }}
        >
          {/* Title */}
          <View>
            <Text
              style={{
                fontSize: 13,
                fontWeight: '600',
                color: colors.text,
                marginBottom: 4,
              }}
            >
              Title
            </Text>
            <TextInput
              value={title}
              onChangeText={setTitle}
              placeholder="Vintage trade night"
              placeholderTextColor={colors.mutedText}
              style={{
                borderRadius: 8,
                borderWidth: 1,
                borderColor: colors.border,
                paddingHorizontal: spacing.sm,
                paddingVertical: 8,
                color: colors.text,
                fontSize: 14,
              }}
            />
          </View>

          {/* Date */}
          <View>
            <Text
              style={{
                fontSize: 13,
                fontWeight: '600',
                color: colors.text,
                marginBottom: 4,
              }}
            >
              Date (yyyy-mm-dd)
            </Text>
            <TextInput
              value={date}
              onChangeText={setDate}
              placeholder="2025-03-21"
              placeholderTextColor={colors.mutedText}
              style={{
                borderRadius: 8,
                borderWidth: 1,
                borderColor: colors.border,
                paddingHorizontal: spacing.sm,
                paddingVertical: 8,
                color: colors.text,
                fontSize: 14,
              }}
            />
          </View>

          {/* Type */}
          <View>
            <Text
              style={{
                fontSize: 13,
                fontWeight: '600',
                color: colors.text,
                marginBottom: 4,
              }}
            >
              Type
            </Text>
            <View
              style={{
                flexDirection: 'row',
                flexWrap: 'wrap',
                gap: spacing.xs,
              }}
            >
              {EVENT_TYPES.map((t) => {
                const active = t === type;
                return (
                  <TouchableOpacity
                    key={t}
                    activeOpacity={0.85}
                    onPress={() => setType(t)}
                    style={{
                      paddingHorizontal: spacing.sm,
                      paddingVertical: 6,
                      borderRadius: 999,
                      borderWidth: 1,
                      borderColor: active
                        ? colors.primary
                        : colors.border,
                      backgroundColor: active
                        ? colors.primary
                        : colors.surface,
                    }}
                  >
                    <Text
                      style={{
                        fontSize: 12,
                        fontWeight: '600',
                        color: active
                          ? colors.onPrimary
                          : colors.text,
                      }}
                    >
                      {t}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Location */}
          <View>
            <Text
              style={{
                fontSize: 13,
                fontWeight: '600',
                color: colors.text,
                marginBottom: 4,
              }}
            >
              Location
            </Text>
            <TextInput
              value={location}
              onChangeText={setLocation}
              placeholder="City / venue"
              placeholderTextColor={colors.mutedText}
              style={{
                borderRadius: 8,
                borderWidth: 1,
                borderColor: colors.border,
                paddingHorizontal: spacing.sm,
                paddingVertical: 8,
                color: colors.text,
                fontSize: 14,
              }}
            />
          </View>

          {/* Note */}
          <View>
            <Text
              style={{
                fontSize: 13,
                fontWeight: '600',
                color: colors.text,
                marginBottom: 4,
              }}
            >
              Notes
            </Text>
            <TextInput
              value={note}
              onChangeText={setNote}
              multiline
              placeholder="What do you want to remember about this event?"
              placeholderTextColor={colors.mutedText}
              style={{
                borderRadius: 8,
                borderWidth: 1,
                borderColor: colors.border,
                paddingHorizontal: spacing.sm,
                paddingVertical: 8,
                color: colors.text,
                fontSize: 14,
                minHeight: 80,
                textAlignVertical: 'top',
              }}
            />
          </View>
        </View>

        {/* Save button */}
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'flex-end',
          }}
        >
          <TouchableOpacity
            activeOpacity={0.9}
            onPress={handleSave}
            style={{
              borderRadius: 999,
              paddingHorizontal: spacing.lg,
              paddingVertical: 10,
              backgroundColor: colors.primary,
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: colors.onPrimary,
              }}
            >
              Save (demo)
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </>
  );
}
TS

#######################################
# calendar-event-detail-demo.tsx
#######################################
FILE2="app/calendar-event-detail-demo.tsx"
cp "$FILE2" "$FILE2.bak-$(date +%s)" 2>/dev/null || true

cat > "$FILE2" <<'TS'
import React from 'react';
import {
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import {
  Stack,
  useLocalSearchParams,
  router,
} from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';

export default function CalendarEventDetailDemoScreen() {
  const { colors, spacing, radii } = useAppTheme();
  const params = useLocalSearchParams<{
    id?: string;
    title?: string;
    date?: string;
    type?: string;
    location?: string;
    note?: string;
    source?: string;
    segment?: string;
  }>();

  const title = (params.title as string) ?? 'Event';
  const date = (params.date as string) ?? '2025-02-18';
  const type = (params.type as string) ?? 'Card show';
  const location = (params.location as string) ?? '';
  const note =
    (params.note as string) ??
    'Demo event — in the real app this would be loaded from your calendar data.';
  const source = (params.source as string) ?? '';
  const segment = (params.segment as string) ?? 'my';

  const isMyEvent = segment === 'my';

  const handleAddToMyEvents = () => {
    // Demo only: navigate back to calendar; later this will POST to backend
    try {
      router.push('/calendar-v1-demo');
    } catch {
      // no-op
    }
  };

  const handleOpenSignup = () => {
    // Demo only: later we can open an external link or deep link to signup
    try {
      router.push('/calendar-v1-demo');
    } catch {
      // no-op
    }
  };

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Event details (demo)',
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
            {title}
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            {date} · {type}
          </Text>
          {location ? (
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
                marginTop: 2,
              }}
            >
              {location}
            </Text>
          ) : null}
        </View>

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
            Details
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            {note}
          </Text>

          {source ? (
            <Text
              style={{
                fontSize: 12,
                color: colors.mutedText,
                marginTop: spacing.sm,
              }}
            >
              Source: {source}
            </Text>
          ) : null}
        </View>

        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
            gap: spacing.sm,
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
            Actions
          </Text>

          {isMyEvent ? (
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
                marginBottom: spacing.sm,
              }}
            >
              Later you&apos;ll be able to enable reminders for this event:
              e.g. 3 days before, or same-day morning.
            </Text>
          ) : (
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
                marginBottom: spacing.sm,
              }}
            >
              This is a major drop or release. In the real app you could
              jump to signup, preorders, or add a personal reminder.
            </Text>
          )}

          {isMyEvent ? (
            <TouchableOpacity
              activeOpacity={0.9}
              onPress={handleAddToMyEvents}
              style={{
                borderRadius: 999,
                paddingHorizontal: spacing.lg,
                paddingVertical: 10,
                backgroundColor: colors.primary,
                alignSelf: 'flex-start',
              }}
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: colors.onPrimary,
                }}
              >
                Back to my events
              </Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              activeOpacity={0.9}
              onPress={handleOpenSignup}
              style={{
                borderRadius: 999,
                paddingHorizontal: spacing.lg,
                paddingVertical: 10,
                backgroundColor: colors.primary,
                alignSelf: 'flex-start',
              }}
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: colors.onPrimary,
                }}
              >
                Back to calendar
              </Text>
            </TouchableOpacity>
          )}
        </View>
      </ScrollView>
    </>
  );
}
TS

echo "Created calendar-add-event-demo.tsx and calendar-event-detail-demo.tsx (backups if existed)."
