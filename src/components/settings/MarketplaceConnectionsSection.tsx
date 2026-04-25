/**
 * MarketplaceConnectionsSection — connect / disconnect external selling
 * accounts (eBay only for v1; Discogs + others later).
 *
 * Tap "Connect eBay" → backend returns the eBay consent URL → we open
 * it in the system browser (Linking.openURL). User signs in on eBay,
 * gets redirected back to our backend callback which stores the OAuth
 * tokens. User returns to the app manually; this component polls
 * /accounts on focus to detect the new connection.
 */
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View, Text, StyleSheet, Linking, Alert, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { startEbayOauth } from '@/api/marketplaceApi';
import { logger } from '@/lib/logger';

export function MarketplaceConnectionsSection() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const [connecting, setConnecting] = useState(false);

  const onConnectEbay = async () => {
    if (connecting) return;
    setConnecting(true);
    try {
      const r: any = await startEbayOauth();
      const url: string | undefined = r?.redirect_url;
      if (!url) throw new Error('no redirect_url');
      const ok = await Linking.canOpenURL(url);
      if (!ok) throw new Error('cannot open URL');
      await Linking.openURL(url);
      // Backend completes the token exchange when eBay redirects there;
      // user comes back to the app manually. We do not await the result
      // — they'll see the connection appear next time this screen
      // refreshes (TODO: add focus-poll for status).
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

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionLabel, { color: colors.muted }]}>
        {t('marketplace_connections.section_title')}
      </Text>
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
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
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 14,
  },
  title: {
    fontSize: 15,
    fontWeight: '600',
  },
  hint: {
    fontSize: 12,
    marginTop: 2,
  },
});
