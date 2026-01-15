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
              e.g. 3 days before, or same-day morning, and attach items
              from your collection or watchlist.
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
              jump to signup/preorders or add key cards and figures from
              this drop straight into your watchlist.
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
                marginBottom: 8,
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
            <>
              <TouchableOpacity
                activeOpacity={0.9}
                onPress={handleOpenSignup}
                style={{
                  borderRadius: 999,
                  paddingHorizontal: spacing.lg,
                  paddingVertical: 10,
                  backgroundColor: colors.primary,
                  alignSelf: 'flex-start',
                  marginBottom: 8,
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

              <TouchableOpacity
                activeOpacity={0.9}
                onPress={() => {
                  try {
                    router.push('/watchlist-v1-demo');
                  } catch {
                    // no-op
                  }
                }}
                style={{
                  borderRadius: 999,
                  paddingHorizontal: spacing.lg,
                  paddingVertical: 10,
                  backgroundColor: colors.card,
                  borderWidth: 1,
                  borderColor: colors.border,
                  alignSelf: 'flex-start',
                }}
              >
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: '600',
                    color: colors.text,
                  }}
                >
                  View related watchlist (demo)
                </Text>
              </TouchableOpacity>
            </>
          )}
        </View>
      </ScrollView>
    </>
  );
}
