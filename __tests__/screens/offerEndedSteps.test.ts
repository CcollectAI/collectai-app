import { readFileSync } from 'fs';
import { join } from 'path';

/** A declined/cancelled/expired trade ended at Respond; the later steps must not
 *  render as if still to come (walked 2026-10-16). */
it('an ended trade shows only the Respond step', () => {
  const src = readFileSync(join(__dirname, '../../app/offer/[offerId].tsx'), 'utf8');
  expect(src).toMatch(/const dead = !open && !live && !done;/);
  expect(src).toMatch(/return dead \? all\.slice\(0, 1\) : all;/);
});
