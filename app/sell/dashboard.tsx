/**
 * Seller Dashboard — Multi-marketplace listing management.
 *
 * Shows active listings across marketplaces, sales history with revenue breakdown,
 * connected marketplace accounts, and fee comparisons.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useModal } from '@/hooks/useModal';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  Alert,
} from 'react-native';
import { router, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { dataProvider } from '@/data';
import { collectorsApi } from '@/api/collectorsApi';
import logger from '@/utils/logger';
import { fireHaptic, HapticIntent } from '@/haptics';
import { radius, text, fontWeight, gap, shadow } from '@/theme/tokens';
import { formatPrice } from '@/lib/format';
import { EmptyState } from '@/components/EmptyState';
import { SkeletonList } from '@/components/Skeleton';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { AnimatedPressable } from '@/motion';
import { SwipeableRow, SwipeActions } from '@/components/SwipeableRow';
import { useAsync } from '@/hooks/useAsync';
import { MARKETPLACE_BRAND_COLORS } from '@/constants/colors';
import { useFormField, validateAll } from '@/hooks/useFormField';
import { compose, required, maxLength, positiveNumber } from '@/lib/validate';
import { CreateListingModal } from '@/components/sell/CreateListingModal';
import { ConnectMarketplaceModal } from '@/components/sell/ConnectMarketplaceModal';
import { PredictionCompsCard } from '@/components/sell/PredictionCompsCard';
import type {
  MarketplaceListing,
  MarketplaceSale,
  MarketplaceAccount,
  MarketplaceFeeSchedule,
  ListingStatus,
  MarketplaceId,
  CurrencyCode,
} from '@/data/types';

// ---------------------------------------------------------------------------
// Marketplace branding
// ---------------------------------------------------------------------------

const MARKETPLACE_CONFIG: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap; color: string }> = {
  collectai: { label: 'CollectAI P2P', icon: 'people-outline', color: MARKETPLACE_BRAND_COLORS.collectai.color },
  ebay: { label: 'eBay', icon: 'cart-outline', color: MARKETPLACE_BRAND_COLORS.ebay.color },
  mercari: { label: 'Mercari', icon: 'storefront-outline', color: MARKETPLACE_BRAND_COLORS.mercari.color },
  cardmarket: { label: 'Cardmarket', icon: 'card-outline', color: MARKETPLACE_BRAND_COLORS.cardmarket.color },
  stockx: { label: 'StockX', icon: 'trending-up-outline', color: MARKETPLACE_BRAND_COLORS.stockx.color },
  bricklink: { label: 'BrickLink', icon: 'cube-outline', color: MARKETPLACE_BRAND_COLORS.bricklink.color },
  tcgplayer: { label: 'TCGPlayer', icon: 'layers-outline', color: MARKETPLACE_BRAND_COLORS.tcgplayer.color },
  discogs: { label: 'Discogs', icon: 'disc-outline', color: MARKETPLACE_BRAND_COLORS.discogs.color },
};

// Status badge colors pulled from tokens at render time via useAppTheme().status
const STATUS_LABELS: Record<ListingStatus, string> = {
  draft: 'Draft',
  active: 'Active',
  sold: 'Sold',
  expired: 'Expired',
  delisted: 'Delisted',
  error: 'Error',
};

// ---------------------------------------------------------------------------
// Tab type
// ---------------------------------------------------------------------------

type Tab = 'listings' | 'sales' | 'accounts';

// ---------------------------------------------------------------------------
// ListingCard
// ---------------------------------------------------------------------------

const ListingCard = React.memo(function ListingCard({
  listing,
  colors,
  status: statusTokens,
  currency,
}: {
  listing: MarketplaceListing;
  colors: ReturnType<typeof useAppTheme>['colors'];
  status: ReturnType<typeof useAppTheme>['status'];
  currency: CurrencyCode;
}) {
  const mp = MARKETPLACE_CONFIG[listing.marketplaceId] ?? MARKETPLACE_CONFIG.collectai;
  const statusCfg = statusTokens[listing.status as keyof typeof statusTokens] ?? statusTokens.draft;

  return (
    <AnimatedPressable
      onPress={() => {
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        // Navigate to listing detail (future screen)
      }}
      style={[styles.listingCard, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="button"
      accessibilityLabel={`${listing.listingTitle} on ${mp.label}, ${STATUS_LABELS[listing.status] ?? listing.status}, ${formatPrice(listing.price, currency)}`}
    >
      <View style={styles.listingTop}>
        {/* Marketplace badge */}
        <View style={[styles.mpBadge, { backgroundColor: mp.color + '15' }]}>
          <Ionicons name={mp.icon} size={12} color={mp.color} />
          <Text style={[styles.mpBadgeText, { color: mp.color }]}>{mp.label}</Text>
        </View>

        {/* Status badge */}
        <View style={[styles.statusBadge, { backgroundColor: statusCfg.bg }]}>
          <Text style={[styles.statusBadgeText, { color: statusCfg.fg }]}>{STATUS_LABELS[listing.status] ?? listing.status}</Text>
        </View>
      </View>

      <Text style={[styles.listingTitle, { color: colors.text }]} numberOfLines={2}>
        {listing.listingTitle}
      </Text>

      <View style={styles.listingMeta}>
        <Text style={[styles.listingPrice, { color: colors.text }]}>
          {formatPrice(listing.price, currency)}
        </Text>
        {listing.estimatedNet != null && (
          <Text style={[styles.listingNet, { color: colors.muted }]}>
            Net: {formatPrice(listing.estimatedNet, currency)}
          </Text>
        )}
      </View>

      {/* Metrics row */}
      <View style={styles.metricsRow}>
        <View style={styles.metricItem}>
          <Ionicons name="eye-outline" size={13} color={colors.muted} />
          <Text style={[styles.metricText, { color: colors.muted }]}>{listing.viewsCount}</Text>
        </View>
        <View style={styles.metricItem}>
          <Ionicons name="heart-outline" size={13} color={colors.muted} />
          <Text style={[styles.metricText, { color: colors.muted }]}>{listing.watchersCount}</Text>
        </View>
        <View style={styles.metricItem}>
          <Ionicons name="chatbubble-outline" size={13} color={colors.muted} />
          <Text style={[styles.metricText, { color: colors.muted }]}>{listing.offersCount}</Text>
        </View>
        {listing.format !== 'fixed_price' && (
          <View style={[styles.formatBadge, { borderColor: colors.border }]}>
            <Text style={[styles.formatText, { color: colors.muted }]}>
              {listing.format === 'auction' ? 'Auction' : 'Best Offer'}
            </Text>
          </View>
        )}
      </View>

      {listing.syncedAt && (
        <Text style={[styles.syncedText, { color: colors.muted }]}>
          Synced {new Date(listing.syncedAt).toLocaleDateString()}
        </Text>
      )}
    </AnimatedPressable>
  );
});

