#!/usr/bin/env node
/**
 * Android / Google Play preflight.
 *
 * Run this before `eas build -p android --profile store` and before any
 * `fastlane supply` upload:
 *
 *     node scripts/preflight_android.mjs
 *
 * Why it exists
 * -------------
 * Every Android gap found on 2026-07-31 was silent. Nothing crashed, no build
 * failed, no test went red — the app just quietly did less on Android than on
 * iOS:
 *
 *   - EXPO_PUBLIC_REVENUECAT_ANDROID_KEY was never set, so initPurchases()
 *     returned early (src/lib/purchases.ts) and the paywall rendered its
 *     "unavailable" state. A shipped Android build could not take money.
 *   - No FCM config, so getExpoPushTokenAsync() threw into a catch and push
 *     never worked on Android.
 *   - The Play submit config pointed at a service-account JSON that did not
 *     exist, which only surfaces at upload time.
 *   - The listing screenshots violated two Play rules that are invisible
 *     locally and only rejected on upload.
 *
 * A checker is cheaper than finding these one at a time from a store rejection.
 * Each check names the exact file or command that fixes it.
 *
 * Exit code 0 = ready to build/submit. 1 = at least one blocker.
 * Checks needing network (the EAS env lookup) degrade to a warning offline.
 */

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const blockers = [];
const warnings = [];
const passes = [];

const fail = (m) => blockers.push(m);
const warn = (m) => warnings.push(m);
const pass = (m) => passes.push(m);

const readJson = (p) => JSON.parse(readFileSync(join(REPO, p), "utf8"));

// ───────────────────────────────────────────────────────────────────────────
// 1. app.json Android block
// ───────────────────────────────────────────────────────────────────────────
function checkAppConfig() {
  const app = readJson("app.json").expo ?? readJson("app.json");
  const android = app.android ?? {};

  if (!android.package) {
    fail("app.json: expo.android.package is missing — Play needs an application id.");
  } else {
    pass(`app.json android.package = ${android.package}`);
  }

  const icon = android.adaptiveIcon?.foregroundImage;
  if (!icon) {
    fail("app.json: expo.android.adaptiveIcon.foregroundImage is missing.");
  } else if (!existsSync(join(REPO, icon))) {
    fail(`app.json: adaptiveIcon.foregroundImage points at ${icon}, which does not exist.`);
  } else {
    pass("app.json adaptive icon present");
  }

  // expo-notifications needs FCM to hand out a token on Android. Without it
  // getExpoPushTokenAsync() throws and usePushNotifications swallows it.
  const hasGoogleServices =
    Boolean(android.googleServicesFile) ||
    existsSync(join(REPO, "google-services.json")) ||
    existsSync(join(REPO, "android/app/google-services.json"));
  const usesNotifications = (app.plugins ?? []).some((p) =>
    (Array.isArray(p) ? p[0] : p) === "expo-notifications",
  );
  if (usesNotifications && !hasGoogleServices) {
    fail(
      "FCM is not configured: no google-services.json and no expo.android.googleServicesFile in app.json.\n" +
        "        Android push notifications will silently never work (the token error is\n" +
        "        caught in src/hooks/usePushNotifications.ts). Fix: create a Firebase\n" +
        "        project, add an Android app for the package above, download\n" +
        "        google-services.json, then set expo.android.googleServicesFile and upload\n" +
        "        the FCM V1 service-account key with `eas credentials -p android`.",
    );
  } else if (usesNotifications) {
    pass("FCM config present for expo-notifications");
  }

  if (android.googleServicesFile && !existsSync(join(REPO, android.googleServicesFile))) {
    fail(`app.json: googleServicesFile points at ${android.googleServicesFile}, which does not exist.`);
  }
}

// ───────────────────────────────────────────────────────────────────────────
// 2. Play submit credentials
// ───────────────────────────────────────────────────────────────────────────
function checkSubmitCredentials() {
  const eas = readJson("eas.json");
  const paths = new Set();
  for (const profile of Object.values(eas.submit ?? {})) {
    const p = profile?.android?.serviceAccountKeyPath;
    if (p) paths.add(p);
  }
  if (paths.size === 0) {
    warn("eas.json declares no submit.*.android.serviceAccountKeyPath — `eas submit -p android` will prompt.");
    return;
  }
  for (const p of paths) {
    if (existsSync(join(REPO, p))) {
      pass(`Play service account key present (${p})`);
    } else {
      fail(
        `Play service account key missing: ${p}\n` +
          "        `eas submit -p android` and `fastlane supply` both fail without it.\n" +
          "        Fix: bash scripts/setup_play_store.sh (walks the GCP + Play Console steps).",
      );
    }
  }
}

