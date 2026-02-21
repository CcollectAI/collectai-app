/**
 * Sponsor Dashboard Screen
 * Route: /sponsor/dashboard
 *
 * Displays the sponsor's company profile, allows inline editing,
 * and provides a CTA to create sponsored events.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  TextInput,
  ActivityIndicator,
  Image,
  Alert,
  Animated,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { dataProvider } from '@/data';
import type { SponsorCompany } from '@/data/events';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import logger from '@/utils/logger';

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

const SponsorDashboardScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();

  /* ---- state ---- */
  const [loading, setLoading] = useState(true);
  const [company, setCompany] = useState<SponsorCompany | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  /* ---- editable fields ---- */
  const [editName, setEditName] = useState('');
  const [editLogoUrl, setEditLogoUrl] = useState('');
  const [editWebsiteUrl, setEditWebsiteUrl] = useState('');
  const [editContactEmail, setEditContactEmail] = useState('');
  const [editDescription, setEditDescription] = useState('');

  /* ---- load company ---- */
  const loadCompany = useCallback(async () => {
    setLoading(true);
    try {
      const companies = await dataProvider.getMySponsorCompanies();
      if (companies.length > 0) {
        const c = companies[0];
        setCompany(c);
        setEditName(c.name);
        setEditLogoUrl(c.logoUrl ?? '');
        setEditWebsiteUrl(c.websiteUrl ?? '');
        setEditContactEmail(c.contactEmail);
        setEditDescription(c.description ?? '');
      } else {
        setCompany(null);
      }
    } catch (err: unknown) {
      logger.warn('[SponsorDashboard] loadCompany error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCompany();
  }, [loadCompany]);

  /* ---- enter edit mode ---- */
  const handleStartEdit = () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setEditing(true);
  };

  /* ---- cancel edit ---- */
  const handleCancelEdit = () => {
    if (company) {
      setEditName(company.name);
      setEditLogoUrl(company.logoUrl ?? '');
      setEditWebsiteUrl(company.websiteUrl ?? '');
      setEditContactEmail(company.contactEmail);
      setEditDescription(company.description ?? '');
    }
    setEditing(false);
  };

  /* ---- save edits ---- */
  const handleSaveEdit = async () => {
    if (!company) return;
    if (!editName.trim() || !editContactEmail.trim()) {
      Alert.alert('Validation Error', 'Company name and contact email are required.');
      return;
    }

    setSaving(true);
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

    try {
      const updated = await dataProvider.updateSponsorCompany(company.id, {
        name: editName.trim(),
        contactEmail: editContactEmail.trim(),
        ...(editLogoUrl.trim() ? { logoUrl: editLogoUrl.trim() } : {}),
        ...(editWebsiteUrl.trim() ? { websiteUrl: editWebsiteUrl.trim() } : {}),
        ...(editDescription.trim() ? { description: editDescription.trim() } : {}),
      });
      setCompany(updated);
      setEditing(false);
    } catch (err: unknown) {
      logger.warn('[SponsorDashboard] save error:', err);
      Alert.alert('Error', (err as Error)?.message || 'Failed to update company. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  /* ---- create sponsored event ---- */
  const handleCreateEvent = () => {
    if (!company) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push(`/create-event?sponsorCompanyId=${company.id}`);
  };

  /* ======================================================================== */
  /*  Loading state                                                            */
  /* ======================================================================== */

  if (loading) {
    return (
      <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  /* ======================================================================== */
  /*  No company — registration CTA                                            */
  /* ======================================================================== */

  if (!company) {
    return (
      <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
        {/* Header */}
        <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
          <AnimatedPressable
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.back(); }}
            style={styles.backBtn}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Sponsor Dashboard</Text>
          <View style={{ width: 32 }} />
        </View>

        <View style={styles.emptyContainer}>
          <Ionicons name="megaphone-outline" size={56} color={colors.muted} />
          <Text style={[styles.emptyTitle, { color: colors.text }]}>No Sponsor Company</Text>
          <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
            Register your company to start creating sponsored events and reaching collectors.
          </Text>
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.push('/sponsor/register');
            }}
            style={[styles.ctaButton, { backgroundColor: colors.accent }]}
            accessibilityRole="button"
            accessibilityLabel="Register your company"
          >
            <Ionicons name="add-circle-outline" size={20} color="#FFFFFF" />
            <Text style={styles.ctaButtonText}>Register Your Company</Text>
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    );
  }

  /* ======================================================================== */
  /*  Dashboard with company                                                   */
  /* ======================================================================== */

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <AnimatedPressable
          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.back(); }}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel="Go back"
        >
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Sponsor Dashboard</Text>
        <View style={{ width: 32 }} />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
          {/* ============================================================ */}
          {/*  Company Profile Card                                        */}
          {/* ============================================================ */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="business-outline" size={16} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Company Profile</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              {/* Logo + Name + Verified Badge */}
              {!editing && (
                <View style={styles.profileRow}>
                  {company.logoUrl ? (
                    <Image
                      source={{ uri: company.logoUrl }}
                      style={styles.logo}
                      accessibilityLabel={`${company.name} logo`}
                    />
                  ) : (
                    <View style={[styles.logoPlaceholder, { backgroundColor: colors.accent + '20' }]}>
                      <Ionicons name="business" size={28} color={colors.accent} />
                    </View>
                  )}
                  <View style={styles.profileInfo}>
                    <View style={styles.nameRow}>
                      <Text style={[styles.companyName, { color: colors.text }]} numberOfLines={1}>
                        {company.name}
                      </Text>
                      {company.isVerified && (
                        <View style={[styles.verifiedBadge, { backgroundColor: colors.accent + '20' }]}>
                          <Ionicons name="checkmark-circle" size={14} color={colors.accent} />
                          <Text style={[styles.verifiedText, { color: colors.accent }]}>Verified</Text>
                        </View>
                      )}
                    </View>
                    <Text style={[styles.companyEmail, { color: colors.muted }]} numberOfLines={1}>
                      {company.contactEmail}
                    </Text>
                    {company.websiteUrl && (
                      <Text style={[styles.companyWebsite, { color: colors.muted }]} numberOfLines={1}>
                        {company.websiteUrl}
                      </Text>
                    )}
                  </View>
                </View>
              )}

              {/* Description (view mode) */}
              {!editing && company.description && (
                <View style={[styles.descriptionBlock, { borderTopColor: colors.border }]}>
                  <Text style={[styles.descriptionText, { color: colors.text }]}>
                    {company.description}
                  </Text>
                </View>
              )}

              {/* Inline editing form */}
              {editing && (
                <View>
                  <View style={styles.fieldBlock}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>
                      Company Name <Text style={{ color: colors.accent }}>*</Text>
                    </Text>
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      <TextInput
                        value={editName}
                        onChangeText={setEditName}
                        style={[styles.input, { color: colors.text }]}
                        accessibilityLabel="Company name"
                      />
                    </View>
                  </View>

                  <View style={styles.fieldBlock}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>
                      Contact Email <Text style={{ color: colors.accent }}>*</Text>
                    </Text>
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      <TextInput
                        value={editContactEmail}
                        onChangeText={setEditContactEmail}
                        style={[styles.input, { color: colors.text }]}
                        autoCapitalize="none"
                        keyboardType="email-address"
                        accessibilityLabel="Contact email"
                      />
                    </View>
                  </View>

                  <View style={styles.fieldBlock}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Logo URL</Text>
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      <TextInput
                        value={editLogoUrl}
                        onChangeText={setEditLogoUrl}
                        style={[styles.input, { color: colors.text }]}
                        autoCapitalize="none"
                        keyboardType="url"
                        accessibilityLabel="Logo URL"
                      />
                    </View>
                  </View>

                  <View style={styles.fieldBlock}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Website</Text>
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      <TextInput
                        value={editWebsiteUrl}
                        onChangeText={setEditWebsiteUrl}
                        style={[styles.input, { color: colors.text }]}
                        autoCapitalize="none"
                        keyboardType="url"
                        accessibilityLabel="Website URL"
                      />
                    </View>
                  </View>

                  <View>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Description</Text>
                    <View style={[styles.inputWrapMultiline, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      <TextInput
                        value={editDescription}
                        onChangeText={setEditDescription}
                        multiline
                        numberOfLines={4}
                        style={[styles.inputMultiline, { color: colors.text }]}
                        textAlignVertical="top"
                        accessibilityLabel="Company description"
                      />
                    </View>
                  </View>
                </View>
              )}

              {/* Edit / Save / Cancel buttons */}
              <View style={[styles.editActionsRow, { borderTopColor: colors.border }]}>
                {!editing ? (
                  <AnimatedPressable
                    onPress={handleStartEdit}
                    style={[styles.editBtn, { borderColor: colors.border }]}
                    accessibilityRole="button"
                    accessibilityLabel="Edit company"
                  >
                    <Ionicons name="create-outline" size={16} color={colors.accent} />
                    <Text style={[styles.editBtnText, { color: colors.accent }]}>Edit Company</Text>
                  </AnimatedPressable>
                ) : (
                  <View style={styles.editButtonsGroup}>
                    <AnimatedPressable
                      onPress={handleCancelEdit}
                      style={[styles.editBtn, { borderColor: colors.border }]}
                      accessibilityRole="button"
                      accessibilityLabel="Cancel editing"
                    >
                      <Ionicons name="close-outline" size={16} color={colors.muted} />
                      <Text style={[styles.editBtnText, { color: colors.muted }]}>Cancel</Text>
                    </AnimatedPressable>
                    <AnimatedPressable
                      onPress={handleSaveEdit}
                      disabled={saving}
                      style={[styles.saveBtn, { backgroundColor: colors.accent }]}
                      accessibilityRole="button"
                      accessibilityLabel="Save changes"
                    >
                      {saving ? (
                        <ActivityIndicator size="small" color="#FFFFFF" />
                      ) : (
                        <>
                          <Ionicons name="checkmark-outline" size={16} color="#FFFFFF" />
                          <Text style={styles.saveBtnText}>Save</Text>
                        </>
                      )}
                    </AnimatedPressable>
                  </View>
                )}
              </View>
            </View>
          </View>

          {/* ============================================================ */}
          {/*  Create Sponsored Event CTA                                   */}
          {/* ============================================================ */}
          <View style={styles.section}>
            <AnimatedPressable
              onPress={handleCreateEvent}
              style={[styles.ctaButton, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Create sponsored event"
            >
              <Ionicons name="megaphone-outline" size={20} color="#FFFFFF" />
              <Text style={styles.ctaButtonText}>Create Sponsored Event</Text>
            </AnimatedPressable>
          </View>

          {/* ============================================================ */}
          {/*  Sponsored Events List (placeholder)                          */}
          {/* ============================================================ */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="calendar-outline" size={16} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Sponsored Events</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.eventsPlaceholder}>
                <Ionicons name="calendar-outline" size={36} color={colors.muted} />
                <Text style={[styles.eventsPlaceholderTitle, { color: colors.text }]}>
                  No sponsored events yet
                </Text>
                <Text style={[styles.eventsPlaceholderSubtitle, { color: colors.muted }]}>
                  Create your first sponsored event to promote your brand to collectors.
                </Text>
              </View>
            </View>
          </View>

          <View style={{ height: 32 }} />
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
};

/* -------------------------------------------------------------------------- */
/*  Styles                                                                     */
/* -------------------------------------------------------------------------- */

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  section: {
    marginBottom: 20,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  card: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
  },

  /* Profile card */
  profileRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  logo: {
    width: 56,
    height: 56,
    borderRadius: 12,
    marginRight: 14,
  },
  logoPlaceholder: {
    width: 56,
    height: 56,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  profileInfo: {
    flex: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  companyName: {
    fontSize: 18,
    fontWeight: '700',
  },
  verifiedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
  },
  verifiedText: {
    fontSize: 11,
    fontWeight: '600',
  },
  companyEmail: {
    fontSize: 13,
    marginTop: 2,
  },
  companyWebsite: {
    fontSize: 12,
    marginTop: 1,
  },
  descriptionBlock: {
    borderTopWidth: StyleSheet.hairlineWidth,
    marginTop: 12,
    paddingTop: 12,
  },
  descriptionText: {
    fontSize: 14,
    lineHeight: 20,
  },

  /* Edit actions */
  editActionsRow: {
    borderTopWidth: StyleSheet.hairlineWidth,
    marginTop: 14,
    paddingTop: 14,
  },
  editButtonsGroup: {
    flexDirection: 'row',
    gap: 10,
  },
  editBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
  },
  editBtnText: {
    fontSize: 14,
    fontWeight: '500',
  },
  saveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
  },
  saveBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
  },

  /* Inline form fields */
  fieldBlock: {
    marginBottom: 14,
  },
  fieldLabel: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 6,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 44,
  },
  inputWrapMultiline: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    minHeight: 100,
  },
  input: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 0,
  },
  inputMultiline: {
    flex: 1,
    fontSize: 14,
    minHeight: 76,
  },

  /* CTA Button */
  ctaButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
  },
  ctaButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },

  /* Empty state */
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },

  /* Events placeholder */
  eventsPlaceholder: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  eventsPlaceholderTitle: {
    fontSize: 15,
    fontWeight: '600',
    marginTop: 12,
  },
  eventsPlaceholderSubtitle: {
    fontSize: 13,
    textAlign: 'center',
    marginTop: 6,
    lineHeight: 18,
    paddingHorizontal: 16,
  },
});

export default SponsorDashboardScreen;
