/**
 * Sponsor Company Registration Screen
 * Route: /sponsor/register
 *
 * Form to register a new sponsor company with name, logo, website,
 * contact email, and description.
 */

import React, { useState } from 'react';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  TextInput,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Alert,
  Animated,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { dataProvider } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useFormField, validateAll } from '@/hooks/useFormField';
import { compose, required, maxLength, email, url } from '@/lib/validate';
import logger from '@/utils/logger';

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

type SaveState = 'idle' | 'saving';

const SponsorRegisterScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();

  /* ---- form state ---- */
  const nameField = useFormField(compose(required('Company name'), maxLength('Company name', 255)));
  const logoUrlField = useFormField(url('Logo URL'));
  const websiteUrlField = useFormField(url('Website URL'));
  const contactEmailField = useFormField(compose(required('Contact email'), email('Contact email')));
  const descriptionField = useFormField(maxLength('Description', 1000));

  const [saveState, setSaveState] = useState<SaveState>('idle');

  /* ---- derived ---- */
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

      router.replace('/sponsor/dashboard');
    } catch (err: unknown) {
      logger.warn('[SponsorRegister] error:', err);
      Alert.alert('Error', (err as Error)?.message || 'Failed to register company. Please try again.');
    } finally {
      setSaveState('idle');
    }
  };

  /* ======================================================================== */
  /*  Render                                                                   */
  /* ======================================================================== */

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        {/* ---------------------------------------------------------------- */}
        {/*  Header                                                          */}
        {/* ---------------------------------------------------------------- */}
        <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
          <AnimatedPressable
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.back(); }}
            style={styles.backBtn}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Register Sponsor Company</Text>
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
            {/*  Section: Company Information                                 */}
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
                  <View style={[styles.inputWrap, { borderColor: nameField.touched && nameField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="business-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={nameField.value}
                      onChangeText={nameField.onChange}
                      onBlur={nameField.onBlur}
                      placeholder="e.g. Acme Collectibles Inc."
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      accessibilityLabel="Company name"
                    />
                  </View>
                  {nameField.touched && nameField.error && <Text style={styles.fieldError}>{nameField.error}</Text>}
                </View>

                {/* Contact Email */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>
                    Contact Email <Text style={{ color: colors.accent }}>*</Text>
                  </Text>
                  <View style={[styles.inputWrap, { borderColor: contactEmailField.touched && contactEmailField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="mail-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={contactEmailField.value}
                      onChangeText={contactEmailField.onChange}
                      onBlur={contactEmailField.onBlur}
                      placeholder="sponsor@example.com"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      autoCapitalize="none"
                      keyboardType="email-address"
                      accessibilityLabel="Contact email"
                    />
                  </View>
                  {contactEmailField.touched && contactEmailField.error && <Text style={styles.fieldError}>{contactEmailField.error}</Text>}
                </View>

                {/* Logo URL */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Logo URL (optional)</Text>
                  <View style={[styles.inputWrap, { borderColor: logoUrlField.touched && logoUrlField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="image-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={logoUrlField.value}
                      onChangeText={logoUrlField.onChange}
                      onBlur={logoUrlField.onBlur}
                      placeholder="https://example.com/logo.png"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      autoCapitalize="none"
                      keyboardType="url"
                      accessibilityLabel="Logo URL"
                    />
                  </View>
                  {logoUrlField.touched && logoUrlField.error && <Text style={styles.fieldError}>{logoUrlField.error}</Text>}
                </View>

                {/* Website URL */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Website (optional)</Text>
                  <View style={[styles.inputWrap, { borderColor: websiteUrlField.touched && websiteUrlField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="globe-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={websiteUrlField.value}
                      onChangeText={websiteUrlField.onChange}
                      onBlur={websiteUrlField.onBlur}
                      placeholder="https://example.com"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      autoCapitalize="none"
                      keyboardType="url"
                      accessibilityLabel="Website URL"
                    />
                  </View>
                  {websiteUrlField.touched && websiteUrlField.error && <Text style={styles.fieldError}>{websiteUrlField.error}</Text>}
                </View>

                {/* Description */}
                <View>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Description (optional)</Text>
                  <View style={[styles.inputWrapMultiline, { borderColor: descriptionField.touched && descriptionField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                    <TextInput
                      value={descriptionField.value}
                      onChangeText={descriptionField.onChange}
                      onBlur={descriptionField.onBlur}
                      multiline
                      numberOfLines={4}
                      placeholder="Tell us about your company and what you sponsor..."
                      placeholderTextColor={colors.muted}
                      style={[styles.inputMultiline, { color: colors.text }]}
                      textAlignVertical="top"
                      accessibilityLabel="Company description"
                    />
                  </View>
                  {descriptionField.touched && descriptionField.error && <Text style={styles.fieldError}>{descriptionField.error}</Text>}
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
              accessibilityLabel="Register sponsor company"
            >
              {saveState === 'saving' ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <Ionicons name="checkmark-circle-outline" size={20} color="#FFFFFF" />
                  <Text style={styles.submitButtonText}>Register Company</Text>
                </>
              )}
            </AnimatedPressable>

            <View style={{ height: 32 }} />
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
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
  submitButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 4,
    marginBottom: 20,
  },
  submitButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  fieldError: {
    fontSize: 12,
    color: '#EF4444',
    marginTop: 4,
    marginLeft: 4,
  },
});

export default SponsorRegisterScreen;
