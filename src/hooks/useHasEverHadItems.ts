/**
 * Persists a single bit: has this user ever had items in their collection?
 *
 * Used by the items + analytics screens to skip skeleton loaders for
 * first-run users — they see the hero CTA from frame 1 instead of grey
 * silhouettes. The flag flips to true once any consumer reports a non-zero
 * item count (call `markHasItems`), and stays true forever after that.
 */

import { useCallback, useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = '@sparrowcollect/items_hasever';

export function useHasEverHadItems(): {
  // null while we're still reading from storage on mount
  hasEverHadItems: boolean | null;
  markHasItems: () => void;
} {
  const [hasEverHadItems, setHasEverHadItems] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(KEY)
      .then((v) => { if (!cancelled) setHasEverHadItems(v === '1'); })
      .catch(() => { if (!cancelled) setHasEverHadItems(false); });
    return () => { cancelled = true; };
  }, []);

  const markHasItems = useCallback(() => {
    setHasEverHadItems((prev) => {
      if (prev === true) return prev;
      AsyncStorage.setItem(KEY, '1').catch(() => {});
      return true;
    });
  }, []);

  return { hasEverHadItems, markHasItems };
}