// ───────────────────────────────────────────────────────────────────────────
// 3. RevenueCat Android key on the EAS production environment
// ───────────────────────────────────────────────────────────────────────────
function checkRevenueCatKey() {
  // Only meaningful if the app actually reads an Android key.
  const purchases = join(REPO, "src/lib/purchases.ts");
  if (!existsSync(purchases)) return;
  const src = readFileSync(purchases, "utf8");
  const match = src.match(/process\.env\.(EXPO_PUBLIC_REVENUECAT_ANDROID_KEY)/);
  if (!match) return;
  const varName = match[1];

  let out;
  try {
    out = execFileSync("npx", ["eas-cli", "env:list", "--environment", "production"], {
      cwd: REPO,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 90_000,
    });
  } catch {
    warn(`Could not reach EAS to verify ${varName} (offline or not logged in). Check manually.`);
    return;
  }

  if (out.includes(varName)) {
    pass(`${varName} is set on the EAS production environment`);
  } else {
    fail(
      `${varName} is NOT set on the EAS production environment.\n` +
        "        src/lib/purchases.ts selects this key on Android; empty means initPurchases()\n" +
        "        returns early and the subscription screen shows its unavailable state — an\n" +
        "        Android build that cannot take money.\n" +
        "        Fix: create the Android app in RevenueCat (Play package + Play service\n" +
        "        account), then:\n" +
        `        eas env:create --environment production --name ${varName} --value 'goog_...' --visibility sensitive`,
    );
  }
}

// ───────────────────────────────────────────────────────────────────────────
// 4. Play listing images
// ───────────────────────────────────────────────────────────────────────────
function checkPlayAssets() {
  const script = join(REPO, "scripts/prepare_play_assets.py");
  if (!existsSync(script)) return;
  for (const python of ["python3", "python"]) {
    try {
      execFileSync(python, [script, "--verify"], {
        cwd: REPO,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      });
      pass("Play listing images satisfy the Play Console limits");
      return;
    } catch (e) {
      const output = `${e.stdout ?? ""}${e.stderr ?? ""}`;
      if (e.code === "ENOENT") continue; // try the next interpreter
      const details = output
        .split("\n")
        .filter((l) => l.includes("FAIL"))
        .map((l) => `        ${l.trim()}`)
        .join("\n");
      fail(
        "Play listing images violate Play Console limits:\n" +
          `${details}\n` +
          "        Fix: python3 scripts/prepare_play_assets.py",
      );
      return;
    }
  }
  warn("Skipped Play image checks: no python interpreter found.");
}

// ───────────────────────────────────────────────────────────────────────────
// 5. Android hardware back button on modals
// ───────────────────────────────────────────────────────────────────────────
function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".git" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (/\.(tsx|jsx)$/.test(entry)) out.push(full);
  }
  return out;
}

function checkModalBackButton() {
  // On Android a react-native <Modal> without onRequestClose ignores the system
  // back button, so the user is trapped in the sheet. It is a no-op on iOS,
  // which is why this only ever shows up on Android.
  const roots = ["app", "src"].map((d) => join(REPO, d)).filter(existsSync);
  const offenders = [];
  for (const root of roots) {
    for (const file of walk(root)) {
      const src = stripComments(readFileSync(file, "utf8"));
      const re = /<Modal\b[^>]*>/g;
      let m;
      while ((m = re.exec(src)) !== null) {
        if (!m[0].includes("onRequestClose")) {
          const line = src.slice(0, m.index).split("\n").length;
          offenders.push(`${relative(REPO, file)}:${line}`);
        }
      }
    }
  }
  if (offenders.length) {
    fail(
      `${offenders.length} <Modal> without onRequestClose — the Android back button cannot dismiss them:\n` +
        offenders.map((o) => `        ${o}`).join("\n"),
    );
  } else {
    pass("every <Modal> handles the Android back button (onRequestClose)");
  }
}

