/**
 * Prod's create RPC writes 'Backlog' and the column default is 'Active'; the
 * screen groups on the pipeline ids. Walked 2026-10-15: a new project read
 * "Backlog" under IN PROGRESS with Wishlist (0).
 */
jest.mock('../../src/lib/supabase', () => ({ supabase: {} }));
import { normalizeProjectStatus } from '../../src/data/providers/buildPaintProvider';

it.each([
  ['Backlog', 'wishlist'],
  ['Active', 'in_progress'],
  ['active', 'in_progress'],
  ['Completed', 'finished'],
  ['primed', 'primed'],
  ['wishlist', 'wishlist'],
  [null, undefined],
  ['', undefined],
])('%s -> %s', (raw, expected) => {
  expect(normalizeProjectStatus(raw)).toBe(expected);
});
