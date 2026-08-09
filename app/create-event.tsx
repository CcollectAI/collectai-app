/**
 * Create Event Screen -- Form to submit a new community event.
 * Route: /create-event
 *
 * Features:
 *  - Format selector (In-Person / Online / Hybrid) with chip UI
 *  - Geolocation support for in-person/hybrid events
 *  - Public / Private toggle
 *  - Invite-friends placeholder (post-creation)
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useModal } from '@/hooks/useModal';
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
  Switch,
  Animated,
  FlatList,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams, Stack } from 'expo-router';
import { dataProvider } from '@/data';
import type { EventKind, EventTemplate } from '@/data/events';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useEventForm, validateEventForm, buildEventInput, type EventFormat } from '@/hooks/useEventForm';
import { BottomSheetModal } from '@/components/BottomSheetModal';
import logger from '@/utils/logger';
import { logAuthState } from '@/utils/diagnostics';
import { useToast } from '@/components/Toast';
import { QuickNavBar } from '@/components/QuickNavBar';
import { FormField } from '@/components/form';
import { KIND_ICON } from '@/constants/eventConstants';
import { EventFormHeader } from '@/components/events/EventFormHeader';
import { EventDateTimePicker } from '@/components/events/EventDateTimePicker';
import { EventLocationSection } from '@/components/events/EventLocationSection';
import { EventTicketingSection } from '@/components/events/EventTicketingSection';
import { safeGoBack } from '@/lib/goBack';

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

const CreateEventScreen: React.FC = () => {
  const router = useRouter();
  const params = useLocalSearchParams<{ sponsorCompanyId?: string }>();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { showToast } = useToast();
  const isSponsored = !!params.sponsorCompanyId;

  /* ---- shared form hook ---- */
  const form = useEventForm();

  /* ---- detail input draft ---- */
  const [detailDraft, setDetailDraft] = useState('');

  /* ---- saving state ---- */
  const [saving, setSaving] = useState(false);

  /* ---- template state ---- */
  const [templates, setTemplates] = useState<EventTemplate[]>([]);
  const [templateSheetOpen, openTemplateSheet, closeTemplateSheet] = useModal();
  const [saveAsTemplate, setSaveAsTemplate] = useState(false);
  const [templateName, setTemplateName] = useState('');

  useEffect(() => {
    dataProvider.listEventTemplates().then(setTemplates).catch(() => {});
  }, []);

  const applyTemplate = useCallback((tpl: EventTemplate) => {
    const d = tpl.templateData as Record<string, unknown>;
    if (d.title) form.titleField.onChange(d.title as string);
    if (d.kind) form.setKind(d.kind as EventKind);
    if (d.category_id) form.setCategoryId(d.category_id as string);
    if (d.format) form.setFormat(d.format as EventFormat);
    if (d.location) form.setLocation(d.location as string);
    if (d.time) form.setTime(d.time as string);
    if (d.description) form.descriptionField.onChange(d.description as string);
    if (d.image_url) form.imageUrlField.onChange(d.image_url as string);
    if (d.online_url) form.onlineUrlField.onChange(d.online_url as string);
    if (d.is_public !== undefined) form.setIsPublic(d.is_public as boolean);
    closeTemplateSheet();
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
  }, [form, closeTemplateSheet]);

  /* ---- submit ---- */
  const handleSubmit = async () => {
    if (!validateEventForm(form)) return;
    if (!form.canSubmit || saving) return;

    setSaving(true);

    // DIAG: snapshot auth state right before the create call so a 401 shows
    // whether the device had a live, non-expired token (Console.app → "DIAG").
    void logAuthState('create-event');

    try {
      const input = buildEventInput(form, {
        ...(params.sponsorCompanyId
          ? { sponsorCompanyId: params.sponsorCompanyId, sponsorTier: 'featured' as const }
          : {}),
      });

      const created = await dataProvider.createEvent(input);

      // Save as template if toggled on
      if (saveAsTemplate && templateName.trim()) {
        try {
          await dataProvider.createEventTemplate(templateName.trim(), created.id);
        } catch (tplErr: unknown) {
          logger.error('[CreateEvent] template save error:', tplErr);
        }
      }

      safeGoBack(router);
    } catch (err: any) {
      logger.error('[CreateEvent] error:', err);
      showToast({ message: err?.message || 'Failed to create event. Please try again.', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  /* ======================================================================== */
  /*  Render                                                                   */
  /* ======================================================================== */

  return (
    <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: isSponsored ? 'Create Sponsored Event' : 'Create Event' }} />
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >

        {/* Sponsored badge */}
        {isSponsored && (
          <View style={[styles.sponsoredBanner, { backgroundColor: colors.accent + '12' }]}>
            <Ionicons name="megaphone-outline" size={16} color={colors.accent} />
            <Text style={[styles.sponsoredBannerText, { color: colors.accent }]}>
              This event will be marked as sponsored and highlighted to collectors.
            </Text>
          </View>
        )}

        {/* Template picker modal */}
        <BottomSheetModal
          visible={templateSheetOpen}
          onClose={() => closeTemplateSheet()}
          title="From Template"
          colors={{ ...colors, background: colors.card }}
          maxHeight="60%"
        >
          <View style={{ paddingBottom: 40 }}>
              {templates.length === 0 ? (
                <Text style={[styles.inviteNote, { color: colors.muted, padding: 20 }]}>No templates yet. Create events and save them as templates.</Text>
              ) : (
                <FlatList
                  data={templates}
                  keyExtractor={(t) => t.id}
                  renderItem={({ item }) => (
                    <TouchableOpacity
                      style={[styles.templateItem, { borderColor: colors.border }]}
                      onPress={() => applyTemplate(item)}
                    >
                      <Text style={[styles.templateName, { color: colors.text }]}>{item.name}</Text>
                      <Text style={[styles.templateMeta, { color: colors.muted }]}>Used {item.useCount} times</Text>
                    </TouchableOpacity>
                  )}
                />
              )}
          </View>
        </BottomSheetModal>

        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>

          {/* From Template button */}
          {templates.length > 0 && (
            <AnimatedPressable
              onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); openTemplateSheet(); }}
              style={[styles.fromTemplateBtn, { borderColor: colors.accent, backgroundColor: colors.accent + '10' }]}
              accessibilityRole="button"
              accessibilityLabel="Create from template"
            >
              <Ionicons name="copy-outline" size={16} color={colors.accent} />
              <Text style={[styles.fromTemplateBtnText, { color: colors.accent }]}>From Template</Text>
            </AnimatedPressable>
          )}

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
                {/* Existing description lines as bullet points */}
                {form.descriptionField.value.trim().length > 0 && (
                  <View style={styles.bulletList}>
                    {form.descriptionField.value.split('\n').filter(Boolean).map((line, idx) => (
                      <View key={idx} style={styles.bulletRow}>
                        <Text style={[styles.bulletDot, { color: colors.accent }]}>{'\u2022'}</Text>
                        <Text style={[styles.bulletText, { color: colors.text }]}>{line.replace(/^[\u2022\-\*]\s*/, '')}</Text>
                        <AnimatedPressable
                          onPress={() => {
                            const lines = form.descriptionField.value.split('\n').filter(Boolean);
                            lines.splice(idx, 1);
                            form.descriptionField.onChange(lines.join('\n'));
                          }}
                          style={styles.bulletRemove}
                          accessibilityRole="button"
                          accessibilityLabel={`Remove detail: ${line}`}
                        >
                          <Ionicons name="close-circle" size={16} color={colors.muted} />
                        </AnimatedPressable>
                      </View>
                    ))}
                  </View>
                )}
                {/* WhatsApp-style add detail input */}
                <View style={[styles.detailInputRow, { borderColor: form.descriptionField.touched && form.descriptionField.error ? colors.danger : colors.border, backgroundColor: colors.background }]}>
                  <TextInput
                    value={detailDraft}
                    onChangeText={setDetailDraft}
                    placeholder="Add a detail..."
                    placeholderTextColor={colors.muted}
                    style={[styles.detailInput, { color: colors.text }]}
                    returnKeyType="send"
                    onSubmitEditing={() => {
                      const draft = detailDraft.trim();
                      if (!draft) return;
                      const current = form.descriptionField.value.trim();
                      form.descriptionField.onChange(current ? `${current}\n${draft}` : draft);
                      setDetailDraft('');
                    }}
                    accessibilityLabel="Add event detail"
                  />
                  <AnimatedPressable
                    onPress={() => {
                      const draft = detailDraft.trim();
                      if (!draft) return;
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                      const current = form.descriptionField.value.trim();
                      form.descriptionField.onChange(current ? `${current}\n${draft}` : draft);
                      setDetailDraft('');
                    }}
                    style={[styles.detailSendBtn, { backgroundColor: colors.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel="Add detail to description"
                  >
                    <Ionicons name="arrow-up" size={18} color="#fff" />
                  </AnimatedPressable>
                </View>
                {form.descriptionField.touched && form.descriptionField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{form.descriptionField.error}</Text>}
              </View>
            </View>
          </View>

          {/* Section: Ticket Price (meetup/convention only) */}
          {(form.kind === 'meetup' || form.kind === 'convention') && (
            <EventTicketingSection
              ticketPriceCents={form.ticketPriceCents}
              onTicketPriceChange={form.setTicketPriceCents}
            />
          )}

          {/* ============================================================== */}
          {/*  Section: Event Image                                           */}
          {/* ============================================================== */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="image-outline" size={16} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Event Image (optional)</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <FormField
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
          {/*  Section: Save as Template                                      */}
          {/* ============================================================== */}
          <View style={styles.section}>
            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.toggleRow}>
                <View style={styles.toggleLeft}>
                  <Ionicons name="bookmark-outline" size={20} color={colors.accent} />
                  <View style={styles.toggleTextBlock}>
                    <Text style={[styles.toggleLabel, { color: colors.text }]}>Save as Template</Text>
                    <Text style={[styles.toggleHint, { color: colors.muted }]}>Reuse this event setup for future events</Text>
                  </View>
                </View>
                <Switch
                  value={saveAsTemplate}
                  onValueChange={(v) => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setSaveAsTemplate(v); }}
                  trackColor={{ false: colors.border, true: colors.accent + '60' }}
                  thumbColor={saveAsTemplate ? colors.accent : colors.muted}
                  ios_backgroundColor={colors.border}
                  accessibilityLabel="Save as template"
                />
              </View>
              {saveAsTemplate && (
                <View style={{ marginTop: 12 }}>
                  <FormField
                    label="Template Name"
                    value={templateName}
                    onChangeText={setTemplateName}
                    placeholder="Template name"
                    returnKeyType="done"
                  />
                </View>
              )}
            </View>
          </View>

          {/* ============================================================== */}
          {/*  Submit Button                                                  */}
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
            accessibilityLabel="Create event"
          >
            {saving ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <>
                <Ionicons name="checkmark-circle-outline" size={20} color="#FFFFFF" />
                <Text style={styles.submitButtonText}>Create Event</Text>
              </>
            )}
          </AnimatedPressable>

          {/* ============================================================== */}
          {/*  Invite Friends (post-creation placeholder)                     */}
          {/* ============================================================== */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="chatbubble-ellipses-outline" size={16} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Invite Friends</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Text style={[styles.inviteNote, { color: colors.muted }]}>
                You can invite friends after creating the event.
              </Text>
              <View
                style={[
                  styles.inviteButton,
                  {
                    backgroundColor: colors.border + '60',
                    borderColor: colors.border,
                  },
                ]}
              >
                <Ionicons name="chatbubbles-outline" size={18} color={colors.muted} />
                <Text style={[styles.inviteButtonText, { color: colors.muted }]}>
                  Invite Friends via Chat
                </Text>
              </View>
              <Text style={[styles.inviteSubtext, { color: colors.muted }]}>
                Available after event creation
              </Text>
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
  sponsoredBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  sponsoredBannerText: {
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
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

  /* Invite friends placeholder */
  inviteNote: {
    fontSize: 13,
    marginBottom: 12,
  },
  inviteButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
  },
  inviteButtonText: {
    fontSize: 14,
    fontWeight: '500',
  },
  inviteSubtext: {
    fontSize: 11,
    textAlign: 'center',
    marginTop: 6,
  },
  fieldError: {
    fontSize: 12,
    marginTop: 4,
    marginLeft: 4,
  },

  /* Bullet-point description */
  bulletList: {
    marginBottom: 10,
  },
  bulletRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: 4,
    gap: 6,
  },
  bulletDot: {
    fontSize: 16,
    lineHeight: 20,
    fontWeight: '700',
  },
  bulletText: {
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
  },
  bulletRemove: {
    padding: 2,
  },
  detailInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 24,
    paddingLeft: 14,
    paddingRight: 4,
    height: 44,
  },
  detailInput: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 0,
  },
  detailSendBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
  },

  /* From Template button */
  fromTemplateBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 16,
  },
  fromTemplateBtnText: {
    fontSize: 14,
    fontWeight: '500',
  },

  /* Template picker */
  templateItem: {
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  templateName: {
    fontSize: 15,
    fontWeight: '500',
  },
  templateMeta: {
    fontSize: 12,
    marginTop: 2,
  },
});

export default function CreateEventScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Create Event">
      <CreateEventScreen />
    </ScreenErrorBoundary>
  );
}
