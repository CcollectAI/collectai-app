/**
 * Pins the Market Movers display-name derivation.
 *
 * GET /catalog/top-movers returns 20 rows; on 2026-07-25, 7 of them had
 * title: null / image_url: null / in_catalog: false — price data for an
 * item_ref the catalog has no row for (the known catalog-reachability gap in
 * CLAUDE.md). The fallback rendered the raw slug, so a third of the feed read
 * `95486586-elemental-hero-core`.
 *
 * The inputs below are the REAL slugs returned by production that day, not
 * invented ones — the point is that the derivation survives the shapes the
 * backend actually emits.
 */
import { humaniseMoverKey, moverTitle } from '@/components/marketplace/MarketMoversSection';

describe('humaniseMoverKey', () => {
  it('strips a leading yugioh passcode', () => {
    expect(humaniseMoverKey('95486586-elemental-hero-core')).toBe('Elemental Hero Core');
    expect(humaniseMoverKey('33166263-hyperinvoked-aeon')).toBe('Hyperinvoked Aeon');
    expect(humaniseMoverKey('3356494-galaxy-eyes-solflare-dragon')).toBe('Galaxy Eyes Solflare Dragon');
  });

  it('strips an mtg set code + collector number', () => {
    expect(humaniseMoverKey('tle-246-zuko-avatar-hunter')).toBe('Zuko Avatar Hunter');
    expect(humaniseMoverKey('msc-533-starks-ingenuity')).toBe('Starks Ingenuity');
    expect(humaniseMoverKey('rex-10-ellie-and-alan-paleontologists')).toBe('Ellie and Alan Paleontologists');
  });

  it('keeps minor words lowercase inside the title', () => {
    expect(humaniseMoverKey('78783557-veidos-the-eruption-dragon-of-extinction')).toBe(
      'Veidos the Eruption Dragon of Extinction',
    );
  });

  it('never returns an empty string — falls back to the key', () => {
    expect(humaniseMoverKey('12345')).toBe('12345');
    expect(humaniseMoverKey('')).toBe('');
  });

  it('does not invent a name when the catalog already supplied one', () => {
    const withTitle = { item_ref: 'yugioh:95486586-elemental-hero-core', item_key: null, title: 'Elemental HERO Core' };
    expect(moverTitle(withTitle as never)).toBe('Elemental HERO Core');
  });

  it('derives a name when the catalog supplied none', () => {
    const noTitle = { item_ref: 'yugioh:95486586-elemental-hero-core', item_key: null, title: null };
    expect(moverTitle(noTitle as never)).toBe('Elemental Hero Core');
  });
});
