/**
 * Edit Event Screen -- Form to update an existing community event.
 * Route: /edit-event?eventId=X
 *
 * Features:
 *  - Loads existing event by ID and verifies current user is the creator
 *  - Pre-populates all form fields from existing event
 *  - Format selector (In-Person / Online / Hybrid) with chip UI
 *  - Geolocation support for in-person/hybrid events
 *  - Public / Private toggle
 *  - "Cancel Event" destructive button at bottom
 */

import React, { useState, useEffect } from 'react';
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
  Alert,
  Switch,
  Animated,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams, Stack } from 'expo-router';
import { dataProvider } from '@/data';
import type { CollectorsEvent, CreateEventInput } from '@/data/events';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useEventForm, validateEventForm, buildEventInput, type EventFormat } from '@/hooks/useEventForm';
import { useAuthContext } from '@/providers/useAuthContext';
import logger from '@/utils/logger';
import { useToast } from '@/components/Toast';
import { QuickNavBar } from '@/components/QuickNavBar';
import { EventFormHeader } from '@/components/events/EventFormHeader';
import { EventDateTimePicker } from '@/components/events/EventDateTimePicker';
import { EventLocationSection } from '@/components/events/EventLocationSection';
import { FormField as FormFieldComponent } from '@/components/form';

/* -------------------------------------------------------------------------- */
/*  Constants                                                                  */
/* -------------------------------------------------------------------------- */

const EVENT_FORMATS: { label: string; value: EventFormat; icon: keyof typeof Ionicons.glyphMap }[] = [
  { label: 'In-Person', value: 'in_person', icon: 'location-outline' },
  { label: 'Online', value: 'online', icon: 'globe-outline' },
  { label: 'Hybrid', value: 'hybrid', icon: 'git-merge-outline' },
];

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

