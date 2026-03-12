/**
 * Ticket price section for the Create Event form.
 *
 * Only visible for meetup/convention event kinds.
 *
 * Extracted from app/create-event.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, TextInput, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

interface EventTicketingSectionProps {
  ticketPriceCents: string;
  onTicketPriceChange: (value: string) => void;
}

export const EventTicketingSection = React.memo(function EventTicketingSection({
  ticketPriceCents,
  onTicketPriceChange,
}: EventTicketingSectionProps) {
  const { colors } = useAppTheme();

  return (
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
            onChangeText={onTicketPriceChange}
            placeholder="0.00"
            placeholderTextColor={colors.muted}
            style={[styles.input, { color: colors.text }]}
            keyboardType="decimal-pad"
            accessibilityLabel="Ticket price in euros"
            returnKeyType="done"
          />
        </View>
        <Text style={[styles.fieldHint, { color: colors.muted }]}>
          A 5% platform fee applies to paid tickets.
        </Text>
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
  input: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 0,
  },
  fieldHint: {
    fontSize: 12,
    marginTop: 6,
    marginLeft: 4,
  },
});
