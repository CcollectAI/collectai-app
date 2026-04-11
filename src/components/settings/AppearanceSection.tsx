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
import type { Region, Currency, LanguagePreference } from '@/lib/settings';
import { fireHaptic, HapticIntent } from '@/haptics';
import { AnimatedPressable } from '@/motion';
import { supabase } from '@/lib/supabase';
import { API_BASE } from '@/api/config';
import { logger } from '@/lib/logger';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import { useTranslation } from 'react-i18next';

const REGION_OPTIONS: { value: Region; label: string }[] = [
  { value: 'americas', label: 'Americas' },
  { value: 'europe', label: 'Europe' },
  { value: 'japan', label: 'Japan' },
  { value: 'korea', label: 'South Korea' },
  { value: 'oceania', label: 'Australia / Oceania' },
  { value: 'other', label: 'Other' },
];

const CURRENCY_OPTIONS: Currency[] = ['EUR', 'USD', 'GBP', 'JPY', 'KRW', 'AUD', 'CAD'];

// Language options — 'auto' is always first, then native-name language entries.
// Native names intentionally — a user looking for their language should recognize it.
const LANGUAGE_OPTIONS: { value: LanguagePreference; label: string }[] = [
  { value: 'auto', label: 'System default' },
  { value: 'en', label: 'English' },
  { value: 'nl', label: 'Nederlands' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
  { value: 'es', label: 'Español' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
];

function AppearanceSectionInner() {
  const { colors } = useAppTheme();
  const { settings, updateSettings } = useSettings();
  const { t } = useTranslation();
  const [regionPickerVisible, setRegionPickerVisible] = useState(false);
  const [currencyPickerVisible, setCurrencyPickerVisible] = useState(false);
  const [languagePickerVisible, setLanguagePickerVisible] = useState(false);

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

  const handleLanguageChange = (language: LanguagePreference) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    updateSettings({ language });
    setLanguagePickerVisible(false);
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
          <Text style={[styles.sectionTitle, { color: colors.text }]}>{t('settings.region_currency')}</Text>
        </View>

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => setRegionPickerVisible(true)}
          accessibilityRole="button"
          accessibilityLabel={t('settings.change_region_a11y')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.region')}</Text>
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
          accessibilityLabel={t('settings.change_currency_a11y')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.currency')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{settings.currency}</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => setLanguagePickerVisible(true)}
          accessibilityRole="button"
          accessibilityLabel={t('settings.language')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.language')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>
              {LANGUAGE_OPTIONS.find((l) => l.value === settings.language)?.label ?? 'System default'}
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>
      </View>

      {/* Preferences */}
      <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.sectionHeader}>
          <Ionicons name="settings-outline" size={18} color={colors.accent} />
          <Text style={[styles.sectionTitle, { color: colors.text }]}>{t('settings.preferences')}</Text>
        </View>

        <View style={styles.settingRow}>
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.dark_mode')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('settings.dark_mode_desc')}</Text>
          </View>
          <Switch
            value={settings.isDark}
            onValueChange={(v) => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              updateSettings({ isDark: v });
            }}
            trackColor={{ false: colors.border, true: colors.accent }}
            thumbColor={colors.accentText}
            accessibilityLabel={t('settings.dark_mode')}
          />
        </View>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <View style={styles.settingRow}>
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.haptics')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('settings.haptics_desc')}</Text>
          </View>
          <Switch
            value={settings.hapticsEnabled}
            onValueChange={(v) => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: true });
              updateSettings({ hapticsEnabled: v });
            }}
            trackColor={{ false: colors.border, true: colors.accent }}
            thumbColor={colors.accentText}
            accessibilityLabel={t('settings.haptics')}
          />
        </View>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <View style={styles.settingRow}>
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.animations')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('settings.animations_desc')}</Text>
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
            <Text style={[styles.pickerTitle, { color: colors.text }]}>{t('settings.select_region')}</Text>
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
            <Text style={[styles.pickerTitle, { color: colors.text }]}>{t('settings.select_currency')}</Text>
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

      {/* Language Picker Modal */}
      <Modal
        visible={languagePickerVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setLanguagePickerVisible(false)}
      >
        <View style={[styles.pickerModal, { backgroundColor: colors.background }]}>
          <View style={[styles.pickerHeader, { borderBottomColor: colors.border }]}>
            <TouchableOpacity onPress={() => setLanguagePickerVisible(false)} accessibilityLabel={t('common.close')}>
              <Ionicons name="close" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={[styles.pickerTitle, { color: colors.text }]}>{t('settings.language')}</Text>
            <View style={{ width: 24 }} />
          </View>
          {LANGUAGE_OPTIONS.map((opt) => (
            <TouchableOpacity
              key={opt.value}
              style={[
                styles.pickerRow,
                { borderBottomColor: colors.border },
                opt.value === settings.language && { backgroundColor: colors.accent + '15' },
              ]}
              onPress={() => handleLanguageChange(opt.value)}
              accessibilityRole="radio"
              accessibilityState={{ selected: opt.value === settings.language }}
              accessibilityLabel={opt.label}
            >
              <Text style={[styles.pickerRowText, { color: colors.text }]}>{opt.label}</Text>
              {opt.value === settings.language && (
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
