/**
 * Market Movers display seam.
 *
 * `/catalog/top-movers` returns rows straight from the price rollup, and any
 * ref the catalog does not cover comes back with title/item_key/brand/image_url
 * all NULL. That is not rare: measured against prod on 2026-07-30,
 * direction=losers&window=30d returned 15 of 20 rows with a null title
 * (title_null tracks in_catalog=false exactly).
 *
 * So `moverTitle` is not a nicety — it is what most of that list renders. These
 * cases are the real `item_ref`s from that response. The QA checklist requires
 * movers show readable names, "not raw keys like base6-base6-8"; this pins it.
 */
// The PURE module, not the component. Importing these from
// MarketMoversSection executed that component's imports — and once it started
// reading useBillingLimits for the Pro gate, that meant loading the RevenueCat
// SDK, which jest cannot parse. The suite then fails to RUN, which looks like
// config noise rather than a broken test.
import { moverKey, moverTitle, humaniseMoverKey } from '@/components/marketplace/moverFormat';
import type { TopMover } from '@/api/dataMoatApi';

/** An uncatalogued row, exactly as the endpoint returns it. */
function uncatalogued(item_ref: string): TopMover {
  return {
    item_ref,
    category: item_ref.split(':')[0],
    item_key: null,
    title: null,
    brand: null,
    set_code: null,
    image_url: null,
    last_price: 0.02,
    comps_30d: 3,
    in_catalog: false,
  };
}

describe('moverKey', () => {
  it('strips the category namespace when item_key is null', () => {
    expect(moverKey(uncatalogued('mtg:msc-79-cosmic-crucible'))).toBe('msc-79-cosmic-crucible');
  });

  it('prefers item_key when the catalog supplied one', () => {
    expect(moverKey({ ...uncatalogued('mtg:x'), item_key: 'vis-78-elkin-lair' })).toBe(
      'vis-78-elkin-lair',
    );
  });
});

describe('moverTitle on real uncatalogued prod rows', () => {
  // ref -> what the user must see
  const cases: [string, string][] = [
    ['mtg:msc-79-cosmic-crucible', 'Cosmic Crucible'],
    ['mtg:msc-11-avenge', 'Avenge'],
    ['mtg:msc-10-silver-surfer-galactuss-herald', 'Silver Surfer Galactuss Herald'],
    ['mtg:msc-28-council-of-reeds', 'Council of Reeds'],
    ['mtg:msc-120-the-great-mound', 'The Great Mound'],
    ['mtg:msc-89-okoye-mighty-and-adored', 'Okoye Mighty and Adored'],
    ['mtg:msc-44-the-frightful-four', 'The Frightful Four'],
    // yugioh passcode form: leading numeric id, no set code
    ['yugioh:11471117-light-laser', 'Light Laser'],
  ];

  it.each(cases)('%s renders as "%s"', (ref, expected) => {
    expect(moverTitle(uncatalogued(ref))).toBe(expected);
  });

  it('never leaks a bare slug or an empty string', () => {
    for (const [ref] of cases) {
      const shown = moverTitle(uncatalogued(ref));
      expect(shown.trim()).not.toBe('');
      expect(shown).not.toMatch(/-/); // a hyphen means the slug came through raw
      expect(shown).not.toMatch(/:/); // a colon means the namespace came through
    }
  });

  it('uses the catalog title verbatim when present', () => {
    expect(
      moverTitle({ ...uncatalogued('mtg:vis-78-elkin-lair'), title: 'Elkin Lair', in_catalog: true }),
    ).toBe('Elkin Lair');
  });
});

describe('humaniseMoverKey', () => {
  it('falls back to the key rather than inventing a name', () => {
    // Nothing left after stripping the set code + collector number.
    expect(humaniseMoverKey('msc-79')).toBe('Msc 79');
    expect(humaniseMoverKey('12345')).toBe('12345');
  });

  it('keeps minor words lowercase except in first position', () => {
    expect(humaniseMoverKey('the-of-thing')).toBe('The of Thing');
  });
});
