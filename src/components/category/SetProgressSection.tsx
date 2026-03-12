/**
 * SetProgressSection — Shows set completion progress for a category.
 * Uses set_router backend (listSets, getMySetProgress).
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Share } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import logger from '@/utils/logger';

type SetItem = {
  id: string;
  name: string;
  total_items: number;
  image_url?: string | null;
};

type SetProgressItem = {
  set_id: string;
  owned_count: number;
  completion_pct: number;
};

type Props = {
  categoryId: string;
  onSetPress?: (setId: string) => void;
};

export default React.memo(function SetProgressSection({ categoryId, onSetPress }: Props) {
  const { colors } = useAppTheme();
  const [sets, setSets] = useState<SetItem[]>([]);
  const [progress, setProgress] = useState<Record<string, SetProgressItem>>({});

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      collectorsApi.listSets(categoryId),
      collectorsApi.getMySetProgress(),
    ])
      .then(([setsData, progressData]) => {
        if (cancelled) return;
        const setsArr = Array.isArray((setsData as { sets?: unknown[] })?.sets)
          ? (setsData as { sets: SetItem[] }).sets
          : Array.isArray(setsData) ? setsData as SetItem[] : [];
        setSets(setsArr.slice(0, 8));

        const progArr = Array.isArray((progressData as { progress?: unknown[] })?.progress)
          ? (progressData as { progress: SetProgressItem[] }).progress
          : Array.isArray(progressData) ? progressData as SetProgressItem[] : [];
        const map: Record<string, SetProgressItem> = {};
        for (const p of progArr) {
          map[p.set_id] = p;
        }
        setProgress(map);
      })
      .catch((err) => logger.warn('[SetProgress] fetch failed:', err));

    return () => { cancelled = true; };
  }, [categoryId]);

  if (sets.length === 0) return null;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="layers-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>Complete Your Sets</Text>
        <View style={{ flex: 1 }} />
        <AnimatedPressable
          onPress={() => {
            const lines = sets.map((s) => {
              const p = progress[s.id];
              return `${s.name}: ${p?.owned_count ?? 0}/${s.total_items} (${Math.round(p?.completion_pct ?? 0)}%)`;
            });
            Share.share({ message: `My Set Progress:\n${lines.join('\n')}` });
          }}
          accessibilityRole="button"
          accessibilityLabel="Share set progress"
        >
          <Ionicons name="share-outline" size={18} color={colors.muted} />
        </AnimatedPressable>
      </View>

      {sets.map((set) => {
        const prog = progress[set.id];
        const owned = prog?.owned_count ?? 0;
        const total = set.total_items || 1;
        const pct = prog?.completion_pct ?? 0;
        const isComplete = pct >= 100;
        const barColor = isComplete ? colors.success : pct >= 50 ? colors.warning : colors.accent;

        return (
          <AnimatedPressable
            key={set.id}
            onPress={() => onSetPress?.(set.id)}
            style={[styles.row, { borderBottomColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel={`${set.name}: ${owned} of ${total} items`}
          >
            <View style={styles.info}>
              <Text style={[styles.setName, { color: colors.text }]} numberOfLines={1}>
                {set.name}
              </Text>
              <Text style={[styles.setMeta, { color: colors.muted }]}>
                {owned}/{total} items
              </Text>
            </View>
            <View style={styles.progressWrap}>
              <View style={[styles.progressBar, { backgroundColor: colors.border + '40' }]}>
                <View
                  style={[
                    styles.progressFill,
                    { backgroundColor: barColor, width: `${Math.min(100, pct)}%` },
                  ]}
                />
              </View>
              {isComplete ? (
                <Ionicons name="checkmark-circle" size={16} color={colors.success} />
              ) : (
                <Text style={[styles.pctText, { color: colors.muted }]}>{Math.round(pct)}%</Text>
              )}
            </View>
          </AnimatedPressable>
        );
      })}
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
    fontSize: 16,
    fontWeight: '700',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  info: {
    flex: 1,
    marginRight: 12,
  },
  setName: {
    fontSize: 14,
    fontWeight: '600',
  },
  setMeta: {
    fontSize: 11,
    marginTop: 2,
  },
  progressWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    width: 120,
  },
  progressBar: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressFill: {
    height: 6,
    borderRadius: 3,
  },
  pctText: {
    fontSize: 12,
    fontWeight: '600',
    minWidth: 30,
    textAlign: 'right',
  },
});
