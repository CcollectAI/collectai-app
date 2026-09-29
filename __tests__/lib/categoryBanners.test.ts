/**
 * Explore banners. A focus only works on an UNCROPPED source: with the CDN's
 * own fit=crop the part you meant to show is already gone before the app
 * positions anything (Bandai's head, 2026-09-29).
 */
import { CATEGORIES } from '@/data/categories';

describe('category banners', () => {
  it('every banner is an https image URL or empty (empty = icon fallback)', () => {
    for (const c of CATEGORIES) {
      expect(c.bannerImageUrl === '' || c.bannerImageUrl.startsWith('https://')).toBe(true);
    }
  });

  it('a focused banner has a 0..1 focus and an uncropped source', () => {
    const focused = CATEGORIES.filter((c) => c.bannerFocusY != null);
    expect(focused.map((c) => c.id).sort()).toEqual(['bandai_premium', 'blind_box', 'digimon', 'hot_toys', 'lorcana', 'one_piece_tcg']);
    for (const c of focused) {
      expect(c.bannerFocusY).toBeGreaterThanOrEqual(0);
      expect(c.bannerFocusY).toBeLessThanOrEqual(1);
      expect(c.bannerImageUrl).not.toMatch(/fit=crop/);
    }
  });
});
