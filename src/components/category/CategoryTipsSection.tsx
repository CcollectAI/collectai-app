/**
 * CategoryTipsSection — First-time tips for new collectors in a category.
 * Shows 2-3 beginner tips on first visit, dismissible with AsyncStorage.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import logger from '@/utils/logger';
import { AnimatedPressable } from '@/motion';

type Tip = { icon: keyof typeof Ionicons.glyphMap; title: string; body: string };

const CATEGORY_TIPS: Record<string, Tip[]> = {
  pokemon: [
    { icon: 'star-outline', title: 'Check the Set Symbol', body: 'Every card has a set symbol — this identifies the expansion and helps determine rarity.' },
    { icon: 'shield-outline', title: 'PSA Grading Matters', body: 'A PSA 10 can be worth 5-10x more than an ungraded copy of the same card.' },
  ],
  mtg: [
    { icon: 'layers-outline', title: 'Edition Is Everything', body: 'Alpha, Beta, and Unlimited printings have wildly different values for the same card.' },
    { icon: 'eye-outline', title: 'Check for Misprints', body: 'Misprints and miscuts can significantly increase a card\'s value to niche collectors.' },
  ],
  funko: [
    { icon: 'barcode-outline', title: 'Check the Box Number', body: 'Each Funko POP has a unique number — use it for accurate identification and pricing.' },
    { icon: 'cube-outline', title: 'Box Condition Matters', body: 'In-box collectors pay premiums for mint boxes. Window damage can cut value 30-50%.' },
  ],
  lego: [
    { icon: 'close-circle-outline', title: 'Retired = Valuable', body: 'LEGO sets that are retired from production often appreciate significantly over time.' },
    { icon: 'receipt-outline', title: 'Keep Instructions & Box', body: 'Complete sets with original box and instructions are worth 20-40% more.' },
  ],
  sneakers: [
    { icon: 'footsteps-outline', title: 'Size Affects Price', body: 'Sizes 9-11 US are most common. Smaller (5-7) and larger (13+) sizes can sell for premiums.' },
    { icon: 'checkmark-circle-outline', title: 'Verify Authenticity', body: 'Use CheckCheck or Legit Check before buying — fakes are rampant in the sneaker market.' },
  ],
  watches: [
    { icon: 'document-text-outline', title: 'Papers & Box', body: 'Original box, papers, and warranty card ("full set") can add 15-30% to resale value.' },
    { icon: 'build-outline', title: 'Service History', body: 'A documented service history from an authorized dealer increases buyer confidence and value.' },
  ],
  manga: [
    { icon: 'book-outline', title: 'First Prints Matter', body: 'First edition prints, especially for popular series, are significantly more valuable.' },
    { icon: 'alert-circle-outline', title: 'Out of Print = Gold', body: 'When a manga goes OOP, prices spike. Complete sets of OOP series are especially sought after.' },
  ],
  vinyl_records: [
    { icon: 'disc-outline', title: 'Pressing Info', body: 'First pressings and limited color variants command premium prices. Check the matrix number.' },
    { icon: 'musical-notes-outline', title: 'Condition Grades', body: 'Vinyl is graded Mint to Poor. VG+ is the minimum for collectible value. Check for warps and scratches.' },
  ],
};

// Generic tips for categories without specific ones
const GENERIC_TIPS: Tip[] = [
  { icon: 'camera-outline', title: 'Photo Everything', body: 'Good photos help with accurate valuation and make items easier to sell later.' },
  { icon: 'pricetag-outline', title: 'Track Market Prices', body: 'Add items to your watchlist to monitor price trends and find the best time to buy or sell.' },
];

type Props = {
  categoryId: string;
};

export default React.memo(function CategoryTipsSection({ categoryId }: Props) {
  const { colors } = useAppTheme();
  const [dismissed, setDismissed] = useState(true);

  const storageKey = `category_tips_dismissed_${categoryId}`;

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(storageKey)
      .then((val) => { if (!cancelled && val !== 'true') setDismissed(false); })
      .catch((err) => logger.warn('[CategoryTips] storage read failed:', err));
    return () => { cancelled = true; };
  }, [storageKey]);

  if (dismissed) return null;

  const tips = CATEGORY_TIPS[categoryId] ?? GENERIC_TIPS;

  const handleDismiss = () => {
    setDismissed(true);
    AsyncStorage.setItem(storageKey, 'true');
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '30' }]}>
      <View style={styles.header}>
        <Ionicons name="bulb-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>Tips for New Collectors</Text>
        <View style={{ flex: 1 }} />
        <AnimatedPressable
          onPress={handleDismiss}
          accessibilityRole="button"
          accessibilityLabel="Dismiss tips"
        >
          <Ionicons name="close" size={18} color={colors.muted} />
        </AnimatedPressable>
      </View>

      {tips.map((tip, idx) => (
        <View key={idx} style={styles.tipRow}>
          <View style={[styles.tipIcon, { backgroundColor: colors.accent + '20' }]}>
            <Ionicons name={tip.icon} size={16} color={colors.accent} />
          </View>
          <View style={styles.tipContent}>
            <Text style={[styles.tipTitle, { color: colors.text }]}>{tip.title}</Text>
            <Text style={[styles.tipBody, { color: colors.muted }]}>{tip.body}</Text>
          </View>
        </View>
      ))}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  title: {
    fontSize: 15,
    fontWeight: '700',
  },
  tipRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginBottom: 10,
  },
  tipIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tipContent: {
    flex: 1,
  },
  tipTitle: {
    fontSize: 13,
    fontWeight: '700',
  },
  tipBody: {
    fontSize: 12,
    marginTop: 2,
    lineHeight: 17,
  },
});
