/**
 * SponsorProfileCard — Company profile display with view/edit modes.
 * Extracted from sponsor/dashboard.tsx for reusability and file-size reduction.
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  ActivityIndicator,
  Image,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import type { SponsorCompany } from '@/data/events';
import type { AppColors } from '@/ui/theme';

/* -------------------------------------------------------------------------- */
/*  Props                                                                      */
/* -------------------------------------------------------------------------- */

export type SponsorProfileCardProps = {
  /** The company data to display. */
  company: SponsorCompany;
  /** Theme colors from useAppTheme. */
  colors: AppColors;
  /** Member-since formatted string, e.g. "January 2026". */
  memberSince: string | null;

  /* ---- View mode ---- */
  editing: boolean;

  /* ---- Edit mode fields ---- */
  editName: string;
  onEditNameChange: (v: string) => void;
  editContactEmail: string;
  onEditContactEmailChange: (v: string) => void;
  editLogoUrl: string;
  editWebsiteUrl: string;
  onEditWebsiteUrlChange: (v: string) => void;
  editDescription: string;
  onEditDescriptionChange: (v: string) => void;

  /* ---- Logo upload ---- */
  editLogoPreview: string | null;
  logoUploading: boolean;
  onPickEditLogo: () => void;

  /* ---- Actions ---- */
  saving: boolean;
  onCancelEdit: () => void;
  onSaveEdit: () => void;
};

/* -------------------------------------------------------------------------- */
/*  Shadows                                                                    */
/* -------------------------------------------------------------------------- */

const SHADOW_SM = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 3 },
  android: { elevation: 1 },
  default: {},
}) as Record<string, unknown>;

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

