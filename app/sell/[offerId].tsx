/**
 * Offer Detail — P2P Deal Desk negotiation screen.
 *
 * Shows item info, negotiation timeline, action buttons based on role + status,
 * counter-offer modal, shipping/completion flows, and reputation display.
 */

import React, { useState, useEffect, useCallback } from 'react';
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
  Alert,
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
import { track } from '@/analytics/track';
import { collectorsApi } from '@/api/collectorsApi';
import logger from '@/utils/logger';
import { timeAgo } from '@/lib/timeAgo';
import { STATUS_LABELS } from '@/constants/dealStatus';
import { radius, text, fontWeight } from '@/theme/tokens';
import { OfferTimeline } from '@/components/sell/OfferTimeline';
import { CounterOfferForm } from '@/components/sell/CounterOfferForm';
import { ReputationBadges } from '@/components/sell/ReputationBadges';
import { SELLING_ENABLED } from '@/config/featureFlags';
import { SellingUnavailable } from '@/components/sell/SellingUnavailable';

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

// Status labels + icons — badge colors come from useAppTheme().status tokens
const STATUS_META: Record<OfferStatus, { label: string; icon: keyof typeof Ionicons.glyphMap }> = {
  proposed: { label: STATUS_LABELS.proposed, icon: 'hourglass-outline' },
  countered: { label: STATUS_LABELS.countered, icon: 'swap-horizontal-outline' },
  accepted: { label: STATUS_LABELS.accepted, icon: 'checkmark-circle-outline' },
  declined: { label: STATUS_LABELS.declined, icon: 'close-circle-outline' },
  expired: { label: STATUS_LABELS.expired, icon: 'time-outline' },
  completed: { label: STATUS_LABELS.completed, icon: 'checkmark-done-outline' },
  cancelled: { label: STATUS_LABELS.cancelled, icon: 'ban-outline' },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '';
  return timeAgo(iso);
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

function OfferDetailScreen() {
  const { colors, status: statusTokens } = useAppTheme();
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
  // Risk flags
  const [riskFlags, setRiskFlags] = useState<{ flag: string; severity: string; message: string }[]>([]);

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

      // Load risk flags (non-blocking)
      collectorsApi.getDealRiskFlags(offerId)
        .then((data) => {
          const flags = (data as Record<string, unknown>)?.flags;
          if (Array.isArray(flags)) setRiskFlags(flags);
        })
        .catch((err) => { logger.warn('[OfferDetail] risk flags fetch failed:', err); });
    } catch (err) {
      logger.error('[OfferDetail] action failed:', err);
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

  const handleAccept = () => {
    if (!offerId || actionLoading) return;
    Alert.alert(
      'Accept Offer',
      `Accept this offer for ${offer ? formatPrice(offer.currentPrice, (offer.currency || settings.currency) as 'EUR') : 'the listed price'}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Accept',
          onPress: async () => {
            setActionLoading(true);
            try {
              await dataProvider.respondToOffer(offerId, true);
              fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
              showToast({ message: 'Offer accepted!', type: 'success' });
              track({ name: 'offer_created', properties: { offer_id: offerId as string } });
              await loadData();
            } catch (err) {
              logger.error('[OfferDetail] action failed:', err);
              showToast({ message: 'Failed to accept offer', type: 'error' });
            } finally {
              setActionLoading(false);
            }
          },
        },
      ],
    );
  };

  const handleDecline = () => {
    if (!offerId || actionLoading) return;
    Alert.alert(
      'Decline Offer',
      'Are you sure you want to decline this offer? This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Decline',
          style: 'destructive',
          onPress: async () => {
            setActionLoading(true);
            try {
              await dataProvider.respondToOffer(offerId, false);
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              showToast({ message: 'Offer declined', type: 'info' });
              await loadData();
            } catch (err) {
              logger.error('[OfferDetail] action failed:', err);
              showToast({ message: 'Failed to decline offer', type: 'error' });
            } finally {
              setActionLoading(false);
            }
          },
        },
      ],
    );
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
      logger.error('[OfferDetail] action failed:', err);
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
      logger.error('[OfferDetail] action failed:', err);
      showToast({ message: 'Failed to send counter-offer', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleShip = () => {
    if (!offerId || actionLoading) return;
    Alert.alert(
      'Confirm Shipment',
      'Mark this item as shipped? The buyer will be notified.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Confirm',
          onPress: async () => {
            setActionLoading(true);
            try {
              await dataProvider.markShipped(offerId, trackingInfo.trim() || undefined);
              fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
              showToast({ message: 'Marked as shipped', type: 'success' });
              setShipVisible(false);
              setTrackingInfo('');
              await loadData();
            } catch (err) {
              logger.error('[OfferDetail] action failed:', err);
              showToast({ message: 'Failed to mark as shipped', type: 'error' });
            } finally {
              setActionLoading(false);
            }
          },
        },
      ],
    );
  };

  const handleComplete = async () => {
    if (!offerId || actionLoading) return;
    setActionLoading(true);
    try {
      await dataProvider.completeDeal(offerId, ratingStars, ratingComment.trim() || undefined);
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Deal completed! Thanks for rating.', type: 'success' });
      track({ name: 'deal_completed', properties: { offer_id: offerId as string } });
      setCompleteVisible(false);
      setRatingStars(5);
      setRatingComment('');
      await loadData();
    } catch (err) {
      logger.error('[OfferDetail] action failed:', err);
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

  const statusMeta = STATUS_META[offer.status] || STATUS_META.proposed;
  const statusCfg = { ...statusMeta, ...(statusTokens[offer.status] || statusTokens.proposed) };
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
                cachePolicy="memory-disk"
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
        <ReputationBadges
          isSeller={isSeller}
          isBuyer={isBuyer}
          sellerRep={sellerRep}
          buyerRep={buyerRep}
        />

        {/* ── Risk flags ────────────────────────────────────────────────── */}
        {riskFlags.length > 0 && (
          <View style={[styles.riskSection, { backgroundColor: colors.warningBg, borderColor: colors.border }]}>
            <View style={styles.riskHeader}>
              <Ionicons name="warning-outline" size={16} color={colors.warning} />
              <Text style={[styles.riskTitle, { color: colors.warning }]}>Risk Flags</Text>
            </View>
            {riskFlags.map((rf, i) => (
              <Text key={i} style={[styles.riskText, { color: colors.text }]}>
                {rf.severity === 'high' ? '\u26A0' : '\u24D8'} {rf.message}
              </Text>
            ))}
          </View>
        )}

        {/* ── Timeline ─────────────────────────────────────────────────── */}
        <OfferTimeline events={events} currency={offer.currency || settings.currency} />

        {/* ── Expiry info ──────────────────────────────────────────────── */}
        {offer.expiresAt && (offer.status === 'proposed' || offer.status === 'countered') && (
          <View style={[styles.expiryBanner, { backgroundColor: colors.warningBg }]}>
            <Ionicons name="time-outline" size={16} color={colors.warning} />
            <Text style={[styles.expiryText, { color: colors.warning }]}>
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
                  style={[styles.actionBtn, { backgroundColor: colors.success }]}
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
                  style={[styles.actionBtn, { backgroundColor: colors.danger }]}
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
                  style={[styles.actionBtn, { backgroundColor: colors.success }]}
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
      <CounterOfferForm
        visible={counterVisible}
        onClose={() => setCounterVisible(false)}
        onSubmit={handleCounter}
        counterPrice={counterPrice}
        onCounterPriceChange={setCounterPrice}
        counterMessage={counterMessage}
        onCounterMessageChange={setCounterMessage}
        actionLoading={actionLoading}
      />

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
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                    setRatingStars(star);
                  }}
                  style={styles.starPickerBtn}
                  accessibilityRole="button"
                  accessibilityLabel={`Rate ${star} star${star !== 1 ? 's' : ''}`}
                >
                  <Ionicons
                    name={star <= ratingStars ? 'star' : 'star-outline'}
                    size={36}
                    color={colors.warning}
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
                { backgroundColor: colors.success, opacity: actionLoading ? 0.5 : 1 },
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
  if (!SELLING_ENABLED) return <SellingUnavailable title="Offer" />;
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
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
  },

  // Item card
  itemCard: {
    flexDirection: 'row',
    padding: 12,
    borderRadius: radius.md,
    borderWidth: 1,
    gap: 12,
    marginBottom: 16,
  },
  itemThumb: {
    width: 72,
    height: 72,
    borderRadius: radius.md,
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
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.xs,
  },
  statusBadgeText: {
    fontSize: text.xs,
    fontWeight: fontWeight.semibold,
  },
  itemPriceCol: {
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  itemPriceLabel: {
    fontSize: text.xs,
    marginBottom: 2,
  },
  itemPrice: {
    fontSize: text.xl,
    fontWeight: fontWeight.bold,
  },

  // Risk flags
  riskSection: {
    padding: 12,
    borderRadius: radius.sm,
    borderWidth: 1,
    marginBottom: 16,
  },
  riskHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 6,
  },
  riskTitle: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  riskText: {
    fontSize: text.sm,
    lineHeight: 18,
    marginBottom: 2,
  },
  // Expiry banner
  expiryBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 12,
    borderRadius: radius.sm,
    marginBottom: 16,
  },
  expiryText: {
    fontSize: text.md,
    fontWeight: fontWeight.medium,
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
    borderRadius: radius.sm,
  },
  actionBtnText: {
    color: '#fff',
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  actionBtnOutline: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: radius.sm,
    borderWidth: 1,
  },
  actionBtnOutlineText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },

  // Modals (shipping + completion — counter-offer is now in CounterOfferForm)
  modalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  modalSheet: {
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
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
    fontSize: text.xl,
    fontWeight: fontWeight.bold,
  },
  modalLabel: {
    fontSize: text.md,
    fontWeight: fontWeight.medium,
    marginBottom: 6,
    marginTop: 8,
  },
  modalInput: {
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: text.lg,
  },
  modalTextarea: {
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: text.md,
    minHeight: 80,
    textAlignVertical: 'top',
  },
  modalConfirmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: radius.md,
    marginTop: 20,
  },
  modalConfirmBtnText: {
    color: '#fff',
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
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
