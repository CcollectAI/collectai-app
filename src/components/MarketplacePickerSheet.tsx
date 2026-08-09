/**
 * MarketplacePickerSheet — bottom-sheet modal showing marketplace options
 * for a specific item. Fetches affiliate-tagged URLs and opens in browser.
 *
 * The server returns `links` ordered by category fit, so the first row is the
 * marketplace that actually suits the item (Cardmarket for an MTG single,
 * BrickLink for a LEGO set) rather than eBay for everything.
 *
 * Pass `maxPrice` when the user has a target price — the search URLs come back
 * capped at it, which is the difference between "every Bayou ever listed" and
 * "the ones you'd actually buy".
 */

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  Modal,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { collectorsApi } from '@/api/collectorsApi';
import { openAffiliateUrl } from '@/utils/affiliateHelpers';
import { formatPrice } from '@/lib/format';

type AffiliateLink = {
  source: string;
  url: string;
  affiliate_url: string;
  label: string;
};

type Props = {
  visible: boolean;
  onClose: () => void;
  itemTitle: string;
  categoryId?: string;
  /** Buyer's price ceiling, in `maxPriceCurrency`. Omitted = no cap. */
  maxPrice?: number | null;
  maxPriceCurrency?: string;
};

const FALLBACK_EBAY_URL = 'https://www.ebay.com/sch/i.html?_nkw=';

export default function MarketplacePickerSheet({
  visible,
  onClose,
  itemTitle,
  categoryId,
  maxPrice,
  maxPriceCurrency,
}: Props) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const [links, setLinks] = useState<AffiliateLink[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!visible || !itemTitle) return;

    setLoading(true);
    setLinks([]);

    collectorsApi
      .getAffiliateLinks(
        itemTitle,
        categoryId,
        6,
        settings.region,
        maxPrice,
        maxPriceCurrency ?? settings.currency,
      )
      .then((res: { links: AffiliateLink[] }) => setLinks(res.links ?? []))
      .catch(() => setLinks([]))
      .finally(() => setLoading(false));
  }, [visible, itemTitle, categoryId, maxPrice, maxPriceCurrency, settings.region, settings.currency]);

  const handleOpenLink = (url: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // Routes through openAffiliateUrl, not Linking directly: it validates the
    // scheme and records the click into demand_signals. A bare Linking.openURL
    // here meant every wishlist Shop tap was invisible to the affiliate funnel.
    openAffiliateUrl(url, { query: itemTitle, category: categoryId });
    onClose();
  };

  const displayLinks =
    links.length > 0
      ? links
      : [{ source: 'ebay', label: 'Search on eBay', url: '', affiliate_url: `${FALLBACK_EBAY_URL}${encodeURIComponent(itemTitle)}` }];

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <AnimatedPressable style={styles.backdrop} onPress={onClose} accessibilityRole="button" accessibilityLabel="Close marketplace picker">
        <View />
      </AnimatedPressable>
      <View style={[styles.sheet, { backgroundColor: colors.card }]}>
        <View style={styles.header}>
          <View style={styles.headerText}>
            <Text style={[styles.title, { color: colors.text }]} numberOfLines={2}>
              Shop: {itemTitle}
            </Text>
            {maxPrice && maxPrice > 0 ? (
              <Text style={[styles.subtitle, { color: colors.muted }]} numberOfLines={1}>
                Buy It Now under {formatPrice(maxPrice)}, cheapest first
              </Text>
            ) : null}
          </View>
          <AnimatedPressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close marketplace picker" accessibilityHint="Double tap to dismiss">
            <Ionicons name="close" size={22} color={colors.muted} />
          </AnimatedPressable>
        </View>

        {loading ? (
          <ActivityIndicator size="small" color={colors.accent} style={styles.loader} />
        ) : (
          displayLinks.map((link) => (
            <AnimatedPressable
              key={link.source + link.label}
              style={[styles.linkRow, { borderBottomColor: colors.border }]}
              onPress={() => handleOpenLink(link.affiliate_url || link.url)}
              accessibilityRole="link"
              accessibilityLabel={`Open ${link.label}`}
              accessibilityHint="Double tap to open in browser"
            >
              <Text style={[styles.linkLabel, { color: colors.text }]}>{link.label}</Text>
              <Ionicons name="open-outline" size={18} color={colors.accent} />
            </AnimatedPressable>
          ))
        )}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  sheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  headerText: {
    flex: 1,
    marginRight: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  loader: {
    marginVertical: 24,
  },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  linkLabel: {
    fontSize: 15,
    fontWeight: '500',
  },
});
