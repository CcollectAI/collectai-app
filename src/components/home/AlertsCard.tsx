/**
 * AlertsCard Component
 * Displays pending alerts with summary.
 */

import React, { useMemo, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { Alert, AlertType } from '@/types/insights';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { formatPrice } from '@/lib/format';

type AlertsCardProps = {
  alerts: Alert[];
  onAlertPress?: (alert: Alert) => void;
  onViewAll?: () => void;
  onStartWatchlist?: () => void;
  showEmptyState?: boolean;
};

type ThemeColors = ReturnType<typeof useAppTheme>['colors'];

function getAlertIcon(type: AlertType): string {
  switch (type) {
    case 'price_drop':
      return 'trending-down';
    case 'price_increase':
      return 'trending-up';
    case 'new_listing':
      return 'pricetag-outline';
    case 'milestone':
      return 'trophy-outline';
    default:
      return 'notifications-outline';
  }
}

function getAlertColor(type: AlertType, colors: ThemeColors): string {
  switch (type) {
    case 'price_drop':
      return colors.error;
    case 'price_increase':
      return colors.success;
    case 'new_listing':
      return colors.info;
    case 'milestone':
      return colors.warning;
    default:
      return colors.muted;
  }
}

type AlertItemProps = {
  alert: Alert;
  colors: ThemeColors;
  onPress?: () => void;
};

// The bell that used to sit here was REMOVED 2026-08-08.
//
// It DID toggle — but only a `Set<string>` held in this component's own state.
// Nothing was persisted and nothing reached the server, so the "setting" reset
// the moment the card remounted, and no worker ever consulted it. A control
// that animates, changes icon, and silently forgets is worse than no control:
// the user believes they have muted an alert and keeps receiving it.
//
// Nothing replaced it because there is nothing to wire. Alerts are armed by a
// watchlist row's `target_price`, and a per-fired-alert mute is not a concept
// this data model has. Category-level muting already exists and is real —
// user_settings.notification_preferences, honoured by notify_user.
function AlertItem({ alert, colors, onPress }: AlertItemProps) {
  const iconColor = getAlertColor(alert.type, colors);

  return (
    <AnimatedPressable
      style={styles.alertRow}
      onPress={() => {
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        onPress?.();
      }}
      accessibilityRole="button"
      accessibilityLabel={`${alert.itemName}. Target: ${formatPrice(alert.value)}`}
    >
      <View style={[styles.alertIcon, { backgroundColor: iconColor + '15' }]}>
        <Ionicons name={getAlertIcon(alert.type) as keyof typeof Ionicons.glyphMap} size={16} color={iconColor} />
      </View>
      <View style={styles.alertContent}>
        <Text style={[styles.alertTitle, { color: colors.text }]} numberOfLines={1}>
          {alert.itemName}
        </Text>
        <Text style={[styles.alertDesc, { color: colors.muted }]} numberOfLines={1}>
          {alert.description}
        </Text>
      </View>
      <View style={styles.alertRight}>
        <Text style={[styles.targetPrice, { color: colors.text }]}>
          {formatPrice(alert.value)}
        </Text>
      </View>
    </AnimatedPressable>
  );
}

function AlertsCardInner({ alerts, onAlertPress, onViewAll, onStartWatchlist, showEmptyState = true }: AlertsCardProps) {
  const { colors } = useAppTheme();
  const unreadCount = useMemo(() => alerts.filter((a) => !a.isRead).length, [alerts]);

  // Show card with empty state prompt if no alerts
  if (alerts.length === 0) {
    if (!showEmptyState) return null;

    return (
      <View
        style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
        accessibilityRole="summary"
        accessibilityLabel="Watchlist section"
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Ionicons name="eye-outline" size={18} color={colors.text} />
            <Text style={[styles.title, { color: colors.text }]}>Watchlist</Text>
          </View>
          <AnimatedPressable
            style={[styles.addBtn, { backgroundColor: colors.accent }]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              onStartWatchlist?.();
            }}
            accessibilityRole="button"
            accessibilityLabel="Add to watchlist"
          >
            <Ionicons name="add" size={16} color="#FFFFFF" />
            <Text style={styles.addBtnText}>Add</Text>
          </AnimatedPressable>
        </View>

        {/* Empty State - Start Watchlist prompt */}
        <AnimatedPressable
          style={styles.emptyState}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
            onStartWatchlist?.();
          }}
          accessibilityRole="button"
          accessibilityLabel="Start your watchlist"
        >
          <View style={styles.emptyContent}>
            <Text style={[styles.emptyTitle, { color: colors.text }]}>Start Your Watchlist</Text>
            <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
              Track items you want and set price alerts
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </AnimatedPressable>
      </View>
    );
  }

  return (
    <View
      style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="list"
      accessibilityLabel={`Watchlist: ${alerts.length} total, ${unreadCount} unread`}
    >
      {/* Header */}
      <View style={styles.headerRow}>
        <View style={styles.headerLeft}>
          <Ionicons name="eye-outline" size={18} color={colors.text} />
          <Text style={[styles.title, { color: colors.text }]}>Watchlist</Text>
          {unreadCount > 0 && (
            <View style={[styles.badge, { backgroundColor: colors.accent }]}>
              <Text style={styles.badgeText}>{unreadCount}</Text>
            </View>
          )}
        </View>
        <AnimatedPressable
          style={[styles.addBtn, { backgroundColor: colors.accent }]}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
            onStartWatchlist?.();
          }}
          accessibilityRole="button"
          accessibilityLabel="Add to watchlist"
        >
          <Ionicons name="add" size={16} color="#FFFFFF" />
          <Text style={styles.addBtnText}>Add</Text>
        </AnimatedPressable>
      </View>

      {/* Alert Items */}
      <View style={styles.alertList}>
        {alerts.slice(0, 3).map((alert, idx) => (
          <React.Fragment key={alert.id}>
            <AlertItem
              alert={alert}
              colors={colors}
              onPress={() => onAlertPress?.(alert)}
            />
            {idx < Math.min(alerts.length, 3) - 1 && (
              <View style={[styles.separator, { backgroundColor: colors.border }]} />
            )}
          </React.Fragment>
        ))}
      </View>

      {/* View All */}
      {alerts.length > 3 && onViewAll && (
        <AnimatedPressable
          style={[styles.viewAll, { borderTopColor: colors.border }]}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
            onViewAll();
          }}
          accessibilityRole="button"
          accessibilityLabel={`View all ${alerts.length} alerts`}
        >
          <Text style={[styles.viewAllText, { color: colors.accent }]}>
            View All ({alerts.length})
          </Text>
          <Ionicons name="chevron-forward" size={16} color={colors.accent} />
        </AnimatedPressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    borderWidth: 1,
    overflow: 'hidden',
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
    paddingHorizontal: 16,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
    paddingHorizontal: 16,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  addBtnText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
  },
  emptyState: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
  },
  emptyContent: {
    flex: 1,
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 2,
  },
  emptySubtitle: {
    fontSize: 12,
  },
  badge: {
    minWidth: 20,
    height: 20,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
  badgeText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
  },
  alertList: {
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  alertRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
  },
  alertIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  alertContent: {
    flex: 1,
    marginRight: 8,
  },
  alertTitle: {
    fontSize: 13,
    fontWeight: '600',
  },
  alertDesc: {
    fontSize: 12,
    marginTop: 2,
  },
  alertRight: {
    alignItems: 'flex-end',
    gap: 4,
  },
  targetPrice: {
    fontSize: 13,
    fontWeight: '700',
  },
  separator: {
    height: StyleSheet.hairlineWidth,
  },
  viewAll: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    padding: 12,
    marginHorizontal: 16,
    marginBottom: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'transparent',
  },
  viewAllText: {
    fontSize: 14,
    fontWeight: '600',
  },
});

export const AlertsCard = React.memo(AlertsCardInner);
export default AlertsCard;
