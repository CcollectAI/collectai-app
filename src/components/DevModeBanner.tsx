import React from 'react';
import { View, Text } from 'react-native';
import { API_BASE_URL, API_KEY } from '@/config/api';
import { useTheme } from '@/theme';

export default function DevModeBanner() {
  const { colors, spacing } = useTheme();

  const baseUrl = API_BASE_URL || 'http://127.0.0.1:8080';
  const hasApiKey = Boolean(API_KEY);

  const isLocal =
    baseUrl.includes('127.0.0.1') ||
    baseUrl.includes('localhost') ||
    baseUrl.startsWith('http://10.') ||
    baseUrl.startsWith('http://192.168.');

  const envLabel = isLocal ? 'LOCAL DEV' : 'REMOTE API';
  const baseUrlDisplay =
    baseUrl.length > 60 ? baseUrl.slice(0, 57) + '...' : baseUrl;

  return (
    <View
      style={{
        borderRadius: spacing.md,
        padding: spacing.sm,
        marginBottom: spacing.md,
        backgroundColor: colors.card,
      }}
    >
      <Text
        style={{
          fontSize: 11,
          color: colors.muted,
          marginBottom: spacing.xs,
        }}
      >
        {envLabel} • {hasApiKey ? 'API key: set' : 'API key: not set'}
      </Text>
      <Text
        style={{
          fontSize: 11,
          color: colors.muted,
        }}
      >
        {baseUrlDisplay}
      </Text>
    </View>
  );
}
