/**
 * itemsProvider — purchase field mapping tests.
 *
 * Pins the FE↔DB contract for the acquisition columns we surfaced 2026-05-01:
 * items.purchase_price_eur / purchase_currency / purchased_at / purchase_notes
 * → Item.purchasePriceEur / purchaseCurrency / purchasedAt / purchaseNotes.
 *
 * Without these tests, a future ITEMS_SELECT change that drops a column
 * would silently null out the paid-price surface on every items row again.
 */
import { jest } from '@jest/globals';

let mockRows: unknown[] = [];
let mockError: { message: string } | null = null;

jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    from: jest.fn().mockReturnThis(),
    select: jest.fn().mockReturnThis(),
    order: jest.fn().mockReturnThis(),
    range: jest.fn().mockImplementation(() => Promise.resolve({ data: mockRows, error: mockError })),
  },
}));

jest.mock('../../src/api/collectorsApi', () => ({
  collectorsApi: { post: jest.fn(), get: jest.fn(), patch: jest.fn(), delete: jest.fn() },
}));

jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { warn: jest.fn(), error: jest.fn(), info: jest.fn(), debug: jest.fn() },
  warn: jest.fn(),
}));

import { listItems } from '../../src/data/providers/itemsProvider';

describe('itemsProvider.listItems — purchase field mapping', () => {
  beforeEach(() => {
    mockRows = [];
    mockError = null;
  });

  it('maps purchase_price_eur and purchase_currency through to the Item', async () => {
    mockRows = [
      {
        id: 'i1',
        title: 'Charizard 1st Edition',
        category: 'pokemon',
        updated_at: '2026-05-01T00:00:00Z',
        attrs: null,
        collection_name: 'Base Set',
        image_url: null,
        purchase_price_eur: 250,
        purchase_currency: 'EUR',
        purchased_at: '2024-12-15',
        purchase_notes: 'Local card shop',
        price_predictions: [],
      },
    ];

    const items = await listItems({ limit: 10, offset: 0 });
    expect(items).toHaveLength(1);
    expect(items[0].purchasePriceEur).toBe(250);
    expect(items[0].purchaseCurrency).toBe('EUR');
    expect(items[0].purchasedAt).toBe('2024-12-15');
    expect(items[0].purchaseNotes).toBe('Local card shop');
  });

  it('returns null (not undefined) for missing purchase fields so callers can distinguish "no record" from "field absent"', async () => {
    mockRows = [
      {
        id: 'i2',
        title: 'Untracked scan',
        category: 'pokemon',
        updated_at: null,
        attrs: null,
        collection_name: null,
        image_url: null,
        // none of the purchase_* columns set
        price_predictions: [],
      },
    ];

    const items = await listItems({ limit: 10, offset: 0 });
    expect(items).toHaveLength(1);
    // null, not undefined — see Item type comment in src/data/types.ts
    expect(items[0].purchasePriceEur).toBeNull();
    expect(items[0].purchaseCurrency).toBeNull();
    expect(items[0].purchasedAt).toBeNull();
    expect(items[0].purchaseNotes).toBeNull();
  });

  it('returns [] on Supabase error without throwing (matches itemsProvider error contract)', async () => {
    mockRows = [];
    mockError = { message: 'PostgREST 400 (column does not exist)' };

    const items = await listItems({ limit: 10, offset: 0 });
    expect(items).toEqual([]);
  });
});
