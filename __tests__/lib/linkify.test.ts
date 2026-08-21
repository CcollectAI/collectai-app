/**
 * The chat bubble's link splitter.
 *
 * Every case here is one the share sheet actually produces or that broke a
 * previous link-handling path in this repo: a url on its own line under a
 * title, a url followed by punctuation (which `inAppListingHref` matches
 * exactly, so a swallowed full stop routes to a browser instead of the
 * listing), and two messages in a row — the module-level /g regex keeps
 * `lastIndex` between calls unless it is reset.
 */
import { splitTextLinks } from '@/lib/linkify';

const LISTING = 'https://sparrowcollect.com/l/7bb1e6d6-2f7c-4c1e-9a8b-1f2e3d4c5b6a';

describe('splitTextLinks', () => {
  it('returns nothing for empty input', () => {
    expect(splitTextLinks('')).toEqual([]);
    expect(splitTextLinks(null)).toEqual([]);
    expect(splitTextLinks(undefined)).toEqual([]);
  });

  it('leaves a message with no url as one plain segment', () => {
    expect(splitTextLinks('is this still available?')).toEqual([
      { text: 'is this still available?', isLink: false },
    ]);
  });

  it('splits the shape ShareToChatSheet sends', () => {
    const segs = splitTextLinks(`Charizard Base Set — €80.00\n${LISTING}`);
    expect(segs).toEqual([
      { text: 'Charizard Base Set — €80.00\n', isLink: false },
      { text: LISTING, isLink: true },
    ]);
  });

  it('does not swallow trailing punctuation into the url', () => {
    const segs = splitTextLinks(`look at ${LISTING}.`);
    expect(segs[1]).toEqual({ text: LISTING, isLink: true });
    expect(segs[2]).toEqual({ text: '.', isLink: false });
  });

  it('matches our own scheme too', () => {
    const segs = splitTextLinks('sparrow://item/abc123');
    expect(segs).toEqual([{ text: 'sparrow://item/abc123', isLink: true }]);
  });

  it('finds several links in one message', () => {
    const segs = splitTextLinks(`${LISTING} and https://example.com/x`);
    expect(segs.filter((s) => s.isLink).map((s) => s.text)).toEqual([
      LISTING,
      'https://example.com/x',
    ]);
  });

  it('does not lose the first link of the next message (regex lastIndex)', () => {
    const first = splitTextLinks(LISTING);
    const second = splitTextLinks(LISTING);
    expect(second).toEqual(first);
    expect(second[0].isLink).toBe(true);
  });
});
