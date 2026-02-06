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

import React, { useState, useCallback } from 'react';
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
  Switch,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { dataProvider } from '@/data';
import type { EventKind, CreateEventInput } from '@/data/events';
import { CATEGORIES } from '@/constants/categories';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

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

const KIND_ICON: Record<EventKind, keyof typeof Ionicons.glyphMap> = {
  meetup: 'people-outline',
  collection_drop: 'cube-outline',
  stream: 'logo-twitch',
  convention: 'map-outline',
  release: 'rocket-outline',
};

const FORMAT_OPTIONS: { label: string; value: EventFormat; icon: keyof typeof Ionicons.glyphMap }[] = [
  { label: 'In-Person', value: 'in_person', icon: 'location-outline' },
  { label: 'Online', value: 'online', icon: 'globe-outline' },
  { label: 'Hybrid', value: 'hybrid', icon: 'git-merge-outline' },
];

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

const CreateEventScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();

  /* ---- form state ---- */
  const [title, setTitle] = useState('');
  const [kind, setKind] = useState<EventKind>('meetup');
  const [categoryId, setCategoryId] = useState<string | undefined>(undefined);
  const [format, setFormat] = useState<EventFormat>('in_person');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [endDate, setEndDate] = useState('');
  const [location, setLocation] = useState('');
  const [onlineUrl, setOnlineUrl] = useState('');
  const [description, setDescription] = useState('');
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
    title.trim().length > 0 &&
    date.trim().length > 0 &&
    description.trim().length > 0 &&
    saveState !== 'saving';

  /* ---- geolocation handler ---- */
  const handleUseMyLocation = useCallback(async () => {
    setGeoLoading(true);
    try {
      const Location = await import('expo-location');

      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location permission is required to use this feature.');
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
    } catch (err: any) {
      console.warn('[CreateEvent] geolocation error:', err);
      Alert.alert('Location Error', 'Could not retrieve your location. Please enter it manually.');
    } finally {
      setGeoLoading(false);
    }
  }, []);

  /* ---- submit ---- */
  const handleSubmit = async () => {
    if (!canSubmit) return;

    setSaveState('saving');

    try {
      const input: CreateEventInput = {
        title: title.trim(),
        kind,
        date: date.trim(),
        description: description.trim(),
        format,
        isPublic,
        ...(categoryId ? { categoryId } : {}),
        ...(time.trim() ? { time: time.trim() } : {}),
        ...(endDate.trim() ? { endDate: endDate.trim() } : {}),
        ...(location.trim() ? { location: location.trim() } : {}),
        ...(onlineUrl.trim() ? { onlineUrl: onlineUrl.trim() } : {}),
        ...(latitude !== undefined ? { latitude } : {}),
        ...(longitude !== undefined ? { longitude } : {}),
      };

      await dataProvider.createEvent(input);
      router.back();
    } catch (err: any) {
      console.warn('[CreateEvent] error:', err);
      Alert.alert('Error', err?.message || 'Failed to create event. Please try again.');
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
          <AnimatedPressable onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Create Event</Text>
          <View style={{ width: 32 }} />
        </View>

        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
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
                <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                  <Ionicons name="text-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                  <TextInput
                    value={title}
                    onChangeText={setTitle}
                    placeholder="e.g. Rotterdam TCG Meetup"
                    placeholderTextColor={colors.muted}
                    style={[styles.input, { color: colors.text }]}
                  />
                </View>
              </View>

              {/* Kind chips */}
              <View style={styles.fieldBlock}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>Kind</Text>
                <View style={styles.chipRow}>
                  {EVENT_KINDS.map((k) => {
                    const isSelected = kind === k.value;
                    return (
                      <AnimatedPressable
                        key={k.value}
                        style={[
                          styles.chip,
                          {
                            backgroundColor: isSelected ? colors.accent + '20' : colors.background,
                            borderColor: isSelected ? colors.accent : colors.border,
                          },
                        ]}
                        onPress={() => setKind(k.value)}
                      >
                        <Ionicons
                          name={KIND_ICON[k.value]}
                          size={14}
                          color={isSelected ? colors.accent : colors.muted}
                        />
                        <Text
                          style={[
                            styles.chipText,
                            { color: isSelected ? colors.accent : colors.text },
                          ]}
                        >
                          {k.label}
                        </Text>
                      </AnimatedPressable>
                    );
                  })}
                </View>
              </View>

              {/* Category chips */}
              <View style={styles.fieldBlock}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>Category (optional)</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={styles.chipRow}>
                    <AnimatedPressable
                      style={[
                        styles.chip,
                        {
                          backgroundColor: !categoryId ? colors.accent + '20' : colors.background,
                          borderColor: !categoryId ? colors.accent : colors.border,
                        },
                      ]}
                      onPress={() => setCategoryId(undefined)}
                    >
                      <Text
                        style={[
                          styles.chipText,
                          { color: !categoryId ? colors.accent : colors.text },
                        ]}
                      >
                        None
                      </Text>
                    </AnimatedPressable>
                    {CATEGORIES.map((cat) => {
                      const isSelected = categoryId === cat.slug;
                      return (
                        <AnimatedPressable
                          key={cat.slug}
                          style={[
                            styles.chip,
                            {
                              backgroundColor: isSelected ? colors.accent + '20' : colors.background,
                              borderColor: isSelected ? colors.accent : colors.border,
                            },
                          ]}
                          onPress={() => setCategoryId(cat.slug)}
                        >
                          <Text
                            style={[
                              styles.chipText,
                              { color: isSelected ? colors.accent : colors.text },
                            ]}
                          >
                            {cat.name}
                          </Text>
                        </AnimatedPressable>
                      );
                    })}
                  </View>
                </ScrollView>
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
                {FORMAT_OPTIONS.map((opt) => {
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
                      onPress={() => setFormat(opt.value)}
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
                <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                  <Ionicons name="calendar-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                  <TextInput
                    value={date}
                    onChangeText={setDate}
                    placeholder="YYYY-MM-DD"
                    placeholderTextColor={colors.muted}
                    style={[styles.input, { color: colors.text }]}
                  />
                </View>
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
                        />
                      </View>
                      <AnimatedPressable
                        onPress={handleUseMyLocation}
                        disabled={geoLoading}
                        style={[
                          styles.geoButton,
                          {
                            backgroundColor: colors.accent + '15',
                            borderColor: colors.accent + '40',
                          },
                        ]}
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
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      <Ionicons name="link-outline" size={16} color={colors.muted} style={styles.inputIcon} />
                      <TextInput
                        value={onlineUrl}
                        onChangeText={setOnlineUrl}
                        placeholder="https://..."
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                        autoCapitalize="none"
                        keyboardType="url"
                      />
                    </View>
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
                <View style={[styles.inputWrapMultiline, { borderColor: colors.border, backgroundColor: colors.background }]}>
                  <TextInput
                    value={description}
                    onChangeText={setDescription}
                    multiline
                    numberOfLines={4}
                    placeholder="What should attendees know about this event?"
                    placeholderTextColor={colors.muted}
                    style={[styles.inputMultiline, { color: colors.text }]}
                    textAlignVertical="top"
                  />
                </View>
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
                />
              </View>
            </View>
          </View>

          {/* ============================================================== */}
          {/*  Submit Button                                                  */}
          {/* ============================================================== */}
          <AnimatedPressable
            onPress={handleSubmit}
            disabled={!canSubmit}
            style={[
              styles.submitButton,
              {
                backgroundColor: canSubmit ? colors.accent : colors.border,
              },
            ]}
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
});

export default CreateEventScreen;
