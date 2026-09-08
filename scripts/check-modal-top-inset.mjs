#!/usr/bin/env node
/**
 * A pageSheet Modal must handle the Android status bar.
 *
 * `presentationStyle="pageSheet"` is an **iOS-only** Modal API. On iOS the
 * sheet is inset from the top automatically. On Android the prop is ignored and
 * the Modal is full-screen, so a header styled with only `paddingVertical`
 * renders UNDERNEATH the status bar.
 *
 * Found on a device 2026-09-08 in the Delete Account modal
 * (ProfileEditSection): the close ✕ sat on top of the clock and the red
 * "Delete" confirm sat on the wifi/battery icons. The button was visible,
 * enabled, and **untappable** — the status bar swallowed the touch, the
 * request never fired, and nothing errored. That modal is the account-deletion
 * flow Google Play and the App Store both require, so it is exactly the screen
 * a reviewer taps.
 *
 * This is the top-edge sibling of check-tab-bar-inset.mjs, and the same family
 * as every other iOS-only API that silently no-ops on Android.
 *
 * A file passes if it shows ANY awareness of the top inset:
 *   - SafeAreaView from react-native-safe-area-context (NOT react-native's,
 *     which is itself iOS-only and renders as a plain View on Android)
 *   - useSafeAreaInsets()
 *   - StatusBar.currentHeight
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const SCAN = ["app", "src"];
const SKIP = /node_modules|__tests__|\.test\.tsx?$/;

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (SKIP.test(p)) continue;
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (/\.tsx$/.test(p)) out.push(p);
  }
  return out;
}

const offenders = [];
let scanned = 0;

for (const base of SCAN) {
  for (const file of walk(join(ROOT, base))) {
    const src = readFileSync(file, "utf8");
    if (!src.includes('presentationStyle="pageSheet"')) continue;
    scanned++;
    const handlesTopInset =
      /from\s+["']react-native-safe-area-context["']/.test(src) ||
      src.includes("useSafeAreaInsets") ||
      src.includes("StatusBar.currentHeight");
    if (!handlesTopInset) {
      const line = src.slice(0, src.indexOf('presentationStyle="pageSheet"')).split("\n").length;
      offenders.push(`${relative(ROOT, file)}:${line}`);
    }
  }
}

if (offenders.length) {
  console.error(
    `FAIL  ${offenders.length} file(s) render a pageSheet Modal with no top-inset handling:\n`,
  );
  for (const o of offenders) console.error(`        ${o}`);
  console.error(
    "\n      presentationStyle=\"pageSheet\" is iOS-only. On Android the Modal is\n" +
      "      full-screen and the header draws under the status bar — controls there\n" +
      "      are visible, enabled and untappable.\n" +
      "      Fix: add `Platform.OS === 'android' ? StatusBar.currentHeight ?? 0 : 0`\n" +
      "      to the header's paddingTop, or use SafeAreaView from\n" +
      "      react-native-safe-area-context.",
  );
  process.exit(1);
}

console.log(`PASS  modal top inset — ${scanned} pageSheet modal file(s) handle the Android status bar`);