// ---------------------------------------------------------------------------
// SaleCard
// ---------------------------------------------------------------------------

const SaleCard = React.memo(function SaleCard({
  sale,
  colors,
  currency,
}: {
  sale: MarketplaceSale;
  colors: ReturnType<typeof useAppTheme>['colors'];
  currency: CurrencyCode;
}) {
  return (
    <View style={[styles.saleCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.saleTop}>
        <Text style={[styles.salePrice, { color: colors.text }]}>
          {formatPrice(sale.salePrice, currency)}
        </Text>
        <View style={[styles.statusBadge, { backgroundColor: colors.successBg }]}>
          <Text style={[styles.statusBadgeText, { color: colors.success }]}>
            {sale.status === 'completed' ? 'Completed' : sale.status.charAt(0).toUpperCase() + sale.status.slice(1)}
          </Text>
        </View>
      </View>

      {sale.buyerName && (
        <Text style={[styles.saleBuyer, { color: colors.muted }]} numberOfLines={1}>
          Buyer: {sale.buyerName}
        </Text>
      )}

      {/* Financial breakdown */}
      <View style={[styles.financialRow, { borderTopColor: colors.border }]}>
        <View style={styles.financialItem}>
          <Text style={[styles.financialLabel, { color: colors.muted }]}>Fees</Text>
          <Text style={[styles.financialValue, { color: colors.error }]}>
            -{formatPrice((sale.platformFee ?? 0) + (sale.paymentProcessingFee ?? 0), currency)}
          </Text>
        </View>
        {sale.shippingCostActual != null && sale.shippingCostActual > 0 && (
          <View style={styles.financialItem}>
            <Text style={[styles.financialLabel, { color: colors.muted }]}>Shipping</Text>
            <Text style={[styles.financialValue, { color: colors.muted }]}>
              -{formatPrice(sale.shippingCostActual, currency)}
            </Text>
          </View>
        )}
        <View style={styles.financialItem}>
          <Text style={[styles.financialLabel, { color: colors.muted }]}>Net</Text>
          <Text style={[styles.financialValue, { color: colors.success }]}>
            {formatPrice(sale.netProceeds, currency)}
          </Text>
        </View>
      </View>

      <Text style={[styles.saleDate, { color: colors.muted }]}>
        {new Date(sale.soldAt).toLocaleDateString()}
      </Text>
    </View>
  );
});

// ---------------------------------------------------------------------------
// AccountCard
// ---------------------------------------------------------------------------

const AccountCard = React.memo(function AccountCard({
  account,
  colors,
}: {
  account: MarketplaceAccount;
  colors: ReturnType<typeof useAppTheme>['colors'];
}) {
  const mp = MARKETPLACE_CONFIG[account.marketplaceId] ?? MARKETPLACE_CONFIG.collectai;

  return (
    <View style={[styles.accountCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={[styles.accountIcon, { backgroundColor: mp.color + '15' }]}>
        <Ionicons name={mp.icon} size={24} color={mp.color} />
      </View>
      <View style={styles.accountInfo}>
        <Text style={[styles.accountName, { color: colors.text }]}>{mp.label}</Text>
        {account.sellerName && (
          <Text style={[styles.accountSeller, { color: colors.muted }]} numberOfLines={1}>
            {account.sellerName}
          </Text>
        )}
        <Text style={[styles.accountDate, { color: colors.muted }]}>
          Connected {new Date(account.connectedAt).toLocaleDateString()}
        </Text>
      </View>
      <View style={[
        styles.accountStatusDot,
        { backgroundColor: account.isActive ? colors.success : colors.error },
      ]} />
    </View>
  );
});

// ---------------------------------------------------------------------------
// Revenue Summary Card
// ---------------------------------------------------------------------------

const RevenueSummary = React.memo(function RevenueSummary({
  sales,
  colors,
  currency,
}: {
  sales: MarketplaceSale[];
  colors: ReturnType<typeof useAppTheme>['colors'];
  currency: CurrencyCode;
}) {
  const totals = useMemo(() => {
    let gross = 0;
    let fees = 0;
    let net = 0;
    for (const s of sales) {
      gross += s.salePrice;
      fees += (s.platformFee ?? 0) + (s.paymentProcessingFee ?? 0);
      net += s.netProceeds;
    }
    return { gross, fees, net, count: sales.length };
  }, [sales]);

  if (totals.count === 0) return null;

  return (
    <View style={[styles.summaryCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <Text style={[styles.summaryTitle, { color: colors.text }]}>Revenue Summary</Text>
      <View style={styles.summaryRow}>
        <View style={styles.summaryItem}>
          <Text style={[styles.summaryLabel, { color: colors.muted }]}>Gross</Text>
          <Text style={[styles.summaryValue, { color: colors.text }]}>
            {formatPrice(totals.gross, currency)}
          </Text>
        </View>
        <View style={styles.summaryItem}>
          <Text style={[styles.summaryLabel, { color: colors.muted }]}>Fees</Text>
          <Text style={[styles.summaryValue, { color: colors.error }]}>
            -{formatPrice(totals.fees, currency)}
          </Text>
        </View>
        <View style={styles.summaryItem}>
          <Text style={[styles.summaryLabel, { color: colors.muted }]}>Net</Text>
          <Text style={[styles.summaryValue, { color: colors.success }]}>
            {formatPrice(totals.net, currency)}
          </Text>
        </View>
      </View>
      <Text style={[styles.summaryCount, { color: colors.muted }]}>
        {totals.count} {totals.count === 1 ? 'sale' : 'sales'} completed
      </Text>
    </View>
  );
});

// ---------------------------------------------------------------------------
// Main Screen
// ---------------------------------------------------------------------------

function SellerDashboardScreen() {
  const { colors, status: statusTokens } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();

  const [tab, setTab] = useState<Tab>('listings');
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState<ListingStatus | 'all'>('all');

  // Create Listing modal state
  const [showCreateModal, openCreateModal, closeCreateModal] = useModal();
  const createTitleField = useFormField(compose(required('Title'), maxLength('Title', 200)));
  const createPriceField = useFormField(compose(required('Price'), positiveNumber('Price')));
  const [createMarketplace, setCreateMarketplace] = useState<MarketplaceId>('collectai');
  const [creating, setCreating] = useState(false);

  // Connect marketplace modal state
  const [showConnectModal, openConnectModal, closeConnectModal] = useModal();
  const [connectMp, setConnectMp] = useState<MarketplaceId>('ebay');
  const [connectName, setConnectName] = useState('');
  const [connecting, setConnecting] = useState(false);

  const { data: dashboardData, loading, error: dashboardError, retry: loadData } = useAsync(
    () => Promise.all([
      dataProvider.listMarketplaceListings(),
      dataProvider.listMarketplaceSales(),
      dataProvider.listMarketplaceAccounts(),
      dataProvider.getMarketplaceFeeSchedules(),
    ]).then(([ls, sl, ac, fees]) => ({
      listings: ls,
      sales: sl,
      accounts: ac,
      feeSchedules: fees,
    })),
    [],
  );

  const listings = dashboardData?.listings ?? [];
  const sales = dashboardData?.sales ?? [];
  const accounts = dashboardData?.accounts ?? [];
  const feeSchedules = dashboardData?.feeSchedules ?? [];

  // Actuals vs Predicted (L2)
  const [predictionComps, setPredictionComps] = useState<Array<{ item_key: string; predicted: number; actual: number; category: string }>>([]);
  useEffect(() => {
    let cancelled = false;
    collectorsApi.getPredictionAccuracy()
      .then((data) => {
        if (cancelled) return;
        const resp = data as { comparisons?: Array<{ item_key: string; predicted: number; actual: number; category: string }> } | undefined;
        if (Array.isArray(resp?.comparisons)) setPredictionComps(resp!.comparisons.slice(0, 6));
      })
      .catch((err) => logger.warn('[SellerDash] prediction accuracy fetch failed:', err));
    return () => { cancelled = true; };
  }, []);

  // Show toast on error
  useEffect(() => {
    if (dashboardError) {
      showToast({ message: 'Failed to load seller data', type: 'error' });
    }
  }, [dashboardError, showToast]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    loadData();
    // refreshing will be cleared when useAsync finishes (loading goes false)
  }, [loadData, settings.hapticsEnabled]);

  // Clear refreshing when loading completes
  useEffect(() => {
    if (!loading) setRefreshing(false);
  }, [loading]);

  // Swipe actions for listings
  const handleDelist = useCallback((listing: MarketplaceListing) => {
    Alert.alert('Delist item?', `Remove "${listing.listingTitle}" from marketplace?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delist', style: 'destructive', onPress: async () => {
          try {
            await dataProvider.deleteMarketplaceListing(listing.id);
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
            showToast({ message: 'Listing removed', type: 'success' });
            loadData();
          } catch (err) { logger.warn('[SellerDash] action failed:', err); showToast({ message: 'Failed to delist', type: 'error' }); }
        },
      },
    ]);
  }, [loadData, showToast]);

  // Create listing handler
  const handleCreateListing = useCallback(async () => {
    if (!validateAll(createTitleField, createPriceField)) return;

    const title = createTitleField.value.trim();
    const price = parseFloat(createPriceField.value.replace(/[^\d.]/g, ''));

    setCreating(true);
    try {
      await dataProvider.createMarketplaceListing({
        itemId: '',
        marketplaceId: createMarketplace,
        listingTitle: title,
        price,
        quantity: 1,
        currency: settings.currency,
        format: 'fixed_price',
        status: 'draft',
      });
      fireHaptic(HapticIntent.JUDGMENT_LOCKED);
      showToast({ message: 'Listing created as draft', type: 'success' });
      closeCreateModal();
      createTitleField.reset();
      createPriceField.reset();
      loadData();
    } catch (err) { logger.warn('[SellerDash] action failed:', err); showToast({ message: 'Failed to create listing', type: 'error' }); }
    finally { setCreating(false); }
  }, [createTitleField, createPriceField, createMarketplace, settings.currency, loadData, showToast]);

  // Disconnect marketplace account
  const handleDisconnect = useCallback((account: MarketplaceAccount) => {
    Alert.alert('Disconnect Account?', `Remove ${MARKETPLACE_CONFIG[account.marketplaceId]?.label ?? account.marketplaceId} connection?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Disconnect', style: 'destructive', onPress: async () => {
        try {
          await collectorsApi.disconnectMarketplaceAccount(account.id);
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
          showToast({ message: 'Account disconnected', type: 'success' });
          loadData();
        } catch (err) { logger.warn('[SellerDash] action failed:', err); showToast({ message: 'Failed to disconnect', type: 'error' }); }
      }},
    ]);
  }, [loadData, showToast]);

  // Connect marketplace account
  const handleConnect = useCallback(async () => {
    if (connecting) return;
    setConnecting(true);
    try {
      await collectorsApi.connectMarketplaceAccount({ marketplace_id: connectMp, seller_name: connectName.trim() || undefined });
      fireHaptic(HapticIntent.JUDGMENT_LOCKED);
      showToast({ message: 'Account connected!', type: 'success' });
      closeConnectModal();
      setConnectName('');
      loadData();
    } catch (err) { logger.warn('[SellerDash] action failed:', err); showToast({ message: 'Failed to connect account', type: 'error' }); }
    finally { setConnecting(false); }
  }, [connectMp, connectName, connecting, loadData, showToast]);

  // Fee preview logic moved to CreateListingModal component

  // Filter listings by status
  const filteredListings = useMemo(() => {
    if (statusFilter === 'all') return listings;
    return listings.filter((l) => l.status === statusFilter);
  }, [listings, statusFilter]);

  // Count by status
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: listings.length };
    for (const l of listings) {
      counts[l.status] = (counts[l.status] ?? 0) + 1;
    }
    return counts;
  }, [listings]);

  const renderListing = useCallback(
    ({ item }: { item: MarketplaceListing }) => (
      <SwipeableRow
        rightActions={[
          ...(item.status === 'active' ? [SwipeActions.delete(() => handleDelist(item))] : []),
        ]}
        enableHaptics={settings.hapticsEnabled}
      >
        <ListingCard listing={item} colors={colors} status={statusTokens} currency={settings.currency} />
      </SwipeableRow>
    ),
    [colors, statusTokens, settings.currency, settings.hapticsEnabled, handleDelist],
  );

  const renderSale = useCallback(
    ({ item }: { item: MarketplaceSale }) => (
      <SaleCard sale={item} colors={colors} currency={settings.currency} />
    ),
    [colors, settings.currency],
  );

  const renderAccount = useCallback(
    ({ item }: { item: MarketplaceAccount }) => (
      <SwipeableRow
        rightActions={[SwipeActions.delete(() => handleDisconnect(item))]}
        enableHaptics={settings.hapticsEnabled}
      >
        <AccountCard account={item} colors={colors} />
      </SwipeableRow>
    ),
    [colors, settings.hapticsEnabled, handleDisconnect],
  );

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: 'Seller Dashboard' }} />

      {/* Tab bar */}
      <View style={[styles.tabBar, { borderBottomColor: colors.border }]}>
        {(['listings', 'sales', 'accounts'] as Tab[]).map((t) => (
          <Pressable
            key={t}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              setTab(t);
            }}
            style={[
              styles.tabBtn,
              tab === t && { borderBottomColor: colors.accent, borderBottomWidth: 2 },
            ]}
            accessibilityRole="tab"
            accessibilityLabel={`${t.charAt(0).toUpperCase() + t.slice(1)} tab`}
            accessibilityState={{ selected: tab === t }}
          >
            <Text style={[styles.tabBtnText, { color: tab === t ? colors.accent : colors.muted }]}>
              {t === 'listings' ? `Listings (${listings.length})` : t === 'sales' ? `Sales (${sales.length})` : `Accounts (${accounts.length})`}
            </Text>
          </Pressable>
        ))}
      </View>

      {loading && !refreshing ? (
        <SkeletonList count={4} type="deal" />
      ) : tab === 'listings' ? (
        <>
          {/* Status filter chips */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterRow} contentContainerStyle={styles.filterContent}>
            {(['all', 'active', 'draft', 'sold', 'expired', 'delisted', 'error'] as const).map((s) => {
              const count = statusCounts[s] ?? 0;
              if (s !== 'all' && count === 0) return null;
              const isActive = statusFilter === s;
              return (
                <Pressable
                  key={s}
                  onPress={() => setStatusFilter(s)}
                  style={[
                    styles.filterChip,
                    { borderColor: isActive ? colors.accent : colors.border },
                    isActive && { backgroundColor: colors.accent + '15' },
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel={`Filter by ${s === 'all' ? 'all statuses' : s}`}
                  accessibilityState={{ selected: isActive }}
                >
                  <Text style={[styles.filterChipText, { color: isActive ? colors.accent : colors.muted }]}>
                    {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)} ({count})
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>

          {filteredListings.length === 0 ? (
            statusFilter !== 'all' ? (
              <EmptyState
                icon="filter-outline"
                title={`No ${statusFilter} listings`}
                subtitle={`You don't have any ${statusFilter} listings right now. Try a different filter or create a new listing.`}
                colors={colors}
                action={
                  <Pressable onPress={() => setStatusFilter('all')} accessibilityRole="button" accessibilityLabel="Show all listings">
                    <Text style={{ color: colors.accent, fontWeight: fontWeight.semibold, marginTop: 8 }}>Show All Listings</Text>
                  </Pressable>
                }
              />
            ) : (
              <EmptyState
                icon="rocket-outline"
                title="Ready to start selling?"
                subtitle="List your collectibles across eBay, Mercari, Cardmarket, and more -- all from one dashboard. Tap the + button to create your first listing!"
                colors={colors}
                action={
                  <Pressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); openCreateModal(); }} accessibilityRole="button" accessibilityLabel="Create your first listing">
                    <Text style={{ color: colors.accent, fontWeight: fontWeight.semibold, marginTop: 8 }}>Create Your First Listing</Text>
                  </Pressable>
                }
              />
            )
          ) : (
            <FlatList
              data={filteredListings}
              renderItem={renderListing}
              keyExtractor={(item) => item.id}
              contentContainerStyle={styles.listContent}
              removeClippedSubviews={true}
              maxToRenderPerBatch={10}
              windowSize={5}
              refreshControl={
                <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.accent} />
              }
            />
          )}
        </>
      ) : tab === 'sales' ? (
        <FlatList
          data={sales}
          renderItem={renderSale}
          keyExtractor={(item) => item.id}
          ListHeaderComponent={<RevenueSummary sales={sales} colors={colors} currency={settings.currency} />}
          ListFooterComponent={predictionComps.length > 0 ? (
            <PredictionCompsCard comparisons={predictionComps} currency={settings.currency} />
          ) : null}
          ListEmptyComponent={
            <EmptyState
              icon="cash-outline"
              title="No sales yet"
              subtitle="When your listings sell, revenue details will appear here"
              colors={colors}
            />
          }
          contentContainerStyle={styles.listContent}
          removeClippedSubviews={true}
          maxToRenderPerBatch={10}
          windowSize={5}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.accent} />
          }
        />
      ) : (
        <FlatList
          data={accounts}
          renderItem={renderAccount}
          keyExtractor={(item) => item.id}
          ListHeaderComponent={
            <AnimatedPressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                openConnectModal();
              }}
              style={[styles.connectBtn, { borderColor: colors.accent, backgroundColor: colors.accent + '10' }]}
              accessibilityRole="button"
              accessibilityLabel="Connect a marketplace account"
            >
              <Ionicons name="add-circle-outline" size={18} color={colors.accent} />
              <Text style={[styles.connectBtnText, { color: colors.accent }]}>Connect Marketplace</Text>
            </AnimatedPressable>
          }
          ListEmptyComponent={
            <EmptyState
              icon="link-outline"
              title="No accounts connected"
              subtitle="Connect your eBay, Mercari, or other marketplace accounts to list items directly"
              colors={colors}
            />
          }
          contentContainerStyle={styles.listContent}
          removeClippedSubviews={true}
          maxToRenderPerBatch={10}
          windowSize={5}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.accent} />
          }
        />
      )}

      {/* Create Listing FAB */}
      {!loading && tab === 'listings' && (
        <AnimatedPressable
          style={[styles.fab, { backgroundColor: colors.accent }]}
          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); openCreateModal(); }}
          accessibilityRole="button"
          accessibilityLabel="Create new listing"
        >
          <Ionicons name="add" size={28} color={colors.accentText} />
        </AnimatedPressable>
      )}

      {/* Create Listing Modal */}
      <CreateListingModal
        visible={showCreateModal}
        onClose={closeCreateModal}
        titleField={createTitleField}
        priceField={createPriceField}
        marketplace={createMarketplace}
        onMarketplaceChange={setCreateMarketplace}
        feeSchedules={feeSchedules}
        currency={settings.currency}
        creating={creating}
        onCreateListing={handleCreateListing}
      />

      {/* Connect Marketplace Modal */}
      <ConnectMarketplaceModal
        visible={showConnectModal}
        onClose={closeConnectModal}
        selectedMp={connectMp}
        onMpChange={setConnectMp}
        sellerName={connectName}
        onSellerNameChange={setConnectName}
        connecting={connecting}
        onConnect={handleConnect}
      />

      <QuickNavBar />
    </View>
  );
}

