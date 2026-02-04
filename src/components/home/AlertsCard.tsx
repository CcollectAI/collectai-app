/**
 * AlertsCard Component
 * Displays pending alerts with summary.
 */

import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { Alert, AlertType } from '@/types/insights';

type AlertsCardProps = {
  alerts: Alert[];
  onAlertPress?: (alert: Alert) => void;
  onViewAll?: () => void;
};

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

function getAlertColor(type: AlertType): string {
  switch (type) {
    case 'price_drop':
      return '#EF4444';
    case 'price_increase':
      return '#0BA86C';
    case 'new_listing':
      return '#3B82F6';
    case 'milestone':
      return '#F59E0B';
    default:
      return '#6B7280';
  }
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffHours < 1) return 'Just now';
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  return `${diffDays}d ago`;
}

type AlertItemProps = {
  alert: Alert;
  colors: any;
  onPress?: () => void;
};

function AlertItem({ alert, colors, onPress }: AlertItemProps) {
  const iconColor = getAlertColor(alert.type);

  return (
    <Pressable
      style={[styles.alertRow, !alert.isRead && styles.alertUnread]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${alert.description}. ${formatTimeAgo(alert.triggeredAt)}`}
    >
      <View style={[styles.alertIcon, { backgroundColor: iconColor + '15' }]}>
        <Ionicons name={getAlertIcon(alert.type) as any} size={16} color={iconColor} />
      </View>
      <View style={styles.alertContent}>
        <Text style={[styles.alertTitle, { color: colors.text }]} numberOfLines={1}>
          {alert.itemName}
        </Text>
        <Text style={[styles.alertDesc, { color: colors.muted }]} numberOfLines={1}>
          {alert.description}
        </Text>
      </View>
      <Text style={[styles.alertTime, { color: colors.muted }]}>
        {formatTimeAgo(alert.triggeredAt)}
      </Text>
    </Pressable>
  );
}

export function AlertsCard({ alerts, onAlertPress, onViewAll }: AlertsCardProps) {
  const { colors } = useAppTheme();
  const unreadCount = alerts.filter((a) => !a.isRead).length;

  if (alerts.length === 0) {
    return null;
  }

  return (
    <View
      style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="list"
      accessibilityLabel={`Alerts: ${alerts.length} total, ${unreadCount} unread`}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="notifications-outline" size={18} color={colors.accent} />
          <Text style={[styles.title, { color: colors.text }]}>Alerts</Text>
          {unreadCount > 0 && (
            <View style={[styles.badge, { backgroundColor: colors.accent }]}>
              <Text style={styles.badgeText}>{unreadCount}</Text>
            </View>
          )}
        </View>
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
        <Pressable
          style={styles.viewAll}
          onPress={onViewAll}
          accessibilityRole="button"
          accessibilityLabel={`View all ${alerts.length} alerts`}
        >
          <Text style={[styles.viewAllText, { color: colors.accent }]}>
            View All ({alerts.length})
          </Text>
          <Ionicons name="chevron-forward" size={16} color={colors.accent} />
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
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
  alertList: {},
  alertRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
  },
  alertUnread: {
    opacity: 1,
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
  alertTime: {
    fontSize: 11,
  },
  separator: {
    height: StyleSheet.hairlineWidth,
  },
  viewAll: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(0,0,0,0.1)',
  },
  viewAllText: {
    fontSize: 14,
    fontWeight: '600',
  },
});

export default AlertsCard;
