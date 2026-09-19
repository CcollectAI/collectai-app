/**
 * PrivacySettingsSection — Privacy toggles (collection value, item count, discovery, online status).
 * Extracted from Settings.tsx.
 */

import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, Switch, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { supabase } from '@/lib/supabase';
import { fireHaptic, HapticIntent } from '@/haptics';
import { logger } from '@/lib/logger';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import { clearProfileCaches } from '@/data/CachedDataProvider';
import { AnimatedPressable } from '@/motion';
import { useTranslation } from 'react-i18next';

type PrivacySettings = {
  showCollectionValue: boolean;
  showItemCount: boolean;
  allowDiscovery: boolean;
  showOnlineStatus: boolean;
};

const DEFAULT_PRIVACY: PrivacySettings = {
  showCollectionValue: true,
  showItemCount: true,
  allowDiscovery: true,
  showOnlineStatus: false,
};

function PrivacySettingsSectionInner() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { t } = useTranslation();
  const [privacy, setPrivacy] = useState<PrivacySettings>(DEFAULT_PRIVACY);
  const [loadingPrivacy, setLoadingPrivacy] = useState(true);
  // DEFAULT_PRIVACY says "Allow discovery" and "Show collection value" are ON.
  // Rendered after a FAILED read, it told a member who had switched discovery
  // off that they were discoverable. Only "no row" (maybeSingle → null, no
  // error) means the defaults are the truth; everything else is a failure.
  const [privacyLoadFailed, setPrivacyLoadFailed] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);
  const [savingPrivacy, setSavingPrivacy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoadingPrivacy(true);
    setPrivacyLoadFailed(false);
    const loadPrivacySettings = async () => {
      try {
        // getSession() reads the cached session from local storage (instant);
        // getUser() hits the auth server over the network with no timeout and
        // hangs the whole load — and therefore this spinner — forever on a bad
        // connection. We only need the user id, so the local session is enough.
        const { data: { session } } = await supabase.auth.getSession();
        const user = session?.user;
        if (cancelled) return;
        if (!user) {
          // Settings is a signed-in screen; no session here is the cold-start
          // window, not a member without settings. Say so rather than defaults.
          setPrivacyLoadFailed(true);
          return;
        }

        const { data, error } = await supabase
          .from('user_privacy_settings')
          .select('*')
          .eq('user_id', user.id)
          .maybeSingle();

        if (cancelled) return;
        // The client RESOLVES a timeout as { error: { code: 'TIMEOUT' } } rather
        // than throwing (installRequestTimeouts), so the catch below never sees it.
        if (error) {
          logger.error('[Settings] Failed to load privacy settings:', error);
          setPrivacyLoadFailed(true);
          return;
        }
        if (data) {
          setPrivacy({
            showCollectionValue: data.show_collection_value ?? true,
            showItemCount: data.show_item_count ?? true,
            allowDiscovery: data.allow_discovery ?? true,
            showOnlineStatus: data.show_online_status ?? false,
          });
        }
      } catch (err) {
        logger.error('[Settings] Failed to load privacy settings:', err);
        if (!cancelled) setPrivacyLoadFailed(true);
      } finally {
        if (!cancelled) setLoadingPrivacy(false);
      }
    };

    loadPrivacySettings();
    return () => { cancelled = true; };
  }, [retryNonce]);

  const updatePrivacy = async (key: keyof PrivacySettings, value: boolean) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const prevPrivacy = { ...privacy };
    setPrivacy((prev) => ({ ...prev, [key]: value }));
    setSavingPrivacy(true);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const user = session?.user;
      if (!user) {
        // Nothing was written — do not leave the optimistic toggle standing,
        // which reads exactly like a saved change.
        setPrivacy(prevPrivacy);
        showToast({ message: t('settings.privacy_save_failed', { defaultValue: 'Failed to save privacy setting' }), type: 'error' });
        return;
      }

      const columnMap: Record<keyof PrivacySettings, string> = {
        showCollectionValue: 'show_collection_value',
        showItemCount: 'show_item_count',
        allowDiscovery: 'allow_discovery',
        showOnlineStatus: 'show_online_status',
      };

      const { error } = await supabase
        .from('user_privacy_settings')
        .upsert({
          user_id: user.id,
          [columnMap[key]]: value,
          updated_at: new Date().toISOString(),
        }, {
          onConflict: 'user_id',
        });

      if (error) {
        // logger.error, not warn — warn is stripped in release builds.
        logger.error('[Settings] Failed to save privacy setting:', error);
        setPrivacy(prevPrivacy);
        showToast({ message: t('settings.privacy_save_failed', { defaultValue: 'Failed to save privacy setting' }), type: 'error' });
      } else {
        // Profiles are cached for the session and now carry privacy-gated
        // stats, so without this the user would toggle "Show collection value"
        // off and still see the number on their own profile.
        await clearProfileCaches();
      }
    } catch (err) {
      logger.error('[Settings] Privacy update error:', err);
      // The toggle snaps back; without a message that reads as a dead switch.
      setPrivacy(prevPrivacy);
      showToast({ message: t('settings.privacy_save_failed', { defaultValue: 'Failed to save privacy setting' }), type: 'error' });
    } finally {
      setSavingPrivacy(false);
    }
  };

  const TOGGLE_ITEMS: { key: keyof PrivacySettings; label: string; hint: string }[] = [
    { key: 'showCollectionValue', label: 'Show collection value', hint: 'Display your total collection value on your profile' },
    { key: 'showItemCount', label: 'Show item count', hint: 'Display how many items you have collected' },
    { key: 'allowDiscovery', label: 'Allow discovery', hint: 'Let other collectors find you by interests' },
    { key: 'showOnlineStatus', label: 'Show online status', hint: 'Let others see when you\'re active' },
  ];

  return (
    <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.sectionHeader}>
        <Ionicons name="shield-checkmark-outline" size={18} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Privacy</Text>
        {savingPrivacy && <ActivityIndicator size="small" color={colors.accent} style={{ marginLeft: 8 }} />}
      </View>

      {loadingPrivacy ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.muted }]}>{t('settings.loading', { defaultValue: 'Loading settings...' })}</Text>
        </View>
      ) : privacyLoadFailed ? (
        <View style={styles.errorRow}>
          <Text style={[styles.settingHint, { color: colors.muted }]}>
            {t('settings.privacy_load_failed', { defaultValue: "Couldn't load your privacy settings" })}
          </Text>
          <AnimatedPressable
            onPress={() => setRetryNonce((n) => n + 1)}
            accessibilityRole="button"
            accessibilityLabel={t('common.try_again', { defaultValue: 'Try again' })}
          >
            <Text style={[styles.retryText, { color: colors.accent }]}>
              {t('common.try_again', { defaultValue: 'Try again' })}
            </Text>
          </AnimatedPressable>
        </View>
      ) : (
        TOGGLE_ITEMS.map((item, idx) => (
          <React.Fragment key={item.key}>
            {idx > 0 && <View style={[styles.divider, { backgroundColor: colors.border }]} />}
            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>{item.label}</Text>
                <Text style={[styles.settingHint, { color: colors.muted }]}>{item.hint}</Text>
              </View>
              <Switch
                value={privacy[item.key]}
                onValueChange={(v) => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); updatePrivacy(item.key, v); }}
                trackColor={{ false: colors.border, true: colors.accent }}
                thumbColor={colors.accentText}
                accessibilityLabel={item.label}
              />
            </View>
          </React.Fragment>
        ))
      )}
    </View>
  );
}

export const PrivacySettingsSection = React.memo(PrivacySettingsSectionInner);

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
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    gap: 8,
  },
  loadingText: {
    fontSize: textToken.md,
  },
  errorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 10,
    paddingVertical: 8,
  },
  retryText: {
    fontSize: textToken.md,
    fontWeight: fw.bold,
    minHeight: 24,
  },
});
