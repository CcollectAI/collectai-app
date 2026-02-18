/**
 * AlertSettings Component
 * Settings UI for alert preferences.
 */

import React, { useState, useEffect } from 'react';
import { View, Text, Switch, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { AlertPreferences, DEFAULT_ALERT_PREFERENCES } from '@/types/insights';
import { featureFlags } from '@/config/featureFlags';

type AlertSettingsProps = {
  preferences: AlertPreferences;
  onUpdate: (preferences: AlertPreferences) => void;
};

type FrequencyOption = 'immediate' | 'daily' | 'weekly';

const FREQUENCY_OPTIONS: { value: FrequencyOption; label: string }[] = [
  { value: 'immediate', label: 'Immediate' },
  { value: 'daily', label: 'Daily Digest' },
  { value: 'weekly', label: 'Weekly Digest' },
];

const THRESHOLD_OPTIONS = [5, 10, 15, 20, 25];

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
        <Text style={[styles.label, { color: colors.text }]}>{label}</Text>
        <Text style={[styles.description, { color: colors.muted }]}>{description}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        accessibilityLabel={label}
        trackColor={{ false: colors.border, true: colors.accent }}
      />
    </View>
  );
}

type ThresholdRowProps = {
  label: string;
  value: number;
  onValueChange: (value: number) => void;
  enabled: boolean;
  colors: ThemeColors;
};

function ThresholdRow({ label, value, onValueChange, enabled, colors }: ThresholdRowProps) {
  if (!enabled) return null;

  return (
    <View style={styles.thresholdRow}>
      <Text style={[styles.thresholdLabel, { color: colors.muted }]}>{label}</Text>
      <View style={styles.thresholdOptions}>
        {THRESHOLD_OPTIONS.map((opt) => (
          <Pressable
            key={opt}
            style={[
              styles.thresholdOption,
              value === opt && { backgroundColor: colors.accent },
              value !== opt && { borderColor: colors.border, borderWidth: 1 },
            ]}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onValueChange(opt); }}
            accessibilityRole="radio"
            accessibilityState={{ checked: value === opt }}
            accessibilityLabel={`${opt}%`}
          >
            <Text
              style={[
                styles.thresholdOptionText,
                { color: value === opt ? '#FFFFFF' : colors.text },
              ]}
            >
              {opt}%
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

export function AlertSettings({ preferences, onUpdate }: AlertSettingsProps) {
  const { colors } = useAppTheme();
  const [prefs, setPrefs] = useState<AlertPreferences>(preferences);

  useEffect(() => {
    setPrefs(preferences);
  }, [preferences]);

  const updatePref = <K extends keyof AlertPreferences>(key: K, value: AlertPreferences[K]) => {
    const updated = { ...prefs, [key]: value };
    setPrefs(updated);
    onUpdate(updated);
  };

  if (!featureFlags.FEATURE_DATA_INSIGHTS_ALERTS) {
    return null;
  }

  return (
    <View
      style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="none"
      accessibilityLabel="Alert settings section"
    >
      <Text style={[styles.sectionTitle, { color: colors.text }]} accessibilityRole="header">
        Alert Types
      </Text>

      <SettingRow
        label="Price Drops"
        description="Notify when watched items drop in price"
        value={prefs.priceDropEnabled}
        onValueChange={(v) => updatePref('priceDropEnabled', v)}
        colors={colors}
      />

      <ThresholdRow
        label="Drop threshold"
        value={prefs.priceDropThreshold}
        onValueChange={(v) => updatePref('priceDropThreshold', v)}
        enabled={prefs.priceDropEnabled}
        colors={colors}
      />

      <View style={[styles.separator, { backgroundColor: colors.border }]} />

      <SettingRow
        label="Price Increases"
        description="Notify when your items increase in value"
        value={prefs.priceIncreaseEnabled}
        onValueChange={(v) => updatePref('priceIncreaseEnabled', v)}
        colors={colors}
      />

      <ThresholdRow
        label="Increase threshold"
        value={prefs.priceIncreaseThreshold}
        onValueChange={(v) => updatePref('priceIncreaseThreshold', v)}
        enabled={prefs.priceIncreaseEnabled}
        colors={colors}
      />

      <View style={[styles.separator, { backgroundColor: colors.border }]} />

      <SettingRow
        label="New Listings"
        description="Notify when new listings match your watchlist"
        value={prefs.newListingEnabled}
        onValueChange={(v) => updatePref('newListingEnabled', v)}
        colors={colors}
      />

      <View style={[styles.separator, { backgroundColor: colors.border }]} />

      <SettingRow
        label="Milestones"
        description="Celebrate collection value milestones"
        value={prefs.milestoneEnabled}
        onValueChange={(v) => updatePref('milestoneEnabled', v)}
        colors={colors}
      />

      <View style={[styles.separator, { backgroundColor: colors.border }]} />

      {/* Frequency */}
      <Text style={[styles.sectionTitle, { color: colors.text, marginTop: 16 }]}>
        Notification Frequency
      </Text>

      <View style={styles.frequencyOptions}>
        {FREQUENCY_OPTIONS.map((opt) => (
          <Pressable
            key={opt.value}
            style={[
              styles.frequencyOption,
              { borderColor: colors.border },
              prefs.frequency === opt.value && { backgroundColor: colors.accent, borderColor: colors.accent },
            ]}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); updatePref('frequency', opt.value); }}
            accessibilityRole="radio"
            accessibilityState={{ checked: prefs.frequency === opt.value }}
            accessibilityLabel={opt.label}
          >
            <Text
              style={[
                styles.frequencyOptionText,
                { color: prefs.frequency === opt.value ? '#FFFFFF' : colors.text },
              ]}
            >
              {opt.label}
            </Text>
          </Pressable>
        ))}
      </View>
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
  thresholdRow: {
    paddingVertical: 8,
    paddingLeft: 16,
  },
  thresholdLabel: {
    fontSize: 12,
    marginBottom: 8,
  },
  thresholdOptions: {
    flexDirection: 'row',
    gap: 8,
  },
  thresholdOption: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  thresholdOptionText: {
    fontSize: 13,
    fontWeight: '500',
  },
  frequencyOptions: {
    flexDirection: 'row',
    gap: 8,
  },
  frequencyOption: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  frequencyOptionText: {
    fontSize: 13,
    fontWeight: '500',
  },
});

export default AlertSettings;