export const SponsorProfileCard: React.FC<SponsorProfileCardProps> = ({
  company,
  colors,
  memberSince,
  editing,
  editName,
  onEditNameChange,
  editContactEmail,
  onEditContactEmailChange,
  editLogoUrl,
  editWebsiteUrl,
  onEditWebsiteUrlChange,
  editDescription,
  onEditDescriptionChange,
  editLogoPreview,
  logoUploading,
  onPickEditLogo,
  saving,
  onCancelEdit,
  onSaveEdit,
}) => {
  return (
    <View style={styles.sectionWrap}>
      <Text style={[styles.sectionLabel, { color: colors.muted }]}>COMPANY PROFILE</Text>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_SM]}>
        {/* View mode */}
        {!editing && (
          <>
            <View style={styles.profileRow}>
              {!!company.logoUrl ? (
                <Image
                  source={{ uri: company.logoUrl }}
                  style={styles.profileLogo}
                  accessibilityLabel={`${company.name} logo`}
                />
              ) : (
                <View style={[styles.profileLogoPlaceholder, { backgroundColor: colors.accent + '10' }]}>
                  <Ionicons name="business" size={28} color={colors.accent} />
                </View>
              )}
              <View style={styles.profileInfo}>
                <View style={styles.profileNameRow}>
                  <Text style={[styles.profileName, { color: colors.text }]} numberOfLines={1}>
                    {company.name}
                  </Text>
                  {!!company.isVerified && (
                    <View style={[styles.verifiedPill, { backgroundColor: '#10B981' + '18' }]}>
                      <Ionicons name="checkmark-circle" size={11} color="#10B981" />
                      <Text style={[styles.verifiedPillText, { color: '#10B981' }]}>Verified</Text>
                    </View>
                  )}
                </View>
                <View style={styles.profileMeta}>
                  <Ionicons name="mail-outline" size={11} color={colors.muted} />
                  <Text style={[styles.profileMetaText, { color: colors.muted }]} numberOfLines={1}>
                    {company.contactEmail}
                  </Text>
                </View>
                {!!company.websiteUrl && (
                  <View style={styles.profileMeta}>
                    <Ionicons name="globe-outline" size={11} color={colors.muted} />
                    <Text style={[styles.profileMetaText, { color: colors.muted }]} numberOfLines={1}>
                      {company.websiteUrl}
                    </Text>
                  </View>
                )}
                {!!memberSince && (
                  <Text style={[styles.profileSince, { color: colors.muted }]}>
                    Member since {memberSince}
                  </Text>
                )}
              </View>
            </View>

            {!!company.description && (
              <View style={[styles.profileDescWrap, { borderTopColor: colors.border }]}>
                <Text style={[styles.profileDesc, { color: colors.text }]} numberOfLines={3}>
                  {company.description}
                </Text>
              </View>
            )}
          </>
        )}

        {/* Edit mode */}
        {!!editing && (
          <View>
            <View style={styles.editFieldGroup}>
              <Text style={[styles.editFieldLabel, { color: colors.muted }]}>
                Company Name <Text style={{ color: colors.accent }}>*</Text>
              </Text>
              <View style={[styles.editInputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                <TextInput
                  value={editName}
                  onChangeText={onEditNameChange}
                  style={[styles.editInput, { color: colors.text }]}
                  accessibilityLabel="Company name"
                  returnKeyType="next"
                />
              </View>
            </View>

            <View style={styles.editFieldGroup}>
              <Text style={[styles.editFieldLabel, { color: colors.muted }]}>
                Contact Email <Text style={{ color: colors.accent }}>*</Text>
              </Text>
              <View style={[styles.editInputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                <TextInput
                  value={editContactEmail}
                  onChangeText={onEditContactEmailChange}
                  style={[styles.editInput, { color: colors.text }]}
                  autoCapitalize="none"
                  keyboardType="email-address"
                  accessibilityLabel="Contact email"
                  returnKeyType="next"
                />
              </View>
            </View>

            <View style={styles.editFieldGroup}>
              <Text style={[styles.editFieldLabel, { color: colors.muted }]}>Company Logo</Text>
              <AnimatedPressable
                onPress={onPickEditLogo}
                disabled={logoUploading}
                style={[styles.logoPicker, { borderColor: colors.border, backgroundColor: colors.background }]}
                accessibilityRole="button"
                accessibilityLabel="Change company logo"
              >
                {!!logoUploading ? (
                  <ActivityIndicator size="small" color={colors.accent} />
                ) : !!editLogoPreview ? (
                  <View style={styles.logoPreviewWrap}>
                    <Image source={{ uri: editLogoPreview }} style={styles.logoPreviewImg} />
                    <Text style={[styles.logoChangeHint, { color: colors.accent }]}>Tap to change</Text>
                  </View>
                ) : (
                  <View style={styles.logoPickerInner}>
                    <View style={[styles.logoPickerCircle, { backgroundColor: colors.accent + '10' }]}>
                      <Ionicons name="camera-outline" size={20} color={colors.accent} />
                    </View>
                    <Text style={[styles.logoPickerHint, { color: colors.muted }]}>Upload logo</Text>
                  </View>
                )}
              </AnimatedPressable>
            </View>

            <View style={styles.editFieldGroup}>
              <Text style={[styles.editFieldLabel, { color: colors.muted }]}>Website</Text>
              <View style={[styles.editInputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                <TextInput
                  value={editWebsiteUrl}
                  onChangeText={onEditWebsiteUrlChange}
                  style={[styles.editInput, { color: colors.text }]}
                  autoCapitalize="none"
                  keyboardType="url"
                  placeholder="https://yourcompany.com"
                  placeholderTextColor={colors.muted}
                  accessibilityLabel="Website URL"
                  returnKeyType="next"
                />
              </View>
            </View>

            <View>
              <Text style={[styles.editFieldLabel, { color: colors.muted }]}>Description</Text>
              <View style={[styles.editTextAreaWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                <TextInput
                  value={editDescription}
                  onChangeText={onEditDescriptionChange}
                  multiline
                  numberOfLines={4}
                  style={[styles.editTextArea, { color: colors.text }]}
                  textAlignVertical="top"
                  placeholder="Tell collectors about your brand..."
                  placeholderTextColor={colors.muted}
                  accessibilityLabel="Company description"
                />
              </View>
            </View>

            <View style={[styles.editActions, { borderTopColor: colors.border }]}>
              <AnimatedPressable
                onPress={onCancelEdit}
                style={[styles.outlineBtn, { borderColor: colors.border, flex: 1 }]}
                accessibilityRole="button"
                accessibilityLabel="Cancel editing"
              >
                <Text style={[styles.outlineBtnText, { color: colors.muted }]}>Cancel</Text>
              </AnimatedPressable>
              <AnimatedPressable
                onPress={onSaveEdit}
                disabled={saving}
                style={[styles.primaryBtn, { backgroundColor: colors.accent, flex: 1 }]}
                accessibilityRole="button"
                accessibilityLabel="Save changes"
              >
                {!!saving ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.primaryBtnText}>Save Changes</Text>
                )}
              </AnimatedPressable>
            </View>
          </View>
        )}
      </View>
    </View>
  );
};

/* -------------------------------------------------------------------------- */
/*  Styles                                                                     */
/* -------------------------------------------------------------------------- */

const styles = StyleSheet.create({
  sectionWrap: {
    marginBottom: 24,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    marginBottom: 10,
  },
  card: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
  },

  /* Profile view mode */
  profileRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  profileLogo: {
    width: 64,
    height: 64,
    borderRadius: 14,
    marginRight: 14,
  },
  profileLogoPlaceholder: {
    width: 64,
    height: 64,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  profileInfo: {
    flex: 1,
  },
  profileNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flexWrap: 'wrap',
    marginBottom: 4,
  },
  profileName: {
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: -0.3,
  },
  verifiedPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 10,
  },
  verifiedPillText: {
    fontSize: 10,
    fontWeight: '600',
  },
  profileMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 2,
  },
  profileMetaText: {
    fontSize: 12,
    flex: 1,
  },
  profileSince: {
    fontSize: 10,
    marginTop: 4,
  },
  profileDescWrap: {
    borderTopWidth: StyleSheet.hairlineWidth,
    marginTop: 14,
    paddingTop: 12,
  },
  profileDesc: {
    fontSize: 13,
    lineHeight: 19,
  },

  /* Edit mode */
  editFieldGroup: {
    marginBottom: 14,
  },
  editFieldLabel: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  editInputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 44,
  },
  editInput: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 0,
  },
  editTextAreaWrap: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    minHeight: 88,
  },
  editTextArea: {
    flex: 1,
    fontSize: 14,
    minHeight: 64,
  },
  editActions: {
    flexDirection: 'row',
    gap: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    marginTop: 16,
    paddingTop: 16,
  },
  logoPicker: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderRadius: 12,
    height: 88,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  logoPreviewWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  logoPreviewImg: {
    width: 48,
    height: 48,
    borderRadius: 10,
  },
  logoChangeHint: {
    fontSize: 11,
    fontWeight: '500',
  },
  logoPickerInner: {
    alignItems: 'center',
    gap: 6,
  },
  logoPickerCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoPickerHint: {
    fontSize: 12,
  },

  /* Shared buttons */
  primaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 11,
    paddingHorizontal: 18,
    borderRadius: 10,
  },
  primaryBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  outlineBtn: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 11,
    paddingHorizontal: 18,
    borderRadius: 10,
    borderWidth: 1,
  },
  outlineBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
});

export default SponsorProfileCard;
