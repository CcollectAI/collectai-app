/**
 * Offers Inbox — P2P Deal Desk offer management.
 *
 * Two tabs: "Active" (proposed/countered/accepted) + "History" (completed/cancelled/declined/expired).
 * Each offer card shows: item thumbnail, counterparty name, offer amount, status badge, date.
 * Pull-to-refresh, empty states, skeleton loading.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { router, Stack } from 'expo-router';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { dataProvider } from '@/data';
import { fireHaptic, HapticIntent } from '@/haptics';
import { formatPrice } from '@/lib/format';
import { EmptyState } from '@/components/EmptyState';
import { SkeletonList } from '@/components/Skeleton';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { AnimatedPressable } from '@/motion';
import type { Offer, OfferStatus } from '@/data/types';

// ---------------------------------------------------------------------------
// Status badge config
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<OfferStatus, { label: string; bg: string; fg: string }> = {
  proposed: { label: 'Pending', bg: '#FEF3C7', fg: '#92400E' },
  countered: { label: 'Countered', bg: '#DBEAFE', fg: '#1E40AF' },
  accepted: { label: 'Accepted', bg: '#D1FAE5', fg: '#065F46' },
  declined: { label: 'Declined', bg: '#FEE2E2', fg: '#991B1B' },
  expired: { label: 'Expired', bg: '#F3F4F6', fg: '#6B7280' },
  completed: { label: 'Completed', bg: '#D1FAE5', fg: '#065F46' },
  cancelled: { label: 'Cancelled', bg: '#F3F4F6', fg: '#6B7280' },
};

// ---------------------------------------------------------------------------
// Relative time helper
// ---------------------------------------------------------------------------

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

// ---------------------------------------------------------------------------
// Tab type
// ---------------------------------------------------------------------------

type Tab = 'active' | 'history';

// ---------------------------------------------------------------------------
// OfferCard component
// ---------------------------------------------------------------------------

function OfferCard({
  offer,
  colors,
  currency,
}: {
  offer: Offer;
  colors: ReturnType<typeof useAppTheme>['colors'];
  currency: string;
}) {
  const statusCfg = STATUS_CONFIG[offer.status] || STATUS_CONFIG.proposed;

  return (
    <AnimatedPressable
      onPress={() => {
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        router.push(`/sell/${encodeURIComponent(offer.id)}`);
      }}
      style={[styles.offerCard, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="button"
      accessibilityLabel={`Offer from ${offer.otherUserName} for ${offer.itemTitle}, ${statusCfg.label}`}
    >
      {/* Item thumbnail */}
      <View style={[styles.offerThumb, { backgroundColor: colors.background }]}>
        {offer.itemImageUrl ? (
          <Image
            source={{ uri: offer.itemImageUrl }}
            style={styles.offerThumbImage}
            contentFit="cover"
            cachePolicy="disk"
            transition={150}
          />
        ) : (
          <Ionicons name="cube-outline" size={24} color={colors.muted} />
        )}
      </View>

      {/* Info */}
      <View style={styles.offerInfo}>
        <Text style={[styles.offerItemTitle, { color: colors.text }]} numberOfLines={1}>
          {offer.itemTitle}
        </Text>
        <View style={styles.offerMetaRow}>
          {offer.otherUserAvatarUrl ? (
            <Image
              source={{ uri: offer.otherUserAvatarUrl }}
              style={styles.offerAvatar}
              contentFit="cover"
              cachePolicy="disk"
            />
          ) : (
            <View style={[styles.offerAvatarPlaceholder, { backgroundColor: colors.accent + '30' }]}>
              <Text style={[styles.offerAvatarInitial, { color: colors.accent }]}>
                {(offer.otherUserName || '?')[0].toUpperCase()}
              </Text>
            </View>
          )}
          <Text style={[styles.offerUserName, { color: colors.muted }]} numberOfLines={1}>
            {offer.otherUserName}
          </Text>
        </View>
        <Text style={[styles.offerTime, { color: colors.muted }]}>
          {relativeTime(offer.updatedAt)}
        </Text>
      </View>

      {/* Price + status */}
      <View style={styles.offerRight}>
        <Text style={[styles.offerPrice, { color: colors.text }]}>
          {formatPrice(offer.currentPrice, currency as 'EUR')}
        </Text>
        <View style={[styles.statusBadge, { backgroundColor: statusCfg.bg }]}>
          <Text style={[styles.statusBadgeText, { color: statusCfg.fg }]}>
            {statusCfg.label}
          </Text>
        </View>
      </View>
    </AnimatedPressable>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

