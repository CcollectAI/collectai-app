/**
 * Pin the test-run timezone.
 *
 * Snapshots that render a timestamp bake the RENDERING machine's timezone into
 * the recorded output. `__tests__/components/sell.test.tsx` renders an
 * OfferTimeline whose fixture is `2026-03-10T12:00:00Z`, which is "12:00 PM" in
 * UTC and "01:00 PM" in CEST — so the suite was green in CI (UTC runners) and
 * red on a European dev machine, for a component with no bug in it.
 *
 * That failure mode is worse than a plain broken test: a test that passes in CI
 * and fails locally trains you to ignore local red, which is where the real
 * regressions show up first.
 *
 * This is a globalSetup rather than `"test": "TZ=UTC jest"` because it has to
 * hold however jest is started — `npm test`, a bare `npx jest`, an IDE runner,
 * or CI calling jest directly. Set here in the parent process, the workers
 * inherit it when they fork.
 *
 * UTC (not Europe/Amsterdam) so snapshots read the same as the ISO fixtures
 * that produce them, and so they stay stable across DST.
 */
module.exports = async () => {
  process.env.TZ = 'UTC';
};
