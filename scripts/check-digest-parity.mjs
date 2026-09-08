#!/usr/bin/env node
/**
 * The weekly-digest toggle and the worker that fulfils it must agree.
 *
 * Two lists define one feature, in two languages, in two directories:
 *   - src/config/featureFlags.ts        FEATURE_WEEKLY_DIGEST  (shows the toggle)
 *   - server/workers/bake_orchestrator.py  _WEEKLY_WORKERS     (runs the worker)
 *
 * Either disagreement is a lie to the user, and neither errors on its own:
 *   flag ON  + worker OFF -> the toggle promises a digest nothing can send.
 *                            This is the state found on 2026-09-08.
 *   flag OFF + worker ON  -> digests arrive that the user has no way to stop,
 *                            which is worse: an unstoppable notification.
 *
 * This is the same shape as check:category-parity — two lists defining the same
 * thing, drifting silently.
 */
import { readFileSync } from 'node:fs';

const FLAGS = 'src/config/featureFlags.ts';
const ORCH = 'server/workers/bake_orchestrator.py';

const flagSrc = readFileSync(FLAGS, 'utf8');
const orchSrc = readFileSync(ORCH, 'utf8');

const flagMatch = flagSrc.match(/FEATURE_WEEKLY_DIGEST:\s*(true|false)/);
if (!flagMatch) {
  console.error(`FAIL  ${FLAGS} no longer declares FEATURE_WEEKLY_DIGEST.`);
  console.error('      The toggle is gated on it; renaming it silently un-gates nothing and breaks this gate.');
  process.exit(1);
}
const flagOn = flagMatch[1] === 'true';

// Find the _WEEKLY_WORKERS list body and ask whether the digest line is live
// (present and NOT commented out). A commented line is the disabled state.
const listMatch = orchSrc.match(/_WEEKLY_WORKERS[^=]*=\s*\[([\s\S]*?)\n\]/);
if (!listMatch) {
  console.error(`FAIL  ${ORCH} no longer defines _WEEKLY_WORKERS.`);
  process.exit(1);
}
const workerOn = listMatch[1]
  .split('\n')
  .some((line) => line.includes('insights_digest_worker') && !line.trim().startsWith('#'));

if (flagOn === workerOn) {
  console.log(
    `✓ digest parity — toggle ${flagOn ? 'shown' : 'hidden'}, worker ${workerOn ? 'scheduled' : 'not scheduled'}.`,
  );
  process.exit(0);
}

console.error('FAIL  weekly digest: the toggle and the worker disagree.');
console.error(`      ${FLAGS}: FEATURE_WEEKLY_DIGEST = ${flagOn}  (toggle ${flagOn ? 'VISIBLE' : 'hidden'})`);
console.error(`      ${ORCH}: insights_digest_worker ${workerOn ? 'SCHEDULED' : 'not scheduled'}`);
console.error(
  flagOn
    ? '      A visible toggle over an unscheduled worker promises a digest that never arrives.'
    : '      A scheduled worker under a hidden toggle sends notifications the user cannot turn off.',
);
process.exit(1);
