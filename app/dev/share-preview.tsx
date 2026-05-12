/**
 * Dev-only ShareCard preview. Lets you iterate on the design without
 * running a real scan. Not linked from anywhere; reach via deep link or
 * by typing the URL in Expo dev tools.
 *
 * Open via:
 *   - Web:  http://localhost:8081/dev/share-preview
 *   - iOS:  expo router deep-link or /(tabs)/_layout.tsx hard-nav
 */
import React, { useState } from 'react';
import { View, Text, ScrollView, StyleSheet, Pressable } from 'react-native';
import { ShareCard } from '@/components/quickscan/ShareCard';

const SAMPLES = [
  {
    label: 'Premium tier (high value, high confidence)',
    props: {
      itemName: 'Charizard - Base Set Shadowless 4/102',
      category: 'pokemon',
      condition: 'PSA 9 Mint',
      priceMid: 1840,
      priceLow: 1620,
      priceHigh: 2100,
      currency: 'EUR' as const,
      imageUri: 'https://images.pokemontcg.io/base1/4_hires.png',
      confidence: 0.92,
    },
  },
  {
    label: 'Mid tier (medium value, medium confidence)',
    props: {
      itemName: 'Funko Pop! Marvel Iron Man (Glow Chase)',
      category: 'funko',
      condition: 'Near Mint',
      priceMid: 78,
      priceLow: 60,
      priceHigh: 110,
      currency: 'EUR' as const,
      imageUri: 'https://images.unsplash.com/photo-1605792657660-596af9009e82?w=800',
      confidence: 0.71,
    },
  },
  {
    label: 'Low tier (sub-€20, lower confidence)',
    props: {
      itemName: 'Generic LEGO Minifigure City Worker',
      category: 'lego',
      condition: 'Used Good',
      priceMid: 4.5,
      priceLow: 2,
      priceHigh: 8,
      currency: 'EUR' as const,
      imageUri: 'https://images.unsplash.com/photo-1558877385-81a1c7e67d72?w=800',
      confidence: 0.42,
    },
  },
];

// Production builds: render a 404-style placeholder so an Apple reviewer who
// somehow deep-links here doesn't see internal scaffolding UI. __DEV__ is
// inlined at build time by Metro, so the hooks-order rule isn't violated.
const IS_DEV = typeof __DEV__ !== 'undefined' && __DEV__;

function NotFound() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Not found</Text>
    </View>
  );
}

function DevShareCardPreview() {
  const [idx, setIdx] = useState(0);
  const sample = SAMPLES[idx];
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.container}>
      <Text style={styles.title}>ShareCard preview</Text>
      <View style={styles.tabs}>
        {SAMPLES.map((s, i) => (
          <Pressable
            key={i}
            onPress={() => setIdx(i)}
            style={[styles.tab, i === idx && styles.tabActive]}
          >
            <Text style={[styles.tabText, i === idx && styles.tabTextActive]}>
              {s.label}
            </Text>
          </Pressable>
        ))}
      </View>
      <View style={styles.cardWrap}>
        <ShareCard {...sample.props} />
      </View>
    </ScrollView>
  );
}

export default IS_DEV ? DevShareCardPreview : NotFound;

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: '#F1F5F9' },
  container: { padding: 24, alignItems: 'center', gap: 16, paddingBottom: 80 },
  title: { fontSize: 14, fontWeight: '700', color: '#475569' },
  tabs: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' },
  tab: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8,
    backgroundColor: '#fff', borderWidth: 1, borderColor: '#E2E8F0',
  },
  tabActive: { backgroundColor: '#0F172A', borderColor: '#0F172A' },
  tabText: { fontSize: 12, fontWeight: '600', color: '#475569' },
  tabTextActive: { color: '#F8FAFC' },
  cardWrap: { marginTop: 8 },
});
