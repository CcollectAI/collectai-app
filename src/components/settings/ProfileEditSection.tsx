/**
 * ProfileEditSection — Account info display + Edit Profile modal + Change Password modal.
 * Extracted from Settings.tsx.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Modal,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useAuthContext } from '@/providers/useAuthContext';
import { useToast } from '@/components/Toast';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { supabase } from '@/lib/supabase';
import { API_BASE } from '@/api/config';
import { deleteAccount, collectorsApi } from '@/api/collectorsApi';
import { logger } from '@/lib/logger';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import { BETA_MODE } from '@/config/featureFlags';

function ProfileEditSectionInner() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { user, profile, signOut } = useAuthContext();
  const { showToast } = useToast();
  const router = useRouter();

  const [editProfileVisible, setEditProfileVisible] = useState(false);
  const [editUsername, setEditUsername] = useState(profile?.username ?? '');
  const [editBio, setEditBio] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);

  const [changePasswordVisible, setChangePasswordVisible] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

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

  return (
    <>
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
                { text: 'Sign Out', style: 'destructive', onPress: signOut },
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
          onPress={async () => {
            try {
              const { createPortalSession } = await import('@/api/collectorsApi');
              const { url } = await createPortalSession();
              if (url) Linking.openURL(url);
            } catch {
              showToast({ message: 'Failed to open billing portal', type: 'error' });
            }
          }}
          accessibilityRole="link"
          accessibilityLabel="Open billing portal"
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Billing Portal</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>Payment methods, invoices, cancel</Text>
          </View>
          <Ionicons name="open-outline" size={16} color={colors.muted} />
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

        {!BETA_MODE && (
          <>
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
          </>
        )}

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
                <Text style={[{ fontSize: textToken.lg, fontWeight: fw.semibold, color: colors.accent }]}>Save</Text>
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
                returnKeyType="next"
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
                returnKeyType="done"
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
                <Text style={[{ fontSize: textToken.lg, fontWeight: fw.semibold, color: colors.accent }]}>Save</Text>
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
                returnKeyType="next"
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
                returnKeyType="done"
              />
            </View>
          </View>
        </View>
      </Modal>
    </>
  );
}

export const ProfileEditSection = React.memo(ProfileEditSectionInner);

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
  signOutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 12,
  },
  signOutText: {
    fontSize: textToken.lg,
    fontWeight: fw.semibold,
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
  profileInput: {
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: textToken.lg,
  },
  profileBioInput: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
});
