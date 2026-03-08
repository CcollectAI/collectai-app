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
import type { EventKind, CreateEventInput, EventTemplate } from '@/data/events';
import { CATEGORIES } from '@/constants/categories';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useFormField, validateAll } from '@/hooks/useFormField';
import { compose, required, maxLength, dateYMD, url } from '@/lib/validate';
import CompactSelect from '@/components/CompactSelect';
import { BottomSheetModal } from '@/components/BottomSheetModal';
import logger from '@/utils/logger';
import { useToast } from '@/components/Toast';
import { QuickNavBar } from '@/components/QuickNavBar';
import { KIND_ICON } from '@/constants/eventConstants';

/* -------------------------------------------------------------------------- */
/*  Constants                                                                  */
/* -------------------------------------------------------------------------- */

type SaveState = 'idle' | 'saving';
type EventFormat = 'in_person' | 'online' | 'hybrid';

const EVENT_KINDS: { label: string; value: EventKind }[] = [
  { label: 'Meetup', value: 'meetup' },
  { label: 'Drop', value: 'collection_drop' },
  { label: 'Stream', value: 'stream' },
  { label: 'Convention', value: 'convention' },
  { label: 'Release', value: 'release' },
];

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

  /* ---- form state ---- */
  const titleField = useFormField(compose(required('Title'), maxLength('Title', 255)));
  const [kind, setKind] = useState<EventKind>('meetup');
  const [categoryId, setCategoryId] = useState<string | undefined>(undefined);
  const [format, setFormat] = useState<EventFormat>('in_person');
  const dateField = useFormField(compose(required('Date'), dateYMD('Date')));
  const [time, setTime] = useState('');
  const [endDate, setEndDate] = useState('');
  const [location, setLocation] = useState('');
  const onlineUrlField = useFormField(url('Online URL'));
  const imageUrlField = useFormField(url('Image URL'));
  const descriptionField = useFormField(compose(required('Description'), maxLength('Description', 2000)));
  const [isPublic, setIsPublic] = useState(true);
  const [ticketPriceCents, setTicketPriceCents] = useState('');

  /* ---- detail input draft ---- */
  const [detailDraft, setDetailDraft] = useState('');

  /* ---- geolocation state ---- */
  const [latitude, setLatitude] = useState<number | undefined>(undefined);
  const [longitude, setLongitude] = useState<number | undefined>(undefined);
  const [geoLoading, setGeoLoading] = useState(false);

  const [saveState, setSaveState] = useState<SaveState>('idle');

  /* ---- template state ---- */
  const [templates, setTemplates] = useState<EventTemplate[]>([]);
  const [templateSheetOpen, setTemplateSheetOpen] = useState(false);
  const [saveAsTemplate, setSaveAsTemplate] = useState(false);
  const [templateName, setTemplateName] = useState('');

  useEffect(() => {
    dataProvider.listEventTemplates().then(setTemplates).catch(() => {});
  }, []);

  const applyTemplate = useCallback((tpl: EventTemplate) => {
    const d = tpl.templateData as Record<string, unknown>;
    if (d.title) titleField.onChange(d.title as string);
    if (d.kind) setKind(d.kind as EventKind);
    if (d.category_id) setCategoryId(d.category_id as string);
    if (d.format) setFormat(d.format as EventFormat);
    if (d.location) setLocation(d.location as string);
    if (d.time) setTime(d.time as string);
    if (d.description) descriptionField.onChange(d.description as string);
    if (d.image_url) imageUrlField.onChange(d.image_url as string);
    if (d.online_url) onlineUrlField.onChange(d.online_url as string);
    if (d.is_public !== undefined) setIsPublic(d.is_public as boolean);
    setTemplateSheetOpen(false);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
  }, [titleField, descriptionField, imageUrlField, onlineUrlField]);

  /* ---- derived ---- */
  const showLocation = format === 'in_person' || format === 'hybrid';
  const showOnlineUrl = format === 'online' || format === 'hybrid';

  const canSubmit =
    titleField.value.trim().length > 0 &&
    dateField.value.trim().length > 0 &&
    descriptionField.value.trim().length > 0 &&
    !titleField.error && !dateField.error && !descriptionField.error && !onlineUrlField.error && !imageUrlField.error &&
    saveState !== 'saving';

  /* ---- geolocation handler ---- */
  const handleUseMyLocation = useCallback(async () => {
    setGeoLoading(true);
    try {
      // @ts-expect-error expo-location is an optional peer dependency loaded at runtime
      const Location = await import('expo-location');

      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        showToast({ message: 'Location permission is required to use this feature.', type: 'warning' });
        return;
      }

      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setLatitude(pos.coords.latitude);
      setLongitude(pos.coords.longitude);

      // Reverse geocode to get city name
      const results = await Location.reverseGeocodeAsync({
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
      });

      if (results.length > 0) {
        const place = results[0];
        const parts: string[] = [];
        if (place.city) parts.push(place.city);
        if (place.region) parts.push(place.region);
        if (place.country) parts.push(place.country);
        const name = parts.join(', ');
        if (name) setLocation(name);
      }
    } catch (err: unknown) {
      logger.warn('[CreateEvent] geolocation error:', err);
      showToast({ message: 'Could not retrieve your location. Please enter it manually.', type: 'error' });
    } finally {
      setGeoLoading(false);
    }
  }, []);

  /* ---- submit ---- */
  const handleSubmit = async () => {
    if (!validateAll(titleField, dateField, descriptionField, onlineUrlField, imageUrlField)) return;
    if (!canSubmit) return;

    setSaveState('saving');

    try {
      const input: CreateEventInput = {
        title: titleField.value.trim(),
        kind,
        date: dateField.value.trim(),
        description: descriptionField.value.trim(),
        format,
        isPublic,
        ...(categoryId ? { categoryId } : {}),
        ...(time.trim() ? { time: time.trim() } : {}),
        ...(endDate.trim() ? { endDate: endDate.trim() } : {}),
        ...(location.trim() ? { location: location.trim() } : {}),
        ...(onlineUrlField.value.trim() ? { onlineUrl: onlineUrlField.value.trim() } : {}),
        ...(imageUrlField.value.trim() ? { imageUrl: imageUrlField.value.trim() } : {}),
        ...(latitude !== undefined ? { latitude } : {}),
        ...(longitude !== undefined ? { longitude } : {}),
        ...(ticketPriceCents.trim() ? { ticketPriceCents: Math.round(parseFloat(ticketPriceCents) * 100) } : {}),
        ...(params.sponsorCompanyId ? { sponsorCompanyId: params.sponsorCompanyId, sponsorTier: 'featured' as const } : {}),
      };

      const created = await dataProvider.createEvent(input);

      // Save as template if toggled on
      if (saveAsTemplate && templateName.trim()) {
        try {
          await dataProvider.createEventTemplate(templateName.trim(), created.id);
        } catch (tplErr: unknown) {
          logger.warn('[CreateEvent] template save error:', tplErr);
        }
      }

      router.back();
    } catch (err: any) {
      logger.warn('[CreateEvent] error:', err);
      showToast({ message: err?.message || 'Failed to create event. Please try again.', type: 'error' });
    } finally {
      setSaveState('idle');
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
          onClose={() => setTemplateSheetOpen(false)}
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
              onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setTemplateSheetOpen(true); }}
              style={[styles.fromTemplateBtn, { borderColor: colors.accent, backgroundColor: colors.accent + '10' }]}
              accessibilityRole="button"
              accessibilityLabel="Create from template"
            >
              <Ionicons name="copy-outline" size={16} color={colors.accent} />
              <Text style={[styles.fromTemplateBtnText, { color: colors.accent }]}>From Template</Text>
            </AnimatedPressable>
          )}

          {/* ============================================================== */}
          {/*  Section: Basic Information                                     */}
          {/* ============================================================== */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="information-circle-outline" size={16} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Basic Information</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              {/* Title */}
              <View style={styles.fieldBlock}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>
                  Title <Text style={{ color: colors.accent }}>*</Text>
                </Text>
                <View style={[styles.inputWrap, { borderColor: titleField.touched && titleField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                  <Ionicons name="text-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                  <TextInput
                    value={titleField.value}
                    onChangeText={titleField.onChange}
                    onBlur={titleField.onBlur}
                    placeholder="e.g. Rotterdam TCG Meetup"
                    placeholderTextColor={colors.muted}
                    style={[styles.input, { color: colors.text }]}
                    accessibilityLabel="Event title"
                  />
                </View>
                {titleField.touched && titleField.error && <Text style={styles.fieldError}>{titleField.error}</Text>}
              </View>

              {/* Kind dropdown */}
              <View style={styles.fieldBlock}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>Kind</Text>
                <CompactSelect
                  title="Kind"
                  value={EVENT_KINDS.find((k) => k.value === kind)?.label}
                  options={EVENT_KINDS.map((k) => k.label)}
                  onChange={(label) => {
                    const match = EVENT_KINDS.find((k) => k.label === label);
                    if (match) setKind(match.value);
                  }}
                />
              </View>

              {/* Category dropdown */}
              <View style={styles.fieldBlock}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>Category (optional)</Text>
                <CompactSelect
                  title="Category"
                  searchable
                  value={categoryId ? CATEGORIES.find((c) => c.slug === categoryId)?.name ?? 'None' : 'None'}
                  options={['None', ...CATEGORIES.map((c) => c.name)]}
                  onChange={(name) => {
                    if (name === 'None') {
                      setCategoryId(undefined);
                    } else {
                      const match = CATEGORIES.find((c) => c.name === name);
                      if (match) setCategoryId(match.slug);
                    }
                  }}
                />
              </View>
            </View>
          </View>

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
                  const isSelected = format === opt.value;
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
                      onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setFormat(opt.value); }}
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

          {/* ============================================================== */}
          {/*  Section: Date & Time                                           */}
          {/* ============================================================== */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="calendar-outline" size={16} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Date & Time</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              {/* Date */}
              <View style={styles.fieldBlock}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>
                  Date <Text style={{ color: colors.accent }}>*</Text>
                </Text>
                <View style={[styles.inputWrap, { borderColor: dateField.touched && dateField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                  <Ionicons name="calendar-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                  <TextInput
                    value={dateField.value}
                    onChangeText={dateField.onChange}
                    onBlur={dateField.onBlur}
                    placeholder="YYYY-MM-DD"
                    placeholderTextColor={colors.muted}
                    style={[styles.input, { color: colors.text }]}
                    accessibilityLabel="Event date"
                  />
                </View>
                {dateField.touched && dateField.error && <Text style={styles.fieldError}>{dateField.error}</Text>}
              </View>

              {/* Time */}
              <View style={styles.fieldBlock}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>Time (optional)</Text>
                <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                  <Ionicons name="time-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                  <TextInput
                    value={time}
                    onChangeText={setTime}
                    placeholder="19:30 CET"
                    placeholderTextColor={colors.muted}
                    style={[styles.input, { color: colors.text }]}
                    accessibilityLabel="Event time"
                  />
                </View>
              </View>

              {/* End Date */}
              <View style={styles.fieldBlock}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>End Date (optional, for multi-day)</Text>
                <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                  <Ionicons name="calendar-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                  <TextInput
                    value={endDate}
                    onChangeText={setEndDate}
                    placeholder="YYYY-MM-DD"
                    placeholderTextColor={colors.muted}
                    style={[styles.input, { color: colors.text }]}
                    accessibilityLabel="Event end date"
                  />
                </View>
              </View>
            </View>
          </View>

          {/* ============================================================== */}
          {/*  Section: Location / Online URL                                 */}
          {/* ============================================================== */}
          {(showLocation || showOnlineUrl) && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="location-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>
                  {showLocation && showOnlineUrl ? 'Location & Link' : showLocation ? 'Location' : 'Online Link'}
                </Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {/* Physical location */}
                {showLocation && (
                  <View style={styles.fieldBlock}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Location</Text>
                    <View style={styles.locationRow}>
                      <View
                        style={[
                          styles.inputWrap,
                          styles.locationInput,
                          { borderColor: colors.border, backgroundColor: colors.background },
                        ]}
                      >
                        <Ionicons name="location-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                        <TextInput
                          value={location}
                          onChangeText={(text) => {
                            setLocation(text);
                            // Clear coordinates when user manually edits
                            if (latitude !== undefined) {
                              setLatitude(undefined);
                              setLongitude(undefined);
                            }
                          }}
                          placeholder="e.g. Amsterdam, Netherlands"
                          placeholderTextColor={colors.muted}
                          style={[styles.input, { color: colors.text }]}
                          accessibilityLabel="Event location"
                        />
                      </View>
                      <AnimatedPressable
                        onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); handleUseMyLocation(); }}
                        disabled={geoLoading}
                        style={[
                          styles.geoButton,
                          {
                            backgroundColor: colors.accent + '15',
                            borderColor: colors.accent + '40',
                          },
                        ]}
                        accessibilityRole="button"
                        accessibilityLabel="Use my current location"
                      >
                        {geoLoading ? (
                          <ActivityIndicator size="small" color={colors.accent} />
                        ) : (
                          <Ionicons name="navigate-outline" size={18} color={colors.accent} />
                        )}
                      </AnimatedPressable>
                    </View>
                    {latitude !== undefined && longitude !== undefined && (
                      <Text style={[styles.geoHint, { color: colors.muted }]}>
                        Coordinates captured ({latitude.toFixed(4)}, {longitude.toFixed(4)})
                      </Text>
                    )}
                  </View>
                )}

                {/* Online URL */}
                {showOnlineUrl && (
                  <View style={showLocation ? styles.fieldBlock : undefined}>
                    <Text style={[styles.fieldLabel, { color: colors.text }]}>Online URL</Text>
                    <View style={[styles.inputWrap, { borderColor: onlineUrlField.touched && onlineUrlField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                      <Ionicons name="link-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                      <TextInput
                        value={onlineUrlField.value}
                        onChangeText={onlineUrlField.onChange}
                        onBlur={onlineUrlField.onBlur}
                        placeholder="https://..."
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                        autoCapitalize="none"
                        keyboardType="url"
                        accessibilityLabel="Online event URL"
                      />
                    </View>
                    {onlineUrlField.touched && onlineUrlField.error && <Text style={styles.fieldError}>{onlineUrlField.error}</Text>}
                  </View>
                )}
              </View>
            </View>
          )}

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
                {descriptionField.value.trim().length > 0 && (
                  <View style={styles.bulletList}>
                    {descriptionField.value.split('\n').filter(Boolean).map((line, idx) => (
                      <View key={idx} style={styles.bulletRow}>
                        <Text style={[styles.bulletDot, { color: colors.accent }]}>{'\u2022'}</Text>
                        <Text style={[styles.bulletText, { color: colors.text }]}>{line.replace(/^[\u2022\-\*]\s*/, '')}</Text>
                        <AnimatedPressable
                          onPress={() => {
                            const lines = descriptionField.value.split('\n').filter(Boolean);
                            lines.splice(idx, 1);
                            descriptionField.onChange(lines.join('\n'));
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
                <View style={[styles.detailInputRow, { borderColor: descriptionField.touched && descriptionField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
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
                      const current = descriptionField.value.trim();
                      descriptionField.onChange(current ? `${current}\n${draft}` : draft);
                      setDetailDraft('');
                    }}
                    accessibilityLabel="Add event detail"
                  />
                  <AnimatedPressable
                    onPress={() => {
                      const draft = detailDraft.trim();
                      if (!draft) return;
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                      const current = descriptionField.value.trim();
                      descriptionField.onChange(current ? `${current}\n${draft}` : draft);
                      setDetailDraft('');
                    }}
                    style={[styles.detailSendBtn, { backgroundColor: colors.accent }]}
                    accessibilityRole="button"
                    accessibilityLabel="Add detail to description"
                  >
                    <Ionicons name="arrow-up" size={18} color="#fff" />
                  </AnimatedPressable>
                </View>
                {descriptionField.touched && descriptionField.error && <Text style={styles.fieldError}>{descriptionField.error}</Text>}
              </View>
            </View>
          </View>

          {/* ============================================================== */}
          {/*  Section: Ticket Price (meetup/convention only)                 */}
          {/* ============================================================== */}
          {(kind === 'meetup' || kind === 'convention') && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="ticket-outline" size={16} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Ticket Price (optional)</Text>
              </View>

              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>Price in EUR (leave empty for free)</Text>
                <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                  <Text style={{ color: colors.muted, marginRight: 4, fontSize: 16 }}>{'\u20AC'}</Text>
                  <TextInput
                    value={ticketPriceCents}
                    onChangeText={setTicketPriceCents}
                    placeholder="0.00"
                    placeholderTextColor={colors.muted}
                    style={[styles.input, { color: colors.text }]}
                    keyboardType="decimal-pad"
                    accessibilityLabel="Ticket price in euros"
                  />
                </View>
                <Text style={[styles.fieldHint, { color: colors.muted }]}>
                  A 5% platform fee applies to paid tickets.
                </Text>
              </View>
            </View>
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
              <View>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>Image URL</Text>
                <View style={[styles.inputWrap, { borderColor: imageUrlField.touched && imageUrlField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                  <Ionicons name="image-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                  <TextInput
                    value={imageUrlField.value}
                    onChangeText={imageUrlField.onChange}
                    onBlur={imageUrlField.onBlur}
                    placeholder="https://example.com/event-image.jpg"
                    placeholderTextColor={colors.muted}
                    style={[styles.input, { color: colors.text }]}
                    autoCapitalize="none"
                    keyboardType="url"
                    accessibilityLabel="Event image URL"
                  />
                </View>
                {imageUrlField.touched && imageUrlField.error && <Text style={styles.fieldError}>{imageUrlField.error}</Text>}
              </View>
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
                    name={isPublic ? 'globe-outline' : 'lock-closed-outline'}
                    size={20}
                    color={colors.accent}
                  />
                  <View style={styles.toggleTextBlock}>
                    <Text style={[styles.toggleLabel, { color: colors.text }]}>
                      {isPublic ? 'Public' : 'Private'}
                    </Text>
                    <Text style={[styles.toggleHint, { color: colors.muted }]}>
                      {isPublic
                        ? 'Anyone can see and join this event'
                        : 'Only people you invite can see this event'}
                    </Text>
                  </View>
                </View>
                <Switch
                  value={isPublic}
                  onValueChange={setIsPublic}
                  trackColor={{ false: colors.border, true: colors.accent + '60' }}
                  thumbColor={isPublic ? colors.accent : colors.muted}
                  ios_backgroundColor={colors.border}
                  accessibilityLabel={isPublic ? "Event is public" : "Event is private"}
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
                  onValueChange={setSaveAsTemplate}
                  trackColor={{ false: colors.border, true: colors.accent + '60' }}
                  thumbColor={saveAsTemplate ? colors.accent : colors.muted}
                  ios_backgroundColor={colors.border}
                  accessibilityLabel="Save as template"
                />
              </View>
              {saveAsTemplate && (
                <View style={[styles.fieldBlock, { marginTop: 12 }]}>
                  <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                    <Ionicons name="bookmark-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                    <TextInput
                      value={templateName}
                      onChangeText={setTemplateName}
                      placeholder="Template name"
                      placeholderTextColor={colors.muted}
                      style={[styles.input, { color: colors.text }]}
                      accessibilityLabel="Template name"
                    />
                  </View>
                </View>
              )}
            </View>
          </View>

          {/* ============================================================== */}
          {/*  Submit Button                                                  */}
          {/* ============================================================== */}
          <AnimatedPressable
            onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED); handleSubmit(); }}
            disabled={!canSubmit}
            style={[
              styles.submitButton,
              {
                backgroundColor: canSubmit ? colors.accent : colors.border,
              },
            ]}
            accessibilityRole="button"
            accessibilityLabel="Create event"
          >
            {saveState === 'saving' ? (
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

  /* Location row with geo button */
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  locationInput: {
    flex: 1,
  },
  geoButton: {
    width: 44,
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  geoHint: {
    fontSize: 11,
    marginTop: 4,
    marginLeft: 4,
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
    color: '#EF4444',
    marginTop: 4,
    marginLeft: 4,
  },
  fieldHint: {
    fontSize: 12,
    marginTop: 6,
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
