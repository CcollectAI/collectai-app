import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * The List callback must see the catalogue match (2026-10-14).
 *
 * `match` is set when the title field BLURS — after the last edit that rebuilt
 * the submit `useCallback`. With `match?.item_key` missing from its deps, a
 * seller who typed the title last, saw the match, and tapped List sent no
 * `canonical_key`: the listing was created unmatched and never reached Target
 * Hit watchers, with nothing on screen to say so. Found by eslint
 * exhaustive-deps. A render test would need the action sheet, the blur and the
 * async match in one order; this reads the dependency array instead.
 */
describe('sell/new — submit callback dependencies', () => {
  const src = readFileSync(join(__dirname, '../../app/sell/new.tsx'), 'utf8');
  const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
  // The one deps array that starts with `canList` belongs to the submit callback.
  const deps = code.match(/\}, \[(canList,[^\]]*)\]\);/)?.[1] ?? '';

  it('finds the submit callback', () => {
    expect(deps).not.toBe('');
  });

  it.each(['match?.item_key', 'fromCollection', 'itemId'])('depends on %s, which the payload reads', (name) => {
    expect(deps.split(',').map((s) => s.trim())).toContain(name);
  });
});
