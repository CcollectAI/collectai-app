/**
 * AccessibilitySettings Component
 * Settings UI for accessibility options.
 */

import React from 'react';
import { View, Text, Switch, StyleSheet } from 'react-native';
import { useAccessibility } from '@/lib/accessibilityContext';
import { useAppTheme } from '@/hooks/useAppTheme';
import { featureFlags } from '@/config/featureFlags';

type ThemeColors = ReturnType<typeof useAppTheme>['colors'];

type SettingRowProps = {
  label: string;
  description: string;
  value: boolean;
  onValueChange: (value: boolean) => void;
  colors: ThemeColors;
};

function SettingRow({ label, description, value, onValueChange, colors }: SettingRowProps) {
  return (
    <View style={styles.row}>
      <View style={styles.rowText}>
        <Text
          style={[styles.label, { color: colors.text }]}
          accessibilityRole="text"
        >
          {label}
        </Text>
        <Text
          style={[styles.description, { color: colors.muted }]}
          accessibilityRole="text"
        >
          {description}
        </Text>
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        accessibilityLabel={label}
        accessibilityHint={`Toggle ${label.toLowerCase()}`}
        trackColor={{ false: colors.border, true: colors.accent }}
      />
    </View>
  );
}

export function AccessibilitySettings() {
  const { colors } = useAppTheme();
  const { settings, updateSettings, systemReduceMotion } = useAccessibility();

  if (!featureFlags.FEATURE_ACCESSIBILITY_ENHANCEMENTS) {
    return null;
  }

  return (
    <View
      style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="none"
      accessibilityLabel="Accessibility settings section"
    >
      <Text
        style={[styles.sectionTitle, { color: colors.text }]}
        accessibilityRole="header"
      >
        Accessibility
      </Text>

      <SettingRow
        label="High Contrast Mode"
        description="Increases color contrast for better visibility"
        value={settings.highContrastEnabled}
        onValueChange={(v) => updateSettings({ highContrastEnabled: v })}
        colors={colors}
      />

      <View style={[styles.separator, { backgroundColor: colors.border }]} />

      <SettingRow
        label="Reduce Motion"
        description={
          systemReduceMotion
            ? "Following system setting (enabled)"
            : "Minimize animations and transitions"
        }
        value={settings.reduceMotionEnabled || systemReduceMotion}
        onValueChange={(v) => updateSettings({ reduceMotionEnabled: v })}
        colors={colors}
      />

      <View style={[styles.separator, { backgroundColor: colors.border }]} />

      <SettingRow
        label="Large Text"
        description="Increase text size throughout the app"
        value={settings.largeTextEnabled}
        onValueChange={(v) => updateSettings({ largeTextEnabled: v })}
        colors={colors}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 16,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  rowText: {
    flex: 1,
    marginRight: 12,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
  },
  description: {
    fontSize: 12,
    marginTop: 2,
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 8,
  },
});

export default AccessibilitySettings;
