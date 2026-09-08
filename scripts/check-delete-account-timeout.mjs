#!/usr/bin/env node
/**
 * Account deletion must not run on the 5-second fast-read budget.
 *
 * httpClient's REQUEST_TIMEOUT_MS is 5 s, deliberately, so a user never watches
 * a slow spinner — and its own comment says endpoints that legitimately need
 * longer must pass `timeoutMs: LONG_REQUEST_TIMEOUT_MS` explicitly. Deletion
 * walks ~84 tables, each DELETE in its own savepoint, so it is a slow WRITE and
 * had no override.
 *
 * Measured on a device 2026-09-08: the server COMPLETED the deletion and the
 * client gave up at 5 s, so the user was shown "Error" for an account that was
 * already gone (verified server-side: admin/users/<id> -> 404). On an
 * irreversible action that is the worst possible mismatch — the user believes
 * their data survived, and a Play or App Store reviewer tapping Delete sees a
 * failure on the exact flow both stores require.
 *
 * Two things must hold, and the second is the subtle one:
 *   1. deleteAccount() passes an explicit long timeoutMs.
 *   2. The confirm handler distinguishes a TIMEOUT from a FAILURE. Even with a
 *      90 s budget a slow network can still time out, and "failed" would again
 *      be a lie about an irreversible action that may have succeeded.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const API = "src/api/miscApi.ts";
const UI = "src/components/settings/ProfileEditSection.tsx";

const api = readFileSync(join(ROOT, API), "utf8");
const ui = readFileSync(join(ROOT, UI), "utf8");
const fail = [];

const fn = api.match(/export async function deleteAccount\([\s\S]*?\n\}/);
if (!fn) {
  fail.push(`${API}: deleteAccount() not found — did it move? Update this check.`);
} else if (!/timeoutMs:\s*LONG_REQUEST_TIMEOUT_MS/.test(fn[0])) {
  fail.push(
    `${API}: deleteAccount() does not pass timeoutMs: LONG_REQUEST_TIMEOUT_MS.\n` +
      `        It would run on the 5 s fast-read default and report "Error" for\n` +
      `        deletions the server actually completed.`,
  );
}

if (!/e instanceof TimeoutError/.test(ui)) {
  fail.push(
    `${UI}: the delete handler does not distinguish a TimeoutError.\n` +
      `        A timeout must not be reported as a failed deletion — the server\n` +
      `        may have succeeded.`,
  );
}

if (fail.length) {
  console.error("FAIL  account deletion timeout contract:\n");
  for (const f of fail) console.error(`      ${f}`);
  process.exit(1);
}
console.log("PASS  account deletion uses a long timeout and reports timeouts honestly");
