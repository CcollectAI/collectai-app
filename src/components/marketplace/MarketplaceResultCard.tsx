/**
 * Individual search result card for the Marketplace screen.
 *
 * Renders a marketplace or collection item row with image, title, meta,
 * price, shipping hints, and domestic-only badge.
 *
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';

export interface MarketplaceResultItem {
  id: string;
  name: string;
  category: string;
  collectionName: string;
  value: number;
  isMarketplace?: boolean;
  externalUrl?: string;
  affiliateUrl?: string;
  source?: string;
  condition?: string;
  image_url?: string | null;
  domesticOnly?: boolean;
  shippingHint?: string;
  secondaryPrice?: string | null;
  sourceCurrency?: string | null;
}

interface MarketplaceResultCardProps {
  item: MarketplaceResultItem;
  onPress: (item: MarketplaceResultItem) => void;
  isTopResult?: boolean;
}

export const MarketplaceResultCard = React.memo(function MarketplaceResultCard({
  item,
  onPress,
  isTopResult,
}: MarketplaceResultCardProps) {
  const { colors } = useAppTheme();

  const iconName = item.domesticOnly
    ? 'ban-outline'
    : item.isMarketplace
      ? 'cart-outline'
      : isTopResult
        ? 'star-outline'
        : 'card-outline';

  const iconColor = item.domesticOnly
    ? colors.muted
    : item.isMarketplace
      ? colors.accent
      : isTopResult
        ? colors.accent
        : colors.muted;

  return (
    <AnimatedPressable
      style={[
        styles.resultRow,
        { borderBottomColor: colors.border },
        item.domesticOnly && { opacity: 0.5 },
      ]}
      onPress={() => onPress(item)}
      disabled={item.domesticOnly}
      accessibilityRole={item.isMarketplace ? 'link' : 'button'}
      accessibilityLabel={`${item.name}, ${formatPrice(item.value)}`}
    >
      {item.image_url ? (
        <Image
          source={{ uri: item.image_url }}
          style={styles.resultThumbnail}
          accessibilityLabel={`Image of ${item.name}`}
        />
      ) : (
        <View style={[styles.resultIcon, { backgroundColor: colors.accent + '15' }]}>
          <Ionicons name={iconName} size={18} color={iconColor} />
        </View>
      )}
      <View style={{ flex: 1 }}>
        <Text style={[styles.resultTitle, { color: colors.text }]}>
          {item.name}
        </Text>
        <Text style={[styles.resultMeta, { color: colors.muted }]}>
          {item.isMarketplace
            ? `${item.source || 'Marketplace'}${item.condition ? ` \u00B7 ${item.condition}` : ''}`
            : `${item.category} \u2022 ${item.collectionName}`}
        </Text>
        {item.secondaryPrice && (
          <Text style={[styles.resultSecondary, { color: colors.muted }]}>
            {item.secondaryPrice}
          </Text>
        )}
        {item.shippingHint && (
          <Text style={[styles.resultShipping, { color: colors.muted }]}>
            {item.shippingHint}
          </Text>
        )}
        {item.domesticOnly && (
          <View style={[styles.domesticBadge, { backgroundColor: colors.muted + '20' }]}>
            <Text style={[styles.domesticBadgeText, { color: colors.muted }]}>Domestic only</Text>
          </View>
        )}
      </View>
      <Text style={[styles.resultValue, { color: colors.text }]}>
        {formatPrice(item.value)}
      </Text>
    </AnimatedPressable>
  );
});

const styles = StyleSheet.create({
  resultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  resultIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  resultThumbnail: {
    width: 48,
    height: 48,
    borderRadius: 8,
    marginRight: 10,
  },
  resultTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  resultMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  resultValue: {
    fontSize: 13,
    fontWeight: '700',
    marginLeft: 8,
  },
  resultSecondary: {
    fontSize: 11,
    marginTop: 1,
  },
  resultShipping: {
    fontSize: 11,
    marginTop: 1,
  },
  domesticBadge: {
    alignSelf: 'flex-start',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginTop: 4,
  },
  domesticBadgeText: {
    fontSize: 10,
    fontWeight: '600',
  },
});
