import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Stack, router } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';

export default function CalendarEntryDebugScreen() {
  const { colors, spacing } = useAppTheme();

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Calendar Entry (Debug)',
        }}
      />
      <View
        style={{
          flex: 1,
          padding: spacing.lg,
          backgroundColor: colors.background,
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <TouchableOpacity
          onPress={() => router.push('/calendar-v1-demo')}
          style={{
            paddingVertical: 16,
            paddingHorizontal: 28,
            borderRadius: 12,
            backgroundColor: colors.primary,
          }}
        >
          <Text
            style={{
              fontSize: 18,
              fontWeight: '700',
              color: colors.onPrimary,
            }}
          >
            Open Calendar
          </Text>
        </TouchableOpacity>

        <Text
          style={{
            marginTop: spacing.md,
            fontSize: 13,
            color: colors.mutedText,
            textAlign: 'center',
          }}
        >
          This screen is temporary and helps you access the calendar
          until we wire it into Portfolio/Analytics without breaking UI.
        </Text>
      </View>
    </>
  );
}