export default function SellerDashboardWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Seller Dashboard">
      <SellerDashboardScreen />
    </ScreenErrorBoundary>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: { flex: 1 },
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
  tabBtnText: { fontSize: text.md, fontWeight: fontWeight.semibold },

  filterRow: { maxHeight: 48 },
  filterContent: { paddingHorizontal: 16, paddingVertical: 10, gap: 8 },
  filterChip: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: radius.md,
    borderWidth: 1,
    marginRight: 6,
  },
  filterChipText: { fontSize: text.sm, fontWeight: fontWeight.semibold },

  listContent: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 24 },

  // Listing card
  listingCard: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 12,
    marginBottom: 10,
  },
  listingTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  mpBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: gap.xs,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.xs,
  },
  mpBadgeText: { fontSize: text.xs, fontWeight: fontWeight.semibold },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.xs,
  },
  statusBadgeText: { fontSize: text.xs, fontWeight: fontWeight.semibold },
  listingTitle: { fontSize: text.md, fontWeight: fontWeight.semibold, marginBottom: 6 },
  listingMeta: { flexDirection: 'row', alignItems: 'baseline', gap: 10, marginBottom: gap.md },
  listingPrice: { fontSize: text.lg, fontWeight: fontWeight.bold },
  listingNet: { fontSize: text.sm },
  metricsRow: { flexDirection: 'row', alignItems: 'center', gap: gap.xl },
  metricItem: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  metricText: { fontSize: text.sm },
  formatBadge: { borderWidth: 1, borderRadius: radius.xs, paddingHorizontal: 6, paddingVertical: 2 },
  formatText: { fontSize: text.xs, fontWeight: fontWeight.semibold },
  syncedText: { fontSize: text.xs, marginTop: 6 },

  // Sale card
  saleCard: { borderRadius: radius.md, borderWidth: 1, padding: 12, marginBottom: 10 },
  saleTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  salePrice: { fontSize: text.lg, fontWeight: fontWeight.bold },
  saleBuyer: { fontSize: text.sm, marginBottom: 8 },
  financialRow: { flexDirection: 'row', justifyContent: 'space-between', paddingTop: 8, borderTopWidth: StyleSheet.hairlineWidth, marginBottom: 6 },
  financialItem: { alignItems: 'center' },
  financialLabel: { fontSize: text.xs, marginBottom: 2 },
  financialValue: { fontSize: text.md, fontWeight: fontWeight.semibold },
  saleDate: { fontSize: text.xs },

  // Account card
  accountCard: { flexDirection: 'row', alignItems: 'center', borderRadius: radius.md, borderWidth: 1, padding: 12, marginBottom: 10, gap: gap.xl },
  accountIcon: { width: 48, height: 48, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  accountInfo: { flex: 1 },
  accountName: { fontSize: text.md, fontWeight: fontWeight.semibold },
  accountSeller: { fontSize: text.sm, marginTop: 2 },
  accountDate: { fontSize: text.xs, marginTop: 2 },
  accountStatusDot: { width: 10, height: 10, borderRadius: 5 },

  // Connect button
  connectBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: gap.md,
    paddingVertical: 12,
    borderRadius: radius.md,
    borderWidth: 1,
    marginBottom: 16,
  },
  connectBtnText: { fontSize: text.md, fontWeight: fontWeight.semibold },

  // Revenue summary
  summaryCard: { borderRadius: radius.md, borderWidth: 1, padding: 16, marginBottom: 16 },
  summaryTitle: { fontSize: text.md, fontWeight: fontWeight.bold, marginBottom: gap.xl },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between' },
  summaryItem: { alignItems: 'center', flex: 1 },
  summaryLabel: { fontSize: text.xs, marginBottom: gap.xs },
  summaryValue: { fontSize: text.lg, fontWeight: fontWeight.bold },
  summaryCount: { fontSize: text.xs, marginTop: 10, textAlign: 'center' },

  // FAB
  fab: {
    position: 'absolute',
    bottom: 80,
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    ...shadow.floating,
  },

  // Modal styles moved to CreateListingModal and ConnectMarketplaceModal components
  // Prediction comps styles moved to PredictionCompsCard component
});