// ───────────────────────────────────────────────────────────────────────────
// 6. react-native's SafeAreaView (iOS-only, silently a plain View on Android)
// ───────────────────────────────────────────────────────────────────────────
function checkSafeAreaImports() {
  // react-native's SafeAreaView applies insets on iOS and renders as a bare
  // View on Android, so a screen that looks correctly inset on iOS can sit
  // under the Android status bar / gesture nav with no warning.
  // docs/ui-playbook.md mandates react-native-safe-area-context.
  const roots = ["app", "src", "components"].map((d) => join(REPO, d)).filter(existsSync);
  const offenders = [];
  for (const root of roots) {
    for (const file of walk(root)) {
      const src = stripComments(readFileSync(file, "utf8"));
      const re = /import\s*\{([^}]*)\}\s*from\s*['"]react-native['"]/g;
      let m;
      while ((m = re.exec(src)) !== null) {
        if (/\bSafeAreaView\b/.test(m[1])) {
          const line = src.slice(0, m.index).split("\n").length;
          offenders.push(`${relative(REPO, file)}:${line}`);
        }
      }
    }
  }
  if (offenders.length) {
    fail(
      `${offenders.length} file(s) import SafeAreaView from 'react-native' — it is a no-op on Android:\n` +
        offenders.map((o) => `        ${o}`).join("\n") +
        "\n        Fix: import { SafeAreaView } from 'react-native-safe-area-context'",
    );
  } else {
    pass("SafeAreaView always comes from react-native-safe-area-context");
  }
}

// ───────────────────────────────────────────────────────────────────────────
// 7. accessibilityRole values Android rejects (HARD CRASH, not a no-op)
// ───────────────────────────────────────────────────────────────────────────

// Roles react-native accepts on Android (ReactAccessibilityDelegate.AccessibilityRole).
// Anything else throws IllegalArgumentException while creating the view, which is
// an uncatchable FATAL EXCEPTION on the main thread.
const ANDROID_ACCESSIBILITY_ROLES = new Set([
  "none", "button", "link", "search", "image", "imagebutton", "keyboardkey", "text",
  "adjustable", "header", "summary", "alert", "checkbox", "combobox", "menu",
  "menubar", "menuitem", "progressbar", "radio", "radiogroup", "scrollbar",
  "spinbutton", "switch", "tab", "tablist", "timer", "list", "grid", "pager",
  "scrollview", "horizontalscrollview", "viewgroup", "webview", "drawerlayout",
  "slidingdrawer", "iconmenu", "toolbar",
]);

function checkAccessibilityRoles() {
  // `tabbar` is iOS-only and crashed the app on 2026-08-01 (QuickNavBar.tsx).
  // This is the one member of the iOS-only family that does NOT degrade quietly.
  const roots = ["app", "src", "components"].map((d) => join(REPO, d)).filter(existsSync);
  const offenders = [];
  for (const root of roots) {
    for (const file of walk(root)) {
      const src = stripComments(readFileSync(file, "utf8"));
      const re = /accessibilityRole\s*[=:]\s*["']([a-zA-Z]+)["']/g;
      let m;
      while ((m = re.exec(src)) !== null) {
        if (!ANDROID_ACCESSIBILITY_ROLES.has(m[1])) {
          const line = src.slice(0, m.index).split("\n").length;
          offenders.push(`${relative(REPO, file)}:${line} — "${m[1]}"`);
        }
      }
    }
  }
  if (offenders.length) {
    fail(
      `${offenders.length} invalid accessibilityRole value(s) — these CRASH the app on Android:\n` +
        offenders.map((o) => `        ${o}`).join("\n") +
        '\n        Android throws IllegalArgumentException from ReactAccessibilityDelegate\n' +
        '        while creating the view — a FATAL EXCEPTION, not a warning.\n' +
        '        For a tab container use "tablist" (valid on both platforms).',
    );
  } else {
    pass("every accessibilityRole is valid on Android");
  }
}

// ───────────────────────────────────────────────────────────────────────────

checkAppConfig();
checkSafeAreaImports();
checkAccessibilityRoles();
checkSubmitCredentials();
checkRevenueCatKey();
checkPlayAssets();
checkModalBackButton();

console.log("Android preflight\n");
for (const p of passes) console.log(`  PASS  ${p}`);
for (const w of warnings) console.log(`  WARN  ${w}`);
for (const b of blockers) console.log(`  FAIL  ${b}`);

console.log("");
if (blockers.length) {
  console.log(`${blockers.length} blocker(s) — not ready for Google Play.`);
  process.exit(1);
}
console.log(`Android preflight passed${warnings.length ? ` (${warnings.length} warning(s))` : ""}.`);
