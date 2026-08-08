/**
 * Watchlist Tab Screen — track prices and drops for items you want.
 * No custom header (Stack header is unified).
 */

import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useModal } from '@/hooks/useModal';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  Modal,
  Alert,
  ActivityIndicator,
  Animated,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type WatchlistItem } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useAuthContext } from '@/providers/useAuthContext';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { formatPrice } from '@/lib/format';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useTranslation } from 'react-i18next';
import { useToast } from '@/components/Toast';
import logger from '@/utils/logger';
import { track } from '@/analytics/track';
import { radius, spacing, text, fontWeight, shadow } from '@/theme/tokens';
import MarketplacePickerSheet from '@/components/MarketplacePickerSheet';
import { collectorsApi } from '@/api/collectorsApi';
import type { P2PWatchlistMatch } from '@/api/p2pApi';
import type { CurrencyCode } from '@/data/types';
import { WishlistStatsBar } from '@/components/wishlist/WishlistStatsBar';
import { WishlistSortControls } from '@/components/wishlist/WishlistSortControls';

// Pull from single source of truth — all 36 categories + "Other"
import { CATEGORIES as ALL_CATS, CATEGORY_NAME_TO_SLUG } from '@/constants/categories';

const CONGRATS_DISPLAY_DURATION = 2000;
const CONGRATS_SPRING = { tension: 50, friction: 7, useNativeDriver: true as const };
const CATEGORIES = [...ALL_CATS.map((c) => c.name), 'Other'];

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function WatchlistTabScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { user } = useAuthContext();
  const { settings } = useSettings();
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const [items, setItems] = useState<WatchlistItem[]>([]);
  // Distinct from "no items". A failed read used to render the empty state,
  // which told the user their watchlist was empty when it simply had not
  // loaded — and the watchlist is the paid feature's input, so "it emptied"
  // is the worst possible wrong message. docs/ui-playbook.md: Empty != loading,
  // and by the same argument Empty != failed.
  const [loadError, setLoadError] = useState<string | null>(null);
  // watchlist row id -> the cheapest live member listing for that item.
  const [matches, setMatches] = useState<Record<string, P2PWatchlistMatch>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modalVisible, openModal, closeModal] = useModal();
  const [saving, setSaving] = useState(false);

  // Form state
  const [formTitle, setFormTitle] = useState('');
  const [formCategory, setFormCategory] = useState('');
  const [formTargetPrice, setFormTargetPrice] = useState('');
  const [formNotes, setFormNotes] = useState('');
  const [categoryPickerVisible, openCategoryPicker, closeCategoryPicker] = useModal();

  // Edit target price state
  const [editTargetModalVisible, openEditTargetModal, closeEditTargetModal] = useModal();
  const [editTargetItem, setEditTargetItem] = useState<WatchlistItem | null>(null);
  const [editTargetValue, setEditTargetValue] = useState('');
  const [editTargetSaving, setEditTargetSaving] = useState(false);

  // Shop state — which watchlist row the marketplace picker is open for
  const [shopItem, setShopItem] = useState<WatchlistItem | null>(null);

  // "I Got It!" acquisition state
  const [acquireModalVisible, openAcquireModal, closeAcquireModal] = useModal();
  const [acquireItem, setAcquireItem] = useState<WatchlistItem | null>(null);
  const [acquirePrice, setAcquirePrice] = useState('');
  const [acquireNotes, setAcquireNotes] = useState('');
  const [acquiring, setAcquiring] = useState(false);
  const [showCongrats, setShowCongrats] = useState(false);
  const congratsScale = useRef(new Animated.Value(0)).current;
  const congratsOpacity = useRef(new Animated.Value(0)).current;
  const congratsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up congrats timer on unmount
  useEffect(() => {
    return () => {
      if (congratsTimerRef.current) clearTimeout(congratsTimerRef.current);
    };
  }, []);

  const loadItems = useCallback(async () => {
    try {
      const data = await dataProvider.listWatchlist(user?.id ?? 'current-user');
      setItems(data);
      setLoadError(null);
    } catch (err) {
      logger.error('[Watchlist] loadItems error:', err);
      // Keep whatever was already on screen. Blanking the list on a refresh
      // failure would reproduce the exact bug this state exists to fix.
      setLoadError(err instanceof Error ? err.message : 'Could not load your watchlist');
      showToast({ message: 'Failed to load watchlist. Pull down to retry.', type: 'error' });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?.id]);

  // Member listings for what the user watches — the pull side of Target Hit.
  //
  // Fetched SEPARATELY from the watchlist rather than awaited alongside it, and
  // deliberately not gating `loading`. A marketplace hiccup must never keep the
  // watchlist itself off screen: the list is the feature, this is an
  // enrichment. On failure the rows simply render without the extra line, which
  // is the honest degrade — no row claims something is for sale that isn't.
  const loadMatches = useCallback(async () => {
    try {
      const { matches: rows } = await collectorsApi.listWatchlistMatches();
      // Keyed by watchlist row id, which is what renderItem has in hand. The
      // server already returns the cheapest listing per row, so a plain
      // last-wins map is correct here rather than a reduce.
      const byRow: Record<string, P2PWatchlistMatch> = {};
      for (const m of rows) byRow[m.watchlist_id] = m;
      setMatches(byRow);
    } catch (err) {
      // NO TOAST — this is additive, and telling the user their watchlist
      // failed because an enrichment call did would be false.
      //
      // But logger.ERROR, not warn: info/warn are stripped from release builds
      // (CLAUDE.md), so a warn here is invisible on TestFlight and production —
      // the exact builds where a silently-missing marketplace row matters. The
      // "don't alarm the user" judgement belongs to the toast, not to whether
      // the failure leaves a trace at all.
      logger.error('[Watchlist] marketplace matches unavailable:', err);
    }
  }, []);

  useEffect(() => {
    loadItems();
    loadMatches();
  }, [loadItems, loadMatches]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    loadItems();
    // Refreshed together: a member listing is the most time-sensitive thing on
    // this screen, and a pull that reloaded stale marketplace data would be
    // worse than not showing it.
    loadMatches();
  }, [loadItems, loadMatches]);

  const resetForm = () => {
    setFormTitle('');
    setFormCategory('');
    setFormTargetPrice('');
    setFormNotes('');
  };

  const handleAdd = async () => {
    if (!formTitle.trim()) {
      showToast({ message: 'Please enter a title.', type: 'warning' });
      return;
    }
    if (!formCategory) {
      showToast({ message: 'Please select a category.', type: 'warning' });
      return;
    }
    // A target price is REQUIRED, not optional. This is the third guard and it
    // is the one that decides whether the row does anything at all:
    // `deal_discovery_worker._check_watchlist_snipes` filters
    // `WHERE w.target_price IS NOT NULL AND w.target_price > 0`, so a row
    // without one is skipped forever. It is not a degraded row — it is an
    // invisible one.
    //
    // It used to be optional, and `WatchlistItemCard` rendered a
    // "No target — won't alert" chip afterwards (added 2026-08-05). Measured
    // 2026-08-08: still zero rows with a target. Telling someone AFTER they
    // saved, on a row they have stopped looking at, does not work.
    //
    // Blocking here is the smaller cost. Free is capped at ONE Target Hit per
    // day (`max_daily_deal_alerts`), so a single working row is the entire
    // demonstration of the paid feature — and a user whose first row is inert
    // never sees the feature at all, waits, and concludes the alerts are
    // broken.
    const parsedTarget = formTargetPrice.trim()
      ? parseFloat(formTargetPrice.replace(/[^0-9.,]/g, '').replace(',', '.'))
      : NaN;
    if (!Number.isFinite(parsedTarget) || parsedTarget <= 0) {
      showToast({
        // Says what the number DOES, not that a field is missing. "Required"
        // reads as bureaucracy; this reads as the reason to type it.
        message: "Set a target price — that's the price we alert you at.",
        type: 'warning',
      });
      return;
    }

    setSaving(true);
    try {
      const targetPrice = parsedTarget;

      // Write the SLUG, not the display name. `formCategory` comes from
      // CATEGORIES = ALL_CATS.map(c => c.name), so this used to store
      // "Magic: The Gathering" while `market_hits.category` holds "mtg" — and
      // the snipe's fallback arm joins on `mh.category = w.category`, so a row
      // added here could never match a listing. WatchlistItemCard already
      // assumed a slug (`categoryDisplayName(item.category)`), so the display
      // was the thing that was wrong-by-luck, not the storage contract.
      const categorySlug = CATEGORY_NAME_TO_SLUG[formCategory] ?? 'unknown';

      await dataProvider.addWatchlistItem({
        title: formTitle.trim(),
        category: categorySlug,
        targetPrice,
        notes: formNotes.trim() || undefined,
      });

      // The target price IS the alert \u2014 no `user_price_alerts` rule is created.
      //
      // This used to also POST /alerts/mine with a `below_threshold` rule and
      // toast "Price alert created \u2014 we'll notify you...". That rule could
      // never fire: price_monitor_worker.check_threshold_alerts filters
      // `AND a.item_id IS NOT NULL` (:84) and a watchlist row is not an `items`
      // uuid, so the rule was skipped every cycle. Measured against prod
      // 2026-08-05: 4 rules, all below_threshold, all item_id NULL, and ZERO
      // below_threshold rows in alert_trigger_history, ever.
      //
      // What actually watches this number is deal_discovery_worker's snipe
      // check, which reads watchlist_items.target_price directly and needs no
      // rule at all. So promise that, and only that.
      if (targetPrice && !isNaN(targetPrice) && targetPrice > 0) {
        showToast({
          message: `Target set \u2014 we'll alert you if it's listed below ${formatPrice(targetPrice, settings.currency)}`,
          type: 'success',
        });
      }

      track({ name: 'watchlist_item_added', properties: { category: categorySlug } });
      closeModal();
      resetForm();
      loadItems();
    } catch (err: any) {
      showToast({ message: err?.message || 'Failed to add item.', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = (item: WatchlistItem) => {
    fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
    Alert.alert(
      'Remove from Watchlist',
      `Remove "${item.title}" from your watchlist?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            try {
              await dataProvider.removeWatchlistItem(item.id);
              loadItems();
            } catch (err: any) {
              showToast({ message: err?.message || 'Failed to remove item.', type: 'error' });
            }
          },
        },
      ]
    );
  };

  // Edit target price flow
  const handleEditTarget = (item: WatchlistItem) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setEditTargetItem(item);
    setEditTargetValue(item.targetPrice?.toString() || '');
    openEditTargetModal();
  };

  const handleSaveTargetPrice = async () => {
    if (!editTargetItem) return;
    setEditTargetSaving(true);
    try {
      const newTarget = editTargetValue.trim()
        ? parseFloat(editTargetValue.replace(/[^0-9.,]/g, '').replace(',', '.'))
        : null;

      await dataProvider.updateWatchlistItem(editTargetItem.id, {
        targetPrice: newTarget && !isNaN(newTarget) ? newTarget : null,
      });

      // No `user_price_alerts` rule is created here either — see the
      // add-item path above for the measurement. The target itself is what
      // deal_discovery_worker's snipe check reads.
      if (newTarget && !isNaN(newTarget) && newTarget > 0) {
        fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
        showToast({
          message: `Target set \u2014 we'll alert you if it's listed below ${formatPrice(newTarget, settings.currency)}`,
          type: 'success',
        });
      } else {
        showToast({ message: 'Target price updated', type: 'success' });
      }

      closeEditTargetModal();
      setEditTargetItem(null);
      setEditTargetValue('');
      loadItems();
    } catch (err: any) {
      showToast({ message: err?.message || 'Failed to update target price.', type: 'error' });
    } finally {
      setEditTargetSaving(false);
    }
  };

  // Shop flow — open the marketplace picker for this row.
  //
  // This used to fetch the links itself and open `links[0]` blind. Two problems:
  // eBay was appended first for every category, so an MTG single always landed
  // on eBay US with Cardmarket unused further down the list; and the raw
  // Linking.openURL bypassed openAffiliateUrl, so the click never reached
  // demand_signals. MarketplacePickerSheet does both correctly and was already
  // built — it just had no callers.
  const handleShop = (item: WatchlistItem) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setShopItem(item);
  };

  // "I Got It!" flow
  const handleGotIt = (item: WatchlistItem) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setAcquireItem(item);
    setAcquirePrice(item.targetPrice?.toString() || '');
    setAcquireNotes('');
    openAcquireModal();
  };

  const playCongrats = () => {
    setShowCongrats(true);
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

    // Animate in
    Animated.parallel([
      Animated.spring(congratsScale, {
        toValue: 1,
        ...CONGRATS_SPRING,
      }),
      Animated.timing(congratsOpacity, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start();

    // Animate out after delay
    if (congratsTimerRef.current) clearTimeout(congratsTimerRef.current);
    congratsTimerRef.current = setTimeout(() => {
      Animated.parallel([
        Animated.timing(congratsScale, {
          toValue: 0,
          duration: 300,
          useNativeDriver: true,
        }),
        Animated.timing(congratsOpacity, {
          toValue: 0,
          duration: 300,
          useNativeDriver: true,
        }),
      ]).start(() => {
        setShowCongrats(false);
        congratsScale.setValue(0);
        congratsOpacity.setValue(0);
      });
    }, CONGRATS_DISPLAY_DURATION);
  };

  const handleConfirmAcquire = async () => {
    if (!acquireItem) return;

    setAcquiring(true);
    try {
      const actualPrice = acquirePrice.trim()
        ? parseFloat(acquirePrice.replace(/[^0-9.,]/g, '').replace(',', '.'))
        : undefined;

      await dataProvider.convertWatchlistToItem(
        acquireItem.id,
        actualPrice && !isNaN(actualPrice) ? actualPrice : undefined,
        acquireNotes.trim() || undefined
      );

      closeAcquireModal();
      setAcquireItem(null);
      setAcquirePrice('');
      setAcquireNotes('');

      // Show congrats animation
      playCongrats();

      // Reload list
      loadItems();
    } catch (err: any) {
      showToast({ message: err?.message || 'Failed to add to collection.', type: 'error' });
    } finally {
      setAcquiring(false);
    }
  };

  // M2: Memoize sorted watchlist items (sorted by priority: high > medium > low)
  const sortedItems = useMemo(() => {
    const priorityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
    return [...items].sort(
      (a, b) => (priorityOrder[a.priority ?? 'low'] ?? 2) - (priorityOrder[b.priority ?? 'low'] ?? 2),
    );
  }, [items]);

  const renderItem = ({ item }: { item: WatchlistItem }) => {
    const priorityColor =
      item.priority === 'high'
        ? colors.danger
        : item.priority === 'medium'
        ? colors.warning
        : colors.success;

    return (
      <View style={[styles.itemCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.itemHeader}>
          <View style={styles.itemTitleRow}>
            <View style={[styles.priorityDot, { backgroundColor: priorityColor }]} />
            <Text style={[styles.itemTitle, { color: colors.text }]} numberOfLines={1}>
              {item.title}
            </Text>
          </View>
          <AnimatedPressable onPress={() => handleRemove(item)} style={styles.removeBtn} accessibilityRole="button" accessibilityLabel={`Remove ${item.title} from watchlist`}>
            <Ionicons name="close-circle" size={22} color={colors.muted} />
          </AnimatedPressable>
        </View>

        <View style={styles.itemMeta}>
          {item.category && (
            <View style={[styles.categoryBadge, { backgroundColor: colors.accent + '20' }]}>
              <Text style={[styles.categoryText, { color: colors.accent }]}>{item.category}</Text>
            </View>
          )}
          <AnimatedPressable
            onPress={() => handleEditTarget(item)}
            style={styles.targetPressable}
            accessibilityRole="button"
            accessibilityLabel={item.targetPrice !== null ? `Target: ${formatPrice(item.targetPrice, settings.currency)}. Tap to edit` : 'Set target price'}
          >
            {item.targetPrice !== null ? (
              <Text style={[styles.targetPrice, { color: colors.text }]}>
                Target: {formatPrice(item.targetPrice, settings.currency)}
              </Text>
            ) : (
              <Text style={[styles.setTargetText, { color: colors.accent }]}>
                Set target price
              </Text>
            )}
            <Ionicons name="pencil-outline" size={12} color={colors.muted} />
          </AnimatedPressable>
        </View>

        {/* A MEMBER is selling this, right now.
            The marketplace and the watchlist were built separately and never
            met on screen: someone could be watching a Bayou while another
            member had one listed, and only a push firing at the right moment
            would connect them — miss it and the two halves never meet again.
            This is the pull side of Target Hit, same exact-identity join, no
            time window.
            Placed above notes and the date because it is the only line here
            that is actionable right now. */}
        {matches[item.id] ? (
          <AnimatedPressable
            onPress={() => router.push({
              pathname: '/listing/[id]',
              params: { id: matches[item.id].listing_id },
            })}
            style={[
              styles.memberListing,
              {
                // Accent only when the user's OWN number is met — that is the
                // Target Hit condition. Everything else is a plain fact and
                // must not shout, or the distinction stops meaning anything.
                backgroundColor: matches[item.id].meets_target
                  ? colors.accent + '18'
                  : colors.background,
                borderColor: matches[item.id].meets_target
                  ? colors.accent + '55'
                  : colors.border,
              },
            ]}
            accessibilityRole="button"
            accessibilityLabel={
              matches[item.id].meets_target
                ? `A member is selling ${item.title} for ${formatPrice(matches[item.id].price, matches[item.id].currency as CurrencyCode)}, which meets your target. Open the listing`
                : `A member is selling ${item.title} for ${formatPrice(matches[item.id].price, matches[item.id].currency as CurrencyCode)}. Open the listing`
            }
          >
            <Ionicons
              name={matches[item.id].meets_target ? 'flash' : 'storefront-outline'}
              size={14}
              color={matches[item.id].meets_target ? colors.accent : colors.muted}
            />
            <Text
              style={[
                styles.memberListingText,
                { color: matches[item.id].meets_target ? colors.accent : colors.text },
              ]}
              numberOfLines={1}
            >
              {matches[item.id].meets_target ? 'Target met — ' : 'A member is selling this — '}
              {/* The listing's OWN currency, not the viewer's. The server sends
                  what the seller set; converting here without their rate would
                  print a number the listing screen then contradicts. */}
              {formatPrice(matches[item.id].price, matches[item.id].currency as CurrencyCode)}
            </Text>
            <Ionicons name="chevron-forward" size={14} color={colors.muted} />
          </AnimatedPressable>
        ) : null}

        {item.notes && (
          <Text style={[styles.notes, { color: colors.muted }]} numberOfLines={2}>
            {item.notes}
          </Text>
        )}

        {item.createdAt && (
          <Text style={[styles.dateAdded, { color: colors.muted }]}>
            Added {formatDate(item.createdAt)}
          </Text>
        )}

        {/* Action buttons */}
        <View style={styles.cardActions}>
          <AnimatedPressable
            style={[styles.shopBtn, { borderColor: colors.accent }]}
            onPress={() => handleShop(item)}
            accessibilityRole="button"
            accessibilityLabel={`Shop for ${item.title}`}
          >
            <Ionicons name="cart-outline" size={16} color={colors.accent} />
            <Text style={[styles.shopBtnText, { color: colors.accent }]}>Shop</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.gotItBtn, { backgroundColor: colors.accent }]}
            onPress={() => handleGotIt(item)}
            accessibilityRole="button"
            accessibilityLabel={`Mark ${item.title} as acquired`}
          >
            <Ionicons name="checkmark-circle" size={18} color={colors.accentText} />
            <Text style={[styles.gotItBtnText, { color: colors.accentText }]}>I Got It!</Text>
          </AnimatedPressable>
        </View>
      </View>
    );
  };

  const renderEmpty = () => (
    // FAILED and EMPTY are different states and must not share a rendering.
    // "No items in your watchlist yet" on a failed read tells the user their
    // saved items are gone — and this list feeds the alert they pay for, so
    // that message costs trust the app cannot easily win back.
    loadError ? (
      <View style={styles.emptyContainer}>
        <View style={[styles.emptyIconWrap, { backgroundColor: colors.danger + '15' }]}>
          <Ionicons name="cloud-offline-outline" size={40} color={colors.danger} />
        </View>
        <Text style={[styles.emptyTitle, { color: colors.text }]}>
          Couldn&apos;t load your watchlist
        </Text>
        <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
          Your saved items are safe — we just couldn&apos;t reach them. Check your
          connection and try again.
        </Text>
        <AnimatedPressable
          style={[styles.emptyBtn, { backgroundColor: colors.accent }]}
          onPress={() => { setLoading(true); loadItems(); loadMatches(); }}
          accessibilityRole="button"
          accessibilityLabel="Try loading your watchlist again"
        >
          <Ionicons name="refresh" size={18} color={colors.accentText} />
          <Text style={[styles.emptyBtnText, { color: colors.accentText }]}>Try again</Text>
        </AnimatedPressable>
      </View>
    ) : (
    <View style={styles.emptyContainer}>
      <View style={[styles.emptyIconWrap, { backgroundColor: colors.accent + '15' }]}>
        <Ionicons name="eye-outline" size={40} color={colors.accent} />
      </View>
      <Text style={[styles.emptyTitle, { color: colors.text }]}>{t('wishlist.empty_title')}</Text>
      <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
        Track prices, get alerts when items drop, and never miss a deal on items you want.
      </Text>
      <AnimatedPressable
        style={[styles.emptyBtn, { backgroundColor: colors.accent }]}
        onPress={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          openModal();
        }}
        accessibilityRole="button"
        accessibilityLabel={t('wishlist.add_first_a11y')}
      >
        <Ionicons name="add" size={18} color={colors.accentText} />
        <Text style={[styles.emptyBtnText, { color: colors.accentText }]}>{t('wishlist.add_first')}</Text>
      </AnimatedPressable>
      <View style={styles.emptyFeatures}>
        <View style={styles.emptyFeatureRow}>
          <Ionicons name="notifications-outline" size={16} color={colors.muted} />
          <Text style={[styles.emptyFeatureText, { color: colors.muted }]}>{t('wishlist.feature_price_drops')}</Text>
        </View>
        <View style={styles.emptyFeatureRow}>
          <Ionicons name="trending-down-outline" size={16} color={colors.muted} />
          <Text style={[styles.emptyFeatureText, { color: colors.muted }]}>{t('wishlist.feature_target_price')}</Text>
        </View>
        <View style={styles.emptyFeatureRow}>
          <Ionicons name="flash-outline" size={16} color={colors.muted} />
          <Text style={[styles.emptyFeatureText, { color: colors.muted }]}>{t('wishlist.feature_member_listings')}</Text>
        </View>
      </View>
    </View>
    )
  );

  // ONE inbox. app/alerts.tsx used to live here and rendered
  // `alert_trigger_history` while app/notifications.tsx rendered
  // `notification_history` — two screens for one event, since
  // deal_discovery_worker writes both for every Target Hit. Merged 2026-08-08.
  const handleAlertsPress = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push('/notifications');
  }, [router, settings.hapticsEnabled]);

  // Bulk entry. watchlist-builder was previously reachable ONLY from the alerts
  // screen; with that screen merged into /notifications this is its sole route.
  const handleBulkPress = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push('/watchlist-builder');
  }, [router, settings.hapticsEnabled]);

  const handleAddPress = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    openModal();
  }, [settings.hapticsEnabled, openModal]);

  const renderHeader = () => (
    <>
      <WishlistSortControls onAlertsPress={handleAlertsPress} onAddPress={handleAddPress} onBulkPress={handleBulkPress} />
      <WishlistStatsBar items={items} currency={settings.currency} />
    </>
  );

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right', 'top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right', 'top']}>
      <Animated.View style={[{ flex: 1 }, animatedStyle]}>
        <FlashList
          data={sortedItems}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          ListHeaderComponent={renderHeader}
          contentContainerStyle={[
            styles.listContent,
            sortedItems.length === 0 && styles.listContentEmpty,
          ]}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.accent} />}
          ListEmptyComponent={renderEmpty}
        />
      </Animated.View>

      {/* Add Modal */}
      <Modal visible={modalVisible} animationType="slide" transparent onRequestClose={() => { closeModal(); resetForm(); }}>
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>{t('wishlist.add_to_watchlist')}</Text>
              <AnimatedPressable onPress={() => { closeModal(); resetForm(); }} accessibilityRole="button" accessibilityLabel={t('wishlist.close_add_form_a11y')}>
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>

            {/* Title */}
            <Text style={[styles.label, { color: colors.text }]}>{t('wishlist.title_required')}</Text>
            <TextInput
              value={formTitle}
              onChangeText={setFormTitle}
              placeholder="e.g. Charizard VMAX Rainbow"
              placeholderTextColor={colors.muted}
              style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
              accessibilityLabel={t('wishlist.title_a11y')}
            />

            {/* Category */}
            <Text style={[styles.label, { color: colors.text }]}>{t('wishlist.category_required')}</Text>
            <AnimatedPressable
              style={[styles.input, styles.pickerBtn, { backgroundColor: colors.background, borderColor: colors.border }]}
              onPress={() => openCategoryPicker()}
              accessibilityRole="button"
              accessibilityLabel={formCategory ? `Category: ${formCategory}. Tap to change` : "Select category"}
            >
              <Text style={{ color: formCategory ? colors.text : colors.muted }}>
                {formCategory || 'Select category'}
              </Text>
              <Ionicons name="chevron-down" size={18} color={colors.muted} />
            </AnimatedPressable>

            {/* Target Price */}
            <Text style={[styles.label, { color: colors.text }]}>Target Price ({settings.currency})</Text>
            <TextInput
              value={formTargetPrice}
              onChangeText={setFormTargetPrice}
              placeholder="e.g. 350"
              placeholderTextColor={colors.muted}
              keyboardType="numeric"
              style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
              accessibilityLabel={`Target price in ${settings.currency}`}
            />

            {/* Notes */}
            <Text style={[styles.label, { color: colors.text }]}>Notes</Text>
            <TextInput
              value={formNotes}
              onChangeText={setFormNotes}
              placeholder="e.g. Looking for PSA 9 or higher"
              placeholderTextColor={colors.muted}
              multiline
              numberOfLines={3}
              style={[styles.input, styles.textArea, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
              accessibilityLabel="Notes"
            />

            {/* Save Button */}
            <AnimatedPressable
              style={[styles.saveBtn, { backgroundColor: colors.accent }]}
              onPress={handleAdd}
              disabled={saving}
              accessibilityRole="button"
              accessibilityLabel={t('wishlist.add_to_watchlist_a11y')}
            >
              {saving ? (
                <ActivityIndicator size="small" color={colors.accentText} />
              ) : (
                <Text style={[styles.saveBtnText, { color: colors.accentText }]}>{t('wishlist.add_to_watchlist')}</Text>
              )}
            </AnimatedPressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Category Picker Modal */}
      <Modal visible={categoryPickerVisible} animationType="slide" transparent onRequestClose={() => closeCategoryPicker()}>
        <AnimatedPressable
          style={styles.pickerOverlay}
          onPress={() => closeCategoryPicker()}
          accessibilityRole="button"
          accessibilityLabel={t('wishlist.close_category_picker_a11y')}
        >
          <View style={[styles.pickerContent, { backgroundColor: colors.card }]}>
            <Text style={[styles.pickerTitle, { color: colors.text }]}>{t('wishlist.select_category')}</Text>
            {CATEGORIES.map((cat) => (
              <AnimatedPressable
                key={cat}
                style={[
                  styles.pickerItem,
                  formCategory === cat && { backgroundColor: colors.accent + '20' },
                ]}
                onPress={() => {
                  setFormCategory(cat);
                  closeCategoryPicker();
                }}
                accessibilityRole="button"
                accessibilityLabel={`${cat}${formCategory === cat ? ', selected' : ''}`}
              >
                <Text style={[styles.pickerItemText, { color: colors.text }]}>{cat}</Text>
                {formCategory === cat && (
                  <Ionicons name="checkmark" size={20} color={colors.accent} />
                )}
              </AnimatedPressable>
            ))}
          </View>
        </AnimatedPressable>
      </Modal>

      {/* "I Got It!" Acquisition Modal */}
      <Modal visible={acquireModalVisible} animationType="slide" transparent onRequestClose={() => { closeAcquireModal(); setAcquireItem(null); }}>
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>{t('wishlist.add_to_collection')}</Text>
              <AnimatedPressable onPress={() => { closeAcquireModal(); setAcquireItem(null); }} accessibilityRole="button" accessibilityLabel={t('wishlist.close_acquisition_a11y')}>
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>

            {acquireItem && (
              <>
                <View style={[styles.acquireItemPreview, { backgroundColor: colors.background }]}>
                  <Text style={[styles.acquireItemTitle, { color: colors.text }]} numberOfLines={2}>
                    {acquireItem.title}
                  </Text>
                  {acquireItem.category && (
                    <View style={[styles.categoryBadge, { backgroundColor: colors.accent + '20' }]}>
                      <Text style={[styles.categoryText, { color: colors.accent }]}>{acquireItem.category}</Text>
                    </View>
                  )}
                </View>

                <Text style={[styles.label, { color: colors.text }]}>What did you pay? ({settings.currency})</Text>
                <TextInput
                  value={acquirePrice}
                  onChangeText={setAcquirePrice}
                  placeholder={acquireItem.targetPrice ? `Target was €${acquireItem.targetPrice}` : 'e.g. 150'}
                  placeholderTextColor={colors.muted}
                  keyboardType="numeric"
                  style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
                  accessibilityLabel={t('wishlist.price_paid_a11y')}
                />
                <Text style={[styles.helperText, { color: colors.muted }]}>
                  This helps improve price predictions for everyone
                </Text>

                <Text style={[styles.label, { color: colors.text }]}>{t('wishlist.notes_optional')}</Text>
                <TextInput
                  value={acquireNotes}
                  onChangeText={setAcquireNotes}
                  placeholder="e.g. Found at local shop, great condition"
                  placeholderTextColor={colors.muted}
                  multiline
                  numberOfLines={2}
                  style={[styles.input, styles.textArea, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
                  accessibilityLabel={t('wishlist.notes_a11y')}
                />

                <AnimatedPressable
                  style={[styles.acquireBtn, { backgroundColor: colors.accent }]}
                  onPress={handleConfirmAcquire}
                  disabled={acquiring}
                  accessibilityRole="button"
                  accessibilityLabel={t('wishlist.add_to_my_collection_a11y')}
                >
                  {acquiring ? (
                    <ActivityIndicator size="small" color={colors.accentText} />
                  ) : (
                    <>
                      <Ionicons name="checkmark-circle" size={20} color={colors.accentText} />
                      <Text style={[styles.acquireBtnText, { color: colors.accentText }]}>{t('wishlist.add_to_my_collection')}</Text>
                    </>
                  )}
                </AnimatedPressable>
              </>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Edit Target Price Modal */}
      <Modal visible={editTargetModalVisible} animationType="slide" transparent onRequestClose={() => { closeEditTargetModal(); setEditTargetItem(null); }}>
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>{t('wishlist.set_target_price')}</Text>
              <AnimatedPressable onPress={() => { closeEditTargetModal(); setEditTargetItem(null); }} accessibilityRole="button" accessibilityLabel={t('wishlist.close_target_edit_a11y')}>
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>

            {editTargetItem && (
              <>
                <View style={[styles.acquireItemPreview, { backgroundColor: colors.background }]}>
                  <Text style={[styles.acquireItemTitle, { color: colors.text }]} numberOfLines={2}>
                    {editTargetItem.title}
                  </Text>
                  {editTargetItem.category && (
                    <View style={[styles.categoryBadge, { backgroundColor: colors.accent + '20' }]}>
                      <Text style={[styles.categoryText, { color: colors.accent }]}>{editTargetItem.category}</Text>
                    </View>
                  )}
                </View>

                <Text style={[styles.label, { color: colors.text }]}>Target Price ({settings.currency})</Text>
                <TextInput
                  value={editTargetValue}
                  onChangeText={setEditTargetValue}
                  placeholder="e.g. 350"
                  placeholderTextColor={colors.muted}
                  keyboardType="numeric"
                  autoFocus
                  style={[styles.input, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
                  accessibilityLabel={t('wishlist.target_price_input_a11y')}
                />
                <Text style={[styles.helperText, { color: colors.muted }]}>
                  A price alert will be created automatically when you set a target price.
                </Text>

                <AnimatedPressable
                  style={[styles.saveBtn, { backgroundColor: colors.accent }]}
                  onPress={handleSaveTargetPrice}
                  disabled={editTargetSaving}
                  accessibilityRole="button"
                  accessibilityLabel={t('wishlist.save_target_a11y')}
                >
                  {editTargetSaving ? (
                    <ActivityIndicator size="small" color={colors.accentText} />
                  ) : (
                    <Text style={[styles.saveBtnText, { color: colors.accentText }]}>{t('wishlist.save_target_button')}</Text>
                  )}
                </AnimatedPressable>
              </>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Marketplace picker — opened by the Shop button on a watchlist row.
          The target price becomes a hard ceiling on the search, so the results
          are things the user would actually buy rather than every listing that
          shares a word with the title. */}
      <MarketplacePickerSheet
        visible={shopItem !== null}
        onClose={() => setShopItem(null)}
        itemTitle={shopItem?.title ?? ''}
        categoryId={shopItem?.category}
        maxPrice={shopItem?.targetPrice}
        maxPriceCurrency={shopItem?.currency}
      />

      {/* Congrats Overlay */}
      {showCongrats && (
        <View style={styles.congratsOverlay}>
          <Animated.View
            style={[
              styles.congratsContent,
              {
                backgroundColor: colors.card,
                transform: [{ scale: congratsScale }],
                opacity: congratsOpacity,
              },
            ]}
          >
            <View style={[styles.congratsIconWrap, { backgroundColor: colors.success + '20' }]}>
              <Ionicons name="trophy" size={48} color={colors.success} />
            </View>
            <Text style={[styles.congratsTitle, { color: colors.text }]}>Congrats!</Text>
            <Text style={[styles.congratsSubtitle, { color: colors.muted }]}>
              Added to your collection
            </Text>
          </Animated.View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  listContentEmpty: {
    flex: 1,
  },
  itemCard: {
    borderRadius: radius.md,
    padding: 14,
    borderWidth: 1,
    ...shadow.card,
  },
  itemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  itemTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginRight: 8,
  },
  priorityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  itemTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
    flex: 1,
  },
  removeBtn: {
    padding: 4,
  },
  itemMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 10,
  },
  categoryBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.md,
  },
  categoryText: {
    fontSize: text.sm,
    fontWeight: fontWeight.medium,
  },
  targetPrice: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  targetPressable: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  setTargetText: {
    fontSize: text.sm,
    fontWeight: fontWeight.medium,
  },
  memberListing: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.sm,
    paddingHorizontal: 10, paddingVertical: 9,
    marginTop: spacing.xs,
  },
  // flex: 1 so the chevron stays pinned right and the title truncates instead
  // of pushing it off the card.
  memberListingText: { flex: 1, fontSize: text.xs, fontWeight: fontWeight.semibold },
  notes: {
    fontSize: text.md,
    marginTop: 8,
    lineHeight: 18,
  },
  dateAdded: {
    fontSize: text.sm,
    marginTop: 6,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
    paddingTop: 60,
  },
  emptyTitle: {
    fontSize: text.xl,
    fontWeight: fontWeight.bold,
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: text.md,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },
  emptyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: radius.xl,
    marginTop: 24,
    gap: 6,
  },
  emptyBtnText: {
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
  },
  emptyIconWrap: {
    width: 80,
    height: 80,
    borderRadius: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyFeatures: {
    marginTop: 32,
    gap: 12,
  },
  emptyFeatureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  emptyFeatureText: {
    fontSize: text.md,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
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
  label: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    borderRadius: radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: text.lg,
    borderWidth: 1,
  },
  textArea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  pickerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  saveBtn: {
    marginTop: 24,
    paddingVertical: 14,
    borderRadius: radius.xl,
    alignItems: 'center',
  },
  saveBtnText: {
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
  },
  pickerOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  pickerContent: {
    width: '100%',
    borderRadius: radius.md,
    padding: 16,
  },
  pickerTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
    marginBottom: 12,
    textAlign: 'center',
  },
  pickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: radius.xs,
  },
  pickerItemText: {
    fontSize: text.lg,
  },
  // Action button row
  cardActions: {
    flexDirection: 'row',
    marginTop: 12,
    gap: 8,
  },
  shopBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radius.pill,
    borderWidth: 1,
    gap: 6,
  },
  shopBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  gotItBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radius.pill,
    gap: 6,
  },
  gotItBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  // Acquire modal styles
  acquireItemPreview: {
    padding: 14,
    borderRadius: radius.md,
    marginBottom: 16,
  },
  acquireItemTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
    marginBottom: 8,
  },
  acquireBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
    paddingVertical: 14,
    borderRadius: radius.xl,
    gap: 8,
  },
  acquireBtnText: {
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
  },
  helperText: {
    fontSize: text.sm,
    marginTop: 4,
    marginBottom: 8,
  },
  // Congrats overlay styles
  congratsOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1000,
  },
  congratsContent: {
    alignItems: 'center',
    padding: 32,
    borderRadius: radius.xl,
    minWidth: 240,
  },
  congratsIconWrap: {
    width: 88,
    height: 88,
    borderRadius: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  congratsTitle: {
    fontSize: text['2xl'],
    fontWeight: fontWeight.bold,
    marginBottom: 4,
  },
  congratsSubtitle: {
    fontSize: text.md,
  },
});

export default function WatchlistTabScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Wishlist">
      <WatchlistTabScreen />
    </ScreenErrorBoundary>
  );
}
