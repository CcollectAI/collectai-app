/** A zero-confidence category is not pre-filled (walk 2026-09-27: "Nintendo Merch" at 0.00). */
import { handoffCategoryName } from '../../src/lib/quickscanHandoff';

it('drops a category vision had no confidence in', () => {
  expect(handoffCategoryName('nintendo_merch', 0)).toBeUndefined();
  expect(handoffCategoryName('nintendo_merch', null)).toBeUndefined();
});
it('keeps a category vision was sure of, by display name', () => {
  expect(handoffCategoryName('pokemon', 0.95)).toBe('Pokémon');
});
it('no slug, no category', () => {
  expect(handoffCategoryName('', 0.9)).toBeUndefined();
});
