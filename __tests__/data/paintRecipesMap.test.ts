/** paint_recipes is mapped, not cast (2026-09-26: the column was missing on prod). */
jest.mock('@/lib/supabase', () => ({ supabase: {} }));
import { toPaintRecipes } from '@/data/providers/buildPaintProvider';

describe('toPaintRecipes', () => {
  it('maps a stored recipe', () => {
    expect(toPaintRecipes([{ name: 'Armour', paints: [{ brand: 'Citadel', color: 'Leadbelcher', type: 'base' }], notes: '' }]))
      .toEqual([{ name: 'Armour', paints: [{ brand: 'Citadel', color: 'Leadbelcher', type: 'base' }], notes: '' }]);
  });
  it('drops malformed rows and survives null', () => {
    expect(toPaintRecipes([{ paints: [] }, 'x', null])).toEqual([]);
    expect(toPaintRecipes(null)).toEqual([]);
  });
});
