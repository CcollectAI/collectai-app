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
  Platform,
} from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
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
import { useTranslation } from 'react-i18next';

function ProfileEditSectionInner() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { user, profile, signOut } = useAuthContext();
  const { showToast } = useToast();
  const router = useRouter();
  const { t } = useTranslation();

  const [editProfileVisible, setEditProfileVisible] = useState(false);
  const [editUsername, setEditUsername] = useState(profile?.username ?? '');
  const [editBio, setEditBio] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);

  const [changePasswordVisible, setChangePasswordVisible] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  const [exportingFullInventory, setExportingFullInventory] = useState(false);

  const handleDownloadFullInventory = async () => {
    if (exportingFullInventory) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setExportingFullInventory(true);
    try {
      const { csv_inline } = await collectorsApi.exportItemsFull(settings.currency);
      const lineCount = csv_inline.trim().split('\n').length;
      const itemCount = Math.max(0, lineCount - 1);
      if (itemCount === 0) {
        showToast({ message: 'No items to export', type: 'info' });
        return;
      }
      if (!FileSystem.documentDirectory) {
        showToast({ message: 'File storage not available on this platform', type: 'error' });
        return;
      }
      const dateStr = new Date().toISOString().split('T')[0];
      const filename = `Sparrow_Collect_Full_Inventory_${dateStr}_${itemCount}items.csv`;
      const filePath = `${FileSystem.documentDirectory}${filename}`;
      await FileSystem.writeAsStringAsync(filePath, csv_inline);

      if (Platform.OS !== 'web' && (await Sharing.isAvailableAsync())) {
        await Sharing.shareAsync(filePath, {
          mimeType: 'text/csv',
          dialogTitle: 'Save Sparrow Collect inventory',
          UTI: 'public.comma-separated-values-text',
        });
        showToast({
          message: `Exported ${itemCount} ${itemCount === 1 ? 'item' : 'items'}`,
          type: 'success',
          duration: 3000,
        });
      } else {
        showToast({ message: `Saved ${filename}`, type: 'info', duration: 4000 });
      }
    } catch (e) {
      logger.error('[Settings] full inventory export failed:', e);
      showToast({ message: 'Failed to export inventory', type: 'error' });
    } finally {
      setExportingFullInventory(false);
    }
  };

  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deletingAccount, setDeletingAccount] = useState(false);

  const canConfirmDelete = deleteConfirmText.trim() === 'DELETE';

  const handleConfirmDelete = async () => {
    if (!canConfirmDelete || deletingAccount) return;
    setDeletingAccount(true);
    try {
      await deleteAccount();
      setDeleteModalVisible(false);
      setDeleteConfirmText('');
      await signOut();
      Alert.alert('Account Deleted', 'Your account has been permanently deleted.');
    } catch (e) {
      logger.error('[silent-catch] ProfileEditSection.tsx:115:', e);
      Alert.alert(
        'Error',
        e instanceof Error ? e.message : 'Failed to delete account. Please try again.',
      );
    } finally {
      setDeletingAccount(false);
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
      logger.error('[Settings] Failed to save profile:', e);
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
          accessibilityLabel={t('account.edit_profile_a11y')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('account.edit_profile')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('account.edit_profile_desc')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => setChangePasswordVisible(true)}
          accessibilityRole="button"
          accessibilityLabel={t('account.change_password_a11y')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('account.change_password')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('account.change_password_desc')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.signOutBtn}
          onPress={() => {
            fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
            Alert.alert(
              t('account.sign_out'),
              'Are you sure you want to sign out?',
              [
                { text: 'Cancel', style: 'cancel' },
                { text: t('account.sign_out'), style: 'destructive', onPress: signOut },
              ],
            );
          }}
          accessibilityRole="button"
          accessibilityLabel={t('account.sign_out_a11y')}
        >
          <Ionicons name="log-out-outline" size={18} color={colors.danger} />
          <Text style={[styles.signOutText, { color: colors.danger }]}>{t('account.sign_out')}</Text>
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/subscription')}
          accessibilityRole="link"
          accessibilityLabel={t('account.manage_subscription_a11y')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('account.manage_subscription')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('account.manage_subscription_desc')}</Text>
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
          accessibilityLabel={t('account.billing_portal_a11y')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('account.billing_portal')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('account.billing_portal_desc')}</Text>
          </View>
          <Ionicons name="open-outline" size={16} color={colors.muted} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={() => router.push('/mfa-setup')}
          accessibilityRole="link"
          accessibilityLabel={t('account.two_factor_a11y')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('account.two_factor')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('account.two_factor_desc')}</Text>
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
              accessibilityLabel={t('account.my_listings_a11y')}
            >
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>{t('account.my_listings')}</Text>
                <Text style={[styles.settingHint, { color: colors.muted }]}>{t('account.my_listings_desc')}</Text>
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
          accessibilityLabel={t('account.blocked_users_a11y')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('account.blocked_users')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('account.blocked_users_desc')}</Text>
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
          accessibilityLabel={t('account.export_insurance_a11y')}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>{t('account.export_insurance')}</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>{t('account.export_insurance_desc')}</Text>
          </View>
          <Ionicons name="document-text-outline" size={16} color={colors.accent} />
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.settingRow}
          onPress={handleDownloadFullInventory}
          accessibilityRole="button"
          accessibilityLabel="Download full inventory as CSV"
          accessibilityState={{ busy: exportingFullInventory }}
          disabled={exportingFullInventory}
        >
          <View style={styles.settingInfo}>
            <Text style={[styles.settingLabel, { color: colors.text }]}>Download full inventory (CSV)</Text>
            <Text style={[styles.settingHint, { color: colors.muted }]}>
              Comprehensive 30-column snapshot — every detail of every item, in your currency. For insurance, accountants, or full collection records.
            </Text>
          </View>
          {exportingFullInventory ? (
            <ActivityIndicator size="small" color={colors.accent} />
          ) : (
            <Ionicons name="download-outline" size={16} color={colors.accent} />
          )}
        </AnimatedPressable>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <AnimatedPressable
          style={styles.signOutBtn}
          onPress={() => {
            fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
            setDeleteConfirmText('');
            setDeleteModalVisible(true);
          }}
          accessibilityRole="button"
          accessibilityLabel={t('account.delete_account_a11y')}
        >
          <Ionicons name="trash-outline" size={18} color={colors.danger} />
          <Text style={[styles.signOutText, { color: colors.danger }]}>{t('account.delete_account')}</Text>
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
            <Text style={[styles.pickerTitle, { color: colors.text }]}>{t('account.edit_profile')}</Text>
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
                placeholder={t('account.bio_placeholder')}
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
            <Text style={[styles.pickerTitle, { color: colors.text }]}>{t('account.change_password')}</Text>
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
              <Text style={[styles.settingLabel, { color: colors.text, marginBottom: 6 }]}>{t('account.new_password')}</Text>
              <TextInput
                style={[styles.profileInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
                value={newPassword}
                onChangeText={setNewPassword}
                placeholder={t('account.new_password_placeholder')}
                placeholderTextColor={colors.muted}
                secureTextEntry
                autoFocus
                returnKeyType="next"
              />
            </View>
            <View>
              <Text style={[styles.settingLabel, { color: colors.text, marginBottom: 6 }]}>{t('account.confirm_new_password')}</Text>
              <TextInput
                style={[styles.profileInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                placeholder={t('account.confirm_new_password_placeholder')}
                placeholderTextColor={colors.muted}
                secureTextEntry
                returnKeyType="done"
              />
            </View>
          </View>
        </View>
      </Modal>

      {/* Delete Account — typed-confirmation modal. Backend requires a
          ?confirm=DELETE_MY_ACCOUNT query param; this modal is the UX
          gate that ensures a deliberate action. */}
      <Modal
        visible={deleteModalVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => {
          if (deletingAccount) return;
          setDeleteModalVisible(false);
          setDeleteConfirmText('');
        }}
      >
        <View style={[styles.pickerModal, { backgroundColor: colors.background }]}>
          <View style={[styles.pickerHeader, { borderBottomColor: colors.border }]}>
            <TouchableOpacity
              onPress={() => {
                if (deletingAccount) return;
                setDeleteModalVisible(false);
                setDeleteConfirmText('');
              }}
              accessibilityLabel="Close"
              disabled={deletingAccount}
            >
              <Ionicons name="close" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={[styles.pickerTitle, { color: colors.text }]}>{t('account.delete_account')}</Text>
            <TouchableOpacity
              onPress={handleConfirmDelete}
              disabled={!canConfirmDelete || deletingAccount}
              accessibilityLabel="Confirm delete account"
              accessibilityState={{ disabled: !canConfirmDelete || deletingAccount }}
            >
              {deletingAccount ? (
                <ActivityIndicator size="small" color={colors.danger} />
              ) : (
                <Text
                  style={[{
                    fontSize: textToken.lg,
                    fontWeight: fw.semibold,
                    color: canConfirmDelete ? colors.danger : colors.muted,
                  }]}
                >
                  Delete
                </Text>
              )}
            </TouchableOpacity>
          </View>
          <View style={{ padding: 16, gap: 16 }}>
            <Text style={[{ color: colors.text, fontSize: textToken.md, lineHeight: 22 }]}>
              This will permanently delete your account and all your data. This action cannot be undone.
            </Text>
            <Text style={[{ color: colors.muted, fontSize: textToken.sm }]}>
              Type <Text style={{ fontWeight: fw.semibold, color: colors.text }}>DELETE</Text> to confirm.
            </Text>
            <TextInput
              style={[styles.profileInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.card }]}
              value={deleteConfirmText}
              onChangeText={setDeleteConfirmText}
              placeholder="DELETE"
              placeholderTextColor={colors.muted}
              autoCapitalize="characters"
              autoCorrect={false}
              autoFocus
              editable={!deletingAccount}
              returnKeyType="done"
              onSubmitEditing={handleConfirmDelete}
              accessibilityLabel="Type DELETE to confirm"
            />
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