function OffersInboxScreen() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();

  const [tab, setTab] = useState<Tab>('active');
  const [activeOffers, setActiveOffers] = useState<Offer[]>([]);
  const [historyOffers, setHistoryOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [active, history] = await Promise.all([
        dataProvider.listActiveOffers(),
        dataProvider.listDealHistory(),
      ]);
      setActiveOffers(active);
      setHistoryOffers(history);
    } catch (err) {
      showToast({ message: 'Failed to load offers', type: 'error' });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    loadData();
  }, [loadData, settings.hapticsEnabled]);

  const offers = tab === 'active' ? activeOffers : historyOffers;

  const renderItem = useCallback(
    ({ item }: { item: Offer }) => (
      <OfferCard offer={item} colors={colors} currency={settings.currency} />
    ),
    [colors, settings.currency],
  );

  const keyExtractor = useCallback((item: Offer) => item.id, []);

  return (
    <View style={[styles.safeArea, { backgroundColor: colors.background, flex: 1 }]}>
      <Stack.Screen options={{ headerTitle: 'My Offers' }} />

      {/* Tab bar */}
      <View style={[styles.tabBar, { borderBottomColor: colors.border }]}>
        <Pressable
          onPress={() => setTab('active')}
          style={[
            styles.tabBtn,
            tab === 'active' && { borderBottomColor: colors.accent, borderBottomWidth: 2 },
          ]}
          accessibilityRole="tab"
          accessibilityState={{ selected: tab === 'active' }}
          accessibilityLabel={`Active offers (${activeOffers.length})`}
        >
          <Text
            style={[
              styles.tabBtnText,
              { color: tab === 'active' ? colors.accent : colors.muted },
            ]}
          >
            Active ({activeOffers.length})
          </Text>
        </Pressable>
        <Pressable
          onPress={() => setTab('history')}
          style={[
            styles.tabBtn,
            tab === 'history' && { borderBottomColor: colors.accent, borderBottomWidth: 2 },
          ]}
          accessibilityRole="tab"
          accessibilityState={{ selected: tab === 'history' }}
          accessibilityLabel={`History (${historyOffers.length})`}
        >
          <Text
            style={[
              styles.tabBtnText,
              { color: tab === 'history' ? colors.accent : colors.muted },
            ]}
          >
            History ({historyOffers.length})
          </Text>
        </Pressable>
      </View>

      {/* Content */}
      {loading ? (
        <SkeletonList count={4} type="deal" />
      ) : offers.length === 0 ? (
        <EmptyState
          icon={tab === 'active' ? 'pricetags-outline' : 'time-outline'}
          title={tab === 'active' ? 'No active offers' : 'No offer history'}
          subtitle={
            tab === 'active'
              ? 'When someone makes an offer on your listed items, it will appear here'
              : 'Your completed, cancelled, and declined offers will appear here'
          }
          colors={colors}
        />
      ) : (
        <FlatList
          data={offers}
          renderItem={renderItem}
          keyExtractor={keyExtractor}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={colors.accent}
              colors={[colors.accent]}
            />
          }
        />
      )}

      <QuickNavBar />
    </View>
  );
}

export default function OffersInboxWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Offers Inbox">
      <OffersInboxScreen />
    </ScreenErrorBoundary>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  tabBar: {
    flexDirection: 'row',
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  tabBtn: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabBtnText: {
    fontSize: 14,
    fontWeight: '600',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 24,
  },
  offerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 14,
    borderWidth: 1,
    marginBottom: 10,
    gap: 12,
  },
  offerThumb: {
    width: 56,
    height: 56,
    borderRadius: 10,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  offerThumbImage: {
    width: 56,
    height: 56,
  },
  offerInfo: {
    flex: 1,
  },
  offerItemTitle: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 4,
  },
  offerMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 2,
  },
  offerAvatar: {
    width: 18,
    height: 18,
    borderRadius: 9,
  },
  offerAvatarPlaceholder: {
    width: 18,
    height: 18,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
  },
  offerAvatarInitial: {
    fontSize: 10,
    fontWeight: '700',
  },
  offerUserName: {
    fontSize: 12,
    flex: 1,
  },
  offerTime: {
    fontSize: 11,
  },
  offerRight: {
    alignItems: 'flex-end',
    gap: 6,
  },
  offerPrice: {
    fontSize: 15,
    fontWeight: '700',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  statusBadgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
});
