/**
 * Category display labels.
 *
 * `v_category_summaries_v1` is defined as `SELECT ci.category AS id,
 * ci.category AS name, ...` — so `name` IS the raw slug. Any screen that renders
 * `summary.name` directly shows `action_figures` / `anime_bluray` to the user.
 * app/categories/index.tsx did exactly that in its card titles, accessibility
 * labels and search filter until 2026-07-30.
 *
 * The 54 slugs below are the live `SELECT DISTINCT category FROM category_items`
 * from prod, so this pins the real input set rather than a hand-picked sample.
 */
import { getCategoryById, type CategoryId } from '@/data/categories';
import { formatCategoryName } from '@/constants/categories';

// Mirrors categoryLabel() in app/categories/index.tsx.
function categoryLabel(id: string): string {
  return getCategoryById(id as CategoryId)?.name ?? formatCategoryName(id);
}

/** Live prod slugs: SELECT DISTINCT category FROM category_items (2026-07-30). */
const PROD_SLUGS = [
  'action_figures', 'anime_bluray', 'anime_figures', 'anime_ost_vinyl',
  'anime_soundtrack', 'bandai_premium', 'blind_box', 'bluray_steelbook',
  'city_pop_vinyl', 'comic_books', 'designer_toys', 'diecast',
  'digimon', 'disney', 'fragrances', 'funko',
  'ghibli', 'gunpla', 'hot_toys', 'jp_event',
  'jp_magazine', 'keycaps', 'kpop_lightsticks', 'kpop_merch',
  'lego', 'lorcana', 'loungefly', 'manga',
  'marvel_legends', 'mtg', 'nintendo_merch', 'one_piece',
  'one_piece_tcg', 'oop_board_games', 'pens', 'plush_collectibles',
  'pokemon', 'pop_fandom', 'retro_games', 'retro_handhelds',
  'retro_pokemon', 'scale_models', 'sneakers', 'sportscards',
  'taylor_swift', 'theme_park', 'vintage_cameras', 'vintage_toys',
  'vinyl_records', 'vtuber', 'warhammer', 'watches',
  'whiskey', 'yugioh',
];

describe('categoryLabel over the live 54 prod slugs', () => {
  it('covers exactly the slug count prod reports', () => {
    expect(PROD_SLUGS).toHaveLength(54);
  });

  it('never renders an underscore, and never renders empty', () => {
    for (const slug of PROD_SLUGS) {
      const label = categoryLabel(slug);
      expect(label.trim()).not.toBe('');
      expect(label).not.toContain('_');
    }
  });

  it('never leaves a lowercase first character', () => {
    for (const slug of PROD_SLUGS) {
      const first = categoryLabel(slug)[0];
      expect(first).toBe(first.toUpperCase());
    }
  });

  it('prefers the curated name over title-casing the slug', () => {
    // These have curated entries in @/data/categories and must not be
    // title-cased into "Pokemon" / "Lorcana".
    expect(categoryLabel('pokemon')).toBe('Pokémon Cards');
    expect(categoryLabel('manga')).toBe('Manga');
  });

  it('title-cases the uncurated tail rather than dropping it', () => {
    // `anime_bluray` is NOT in this group — it has a curated 'Anime Blu-rays'.
    expect(categoryLabel('action_figures')).toBe('Action Figures');
    expect(categoryLabel('vintage_cameras')).toBe('Vintage Cameras');
  });

  it('curated names win over title-casing wherever one exists', () => {
    // Regression guard: a curated entry must never be flattened by the
    // slug fallback. 'Anime Blu-rays' would become 'Anime Bluray'.
    expect(categoryLabel('anime_bluray')).toBe('Anime Blu-rays');
  });

  it('is safe on empty / unknown input', () => {
    expect(categoryLabel('')).toBe('');
    expect(categoryLabel('not_a_real_category')).toBe('Not A Real Category');
  });
});
