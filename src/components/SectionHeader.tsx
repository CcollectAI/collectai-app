/**
 * SectionHeader — Consistent section header for screens.
 * Standardizes typography, spacing, and optional right action.
 */

import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  style?: ViewStyle;
}

export const SectionHeader = React.memo(function SectionHeader({
  title,
  subtitle,
  action,
  style,
}: SectionHeaderProps) {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.container, style]}>
      <View style={styles.textColumn}>
        <Text style={[styles.title, { color: colors.text }]}>{title}</Text>
        {subtitle && (
          <Text style={[styles.subtitle, { color: colors.muted }]}>{subtitle}</Text>
        )}
      </View>
      {action && <View style={styles.action}>{action}</View>}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
    paddingHorizontal: 16,
  },
  textColumn: {
    flex: 1,
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  subtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  action: {
    marginLeft: 12,
  },
});

export default SectionHeader;
