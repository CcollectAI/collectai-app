import React from 'react';
import { View, Text, Linking, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import logger from '@/utils/logger';
import type { AppTheme } from '@/hooks/useAppTheme';

type ExternalMarketplace = {
  id: string;
  label: string;
  url: string;
};

type AffiliateLink = {
  source: string;
  url: string;
  affiliate_url: string;
  label: string;
};

type Props = {
  marketplaces: ExternalMarketplace[];
  affiliateLinks: AffiliateLink[];
  onPress: () => void; // fire haptic before opening
  colors: AppTheme['colors'];
};

const ExternalMarketplacesSection: React.FC<Props> = ({
  marketplaces,
  affiliateLinks,
  onPress,
  colors,
}) => {
  if (marketplaces.length === 0) return null;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>External Marketplaces</Text>
      <View style={styles.marketplaceRow}>
        {marketplaces.map((mp) => {
          const affiliateMatch = affiliateLinks.find(
            (al) => al.source.toLowerCase() === mp.id.toLowerCase()
          );
          const url = affiliateMatch?.affiliate_url ?? mp.url;
          return (
            <AnimatedPressable
              key={mp.id}
              style={[styles.marketplaceBtn, { backgroundColor: colors.accent + '15', borderColor: colors.accent }]}
              onPress={() => {
                onPress();
                Linking.openURL(url).catch((err) => logger.warn('[CategoryStore] open URL error:', err));
              }}
              accessibilityRole="link"
              accessibilityLabel={`Shop ${mp.label}`}
            >
              <Ionicons name="open-outline" size={14} color={colors.accent} />
              <Text style={[styles.marketplaceBtnText, { color: colors.accent }]}>{mp.label}</Text>
            </AnimatedPressable>
          );
        })}
      </View>
    </View>
  );
};

export default React.memo(ExternalMarketplacesSection);

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  marketplaceRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  marketplaceBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
  },
  marketplaceBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
