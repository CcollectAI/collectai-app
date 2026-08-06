/**
 * Alerts Feed — Shows trigger history and alert rules.
 * Route: /alerts
 *
 * Two tabs:
 *   "Recent"  — entries from alert_trigger_history (when alerts actually fired)
 *   "Rules"   — the user's standing rules from GET /alerts/mine (user_price_alerts)
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  Alert,
  Linking,
  RefreshControl,
} from 'react-native';
import { useRouter, Stack } from 'expo-router';
import { itemHref } from '@/lib/ids';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type AlertRule } from '@/data';
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
import { timeAgo } from '@/lib/timeAgo';
import { MS_PER_WEEK } from '@/constants/time';
import { useBillingLimits } from '@/hooks/useBillingLimits';
import { UpgradePrompt } from '@/components/UpgradePrompt';
import { SwipeableRow, SwipeActions } from '@/components/SwipeableRow';
import { useToast } from '@/components/Toast';

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

/**
 * Resolve alert type → theme color. Must be called inside a component with colors.
 *
 * Keys are `alert_trigger_history.trigger_type` values. The four marked PRESENT
 * are the only ones prod has ever written (counted 2026-08-05: low_value 58,
 * weekly_digest 30, value_change 12, watchlist_snipe 1). Every one of them was
 * unmapped, so ~100% of the screen rendered `colors.muted` + the generic bell
 * and read as disabled — while the seven mapped types below had never occurred
 * once. Same drift the notifications screen hit (see `_FEED_TYPE_BY_CATEGORY`
 * in server/app/lib/notify.py); icons here match app/notifications.tsx.
 *
 * "Present" is not "currently produced": low_value, weekly_digest and
 * value_change all stop at 2026-04-22 — their workers were commented out of
 * the bake manifest in the 2026-05-04 pre-launch cut, so those rows are a
 * backlog. Only watchlist_snipe has been written since. Mapping them is still
 * correct: the rows are on screen today either way.
 *
 * Anything unmapped still falls back to muted — deliberately, so a new
 * server-side type degrades to plain rather than mis-labelled.
 */
function getTypeColor(colors: { success: string; warning: string; info: string; danger: string; accent: string; muted: string }, type: string): { bg: string; text: string } {
  const MAP: Record<string, string> = {
    // LIVE — written by workers today
    watchlist_snipe: colors.success,   // deal_discovery_worker, phase 2
    low_value: colors.warning,         // alerts_worker / signal_alerts_worker
    value_change: colors.info,         // value_change_worker
    weekly_digest: colors.accent,      // insights_digest_worker
    // Designed but never yet written by any worker
    price_drop: colors.success,
    price_spike: colors.warning,
    below_threshold: colors.success,
    restock: colors.info,
    drop_detected: colors.accent,
    completeness: colors.info,
    rarity: colors.danger,
  };
  const c = MAP[type] ?? colors.muted;
  return { bg: c + '20', text: c };
}

const TYPE_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  // LIVE — see getTypeColor above
  watchlist_snipe: 'flash-outline',
  low_value: 'trending-down',
  value_change: 'analytics-outline',  // matches app/notifications.tsx
  weekly_digest: 'bulb-outline',      // 'insight' there
  // Designed but never yet written
  price_drop: 'trending-down',
  price_spike: 'trending-up',
  below_threshold: 'trending-down',
  restock: 'cube-outline',
  drop_detected: 'flash-outline',
  completeness: 'checkmark-circle-outline',
  rarity: 'diamond-outline',
};

/**
 * Human labels for `alert_trigger_history.trigger_type`.
 *
 * "Snipe" was never a user-facing word — the badge just title-cased the raw
 * column value, so the screen read "Watchlist Snipe", which describes our
 * implementation rather than what happened to the user. `watchlist_snipe` stays
 * as the STORED key (renaming it would orphan every existing row and every
 * server-side reference); only the label changes.
 *
 * "Target Hit" is the whole feature in two words: the price you set has been
 * met by something you can actually buy right now.
 */
const TRIGGER_LABELS: Record<string, string> = {
  watchlist_snipe: 'Target Hit',
  value_change: 'Value Change',
  weekly_digest: 'Weekly Digest',
  // Retired 2026-08-06 (the worker is deleted), but 58 rows remain in prod
  // history and must still render with a label rather than a raw column value.
  low_value: 'Low Value',
};

