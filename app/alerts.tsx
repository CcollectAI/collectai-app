/**
 * Alerts Feed — Shows trigger history and alert rules.
 * Route: /alerts
 *
 * Two tabs:
 *   "Recent"  — entries from alert_trigger_history (when alerts actually fired)
 *   "Rules"   — configured alert rules from v_alerts_feed_v1 / user_price_alerts
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  Linking,
  RefreshControl,
} from 'react-native';
import { useRouter, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type AlertFeedItem } from '@/data';
import { collectorsApi } from '@/api/collectorsApi';
import { useAppTheme } from '@/hooks/useAppTheme';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { AnimatedPressable } from '@/motion';
import { SkeletonList } from '@/components/Skeleton';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import logger from '@/utils/logger';
import { QuickNavBar } from '@/components/QuickNavBar';
import { useAsync } from '@/hooks/useAsync';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TriggerHistoryItem = {
  id: string;
  alertId: string | null;
  itemId: string | null;
  triggerType: string;
  triggerValue: Record<string, unknown>;
  message: string;
  read: boolean;
  createdAt: string;
};

type ActiveTab = 'triggers' | 'rules';

// ---------------------------------------------------------------------------
// Constants — badge colours & icons
// ---------------------------------------------------------------------------

const TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  price_drop: { bg: '#16653420', text: '#166534' },
  price_spike: { bg: '#92400e20', text: '#92400e' },
  below_threshold: { bg: '#16653420', text: '#166534' },
  restock: { bg: '#1e40af20', text: '#1e40af' },
  drop_detected: { bg: '#6b21a820', text: '#6b21a8' },
  completeness: { bg: '#0369a120', text: '#0369a1' },
  rarity: { bg: '#9d174d20', text: '#9d174d' },
};

const TYPE_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  price_drop: 'trending-down',
  price_spike: 'trending-up',
  below_threshold: 'trending-down',
  restock: 'cube-outline',
  drop_detected: 'flash-outline',
  completeness: 'checkmark-circle-outline',
  rarity: 'diamond-outline',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function AlertsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const [activeTab, setActiveTab] = useState<ActiveTab>('triggers');
  const [refreshing, setRefreshing] = useState(false);

  // -----------------------------------------------------------------------
  // Paginated alert rules via usePaginatedList
  // -----------------------------------------------------------------------

  const alertsFetcher = useCallback(
    async (limit: number, offset: number): Promise<AlertFeedItem[]> => {
      return dataProvider.listAlertsFeed({ limit, offset });
    },
    [],
  );

  const {
    items: alerts,
    isLoading: alertsLoading,
    isLoadingMore: alertsLoadingMore,
    hasMore: alertsHasMore,
    error: alertsError,
    loadMore: alertsLoadMore,
    refresh: alertsRefresh,
  } = usePaginatedList<AlertFeedItem>(alertsFetcher, { pageSize: 20 });

  // -----------------------------------------------------------------------
  // Trigger history loading (not paginated — comes from API endpoint)
  // -----------------------------------------------------------------------

  const { data: triggersData, loading: triggersLoading, error: triggersError, retry: loadTriggers } = useAsync(
    async () => {
      const historyData = await collectorsApi
        .getAlertTriggerHistory()
        .catch((err) => {
          logger.warn('[Alerts] Failed to load triggers', err);
          return { triggers: [] as Array<{ id: string; alert_id: string | null; item_id: string | null; trigger_type: string; trigger_value: Record<string, unknown>; message: string; read: boolean; created_at: string }>, unread_count: 0 };
        });
      return {
        triggers: historyData.triggers.map((t) => ({
          id: t.id,
          alertId: t.alert_id,
          itemId: t.item_id,
          triggerType: t.trigger_type,
          triggerValue: t.trigger_value,
          message: t.message,
          read: t.read,
          createdAt: t.created_at,
        })),
        unreadCount: historyData.unread_count,
      };
    },
    [],
  );

  // Local state for optimistic updates on mark-as-read
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const baseTriggers = triggersData?.triggers ?? [];
  const triggerHistory = baseTriggers.map((t) =>
    readIds.has(t.id) ? { ...t, read: true } : t,
  );
  const baseUnreadCount = triggersData?.unreadCount ?? 0;
  const unreadCount = Math.max(0, baseUnreadCount - readIds.size);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    setReadIds(new Set());
    await Promise.all([
      (async () => { loadTriggers(); })(),
      alertsRefresh(),
    ]);
    setRefreshing(false);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
  }, [loadTriggers, alertsRefresh, settings.hapticsEnabled]);

  // Combined loading state for initial render
  const loading = triggersLoading && alertsLoading;
  const error = activeTab === 'triggers' ? triggersError : alertsError;

  // -----------------------------------------------------------------------
  // Mark a trigger as read
  // -----------------------------------------------------------------------

  const handleMarkRead = useCallback(
    async (triggerId: string) => {
      // Optimistic update via local read tracking
      setReadIds((prev) => new Set(prev).add(triggerId));
      try {
        await collectorsApi.markTriggerRead(triggerId);
      } catch {
        // Revert on failure — reload from server
        setReadIds(new Set());
        loadTriggers();
      }
    },
    [loadTriggers],
  );

  // -----------------------------------------------------------------------
  // FlatList footer: loading-more spinner
  // -----------------------------------------------------------------------

  const renderAlertsFooter = useCallback(() => {
    if (!alertsLoadingMore) return null;
    return (
      <View style={styles.loadingMoreContainer}>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }, [alertsLoadingMore, colors.accent]);

  // -----------------------------------------------------------------------
  // Render: trigger history card
  // -----------------------------------------------------------------------

  const renderTrigger = ({ item }: { item: TriggerHistoryItem }) => {
    const typeColor =
      TYPE_COLORS[item.triggerType] || { bg: '#47556920', text: '#475569' };
    const typeIcon: keyof typeof Ionicons.glyphMap =
      TYPE_ICONS[item.triggerType] || 'notifications-outline';
    const typeLabel = item.triggerType
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());

    return (
      <AnimatedPressable
        onPress={() => {
          if (!item.read) handleMarkRead(item.id);
        }}
        accessibilityRole="button"
        accessibilityLabel={`${item.read ? '' : 'Unread '}alert: ${item.message}`}
      >
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          {/* Unread dot + type badge row */}
          <View style={styles.triggerBadgeRow}>
            {!item.read && <View style={[styles.unreadDot, { backgroundColor: colors.accent }]} />}
            <View style={[styles.typeBadge, { backgroundColor: typeColor.bg }]}>
              <Ionicons name={typeIcon} size={12} color={typeColor.text} />
              <Text style={[styles.typeBadgeText, { color: typeColor.text }]}>
                {typeLabel}
              </Text>
            </View>
          </View>

          {/* Message body */}
          <Text
            style={[
              styles.cardBody,
              { color: colors.text },
              !item.read && styles.unreadText,
            ]}
            numberOfLines={3}
          >
            {item.message}
          </Text>

          {/* Timestamp */}
          <Text style={[styles.cardTime, { color: colors.muted }]}>
            {formatRelativeTime(item.createdAt)}
          </Text>

          {/* View Listing / View Item link */}
          {(typeof item.triggerValue?.listing_url === 'string' || typeof item.triggerValue?.affiliate_url === 'string') ? (
            <AnimatedPressable
              onPress={() => {
                handleMarkRead(item.id);
                const url = String(item.triggerValue.affiliate_url || item.triggerValue.listing_url);
                Linking.openURL(url).catch(() => {});
              }}
              style={[styles.viewListingBtn, { borderColor: colors.accent + '40' }]}
              accessibilityRole="link"
              accessibilityLabel={`View on ${String(item.triggerValue.listing_source || 'Marketplace')}`}
            >
              <Ionicons name="open-outline" size={13} color={colors.accent} />
              <Text style={[styles.viewListingText, { color: colors.accent }]}>
                View on {String(item.triggerValue.listing_source || 'Marketplace')}
                {typeof item.triggerValue.listing_price === 'number' ? ` · ${formatPrice(item.triggerValue.listing_price)}` : ''}
              </Text>
            </AnimatedPressable>
          ) : item.itemId ? (
            <AnimatedPressable
              onPress={() => {
                handleMarkRead(item.id);
                router.push(`/item/${item.itemId}` as never);
              }}
              style={[styles.viewListingBtn, { borderColor: colors.accent + '40' }]}
              accessibilityRole="link"
              accessibilityLabel="View item details"
            >
              <Ionicons name="eye-outline" size={13} color={colors.accent} />
              <Text style={[styles.viewListingText, { color: colors.accent }]}>View Item</Text>
            </AnimatedPressable>
          ) : null}
        </View>
      </AnimatedPressable>
    );
  };

  // -----------------------------------------------------------------------
  // Render: existing alert-rule card (unchanged logic)
  // -----------------------------------------------------------------------

  const renderAlert = ({ item }: { item: AlertFeedItem }) => {
    const typeColor = TYPE_COLORS[item.type] || { bg: '#47556920', text: '#475569' };
    const typeIcon: keyof typeof Ionicons.glyphMap =
      TYPE_ICONS[item.type] || 'notifications-outline';
    const typeLabel = item.type
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());

    return (
      <View
        style={[
          styles.card,
          { backgroundColor: colors.card, borderColor: colors.border },
        ]}
      >
        {/* Type badge */}
        <View style={[styles.typeBadge, { backgroundColor: typeColor.bg }]}>
          <Ionicons name={typeIcon} size={12} color={typeColor.text} />
          <Text style={[styles.typeBadgeText, { color: typeColor.text }]}>
            {typeLabel}
          </Text>
        </View>

        {/* Content */}
        <Text
          style={[styles.cardTitle, { color: colors.text }]}
          numberOfLines={2}
        >
          {item.title}
        </Text>
        {item.body && (
          <Text
            style={[styles.cardBody, { color: colors.muted }]}
            numberOfLines={3}
          >
            {item.body}
          </Text>
        )}

        {/* Timestamp */}
        <Text style={[styles.cardTime, { color: colors.muted }]}>
          {formatRelativeTime(item.createdAt)}
        </Text>
      </View>
    );
  };

  // -----------------------------------------------------------------------
  // Shared header (used in loading + main states)
  // -----------------------------------------------------------------------

  // Header title is handled by Stack header from _layout.tsx

  // -----------------------------------------------------------------------
  // Tab bar
  // -----------------------------------------------------------------------

  const renderTabBar = () => (
    <View
      style={[
        styles.tabBar,
        { backgroundColor: colors.card, borderBottomColor: colors.border },
      ]}
    >
      <AnimatedPressable
        onPress={() => setActiveTab('triggers')}
        style={[
          styles.tab,
          activeTab === 'triggers' && [
            styles.tabActive,
            { borderBottomColor: colors.accent },
          ],
        ]}
        accessibilityRole="tab"
        accessibilityLabel="Recent triggers tab"
        accessibilityState={{ selected: activeTab === 'triggers' }}
      >
        <Text
          style={[
            styles.tabText,
            { color: activeTab === 'triggers' ? colors.accent : colors.muted },
          ]}
        >
          Recent
        </Text>
        {unreadCount > 0 && (
          <View style={[styles.badge, { backgroundColor: colors.accent }]}>
            <Text style={styles.badgeText}>
              {unreadCount > 99 ? '99+' : unreadCount}
            </Text>
          </View>
        )}
      </AnimatedPressable>

      <AnimatedPressable
        onPress={() => setActiveTab('rules')}
        style={[
          styles.tab,
          activeTab === 'rules' && [
            styles.tabActive,
            { borderBottomColor: colors.accent },
          ],
        ]}
        accessibilityRole="tab"
        accessibilityLabel="Alert rules tab"
        accessibilityState={{ selected: activeTab === 'rules' }}
      >
        <Text
          style={[
            styles.tabText,
            { color: activeTab === 'rules' ? colors.accent : colors.muted },
          ]}
        >
          Rules
        </Text>
      </AnimatedPressable>
    </View>
  );

  // -----------------------------------------------------------------------
  // Loading state
  // -----------------------------------------------------------------------

  if (loading) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <Stack.Screen options={{ headerTitle: 'Alerts' }} />
        <View style={styles.loadingContainer}>
          <SkeletonList count={5} type="row" />
        </View>
      </View>
    );
  }

  // -----------------------------------------------------------------------
  // Main render
  // -----------------------------------------------------------------------

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: 'Alerts' }} />
      {renderTabBar()}

      {error ? (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
          <Text style={[styles.errorText, { color: colors.text }]}>Error</Text>
          <Text style={[styles.errorMessage, { color: colors.muted }]}>
            {error}
          </Text>
          <AnimatedPressable
            style={[styles.retryBtn, { backgroundColor: colors.accent }]}
            onPress={handleRefresh}
            accessibilityRole="button"
            accessibilityLabel="Retry loading alerts"
          >
            <Text style={styles.retryBtnText}>Retry</Text>
          </AnimatedPressable>
        </View>
      ) : activeTab === 'triggers' ? (
        <FlatList
          data={triggerHistory}
          keyExtractor={(item) => item.id}
          renderItem={renderTrigger}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons
                name="notifications-outline"
                size={48}
                color={colors.muted}
              />
              <Text style={[styles.emptyText, { color: colors.muted }]}>
                No triggered alerts yet
              </Text>
              <Text style={[styles.emptySubtext, { color: colors.muted }]}>
                When your price alerts fire, they will appear here.
              </Text>
              <View style={styles.emptyCtaContainer}>
                <AnimatedPressable
                  onPress={() => router.push('/watchlist-builder')}
                  style={[styles.emptyCtaBtn, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Create an alert"
                >
                  <Text style={styles.emptyCtaBtnText}>Create an Alert</Text>
                </AnimatedPressable>
              </View>
            </View>
          }
        />
      ) : (
        <FlatList
          data={alerts}
          keyExtractor={(item) => item.id}
          renderItem={renderAlert}
          contentContainerStyle={styles.list}
          onEndReached={alertsLoadMore}
          onEndReachedThreshold={0.5}
          ListFooterComponent={renderAlertsFooter}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons
                name="notifications-outline"
                size={48}
                color={colors.muted}
              />
              <Text style={[styles.emptyText, { color: colors.muted }]}>
                No alert rules yet
              </Text>
              <Text style={[styles.emptySubtext, { color: colors.muted }]}>
                Add items to your watchlist to get price and restock alerts.
              </Text>
              <View style={styles.emptyCtaContainer}>
                <AnimatedPressable
                  onPress={() => router.push('/watchlist-builder')}
                  style={[styles.emptyCtaBtn, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Create an alert"
                >
                  <Text style={styles.emptyCtaBtnText}>Create an Alert</Text>
                </AnimatedPressable>
              </View>
            </View>
          }
        />
      )}
      <QuickNavBar />
    </View>
  );
}

