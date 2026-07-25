/**
 * useEventForm — shared hook for event form state, validation, and submission.
 * Used by both create-event.tsx and edit-event.tsx to eliminate duplicated
 * form state management (~15 useState calls, validation, geolocation, submit).
 */

import { useState, useCallback, useEffect } from 'react';
import { useFormField, validateAll, type FormField } from '@/hooks/useFormField';
import { compose, required, maxLength, dateYMD, url } from '@/lib/validate';
import { useToast } from '@/components/Toast';
import { fireHaptic, HapticIntent } from '@/haptics';
import logger from '@/utils/logger';
import type { EventKind, CreateEventInput, CollectorsEvent } from '@/data/events';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type EventFormat = 'in_person' | 'online' | 'hybrid';
type SaveState = 'idle' | 'saving';

export type EventFormState = {
  // Validated fields
  titleField: FormField;
  dateField: FormField;
  descriptionField: FormField;
  onlineUrlField: FormField;
  imageUrlField: FormField;
  // Simple state
  kind: EventKind;
  setKind: (k: EventKind) => void;
  categoryId: string | undefined;
  setCategoryId: (id: string | undefined) => void;
  format: EventFormat;
  setFormat: (f: EventFormat) => void;
  time: string;
  setTime: (t: string) => void;
  endDate: string;
  setEndDate: (d: string) => void;
  location: string;
  setLocation: (l: string) => void;
  isPublic: boolean;
  setIsPublic: (v: boolean) => void;
  ticketPriceCents: string;
  setTicketPriceCents: (v: string) => void;
  // Geolocation
  latitude: number | undefined;
  longitude: number | undefined;
  geoLoading: boolean;
  handleUseMyLocation: () => Promise<void>;
  clearCoordinates: () => void;
  // Derived
  showLocation: boolean;
  showOnlineUrl: boolean;
  canSubmit: boolean;
  saveState: SaveState;
};

export type UseEventFormOptions = {
  /** For edit mode: pre-populate from existing event */
  initialEvent?: CollectorsEvent | null;
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useEventForm(options?: UseEventFormOptions): EventFormState {
  const { showToast } = useToast();
  const initialEvent = options?.initialEvent;

  // Validated fields
  const titleField = useFormField(compose(required('Title'), maxLength('Title', 255)));
  const dateField = useFormField(compose(required('Date'), dateYMD('Date')));
  const descriptionField = useFormField(
    compose(required('Description'), maxLength('Description', 2000)),
  );
  const onlineUrlField = useFormField(url('Online URL'));
  const imageUrlField = useFormField(url('Image URL'));

  // Simple state
  const [kind, setKind] = useState<EventKind>('meetup');
  const [categoryId, setCategoryId] = useState<string | undefined>(undefined);
  const [format, setFormat] = useState<EventFormat>('in_person');
  const [time, setTime] = useState('');
  const [endDate, setEndDate] = useState('');
  const [location, setLocation] = useState('');
  const [isPublic, setIsPublic] = useState(true);
  const [ticketPriceCents, setTicketPriceCents] = useState('');

  // Geolocation
  const [latitude, setLatitude] = useState<number | undefined>(undefined);
  const [longitude, setLongitude] = useState<number | undefined>(undefined);
  const [geoLoading, setGeoLoading] = useState(false);

  const [saveState, setSaveState] = useState<SaveState>('idle');

  // Pre-populate from existing event (edit mode)
  useEffect(() => {
    if (!initialEvent) return;
    titleField.onChange(initialEvent.title);
    setKind(initialEvent.kind);
    setCategoryId(initialEvent.categoryId ?? undefined);
    setFormat((initialEvent.format as EventFormat) ?? 'in_person');
    dateField.onChange(initialEvent.date);
    setTime(initialEvent.time ?? '');
    setEndDate(initialEvent.endDate ?? '');
    setLocation(initialEvent.location ?? '');
    onlineUrlField.onChange(initialEvent.onlineUrl ?? '');
    imageUrlField.onChange(initialEvent.imageUrl ?? '');
    descriptionField.onChange(initialEvent.description);
    setIsPublic(initialEvent.isPublic ?? true);
    setLatitude(initialEvent.latitude);
    setLongitude(initialEvent.longitude);
  }, [initialEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  // Derived
  const showLocation = format === 'in_person' || format === 'hybrid';
  const showOnlineUrl = format === 'online' || format === 'hybrid';

  const canSubmit =
    titleField.value.trim().length > 0 &&
    dateField.value.trim().length > 0 &&
    descriptionField.value.trim().length > 0 &&
    !titleField.error &&
    !dateField.error &&
    !descriptionField.error &&
    !onlineUrlField.error &&
    !imageUrlField.error &&
    saveState !== 'saving';

  // Geolocation handler
  const handleUseMyLocation = useCallback(async () => {
    setGeoLoading(true);
    try {
      const Location = await import('expo-location');

      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        showToast({
          message: 'Location permission is required to use this feature.',
          type: 'warning',
        });
        return;
      }

      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
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
      logger.error('[useEventForm] geolocation error:', err);
      showToast({
        message: 'Could not retrieve your location. Please enter it manually.',
        type: 'error',
      });
    } finally {
      setGeoLoading(false);
    }
  }, [showToast]);

  const clearCoordinates = useCallback(() => {
    setLatitude(undefined);
    setLongitude(undefined);
  }, []);

  return {
    titleField,
    dateField,
    descriptionField,
    onlineUrlField,
    imageUrlField,
    kind,
    setKind,
    categoryId,
    setCategoryId,
    format,
    setFormat,
    time,
    setTime,
    endDate,
    setEndDate,
    location,
    setLocation,
    isPublic,
    setIsPublic,
    ticketPriceCents,
    setTicketPriceCents,
    latitude,
    longitude,
    geoLoading,
    handleUseMyLocation,
    clearCoordinates,
    showLocation,
    showOnlineUrl,
    canSubmit,
    saveState,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Validate all form fields. Returns true if all are valid. */
export function validateEventForm(form: EventFormState): boolean {
  return validateAll(
    form.titleField,
    form.dateField,
    form.descriptionField,
    form.onlineUrlField,
    form.imageUrlField,
  );
}

/** Build a CreateEventInput from the current form state. */
export function buildEventInput(
  form: EventFormState,
  extras?: Partial<CreateEventInput>,
): CreateEventInput {
  return {
    title: form.titleField.value.trim(),
    kind: form.kind,
    date: form.dateField.value.trim(),
    description: form.descriptionField.value.trim(),
    format: form.format,
    isPublic: form.isPublic,
    ...(form.categoryId ? { categoryId: form.categoryId } : {}),
    ...(form.time.trim() ? { time: form.time.trim() } : {}),
    ...(form.endDate.trim() ? { endDate: form.endDate.trim() } : {}),
    ...(form.location.trim() ? { location: form.location.trim() } : {}),
    ...(form.onlineUrlField.value.trim()
      ? { onlineUrl: form.onlineUrlField.value.trim() }
      : {}),
    ...(form.imageUrlField.value.trim()
      ? { imageUrl: form.imageUrlField.value.trim() }
      : {}),
    ...(form.latitude !== undefined ? { latitude: form.latitude } : {}),
    ...(form.longitude !== undefined ? { longitude: form.longitude } : {}),
    ...(form.ticketPriceCents.trim()
      ? { ticketPriceCents: Math.round(parseFloat(form.ticketPriceCents) * 100) }
      : {}),
    ...extras,
  };
}
