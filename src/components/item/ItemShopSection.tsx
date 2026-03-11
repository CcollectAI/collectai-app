/**
 * ItemShopSection — Affiliate links for shopping the item on external marketplaces.
 */
import React from 'react';
import { View, Text, Pressable, StyleSheet, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { fireHaptic, HapticIntent } from '@/haptics';
import logger from '@/utils/logger';

interface AffiliateLink {
  source: string;
  url: string;
  affiliate_url: string;
  label: string;
}

interface ItemShopSectionProps {
  affiliateLinks: AffiliateLink[];
}

export const ItemShopSection = React.memo(function ItemShopSection({ affiliateLinks }: ItemShopSectionProps) {
  const { colors: theme } = useAppTheme();
  const { settings } = useSettings();

  if (affiliateLinks.length === 0) return null;

  return (
    <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
      <View style={styles.sectionHeaderRow}>
        <View style={styles.sectionHeaderLeft}>
          <Ionicons name="open-outline" size={20} color={theme.accent} />
          <Text style={[styles.sectionTitle, { color: theme.text }]}>Shop this Item</Text>
        </View>
      </View>
      <View style={styles.linksRow}>
        {affiliateLinks.map((link) => (
          <Pressable
            key={link.source}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              Linking.openURL(link.affiliate_url).catch((err) =>
                logger.warn('[ItemDetail] Failed to open affiliate URL', err)
              );
            }}
            style={[styles.affiliateLinkBtn, { borderColor: theme.border }]}
            accessibilityRole="link"
            accessibilityLabel={link.label}
          >
            <Ionicons name="open-outline" size={14} color={theme.accent} />
            <Text style={[styles.affiliateLinkText, { color: theme.text }]}>{link.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  sectionBlock: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  sectionHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  linksRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    paddingTop: 8,
  },
  affiliateLinkBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
  },
  affiliateLinkText: {
    fontSize: 13,
    fontWeight: '500',
  },
});
