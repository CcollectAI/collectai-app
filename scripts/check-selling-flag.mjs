#!/usr/bin/env node
/**
 * Selling cannot be switched on into a 404.
 *
 * `SELLING_ENABLED` (src/config/featureFlags.ts) gates Item Detail's
 * "List for Sale" and "Unlist" buttons. Both call
 * dealsProvider.toggleForSale -> PUT /items/{item_id}/for-sale, and that
 * route NO LONGER EXISTS server-side — it is allowlisted in
 * scripts/api_drift_allowlist.txt precisely because the flag is false, so
 * nothing can reach it today.
 *
 * That makes the flag load-bearing in a way nothing else records. Flipping it
 * to true is a one-word change that ships two buttons which fail every tap,
 * and no existing gate would say a word: the drift audit stays green because
 * the entry is allowlisted, and the allowlist has no idea the flag moved.
 *
 * So this checks the pair, not either half:
 *   SELLING_ENABLED === true  AND  the route missing from api.lock  ->  fail.
 *
 * The fix when it fires is NOT to delete this check. It is to route listing
 * through the P2P flow that already works (app/sell/new -> createListing);
 * docs/P2P_MARKETPLACE_SPEC.md is explicit that `for_sale` is owned by
 * trg_sync_item_for_sale and must not be written directly.
 */
import { readFileSync } from 'node:fs';

const FLAG_FILE = 'src/config/featureFlags.ts';
const LOCK_FILE = 'scripts/api.lock.json';
const ROUTE = { method: 'PUT', path: '/items/{item_id}/for-sale' };

const flagSrc = readFileSync(FLAG_FILE, 'utf8');
const m = flagSrc.match(/export\s+const\s+SELLING_ENABLED\s*=\s*(true|false)/);
if (!m) {
  // Fail closed: if the declaration cannot be found it may have been renamed
  // or made dynamic, and a check that silently passes on a shape it does not
  // understand is worse than no check.
  console.error(`FAIL  ${FLAG_FILE}: could not find "export const SELLING_ENABLED = true|false".`);
  console.error('      If it was renamed or made dynamic, update this check.');
  process.exit(1);
}
const enabled = m[1] === 'true';

const lock = JSON.parse(readFileSync(LOCK_FILE, 'utf8'));
const present = (lock.routes ?? lock).some(
  (r) => r.method === ROUTE.method && r.path === ROUTE.path,
);

if (enabled && !present) {
  console.error('FAIL  SELLING_ENABLED is true, but the route its buttons call does not exist.');
  console.error(`      missing: ${ROUTE.method} ${ROUTE.path}  (not in ${LOCK_FILE})`);
  console.error('      Item Detail\'s "List for Sale" and "Unlist" would 404 on every tap.');
  console.error('      Route listing through the P2P flow (app/sell/new -> createListing)');
  console.error('      instead; for_sale is owned by trg_sync_item_for_sale — see');
  console.error('      docs/P2P_MARKETPLACE_SPEC.md. Do not delete this check.');
  process.exit(1);
}

console.log(
  present
    ? 'PASS  selling flag — the for-sale route exists; the flag is free to move.'
    : `PASS  selling flag — SELLING_ENABLED is false, so the missing ${ROUTE.method} ${ROUTE.path} is unreachable.`,
);