const EditEventScreen: React.FC = () => {
  const router = useRouter();
  const { eventId } = useLocalSearchParams<{ eventId?: string }>();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { user } = useAuthContext();

  /* ---- loading / auth state ---- */
  const [initialLoading, setInitialLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [originalEvent, setOriginalEvent] = useState<CollectorsEvent | null>(null);

  /* ---- shared form hook ---- */
  const form = useEventForm({ initialEvent: originalEvent });

  /* ---- saving state ---- */
  const [saving, setSaving] = useState(false);

  /* ---- load existing event ---- */
  useEffect(() => {
    if (!eventId) {
      setAuthError('No event ID provided.');
      setInitialLoading(false);
      return;
    }

    (async () => {
      try {
        const evt = await dataProvider.getEventById(eventId);
        if (!evt) {
          setAuthError('Event not found.');
          setInitialLoading(false);
          return;
        }

        // Verify current user is the creator
        const currentUserId = user?.id;
        if (!currentUserId || (evt.createdBy !== currentUserId && evt.hostUserId !== currentUserId)) {
          setAuthError('You do not have permission to edit this event.');
          setInitialLoading(false);
          return;
        }

        setOriginalEvent(evt);
      } catch (err: unknown) {
        logger.warn('[EditEvent] load error:', err);
        setAuthError('Failed to load event.');
      } finally {
        setInitialLoading(false);
      }
    })();
  }, [eventId, user?.id]);

  /* ---- submit ---- */
  const handleSubmit = async () => {
    if (!validateEventForm(form)) return;
    if (!form.canSubmit || !eventId || saving) return;

    setSaving(true);

    try {
      const patch: Partial<CreateEventInput> = {
        ...buildEventInput(form),
        // For edit, explicitly set undefined for cleared optional fields
        ...(form.categoryId ? { categoryId: form.categoryId } : { categoryId: undefined }),
        ...(form.time.trim() ? { time: form.time.trim() } : { time: undefined }),
        ...(form.endDate.trim() ? { endDate: form.endDate.trim() } : { endDate: undefined }),
        ...(form.location.trim() ? { location: form.location.trim() } : { location: undefined }),
        ...(form.onlineUrlField.value.trim() ? { onlineUrl: form.onlineUrlField.value.trim() } : { onlineUrl: undefined }),
        ...(form.imageUrlField.value.trim() ? { imageUrl: form.imageUrlField.value.trim() } : { imageUrl: undefined }),
      };

      await dataProvider.updateEvent(eventId, patch);
      router.back();
    } catch (err: unknown) {
      logger.warn('[EditEvent] error:', err);
      showToast({ message: (err as Error)?.message || 'Failed to update event. Please try again.', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  /* ---- cancel event ---- */
  const handleCancelEvent = () => {
    if (!eventId) return;

    Alert.alert(
      'Cancel Event',
      'Are you sure you want to cancel this event? This action cannot be undone and all attendees will be notified.',
      [
        { text: 'Keep Event', style: 'cancel' },
        {
          text: 'Cancel Event',
          style: 'destructive',
          onPress: async () => {
            try {
              await dataProvider.cancelEvent(eventId);
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              router.back();
            } catch (err: unknown) {
              logger.warn('[EditEvent] cancel error:', err);
              showToast({ message: (err as Error)?.message || 'Failed to cancel event.', type: 'error' });
            }
          },
        },
      ],
    );
  };

  /* ======================================================================== */
  /*  Loading / Error states                                                   */
  /* ======================================================================== */

  if (initialLoading) {
    return (
      <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.muted }]}>Loading event...</Text>
        </View>
        <QuickNavBar />
      </View>
    );
  }

  if (authError) {
    return (
      <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
        <View style={styles.centerContainer}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.danger} />
          <Text style={[styles.errorTitle, { color: colors.text }]}>{authError}</Text>
          <AnimatedPressable
            onPress={() => router.back()}
            style={[styles.errorBtn, { borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Text style={[styles.errorBtnText, { color: colors.text }]}>Go Back</Text>
          </AnimatedPressable>
        </View>
        <QuickNavBar />
      </View>
    );
  }

  /* ======================================================================== */
  /*  Render                                                                   */
  /* ======================================================================== */

  return (
    <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: 'Edit Event' }} />
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

          {/* Section: Basic Information */}
          <EventFormHeader
            titleField={form.titleField}
            kind={form.kind}
            onKindChange={form.setKind}
            categoryId={form.categoryId}
            onCategoryChange={form.setCategoryId}
          />

          {/* ============================================================== */}
          {/*  Section: Format                                                */}
          {/* ============================================================== */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="options-outline" size={16} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Format</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.chipRow}>
                {EVENT_FORMATS.map((opt) => {
                  const isSelected = form.format === opt.value;
                  return (
                    <AnimatedPressable
                      key={opt.value}
                      style={[
                        styles.chip,
                        {
                          backgroundColor: isSelected ? colors.accent + '20' : colors.background,
                          borderColor: isSelected ? colors.accent : colors.border,
                        },
                      ]}
                      onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); form.setFormat(opt.value); }}
                      accessibilityRole="button"
                      accessibilityLabel={`${opt.label} format${isSelected ? ', selected' : ''}`}
                    >
                      <Ionicons
                        name={opt.icon}
                        size={14}
                        color={isSelected ? colors.accent : colors.muted}
                      />
                      <Text
                        style={[
                          styles.chipText,
                          { color: isSelected ? colors.accent : colors.text },
                        ]}
                      >
                        {opt.label}
                      </Text>
                    </AnimatedPressable>
                  );
                })}
              </View>
            </View>
          </View>

          {/* Section: Date & Time */}
          <EventDateTimePicker
            dateField={form.dateField}
            time={form.time}
            onTimeChange={form.setTime}
            endDate={form.endDate}
            onEndDateChange={form.setEndDate}
          />

          {/* Section: Location / Online URL */}
          <EventLocationSection
            showLocation={form.showLocation}
            showOnlineUrl={form.showOnlineUrl}
            location={form.location}
            onLocationChange={(text) => {
              form.setLocation(text);
              if (form.latitude !== undefined) {
                form.clearCoordinates();
              }
            }}
            onUseMyLocation={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); form.handleUseMyLocation(); }}
            geoLoading={form.geoLoading}
            latitude={form.latitude}
            longitude={form.longitude}
            onlineUrlField={form.onlineUrlField}
          />

          {/* ============================================================== */}
          {/*  Section: Description                                           */}
          {/* ============================================================== */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="document-text-outline" size={16} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Details</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.fieldBlock}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>
                  Description <Text style={{ color: colors.accent }}>*</Text>
                </Text>
                <View style={[styles.inputWrapMultiline, { borderColor: form.descriptionField.touched && form.descriptionField.error ? colors.danger : colors.border, backgroundColor: colors.background }]}>
                  <TextInput
                    value={form.descriptionField.value}
                    onChangeText={form.descriptionField.onChange}
                    onBlur={form.descriptionField.onBlur}
                    multiline
                    numberOfLines={4}
                    placeholder="What should attendees know about this event?"
                    placeholderTextColor={colors.muted}
                    style={[styles.inputMultiline, { color: colors.text }]}
                    textAlignVertical="top"
                    accessibilityLabel="Event description"
                  />
                </View>
                {form.descriptionField.touched && form.descriptionField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{form.descriptionField.error}</Text>}
              </View>
            </View>
          </View>

          {/* ============================================================== */}
          {/*  Section: Event Image                                           */}
          {/* ============================================================== */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="image-outline" size={16} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Event Image (optional)</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <FormFieldComponent
                label="Image URL"
                value={form.imageUrlField.value}
                onChangeText={form.imageUrlField.onChange}
                onBlur={form.imageUrlField.onBlur}
                placeholder="https://example.com/event-image.jpg"
                error={form.imageUrlField.touched && form.imageUrlField.error ? form.imageUrlField.error : null}
                autoCapitalize="none"
                keyboardType="url"
                returnKeyType="done"
              />
            </View>
          </View>

          {/* ============================================================== */}
          {/*  Section: Visibility                                            */}
          {/* ============================================================== */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="eye-outline" size={16} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Visibility</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.toggleRow}>
                <View style={styles.toggleLeft}>
                  <Ionicons
                    name={form.isPublic ? 'globe-outline' : 'lock-closed-outline'}
                    size={20}
                    color={colors.accent}
                  />
                  <View style={styles.toggleTextBlock}>
                    <Text style={[styles.toggleLabel, { color: colors.text }]}>
                      {form.isPublic ? 'Public' : 'Private'}
                    </Text>
                    <Text style={[styles.toggleHint, { color: colors.muted }]}>
                      {form.isPublic
                        ? 'Anyone can see and join this event'
                        : 'Only people you invite can see this event'}
                    </Text>
                  </View>
                </View>
                <Switch
                  value={form.isPublic}
                  onValueChange={(v) => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); form.setIsPublic(v); }}
                  trackColor={{ false: colors.border, true: colors.accent + '60' }}
                  thumbColor={form.isPublic ? colors.accent : colors.muted}
                  ios_backgroundColor={colors.border}
                  accessibilityLabel={form.isPublic ? "Event is public" : "Event is private"}
                />
              </View>
            </View>
          </View>

          {/* ============================================================== */}
          {/*  Save Changes Button                                            */}
          {/* ============================================================== */}
          <AnimatedPressable
            onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED); handleSubmit(); }}
            disabled={!form.canSubmit || saving}
            style={[
              styles.submitButton,
              {
                backgroundColor: form.canSubmit && !saving ? colors.accent : colors.border,
              },
            ]}
            accessibilityRole="button"
            accessibilityLabel="Save changes"
          >
            {saving ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <>
                <Ionicons name="checkmark-circle-outline" size={20} color="#FFFFFF" />
                <Text style={styles.submitButtonText}>Save Changes</Text>
              </>
            )}
          </AnimatedPressable>

          {/* ============================================================== */}
          {/*  Cancel Event (Destructive)                                     */}
          {/* ============================================================== */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="warning-outline" size={16} color={colors.danger} />
              <Text style={[styles.sectionTitle, { color: colors.danger }]}>Danger Zone</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.danger + '30' }]}>
              <Text style={[styles.dangerHint, { color: colors.muted }]}>
                Cancelling this event is permanent. All attendees will be notified.
              </Text>
              <AnimatedPressable
                onPress={handleCancelEvent}
                style={[styles.cancelEventButton, { backgroundColor: colors.danger }]}
                accessibilityRole="button"
                accessibilityLabel="Cancel event"
              >
                <Ionicons name="close-circle-outline" size={20} color="#FFFFFF" />
                <Text style={styles.cancelEventButtonText}>Cancel Event</Text>
              </AnimatedPressable>
            </View>
          </View>

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
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  loadingText: {
    fontSize: 14,
    marginTop: 12,
  },
  errorTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginTop: 16,
    textAlign: 'center',
  },
  errorBtn: {
    marginTop: 20,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
  },
  errorBtnText: {
    fontSize: 14,
    fontWeight: '500',
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
  inputWrapMultiline: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    minHeight: 100,
  },
  inputMultiline: {
    flex: 1,
    fontSize: 14,
    minHeight: 76,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
  },
  chipText: {
    fontSize: 13,
    fontWeight: '500',
  },

  /* Public / Private toggle */
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  toggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
    marginRight: 12,
  },
  toggleTextBlock: {
    flex: 1,
  },
  toggleLabel: {
    fontSize: 14,
    fontWeight: '600',
  },
  toggleHint: {
    fontSize: 12,
    marginTop: 2,
  },

  /* Submit button */
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

  /* Cancel Event button (destructive) */
  dangerHint: {
    fontSize: 13,
    marginBottom: 12,
    lineHeight: 18,
  },
  cancelEventButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: '#EF4444', // overridden inline via colors.danger
  },
  cancelEventButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },

  fieldError: {
    fontSize: 12,
    marginTop: 4,
    marginLeft: 4,
  },
});

export default function EditEventScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Edit Event">
      <EditEventScreen />
    </ScreenErrorBoundary>
  );
}
