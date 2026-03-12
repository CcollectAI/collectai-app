/**
 * ProvenanceTimeline Component
 * Displays a vertical timeline of provenance events with authenticity signals.
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { timeAgo } from '@/lib/timeAgo';

type ProvenanceEvent = {
  id: string;
  eventType: string;
  timestamp: string;
  note: string | null;
  source: string | null;
  metadata: Record<string, unknown>;
};

type ProvenanceTimelineProps = {
  events: ProvenanceEvent[];
  authenticitySignals: string[];
  loading?: boolean;
};

const EVENT_TYPE_CONFIG: Record<string, { icon: keyof typeof Ionicons.glyphMap; label: string }> = {
  added: { icon: 'add-circle-outline', label: 'Added to Collection' },
  transferred_in: { icon: 'arrow-down-circle-outline', label: 'Transferred In' },
  transferred_out: { icon: 'arrow-up-circle-outline', label: 'Transferred Out' },
  sale: { icon: 'cash-outline', label: 'Sale Recorded' },
  purchase: { icon: 'cart-outline', label: 'Purchase Recorded' },
  graded: { icon: 'ribbon-outline', label: 'Professional Grading' },
  verified: { icon: 'shield-checkmark-outline', label: 'Verified' },
  updated: { icon: 'pencil-outline', label: 'Updated' },
};

const SOURCE_LABELS: Record<string, string> = {
  manual: 'manual entry',
  receipt: 'via receipt',
  marketplace: 'via marketplace',
  ocr: 'via OCR',
  barcode: 'via barcode',
  import: 'via import',
  admin: 'by admin',
};

const SIGNAL_LABELS: Record<string, string> = {
  owner_verified: 'Owner Verified',
  professionally_graded: 'Professionally Graded',
  receipt_on_file: 'Receipt on File',
};

function formatRelativeTime(timestamp: string): string {
  return timeAgo(timestamp);
}

function getSignalLabel(signal: string): string {
  return SIGNAL_LABELS[signal] || signal.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function getSourceLabel(source: string | null): string | null {
  if (!source) return null;
  return SOURCE_LABELS[source] || source;
}

function getEventConfig(eventType: string) {
  return EVENT_TYPE_CONFIG[eventType] || {
    icon: 'ellipse-outline' as keyof typeof Ionicons.glyphMap,
    label: eventType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
  };
}

export function ProvenanceTimeline({
  events,
  authenticitySignals,
  loading = false,
}: ProvenanceTimelineProps) {
  const { colors } = useAppTheme();

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="small" color={colors.accent} />
        <Text style={[styles.loadingText, { color: colors.muted }]}>
          Loading history...
        </Text>
      </View>
    );
  }

  if (events.length === 0 && authenticitySignals.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="document-text-outline" size={28} color={colors.muted} />
        <Text style={[styles.emptyText, { color: colors.muted }]}>
          No history yet
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Authenticity Signals */}
      {authenticitySignals.length > 0 && (
        <View style={styles.signalsRow}>
          {authenticitySignals.map((signal) => (
            <View
              key={signal}
              style={[styles.signalBadge, { backgroundColor: colors.success + '18' }]}
            >
              <Ionicons name="shield-checkmark" size={12} color={colors.success} />
              <Text style={[styles.signalText, { color: colors.success }]}>
                {getSignalLabel(signal)}
              </Text>
            </View>
          ))}
        </View>
      )}

      {/* Timeline Events */}
      {events.length > 0 && (
        <View style={styles.timeline}>
          {events.map((event, index) => {
            const config = getEventConfig(event.eventType);
            const isLast = index === events.length - 1;
            const sourceLabel = getSourceLabel(event.source);

            return (
              <View key={event.id} style={styles.timelineItem}>
                {/* Timeline line + dot */}
                <View style={styles.timelineLeft}>
                  <View
                    style={[
                      styles.timelineDot,
                      { backgroundColor: colors.accent, borderColor: colors.accent + '30' },
                    ]}
                  >
                    <Ionicons name={config.icon} size={14} color="#FFFFFF" />
                  </View>
                  {!isLast && (
                    <View
                      style={[styles.timelineLine, { backgroundColor: colors.border }]}
                    />
                  )}
                </View>

                {/* Event content */}
                <View style={[styles.timelineContent, isLast && styles.timelineContentLast]}>
                  <View style={styles.eventHeader}>
                    <Text style={[styles.eventLabel, { color: colors.text }]}>
                      {config.label}
                    </Text>
                    <Text style={[styles.eventTime, { color: colors.muted }]}>
                      {formatRelativeTime(event.timestamp)}
                    </Text>
                  </View>

                  {event.note && (
                    <Text style={[styles.eventNote, { color: colors.muted }]}>
                      {event.note}
                    </Text>
                  )}

                  {sourceLabel && (
                    <View
                      style={[
                        styles.sourceBadge,
                        { backgroundColor: colors.border },
                      ]}
                    >
                      <Text style={[styles.sourceText, { color: colors.muted }]}>
                        {sourceLabel}
                      </Text>
                    </View>
                  )}
                </View>
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 12,
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 20,
    gap: 8,
  },
  loadingText: {
    fontSize: 13,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 24,
    gap: 8,
  },
  emptyText: {
    fontSize: 13,
  },
  signalsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 4,
  },
  signalBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    gap: 5,
  },
  signalText: {
    fontSize: 12,
    fontWeight: '600',
  },
  timeline: {
    paddingTop: 4,
  },
  timelineItem: {
    flexDirection: 'row',
  },
  timelineLeft: {
    width: 32,
    alignItems: 'center',
  },
  timelineDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 3,
    alignItems: 'center',
    justifyContent: 'center',
  },
  timelineLine: {
    width: 2,
    flex: 1,
    marginVertical: 2,
  },
  timelineContent: {
    flex: 1,
    paddingLeft: 10,
    paddingBottom: 20,
  },
  timelineContentLast: {
    paddingBottom: 4,
  },
  eventHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  eventLabel: {
    fontSize: 14,
    fontWeight: '600',
  },
  eventTime: {
    fontSize: 11,
  },
  eventNote: {
    fontSize: 13,
    lineHeight: 18,
    marginTop: 4,
  },
  sourceBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    marginTop: 6,
  },
  sourceText: {
    fontSize: 11,
    fontWeight: '500',
  },
});

export default ProvenanceTimeline;
