/**
 * AppearanceSection — Theme toggle, haptics, animations, region & currency pickers.
 * Extracted from Settings.tsx.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Switch,
  Modal,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings, REGION_DEFAULTS } from '@/lib/settings';
import type { Region, Currency } from '@/lib/settings';
import { fireHaptic, HapticIntent } from '@/haptics';
import { AnimatedPressable } from '@/motion';
import { supabase } from '@/lib/supabase';
import { API_BASE } from '@/api/config';
import { logger } from '@/lib/logger';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';

const REGION_OPTIONS: { value: Region; label: string }[] = [
  { value: 'americas', label: 'Americas' },
  { value: 'europe', label: 'Europe' },
  { value: 'japan', label: 'Japan' },
  { value: 'korea', label: 'South Korea' },
  { value: 'oceania', label: 'Australia / Oceania' },
  { value: 'other', label: 'Other' },
];

const CURRENCY_OPTIONS: Currency[] = ['EUR', 'USD', 'GBP', 'JPY', 'KRW', 'AUD', 'CAD'];

function AppearanceSectionInner() {
  const { colors } = useAppTheme();
  const { settings, updateSettings } = useSettings();
  const [regionPickerVisible, setRegionPickerVisible] = useState(false);
  const [currencyPickerVisible, setCurrencyPickerVisible] = useState(false);

  const handleRegionChange = async (region: Region) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const defaults = REGION_DEFAULTS[region];
    updateSettings({ region, currency: defaults.currency, numberLocale: defaults.numberLocale });
    setRegionPickerVisible(false);
    try {
      const auth = await supabase.auth.getSession();
      if (auth.data?.session) {
        await fetch(`${API_BASE}/settings`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${auth.data.session.access_token}`,
          },
          body: JSON.stringify({ region, currency: defaults.currency, locale: defaults.numberLocale }),
        });
      }
    } catch (e) {
      logger.warn('[Settings] Failed to persist region to backend:', e);
    }
  };

  const handleCurrencyChange = async (currency: Currency) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    updateSettings({ currency });
    setCurrencyPickerVisible(false);
    try {
      const auth = await supabase.auth.getSession();
      if (auth.data?.session) {
        await fetch(`${API_BASE}/settings`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${auth.data.session.access_token}`,
          },
          body: JSON.stringify({ currency }),
        });
      }
    } catch (e) {
      logger.warn('[Settings] Failed to persist currency to backend:', e);
    }
  };

  return (
    <>
      {/* Region & Currency */}
      <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.sectionHeader}>
          <Ionicons name="globe-outline" size={18} color={colors.accent} />
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Region & Currency</Text>
        </View>

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => setRegionPickerVisible(true)}
          accessibilityRole="button"
          accessibilityLabel="Change region"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Region</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>
              {REGION_OPTIONS.find((r) => r.value === settings.region)?.label ?? 'Europe'}
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => setCurrencyPickerVisible(true)}
          accessibilityRole="button"
          accessibilityLabel="Change currency"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Currency</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{settings.currency}</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>
      </View>

      {/* Preferences */}
      <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.sectionHeader}>
          <Ionicons name="settings-outline" size={18} color={colors.accent} />
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Preferences</Text>
        </View>

        <View style={styles.settingRow}>
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Dark mode</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Switch between light and dark theme</Text>
          </View>
          <Switch
            value={settings.isDark}
            onValueChange={(v) => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              updateSettings({ isDark: v });
            }}
            trackColor={{ false: colors.border, true: colors.accent }}
            thumbColor={colors.accentText}
            accessibilityLabel="Dark mode"
          />
        </View>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <View style={styles.settingRow}>
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Haptic feedback</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Vibration feedback for interactions</Text>
          </View>
          <Switch
            value={settings.hapticsEnabled}
            onValueChange={(v) => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: true });
              updateSettings({ hapticsEnabled: v });
            }}
            trackColor={{ false: colors.border, true: colors.accent }}
            thumbColor={colors.accentText}
            accessibilityLabel="Haptic feedback"
          />
        </View>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <View style={styles.settingRow}>
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Animations</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Enable micro-animations throughout the app</Text>
          </View>
          <Switch
            value={settings.animationsEnabled}
            onValueChange={(v) => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              updateSettings({ animationsEnabled: v });
            }}
            trackColor={{ false: colors.border, true: colors.accent }}
            thumbColor={colors.accentText}
            accessibilityLabel="Animations"
          />
        </View>
      </View>

      {/* Region Picker Modal */}
      <Modal
        visible={regionPickerVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setRegionPickerVisible(false)}
      >
        <View style={[styles.pickerModal, { backgroundColor: colors.background }]}>
          <View style={[styles.pickerHeader, { borderBottomColor: colors.border }]}>
            <TouchableOpacity onPress={() => setRegionPickerVisible(false)} accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={[styles.pickerTitle, { color: colors.text }]}>Select Region</Text>
            <View style={{ width: 24 }} />
          </View>
          {REGION_OPTIONS.map((opt) => (
            <TouchableOpacity
              key={opt.value}
              style={[
                styles.pickerRow,
                { borderBottomColor: colors.border },
                opt.value === settings.region && { backgroundColor: colors.accent + '15' },
              ]}
              onPress={() => handleRegionChange(opt.value)}
              accessibilityRole="radio"
              accessibilityState={{ selected: opt.value === settings.region }}
              accessibilityLabel={opt.label}
            >
              <Text style={[styles.pickerRowText, { color: colors.text }]}>{opt.label}</Text>
              {opt.value === settings.region && (
                <Ionicons name="checkmark" size={20} color={colors.accent} />
              )}
            </TouchableOpacity>
          ))}
        </View>
      </Modal>

      {/* Currency Picker Modal */}
      <Modal
        visible={currencyPickerVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setCurrencyPickerVisible(false)}
      >
        <View style={[styles.pickerModal, { backgroundColor: colors.background }]}>
          <View style={[styles.pickerHeader, { borderBottomColor: colors.border }]}>
            <TouchableOpacity onPress={() => setCurrencyPickerVisible(false)} accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={[styles.pickerTitle, { color: colors.text }]}>Select Currency</Text>
            <View style={{ width: 24 }} />
          </View>
          {CURRENCY_OPTIONS.map((cur) => (
            <TouchableOpacity
              key={cur}
              style={[
                styles.pickerRow,
                { borderBottomColor: colors.border },
                cur === settings.currency && { backgroundColor: colors.accent + '15' },
              ]}
              onPress={() => handleCurrencyChange(cur)}
              accessibilityRole="radio"
              accessibilityState={{ selected: cur === settings.currency }}
              accessibilityLabel={cur}
            >
              <Text style={[styles.pickerRowText, { color: colors.text }]}>{cur}</Text>
              {cur === settings.currency && (
                <Ionicons name="checkmark" size={20} color={colors.accent} />
              )}
            </TouchableOpacity>
          ))}
        </View>
      </Modal>
    </>
  );
}

export const AppearanceSection = React.memo(AppearanceSectionInner);

const styles = StyleSheet.create({
  section: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: textToken.lg,
    fontWeight: fw.semibold,
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  settingInfo: {
    flex: 1,
    marginRight: 16,
  },
  settingLabel: {
    fontSize: textToken.lg,
    fontWeight: fw.medium,
  },
  settingHint: {
    fontSize: textToken.sm,
    marginTop: 2,
  },
  divider: {
    height: 1,
    marginVertical: 8,
  },
  pickerModal: {
    flex: 1,
  },
  pickerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  pickerTitle: {
    fontSize: textToken.lg,
    fontWeight: fw.bold,
  },
  pickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  pickerRowText: {
    fontSize: textToken.lg,
    fontWeight: fw.medium,
  },
});
