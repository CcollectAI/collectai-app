/**
 * ItemCatalogRefresh — small "Match against catalog" action for an item card.
 *
 * Triggers the same /catalog/match endpoint that QuickScan + add-manual use,
 * lets the user confirm before overwriting any attrs, and writes the result
 * via Supabase REST (RLS-safe; owner-only update).
 *
 * Why: the bake's catalog_learning_worker grows the catalog over time, but
 * existing user items don't get re-enriched. This action lets the user
 * opt-in retroactively. Non-destructive — only fills empty attrs by
 * default; user explicitly opts to overwrite via the second prompt.
 *
 * Wired 2026-05-02 alongside the QuickScan/add-manual canonical_key writers.
 */
import React, { useCallback, useState } from 'react';
import { View, Text, Pressable, ActivityIndicator, StyleSheet, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useToast } from '@/components/Toast';
import { matchCatalog, type CatalogMatchHit } from '@/api/itemsApi';
import { supabase } from '@/lib/supabase';
import { fireHaptic, HapticIntent } from '@/haptics';
import logger from '@/utils/logger';

interface Props {
  itemId: string;
  itemTitle: string;
  itemCategory: string;
  /** Current attrs jsonb on the item. Used to decide which fields are
   * empty (safe to fill) vs already-set (would need overwrite confirm). */
  currentAttrs: Record<string, unknown> | null;
  currentCanonicalKey: string | null;
  /** Called after a successful update so the parent can re-fetch. */
  onUpdated?: () => void;
}

// Fields the catalog match can populate. Keep in sync with /catalog/match
// response shape (CatalogMatchHit) and the add-manual auto-fill effect.
const FILLABLE_FIELDS: Array<{ attrKey: string; label: string; sourceKey: keyof CatalogMatchHit }> = [
  { attrKey: 'brand', label: 'Brand', sourceKey: 'brand' },
  { attrKey: 'set_code', label: 'Set', sourceKey: 'set_code' },
  { attrKey: 'rarity', label: 'Rarity', sourceKey: 'rarity' },
];

function describeChanges(
  best: CatalogMatchHit,
  currentAttrs: Record<string, unknown> | null,
  currentCanonicalKey: string | null,
): { proposed: Record<string, unknown>; canonicalKey: string | null; summary: string } {
  const summary: string[] = [];
  const proposed: Record<string, unknown> = {};

  // canonical_key — only set if currently null (never overwrite a real key)
  let nextCanonical: string | null = currentCanonicalKey;
  if (!currentCanonicalKey && best.item_key) {
    nextCanonical = best.item_key;
    summary.push(`• Link to catalog: ${best.title ?? best.item_key}`);
  } else if (currentCanonicalKey && best.item_key && best.item_key !== currentCanonicalKey) {
    // Different match — surface it but don't auto-change. User has to
    // explicitly retry; for now we keep the existing key.
    summary.push(`• Already linked to a different catalog entry — keeping existing link`);
  }

  for (const f of FILLABLE_FIELDS) {
    const v = best[f.sourceKey] as string | null | undefined;
    if (!v) continue;
    const existing = (currentAttrs?.[f.attrKey] ?? '') as string;
    if (!existing) {
      proposed[f.attrKey] = v;
      summary.push(`• ${f.label}: ${v}`);
    } else if (existing !== v) {
      // Skip overwriting — user keeps their value. The user can opt to
      // overwrite via a separate flow if they want.
      summary.push(`• ${f.label}: keeping your "${existing}" (catalog says "${v}")`);
    }
  }

  return {
    proposed,
    canonicalKey: nextCanonical,
    summary: summary.length > 0 ? summary.join('\n') : 'No new fields to add — everything matches what you already have.',
  };
}

export const ItemCatalogRefresh = React.memo(function ItemCatalogRefresh({
  itemId, itemTitle, itemCategory, currentAttrs, currentCanonicalKey, onUpdated,
}: Props) {
  const { colors: theme } = useAppTheme();
  const { showToast } = useToast();
  const [matching, setMatching] = useState(false);

  const handleRefresh = useCallback(async () => {
    if (matching) return;
    if (!itemTitle.trim() || !itemCategory.trim()) {
      showToast({ message: 'Need a title and category to match', type: 'info' });
      return;
    }
    setMatching(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);

    let bestHit: CatalogMatchHit | null = null;
    try {
      const res = await matchCatalog(itemTitle.trim(), itemCategory.trim());
      bestHit = res.best;
    } catch (e) {
      logger.warn('[ItemCatalogRefresh] match call failed:', e);
      showToast({ message: 'Catalog match failed — try again later', type: 'error' });
      setMatching(false);
      return;
    }

    if (!bestHit || (bestHit.match_score ?? 0) < 0.6) {
      showToast({
        message: bestHit
          ? `Best match was too weak (${Math.round((bestHit.match_score ?? 0) * 100)}%) — kept as-is`
          : 'No catalog match found',
        type: 'info',
      });
      setMatching(false);
      return;
    }

    const { proposed, canonicalKey, summary } = describeChanges(bestHit, currentAttrs, currentCanonicalKey);
    setMatching(false);

    const willChangeAttrs = Object.keys(proposed).length > 0;
    const willChangeCanonical = canonicalKey !== currentCanonicalKey;
    if (!willChangeAttrs && !willChangeCanonical) {
      showToast({ message: 'Already in sync with the catalog', type: 'info' });
      return;
    }

    const score = Math.round((bestHit.match_score ?? 0) * 100);
    Alert.alert(
      `Catalog match (${score}%)`,
      summary,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Apply',
          onPress: async () => {
            try {
              const update: Record<string, unknown> = {};
              if (willChangeCanonical) update.canonical_key = canonicalKey;
              if (willChangeAttrs) {
                update.attrs = { ...(currentAttrs ?? {}), ...proposed };
              }
              const { error } = await supabase
                .from('items')
                .update(update)
                .eq('id', itemId);
              if (error) {
                logger.warn('[ItemCatalogRefresh] update failed:', error);
                showToast({ message: 'Failed to update — try again', type: 'error' });
                return;
              }
              fireHaptic(HapticIntent.JUDGMENT_LOCKED);
              showToast({ message: 'Catalog data refreshed', type: 'success' });
              onUpdated?.();
            } catch (e) {
              logger.warn('[ItemCatalogRefresh] apply failed:', e);
              showToast({ message: 'Failed to update — try again', type: 'error' });
            }
          },
        },
      ],
    );
  }, [matching, itemTitle, itemCategory, currentAttrs, currentCanonicalKey, itemId, showToast, onUpdated]);

  return (
    <Pressable
      onPress={handleRefresh}
      disabled={matching}
      style={[styles.btn, { backgroundColor: theme.accent + '14', opacity: matching ? 0.7 : 1 }]}
      accessibilityRole="button"
      accessibilityLabel="Re-match this item against the catalog and update attributes"
    >
      {matching ? (
        <ActivityIndicator size="small" color={theme.accent} />
      ) : (
        <Ionicons name="link-outline" size={14} color={theme.accent} />
      )}
      <Text style={[styles.btnText, { color: theme.accent }]}>
        {matching ? 'Matching…' : 'Match against catalog'}
      </Text>
    </Pressable>
  );
});

const styles = StyleSheet.create({
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 14,
    marginTop: 8,
    marginBottom: 4,
  },
  btnText: {
    fontSize: 12,
    fontWeight: '600',
  },
});
