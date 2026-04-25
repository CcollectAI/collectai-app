/**
 * EmptyState - Consistent empty state component with illustration.
 * Used when lists/screens have no data to display.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface Props {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  iconColor?: string;
  style?: ViewStyle;
  colors: {
    text: string;
    muted: string;
    accent: string;
  };
}

export function EmptyState({
  icon,
  title,
  subtitle,
  action,
  iconColor,
  style,
  colors,
}: Props) {
  return (
    <View style={[styles.container, style]}>
      <View style={[styles.iconWrapper, { backgroundColor: (iconColor || colors.accent) + '15' }]}>
        <Ionicons
          name={icon}
          size={48}
          color={iconColor || colors.accent}
        />
      </View>

      <Text style={[styles.title, { color: colors.text }]}>
        {title}
      </Text>

      {subtitle && (
        <Text style={[styles.subtitle, { color: colors.muted }]}>
          {subtitle}
        </Text>
      )}

      {action && (
        <View style={styles.actionContainer}>
          {action}
        </View>
      )}
    </View>
  );
}

// Pre-built empty states for common screens
export function EmptyCollection({
  colors,
  onAddPress,
}: {
  colors: { text: string; muted: string; accent: string };
  onAddPress?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <EmptyState
      icon="albums-outline"
      title={t('empty_state.no_items')}
      subtitle="Start building your collection by adding your first item"
      colors={colors}
    />
  );
}

export function EmptyWatchlist({
  colors,
}: {
  colors: { text: string; muted: string; accent: string };
}) {
  const { t } = useTranslation();
  return (
    <EmptyState
      icon="eye-outline"
      title={t('empty_state.watchlist_empty')}
      subtitle="Add items you want to track and get notified when prices drop"
      colors={colors}
    />
  );
}

export function EmptySearch({
  query,
  colors,
}: {
  query: string;
  colors: { text: string; muted: string; accent: string };
}) {
  const { t } = useTranslation();
  return (
    <EmptyState
      icon="search-outline"
      title={t('empty_state.no_results')}
      subtitle={`We couldn't find anything matching "${query}"`}
      colors={colors}
    />
  );
}

export function EmptyEvents({
  colors,
}: {
  colors: { text: string; muted: string; accent: string };
}) {
  const { t } = useTranslation();
  return (
    <EmptyState
      icon="calendar-outline"
      title={t('empty_state.no_events')}
      subtitle="Check back later for drops, meetups, and streams"
      colors={colors}
    />
  );
}

export function EmptyMessages({
  colors,
}: {
  colors: { text: string; muted: string; accent: string };
}) {
  const { t } = useTranslation();
  return (
    <EmptyState
      icon="chatbubbles-outline"
      title={t('empty_state.no_messages')}
      subtitle="Connect with other collectors to start a conversation"
      colors={colors}
    />
  );
}

export function EmptyProjects({
  colors,
}: {
  colors: { text: string; muted: string; accent: string };
}) {
  const { t } = useTranslation();
  return (
    <EmptyState
      icon="color-palette-outline"
      title={t('empty_state.no_projects')}
      subtitle="Start a build or paint project to track your progress"
      colors={colors}
    />
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    paddingVertical: 48,
  },
  iconWrapper: {
    width: 96,
    height: 96,
    borderRadius: 48,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    maxWidth: 280,
  },
  actionContainer: {
    marginTop: 24,
  },
});

export default EmptyState;