export default function AlertsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Alerts">
      <AlertsScreen />
    </ScreenErrorBoundary>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    flex: 1,
    textAlign: 'center',
    marginHorizontal: 8,
  },

  // Tab bar
  tabBar: {
    flexDirection: 'row',
    borderBottomWidth: 1,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    gap: 6,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomWidth: 2,
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
  },
  badge: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 5,
  },
  badgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '700',
  },

  // Lists
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  list: {
    padding: 16,
    gap: 12,
  },
  loadingMoreContainer: {
    paddingVertical: 16,
    alignItems: 'center',
  },

  // Cards
  card: {
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  triggerBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  unreadText: {
    fontWeight: '600',
  },
  typeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    gap: 4,
  },
  typeBadgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '600',
    marginBottom: 4,
  },
  cardBody: {
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 8,
  },
  cardTime: {
    fontSize: 12,
  },
  viewListingBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  viewListingText: {
    fontSize: 13,
    fontWeight: '600',
  },

  // Empty / Error states
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 60,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '600',
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 4,
    paddingHorizontal: 32,
  },
  emptyCtaContainer: {
    alignItems: 'center',
    marginTop: 16,
  },
  emptyCtaBtn: {
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 12,
  },
  emptyCtaBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  errorContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  errorText: {
    fontSize: 18,
    fontWeight: '600',
    marginTop: 12,
  },
  errorMessage: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
    marginBottom: 16,
  },
  retryBtn: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryBtnText: {
    color: '#fff',
    fontWeight: '600',
  },
});
