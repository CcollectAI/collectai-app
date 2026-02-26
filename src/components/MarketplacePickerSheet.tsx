/**
 * MarketplacePickerSheet — bottom-sheet modal showing marketplace options
 * for a specific item. Fetches affiliate-tagged URLs and opens in browser.
 */

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  Modal,
  StyleSheet,
  ActivityIndicator,
  Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { collectorsApi } from '@/api/collectorsApi';

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
};

const FALLBACK_EBAY_URL = 'https://www.ebay.com/sch/i.html?_nkw=';

export default function MarketplacePickerSheet({ visible, onClose, itemTitle, categoryId }: Props) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const [links, setLinks] = useState<AffiliateLink[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!visible || !itemTitle) return;

    setLoading(true);
    setLinks([]);

    collectorsApi
      .getAffiliateLinks(itemTitle, categoryId, 6, settings.region)
      .then((res: { links: AffiliateLink[] }) => setLinks(res.links ?? []))
      .catch(() => setLinks([]))
      .finally(() => setLoading(false));
  }, [visible, itemTitle, categoryId]);

  const handleOpenLink = (url: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    Linking.openURL(url).catch(() => {});
  };

  const displayLinks =
    links.length > 0
      ? links
      : [{ source: 'ebay', label: 'Search on eBay', url: '', affiliate_url: `${FALLBACK_EBAY_URL}${encodeURIComponent(itemTitle)}` }];

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <AnimatedPressable style={styles.backdrop} onPress={onClose}>
        <View />
      </AnimatedPressable>
      <View style={[styles.sheet, { backgroundColor: colors.card }]}>
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text }]} numberOfLines={2}>
            Shop: {itemTitle}
          </Text>
          <AnimatedPressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close">
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
  title: {
    fontSize: 16,
    fontWeight: '700',
    flex: 1,
    marginRight: 12,
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
