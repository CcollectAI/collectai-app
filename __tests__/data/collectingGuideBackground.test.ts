/**
 * The Background primers and the renderer that has to keep them readable.
 *
 * On 2026-08-16 the seven most-collected categories (pokemon, mtg, yugioh,
 * lorcana, digimon, one_piece_tcg, lego) got multi-paragraph beginner primers
 * — roughly 1,800-2,000 characters each covering eras, how the market works
 * and the vocabulary. The screen rendered `whatItIs` in ONE <Text>, so all four
 * paragraphs ran together into a wall that nobody reads. `app/guide/
 * [categoryId].tsx` now splits on blank lines.
 *
 * Two halves, and both can regress silently:
 *
 *   1. Someone reformats collectingGuides.ts and the `\n\n` separators
 *      collapse. tsc stays green; the page just goes back to a wall.
 *   2. Someone simplifies the screen back to a single <Text>. Same wall, and
 *      the content tests would all still pass.
 *
 * So this asserts the CONTENT shape and the RENDERER together. It deliberately
 * does not assert prose — only that a primer is long enough to need breaks and
 * actually has them.
 *
 * The price figures inside the primers were read off mv_catalog_item_price on
 * 2026-08-16 (Base Set holo Charizard €1,469 vs Blastoise €175, Black Lotus
 * €11,005, Enchanted Elsa €824, WarGreymon Rare Pull €1,760, OP01 Wave 1 box
 * €5,498, LEGO Inside Tour €6,996). Numbers cannot be pinned by a unit test —
 * re-verify them against the view before quoting new ones.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { COLLECTING_GUIDES } from '@/data/collectingGuides';

const SCREEN = path.join(__dirname, '../../app/guide/[categoryId].tsx');

/** The categories that carry an extended primer, by catalogue size. */
const PRIMER_CATEGORIES = [
  'pokemon',
  'mtg',
  'yugioh',
  'lorcana',
  'digimon',
  'one_piece_tcg',
  'lego',
] as const;

const paragraphs = (text: string) =>
  text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);

describe('collecting guide backgrounds', () => {
  it('the most-collected categories carry a multi-paragraph primer', () => {
    const thin = PRIMER_CATEGORIES.filter((id) => {
      const body = COLLECTING_GUIDES[id]?.whatItIs ?? '';
      return paragraphs(body).length < 3 || body.length < 1200;
    });
    expect(thin).toEqual([]);
  });

  it('no guide has a stray blank line that would render as an empty paragraph', () => {
    // `split` on a trailing or doubled separator yields an empty string, which
    // renders as a gap with nothing in it — visible, and nothing else catches
    // it. Comparing the raw split against the filtered one proves there is no
    // separator that produces nothing.
    const ragged = Object.entries(COLLECTING_GUIDES)
      .filter(([, g]) => g?.whatItIs)
      .filter(([, g]) => {
        const raw = g!.whatItIs!.split(/\n\s*\n/);
        return raw.length !== paragraphs(g!.whatItIs!).length;
      })
      .map(([id]) => id);
    expect(ragged).toEqual([]);
  });

  it('every background is trimmed and non-empty where it exists', () => {
    const bad = Object.entries(COLLECTING_GUIDES)
      .filter(([, g]) => g?.whatItIs !== undefined)
      .filter(([, g]) => {
        const body = g!.whatItIs!;
        return body.trim() !== body || body.trim().length === 0;
      })
      .map(([id]) => id);
    expect(bad).toEqual([]);
  });

  it('the guide screen still renders the background as separate paragraphs', () => {
    // The content above is worthless if the screen concatenates it again.
    const src = readFileSync(SCREEN, 'utf8');
    expect(src).toMatch(/guide\.whatItIs\.split\(\/\\n\\s\*\\n\/\)/);
    expect(src).toMatch(/bodyNext/);
  });
});
