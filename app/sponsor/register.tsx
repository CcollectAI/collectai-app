/**
 * Sponsor Company Registration Screen
 * Route: /sponsor/register
 *
 * Premium registration flow with hero, benefits grid, tier preview,
 * image picker, keyboard chaining, and polished form.
 */

import React, { useState, useRef } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  TextInput,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Animated,
  Image,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, Stack } from 'expo-router';
import { dataProvider } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useFormField, validateAll } from '@/hooks/useFormField';
import { compose, required, maxLength, email, url } from '@/lib/validate';
import logger from '@/utils/logger';
import { useToast } from '@/components/Toast';
import { usePhotoUpload } from '@/hooks/usePhotoUpload';
import { QuickNavBar } from '@/components/QuickNavBar';
import { track } from '@/analytics/track';

/* -------------------------------------------------------------------------- */
/*  Static data                                                                */
/* -------------------------------------------------------------------------- */

const BENEFITS = [
  { icon: 'people-outline' as const, title: 'Reach Fans', desc: 'Connect with thousands of dedicated collectors' },
  { icon: 'megaphone-outline' as const, title: 'Announce Drops', desc: 'Notify fans about limited editions & releases' },
  { icon: 'eye-outline' as const, title: 'Brand Visibility', desc: 'Feature your brand across collector feeds' },
  { icon: 'analytics-outline' as const, title: 'Analytics', desc: 'Track engagement, attendance & conversions' },
];

const TIERS = [
  {
    name: 'Featured',
    features: ['Event listing', 'Category placement', 'Basic analytics'],
  },
  {
    name: 'Promoted',
    badge: 'POPULAR',
    features: ['Everything in Featured', 'Homepage banner', 'Push notifications', 'Priority support'],
  },
  {
    name: 'Spotlight',
    features: ['Everything in Promoted', 'Dedicated landing page', 'Custom branding', 'Advanced analytics'],
  },
];

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

type SaveState = 'idle' | 'saving';

const SponsorRegisterScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { showToast } = useToast();

  /* ---- refs for keyboard chaining ---- */
  const emailRef = useRef<TextInput>(null);
  const websiteRef = useRef<TextInput>(null);
  const descriptionRef = useRef<TextInput>(null);

  /* ---- form state ---- */
  const nameField = useFormField(compose(required('Company name'), maxLength('Company name', 255)));
  const logoUrlField = useFormField(url('Logo URL'));
  const websiteUrlField = useFormField(url('Website URL'));
  const contactEmailField = useFormField(compose(required('Contact email'), email('Contact email')));
  const descriptionField = useFormField(maxLength('Description', 1000));

  const [saveState, setSaveState] = useState<SaveState>('idle');

  /* ---- photo upload for logo ---- */
  const { pickAndUpload, uploading: logoUploading, photoUrl: uploadedLogoUrl, error: logoError } = usePhotoUpload('sponsor-logo');

  const handlePickLogo = async () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const resultUrl = await pickAndUpload('gallery');
    if (resultUrl) {
      logoUrlField.onChange(resultUrl);
    }
  };

  /* ---- derived ---- */
  const logoPreview = uploadedLogoUrl || (logoUrlField.value.trim() || null);

  const canSubmit =
    nameField.value.trim().length > 0 &&
    contactEmailField.value.trim().length > 0 &&
    !nameField.error &&
    !contactEmailField.error &&
    !logoUrlField.error &&
    !websiteUrlField.error &&
    !descriptionField.error &&
    saveState !== 'saving';

  /* ---- submit ---- */
  const handleSubmit = async () => {
    if (!validateAll(nameField, contactEmailField, logoUrlField, websiteUrlField, descriptionField)) return;
    if (!canSubmit) return;

    setSaveState('saving');
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

    try {
      await dataProvider.registerSponsorCompany({
        name: nameField.value.trim(),
        contactEmail: contactEmailField.value.trim(),
        ...(logoUrlField.value.trim() ? { logoUrl: logoUrlField.value.trim() } : {}),
        ...(websiteUrlField.value.trim() ? { websiteUrl: websiteUrlField.value.trim() } : {}),
        ...(descriptionField.value.trim() ? { description: descriptionField.value.trim() } : {}),
      });

      track({ name: 'sponsor_company_registered' });
      router.replace('/sponsor/dashboard');
    } catch (err: unknown) {
      logger.warn('[SponsorRegister] error:', err);
      showToast({ message: (err as Error)?.message || 'Failed to register company. Please try again.', type: 'error' });
    } finally {
      setSaveState('idle');
    }
  };

  /* ======================================================================== */
  /*  Render                                                                   */
  /* ======================================================================== */

  return (
    <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: 'Become a Sponsor' }} />
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
            {/* ============================================================ */}
            {/*  Hero Section                                                */}
            {/* ============================================================ */}
            <View style={styles.heroSection}>
              <View style={[styles.heroIconCircle, { backgroundColor: colors.accent + '20' }]}>
                <Ionicons name="megaphone" size={36} color={colors.accent} />
              </View>
              <Text style={[styles.heroTitle, { color: colors.text }]}>
                Sponsor on Sparrow Collect
              </Text>
              <Text style={[styles.heroSubtitle, { color: colors.muted }]}>
                Reach passionate collectors, announce exclusive drops, and grow your brand with the community that loves what you make.
              </Text>
            </View>

            {/* ============================================================ */}
            {/*  Benefits Grid (2x2)                                         */}
            {/* ============================================================ */}
            <View style={styles.benefitsGrid}>
              {BENEFITS.map((b) => (
                <View
                  key={b.title}
                  style={[styles.benefitCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                >
                  <View style={[styles.benefitIconCircle, { backgroundColor: colors.accent + '15' }]}>
                    <Ionicons name={b.icon} size={20} color={colors.accent} />
                  </View>
                  <Text style={[styles.benefitTitle, { color: colors.text }]}>{b.title}</Text>
                  <Text style={[styles.benefitDesc, { color: colors.muted }]}>{b.desc}</Text>
                </View>
              ))}
            </View>

            {/* ============================================================ */}
            {/*  Tier Preview (horizontal scroll)                            */}
            {/* ============================================================ */}
            <View style={styles.tierSection}>
              <View style={styles.sectionHeader}>
                <Ionicons name="ribbon-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Sponsorship Tiers</Text>
              </View>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.tierScroll}
              >
                {TIERS.map((tier) => (
                  <View
                    key={tier.name}
                    style={[
                      styles.tierCard,
                      { backgroundColor: colors.card, borderColor: tier.badge ? colors.accent : colors.border },
                      tier.badge && { borderWidth: 2 },
                    ]}
                  >
                    {tier.badge && (
                      <View style={[styles.tierBadge, { backgroundColor: colors.accent }]}>
                        <Text style={styles.tierBadgeText}>{tier.badge}</Text>
                      </View>
                    )}
                    <Text style={[styles.tierName, { color: colors.text }]}>{tier.name}</Text>
                    {tier.features.map((f) => (
                      <View key={f} style={styles.tierFeatureRow}>
                        <Ionicons name="checkmark-circle" size={14} color={colors.accent} />
                        <Text style={[styles.tierFeatureText, { color: colors.muted }]}>{f}</Text>
                      </View>
                    ))}
                  </View>
                ))}
              </ScrollView>
            </View>

            {/* ============================================================ */}
            {/*  Registration Form                                           */}
            {/* ============================================================ */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="business-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Company Information</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {/* Company Name */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>
                    Company Name <Text style={{ color: colors.accent }}>*</Text>
                  </Text>
                  <View style={[styles.inputWrap, { borderColor: nameField.touched && nameField.error ? colors.danger : colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="business-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={nameField.value}
                      onChangeText={nameField.onChange}
                      onBlur={nameField.onBlur}
                      placeholder="Games Workshop, TOPPS, Bandai"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      accessibilityLabel="Company name"
                      returnKeyType="next"
                      onSubmitEditing={() => emailRef.current?.focus()}
                    />
                  </View>
                  {nameField.touched && nameField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{nameField.error}</Text>}
                </View>

                {/* Contact Email */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>
                    Contact Email <Text style={{ color: colors.accent }}>*</Text>
                  </Text>
                  <View style={[styles.inputWrap, { borderColor: contactEmailField.touched && contactEmailField.error ? colors.danger : colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="mail-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      ref={emailRef}
                      value={contactEmailField.value}
                      onChangeText={contactEmailField.onChange}
                      onBlur={contactEmailField.onBlur}
                      placeholder="events@yourcompany.com"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      autoCapitalize="none"
                      keyboardType="email-address"
                      accessibilityLabel="Contact email"
                      returnKeyType="next"
                      onSubmitEditing={() => websiteRef.current?.focus()}
                    />
                  </View>
                  {contactEmailField.touched && contactEmailField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{contactEmailField.error}</Text>}
                </View>

                {/* Logo Picker */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Company Logo (optional)</Text>
                  <AnimatedPressable
                    onPress={handlePickLogo}
                    disabled={logoUploading}
                    style={[styles.logoPicker, { borderColor: colors.border, backgroundColor: colors.background }]}
                    accessibilityRole="button"
                    accessibilityLabel="Pick company logo"
                  >
                    {logoUploading ? (
                      <ActivityIndicator size="small" color={colors.accent} />
                    ) : logoPreview ? (
                      <View style={styles.logoPreviewWrap}>
                        <Image source={{ uri: logoPreview }} style={styles.logoPreviewImg} />
                        <Text style={[styles.logoChangeText, { color: colors.accent }]}>Tap to change</Text>
                      </View>
                    ) : (
                      <View style={styles.logoPickerContent}>
                        <Ionicons name="camera-outline" size={28} color={colors.muted} />
                        <Text style={[styles.logoPickerText, { color: colors.muted }]}>Tap to upload logo</Text>
                      </View>
                    )}
                  </AnimatedPressable>
                  {logoError && <Text style={[styles.fieldError, { color: colors.danger }]}>{logoError}</Text>}
                </View>

                {/* Website URL */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Website (optional)</Text>
                  <View style={[styles.inputWrap, { borderColor: websiteUrlField.touched && websiteUrlField.error ? colors.danger : colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="globe-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      ref={websiteRef}
                      value={websiteUrlField.value}
                      onChangeText={websiteUrlField.onChange}
                      onBlur={websiteUrlField.onBlur}
                      placeholder="https://yourcompany.com"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      autoCapitalize="none"
                      keyboardType="url"
                      accessibilityLabel="Website URL"
                      returnKeyType="next"
                      onSubmitEditing={() => descriptionRef.current?.focus()}
                    />
                  </View>
                  {websiteUrlField.touched && websiteUrlField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{websiteUrlField.error}</Text>}
                </View>

                {/* Description */}
                <View>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Description (optional)</Text>
                  <View style={[styles.inputWrapMultiline, { borderColor: descriptionField.touched && descriptionField.error ? colors.danger : colors.border, backgroundColor: colors.background }]}>
                    <TextInput
                      ref={descriptionRef}
                      value={descriptionField.value}
                      onChangeText={descriptionField.onChange}
                      onBlur={descriptionField.onBlur}
                      multiline
                      numberOfLines={4}
                      placeholder="Tell us about your company and what you'd like to sponsor..."
                      placeholderTextColor={colors.muted}
                      style={[styles.inputMultiline, { color: colors.text }]}
                      textAlignVertical="top"
                      accessibilityLabel="Company description"
                    />
                  </View>
                  {descriptionField.touched && descriptionField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{descriptionField.error}</Text>}
                </View>
              </View>
            </View>

            {/* ============================================================ */}
            {/*  Submit Button                                                */}
            {/* ============================================================ */}
            <AnimatedPressable
              onPress={handleSubmit}
              disabled={!canSubmit}
              style={[
                styles.submitButton,
                {
                  backgroundColor: canSubmit ? colors.accent : colors.border,
                },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Get started as a sponsor"
            >
              {saveState === 'saving' ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <Ionicons name="rocket-outline" size={20} color="#FFFFFF" />
                  <Text style={styles.submitButtonText}>Get Started as a Sponsor</Text>
                </>
              )}
            </AnimatedPressable>

            <Text style={[styles.finePrint, { color: colors.muted }]}>
              Registration is free. You'll choose a tier when creating your first event.
            </Text>

            <View style={{ height: 32 }} />
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
      <QuickNavBar />
    </View>
  );
};

/* -------------------------------------------------------------------------- */
/*  Styles                                                                     */
/* -------------------------------------------------------------------------- */

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
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
    paddingTop: 20,
  },

  /* Hero */
  heroSection: {
    alignItems: 'center',
    marginBottom: 28,
  },
  heroIconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  heroTitle: {
    fontSize: 24,
    fontWeight: '800',
    textAlign: 'center',
  },
  heroSubtitle: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginTop: 8,
    paddingHorizontal: 8,
  },

  /* Benefits grid */
  benefitsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 24,
  },
  benefitCard: {
    width: '48%' as unknown as number,
    flexBasis: '47%',
    flexGrow: 1,
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
  },
  benefitIconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 10,
  },
  benefitTitle: {
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 4,
  },
  benefitDesc: {
    fontSize: 12,
    lineHeight: 16,
  },

  /* Tier preview */
  tierSection: {
    marginBottom: 24,
  },
  tierScroll: {
    gap: 10,
    paddingRight: 4,
  },
  tierCard: {
    width: 200,
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
  },
  tierBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    marginBottom: 8,
  },
  tierBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  tierName: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 10,
  },
  tierFeatureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 6,
  },
  tierFeatureText: {
    fontSize: 12,
    flex: 1,
  },

  /* Form sections */
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
  inputIcon: {
    marginRight: 8,
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

  /* Logo picker */
  logoPicker: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderRadius: 12,
    height: 100,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  logoPreviewWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  logoPreviewImg: {
    width: 56,
    height: 56,
    borderRadius: 12,
  },
  logoChangeText: {
    fontSize: 12,
    fontWeight: '500',
  },
  logoPickerContent: {
    alignItems: 'center',
    gap: 6,
  },
  logoPickerText: {
    fontSize: 13,
  },

  /* Submit */
  submitButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    borderRadius: 12,
    marginTop: 4,
  },
  submitButtonText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  finePrint: {
    fontSize: 12,
    textAlign: 'center',
    marginTop: 12,
    lineHeight: 16,
    paddingHorizontal: 16,
  },
  fieldError: {
    fontSize: 12,
    marginTop: 4,
    marginLeft: 4,
  },
});

export default function SponsorRegisterScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Sponsor Register">
      <SponsorRegisterScreen />
    </ScreenErrorBoundary>
  );
}
