/**
 * Compose Announcement Screen
 * Route: /events/compose-announcement?eventId=X
 *
 * Form for event hosts to compose and send an announcement
 * to all event attendees.
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
import { useRouter, useLocalSearchParams } from 'expo-router';
import { dataProvider } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useFormField, validateAll } from '@/hooks/useFormField';
import { compose, required, maxLength, url } from '@/lib/validate';
import logger from '@/utils/logger';

/* -------------------------------------------------------------------------- */
/*  Constants                                                                  */
/* -------------------------------------------------------------------------- */

const BODY_MAX_LENGTH = 2000;

type SaveState = 'idle' | 'sending';

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

const ComposeAnnouncementScreen: React.FC = () => {
  const { eventId } = useLocalSearchParams<{ eventId?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();

  /* ---- form state ---- */
  const titleField = useFormField(maxLength('Title', 255));
  const bodyField = useFormField(compose(required('Message'), maxLength('Message', BODY_MAX_LENGTH)));
  const imageUrlField = useFormField(url('Image URL'));

  const [saveState, setSaveState] = useState<SaveState>('idle');

  /* ---- derived ---- */
  const bodyLength = bodyField.value.length;
  const canSubmit =
    bodyField.value.trim().length > 0 &&
    !bodyField.error &&
    !titleField.error &&
    !imageUrlField.error &&
    saveState !== 'sending';

  /* ---- submit ---- */
  const handleSubmit = async () => {
    if (!eventId) {
      Alert.alert('Error', 'No event ID provided.');
      return;
    }
    if (!validateAll(bodyField, titleField, imageUrlField)) return;
    if (!canSubmit) return;

    setSaveState('sending');
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

    try {
      await dataProvider.postEventAnnouncement(
        eventId,
        bodyField.value.trim(),
        titleField.value.trim() || undefined,
        imageUrlField.value.trim() || undefined,
      );
      router.back();
    } catch (err: unknown) {
      logger.warn('[ComposeAnnouncement] error:', err);
      Alert.alert('Error', (err as Error)?.message || 'Failed to send announcement. Please try again.');
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
          <Text style={[styles.headerTitle, { color: colors.text }]}>Compose Announcement</Text>
          <View style={{ width: 32 }} />
        </View>

        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
            {/* Helper text */}
            <View style={[styles.helperCard, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '30' }]}>
              <Ionicons name="information-circle-outline" size={16} color={colors.accent} />
              <Text style={[styles.helperText, { color: colors.accent }]}>
                This will be sent to all attendees of this event.
              </Text>
            </View>

            {/* ============================================================ */}
            {/*  Section: Announcement                                        */}
            {/* ============================================================ */}
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="megaphone-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Announcement</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {/* Title (optional) */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Title (optional)</Text>
                  <View style={[styles.inputWrap, { borderColor: titleField.touched && titleField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="text-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={titleField.value}
                      onChangeText={titleField.onChange}
                      onBlur={titleField.onBlur}
                      placeholder="e.g. Schedule Update"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      accessibilityLabel="Announcement title"
                    />
                  </View>
                  {titleField.touched && titleField.error && <Text style={styles.fieldError}>{titleField.error}</Text>}
                </View>

                {/* Body (required) */}
                <View style={styles.fieldBlock}>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>
                    Message <Text style={{ color: colors.accent }}>*</Text>
                  </Text>
                  <View style={[styles.inputWrapMultiline, { borderColor: bodyField.touched && bodyField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                    <TextInput
                      value={bodyField.value}
                      onChangeText={bodyField.onChange}
                      onBlur={bodyField.onBlur}
                      multiline
                      numberOfLines={6}
                      maxLength={BODY_MAX_LENGTH}
                      placeholder="Write your announcement to attendees..."
                      placeholderTextColor={colors.muted}
                      style={[styles.inputMultiline, { color: colors.text }]}
                      textAlignVertical="top"
                      accessibilityLabel="Announcement body"
                    />
                  </View>
                  <View style={styles.charCountRow}>
                    {bodyField.touched && bodyField.error ? (
                      <Text style={styles.fieldError}>{bodyField.error}</Text>
                    ) : (
                      <View />
                    )}
                    <Text style={[styles.charCount, { color: bodyLength > BODY_MAX_LENGTH ? '#EF4444' : colors.muted }]}>
                      {bodyLength}/{BODY_MAX_LENGTH}
                    </Text>
                  </View>
                </View>

                {/* Image URL (optional) */}
                <View>
                  <Text style={[styles.fieldLabel, { color: colors.text }]}>Image URL (optional)</Text>
                  <View style={[styles.inputWrap, { borderColor: imageUrlField.touched && imageUrlField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="image-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={imageUrlField.value}
                      onChangeText={imageUrlField.onChange}
                      onBlur={imageUrlField.onBlur}
                      placeholder="https://example.com/image.jpg"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      autoCapitalize="none"
                      keyboardType="url"
                      accessibilityLabel="Image URL"
                    />
                  </View>
                  {imageUrlField.touched && imageUrlField.error && <Text style={styles.fieldError}>{imageUrlField.error}</Text>}
                </View>
              </View>
            </View>

            {/* ============================================================ */}
            {/*  Send Button                                                  */}
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
              accessibilityLabel="Send announcement"
            >
              {saveState === 'sending' ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <Ionicons name="send-outline" size={18} color="#FFFFFF" />
                  <Text style={styles.submitButtonText}>Send Announcement</Text>
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
  helperCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 20,
  },
  helperText: {
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
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
    minHeight: 140,
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
    minHeight: 116,
  },
  charCountRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
    paddingHorizontal: 4,
  },
  charCount: {
    fontSize: 11,
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

export default ComposeAnnouncementScreen;
