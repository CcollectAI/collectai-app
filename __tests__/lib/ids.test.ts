/**
 * Seam gate for item-route identifier discrimination.
 *
 * The bug this pins (verified in production 2026-07-25): `/item/[id]` is keyed
 * by `items.id` (uuid), but three producers hand the app a `text` catalog key —
 * `alert_trigger_history.item_id`, `catalog_suggestions.mapped_item_key`, and
 * the push payload `data.item_id`. 58/58 non-null `alert_trigger_history` rows
 * were catalog keys. Interpolating one into `/item/[id]` makes PostgREST fail
 * with `22P02 invalid input syntax for type uuid`, which every call site
 * swallows as a `logger.warn` — the user sees an "Unknown item" shell.
 *
 * Teeth check: reverting `itemHref` to `` `/item/${id}` `` turns the four
 * catalog-key cases below red.
 */

import { isUuid, itemHref } from '@/lib/ids';

describe('isUuid', () => {
  it('accepts canonical 8-4-4-4-12 uuids', () => {
    expect(isUuid('4497d8bf-6e60-483a-ba97-1e3dfe6e6636')).toBe(true);
    expect(isUuid('BBB5736D-CEF7-4090-8B19-E86AB58F2256')).toBe(true);
  });

  it('rejects the catalog keys production actually stores', () => {
    // Real values from alert_trigger_history.item_id
    expect(isUuid('pokemon:base1-base1-99')).toBe(false);
    expect(isUuid('funko:vinyl-soda-se-joker-soda-chase')).toBe(false);
    expect(isUuid('yugioh:tcgplayer:228011:1st_edition')).toBe(false);
    expect(isUuid('watchlist_snipe:1673d0cc-81c3-4249-b1e1-5d83eabe5f8a')).toBe(false);
  });

  it('rejects empty, null and non-strings', () => {
    expect(isUuid('')).toBe(false);
    expect(isUuid(null)).toBe(false);
    expect(isUuid(undefined)).toBe(false);
    expect(isUuid(12345)).toBe(false);
  });
});

describe('itemHref', () => {
  it('routes a uuid to the owned-item screen', () => {
    expect(itemHref('4497d8bf-6e60-483a-ba97-1e3dfe6e6636')).toEqual({
      pathname: '/item/[id]',
      params: { id: '4497d8bf-6e60-483a-ba97-1e3dfe6e6636' },
    });
  });

  it('routes a catalog key to the catalog screen, NOT /item/[id]', () => {
    // This is the bug: these four used to become `/item/pokemon:base1-base1-99`
    // and hit 22P02.
    for (const key of [
      'pokemon:base1-base1-99',
      'funko:vinyl-soda-se-joker-soda-chase',
      'yugioh:tcgplayer:228011:1st_edition',
      'jp_event:anime-nyc-frieren-anime-nyc-2024-exclusive-mini-figure',
    ]) {
      expect(itemHref(key)).toEqual({
        pathname: '/catalog-item/[key]',
        params: { key },
      });
    }
  });

  it('returns null for a missing id so callers can render it non-tappable', () => {
    expect(itemHref(null)).toBeNull();
    expect(itemHref(undefined)).toBeNull();
    expect(itemHref('')).toBeNull();
    expect(itemHref('   ')).toBeNull();
  });

  it('forwards extras as params and drops empty ones', () => {
    expect(
      itemHref('pokemon:base1-base1-99', {
        title: 'Charizard',
        category: 'pokemon',
        image_url: undefined,
        rarity: '',
      }),
    ).toEqual({
      pathname: '/catalog-item/[key]',
      params: { key: 'pokemon:base1-base1-99', title: 'Charizard', category: 'pokemon' },
    });
  });
});
