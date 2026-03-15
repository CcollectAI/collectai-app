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
import { timeAgo } from '@/lib/timeAgo';
import { STATUS_LABELS } from '@/constants/dealStatus';
import { radius, text, fontWeight } from '@/theme/tokens';

// ---------------------------------------------------------------------------
// Relative time helper
// ---------------------------------------------------------------------------

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '';
  return timeAgo(iso);
}

// ---------------------------------------------------------------------------
// Tab type
// ---------------------------------------------------------------------------

type Tab = 'active' | 'history';

// ---------------------------------------------------------------------------
// OfferCard component
// ---------------------------------------------------------------------------

const OfferCard = React.memo(function OfferCard({
  offer,
  colors,
  statusTokens,
  currency,
}: {
  offer: Offer;
  colors: ReturnType<typeof useAppTheme>['colors'];
  statusTokens: ReturnType<typeof useAppTheme>['status'];
  currency: string;
}) {
  const statusColor = statusTokens[offer.status as keyof typeof statusTokens] || statusTokens.proposed;
  const statusLabel = STATUS_LABELS[offer.status] || STATUS_LABELS.proposed;

  return (
    <AnimatedPressable
      onPress={() => {
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        router.push(`/sell/${encodeURIComponent(offer.id)}`);
      }}
      style={[styles.offerCard, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="button"
      accessibilityLabel={`Offer from ${offer.otherUserName} for ${offer.itemTitle}, ${statusLabel}`}
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
        <View style={[styles.statusBadge, { backgroundColor: statusColor.bg }]}>
          <Text style={[styles.statusBadgeText, { color: statusColor.fg }]}>
            {statusLabel}
          </Text>
        </View>
      </View>
    </AnimatedPressable>
  );
});

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

function OffersInboxScreen() {
  const { colors, status: statusTokens } = useAppTheme();
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
      <OfferCard offer={item} colors={colors} statusTokens={statusTokens} currency={settings.currency} />
    ),
    [colors, statusTokens, settings.currency],
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
          removeClippedSubviews={true}
          maxToRenderPerBatch={8}
          windowSize={5}
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
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
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
    borderRadius: radius.md,
    borderWidth: 1,
    marginBottom: 10,
    gap: 12,
  },
  offerThumb: {
    width: 56,
    height: 56,
    borderRadius: radius.sm,
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
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
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
    fontSize: text.xs,
    fontWeight: fontWeight.bold,
  },
  offerUserName: {
    fontSize: text.sm,
    flex: 1,
  },
  offerTime: {
    fontSize: text.xs,
  },
  offerRight: {
    alignItems: 'flex-end',
    gap: 6,
  },
  offerPrice: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.xs,
  },
  statusBadgeText: {
    fontSize: text.xs,
    fontWeight: fontWeight.semibold,
  },
});
