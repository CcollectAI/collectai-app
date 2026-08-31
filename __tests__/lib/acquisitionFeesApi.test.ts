/**
 * THREE states on the wire, not two.
 *
 * `updateItemPurchase` must OMIT a key the caller did not address, because the
 * server distinguishes omitted / null / value via `model_fields_set`:
 *   - resending an unchanged `purchase_price` makes the server re-convert it at
 *     TODAY's rate, so a non-EUR cost basis drifts on every unrelated save
 *   - and omission is what lets fees be edited on their own
 *
 * Asserts the BODY, because "we pass undefined" is not the same claim as "the
 * key is absent from the JSON" — `{a: undefined}` still has the key in JS.
 */
jest.mock('@/api/httpClient', () => ({
  get: jest.fn(), post: jest.fn(), del: jest.fn(),
  patch: jest.fn((url: string, body: unknown) => Promise.resolve({ url, body })),
}));

import { patch } from '@/api/httpClient';
import { updateItemPurchase } from '@/api/itemsApi';

const bodyOf = () => (patch as jest.Mock).mock.calls.at(-1)![1] as Record<string, unknown>;

beforeEach(() => (patch as jest.Mock).mockClear());

describe('updateItemPurchase — omitted is not null', () => {
  it('omits purchase_price entirely when undefined (fees-only edit)', async () => {
    await updateItemPurchase('i1', undefined, 'USD', undefined, 70);
    const b = bodyOf();
    expect('purchase_price' in b).toBe(false);
    expect(b.acquisition_fees).toBe(70);
    expect(b.purchase_currency).toBe('USD');
  });

  it('omits acquisition_fees entirely when undefined (price-only edit)', async () => {
    await updateItemPurchase('i1', 950, 'EUR');
    const b = bodyOf();
    expect(b.purchase_price).toBe(950);
    expect('acquisition_fees' in b).toBe(false);
  });

  it('sends an EXPLICIT null when clearing — that is a different state', async () => {
    await updateItemPurchase('i1', null, 'EUR', undefined, null);
    const b = bodyOf();
    expect('purchase_price' in b).toBe(true);
    expect(b.purchase_price).toBeNull();
    expect('acquisition_fees' in b).toBe(true);
    expect(b.acquisition_fees).toBeNull();
  });

  it('sends both when both changed', async () => {
    await updateItemPurchase('i1', 900, 'EUR', undefined, 56.25);
    expect(bodyOf()).toMatchObject({ purchase_price: 900, acquisition_fees: 56.25 });
  });

  it('zero is a VALUE, not an absence — 0 fees must reach the server', async () => {
    await updateItemPurchase('i1', undefined, 'EUR', undefined, 0);
    expect(bodyOf().acquisition_fees).toBe(0);
  });

  it('purchased_at keeps its existing omit-when-undefined behaviour', async () => {
    await updateItemPurchase('i1', 900, 'EUR');
    expect('purchased_at' in bodyOf()).toBe(false);
  });
});
