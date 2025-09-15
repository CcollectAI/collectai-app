import { useSyncExternalStore } from 'react';

export type NewItem = {
  category: string;
  name: string;
  price: number;      // estimated value shown in Items
  pct?: number;       // optional % vs purchase price
  notes?: string;
};
export type Item = NewItem & { id: string };

const state: { items: Item[] } = { items: [] };
const subs = new Set<() => void>();
const emit = () => subs.forEach((f) => f());

function subscribe(cb: () => void) { subs.add(cb); return () => subs.delete(cb); }
function getSnapshot() { return state.items; }

export function useItems() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
export function addItem(input: NewItem) {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2,8)}`;
  state.items.push({ id, ...input });
  emit();
}

// compute a simple tier by category total (no extra deps)
export type Tier = 'silver' | 'gold' | 'platinum';
export function tierFromTotal(total: number): Tier {
  if (total >= 1500) return 'platinum';
  if (total >= 500) return 'gold';
  return 'silver';
}

export function groupByCategory(items: Item[]) {
  const map = new Map<string, Item[]>();
  for (const it of items) {
    const arr = map.get(it.category) || [];
    arr.push(it);
    map.set(it.category, arr);
  }
  return Array.from(map.entries()).map(([category, items]) => {
    const total = items.reduce((s, it) => s + (it.price || 0), 0);
    return { category, items, total, tier: tierFromTotal(total) as Tier };
  });
}
