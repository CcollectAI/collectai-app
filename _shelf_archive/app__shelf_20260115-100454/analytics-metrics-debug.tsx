import React from 'react';
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import {
  PortfolioItem,
  CollectionDefinition,
  buildPortfolioSnapshotDemo,
} from '@/analytics/portfolioMetrics';

const formatCurrency = (v: number) => v.toFixed(0) + ' €';
const formatPct = (v: number) =>
  (v >= 0 ? '+' : '') + v.toFixed(1) + '%';

const AnalyticsMetricsDebug: React.FC = () => {
  // Demo items & collections – replace with real data wiring later.
  const items: PortfolioItem[] = [
    {
      id: '1',
      title: 'Pokémon Charizard Holo',
      category: 'Pokémon TCG',
      costBasis: 200,
      currentValue: 450,
      rarityScore: 0.9,
      collectionKey: 'pokemon-base-set',
      inTrackedSet: true,
    },
    {
      id: '2',
      title: 'Pokémon Blastoise Holo',
      category: 'Pokémon TCG',
      costBasis: 150,
      currentValue: 280,
      rarityScore: 0.8,
      collectionKey: 'pokemon-base-set',
      inTrackedSet: true,
    },
    {
      id: '3',
      title: 'Funko Iron Man',
      category: 'Funko Pops',
      costBasis: 25,
      currentValue: 40,
      rarityScore: 0.5,
      collectionKey: 'funko-marvel',
      inTrackedSet: true,
    },
    {
      id: '4',
      title: 'Diecast Porsche 911',
      category: 'Diecast',
      costBasis: 40,
      currentValue: 60,
      rarityScore: 0.6,
      inTrackedSet: false,
    },
  ];

  const collections: CollectionDefinition[] = [
    {
      key: 'pokemon-base-set',
      label: 'Pokémon Base Set (Demo)',
      requiredItemCount: 15,
    },
    {
      key: 'funko-marvel',
      label: 'Funko Marvel (Demo)',
      requiredItemCount: 10,
    },
  ];

  const snapshot = buildPortfolioSnapshotDemo(items, collections);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>Analytics metrics debug</Text>
        <Text style={styles.subtitle}>
          Pure data view of the portfolio analytics engine:
          P/L card, series, allocations, winners/losers,
          completeness/rarity status, and tier.
        </Text>

        {/* P/L CARD */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>P/L card</Text>
          <Text>Start: {formatCurrency(snapshot.plCard.startValue)}</Text>
          <Text>Current: {formatCurrency(snapshot.plCard.currentValue)}</Text>
          <Text>P/L: {formatCurrency(snapshot.plCard.plAbs)}</Text>
          <Text>P/L %: {formatPct(snapshot.plCard.plPct)}</Text>
        </View>

        {/* SERIES */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Value over time (12 pts)</Text>
          {snapshot.series.map((pt) => (
            <Text key={pt.label}>
              {pt.label} → {formatCurrency(pt.value)}
            </Text>
          ))}
        </View>

        {/* CATEGORY ALLOCATION */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Category allocation</Text>
          {snapshot.allocations.map((a) => (
            <Text key={a.category}>
              {a.category}: {formatCurrency(a.value)} (
              {(a.pct * 100).toFixed(1)}%)
            </Text>
          ))}
        </View>

        {/* WINNERS / LOSERS */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Top winners</Text>
          {snapshot.winners.map((w) => (
            <Text key={w.id}>
              {w.title}: {formatCurrency(w.plAbs)} (
              {formatPct(w.plPct)})
            </Text>
          ))}
          <View style={{ height: 8 }} />
          <Text style={styles.cardTitle}>Top losers</Text>
          {snapshot.losers.map((l) => (
            <Text key={l.id}>
              {l.title}: {formatCurrency(l.plAbs)} (
              {formatPct(l.plPct)})
            </Text>
          ))}
        </View>

        {/* COMPLETENESS + RARITY + STATUS */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Status & leaderboard inputs</Text>
          <Text>
            Completeness score:{' '}
            {snapshot.completeness.completenessScore.toFixed(2)}
          </Text>
          <Text>
            Complete collections:{' '}
            {snapshot.completeness.completeCollections}/
            {snapshot.completeness.totalTrackedCollections}
          </Text>
          <Text>
            Avg rarity score:{' '}
            {snapshot.rarity.avgRarityScore.toFixed(2)}
          </Text>
          <Text>
            Rare share:{' '}
            {(snapshot.rarity.rareShare * 100).toFixed(1)}%
          </Text>
          <View style={{ height: 8 }} />
          <Text>
            Status tier: {snapshot.status.tier.toUpperCase()}
          </Text>
          <Text>Points: {snapshot.status.points.toFixed(1)}</Text>
          <Text>
            Components → completeness:{' '}
            {(snapshot.status.completenessScore * 100).toFixed(1)}%, rarity:{' '}
            {(snapshot.status.rarityScore * 100).toFixed(1)}%
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#e2f3ff',
  },
  content: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#0f172a',
  },
  subtitle: {
    fontSize: 12,
    color: '#4b5563',
    marginTop: 4,
    marginBottom: 4,
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 12,
    marginTop: 8,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#0f172a',
    marginBottom: 4,
  },
});

export default AnalyticsMetricsDebug;
