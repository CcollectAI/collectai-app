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
  Alert,
  Switch,
  Animated,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams, Stack } from 'expo-router';
import { dataProvider } from '@/data';
import type { EventKind, CreateEventInput, CollectorsEvent } from '@/data/events';
import { CATEGORIES } from '@/constants/categories';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useFormField, validateAll } from '@/hooks/useFormField';
import { compose, required, maxLength, dateYMD, url } from '@/lib/validate';
import { useAuthContext } from '@/providers/useAuthContext';
import CompactSelect from '@/components/CompactSelect';
import logger from '@/utils/logger';
import { useToast } from '@/components/Toast';
import { QuickNavBar } from '@/components/QuickNavBar';

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

  /* ---- geolocation state ---- */
  const [latitude, setLatitude] = useState<number | undefined>(undefined);
  const [longitude, setLongitude] = useState<number | undefined>(undefined);
  const [geoLoading, setGeoLoading] = useState(false);

  const [saveState, setSaveState] = useState<SaveState>('idle');

  /* ---- derived ---- */
  const showLocation = format === 'in_person' || format === 'hybrid';
  const showOnlineUrl = format === 'online' || format === 'hybrid';

  const canSubmit =
    titleField.value.trim().length > 0 &&
    dateField.value.trim().length > 0 &&
    descriptionField.value.trim().length > 0 &&
    !titleField.error && !dateField.error && !descriptionField.error && !onlineUrlField.error && !imageUrlField.error &&
    saveState !== 'saving';

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

        // Pre-populate form fields
        titleField.onChange(evt.title);
        setKind(evt.kind);
        setCategoryId(evt.categoryId ?? undefined);
        setFormat((evt.format as EventFormat) ?? 'in_person');
        dateField.onChange(evt.date);
        setTime(evt.time ?? '');
        setEndDate(evt.endDate ?? '');
        setLocation(evt.location ?? '');
        onlineUrlField.onChange(evt.onlineUrl ?? '');
        imageUrlField.onChange(evt.imageUrl ?? '');
        descriptionField.onChange(evt.description);
        setIsPublic(evt.isPublic ?? true);
        setLatitude(evt.latitude);
        setLongitude(evt.longitude);
      } catch (err: unknown) {
        logger.warn('[EditEvent] load error:', err);
        setAuthError('Failed to load event.');
      } finally {
        setInitialLoading(false);
      }
    })();
  }, [eventId, user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---- geolocation handler ---- */
  const handleUseMyLocation = useCallback(async () => {
    setGeoLoading(true);
    try {
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
      logger.warn('[EditEvent] geolocation error:', err);
      showToast({ message: 'Could not retrieve your location. Please enter it manually.', type: 'error' });
    } finally {
      setGeoLoading(false);
    }
  }, []);

  /* ---- submit ---- */
  const handleSubmit = async () => {
    if (!validateAll(titleField, dateField, descriptionField, onlineUrlField, imageUrlField)) return;
    if (!canSubmit || !eventId) return;

    setSaveState('saving');

    try {
      const patch: Partial<CreateEventInput> = {
        title: titleField.value.trim(),
        kind,
        date: dateField.value.trim(),
        description: descriptionField.value.trim(),
        format,
        isPublic,
        ...(categoryId ? { categoryId } : { categoryId: undefined }),
        ...(time.trim() ? { time: time.trim() } : { time: undefined }),
        ...(endDate.trim() ? { endDate: endDate.trim() } : { endDate: undefined }),
        ...(location.trim() ? { location: location.trim() } : { location: undefined }),
        ...(onlineUrlField.value.trim() ? { onlineUrl: onlineUrlField.value.trim() } : { onlineUrl: undefined }),
        ...(imageUrlField.value.trim() ? { imageUrl: imageUrlField.value.trim() } : { imageUrl: undefined }),
        ...(latitude !== undefined ? { latitude } : {}),
        ...(longitude !== undefined ? { longitude } : {}),
      };

      await dataProvider.updateEvent(eventId, patch);
      router.back();
    } catch (err: unknown) {
      logger.warn('[EditEvent] error:', err);
      showToast({ message: (err as Error)?.message || 'Failed to update event. Please try again.', type: 'error' });
    } finally {
      setSaveState('idle');
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
          <Ionicons name="alert-circle-outline" size={48} color="#EF4444" />
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
                <View style={[styles.inputWrapMultiline, { borderColor: descriptionField.touched && descriptionField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
                  <TextInput
                    value={descriptionField.value}
                    onChangeText={descriptionField.onChange}
                    onBlur={descriptionField.onBlur}
                    multiline
                    numberOfLines={4}
                    placeholder="What should attendees know about this event?"
                    placeholderTextColor={colors.muted}
                    style={[styles.inputMultiline, { color: colors.text }]}
                    textAlignVertical="top"
                    accessibilityLabel="Event description"
                  />
                </View>
                {descriptionField.touched && descriptionField.error && <Text style={styles.fieldError}>{descriptionField.error}</Text>}
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
          {/*  Save Changes Button                                            */}
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
            accessibilityLabel="Save changes"
          >
            {saveState === 'saving' ? (
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
              <Ionicons name="warning-outline" size={16} color="#EF4444" />
              <Text style={[styles.sectionTitle, { color: '#EF4444' }]}>Danger Zone</Text>
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: '#EF444430' }]}>
              <Text style={[styles.dangerHint, { color: colors.muted }]}>
                Cancelling this event is permanent. All attendees will be notified.
              </Text>
              <AnimatedPressable
                onPress={handleCancelEvent}
                style={styles.cancelEventButton}
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
    backgroundColor: '#EF4444',
  },
  cancelEventButtonText: {
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

export default function EditEventScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Edit Event">
      <EditEventScreen />
    </ScreenErrorBoundary>
  );
}
