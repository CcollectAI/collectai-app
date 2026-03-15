/**
 * MutationQueuePanel — Displays queued offline mutations with retry/clear controls.
 *
 * Shown in Settings when there are pending mutations waiting to be replayed.
 */

import React from 'react';
import { View, Text, StyleSheet, FlatList } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import type { QueuedMutation, MutationType } from '@/lib/mutationQueue';

// ── Types ────────────────────────────────────────────────────────────────────

type ThemeColors = {
  background: string;
  text: string;
  muted: string;
  border: string;
  card: string;
  accent: string;
  warning: string;
  danger: string;
};

type MutationQueuePanelProps = {
  colors: ThemeColors;
  mutations: QueuedMutation[];
  onRetry: (id: string) => void;
  onRetryAll: () => void;
  onClear: () => void;
};

// ── Helpers ──────────────────────────────────────────────────────────────────

const MUTATION_ICONS: Record<MutationType, keyof typeof Ionicons.glyphMap> = {
  createItem: 'add-circle-outline',
  updateItem: 'create-outline',
  deleteItem: 'trash-outline',
  rsvpEvent: 'calendar-outline',
  sendMessage: 'chatbubble-outline',
  addWatchlistItem: 'eye-outline',
  removeWatchlistItem: 'eye-off-outline',
  createEvent: 'calendar-outline',
  updateWatchlistItem: 'eye-outline',
  createBuildPaintProject: 'color-palette-outline',
};

const MUTATION_LABELS: Record<MutationType, string> = {
  createItem: 'Create item',
  updateItem: 'Update item',
  deleteItem: 'Delete item',
  rsvpEvent: 'RSVP event',
  sendMessage: 'Send message',
  addWatchlistItem: 'Add to watchlist',
  removeWatchlistItem: 'Remove from watchlist',
  createEvent: 'Create event',
  updateWatchlistItem: 'Update watchlist item',
  createBuildPaintProject: 'Create build project',
};

function previewText(mutation: QueuedMutation): string {
  const label = MUTATION_LABELS[mutation.type] ?? mutation.type;
  const firstArg = mutation.args[0];
  const id =
    typeof firstArg === 'string'
      ? firstArg.slice(0, 8)
      : typeof firstArg === 'object' && firstArg !== null && 'title' in (firstArg as Record<string, unknown>)
        ? String((firstArg as Record<string, unknown>).title).slice(0, 24)
        : '';
  return id ? `${label}: ${id}...` : label;
}

// ── Component ────────────────────────────────────────────────────────────────

function MutationQueuePanelInner({
  colors,
  mutations,
  onRetry,
  onRetryAll,
  onClear,
}: MutationQueuePanelProps) {
  if (mutations.length === 0) return null;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="cloud-upload-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>
          Pending Changes ({mutations.length})
        </Text>
      </View>

      <FlatList
        data={mutations}
        keyExtractor={(item) => item.id}
        scrollEnabled={false}
        renderItem={({ item }) => (
          <View style={[styles.row, { borderBottomColor: colors.border }]}>
            <Ionicons
              name={MUTATION_ICONS[item.type] ?? 'ellipse-outline'}
              size={18}
              color={colors.muted}
            />
            <View style={styles.rowInfo}>
              <Text style={[styles.rowText, { color: colors.text }]} numberOfLines={1}>
                {previewText(item)}
              </Text>
              {item.retries > 0 && (
                <Text style={[styles.retryBadge, { color: colors.warning }]}>
                  Retry {item.retries}/3
                </Text>
              )}
            </View>
            <AnimatedPressable
              onPress={() => onRetry(item.id)}
              style={styles.retryBtn}
              accessibilityRole="button"
              accessibilityLabel={`Retry ${MUTATION_LABELS[item.type] ?? item.type}`}
            >
              <Ionicons name="refresh-outline" size={16} color={colors.accent} />
            </AnimatedPressable>
          </View>
        )}
      />

      <View style={styles.actions}>
        <AnimatedPressable
          onPress={onRetryAll}
          style={[styles.actionBtn, { backgroundColor: colors.accent + '20' }]}
          accessibilityRole="button"
          accessibilityLabel="Retry all pending changes"
        >
          <Ionicons name="refresh" size={14} color={colors.accent} />
          <Text style={[styles.actionText, { color: colors.accent }]}>Retry All</Text>
        </AnimatedPressable>

        <AnimatedPressable
          onPress={onClear}
          style={[styles.actionBtn, { backgroundColor: colors.danger + '15' }]}
          accessibilityRole="button"
          accessibilityLabel="Clear all pending changes"
        >
          <Ionicons name="close-circle-outline" size={14} color={colors.danger} />
          <Text style={[styles.actionText, { color: colors.danger }]}>Clear</Text>
        </AnimatedPressable>
      </View>
    </View>
  );
}

export const MutationQueuePanel = React.memo(MutationQueuePanelInner);

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 10,
  },
  rowInfo: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  rowText: {
    fontSize: 14,
    fontWeight: '500',
    flexShrink: 1,
  },
  retryBadge: {
    fontSize: 11,
    fontWeight: '600',
  },
  retryBtn: {
    padding: 6,
  },
  actions: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 12,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  actionText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
