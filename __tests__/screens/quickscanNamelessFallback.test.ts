import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * A scan with no name is not a result (2026-10-14).
 *
 * On the emulator an unidentifiable photo came back with the name "null" at 0%
 * and still opened the result card — the low-confidence fallback only looked
 * at the price-band confidence. Both scan paths (gallery and camera) must also
 * hand off to Add manually when there is no name. The server now sends no name
 * for "null"/"unknown" placeholders (intake_router._real_name).
 */
describe('QuickScan — nameless scans fall back to Add manually', () => {
  const code = readFileSync(join(__dirname, '../../app/quickscan.tsx'), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');

  it('checks the name in BOTH low-confidence fallbacks', () => {
    const fallbacks = code.match(/if \(sr\.prediction\.confidence < LOW_CONFIDENCE_THRESHOLD[^{]*\{/g) ?? [];
    expect(fallbacks).toHaveLength(2);
    for (const f of fallbacks) expect(f).toMatch(/!sr\.prediction\.name\.trim\(\)/);
  });
});
