import React, { useState, useEffect } from 'react';
import { View, ScrollView, Alert, Text, StyleSheet, Switch, ActivityIndicator } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { supabase } from "@/lib/supabase";
import ActionTile from '@/components/ActionTile';
import { AccessibilitySettings } from '@/components/AccessibilitySettings';
import { AlertSettings } from '@/components/AlertSettings';
import { featureFlags } from '@/config/featureFlags';
import { DEFAULT_ALERT_PREFERENCES, AlertPreferences } from '@/types/insights';
import { useSettings } from '@/lib/settings';
import { Ionicons } from '@expo/vector-icons';

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

export default function Settings() {
  const { colors } = useAppTheme();
  const { settings, updateSettings } = useSettings();
  const [alertPrefs, setAlertPrefs] = useState<AlertPreferences>(DEFAULT_ALERT_PREFERENCES);
  const [privacy, setPrivacy] = useState<PrivacySettings>(DEFAULT_PRIVACY);
  const [loadingPrivacy, setLoadingPrivacy] = useState(true);
  const [savingPrivacy, setSavingPrivacy] = useState(false);

  // Load privacy settings from Supabase on mount
  useEffect(() => {
    const loadPrivacySettings = async () => {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) {
          setLoadingPrivacy(false);
          return;
        }

        const { data, error } = await supabase
          .from('user_privacy_settings')
          .select('*')
          .eq('user_id', user.id)
          .single();

        if (data && !error) {
          setPrivacy({
            showCollectionValue: data.show_collection_value ?? true,
            showItemCount: data.show_item_count ?? true,
            allowDiscovery: data.allow_discovery ?? true,
            showOnlineStatus: data.show_online_status ?? false,
          });
        }
      } catch (err) {
        console.warn('[Settings] Failed to load privacy settings:', err);
      } finally {
        setLoadingPrivacy(false);
      }
    };

    loadPrivacySettings();
  }, []);

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) Alert.alert('Sign out error', error.message);
  };

  const handleAlertPrefsUpdate = (prefs: AlertPreferences) => {
    setAlertPrefs(prefs);
    // TODO: Persist to backend
  };

  const updatePrivacy = async (key: keyof PrivacySettings, value: boolean) => {
    const prevPrivacy = { ...privacy };
    setPrivacy((prev) => ({ ...prev, [key]: value }));
    setSavingPrivacy(true);

    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        setSavingPrivacy(false);
        return;
      }

      // Map state keys to database column names
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
        console.warn('[Settings] Failed to save privacy setting:', error);
        // Revert on error
        setPrivacy(prevPrivacy);
        Alert.alert('Error', 'Failed to save privacy setting');
      }
    } catch (err) {
      console.warn('[Settings] Privacy update error:', err);
      setPrivacy(prevPrivacy);
    } finally {
      setSavingPrivacy(false);
    }
  };

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.background }]}
      contentContainerStyle={styles.content}
    >
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

      {/* Privacy Section */}
      <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.sectionHeader}>
          <Ionicons name="shield-checkmark-outline" size={18} color={colors.accent} />
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Privacy</Text>
          {savingPrivacy && <ActivityIndicator size="small" color={colors.accent} style={{ marginLeft: 8 }} />}
        </View>

        {loadingPrivacy ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="small" color={colors.accent} />
            <Text style={[styles.loadingText, { color: colors.muted }]}>Loading settings...</Text>
          </View>
        ) : (
          <>
            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>Show collection value</Text>
                <Text style={[styles.settingHint, { color: colors.muted }]}>Display your total collection value on your profile</Text>
              </View>
              <Switch
                value={privacy.showCollectionValue}
                onValueChange={(v) => updatePrivacy('showCollectionValue', v)}
                trackColor={{ false: colors.border, true: colors.accent }}
                thumbColor="#FFFFFF"
              />
            </View>

            <View style={[styles.divider, { backgroundColor: colors.border }]} />

            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>Show item count</Text>
                <Text style={[styles.settingHint, { color: colors.muted }]}>Display how many items you have collected</Text>
              </View>
              <Switch
                value={privacy.showItemCount}
                onValueChange={(v) => updatePrivacy('showItemCount', v)}
                trackColor={{ false: colors.border, true: colors.accent }}
                thumbColor="#FFFFFF"
              />
            </View>

            <View style={[styles.divider, { backgroundColor: colors.border }]} />

            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>Allow discovery</Text>
                <Text style={[styles.settingHint, { color: colors.muted }]}>Let other collectors find you by interests</Text>
              </View>
              <Switch
                value={privacy.allowDiscovery}
                onValueChange={(v) => updatePrivacy('allowDiscovery', v)}
                trackColor={{ false: colors.border, true: colors.accent }}
                thumbColor="#FFFFFF"
              />
            </View>

            <View style={[styles.divider, { backgroundColor: colors.border }]} />

            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>Show online status</Text>
                <Text style={[styles.settingHint, { color: colors.muted }]}>Let others see when you're active</Text>
              </View>
              <Switch
                value={privacy.showOnlineStatus}
                onValueChange={(v) => updatePrivacy('showOnlineStatus', v)}
                trackColor={{ false: colors.border, true: colors.accent }}
                thumbColor="#FFFFFF"
              />
            </View>
          </>
        )}
      </View>

      {/* Preferences Section */}
      <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.sectionHeader}>
          <Ionicons name="settings-outline" size={18} color={colors.accent} />
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Preferences</Text>
        </View>

        <View style={styles.settingRow}>
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Haptic feedback</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Vibration feedback for interactions</Text>
          </View>
          <Switch
            value={settings.hapticsEnabled}
            onValueChange={(v) => updateSettings({ hapticsEnabled: v })}
            trackColor={{ false: colors.border, true: colors.accent }}
            thumbColor="#FFFFFF"
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
            onValueChange={(v) => updateSettings({ animationsEnabled: v })}
            trackColor={{ false: colors.border, true: colors.accent }}
            thumbColor="#FFFFFF"
          />
        </View>
      </View>

      {/* Account Section */}
      <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.sectionHeader}>
          <Ionicons name="person-outline" size={18} color={colors.accent} />
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Account</Text>
        </View>
        <ActionTile
          title="Log Out"
          subtitle="Sign out of your account"
          icon="log-out-outline"
          onPress={signOut}
        />
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
    borderRadius: 16,
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
    fontSize: 16,
    fontWeight: '600',
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
    fontSize: 15,
    fontWeight: '500',
  },
  settingHint: {
    fontSize: 12,
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
    fontSize: 13,
  },
});
