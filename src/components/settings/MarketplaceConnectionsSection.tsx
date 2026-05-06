/**
 * MarketplaceConnectionsSection — connect / configure / disconnect external
 * selling accounts (eBay primary; Discogs and others later).
 *
 * Replaces the v1 bare "Connect eBay" stub. Shows:
 *   • Connected accounts with status + last sync
 *   • Whether publish defaults are configured (per-marketplace)
 *   • Connect button when no account exists
 *   • Per-account "Configure defaults" + "Disconnect" actions
 *
 * Flow:
 *   1. Tap "Connect eBay" → backend mints consent URL → open in browser.
 *   2. User signs in on eBay; backend exchanges code for tokens.
 *   3. User returns to app — focus refresh re-fetches accounts.
 *   4. eBay account row shows ⚠ "Set up publish defaults" until
 *      categoryId + 3 policy IDs saved (else /publish 412s).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import {
  View,
  Text,
  StyleSheet,
  Linking,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import {
  startEbayOauth,
  listMarketplaceAccounts,
  disconnectMarketplaceAccount,
  getEbayDefaults,
} from '@/api/marketplaceApi';
import { logger } from '@/lib/logger';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import type { MarketplaceAccount } from '@/data/types';

type AccountWithDefaults = MarketplaceAccount & {
  defaultsConfigured: boolean;
};

const MARKETPLACE_LABELS: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap }> = {
  ebay: { label: 'eBay', icon: 'storefront-outline' },
  mercari: { label: 'Mercari', icon: 'storefront-outline' },
  discogs: { label: 'Discogs', icon: 'disc-outline' },
  cardmarket: { label: 'Cardmarket', icon: 'pricetag-outline' },
};

function formatRelative(iso?: string | null): string {
  if (!iso) return 'never';
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60_000);
  if (min < 1) return 'just now';
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} ${hr === 1 ? 'hour' : 'hours'} ago`;
  const d = Math.floor(hr / 24);
  if (d === 1) return 'yesterday';
  if (d < 30) return `${d} days ago`;
  return new Date(iso).toLocaleDateString();
}

export function MarketplaceConnectionsSection() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();

  const [accounts, setAccounts] = useState<AccountWithDefaults[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null);

  const loadAccounts = useCallback(async () => {
    try {
      const res = (await listMarketplaceAccounts()) as
        | { accounts?: MarketplaceAccount[] }
        | undefined;
      const raw = res?.accounts ?? [];
      // For each eBay account, check whether publish defaults are set so
      // we can surface a "Set up defaults" warning before the user hits
      // 412 on /publish.
      const withDefaults: AccountWithDefaults[] = await Promise.all(
        raw.map(async (a) => {
          if (a.marketplaceId !== 'ebay') {
            return { ...a, defaultsConfigured: true };
          }
          try {
            const d = (await getEbayDefaults()) as {
              ebay_category_id?: string;
              fulfillment_policy_id?: string;
              payment_policy_id?: string;
              return_policy_id?: string;
            } | undefined;
            const ok = Boolean(
              d?.ebay_category_id &&
                d?.fulfillment_policy_id &&
                d?.payment_policy_id &&
                d?.return_policy_id,
            );
            return { ...a, defaultsConfigured: ok };
          } catch {
            return { ...a, defaultsConfigured: false };
          }
        }),
      );
      setAccounts(withDefaults);
    } catch (e) {
      logger.warn('list_marketplace_accounts_failed', { error: String(e) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  // Re-fetch when the user returns to Settings (e.g. after completing eBay OAuth in the browser)
  useFocusEffect(
    useCallback(() => {
      loadAccounts();
    }, [loadAccounts]),
  );

  const onConnectEbay = async () => {
    if (connecting) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setConnecting(true);
    try {
      const r = await startEbayOauth();
      const url = r?.redirect_url;
      if (!url) throw new Error('no redirect_url');
      const ok = await Linking.canOpenURL(url);
      if (!ok) throw new Error('cannot open URL');
      await Linking.openURL(url);
    } catch (e) {
      logger.warn('connect_ebay_failed', { error: String(e) });
      Alert.alert(
        t('marketplace_connections.connect_failed_title'),
        t('marketplace_connections.connect_failed_body'),
      );
    } finally {
      setConnecting(false);
    }
  };

  const onDisconnect = (account: AccountWithDefaults) => {
    const label = MARKETPLACE_LABELS[account.marketplaceId]?.label ?? account.marketplaceId;
    Alert.alert(
      `Disconnect ${label}?`,
      `Active listings will stay live, but you won't be able to publish new ones until you reconnect.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Disconnect',
          style: 'destructive',
          onPress: async () => {
            setDisconnectingId(account.id);
            try {
              await disconnectMarketplaceAccount(account.id);
              await loadAccounts();
            } catch (e) {
              logger.warn('disconnect_failed', { error: String(e) });
              Alert.alert('Disconnect failed', 'Please try again.');
            } finally {
              setDisconnectingId(null);
            }
          },
        },
      ],
    );
  };

  const onConfigureDefaults = (account: AccountWithDefaults) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    if (account.marketplaceId === 'ebay') {
      router.push('/sell/ebay-defaults');
    }
  };

  const ebayConnected = accounts.some((a) => a.marketplaceId === 'ebay' && a.isActive);

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionLabel, { color: colors.muted }]}>
        {t('marketplace_connections.section_title')}
      </Text>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {loading ? (
          <View style={styles.loadingRow}>
            <ActivityIndicator size="small" color={colors.muted} />
          </View>
        ) : (
          <>
            {accounts.length === 0 && (
              <View style={styles.emptyRow}>
                <Text style={[styles.emptyText, { color: colors.muted }]}>
                  No marketplaces connected yet. Sparrow can help you list items
                  on eBay once you sign in.
                </Text>
              </View>
            )}

            {accounts.map((account, idx) => {
              const meta = MARKETPLACE_LABELS[account.marketplaceId] ?? {
                label: account.marketplaceId,
                icon: 'storefront-outline' as const,
              };
              const showDefaultsWarning =
                account.marketplaceId === 'ebay' && !account.defaultsConfigured;
              const statusColor = !account.isActive
                ? colors.muted
                : showDefaultsWarning
                  ? colors.warning
                  : colors.success;
              const statusLabel = !account.isActive
                ? 'Inactive'
                : showDefaultsWarning
                  ? 'Set up defaults'
                  : 'Connected';
              return (
                <View
                  key={account.id}
                  style={[
                    styles.accountRow,
                    idx > 0 && { borderTopWidth: 1, borderTopColor: colors.border },
                  ]}
                >
                  <View style={styles.accountHeader}>
                    <View style={[styles.accountIcon, { backgroundColor: colors.accent + '15' }]}>
                      <Ionicons name={meta.icon} size={18} color={colors.accent} />
                    </View>
                    <View style={{ flex: 1, marginLeft: 12 }}>
                      <Text style={[styles.accountTitle, { color: colors.text }]}>
                        {meta.label}
                      </Text>
                      <Text style={[styles.accountMeta, { color: colors.muted }]} numberOfLines={1}>
                        {account.sellerName ?? account.sellerId ?? '—'} · last sync {formatRelative(account.lastSyncAt)}
                      </Text>
                    </View>
                    <View
                      style={[
                        styles.statusPill,
                        { backgroundColor: statusColor + '20' },
                      ]}
                    >
                      <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
                      <Text style={[styles.statusText, { color: statusColor }]}>
                        {statusLabel}
                      </Text>
                    </View>
                  </View>

                  <View style={styles.accountActions}>
                    {showDefaultsWarning && (
                      <AnimatedPressable
                        style={[styles.actionBtn, { backgroundColor: colors.warning + '18' }]}
                        onPress={() => onConfigureDefaults(account)}
                        accessibilityRole="button"
                        accessibilityLabel={`Configure ${meta.label} defaults`}
                      >
                        <Ionicons name="settings-outline" size={14} color={colors.warning} />
                        <Text style={[styles.actionBtnText, { color: colors.warning }]}>
                          Set up defaults
                        </Text>
                      </AnimatedPressable>
                    )}
                    {!showDefaultsWarning && account.marketplaceId === 'ebay' && (
                      <AnimatedPressable
                        style={[styles.actionBtn, { backgroundColor: colors.muted + '15' }]}
                        onPress={() => onConfigureDefaults(account)}
                        accessibilityRole="button"
                        accessibilityLabel={`Edit ${meta.label} defaults`}
                      >
                        <Ionicons name="settings-outline" size={14} color={colors.muted} />
                        <Text style={[styles.actionBtnText, { color: colors.muted }]}>
                          Edit defaults
                        </Text>
                      </AnimatedPressable>
                    )}
                    <AnimatedPressable
                      style={[styles.actionBtn, { backgroundColor: colors.danger + '12' }]}
                      onPress={() => onDisconnect(account)}
                      disabled={disconnectingId === account.id}
                      accessibilityRole="button"
                      accessibilityLabel={`Disconnect ${meta.label}`}
                    >
                      {disconnectingId === account.id ? (
                        <ActivityIndicator size="small" color={colors.danger} />
                      ) : (
                        <>
                          <Ionicons name="close-outline" size={14} color={colors.danger} />
                          <Text style={[styles.actionBtnText, { color: colors.danger }]}>
                            Disconnect
                          </Text>
                        </>
                      )}
                    </AnimatedPressable>
                  </View>
                </View>
              );
            })}

            {!ebayConnected && (
              <View
                style={[
                  styles.connectRow,
                  accounts.length > 0 && { borderTopWidth: 1, borderTopColor: colors.border },
                ]}
              >
                <AnimatedPressable
                  style={styles.row}
                  onPress={onConnectEbay}
                  disabled={connecting}
                  accessibilityRole="button"
                  accessibilityLabel={t('marketplace_connections.connect_ebay_a11y')}
                >
                  <Ionicons name="storefront-outline" size={20} color={colors.accent} />
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={[styles.title, { color: colors.text }]}>
                      {t('marketplace_connections.connect_ebay')}
                    </Text>
                    <Text style={[styles.hint, { color: colors.muted }]}>
                      {t('marketplace_connections.connect_ebay_hint')}
                    </Text>
                  </View>
                  {connecting ? (
                    <ActivityIndicator size="small" color={colors.accent} />
                  ) : (
                    <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                  )}
                </AnimatedPressable>
              </View>
            )}
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginTop: 16 },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginBottom: 8,
    paddingHorizontal: 4,
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    overflow: 'hidden',
  },
  loadingRow: { paddingVertical: 24, alignItems: 'center' },
  emptyRow: { padding: 14 },
  emptyText: { fontSize: 13, lineHeight: 18 },

  accountRow: { padding: 14 },
  accountHeader: { flexDirection: 'row', alignItems: 'center' },
  accountIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  accountTitle: { fontSize: 15, fontWeight: '700' },
  accountMeta: { fontSize: 12, marginTop: 2 },
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 100,
  },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusText: { fontSize: 11, fontWeight: '700' },

  accountActions: { flexDirection: 'row', gap: 6, marginTop: 12 },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
  },
  actionBtnText: { fontSize: 12, fontWeight: '600' },

  connectRow: {},
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 14,
  },
  title: { fontSize: 15, fontWeight: '600' },
  hint: { fontSize: 12, marginTop: 2 },
});
