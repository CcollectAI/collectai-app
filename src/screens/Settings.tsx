import React, { useState, useEffect } from 'react';
import { View, ScrollView, Text, StyleSheet, Linking } from 'react-native';
import { useTranslation } from 'react-i18next';
import { useToast } from '@/components/Toast';
import Constants from 'expo-constants';
import { useRouter, type Href } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AccessibilitySettings } from '@/components/AccessibilitySettings';
import { AlertSettings } from '@/components/AlertSettings';
import { featureFlags, SELLING_ENABLED } from '@/config/featureFlags';
import { DEFAULT_ALERT_PREFERENCES, AlertPreferences } from '@/types/insights';
import { useSettings } from '@/lib/settings';
import { AnimatedPressable } from '@/motion';
import { Ionicons } from '@expo/vector-icons';
import { logger } from '@/lib/logger';
import { fireHaptic, HapticIntent } from '@/haptics';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import { collectorsApi } from '@/api/collectorsApi';
import { useFeatureTour } from '@/lib/featureTour';
import { PrivacySettingsSection } from '@/components/settings/PrivacySettingsSection';
import { NotificationPreferencesSection } from '@/components/settings/NotificationPreferencesSection';
import { AppearanceSection } from '@/components/settings/AppearanceSection';
import { ProfileEditSection } from '@/components/settings/ProfileEditSection';
import { DevForcePlanSection } from '@/components/settings/DevForcePlanSection';
import { DevSentryCrashSection } from '@/components/settings/DevSentryCrashSection';
import { MarketplaceConnectionsSection } from '@/components/settings/MarketplaceConnectionsSection';

export default function Settings() {
  const { t } = useTranslation();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { resetAll: resetFeatureTips } = useFeatureTour();
  const [alertPrefs, setAlertPrefs] = useState<AlertPreferences>(DEFAULT_ALERT_PREFERENCES);

  useEffect(() => {
    let cancelled = false;
    const loadAlertPreferences = async () => {
      try {
        const data = await collectorsApi.getAlertPreferences();
        if (cancelled) return;
        setAlertPrefs({
          priceDropEnabled: data.price_drop_enabled,
          priceDropThreshold: data.price_drop_threshold,
          newListingEnabled: data.new_listing_enabled,
          milestoneEnabled: data.milestone_enabled,
          priceIncreaseEnabled: data.price_increase_enabled,
          priceIncreaseThreshold: data.price_increase_threshold,
          frequency: data.frequency,
        });
      } catch (err) {
        logger.error('[Settings] Failed to load alert preferences:', err);
      }
    };
    loadAlertPreferences();
    return () => { cancelled = true; };
  }, []);

  const handleAlertPrefsUpdate = async (prefs: AlertPreferences) => {
    setAlertPrefs(prefs);
    try {
      await collectorsApi.updateAlertPreferences({
        price_drop_enabled: prefs.priceDropEnabled,
        price_drop_threshold: prefs.priceDropThreshold,
        new_listing_enabled: prefs.newListingEnabled,
        milestone_enabled: prefs.milestoneEnabled,
        price_increase_enabled: prefs.priceIncreaseEnabled,
        price_increase_threshold: prefs.priceIncreaseThreshold,
        frequency: prefs.frequency,
      });
    } catch (e) {
      logger.error('[Settings] Failed to persist alert preferences:', e);
    }
  };

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.background }]}
      contentContainerStyle={styles.content}
    >
      {/* Privacy Section */}
      <PrivacySettingsSection />

      {/* Notification category toggles. The API has always supported these; there
          was simply no screen for them, so a user had no way to turn any push
          category off. Must stay mounted whenever a sending worker is enabled. */}
      <NotificationPreferencesSection />

      {/* Appearance, Region & Currency, Preferences */}
      <AppearanceSection />

      {/* Accessibility Section */}
      {featureFlags.FEATURE_ACCESSIBILITY_ENHANCEMENTS && (
        <AccessibilitySettings />
      )}

      {/* Alerts Section */}
      {featureFlags.FEATURE_DATA_INSIGHTS_ALERTS && (
        <AlertSettings
          preferences={alertPrefs}
          onUpdate={handleAlertPrefsUpdate}
        />
      )}

      {/* Account Section (profile, password, sign out, billing, etc.) */}
      <ProfileEditSection />

      {/* Marketplace connections (eBay OAuth, defaults, listing chain).
          Hidden with the rest of selling: the section invites the user to
          "Sign in with your eBay account to list items directly", and there is
          no eBay OAuth behind it. */}
      {SELLING_ENABLED && <MarketplaceConnectionsSection />}

      {/* Dev-only: Force subscription tier (for previewing paid views) */}
      <DevForcePlanSection />

      {/* Dev-only: Sentry test buttons (verify PII scrubbing pipeline) */}
      <DevSentryCrashSection />

      {/* About Section */}
      <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.sectionHeader}>
          <Ionicons name="information-circle-outline" size={18} color={colors.accent} />
          <Text style={[styles.sectionTitle, { color: colors.text }]}>About</Text>
        </View>

        <View style={styles.settingRow}>
          <Text style={[styles.settingLabel, { color: colors.text }]}>Version</Text>
          <Text style={[styles.settingHint, { color: colors.muted }]}>
            {Constants.expoConfig?.version ?? '1.0.0'}
          </Text>
        </View>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push('/my-suggestions' as Href);
          }}
          accessibilityRole="link"
          accessibilityLabel={t('settings.my_suggestions')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.my_suggestions')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('settings.my_suggestions_desc')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            resetFeatureTips();
            showToast({ message: t('settings.reset_tips_toast'), type: 'success' });
          }}
          accessibilityRole="button"
          accessibilityLabel={t('settings.reset_tips_a11y')}
        >
          <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.reset_tips')}</Text>
          <Ionicons name="refresh-outline" size={18} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => Linking.openURL('mailto:support@sparrowcollect.com')}
          accessibilityRole="link"
          accessibilityLabel={t('settings.report_bug_a11y')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.report_bug')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>support@sparrowcollect.com</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/legal/privacy-policy')}
          accessibilityRole="link"
          accessibilityLabel={t('settings.privacy_policy')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.privacy_policy')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/legal/terms')}
          accessibilityRole="link"
          accessibilityLabel={t('settings.terms_of_service')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.terms_of_service')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/legal/user-policy')}
          accessibilityRole="link"
          accessibilityLabel={t('settings.user_policy')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.user_policy')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/legal/data-processing' as any)}
          accessibilityRole="link"
          accessibilityLabel={t('settings.data_processing')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.data_processing')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/condition-guide')}
          accessibilityRole="link"
          accessibilityLabel={t('settings.condition_guide')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('settings.condition_guide')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('settings.condition_guide_desc')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>
      </View>

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: 16,
    gap: 16,
    paddingBottom: 32,
  },
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
});
