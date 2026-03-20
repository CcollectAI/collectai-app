/**
 * Temporary preview screen for the ShareCard component.
 * Navigate to: /preview-share-card
 * DELETE THIS FILE before production release.
 */

import React from 'react';
import { View, StyleSheet, ScrollView, Text } from 'react-native';
import { Stack } from 'expo-router';
import { ShareCard } from '@/components/quickscan/ShareCard';

const MOCK_ITEMS = [
  {
    itemName: 'Charizard Base Set 1st Edition Holo #4',
    category: 'pokemon',
    condition: 'Near Mint',
    priceMid: 12500,
    priceLow: 9800,
    priceHigh: 18000,
    currency: 'EUR' as const,
    imageUri: 'https://images.pokemontcg.io/base1/4_hires.png',
    confidence: 0.92,
  },
  {
    itemName: 'Rolex Submariner Date 126610LN',
    category: 'watches',
    condition: 'Excellent',
    priceMid: 9450,
    priceLow: 8200,
    priceHigh: 11000,
    currency: 'EUR' as const,
    imageUri: 'https://images.unsplash.com/photo-1587836374828-4dbafa94cf0e?w=400&h=400&fit=crop',
    confidence: 0.85,
  },
  {
    itemName: 'Funko Pop! Dragon Ball Z - Vegeta Over 9000 #3618',
    category: 'funko',
    condition: 'Mint / Sealed',
    priceMid: 340,
    priceLow: 280,
    priceHigh: 420,
    currency: 'USD' as const,
    imageUri: 'https://images.unsplash.com/photo-1608889476518-738c9b1dcb40?w=400&h=400&fit=crop',
    confidence: 0.78,
  },
  {
    itemName: 'Miles Davis - Kind of Blue (1959 Columbia 6-Eye Mono)',
    category: 'vinyl_records',
    condition: 'Very Good+',
    priceMid: 1850,
    priceLow: 1200,
    priceHigh: 2800,
    currency: 'EUR' as const,
    imageUri: 'https://images.unsplash.com/photo-1539375665275-f9de415ef9ac?w=400&h=400&fit=crop',
    confidence: 0.61,
  },
];

export default function PreviewShareCardScreen() {
  return (
    <>
      <Stack.Screen options={{ title: 'ShareCard Preview', headerShown: true }} />
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
      >
        <Text style={styles.hint}>
          Preview of the share card that gets generated when users tap Share on a scan result.
          {'\n'}This is what gets shared to Instagram/TikTok/group chats.
        </Text>

        {MOCK_ITEMS.map((item, idx) => (
          <View key={idx} style={styles.cardWrapper}>
            <Text style={styles.label}>
              {idx + 1}. {item.category} — {Math.round(item.confidence * 100)}% confidence
            </Text>
            <ShareCard {...item} />
          </View>
        ))}

        <Text style={styles.deleteNote}>
          DELETE app/preview-share-card.tsx before production release
        </Text>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F1F5F9',
  },
  content: {
    alignItems: 'center',
    paddingVertical: 24,
    paddingHorizontal: 16,
    gap: 32,
  },
  hint: {
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
    lineHeight: 20,
    paddingHorizontal: 8,
  },
  cardWrapper: {
    alignItems: 'center',
    gap: 8,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: '#94A3B8',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  deleteNote: {
    fontSize: 11,
    color: '#EF4444',
    fontWeight: '600',
    marginTop: 8,
  },
});
