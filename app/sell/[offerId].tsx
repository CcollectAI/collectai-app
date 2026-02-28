/**
 * Offer Detail — P2P Deal Desk negotiation screen.
 *
 * Shows item info, negotiation timeline, action buttons based on role + status,
 * counter-offer modal, shipping/completion flows, and reputation display.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  TextInput,
  Modal,
  Pressable,
  ActivityIndicator,
  RefreshControl,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { router, useLocalSearchParams, Stack } from 'expo-router';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useAuthContext } from '@/providers/useAuthContext';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { dataProvider } from '@/data';
import { fireHaptic, HapticIntent } from '@/haptics';
import { formatPrice } from '@/lib/format';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { AnimatedPressable } from '@/motion';
import { SkeletonList } from '@/components/Skeleton';
import type { Offer, OfferEvent, OfferStatus, UserReputation } from '@/data/types';

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<OfferStatus, { label: string; bg: string; fg: string; icon: keyof typeof Ionicons.glyphMap }> = {
  proposed: { label: 'Pending', bg: '#FEF3C7', fg: '#92400E', icon: 'hourglass-outline' },
  countered: { label: 'Countered', bg: '#DBEAFE', fg: '#1E40AF', icon: 'swap-horizontal-outline' },
  accepted: { label: 'Accepted', bg: '#D1FAE5', fg: '#065F46', icon: 'checkmark-circle-outline' },
  declined: { label: 'Declined', bg: '#FEE2E2', fg: '#991B1B', icon: 'close-circle-outline' },
  expired: { label: 'Expired', bg: '#F3F4F6', fg: '#6B7280', icon: 'time-outline' },
  completed: { label: 'Completed', bg: '#D1FAE5', fg: '#065F46', icon: 'checkmark-done-outline' },
  cancelled: { label: 'Cancelled', bg: '#F3F4F6', fg: '#6B7280', icon: 'ban-outline' },
};

// ---------------------------------------------------------------------------
// Event type display config
// ---------------------------------------------------------------------------

const EVENT_DISPLAY: Record<string, { icon: keyof typeof Ionicons.glyphMap; label: string; color: string }> = {
  proposed: { icon: 'pricetag-outline', label: 'Offer proposed', color: '#2563EB' },
  countered: { icon: 'swap-horizontal-outline', label: 'Counter-offer', color: '#7C3AED' },
  accepted: { icon: 'checkmark-circle-outline', label: 'Offer accepted', color: '#059669' },
  declined: { icon: 'close-circle-outline', label: 'Offer declined', color: '#DC2626' },
  cancelled: { icon: 'ban-outline', label: 'Offer cancelled', color: '#6B7280' },
  shipped: { icon: 'airplane-outline', label: 'Marked as shipped', color: '#2563EB' },
  completed: { icon: 'checkmark-done-outline', label: 'Deal completed', color: '#059669' },
  expired: { icon: 'time-outline', label: 'Offer expired', color: '#6B7280' },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
    ' at ' +
    d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ---------------------------------------------------------------------------
// Star display
// ---------------------------------------------------------------------------

function StarRating({ stars, size = 14 }: { stars: number; size?: number }) {
  const fullStars = Math.floor(stars);
  const hasHalf = stars - fullStars >= 0.25;
  return (
    <View style={{ flexDirection: 'row', gap: 1 }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <Ionicons
          key={i}
          name={i < fullStars ? 'star' : (i === fullStars && hasHalf ? 'star-half' : 'star-outline')}
          size={size}
          color="#F59E0B"
        />
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// ReputationBadge
// ---------------------------------------------------------------------------

function ReputationBadge({
  label,
  reputation,
  colors,
}: {
  label: string;
  reputation: UserReputation | null;
  colors: ReturnType<typeof useAppTheme>['colors'];
}) {
  if (!reputation) return null;
  return (
    <View style={[styles.repBadge, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <Text style={[styles.repLabel, { color: colors.muted }]}>{label}</Text>
      <View style={styles.repRow}>
        {reputation.totalRatings > 0 ? (
          <>
            <StarRating stars={reputation.avgStars} />
            <Text style={[styles.repScore, { color: colors.text }]}>
              {reputation.avgStars.toFixed(1)}
            </Text>
          </>
        ) : (
          <Text style={[styles.repNoRating, { color: colors.muted }]}>No ratings yet</Text>
        )}
      </View>
      <Text style={[styles.repDeals, { color: colors.muted }]}>
        {reputation.completedDeals} deal{reputation.completedDeals !== 1 ? 's' : ''} completed
      </Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

function OfferDetailScreen() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { user } = useAuthContext();
  const { offerId } = useLocalSearchParams<{ offerId: string }>();

  const [offer, setOffer] = useState<Offer | null>(null);
  const [events, setEvents] = useState<OfferEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Counter modal
  const [counterVisible, setCounterVisible] = useState(false);
  const [counterPrice, setCounterPrice] = useState('');
  const [counterMessage, setCounterMessage] = useState('');

  // Shipping modal
  const [shipVisible, setShipVisible] = useState(false);
  const [trackingInfo, setTrackingInfo] = useState('');

  // Completion modal
  const [completeVisible, setCompleteVisible] = useState(false);
  const [ratingStars, setRatingStars] = useState(5);
  const [ratingComment, setRatingComment] = useState('');

  // Reputation
  const [sellerRep, setSellerRep] = useState<UserReputation | null>(null);
  const [buyerRep, setBuyerRep] = useState<UserReputation | null>(null);

  const currentUserId = user?.id;
  const isSeller = offer ? currentUserId === offer.sellerId : false;
  const isBuyer = offer ? currentUserId === offer.buyerId : false;

  const loadData = useCallback(async () => {
    if (!offerId) return;
    try {
      const result = await dataProvider.getOfferDetail(offerId);
      setOffer(result.offer);
      setEvents(result.events);

      // Load reputations
      const [sRep, bRep] = await Promise.all([
        dataProvider.getUserReputation(result.offer.sellerId).catch(() => null),
        dataProvider.getUserReputation(result.offer.buyerId).catch(() => null),
      ]);
      setSellerRep(sRep);
      setBuyerRep(bRep);
    } catch (err) {
      showToast({ message: 'Failed to load offer details', type: 'error' });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [offerId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    loadData();
  }, [loadData, settings.hapticsEnabled]);

  // ── Actions ──────────────────────────────────────────────────────────────

  const handleAccept = async () => {
    if (!offerId || actionLoading) return;
    setActionLoading(true);
    try {
      await dataProvider.respondToOffer(offerId, true);
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Offer accepted!', type: 'success' });
      await loadData();
    } catch (err) {
      showToast({ message: 'Failed to accept offer', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleDecline = async () => {
    if (!offerId || actionLoading) return;
    setActionLoading(true);
    try {
      await dataProvider.respondToOffer(offerId, false);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Offer declined', type: 'info' });
      await loadData();
    } catch (err) {
      showToast({ message: 'Failed to decline offer', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!offerId || actionLoading) return;
    setActionLoading(true);
    try {
      await dataProvider.cancelOffer(offerId);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Offer cancelled', type: 'info' });
      await loadData();
    } catch (err) {
      showToast({ message: 'Failed to cancel offer', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleCounter = async () => {
    if (!offerId || !counterPrice.trim() || actionLoading) return;
    const price = parseFloat(counterPrice);
    if (isNaN(price) || price <= 0) {
      showToast({ message: 'Enter a valid price', type: 'error' });
      return;
    }
    setActionLoading(true);
    try {
      await dataProvider.counterOffer(offerId, price, counterMessage.trim() || undefined);
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Counter-offer sent', type: 'success' });
      setCounterVisible(false);
      setCounterPrice('');
      setCounterMessage('');
      await loadData();
    } catch (err) {
      showToast({ message: 'Failed to send counter-offer', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleShip = async () => {
    if (!offerId || actionLoading) return;
    setActionLoading(true);
    try {
      await dataProvider.markShipped(offerId, trackingInfo.trim() || undefined);
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Marked as shipped', type: 'success' });
      setShipVisible(false);
      setTrackingInfo('');
      await loadData();
    } catch (err) {
      showToast({ message: 'Failed to mark as shipped', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleComplete = async () => {
    if (!offerId || actionLoading) return;
    setActionLoading(true);
    try {
      await dataProvider.completeDeal(offerId, ratingStars, ratingComment.trim() || undefined);
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Deal completed! Thanks for rating.', type: 'success' });
      setCompleteVisible(false);
      setRatingStars(5);
      setRatingComment('');
      await loadData();
    } catch (err) {
      showToast({ message: 'Failed to complete deal', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  // Open DM thread
  const handleOpenChat = () => {
    if (!offer?.dmThreadId) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push(`/chat/${encodeURIComponent(offer.dmThreadId)}`);
  };

  if (loading) {
    return (
      <View style={[styles.safeArea, { backgroundColor: colors.background, flex: 1 }]}>
        <Stack.Screen options={{ headerTitle: 'Offer Detail' }} />
        <SkeletonList count={3} type="deal" />
        <QuickNavBar />
      </View>
    );
  }

  if (!offer) {
    return (
      <View style={[styles.safeArea, { backgroundColor: colors.background, flex: 1 }]}>
        <Stack.Screen options={{ headerTitle: 'Offer Detail' }} />
        <View style={styles.errorState}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
          <Text style={[styles.errorText, { color: colors.muted }]}>Offer not found</Text>
        </View>
        <QuickNavBar />
      </View>
    );
  }

  const statusCfg = STATUS_CONFIG[offer.status] || STATUS_CONFIG.proposed;
  const canRespond = isSeller && (offer.status === 'proposed' || offer.status === 'countered');
  const canCounter = (isSeller || isBuyer) && (offer.status === 'proposed' || offer.status === 'countered');
  const canCancel = isBuyer && (offer.status === 'proposed' || offer.status === 'countered');
  const canShip = isSeller && offer.status === 'accepted';
  const canComplete = isBuyer && offer.status === 'accepted';

  return (
    <View style={[styles.safeArea, { backgroundColor: colors.background, flex: 1 }]}>
      <Stack.Screen options={{ headerTitle: 'Offer Detail' }} />

      {/* Chat shortcut above scroll when DM exists */}
      {offer.dmThreadId && (
        <View style={{ flexDirection: 'row', justifyContent: 'flex-end', paddingHorizontal: 16, paddingBottom: 4 }}>
          <AnimatedPressable
            onPress={handleOpenChat}
            style={{ padding: 6 }}
            accessibilityRole="button"
            accessibilityLabel="Open chat"
          >
            <Ionicons name="chatbubble-outline" size={22} color={colors.accent} />
          </AnimatedPressable>
        </View>
      )}

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor={colors.accent}
            colors={[colors.accent]}
          />
        }
      >
        {/* ── Item info card ───────────────────────────────────────────── */}
        <Pressable
          onPress={() => router.push(`/item/${encodeURIComponent(offer.itemId)}`)}
          style={[styles.itemCard, { backgroundColor: colors.card, borderColor: colors.border }]}
          accessibilityRole="button"
          accessibilityLabel={`View item: ${offer.itemTitle}`}
        >
          <View style={[styles.itemThumb, { backgroundColor: colors.background }]}>
            {offer.itemImageUrl ? (
              <Image
                source={{ uri: offer.itemImageUrl }}
                style={styles.itemThumbImage}
                contentFit="cover"
                cachePolicy="disk"
                transition={150}
              />
            ) : (
              <Ionicons name="cube-outline" size={32} color={colors.muted} />
            )}
          </View>
          <View style={styles.itemInfo}>
            <Text style={[styles.itemTitle, { color: colors.text }]} numberOfLines={2}>
              {offer.itemTitle}
            </Text>
            <View style={[styles.statusBadge, { backgroundColor: statusCfg.bg, alignSelf: 'flex-start' }]}>
              <Ionicons name={statusCfg.icon} size={12} color={statusCfg.fg} />
              <Text style={[styles.statusBadgeText, { color: statusCfg.fg }]}>{statusCfg.label}</Text>
            </View>
          </View>
          <View style={styles.itemPriceCol}>
            <Text style={[styles.itemPriceLabel, { color: colors.muted }]}>Current offer</Text>
            <Text style={[styles.itemPrice, { color: colors.accent }]}>
              {formatPrice(offer.currentPrice, (offer.currency || settings.currency) as 'EUR')}
            </Text>
          </View>
        </Pressable>

        {/* ── Reputation row ───────────────────────────────────────────── */}
        <View style={styles.repRow}>
          <ReputationBadge
            label={isSeller ? 'Your reputation (Seller)' : 'Seller'}
            reputation={sellerRep}
            colors={colors}
          />
          <ReputationBadge
            label={isBuyer ? 'Your reputation (Buyer)' : 'Buyer'}
            reputation={buyerRep}
            colors={colors}
          />
        </View>

        {/* ── Timeline ─────────────────────────────────────────────────── */}
        <View style={styles.timelineSection}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Negotiation Timeline</Text>
          {events.length === 0 ? (
            <Text style={[styles.noEvents, { color: colors.muted }]}>No events yet</Text>
          ) : (
            events.map((ev, idx) => {
              const evDisplay = EVENT_DISPLAY[ev.eventType] || {
                icon: 'ellipsis-horizontal-outline' as keyof typeof Ionicons.glyphMap,
                label: ev.eventType,
                color: colors.muted,
              };
              const isLast = idx === events.length - 1;

              return (
                <View key={ev.id} style={styles.timelineItem}>
                  {/* Vertical line */}
                  {!isLast && (
                    <View style={[styles.timelineLine, { backgroundColor: colors.border }]} />
                  )}
                  {/* Dot */}
                  <View style={[styles.timelineDot, { backgroundColor: evDisplay.color }]}>
                    <Ionicons name={evDisplay.icon} size={14} color="#fff" />
                  </View>
                  {/* Content */}
                  <View style={styles.timelineContent}>
                    <Text style={[styles.timelineLabel, { color: colors.text }]}>
                      {evDisplay.label}
                    </Text>
                    {ev.price != null && (
                      <Text style={[styles.timelinePrice, { color: colors.accent }]}>
                        {formatPrice(ev.price, (offer.currency || settings.currency) as 'EUR')}
                      </Text>
                    )}
                    {ev.message ? (
                      <Text style={[styles.timelineMessage, { color: colors.muted }]}>
                        &ldquo;{ev.message}&rdquo;
                      </Text>
                    ) : null}
                    <Text style={[styles.timelineTime, { color: colors.muted }]}>
                      {formatDateTime(ev.createdAt)}
                    </Text>
                  </View>
                </View>
              );
            })
          )}
        </View>

        {/* ── Expiry info ──────────────────────────────────────────────── */}
        {offer.expiresAt && (offer.status === 'proposed' || offer.status === 'countered') && (
          <View style={[styles.expiryBanner, { backgroundColor: '#FEF3C7' }]}>
            <Ionicons name="time-outline" size={16} color="#92400E" />
            <Text style={[styles.expiryText, { color: '#92400E' }]}>
              Expires {relativeTime(offer.expiresAt)}
            </Text>
          </View>
        )}
      </ScrollView>

      {/* ── Action buttons ─────────────────────────────────────────────── */}
      {(canRespond || canCounter || canCancel || canShip || canComplete) && (
        <View style={[styles.actionBar, { backgroundColor: colors.card, borderTopColor: colors.border }]}>
          {actionLoading ? (
            <ActivityIndicator size="small" color={colors.accent} />
          ) : (
            <View style={styles.actionRow}>
              {/* Seller: Accept */}
              {canRespond && (
                <AnimatedPressable
                  onPress={handleAccept}
                  style={[styles.actionBtn, { backgroundColor: '#059669' }]}
                  accessibilityRole="button"
                  accessibilityLabel="Accept offer"
                >
                  <Ionicons name="checkmark-circle" size={18} color="#fff" />
                  <Text style={styles.actionBtnText}>Accept</Text>
                </AnimatedPressable>
              )}

              {/* Seller: Decline */}
              {canRespond && (
                <AnimatedPressable
                  onPress={handleDecline}
                  style={[styles.actionBtn, { backgroundColor: '#DC2626' }]}
                  accessibilityRole="button"
                  accessibilityLabel="Decline offer"
                >
                  <Ionicons name="close-circle" size={18} color="#fff" />
                  <Text style={styles.actionBtnText}>Decline</Text>
                </AnimatedPressable>
              )}

              {/* Both: Counter */}
              {canCounter && (
                <AnimatedPressable
                  onPress={() => {
                    setCounterPrice(String(offer.currentPrice));
                    setCounterVisible(true);
                  }}
                  style={[styles.actionBtn, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Counter offer"
                >
                  <Ionicons name="swap-horizontal" size={18} color="#fff" />
                  <Text style={styles.actionBtnText}>Counter</Text>
                </AnimatedPressable>
              )}

              {/* Buyer: Cancel */}
              {canCancel && (
                <AnimatedPressable
                  onPress={handleCancel}
                  style={[styles.actionBtnOutline, { borderColor: colors.border }]}
                  accessibilityRole="button"
                  accessibilityLabel="Cancel offer"
                >
                  <Ionicons name="ban-outline" size={18} color={colors.muted} />
                  <Text style={[styles.actionBtnOutlineText, { color: colors.muted }]}>Cancel</Text>
                </AnimatedPressable>
              )}

              {/* Seller: Mark Shipped */}
              {canShip && (
                <AnimatedPressable
                  onPress={() => setShipVisible(true)}
                  style={[styles.actionBtn, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Mark as shipped"
                >
                  <Ionicons name="airplane" size={18} color="#fff" />
                  <Text style={styles.actionBtnText}>Mark Shipped</Text>
                </AnimatedPressable>
              )}

              {/* Buyer: Complete */}
              {canComplete && (
                <AnimatedPressable
                  onPress={() => setCompleteVisible(true)}
                  style={[styles.actionBtn, { backgroundColor: '#059669' }]}
                  accessibilityRole="button"
                  accessibilityLabel="Confirm received and rate"
                >
                  <Ionicons name="checkmark-done" size={18} color="#fff" />
                  <Text style={styles.actionBtnText}>Confirm Received</Text>
                </AnimatedPressable>
              )}
            </View>
          )}
        </View>
      )}

      <QuickNavBar />

      {/* ── Counter-offer modal ────────────────────────────────────────── */}
      <Modal
        visible={counterVisible}
        animationType="slide"
        transparent
        onRequestClose={() => setCounterVisible(false)}
      >
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Counter-Offer</Text>
              <Pressable onPress={() => setCounterVisible(false)}>
                <Ionicons name="close" size={24} color={colors.muted} />
              </Pressable>
            </View>

            <Text style={[styles.modalLabel, { color: colors.muted }]}>Your price</Text>
            <TextInput
              style={[styles.modalInput, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
              value={counterPrice}
              onChangeText={setCounterPrice}
              keyboardType="decimal-pad"
              placeholder="0.00"
              placeholderTextColor={colors.muted}
              autoFocus
            />

            <Text style={[styles.modalLabel, { color: colors.muted }]}>Message (optional)</Text>
            <TextInput
              style={[styles.modalTextarea, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
              value={counterMessage}
              onChangeText={setCounterMessage}
              placeholder="Add a message..."
              placeholderTextColor={colors.muted}
              multiline
              maxLength={2000}
            />

            <AnimatedPressable
              onPress={handleCounter}
              disabled={actionLoading || !counterPrice.trim()}
              style={[
                styles.modalConfirmBtn,
                { backgroundColor: colors.accent, opacity: actionLoading || !counterPrice.trim() ? 0.5 : 1 },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Send counter-offer"
            >
              {actionLoading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <Ionicons name="swap-horizontal" size={18} color="#fff" />
                  <Text style={styles.modalConfirmBtnText}>Send Counter-Offer</Text>
                </>
              )}
            </AnimatedPressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ── Shipping modal ─────────────────────────────────────────────── */}
      <Modal
        visible={shipVisible}
        animationType="slide"
        transparent
        onRequestClose={() => setShipVisible(false)}
      >
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Mark as Shipped</Text>
              <Pressable onPress={() => setShipVisible(false)}>
                <Ionicons name="close" size={24} color={colors.muted} />
              </Pressable>
            </View>

            <Text style={[styles.modalLabel, { color: colors.muted }]}>Tracking info (optional)</Text>
            <TextInput
              style={[styles.modalInput, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
              value={trackingInfo}
              onChangeText={setTrackingInfo}
              placeholder="Tracking number or carrier"
              placeholderTextColor={colors.muted}
              autoFocus
              maxLength={500}
            />

            <AnimatedPressable
              onPress={handleShip}
              disabled={actionLoading}
              style={[
                styles.modalConfirmBtn,
                { backgroundColor: colors.accent, opacity: actionLoading ? 0.5 : 1 },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Confirm shipment"
            >
              {actionLoading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <Ionicons name="airplane" size={18} color="#fff" />
                  <Text style={styles.modalConfirmBtnText}>Confirm Shipped</Text>
                </>
              )}
            </AnimatedPressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ── Completion / Rating modal ──────────────────────────────────── */}
      <Modal
        visible={completeVisible}
        animationType="slide"
        transparent
        onRequestClose={() => setCompleteVisible(false)}
      >
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Confirm & Rate</Text>
              <Pressable onPress={() => setCompleteVisible(false)}>
                <Ionicons name="close" size={24} color={colors.muted} />
              </Pressable>
            </View>

            <Text style={[styles.modalLabel, { color: colors.muted }]}>
              Confirm you received the item and rate the seller
            </Text>

            {/* Star picker */}
            <View style={styles.starPicker}>
              {[1, 2, 3, 4, 5].map((star) => (
                <Pressable
                  key={star}
                  onPress={() => setRatingStars(star)}
                  style={styles.starPickerBtn}
                  accessibilityRole="button"
                  accessibilityLabel={`Rate ${star} star${star !== 1 ? 's' : ''}`}
                >
                  <Ionicons
                    name={star <= ratingStars ? 'star' : 'star-outline'}
                    size={36}
                    color="#F59E0B"
                  />
                </Pressable>
              ))}
            </View>

            <Text style={[styles.modalLabel, { color: colors.muted }]}>Comment (optional)</Text>
            <TextInput
              style={[styles.modalTextarea, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
              value={ratingComment}
              onChangeText={setRatingComment}
              placeholder="How was the transaction?"
              placeholderTextColor={colors.muted}
              multiline
              maxLength={2000}
            />

            <AnimatedPressable
              onPress={handleComplete}
              disabled={actionLoading}
              style={[
                styles.modalConfirmBtn,
                { backgroundColor: '#059669', opacity: actionLoading ? 0.5 : 1 },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Complete deal and submit rating"
            >
              {actionLoading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <Ionicons name="checkmark-done" size={18} color="#fff" />
                  <Text style={styles.modalConfirmBtnText}>Complete Deal</Text>
                </>
              )}
            </AnimatedPressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

export default function OfferDetailWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Offer Detail">
      <OfferDetailScreen />
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
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 24,
  },
  errorState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  errorText: {
    fontSize: 15,
    fontWeight: '600',
  },

  // Item card
  itemCard: {
    flexDirection: 'row',
    padding: 12,
    borderRadius: 14,
    borderWidth: 1,
    gap: 12,
    marginBottom: 16,
  },
  itemThumb: {
    width: 72,
    height: 72,
    borderRadius: 12,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemThumbImage: {
    width: 72,
    height: 72,
  },
  itemInfo: {
    flex: 1,
    gap: 8,
  },
  itemTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  statusBadgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
  itemPriceCol: {
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  itemPriceLabel: {
    fontSize: 11,
    marginBottom: 2,
  },
  itemPrice: {
    fontSize: 18,
    fontWeight: '700',
  },

  // Reputation
  repRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 16,
  },
  repBadge: {
    flex: 1,
    padding: 10,
    borderRadius: 10,
    borderWidth: 1,
  },
  repLabel: {
    fontSize: 11,
    fontWeight: '500',
    marginBottom: 4,
  },
  repScore: {
    fontSize: 14,
    fontWeight: '700',
    marginLeft: 6,
  },
  repNoRating: {
    fontSize: 12,
    fontStyle: 'italic',
  },
  repDeals: {
    fontSize: 11,
    marginTop: 4,
  },

  // Timeline
  timelineSection: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 14,
  },
  noEvents: {
    fontSize: 13,
    fontStyle: 'italic',
  },
  timelineItem: {
    flexDirection: 'row',
    paddingLeft: 4,
    marginBottom: 18,
    position: 'relative',
  },
  timelineLine: {
    position: 'absolute',
    left: 15,
    top: 28,
    bottom: -18,
    width: 2,
    borderRadius: 1,
  },
  timelineDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  timelineContent: {
    flex: 1,
    paddingTop: 2,
  },
  timelineLabel: {
    fontSize: 14,
    fontWeight: '600',
  },
  timelinePrice: {
    fontSize: 15,
    fontWeight: '700',
    marginTop: 2,
  },
  timelineMessage: {
    fontSize: 13,
    fontStyle: 'italic',
    marginTop: 4,
    lineHeight: 18,
  },
  timelineTime: {
    fontSize: 11,
    marginTop: 4,
  },

  // Expiry banner
  expiryBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 12,
    borderRadius: 10,
    marginBottom: 16,
  },
  expiryText: {
    fontSize: 13,
    fontWeight: '500',
  },

  // Action bar
  actionBar: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
  },
  actionBtnText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },
  actionBtnOutline: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
  },
  actionBtnOutlineText: {
    fontSize: 13,
    fontWeight: '600',
  },

  // Modals
  modalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  modalSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  modalLabel: {
    fontSize: 13,
    fontWeight: '500',
    marginBottom: 6,
    marginTop: 8,
  },
  modalInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
  },
  modalTextarea: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    minHeight: 80,
    textAlignVertical: 'top',
  },
  modalConfirmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 20,
  },
  modalConfirmBtnText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
  },

  // Star picker
  starPicker: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
  },
  starPickerBtn: {
    padding: 4,
  },
});
