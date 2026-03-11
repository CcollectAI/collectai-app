/**
 * Batch scan summary screen showing all items scanned in the session.
 * Displays item list with total estimated value and a Done button.
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Image,
  FlatList,
  StatusBar,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';
import type { CurrencyCode } from '@/data/types';

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';

export interface BatchScannedItem {
  id: string;
  name: string;
  category: string;
  condition: string;
  estimatedMid: number;
  estimatedLow: number;
  estimatedHigh: number;
  confidence: number;
  imageUri: string;
  saved: boolean;
}

interface BatchSummaryScreenProps {
  batchItems: BatchScannedItem[];
  savedBatchCount: number;
  totalBatchValue: number;
  currency: CurrencyCode;
  onFinish: () => void;
  colors: {
    background: string;
    text: string;
    muted: string;
    card: string;
    border: string;
  };
}

function BatchSummaryScreenInner({
  batchItems,
  savedBatchCount,
  totalBatchValue,
  currency,
  onFinish,
  colors,
}: BatchSummaryScreenProps) {
  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <StatusBar barStyle="dark-content" />
      <View style={styles.summaryHeader}>
        <Ionicons name="checkmark-circle" size={56} color={TIFFANY} />
        <Text style={[styles.summaryTitle, { color: colors.text }]}>
          Batch Scan Complete
        </Text>
        <Text style={[styles.summarySubtitle, { color: colors.muted }]}>
          You scanned {savedBatchCount} item{savedBatchCount !== 1 ? 's' : ''}
        </Text>
        {savedBatchCount > 0 && (
          <View style={[styles.summaryValueBadge, { backgroundColor: TIFFANY + '18' }]}>
            <Text style={[styles.summaryValueLabel, { color: TIFFANY_DARK }]}>
              Total estimated value
            </Text>
            <Text style={[styles.summaryValueAmount, { color: TIFFANY_DARK }]}>
              {formatPrice(totalBatchValue, currency)}
            </Text>
          </View>
        )}
      </View>

      <FlatList
        data={batchItems.filter((i) => i.saved)}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.summaryList}
        renderItem={({ item }) => (
          <View style={[styles.summaryItemCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Image
              source={{ uri: item.imageUri }}
              style={[styles.summaryItemImage, { backgroundColor: colors.border }]}
              resizeMode="cover"
            />
            <View style={styles.summaryItemInfo}>
              <Text style={[styles.summaryItemName, { color: colors.text }]} numberOfLines={1}>
                {item.name}
              </Text>
              <Text style={[styles.summaryItemCategory, { color: colors.muted }]} numberOfLines={1}>
                {item.category} -- {item.condition}
              </Text>
            </View>
            <Text style={[styles.summaryItemPrice, { color: TIFFANY_DARK }]}>
              {formatPrice(item.estimatedMid, currency)}
            </Text>
          </View>
        )}
        ListEmptyComponent={
          <View style={styles.summaryEmpty}>
            <Text style={[styles.summaryEmptyText, { color: colors.muted }]}>
              No items were saved during this session.
            </Text>
          </View>
        }
      />

      <View style={styles.summaryBottomBar}>
        <AnimatedPressable
          style={[styles.summaryDoneBtn, { backgroundColor: TIFFANY }]}
          onPress={onFinish}
          accessibilityRole="button"
          accessibilityLabel="Done, go back"
        >
          <Text style={styles.summaryDoneBtnText}>Done</Text>
        </AnimatedPressable>
      </View>
    </View>
  );
}

export const BatchSummaryScreen = React.memo(BatchSummaryScreenInner);

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  summaryHeader: {
    alignItems: 'center',
    paddingTop: 40,
    paddingBottom: 24,
    paddingHorizontal: 24,
    gap: 8,
  },
  summaryTitle: {
    fontSize: 24,
    fontWeight: '700',
    marginTop: 12,
  },
  summarySubtitle: {
    fontSize: 16,
    fontWeight: '400',
  },
  summaryValueBadge: {
    marginTop: 12,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 16,
    alignItems: 'center',
    gap: 4,
  },
  summaryValueLabel: {
    fontSize: 13,
    fontWeight: '500',
  },
  summaryValueAmount: {
    fontSize: 28,
    fontWeight: '700',
  },
  summaryList: {
    paddingHorizontal: 20,
    paddingBottom: 100,
    gap: 10,
  },
  summaryItemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 14,
    borderWidth: 1,
    gap: 12,
  },
  summaryItemImage: {
    width: 48,
    height: 48,
    borderRadius: 10,
  },
  summaryItemInfo: {
    flex: 1,
    gap: 2,
  },
  summaryItemName: {
    fontSize: 15,
    fontWeight: '600',
  },
  summaryItemCategory: {
    fontSize: 13,
    fontWeight: '400',
  },
  summaryItemPrice: {
    fontSize: 16,
    fontWeight: '700',
  },
  summaryEmpty: {
    alignItems: 'center',
    paddingTop: 40,
  },
  summaryEmptyText: {
    fontSize: 15,
    fontWeight: '400',
  },
  summaryBottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: 20,
    paddingBottom: 40,
    paddingTop: 16,
  },
  summaryDoneBtn: {
    alignItems: 'center',
    paddingVertical: 16,
    borderRadius: 14,
  },
  summaryDoneBtnText: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '700',
  },
});
