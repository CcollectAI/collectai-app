import React, { useState, useEffect, useCallback } from 'react';
import { View, ScrollView, Alert, Text, TextInput, StyleSheet, Switch, ActivityIndicator, Linking, Modal, TouchableOpacity } from 'react-native';
import { useToast } from '@/components/Toast';
import Constants from 'expo-constants';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { supabase } from "@/lib/supabase";
import { AccessibilitySettings } from '@/components/AccessibilitySettings';
import { AlertSettings } from '@/components/AlertSettings';
import { MutationQueuePanel } from '@/components/MutationQueuePanel';
import { featureFlags } from '@/config/featureFlags';
import { DEFAULT_ALERT_PREFERENCES, AlertPreferences } from '@/types/insights';
import { useSettings, REGION_DEFAULTS } from '@/lib/settings';
import type { Region, Currency } from '@/lib/settings';
import { useAuthContext } from '@/providers/useAuthContext';
import { AnimatedPressable } from '@/motion';
import { Ionicons } from '@expo/vector-icons';
import { logger } from '@/lib/logger';
import { fireHaptic, HapticIntent } from '@/haptics';
import { deleteAccount, collectorsApi } from '@/api/collectorsApi';
import { API_BASE } from '@/api/config';
import { useFeatureTour } from '@/lib/featureTour';
import {
  getQueuedMutations,
  getQueueLength,
  removeMutation,
  clearQueue,
  replayQueue,
  type MutationType,
  type QueuedMutation,
} from '@/lib/mutationQueue';
import { offlineSafeMutation } from '@/data/OfflineDataProvider';

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
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings, updateSettings } = useSettings();
  const { user, profile, signOut } = useAuthContext();
  const { showToast } = useToast();
  const { resetAll: resetFeatureTips } = useFeatureTour();
  const [alertPrefs, setAlertPrefs] = useState<AlertPreferences>(DEFAULT_ALERT_PREFERENCES);
  const [privacy, setPrivacy] = useState<PrivacySettings>(DEFAULT_PRIVACY);
  const [loadingPrivacy, setLoadingPrivacy] = useState(true);
  const [savingPrivacy, setSavingPrivacy] = useState(false);
  const [regionPickerVisible, setRegionPickerVisible] = useState(false);
  const [currencyPickerVisible, setCurrencyPickerVisible] = useState(false);
  const [editProfileVisible, setEditProfileVisible] = useState(false);
  const [editUsername, setEditUsername] = useState(profile?.username ?? '');
  const [editBio, setEditBio] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);
  const [changePasswordVisible, setChangePasswordVisible] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  const REGION_OPTIONS: { value: Region; label: string }[] = [
    { value: 'americas', label: 'Americas' },
    { value: 'europe', label: 'Europe' },
    { value: 'japan', label: 'Japan' },
    { value: 'korea', label: 'South Korea' },
    { value: 'oceania', label: 'Australia / Oceania' },
    { value: 'other', label: 'Other' },
  ];

  const CURRENCY_OPTIONS: Currency[] = ['EUR', 'USD', 'GBP', 'JPY', 'KRW', 'AUD', 'CAD'];

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

  const handleSaveProfile = async () => {
    setSavingProfile(true);
    try {
      const auth = await supabase.auth.getSession();
      if (auth.data?.session) {
        await fetch(`${API_BASE}/settings/profile`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${auth.data.session.access_token}`,
          },
          body: JSON.stringify({ username: editUsername.trim(), bio: editBio.trim() }),
        });
      }
      setEditProfileVisible(false);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    } catch (e) {
      logger.warn('[Settings] Failed to save profile:', e);
      showToast({ message: 'Failed to save profile changes', type: 'error' });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword.length < 8) {
      showToast({ message: 'New password must be at least 8 characters', type: 'error' });
      return;
    }
    if (newPassword !== confirmPassword) {
      showToast({ message: 'Passwords do not match', type: 'error' });
      return;
    }
    setSavingPassword(true);
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) throw error;
      setChangePasswordVisible(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Password updated successfully', type: 'success' });
    } catch (e) {
      showToast({ message: e instanceof Error ? e.message : 'Failed to change password', type: 'error' });
    } finally {
      setSavingPassword(false);
    }
  };

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
        logger.warn('[Settings] Failed to load privacy settings:', err);
      } finally {
        setLoadingPrivacy(false);
      }
    };

    loadPrivacySettings();
  }, []);

  const handleAlertPrefsUpdate = async (prefs: AlertPreferences) => {
    setAlertPrefs(prefs);
    try {
      const auth = await supabase.auth.getSession();
      if (auth.data?.session) {
        await fetch(`${API_BASE}/settings/alert-preferences`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${auth.data.session.access_token}`,
          },
          body: JSON.stringify(prefs),
        });
      }
    } catch (e) {
      logger.warn('[Settings] Failed to persist alert preferences:', e);
    }
  };

  const updatePrivacy = async (key: keyof PrivacySettings, value: boolean) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
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
        logger.warn('[Settings] Failed to save privacy setting:', error);
        // Revert on error
        setPrivacy(prevPrivacy);
        showToast({ message: 'Failed to save privacy setting', type: 'error' });
      }
    } catch (err) {
      logger.warn('[Settings] Privacy update error:', err);
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
                onValueChange={(v) => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); updatePrivacy('showCollectionValue', v); }}
                trackColor={{ false: colors.border, true: colors.accent }}
                thumbColor="#FFFFFF"
                accessibilityLabel="Show collection value"
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
                onValueChange={(v) => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); updatePrivacy('showItemCount', v); }}
                trackColor={{ false: colors.border, true: colors.accent }}
                thumbColor="#FFFFFF"
                accessibilityLabel="Show item count"
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
                onValueChange={(v) => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); updatePrivacy('allowDiscovery', v); }}
                trackColor={{ false: colors.border, true: colors.accent }}
                thumbColor="#FFFFFF"
                accessibilityLabel="Allow discovery"
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
                onValueChange={(v) => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); updatePrivacy('showOnlineStatus', v); }}
                trackColor={{ false: colors.border, true: colors.accent }}
                thumbColor="#FFFFFF"
                accessibilityLabel="Show online status"
              />
            </View>
          </>
        )}
      </View>

      {/* Region & Currency Section */}
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

      {/* Preferences Section */}
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
            thumbColor="#FFFFFF"
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
            thumbColor="#FFFFFF"
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
            thumbColor="#FFFFFF"
            accessibilityLabel="Animations"
          />
        </View>
      </View>

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

      {/* Account Section */}
      <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.sectionHeader}>
          <Ionicons name="person-outline" size={18} color={colors.accent} />
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Account</Text>
        </View>

        {user && (
          <View style={styles.settingRow}>
            <View style={styles.settingInfo}>
              <Text style={[styles.settingLabel, { color: colors.text }]}>
                {profile?.username ?? 'User'}
              </Text>
              <Text style={[styles.settingHint, { color: colors.muted }]}>
                {user.email ?? ''}
              </Text>
            </View>
          </View>
        )}

        {user && <View style={[styles.divider, { backgroundColor: colors.border }]} />}

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => {
            setEditUsername(profile?.username ?? '');
            setEditProfileVisible(true);
          }}
          accessibilityRole="button"
          accessibilityLabel="Edit profile"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Edit Profile</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Change your username and bio</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => setChangePasswordVisible(true)}
          accessibilityRole="button"
          accessibilityLabel="Change password"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Change Password</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Update your account password</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.signOutBtn}
          onPress={() => {
            fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
            Alert.alert(
              'Sign Out',
              'Are you sure you want to sign out?',
              [
                { text: 'Cancel', style: 'cancel' },
                {
                  text: 'Sign Out',
                  style: 'destructive',
                  onPress: signOut,
                },
              ],
            );
          }}
          accessibilityRole="button"
          accessibilityLabel="Sign out"
        >
          <Ionicons name="log-out-outline" size={18} color={colors.danger} />
          <Text style={[styles.signOutText, { color: colors.danger }]}>Sign Out</Text>
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/subscription')}
          accessibilityRole="link"
          accessibilityLabel="Manage subscription"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Subscription</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Manage your plan</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/mfa-setup')}
          accessibilityRole="link"
          accessibilityLabel="Two-factor authentication"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Two-Factor Auth</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Secure your account with 2FA</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/sell/offers')}
          accessibilityRole="link"
          accessibilityLabel="My Listings and Offers"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>My Listings & Offers</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Manage items for sale and P2P offers</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/settings/blocked-users')}
          accessibilityRole="link"
          accessibilityLabel="Blocked Users"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Blocked Users</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Manage users you've blocked</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            const url = collectorsApi.getInsuranceReportUrl('html', settings.currency);
            Linking.openURL(url);
          }}
          accessibilityRole="link"
          accessibilityLabel="Export insurance valuation report"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Export Insurance Report</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Generate a PDF-ready valuation report for insurance</Text>
          </View>
          <Ionicons name="document-text-outline" size={16} color={colors.accent} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.signOutBtn}
          onPress={() => {
            fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
            Alert.alert(
              'Delete Account',
              'This will permanently delete your account and all your data. This action cannot be undone.',
              [
                { text: 'Cancel', style: 'cancel' },
                {
                  text: 'Delete Account',
                  style: 'destructive',
                  onPress: async () => {
                    try {
                      await deleteAccount();
                      await signOut();
                      Alert.alert('Account Deleted', 'Your account has been permanently deleted.');
                    } catch (e) {
                      Alert.alert(
                        'Error',
                        e instanceof Error ? e.message : 'Failed to delete account. Please try again.',
                      );
                    }
                  },
                },
              ],
            );
          }}
          accessibilityRole="button"
          accessibilityLabel="Delete account"
        >
          <Ionicons name="trash-outline" size={18} color={colors.danger} />
          <Text style={[styles.signOutText, { color: colors.danger }]}>Delete Account</Text>
        </AnimatedPressable>
      </View>

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
            resetFeatureTips();
            showToast({ message: 'Feature tips reset. They will appear again as you navigate.', type: 'success' });
          }}
          accessibilityRole="button"
          accessibilityLabel="Reset feature tips"
        >
          <Text style={[styles.settingLabel, { color: colors.text }]}>Reset Feature Tips</Text>
          <Ionicons name="refresh-outline" size={18} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => Linking.openURL('mailto:support@collectai.app')}
          accessibilityRole="link"
          accessibilityLabel="Report a bug"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Report a Bug</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>support@collectai.app</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/legal/privacy-policy')}
          accessibilityRole="link"
          accessibilityLabel="Privacy Policy"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Privacy Policy</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/legal/terms')}
          accessibilityRole="link"
          accessibilityLabel="Terms of Service"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Terms of Service</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/legal/user-policy')}
          accessibilityRole="link"
          accessibilityLabel="User Policy"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>User Policy</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/condition-guide')}
          accessibilityRole="link"
          accessibilityLabel="Condition Guide"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Condition Guide</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Grading reference for all categories</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>
      </View>

      {/* Edit Profile Modal */}
      <Modal
        visible={editProfileVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setEditProfileVisible(false)}
      >
        <View style={[styles.pickerModal, { backgroundColor: colors.background }]}>
          <View style={[styles.pickerHeader, { borderBottomColor: colors.border }]}>
            <TouchableOpacity onPress={() => setEditProfileVisible(false)} accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={[styles.pickerTitle, { color: colors.text }]}>Edit Profile</Text>
            <TouchableOpacity onPress={handleSaveProfile} disabled={savingProfile} accessibilityLabel="Save">
              {savingProfile ? (
                <ActivityIndicator size="small" color={colors.accent} />
              ) : (
                <Text style={[{ fontSize: 16, fontWeight: '600', color: colors.accent }]}>Save</Text>
              )}
            </TouchableOpacity>
          </View>
          <View style={{ padding: 16, gap: 16 }}>
            <View>
              <Text style={[styles.settingLabel, { color: colors.text, marginBottom: 6 }]}>Username</Text>
              <TextInput
                style={[styles.profileInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
                value={editUsername}
                onChangeText={setEditUsername}
                placeholder="Username"
                placeholderTextColor={colors.muted}
                autoCapitalize="none"
                autoFocus
              />
            </View>
            <View>
              <Text style={[styles.settingLabel, { color: colors.text, marginBottom: 6 }]}>Bio</Text>
              <TextInput
                style={[styles.profileInput, styles.profileBioInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
                value={editBio}
                onChangeText={setEditBio}
                placeholder="Tell other collectors about yourself"
                placeholderTextColor={colors.muted}
                multiline
                maxLength={200}
              />
            </View>
          </View>
        </View>
      </Modal>

      {/* Change Password Modal */}
      <Modal
        visible={changePasswordVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setChangePasswordVisible(false)}
      >
        <View style={[styles.pickerModal, { backgroundColor: colors.background }]}>
          <View style={[styles.pickerHeader, { borderBottomColor: colors.border }]}>
            <TouchableOpacity onPress={() => setChangePasswordVisible(false)} accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={[styles.pickerTitle, { color: colors.text }]}>Change Password</Text>
            <TouchableOpacity onPress={handleChangePassword} disabled={savingPassword} accessibilityLabel="Save">
              {savingPassword ? (
                <ActivityIndicator size="small" color={colors.accent} />
              ) : (
                <Text style={[{ fontSize: 16, fontWeight: '600', color: colors.accent }]}>Save</Text>
              )}
            </TouchableOpacity>
          </View>
          <View style={{ padding: 16, gap: 16 }}>
            <View>
              <Text style={[styles.settingLabel, { color: colors.text, marginBottom: 6 }]}>New Password</Text>
              <TextInput
                style={[styles.profileInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
                value={newPassword}
                onChangeText={setNewPassword}
                placeholder="At least 8 characters"
                placeholderTextColor={colors.muted}
                secureTextEntry
                autoFocus
              />
            </View>
            <View>
              <Text style={[styles.settingLabel, { color: colors.text, marginBottom: 6 }]}>Confirm New Password</Text>
              <TextInput
                style={[styles.profileInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                placeholder="Confirm new password"
                placeholderTextColor={colors.muted}
                secureTextEntry
              />
            </View>
          </View>
        </View>
      </Modal>

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
  signOutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 12,
  },
  signOutText: {
    fontSize: 15,
    fontWeight: '600',
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
    fontSize: 17,
    fontWeight: '700',
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
    fontSize: 16,
    fontWeight: '500',
  },
  profileInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
  },
  profileBioInput: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
});
