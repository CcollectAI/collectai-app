/**
 * Location / Online URL section for the Create Event form.
 *
 * Renders location input with geolocation button and/or online URL field
 * depending on the selected event format.
 *
 * Extracted from app/create-event.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, TextInput, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

interface FormFieldState {
  value: string;
  error: string | null;
  touched: boolean;
  onChange: (text: string) => void;
  onBlur: () => void;
}

interface EventLocationSectionProps {
  showLocation: boolean;
  showOnlineUrl: boolean;
  location: string;
  onLocationChange: (text: string) => void;
  onUseMyLocation: () => void;
  geoLoading: boolean;
  latitude: number | undefined;
  longitude: number | undefined;
  onlineUrlField: FormFieldState;
}

export const EventLocationSection = React.memo(function EventLocationSection({
  showLocation,
  showOnlineUrl,
  location,
  onLocationChange,
  onUseMyLocation,
  geoLoading,
  latitude,
  longitude,
  onlineUrlField,
}: EventLocationSectionProps) {
  const { colors } = useAppTheme();

  if (!showLocation && !showOnlineUrl) return null;

  return (
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
                  onChangeText={onLocationChange}
                  placeholder="e.g. Amsterdam, Netherlands"
                  placeholderTextColor={colors.muted}
                  style={[styles.input, { color: colors.text }]}
                  accessibilityLabel="Event location"
                  returnKeyType="next"
                />
              </View>
              <AnimatedPressable
                onPress={onUseMyLocation}
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
            <View style={[styles.inputWrap, { borderColor: onlineUrlField.touched && onlineUrlField.error ? colors.danger : colors.border, backgroundColor: colors.background }]}>
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
                returnKeyType="next"
              />
            </View>
            {onlineUrlField.touched && onlineUrlField.error && <Text style={[styles.fieldError, { color: colors.danger }]}>{onlineUrlField.error}</Text>}
          </View>
        )}
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
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
  inputIcon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 0,
  },
  fieldError: {
    fontSize: 12,
    marginTop: 4,
    marginLeft: 4,
  },
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
});
