/** A signed-out member's tab screens do not load (email-confirm walk, 2026-09-27). */
import { mayLoadSignedInData } from '../../src/lib/signedInLoad';

it('waits while auth resolves, unless the gate expired', () => {
  expect(mayLoadSignedInData(true, false, false)).toBe(false);
  expect(mayLoadSignedInData(true, true, false)).toBe(true);
});

it('loads for a signed-in member, never for a signed-out one', () => {
  expect(mayLoadSignedInData(false, false, true)).toBe(true);
  expect(mayLoadSignedInData(false, false, false)).toBe(false);
  expect(mayLoadSignedInData(false, true, false)).toBe(false);
});
