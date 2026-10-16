import { readFileSync } from 'fs';
import { join } from 'path';

/** The app's minimum for a negative rating's reason must match the server's
 *  (GradeCreate, 2026-10-16) — a client below it gets a 422, above it blocks a
 *  reason the server would take. */
it('NEGATIVE_NOTE_MIN agrees between app/offers.tsx and the server', () => {
  const app = readFileSync(join(__dirname, '../../app/offers.tsx'), 'utf8').match(/const NEGATIVE_NOTE_MIN = (\d+);/)?.[1];
  const srv = readFileSync(join(__dirname, '../../server/app/features/p2p_offers_router.py'), 'utf8').match(/^NEGATIVE_NOTE_MIN = (\d+)$/m)?.[1];
  expect(app).toBeDefined();
  expect(app).toBe(srv);
});
