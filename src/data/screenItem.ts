/**
 * Provider → screen mapping for collection items.
 *
 * This is the seam where enrichment used to silently die: the items screen
 * mapped `condition: undefined` and `collectionName: ""` inline, so every rich
 * field the add flow stored (condition, brand, year, series, edition, and even
 * the collection name) was thrown away before any card could render it. tsc
 * never caught it because `undefined` is a legal value for an optional field,
 * and the isolated card tests pass their own props — nothing exercised THIS
 * mapping. Extracting it here makes the seam a pure, unit-testable function so
 * `screenItem.test.ts` can pin that every provider field reaches the card.
 */
import type { Item as DataItem } from './types';

/** Shape consumed by the items list rows + gallery tiles. */
export type ScreenItem = {
  id: string;
  name: string;
  category: string;
  collectionName: string;
  value: number;
  condition?: string;
  notes?: string;
  imageUrl?: string;
  // Rich detail surfaced on the card (2026-07-15 enrichment).
  brand?: string;
  year?: number;
  series?: string;
  editionLabel?: string;
  source?: string;
  isManual?: boolean;
  purchasePriceEur?: number | null;
  purchasedAt?: string | null;
  /** `v_item_values_v1.value_source` — carried so the row can say whether the
   *  figure is comp-backed or somebody's estimate. Dropping it here would make
   *  the chip render nothing on the one screen that shows twenty values at
   *  once, which is exactly where the distinction earns its keep. */
  valueSource?: string | null;
};

/**
 * Map one provider Item to the screen shape. Keep this a pure pass-through:
 * do NOT hardcode fields to `undefined`/`""` — if a value isn't wanted on the
 * card, drop it from ScreenItem, don't silently null it here.
 */
export function mapDataItemToScreenItem(it: DataItem): ScreenItem {
  const source = (it as Record<string, unknown>).source as string | undefined;
  return {
    id: it.id,
    name: it.name || '(Untitled)',
    category: it.category,
    // The provider resolves collection_name into collections[]. Show the first
    // tag; empty string when none (the meta line guards on it).
    collectionName: it.collections?.[0] ?? '',
    value: it.price,
    condition: it.condition,
    notes: undefined,
    imageUrl: it.imageUrl,
    brand: it.brand,
    year: it.year,
    series: it.series,
    editionLabel: it.editionLabel,
    source,
    isManual: source === 'manual' && !it.priceBand,
    purchasePriceEur: it.purchasePriceEur ?? null,
    purchasedAt: it.purchasedAt ?? null,
    valueSource: it.valueSource ?? null,
  };
}
