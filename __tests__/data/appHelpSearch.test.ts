/**
 * Help search matches words, not fragments (2026-09-24: "Charizard ex" offered
 * the privacy/delete-account topic because "ex" is inside "export").
 */
import { searchAppHelp } from '@/data/appHelp';

describe('searchAppHelp', () => {
  it('a card name offers no help topic', () => {
    expect(searchAppHelp('Charizard ex')).toEqual([]);
  });
  it('still finds a topic by the start of a word', () => {
    expect(searchAppHelp('delet').length).toBeGreaterThan(0);
  });
  it('a real question still finds its topic', () => {
    expect(searchAppHelp('delete account').length).toBeGreaterThan(0);
  });
});
