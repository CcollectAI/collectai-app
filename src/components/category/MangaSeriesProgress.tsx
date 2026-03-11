import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { Item } from '@/data';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  categoryId: string | undefined;
  items: Item[];
  accentColor: string;
  colors: AppTheme['colors'];
};

const MangaSeriesProgress: React.FC<Props> = ({ categoryId, items, accentColor, colors }) => {
  if (categoryId !== 'manga' || items.length === 0) return null;

  // Group items by series title (from attributes or name prefix)
  const seriesMap: Record<string, { count: number; total?: number; items: typeof items }> = {};
  for (const item of items) {
    const attrs = (item as Record<string, unknown>).attributesJson as Record<string, unknown> | undefined;
    const seriesName = (attrs?.title as string) || item.name.replace(/\s*vol\.?\s*\d+.*/i, '').replace(/\s*#\d+.*/i, '').trim();
    if (!seriesName) continue;
    if (!seriesMap[seriesName]) {
      seriesMap[seriesName] = { count: 0, total: undefined, items: [] };
    }
    seriesMap[seriesName].count += 1;
    seriesMap[seriesName].items.push(item);
    const totalVols = attrs?.total_volumes;
    if (totalVols && typeof totalVols === 'string' && parseInt(totalVols, 10) > 0) {
      seriesMap[seriesName].total = parseInt(totalVols, 10);
    }
  }

  const seriesEntries = Object.entries(seriesMap)
    .filter(([_, s]) => s.count > 0)
    .sort((a, b) => b[1].count - a[1].count);

  if (seriesEntries.length === 0) return null;

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeaderRow}>
        <Ionicons name="library-outline" size={18} color={accentColor} />
        <Text style={[styles.sectionTitle, { color: colors.text, marginBottom: 0 }]}>Series Progress</Text>
      </View>
      {seriesEntries.slice(0, 8).map(([seriesName, series]) => {
        const pct = series.total ? Math.min(100, Math.round((series.count / series.total) * 100)) : null;
        return (
          <View key={seriesName} style={[styles.seriesProgressCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.seriesProgressHeader}>
              <Text style={[styles.seriesProgressName, { color: colors.text }]} numberOfLines={1}>
                {seriesName}
              </Text>
              <Text style={[styles.seriesProgressCount, { color: accentColor }]}>
                {series.count}{series.total ? `/${series.total}` : ''} vol
              </Text>
            </View>
            {pct !== null && (
              <View style={[styles.seriesProgressBarBg, { backgroundColor: colors.border }]}>
                <View
                  style={[
                    styles.seriesProgressBarFill,
                    { backgroundColor: pct >= 100 ? colors.success : accentColor, width: `${pct}%` },
                  ]}
                />
              </View>
            )}
            {pct !== null && pct >= 100 && (
              <View style={[styles.seriesCompleteBadge, { backgroundColor: colors.success + '20' }]}>
                <Ionicons name="checkmark-circle" size={14} color={colors.success} />
                <Text style={{ fontSize: 11, fontWeight: '600', color: colors.success }}>Complete!</Text>
              </View>
            )}
          </View>
        );
      })}
      {seriesEntries.length > 8 && (
        <Text style={[styles.emptyText, { color: colors.muted }]}>
          +{seriesEntries.length - 8} more series
        </Text>
      )}
    </View>
  );
};

export default React.memo(MangaSeriesProgress);

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  emptyText: {
    fontSize: 13,
  },
  seriesProgressCard: {
    borderRadius: 10,
    borderWidth: 1,
    padding: 12,
    marginBottom: 8,
  },
  seriesProgressHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  seriesProgressName: {
    fontSize: 14,
    fontWeight: '600',
    flex: 1,
    marginRight: 8,
  },
  seriesProgressCount: {
    fontSize: 13,
    fontWeight: '700',
  },
  seriesProgressBarBg: {
    height: 6,
    borderRadius: 3,
    marginTop: 8,
    overflow: 'hidden',
  },
  seriesProgressBarFill: {
    height: 6,
    borderRadius: 3,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  seriesCompleteBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    marginTop: 6,
  },
});
