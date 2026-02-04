/**
 * AlertDetailModal Component
 * Modal showing detailed alert information with actions.
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  Pressable,
  SafeAreaView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { Alert, AlertType } from '@/types/insights';

type AlertDetailModalProps = {
  alert: Alert | null;
  visible: boolean;
  onClose: () => void;
  onViewItem?: (itemId: string) => void;
  onUpdateThreshold?: (alert: Alert) => void;
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

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
  }).format(value);
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function AlertDetailModal({
  alert,
  visible,
  onClose,
  onViewItem,
  onUpdateThreshold,
}: AlertDetailModalProps) {
  const { colors } = useAppTheme();

  if (!alert) return null;

  const iconColor = getAlertColor(alert.type);

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        {/* Header */}
        <View style={styles.header}>
          <Pressable
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close"
          >
            <Ionicons name="close" size={24} color={colors.text} />
          </Pressable>
          <Text style={[styles.headerTitle, { color: colors.text }]}>Alert Details</Text>
          <View style={{ width: 24 }} />
        </View>

        {/* Content */}
        <View style={styles.content}>
          {/* Alert Type Icon */}
          <View style={[styles.iconContainer, { backgroundColor: iconColor + '20' }]}>
            <Ionicons name={getAlertIcon(alert.type) as any} size={32} color={iconColor} />
          </View>

          {/* Item Info */}
          <Text style={[styles.itemName, { color: colors.text }]}>{alert.itemName}</Text>
          <Text style={[styles.itemCategory, { color: colors.muted }]}>
            {alert.itemCategory}
          </Text>

          {/* Description */}
          <View style={[styles.descCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.description, { color: colors.text }]}>
              {alert.description}
            </Text>
            <Text style={[styles.condition, { color: colors.muted }]}>
              {alert.condition}
            </Text>
          </View>

          {/* Value Info */}
          <View style={styles.valueRow}>
            <View style={styles.valueBlock}>
              <Text style={[styles.valueLabel, { color: colors.muted }]}>Current</Text>
              <Text style={[styles.valueAmount, { color: colors.text }]}>
                {formatCurrency(alert.value)}
              </Text>
            </View>
            {alert.previousValue && (
              <View style={styles.valueBlock}>
                <Text style={[styles.valueLabel, { color: colors.muted }]}>Previous</Text>
                <Text style={[styles.valueAmount, { color: colors.muted }]}>
                  {formatCurrency(alert.previousValue)}
                </Text>
              </View>
            )}
          </View>

          {/* Timestamp */}
          <Text style={[styles.timestamp, { color: colors.muted }]}>
            Triggered {formatDate(alert.triggeredAt)}
          </Text>
        </View>

        {/* Actions */}
        <View style={styles.actions}>
          {onViewItem && (
            <Pressable
              style={[styles.actionButton, { backgroundColor: colors.accent }]}
              onPress={() => onViewItem(alert.itemId)}
              accessibilityRole="button"
              accessibilityLabel="View item details"
            >
              <Text style={styles.actionButtonText}>View Item</Text>
            </Pressable>
          )}

          {onUpdateThreshold && alert.type === 'price_drop' && (
            <Pressable
              style={[styles.actionButtonSecondary, { borderColor: colors.border }]}
              onPress={() => onUpdateThreshold(alert)}
              accessibilityRole="button"
              accessibilityLabel="Update price threshold"
            >
              <Text style={[styles.actionButtonSecondaryText, { color: colors.text }]}>
                Update Threshold
              </Text>
            </Pressable>
          )}
        </View>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(0,0,0,0.1)',
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  content: {
    flex: 1,
    padding: 24,
    alignItems: 'center',
  },
  iconContainer: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  itemName: {
    fontSize: 20,
    fontWeight: '700',
    textAlign: 'center',
  },
  itemCategory: {
    fontSize: 14,
    marginTop: 4,
    marginBottom: 20,
  },
  descCard: {
    width: '100%',
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    marginBottom: 20,
  },
  description: {
    fontSize: 16,
    fontWeight: '500',
    marginBottom: 8,
  },
  condition: {
    fontSize: 14,
  },
  valueRow: {
    flexDirection: 'row',
    width: '100%',
    marginBottom: 20,
  },
  valueBlock: {
    flex: 1,
    alignItems: 'center',
  },
  valueLabel: {
    fontSize: 12,
    marginBottom: 4,
  },
  valueAmount: {
    fontSize: 24,
    fontWeight: '700',
  },
  timestamp: {
    fontSize: 12,
  },
  actions: {
    padding: 16,
    gap: 12,
  },
  actionButton: {
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  actionButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  actionButtonSecondary: {
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 1,
  },
  actionButtonSecondaryText: {
    fontSize: 16,
    fontWeight: '600',
  },
});

export default AlertDetailModal;
