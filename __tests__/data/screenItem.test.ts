/**
 * mapDataItemToScreenItem — provider → screen pass-through gate.
 *
 * This is the seam that silently dropped enrichment: the items screen mapped
 * `condition: undefined` and `collectionName: ""` inline, so condition, brand,
 * year, series, edition, and the collection name never reached any card even
 * though the DB stored them. tsc can't catch that (undefined is valid for an
 * optional field) and the isolated card tests pass their own props. These
 * assertions pin every enriched field so a future edit can't null it out again.
 */
import { mapDataItemToScreenItem } from '../../src/data/screenItem';
import type { Item as DataItem } from '../../src/data/types';

function makeDataItem(overrides: Partial<DataItem> = {}): DataItem {
  return {
    id: 'i1',
    name: 'Charizard 1st Edition',
    category: 'pokemon',
    price: 100,
    collections: ['Base Set'],
    condition: 'PSA 9',
    brand: 'Wizards of the Coast',
    year: 1999,
    series: 'Base',
    editionLabel: '1st Edition',
    imageUrl: 'https://example.com/charizard.png',
    ...overrides,
  };
}

describe('mapDataItemToScreenItem — enrichment pass-through', () => {
  it('carries every rich field through to the screen shape', () => {
    const row = mapDataItemToScreenItem(makeDataItem());
    expect(row.condition).toBe('PSA 9');
    expect(row.brand).toBe('Wizards of the Coast');
    expect(row.year).toBe(1999);
    expect(row.series).toBe('Base');
    expect(row.editionLabel).toBe('1st Edition');
    expect(row.imageUrl).toBe('https://example.com/charizard.png');
  });

  it('resolves collectionName from collections[0]', () => {
    expect(mapDataItemToScreenItem(makeDataItem()).collectionName).toBe('Base Set');
  });

  it('never hardcodes condition to undefined (the original bug)', () => {
    // Regression pin: this exact assertion fails against the pre-fix code,
    // which set `condition: undefined` regardless of the provider value.
    expect(mapDataItemToScreenItem(makeDataItem({ condition: 'Near Mint' })).condition).toBe('Near Mint');
  });

  it('falls back to empty collectionName (not a crash) when there are no collections', () => {
    expect(mapDataItemToScreenItem(makeDataItem({ collections: undefined })).collectionName).toBe('');
  });

  it('leaves rich fields undefined for a sparse (QuickScan-only) item', () => {
    const sparse = mapDataItemToScreenItem({ id: 'i2', name: 'Mystery', category: 'other', price: 0 } as DataItem);
    expect(sparse.condition).toBeUndefined();
    expect(sparse.brand).toBeUndefined();
    expect(sparse.year).toBeUndefined();
    expect(sparse.collectionName).toBe('');
  });

  it('maps price → value and title fallback', () => {
    const row = mapDataItemToScreenItem(makeDataItem({ price: 42 }));
    expect(row.value).toBe(42);
    expect(mapDataItemToScreenItem({ id: 'x', name: '', category: 'c', price: 1 } as DataItem).name).toBe('(Untitled)');
  });
});
