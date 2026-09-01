/**
 * itemsProvider — where a member's own number is written, and who authored it.
 *
 * Three defects this pins, all found 2026-08-19:
 *
 * 1. `updateItem` accepted `price` in its signature and mapped it to NOTHING.
 *    The offline queue replays whatever was queued verbatim, so a queued price
 *    edit was dropped with no error.
 * 2. There were TWO user-estimate columns at different ranks of the value
 *    chain — `add-manual` wrote `predicted_price_eur` (link 3, a column whose
 *    NAME says model output) while everything else wrote `estimated_value`
 *    (link 4). An older typed number outranked a newer correction.
 * 3. `persistQuickscanDraft` posted four fields and dropped the scan's
 *    estimate and condition entirely, so a scanned item saved with no value
 *    and the member had to retype what the app had just told them.
 *
 * And the provenance stamp: `estimated_value` is written by this screen, the
 * CSV importer and QuickScan drafts, and `POST /items` sets no `items.source`,
 * so the column cannot say whether a person or a vision model produced the
 * number. `attrs.value_entry` is what lets the UI say "app estimate" instead
 * of "your estimate" — see v_item_values_v1.value_source.
 */
import { jest } from '@jest/globals';

let mockUpdatePayload: Record<string, unknown> | null = null;
let mockPostBody: Record<string, unknown> | null = null;
let mockPatchBody: Record<string, unknown> | null = null;

jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    from: jest.fn().mockReturnThis(),
    update: jest.fn(function (this: unknown, payload: Record<string, unknown>) {
      mockUpdatePayload = payload;
      return this;
    }),
    eq: jest.fn().mockReturnThis(),
    select: jest.fn().mockReturnThis(),
    single: jest.fn().mockImplementation(() =>
      Promise.resolve({ data: { id: 'i1', title: 'x', category: 'lego' }, error: null }),
    ),
  },
}));

jest.mock('../../src/api/collectorsApi', () => ({
  collectorsApi: {
    post: jest.fn((_path: string, body: Record<string, unknown>) => {
      mockPostBody = body;
      return Promise.resolve({ id: 'new-item-id' });
    }),
    patch: jest.fn((_path: string, body: Record<string, unknown>) => {
      mockPatchBody = body;
      return Promise.resolve({});
    }),
    get: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { warn: jest.fn(), error: jest.fn(), info: jest.fn(), debug: jest.fn() },
  warn: jest.fn(),
}));

import { updateItem, persistQuickscanDraft } from '../../src/data/providers/itemsProvider';

beforeEach(() => {
  mockUpdatePayload = null;
  mockPostBody = null;
  mockPatchBody = null;
});

describe('updateItem writes the price it accepts', () => {
  it('maps price onto estimated_value — the single user-estimate column', async () => {
    await updateItem('i1', { price: 42.5 });
    expect(mockUpdatePayload).toEqual({ estimated_value: 42.5 });
  });

  it('never writes predicted_price_eur — that rank is retired', async () => {
    await updateItem('i1', { price: 42.5 });
    expect(mockUpdatePayload).not.toHaveProperty('predicted_price_eur');
  });

  it('clears with null rather than 0 — "no estimate" is not "worth nothing"', async () => {
    await updateItem('i1', { price: NaN as unknown as number });
    expect(mockUpdatePayload).toEqual({ estimated_value: null });
  });

  it('leaves the payload untouched when price is not part of the patch', async () => {
    await updateItem('i1', { name: 'Renamed' });
    expect(mockUpdatePayload).not.toHaveProperty('estimated_value');
  });
});

describe('persistQuickscanDraft keeps what the scan found', () => {
  const draft = {
    photoUri: 'file:///x.jpg',
    categoryId: 'pokemon',
    title: 'Charizard',
    canonicalKey: 'base1-base1-4',
    estimatedValue: 187.5,
    condition: 'Near Mint',
    scanBand: { q10: 150, q50: 187.5, q90: 240, confidence: 83 },
  };

  it('persists the estimate, and NORMALISES the condition to a slug', async () => {
    // Updated 2026-09-01. The draft carries a display name ('Near Mint') and
    // the column stores a SLUG — items.condition held both vocabularies at
    // once until `toConditionSlug` was added at this write chokepoint
    // (docs/TAXONOMY.md; measured on prod: new_sealed 10, near_mint 8, mint 5
    // alongside Sealed, Mint, NM). Asserting the display name here would pin
    // the drift the normalisation removed.
    await persistQuickscanDraft(draft);
    expect(mockPostBody).toMatchObject({
      estimated_value: 187.5,
      condition: 'near_mint',
      canonical_key: 'base1-base1-4',
    });
  });

  it("stamps the estimate as the APP's, not the member's", async () => {
    await persistQuickscanDraft(draft);
    expect(
      (mockPatchBody?.attributes as Record<string, unknown>)?.value_entry,
    ).toBe('app');
  });

  it('keeps the band as evidence in attrs, not in the value chain', async () => {
    // quick_predictions is link 1 and outranks the catalogue model. A vision
    // guess there would beat a comp-backed price for an identified product —
    // the exact opposite of the rule that an identified product uses our
    // database estimate.
    await persistQuickscanDraft(draft);
    const attrs = mockPatchBody?.attributes as Record<string, unknown>;
    expect(attrs.scan).toMatchObject({ q10: 150, q50: 187.5, q90: 240 });
  });

  it('sends no estimate, and no stamp, when the scan produced none', async () => {
    await persistQuickscanDraft({ ...draft, estimatedValue: null, scanBand: null });
    expect(mockPostBody?.estimated_value).toBeUndefined();
    expect(
      (mockPatchBody?.attributes as Record<string, unknown> | undefined)?.value_entry,
    ).toBeUndefined();
  });
});