/** Human labels for the 3 legal user_price_alerts.trigger_type values. */
const RULE_TYPE_LABELS: Record<string, string> = {
  below_threshold: 'Price drop',
  category_trend: 'Trend',
  high_prediction: 'Predicted rise',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const diff = Date.now() - date.getTime();
  if (diff < MS_PER_WEEK) return timeAgo(date);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function AlertsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { plan } = useBillingLimits();

  const [activeTab, setActiveTab] = useState<ActiveTab>('triggers');
  const [refreshing, setRefreshing] = useState(false);
  const [scarcityItems, setScarcityItems] = useState<{ item_key: string; title: string; scarcity_score: number; supply_trend: string }[]>([]);

  // Fetch scarcity alerts (rare items in collection)
  React.useEffect(() => {
    let cancelled = false;
    collectorsApi.getScarcityScores()
      .then((data) => {
        if (!cancelled && Array.isArray(data?.items)) {
          setScarcityItems(data.items.filter((i) => i.scarcity_score >= 0.7).slice(0, 5));
        }
      })
      .catch((err) => logger.warn('[Alerts] scarcity fetch failed:', err));
    return () => { cancelled = true; };
  }, []);

  // -----------------------------------------------------------------------
  // Paginated alert rules via usePaginatedList
  // -----------------------------------------------------------------------

  // The Rules tab must read the user's standing rules (GET /alerts/mine), not
  // the trigger feed. It called listAlertsFeed until 2026-07-30, which meant
  // it duplicated the Triggers tab, showed "No alert rules yet" even when the
  // user had rules, and fed trigger-history ids to DELETE /alerts/mine/{id}
  // (a 404 on every swipe-to-delete).
  const alertsFetcher = useCallback(
    async (limit: number, offset: number): Promise<AlertRule[]> => {
      return dataProvider.listAlertRules({ limit, offset });
    },
    [],
  );

  const {
    items: alerts,
    setItems: setAlerts,
    isLoading: alertsLoading,
    isLoadingMore: alertsLoadingMore,
    hasMore: alertsHasMore,
    error: alertsError,
    loadMore: alertsLoadMore,
    refresh: alertsRefresh,
  } = usePaginatedList<AlertRule>(alertsFetcher, { pageSize: 20 });

  const { showToast } = useToast();

  // Optimistic delete for an alert rule. Hits DELETE /alerts/mine/{id}
  // and rolls back the row if the request fails.
  const handleDeleteAlert = useCallback((alertId: string) => {
    Alert.alert(
      'Delete Alert',
      'Stop receiving notifications for this alert?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            const snapshot = alerts;
            setAlerts((prev) => prev.filter((a) => a.id !== alertId));
            try {
              await collectorsApi.deleteAlert(alertId);
              fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
              showToast({ message: 'Alert deleted', type: 'success', duration: 2000 });
            } catch (err: unknown) {
              setAlerts(snapshot);
              showToast({ message: (err as Error)?.message || 'Failed to delete alert', type: 'error' });
              fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
            }
          },
        },
      ],
    );
  }, [alerts, setAlerts, showToast, settings.hapticsEnabled]);

  // -----------------------------------------------------------------------
  // Trigger history loading (not paginated — comes from API endpoint)
  // -----------------------------------------------------------------------

  const { data: triggersData, loading: triggersLoading, error: triggersError, retry: loadTriggers } = useAsync(
    async () => {
      const historyData = await collectorsApi
        .getAlertTriggerHistory()
        .catch((err) => {
          logger.warn('[Alerts] Failed to load triggers', err);
          return { triggers: [] as { id: string; alert_id: string | null; item_id: string | null; trigger_type: string; trigger_value: Record<string, unknown>; message: string; read: boolean; created_at: string }[], unread_count: 0 };
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
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      try {
        await collectorsApi.markTriggerRead(triggerId);
      } catch (e) {
        logger.error('[silent-fallback] alerts: mark-read failed, reverting:', e);
        // Revert on failure — reload from server
        setReadIds(new Set());
        loadTriggers();
      }
    },
    [loadTriggers, settings.hapticsEnabled],
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
    const typeColor = getTypeColor(colors, item.triggerType);
    const typeIcon: keyof typeof Ionicons.glyphMap =
      TYPE_ICONS[item.triggerType] || 'notifications-outline';
    const typeLabel = TRIGGER_LABELS[item.triggerType]
      ?? item.triggerType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

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
          ) : item.itemId && !item.itemId.startsWith('watchlist_snipe:') ? (
            <AnimatedPressable
              onPress={() => {
                handleMarkRead(item.id);
                // itemId comes from `alert_trigger_history.item_id`, a TEXT
                // column: the low-value worker stores a catalog key there, not
                // an items uuid. Interpolating it into /item/[id] produced
                // 22P02 and a blank "Unknown item" screen. itemHref picks the
                // screen that matches the identifier's shape.
                //
                // `watchlist_snipe:<uuid>` is neither an items uuid nor a
                // catalog key — deal_discovery_worker synthesises it as a
                // dedupe handle. It fell into itemHref's catalog branch and
                // routed to /catalog-item/watchlist_snipe:<uuid>, which
                // resolves to nothing. A snipe alert's real destination is the
                // listing, rendered by the branch above; when the listing URL
                // is missing there is nothing to open, so render no button
                // rather than one that dead-ends.
                const href = itemHref(item.itemId);
                if (href) router.push(href);
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
  // Render: a standing alert rule (GET /alerts/mine)
  // -----------------------------------------------------------------------

  const renderAlert = ({ item }: { item: AlertRule }) => {
    const typeColor = getTypeColor(colors, item.triggerType);
    const typeIcon: keyof typeof Ionicons.glyphMap =
      TYPE_ICONS[item.triggerType] || 'notifications-outline';
    const typeLabel = RULE_TYPE_LABELS[item.triggerType] ?? 'Alert';

    // One plain sentence, no sub-explanations. `threshold_value` has no
    // currency column server-side — it is stored as the number the user typed
    // in the wishlist, so render it in their current display currency, which
    // is what that screen showed them when they set it.
    const subject = item.category
      ? item.category.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
      : 'This item';
    const threshold =
      item.thresholdValue != null
        ? formatPrice(item.thresholdValue, settings.currency, settings.numberLocale)
        : null;
    const title =
      item.triggerType === 'below_threshold' && threshold
        ? `${subject} drops below ${threshold}`
        : item.triggerType === 'high_prediction'
          ? `${subject} is predicted to rise`
          : `${subject} trends ${item.direction === 'up' ? 'up' : 'down'}`;
    const body = item.active ? null : 'Paused';

    const card = (
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
          {title}
        </Text>
        {body && (
          <Text
            style={[styles.cardBody, { color: colors.muted }]}
            numberOfLines={3}
          >
            {body}
          </Text>
        )}

        {/* Timestamp */}
        <Text style={[styles.cardTime, { color: colors.muted }]}>
          {formatRelativeTime(item.createdAt)}
        </Text>
      </View>
    );

    return (
      <SwipeableRow
        rightActions={[SwipeActions.delete(() => handleDeleteAlert(item.id))]}
        enableHaptics={settings.hapticsEnabled}
      >
        {card}
      </SwipeableRow>
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
          removeClippedSubviews={true}
          maxToRenderPerBatch={10}
          windowSize={5}
          ListHeaderComponent={<>
            {plan === 'free' && (
              <View style={{ marginBottom: 12 }}>
                <UpgradePrompt
                  feature="Unlimited Alerts (1/week on Free)"
                  requiredPlan="Pro"
                />
              </View>
            )}
            {scarcityItems.length > 0 ? (
            <View style={[styles.scarcityCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.scarcityHeader}>
                <Ionicons name="diamond-outline" size={16} color={colors.warning} />
                <Text style={[styles.scarcityTitle, { color: colors.text }]}>Rare in Your Collection</Text>
              </View>
              {scarcityItems.map((item) => (
                <View key={item.item_key} style={[styles.scarcityRow, { borderBottomColor: colors.border }]}>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.scarcityName, { color: colors.text }]} numberOfLines={1}>
                      {item.title || item.item_key.replace(/-/g, ' ')}
                    </Text>
                    <Text style={[styles.scarcityMeta, { color: colors.muted }]}>{item.supply_trend}</Text>
                  </View>
                  <View style={[styles.scarcityBadge, { backgroundColor: colors.warning + '20' }]}>
                    <Text style={[styles.scarcityScore, { color: colors.warning }]}>
                      {Math.round(item.scarcity_score * 100)}%
                    </Text>
                  </View>
                </View>
              ))}
            </View>
          ) : null}
          </>}
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
          removeClippedSubviews={true}
          maxToRenderPerBatch={10}
          windowSize={5}
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
              {/* This tab is empty BY DESIGN as of 2026-08-05: nothing in the
                  app writes `user_price_alerts` any more, because those rules
                  could never fire (price_monitor_worker requires item_id, the
                  wishlist has none — 4 rules, 0 triggers in prod). A watchlist
                  target price IS the standing rule now, so send the user there
                  and describe what actually happens. */}
              <Text style={[styles.emptyText, { color: colors.muted }]}>
                Your targets live on the watchlist
              </Text>
              <Text style={[styles.emptySubtext, { color: colors.muted }]}>
                Set a target price on a watchlist item and we&apos;ll alert you when
                it&apos;s listed below it.
              </Text>
              <View style={styles.emptyCtaContainer}>
                <AnimatedPressable
                  onPress={() => router.push('/watchlist-builder')}
                  style={[styles.emptyCtaBtn, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Set a target price"
                >
                  <Text style={styles.emptyCtaBtnText}>Set a Target Price</Text>
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

  // Scarcity alerts (M5)
  scarcityCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 12,
  },
  scarcityHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  scarcityTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  scarcityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  scarcityName: {
    fontSize: 13,
    fontWeight: '600',
  },
  scarcityMeta: {
    fontSize: 11,
    marginTop: 1,
    textTransform: 'capitalize',
  },
  scarcityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    marginLeft: 8,
  },
  scarcityScore: {
    fontSize: 12,
    fontWeight: '700',
  },
});
